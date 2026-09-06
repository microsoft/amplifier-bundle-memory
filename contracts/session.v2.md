# session.v2 — what happens inside an Amplifier session (FROZEN 2026-09-06)

**Governs:** the bundle's session-plane modules (inject
hook, memory tool, `/remember` `/edit` `/forget` `/memory` commands)
**Who builds against it:** the bundle; every Amplifier session on the device.
**Supersedes:** `session.v1.md` (locked 2026-09-06 14:28; changed by the
ratified proposal `session.v1.v2-candidate.md`).

## Purpose

The session plane does exactly three things: load memories at the start,
save a memory the moment the human states one, and announce both. It does
nothing at session end. What the human reads about memory is rendered by
code, once, and is never restated by the model.

## Core

1. **Loaded in every request.** The inject hook places the full text of
   `MEMORY.md` into context, verbatim, so that it is present in every model
   request of the session — the first, and every one after a context
   compaction — inside a marked block that begins with a fixed framing
   sentence:
   > These are memories of how this human works — hints recorded from past
   > sessions, not ground truth. Verify against current reality before
   > acting on one. To change one: `/forget <id>`, `/edit <id> <text>` or
   > `/remember <text>`.
   The block is cache-stable: no timestamps, counters, or session ids inside
   it, and **no announce instruction**. Topic files are **not** injected; the
   block's pointer lines tell the assistant they exist.
2. **Announce the load, once, in code.** The inject hook renders one line to
   the human through the runtime's user-message channel on the first model
   request of a session and on the first after a compaction — never by
   instructing the model:
   `3 memories loaded. /memory to see them.` — topics named only when more
   than zero: `3 memories loaded, 2 topics. /memory to see them.`; singular
   `1 memory loaded.`; after a compaction `context compacted. 3 memories
   still loaded.`; when `MEMORY.md` is empty `no memories yet. Tell me a
   standing preference — "never use tabs in YAML" — and I'll keep it in every
   session on this device.`
3. **Save on correction, in the same turn.** When the human states a
   standing preference or corrects the assistant's behavior in a way that
   should hold beyond the current task — "never X", "always Y", "stop doing
   Z", "for future reference…" — the assistant calls the memory tool in that
   turn with (a) the memory text, one imperative line, and (b) the verbatim
   quote from the human's message. The tool result is the receipt, three
   lines, never restated by the model:
   ```
   saved m-017 — /forget m-017 to undo.
     <the memory text, unquoted, on its own line>
     your words, verbatim
   ```
   The third line reads `my wording, your go-ahead: "<the quote>"` when the
   writer is `assistant`. When the human approves several drafted lines at
   once ("remember these"), each is saved one call at a time and the last
   result adds `saved N memories — my wording, your go-ahead: "<quote>".
   Reword any line and I'll replace it; /forget <id> drops one.` followed by
   the lines. No repetition is required. One clear statement is enough.
4. **Do not save** task-scoped instructions ("do step 1", "reply with exactly
   ok"), facts re-derivable from the codebase or the current task, anything
   already in `MEMORY.md` or the repo's `AGENTS.md`, or anything the human
   asked to keep private. When unsure whether something is standing, the
   assistant may ask in one line: `Remember this for future sessions? (y/n)`
   — but the default is to save and announce, not to ask. The assistant never
   tells the human it cannot save what they approved: a drafted line the
   human says yes to is saved with the approval as its quote.
5. **The model proposes; the writer commits.** The memory tool is
   deterministic code — the `amplifier_memory` library's writer, shared with
   the CLI — that: verifies the quoted text appears in a **human**
   turn of the current session and is long enough to identify one (rejects
   otherwise — tool output and external content can never become memory);
   rejects exact duplicates of an existing line; assigns the next id;
   enforces store caps; writes the line atomically under a lock; commits with
   the store §6 message; re-reads what it wrote before reporting success. A
   refusal is returned to the assistant as one line, and the assistant relays
   it unchanged:
   `not saved — MEMORY.md is full (200 of 200 lines). /forget one you no
   longer need, or ask me to move a group into a topic file.` ·
   `already remembered as m-003 — nothing changed.` ·
   `can't save that one — you haven't said it in your own words yet. Type it
   and I'll record it verbatim.` · any other failure:
   `not saved — nothing changed, nothing lost. Details:
   ~/.amplifier/memory-errors.log`.
6. **Commands.** **`/remember <text>`** writes exactly what the human typed
   (the quote is the text itself). **`/edit <id> <text>`** replaces one
   memory's text keeping its id; the commit carries the old text (`was:`)
   and the new; the receipt is `edited m-004 — was: "<old>"` then
   `  now: <new>`. **`/forget <id>`** removes the line and commits; the
   receipt is `forgot m-002 — still in git: amplifier-memory why m-002` then
   the removed text on its own line. **`/memory`** renders `MEMORY.md` with
   ids, `-` bullets, `N memories` (singular `1 memory`), topics named only
   when more than zero, and the line `edit by hand: $EDITOR
   ~/.amplifier/memory/MEMORY.md`; the model does not restate it. These are
   the only commands; they are user-invocable skills shipped by the bundle,
   and the writer applies §5's human-turn check to them like any other save.
   **Ids are the only names:** a bare number `N` means `m-00N`, never a
   position in a list; a destructive command that cannot resolve its id asks
   (`no memory m-004 — forgotten 2026-09-06. Current: m-003, m-005. Say the
   id.`) and never guesses. No receipt carries a commit sha, a phase name, a
   zero-valued count, or a `<placeholder>`.
7. **Recall is reading.** When a topic pointer is relevant, the assistant
   reads the topic file with ordinary file tools and says so in one line
   (`Recalled topics/yaml-style.md`). The read is logged to `usage.jsonl`.
   There is no search tool; `grep` over the directory is the search tool. A
   ruleset or anything longer than one line is saved to `topics/<slug>.md`
   plus one pointer line in `MEMORY.md`, never squeezed into a line.
8. **Cite at use, and count it.** When a memory changes what the assistant
   would otherwise have done, it says so inline (`going long here, per
   m-004`). The tool records each citation as a `cited` usage event (store
   §8) and `amplifier-memory status` shows the citation rate. The rate is a
   floor, never an estimate; this contract promises the instrument, not the
   rate. A wrong memory should die the first time it is used, not months
   later.
9. **Nothing at session end.** No hook runs on session end, no distillation,
   no summary, no flush. Exit cost from this bundle is zero by construction.
10. **Fail open, never block.** If the store is missing, unreadable, or the
    writer errors, the session proceeds unchanged; the failure is one line
    in the transcript and one line in `~/.amplifier/memory-errors.log`. A
    byte that does not decode is shown as U+FFFD and named by `doctor`; it
    never raises inside the hook or the tool.

## Reserved

- **R1 — save-vs-ask default.** v2 keeps save-and-announce (unanimous across
  the 2026-09-06 reviews: "a confirm is a preamble"). A config
  `confirm_saves: true` flips to ask first. Revisit if the owner is
  forgetting more than a few saves a week.
- **R2 — sub-agent sessions.** Sub-agents inherit the injected block (they
  work for the same human) but **never save**: only a root session with a
  human interlocutor may write. An orchestrator's brief is not the human's
  voice.
- **R3 — hints or instructions.** The framing sentence calls memories hints.
  Whether behavioural memories should be framed as instructions is decided by
  the citation data from §8, not before it.

## Explicitly backlogged

- Mid-session hot-load of topic files chosen by something other than the
  assistant's own judgment (VISION backlog).
- Path-scoped topic loading (`paths:` globs) — promote when topic files
  exceed 20 and relevance misses are documented.
- A deterministic `/memory` that costs no model round trip — blocked on the
  CLI's command registry being open to bundles; asked for, not depended on.

## Conformance

- Injected block is byte-identical across two sessions with the same
  `MEMORY.md` (cache-stability); contains the framing sentence; contains no
  topic bodies and no announce instruction.
- The announce line renders in a real PTY session exactly once on the first
  request and once after a compaction (device-checked), with the exact text of
  §2; a reply constraint on the human's turn does not suppress it.
- Every receipt in §3, §5 and §6 is byte-identical to a fixture and contains
  no commit sha, no phase name, no zero-valued count, no `<placeholder>`.
- **In a real session:** human states an explicit correction → within that
  turn a save is announced, the line exists in `MEMORY.md`, the commit
  carries the verbatim quote (discriminating pair: a task-scoped instruction
  in the same session produces no save).
- Writer rejects a save whose quote is absent from any human turn or too
  short to identify one (poisoning arm); rejects an exact duplicate; refuses
  at the cap; refuses a text that is not one line.
- `/remember`, `/edit`, `/forget`, `/memory` behave as §6; `/edit` keeps the
  id and `why` shows `was:`/`now:`; `/forget` of an unknown id is the §6
  one-line refusal naming the current ids.
- `/memory` costs one model round trip and the listing shown equals the file.
- A `cited` event is written when the assistant names a memory at use;
  `status` prints the rate.
- Sub-agent session: block injected, save rejected.
- **Exit latency:** a 2-turn session's exit time with the bundle equals a
  control without it, within noise.
- Store unwritable: session output identical to control; one line in the
  error log.

## Changelog

- **2026-09-06 — v2 locked (FROZEN 2026-09-06).** The steward's word,
  verbatim "lgtm, do it", is recorded in `docs/workflow/OWNER-RETURN-LOG.md`
  (entry 2026-09-06 20:55). Ratifies `session.v1.v2-candidate.md` as written:
  §2 rendered by the hook, not instructed; §3 three-line receipt with
  provenance; §5 refusals as exact one-liners; §6 adds `/edit`, receipts echo
  text, ids-only rule; §7 topic-file path; §8 measured, not promised; §10
  tolerant reads; R3 added. Evidence: the steward's transcript of 2026-09-06
  and the four reviews in `docs/workflow/reviews/`.
- 2026-09-06 — v1 locked; see `session.v1.md`.
