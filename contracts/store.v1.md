# store.v1 — the memory directory on disk

**Status:** DRAFT · **Governs:** everything under `~/.amplifier/memory/`
**Who builds against it:** the session modules, the CLI, the Phase 2 timer,
humans with an editor, and git.

## Purpose

The store is the seam every other part depends on: a directory of plain
text a human can `cat`, `grep`, edit, and `git log`. Its layout and entry
format are the contract. Nothing else about the system needs to be stable
if this is.

## Core

1. **Location.** `${AMPLIFIER_MEMORY_HOME:-~/.amplifier/memory}` — a git
   repository initialized by `amplifier-memory install`. Every mutation is
   one commit.
2. **Fixed layout.**
   ```
   MEMORY.md          always-loaded memories (Core §3–§4)
   topics/<slug>.md   long-tail notes, read on demand (§5)
   declined.md        suggestions the human said no to (§7)
   inbox.md           pending suggestions, Phase 2 only (suggestions.v1)
   usage.jsonl        append-only reads/loads log for staleness (§8)
   ```
   No other files are part of the contract. A file not listed here is not
   memory.
3. **MEMORY.md is a flat list of memories, one per line, capped at 200
   lines** (comments and blank lines count). A line is:
   ```
   - [m-017] never use tabs in YAML files; always two-space indentation
   ```
   `m-NNN` is a stable id assigned by code, never reused after `/forget`.
   Lines may be grouped under `## headings` chosen by the human or the
   assistant; headings count toward the cap. A topic pointer is an ordinary
   line: `- [m-031] YAML/JSON style conventions → topics/yaml-style.md`.
4. **The cap is enforced by the writer, not by advice.** A write that would
   exceed 200 lines is **refused** with an error naming the cap and the
   remedy (consolidate into a topic file, or `/forget` something). The
   assistant resolves it in the same turn; the human sees the refusal.
5. **Topic files** are markdown, at most 150 lines each, at most 50 files.
   Each begins with a one-line purpose. Over either limit the writer refuses
   as in §4. Topic files are read by ordinary file tools when relevant; they
   are never injected wholesale.
6. **Provenance lives in git.** Every write is one commit whose message
   carries: the id, the memory text, the **verbatim human quote** that
   justified it, the session id, and the writer (`human` for `/remember`,
   `assistant` for in-turn saves, `suggestion` for accepted inbox items).
   `amplifier-memory why m-017` is `git log --grep '\[m-017\]'`. No separate
   provenance store exists.
7. **declined.md** is an append-only list of suggestion texts (with the date
   and a one-line reason if given) that the human rejected. It is fed back
   to the Phase 2 prompt and matched exactly by code so nothing declined is
   proposed again. Declining is not forgetting: a declined suggestion was
   never in MEMORY.md.
8. **usage.jsonl** records `{ts, event: loaded|read, target: MEMORY.md|topics/<slug>.md, session_id}`.
   It exists only so staleness can be *reported* (cli.v1 §5): a topic file
   not read for 90 days is listed as "unused — keep?". Nothing is deleted
   automatically. The file is truncated to the last 90 days on each write.
9. **Two writers, one path.** Humans edit files directly or via the CLI; the
   assistant writes only through the deterministic writer (session.v1 §5).
   Both produce ordinary git commits. Hand edits are legitimate and need no
   ceremony — `git log` attributes them.
10. **Bounded by construction.** The store's size is bounded by §3, §5, §8,
    and the 30-day inbox expiry (suggestions.v1 §6). No garbage collector
    exists because nothing grows without a cap.

## Reserved

- **R1 — cap sizes.** 200 lines / 150 lines / 50 files are borrowed from
  Claude Code's shipped limits. Tune by evidence (owner's MEMORY.md hits the
  cap, or context cost is felt), never by taste.
- **R2 — per-line length.** Unbounded in v1; a line is one memory. Revisit
  if lines routinely exceed ~200 characters.

## Explicitly backlogged

- Project-scoped store in a repo (`.amplifier/memory/`) — see VISION.
- Encryption at rest — the directory has the same protection as the rest of
  `~/.amplifier`.

## Conformance

- Writer refuses the 201st MEMORY.md line with the named remedy; the 200th
  succeeds (discriminating pair).
- Writer refuses a topic file's 151st line and the 51st topic file.
- Every commit created by the writer has id, text, verbatim quote, session
  id, and writer in its message; `why <id>` returns it.
- `/forget` removes the line and commits; the id is never reassigned.
- `declined.md` exact-match blocks re-proposal (suggestions.v1 conformance).
- usage.jsonl truncates to 90 days; a topic unread for 90 days appears in
  `status` as stale; nothing is deleted.
- A fresh `install` produces exactly the §2 layout and one initial commit.

## Changelog

- 2026-09-06 — Initial draft.
