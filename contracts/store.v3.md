# store.v3 — the memory directory on disk (FROZEN 2026-09-07)

**Governs:** everything under a memory instance (default `~/.amplifier-memory/`; §1)
**Who builds against it:** the session modules, the CLI, the Phase 2 timer,
humans with an editor, and git.
**Supersedes:** `store.v2.md` (locked 2026-09-06, amended 2026-09-07;
changed by the ratified proposal `store.v2.v3-candidate.md`).

## Purpose

The store is the seam every other part depends on: a directory of plain
text a human can `cat`, `grep`, edit, and `git log`. Its layout and entry
format are the contract. Nothing else about the system needs to be stable
if this is.

## Core

1. **Location — an instance.** A store is a directory, and there may be more than
   one. Resolved in order: an explicit `home` from the caller (the modules'
   mount-plan `config: home:`, or the CLI's `--home`), else `$AMPLIFIER_MEMORY_HOME`,
   else the default `~/.amplifier-memory`. Each is an independent instance — its own
   git repository, initialized by `amplifier-memory init`. **Migration:** when the
   default does not exist and `~/.amplifier/memory` does, the older path is the
   default; `init` offers to move it, and says so. Every mutation is
   one commit. Appends to `usage.jsonl` are the one exception: they are
   written without a commit, so a session that only *reads* memory leaves no
   commit behind. Everything a human would call a change — a save, an edit,
   a forget, a topic write — is still exactly one commit.
2. **Fixed layout.**
   ```
   MEMORY.md          always-loaded memories (Core §3–§4)
   topics/<slug>.md   long-tail notes, read on demand (§5)
   declined.md        suggestions the human said no to (§7)
   inbox.md           pending suggestions, Phase 2 only (suggestions.v2)
   usage.jsonl        append-only reads/loads/citations log (§8)
   config.yaml        this instance's configuration (§11) — NOT memory
   sessions.jsonl     one line per session seen — NOT memory
   ```
   No other files are part of the contract. A file not listed here is not
   memory. `.lock`, `.gitignore`, `config.yaml` and `sessions.jsonl` inside the
   store are plumbing, not memory: never injected, never suggested, never cited.
   `config.yaml` holds what shipped as `~/.amplifier/memory-config.toml` —
   `[llm.judge]` becomes `llm: judge:`, plus `enabled: true|false` (§11); the
   `.toml` is retired. `sessions.jsonl` records `{session_id, origin,
   first_seen}`, appended by the session hook at start, read by the suggest job.
3. **MEMORY.md is a flat list of memories, one per line, capped at 200
   lines** (comments and blank lines count). A line is:
   ```
   - [m-017] never use tabs in YAML files; always two-space indentation
   ```
   `m-NNN` is a stable id assigned by code, never reused after a forget,
   and kept across an edit. Lines may be grouped under `## headings` chosen
   by the human or the assistant; headings count toward the cap. A topic
   pointer is an ordinary line: `- [m-031] YAML/JSON style conventions →
   topics/yaml-style.md`. One memory is one line: the writer refuses a text
   containing a line separator or a control character, and a line over
   2,000 bytes.
4. **The cap is enforced by the writer, not by advice.** A write that would
   exceed 200 lines is **refused** with an error naming the cap and the
   remedy (consolidate into a topic file, or `/memory forget` something). The
   assistant resolves it in the same turn; the human sees the refusal.
5. **Topic files** are markdown, at most 150 lines each, at most 50 files.
   Each begins with a one-line purpose. Over either limit the writer refuses
   as in §4. Topic files are read by ordinary file tools when relevant; they
   are never injected wholesale. The writer can create one from a session
   (session.v4 §7): the file plus one pointer line, in one commit.
6. **Provenance lives in git.** Every write is one commit whose message
   carries: the id, the memory text, the **verbatim human quote** that
   justified it, the session id, the writer (`human` for `/remember` and
   `/memory edit`, `assistant` for in-turn saves, `suggestion` for accepted inbox
   items), and `action: save|edit|forget|topic`; an `edit` also carries
   `was: "<previous text>"`. A forget's first line reads `forgot [m-017] …`
   so a removal is never mistaken for a creation in `git log --oneline`.
   `amplifier-memory why m-017` is `git log --grep '\[m-017\]'`. No separate
   provenance store exists.
7. **declined.md** is an append-only list of declined suggestions, one per line:
   `- <YYYY-MM-DD> <text>  quote: "<quote>"` — the verbatim human quote after the
   text. Older two-field lines (`- <YYYY-MM-DD> <text>`) stay readable and keep
   working. It is fed back to the Phase 2 prompt and matched exactly by code on
   **text OR quote**, so a declined suggestion returning paraphrased is blocked. Declining is not forgetting: a declined suggestion was
   never in MEMORY.md.
8. **usage.jsonl** records `{ts, event: loaded|read|cited, target:
   MEMORY.md|topics/<slug>.md|m-NNN, session_id}`. `loaded` and `read` exist
   so staleness can be *reported* (cli.v3 §5): a topic file not read for 90
   days is listed as "unused — keep?". `cited` records each time the
   assistant names a memory at use (session.v4 §8) so `status` can derive a
   citation rate. Nothing is deleted automatically. The file is truncated to
   the last 90 days on each write, and is never committed.
9. **Two writers, one path.** Humans edit files directly or via the CLI; the
   assistant writes only through the deterministic writer (session.v4 §5).
   Both produce ordinary git commits. Hand edits are legitimate and need no
   ceremony — `git log` attributes them. The writer takes an exclusive lock
   for the length of one read-modify-write-commit, so concurrent writers
   serialize; an editor takes no lock, and damage from an editor save landing
   inside a write is named by `doctor` and restored by `doctor --repair`.
10. **Bounded by construction.** The store's size is bounded by §3, §5, §8,
    the 30-day inbox expiry (suggestions.v2 §6), and §1's exception for
    usage appends — git history grows only with changes a human made or
    approved. No garbage collector exists because nothing grows without a
    cap.
11. **`enabled: false` makes the instance inert.** Nothing injects, no memory
    tool is offered, no skills are advertised, and no timer runs against it.
    `doctor` names the instance as disabled rather than reporting it healthy.

## Reserved

- **R1 — cap sizes.** 200 lines / 150 lines / 50 files are borrowed from
  Claude Code's shipped limits. Tune by evidence (owner's MEMORY.md hits the
  cap, or context cost is felt), never by taste.
- **R2 — per-line length.** 2,000 bytes is a safety bound, not a style rule;
  a line is one memory. Revisit if lines routinely exceed ~200 characters.

## Explicitly backlogged

- Project-scoped store in a repo (`.amplifier/memory/`) — see VISION.
- Encryption at rest — the directory has the same protection as the rest of
  `~/.amplifier`.

## Conformance

- Writer refuses the 201st MEMORY.md line with the named remedy; the 200th
  succeeds (discriminating pair).
- Writer refuses a topic file's 151st line and the 51st topic file.
- Writer refuses a text containing any line separator or control character,
  and a text over 2,000 bytes, before anything is written (file hash
  unchanged; `git status` clean).
- Every commit created by the writer has id, text, verbatim quote, session
  id, writer and action in its message; an edit carries `was:`; a forget's
  subject begins `forgot`; `why <id>` returns them.
- `/memory forget` removes the line and commits; the id is never reassigned.
  `/memory edit` keeps the id.
- `declined.md` exact-match blocks re-proposal (suggestions.v2 conformance).
- usage.jsonl truncates to 90 days; a topic unread for 90 days appears in
  `status` as stale; nothing is deleted; a session that only loads adds no
  commit; a `cited` event is recorded when the assistant cites.
- Eight concurrent saves leave eight well-formed lines and eight commits with
  no id gap or duplicate; a save reports success only after re-reading the
  file it wrote.
- A fresh `init` produces exactly the §2 layout and one initial commit.

## Changelog

- **2026-09-07 — amended in place (still FROZEN 2026-09-07).** The steward's word,
  "Let's fix those wrinkles.", on `store.v3-candidate.md`: the header line now names
  an instance (default `~/.amplifier-memory/`, §1) instead of the pre-v3 path, and
  seven cross-references point at the current versions (session.v4, cli.v3,
  suggestions.v2). No clause changed.
- **2026-09-07 — v3 locked.** Ratified by the steward ("ratified",
  2026-09-07) from `store.v2.v3-candidate.md`:
  - §1 becomes an instance: an explicit `home` from the caller, else
    `$AMPLIFIER_MEMORY_HOME`, else the default `~/.amplifier-memory`, each its
    own git repository; `init` offers to move an older `~/.amplifier/memory`.
  - §2's layout gains `config.yaml` (this instance's configuration, §11) and
    `sessions.jsonl` (`{session_id, origin, first_seen}`) — both plumbing,
    neither memory; `~/.amplifier/memory-config.toml` is retired into
    `config.yaml`.
  - §7 `declined.md` carries the verbatim quote beside the text and is matched
    on text OR quote, so a paraphrased return is blocked.
  - New §11: `enabled: false` makes the instance inert — nothing injected, no
    tool, no skills, no timer, and `doctor` names it disabled.
  Supersedes v2, which stays locked as the record of what earlier work was
  built against.
- **2026-09-07 — amended in place (still FROZEN 2026-09-06).** The steward's
  word, verbatim "ratified", together with `session.v2.v3-candidate.md`;
  recorded in `docs/workflow/OWNER-RETURN-LOG.md` (entry 2026-09-07). Applies
  `store.v2-candidate.md`: four wording spots that named `/forget` and `/edit`
  now name `/memory forget` and `/memory edit` (session v3 §6). No promise
  added, removed or weakened; the layout, caps, provenance and ids are as
  they were.
- **2026-09-06 — v2 locked (FROZEN 2026-09-06).** The steward's word,
  verbatim "lgtm, do it", is recorded in `docs/workflow/OWNER-RETURN-LOG.md`
  (entry 2026-09-06 20:55). Ratifies `store.v1.v2-candidate.md` as written
  and writes down what waves 4–6 already made true: §1 usage appends without
  a commit; §3 one-line rule and byte cap; §5 topic write path; §6 `action`,
  `was:`, `forgot` subject; §8 `cited`; §9 the lock; §10 history bound.
  Evidence: four `usage: loaded` commits in one afternoon on the steward's
  store; the corruption of 2026-09-06 and its fix (CHECK-RECORD waves 4–5).
- 2026-09-06 — v1 locked; see `store.v1.md`.
