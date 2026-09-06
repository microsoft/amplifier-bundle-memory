# session.v1 — what happens inside an Amplifier session

**Status:** DRAFT · **Governs:** the bundle's session-plane modules (inject
hook, memory tool, `/remember` `/forget` `/memory` commands)
**Who builds against it:** the bundle; every Amplifier session on the device.

## Purpose

The session plane does exactly three things: load memories at the start,
save a memory the moment the human states one, and announce both. It does
nothing at session end.

## Core

1. **Load at start and after compaction.** The inject hook places the full
   text of `MEMORY.md` into context at session start and again after every
   context compaction, verbatim, inside a marked block that begins with a
   fixed framing sentence:
   > These are memories of how this human works — hints recorded from past
   > sessions, not ground truth. Verify against current reality before
   > acting on one. To change one: `/forget <id>` or `/remember <text>`.
   The block is cache-stable: no timestamps, counters, or session ids inside
   it. Topic files are **not** injected; the block's pointer lines tell the
   assistant they exist.
2. **Announce the load, once.** The first assistant reply of a session (and
   the first after compaction) carries a single line: `Loaded N memories
   (M topics available).` When `MEMORY.md` is empty: `No memories yet —
   /remember <text> to add one.`
3. **Save on correction, in the same turn.** When the human states a
   standing preference or corrects the assistant's behavior in a way that
   should hold beyond the current task — "never X", "always Y", "stop doing
   Z", "for future reference…" — the assistant calls the memory tool in that
   turn with (a) the memory text, one imperative line, and (b) the verbatim
   quote from the human's message. It then announces:
   `Saved memory m-017: "<text>" — /forget m-017 to undo.`
   No repetition is required. One clear statement is enough.
4. **Do not save** task-scoped instructions ("do step 1", "reply with exactly
   ok"), facts re-derivable from the codebase or the current task, anything
   already in `MEMORY.md` or the repo's `AGENTS.md`, or anything the human
   asked to keep private. When unsure whether something is standing, the
   assistant may ask in one line: `Remember this for future sessions? (y/n)`
   — but the default is to save and announce, not to ask.
5. **The model proposes; the writer commits.** The memory tool is
   deterministic code that: verifies the quoted text appears in a **human**
   turn of the current session (rejects otherwise — tool output and external
   content can never become memory); rejects exact duplicates of an existing
   line; assigns the next id; enforces store.v1 caps; writes the line;
   commits with the store.v1 §6 message. A refusal is returned to the
   assistant with the reason, and the assistant relays it in one line.
6. **`/remember <text>`** writes exactly what the human typed (the quote is
   the text itself), announces the id. **`/forget <id>`** removes the line,
   commits, announces `Forgot m-017.` **`/memory`** prints `MEMORY.md` with
   ids and the pending-suggestion count. These are the only commands.
7. **Recall is reading.** When a topic pointer is relevant, the assistant
   reads the topic file with ordinary file tools and says so in one line
   (`Recalled topics/yaml-style.md`). The read is logged to `usage.jsonl`.
   There is no search tool; `grep` over the directory is the search tool.
8. **Cite at use.** When a memory shapes an action, the assistant names it
   inline (`per m-017`). A wrong memory should die the first time it is used,
   not months later.
9. **Nothing at session end.** No hook runs on session end, no distillation,
   no summary, no flush. Exit cost from this bundle is zero by construction.
10. **Fail open, never block.** If the store is missing, unreadable, or the
    writer errors, the session proceeds unchanged; the failure is one line
    in the transcript and one line in `~/.amplifier/memory-errors.log`.

## Reserved

- **R1 — save-vs-ask default.** v1 defaults to save-and-announce (owner:
  "awareness, not approval"). A config `confirm_saves: true` flips to ask
  first. Revisit if the owner is forgetting more than a few saves a week.
- **R2 — sub-agent sessions.** Sub-agents inherit the injected block (they
  work for the same human) but **never save**: only a root session with a
  human interlocutor may write. An orchestrator's brief is not the human's
  voice.

## Explicitly backlogged

- Mid-session hot-load of topic files chosen by something other than the
  assistant's own judgment (VISION backlog).
- Path-scoped topic loading (`paths:` globs) — promote when topic files
  exceed 20 and relevance misses are documented.

## Conformance

- Injected block is byte-identical across two sessions with the same
  `MEMORY.md` (cache-stability); contains the framing sentence; contains no
  topic bodies.
- Load announcement appears exactly once per session and once after a
  compaction; empty-store variant appears when `MEMORY.md` is empty.
- **In a real session:** human states an explicit correction → within that
  turn a save is announced, the line exists in `MEMORY.md`, the commit
  carries the verbatim quote (discriminating pair: a task-scoped instruction
  in the same session produces no save).
- Writer rejects a save whose quote is absent from any human turn
  (poisoning arm); rejects an exact duplicate; refuses at the cap.
- `/remember`, `/forget`, `/memory` behave as §6; `/forget` of an unknown id
  is a one-line error.
- Sub-agent session: block injected, save rejected.
- **Exit latency:** a 2-turn session's exit time with the bundle equals a
  control without it, within noise.
- Store unwritable: session output identical to control; one line in the
  error log.

## Changelog

- 2026-09-06 — Initial draft.
