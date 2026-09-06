# amplifier-memory — Vision

**Status:** DRAFT — awaiting owner ratification. Amendments to this page are
recorded in the Changelog, never feature status.

## The one sentence

A human working with Amplifier says a standing preference **once**, sees it
saved, and never has to say it again — in any session, on any project, on
this device.

## Why this exists

Every long-running Amplifier user repeats the same handful of corrections:
"don't use tabs in YAML", "the test suite must be fully green, not just
no-regressions", "Samuel Lee is not the Sam we present to." Each repetition
costs attention and each miss costs a turn. The fix is not a smarter model;
it is a small, always-present file the model reads every session and writes
to the moment it is corrected.

## What memory IS here

**Memory is a file.** One directory of plain markdown under git:
`~/.amplifier/memory/`. A capped `MEMORY.md` is loaded into every session,
verbatim, framed as *memories — hints to verify against current reality*.
Topic files hold the long tail and are read on demand. Git is the audit log,
the revert mechanism, and the "why". There is no database, no embeddings, no
consolidation daemon, no scoring, and nothing that runs when a session ends.

## How it learns

1. **In the turn, on the correction.** When the human states a standing
   preference or corrects the assistant, the assistant saves it *right then*
   and says so: `Saved memory m-017: "never use tabs in YAML; two-space
   indent" — /forget m-017 to undo.` One statement is enough. There is no
   accumulation gate: people say standing preferences once, usually while
   annoyed, and expect them honored.
2. **By hand, in one line.** `/remember <text>` writes exactly what the human
   typed. The highest-precision write path there is.
3. **By suggestion, once a day (Phase 2).** A plain timer reads yesterday's
   session transcripts and proposes the explicit standing corrections it
   finds — verbatim, cited — into an inbox. The next session announces
   "3 memory suggestions pending — `/memory review`." Accept or decline each
   with one keystroke. Declined suggestions are never re-proposed. This is
   the *only* automation in the system, and it proposes; it never mints.

## Principles

1. **Write on the correction, announce every write.** Awareness is the human
   seeing the save happen in the transcript, with the undo command attached
   — not approving each one, and not discovering it weeks later.
2. **A hard cap, loudly enforced.** `MEMORY.md` is at most 200 lines. Over
   the cap, writes are *refused* with an error the assistant must resolve by
   consolidating into topic files. Context is finite; an unbounded store is
   actively harmful.
3. **Memories are hints.** Every injected block and every recall says so. The
   assistant verifies against current reality before acting on one.
4. **The model proposes; code commits.** Deterministic code assigns ids,
   validates format, enforces the cap, refuses duplicates, and makes the git
   commit. The model never edits the store directly.
5. **Only the human's own words become memory.** A save must cite a verbatim
   quote from a human turn; code checks the quote exists before committing.
   Tool output and external content can never become a standing rule.
6. **Never store what can be re-derived.** Not the codebase, not the current
   task, not what `AGENTS.md` already says.
7. **Inspectable by `cat`, revertible by `/forget`, explained by `git log`.**
   `amplifier-memory why m-017` is `git log --grep`. Nothing is hidden in a
   service.
8. **Nothing runs at session end.** Sessions that crash, camp for weeks, or
   never exit lose nothing and pay nothing — the write already happened.
9. **Measure the only thing that matters: memories the human keeps.**
   Written, kept at 7 and 30 days, forgotten, loaded. If a week of real use
   yields fewer than five kept memories, the system is broken, whatever the
   tests say.

## Deliberately resists

- **A resident server or daemon.** Phase 2 is a timer that runs and exits.
- **Consolidation machinery** — epochs, evidence ladders, repetition
  thresholds, tombstones, fingerprints, semantic clustering, pending pools.
  A one-shot signal needs none of it.
- **Vector search or embeddings.** `MEMORY.md` + `grep` + on-demand reads.
- **Approval gates on writes.** Announce and undo, not approve.
- **Silent anything.** Every save, forget, load, suggestion, and refusal is
  visible in the transcript or the CLI.
- **Automatic deletion.** Staleness is *reported* ("unused 90 days —
  keep?"); a human decides.
- **Team or shared memory.** This is how *one human* works on *one device*.
  Sharing goes through the repo's `AGENTS.md`, by hand.
- **Network exposure.** Localhost files only. No wire face.

## Backlogged (promotion triggers, not roadmap)

- **Project-scoped memory** → the repo's `AGENTS.md` (already loaded by
  Amplifier). Promote when the first memory is clearly project-only and the
  owner asks for `/remember --project`.
- **Mid-session hot-load** of a topic file the assistant did not think to
  read. Promote on the first documented "the right topic existed, wasn't
  read, and the session needed it."
- **Cross-device sync** via the git remote. Promote when the owner works from
  a second device.

## Sequencing

**Phase 1 (A):** store + session behavior + CLI. Ships first. Success gate:
≥5 kept memories after 7 days of the owner's real use.
**Phase 2 (B):** the daily suggestion inbox. Contract written now;
implementation begins only after Phase 1's gate is met.

## Changelog

- 2026-09-06 — Initial draft, written fresh as the successor to the engram
  experiment. Design inputs: shipped-product convergence (Claude Code, VS
  Code, Gemini CLI, Copilot memory), the removal/demotion of auto-memory by
  Cursor and Windsurf, MemDelta/LoCoMo evidence that automatic extraction
  does not beat a curated file, and the owner's curated corpus.
