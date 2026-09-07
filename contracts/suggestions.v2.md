# suggestions.v2 — the daily suggestion inbox (Phase 2) (FROZEN 2026-09-07)

**Status:** FROZEN 2026-09-07 · **Governs:** `amplifier-memory suggest` and the timer that
runs it; `inbox.md`; `/memory review`
**Who builds against it:** the CLI, the timer unit, the session `/memory`
command. **Implementation begins only after Phase 1's gate is met (VISION
Sequencing).**

## Purpose

Some standing preferences are said in the flow of work and never saved in
the turn. Once a day, a plain job reads yesterday's transcripts, finds the
explicit corrections the assistant missed, and *proposes* them. It never
writes to `MEMORY.md`. A human accepts each with one keystroke, or declines
it once and never sees it again.

## Core

1. **A timer, not a service.** `amplifier-memory suggest` runs once a day from
   a systemd `--user` timer / launchd agent installed by `service install`,
   does its work, and exits. Nothing is resident. Localhost files only.
2. **Input: recorded sessions.** The job reads the context-intelligence
   bundle's local session capture
   (`${AMPLIFIER_CONTEXT_INTELLIGENCE_BASE_PATH:-~/.amplifier/projects}`) —
   a **required** dependency of Phase 2, never of Phase 1. "A human
   interlocutor" is made checkable: a session is read only when **both**
   hold. (a) **Its recorded origin is `human`** — from the instance's
   `sessions.jsonl` (store §2), written at start from
   `AMPLIFIER_SESSION_ORIGIN` (session §13); **no record counts as
   `human`**, so nothing is dropped for being unclassified and the filter
   improves as launchers adopt the variable. (b) **It has ≥2 human turns of
   typed text in the last 24 hours** — and two measured shapes are not typed
   text: a **lane brief** (a turn addressed to an agent, opening with a claim
   or work-item instruction — "Claim <id> from the <project> work-tracker
   project…") and a **system-reminder-only continuation**. Sessions spawned by
   this job or by sub-agents remain excluded. At most 30 sessions per run,
   most recent first. Sessions refused by origin are counted (§9).
3. **One question, one call per session.** The prompt asks exactly: "List
   the explicit standing preferences or corrections this human stated —
   things meant to hold beyond this task. Quote each verbatim from a human
   turn. Skip task instructions, facts about the code, and anything already
   in this list: <MEMORY.md> <declined.md>." Output is structured
   (text + verbatim quote). The judge never invents criteria beyond that
   question. **Which model answers it** is resolved from the instance's
   `config.yaml` `llm: judge:`, in this order: `provider`/`model`/`bundle`
   when set; else the **role** — `fast` as shipped — resolved through the
   host's routing when it can (`amplifier run --model-role`); else the app's
   own default, inherited. **The shipped default is a role, never a provider
   id:** a provider id names one machine's account.
4. **Code verifies before it proposes.** For each candidate: the quote must
   appear verbatim in a human turn of the named session (rejected
   otherwise); the text must not exactly match a `MEMORY.md` line or a
   `declined.md` entry; duplicates within the run are merged. Survivors are
   appended to `inbox.md` as:
   ```
   - [s-042] never use tabs in YAML; two-space indentation
     quote: "never use tabs in YAML files I ask you to write…"  session: bc214bdf  2026-09-05
   ```
5. **Surface without interrupting.** The next session's rendered load line
   (session.v2 §2 — code renders it, the model never says it) gains a second
   line: `3 suggestions waiting. /memory review to see them.` (singular
   `1 suggestion waiting.`; nothing when the inbox is empty). The
   job never injects suggestions into context; only accepted memories are
   loaded.
6. **Review is one keystroke per item.** `/memory review` (or
   `amplifier-memory review`) walks the inbox: **accept** writes the line
   through the same writer as session.v2 §5 (writer `suggestion`, quote and
   session carried into the commit) and removes it from the inbox;
   **decline** appends the text to `declined.md` with the date and removes
   it; **skip** leaves it. Items unreviewed for 30 days are dropped and
   counted in the next run's report.
7. **Never re-propose a decline.** Exact-match against `declined.md` in code
   (§4) plus the list in the prompt (§3). Reversal is by hand: delete the
   line from `declined.md`.
8. **Bounded cost, visible.** ≤30 model calls per run, one run per day.
   `doctor` shows last run, sessions read, candidates proposed, rejected by
   verification, and inbox size — **and names the judge**: the configured
   provider/model, or the role it resolved through, or `inherited` with the
   app's default and its measured per-call cost, so an unattended night's
   bill is never learned afterwards. Exceeding any bound skips and reports;
   it never queues.
9. **Report, even when empty.** Every run appends one line to
   `~/.amplifier/memory/suggest.log`: sessions read, **sessions refused by
   origin (`origin_excluded=N`, beside `sessions=`)**, proposed, rejected,
   dropped-as-stale. "0 proposed" is a normal, recorded outcome.
10. **Fail open.** Substrate missing, model unavailable, or malformed reply:
    the run records the failure and exits 0-for-the-timer; nothing is
    written to the inbox; `doctor` shows the degraded state.

## Reserved

- **R1 — the Phase 1 gate.** Implementation starts only when the owner's
  `status` shows ≥5 kept memories after 7 days of real Phase 1 use
  (VISION Sequencing). If Phase 1 alone already catches the corrections,
  Phase 2 may never be needed — that is a success, not a gap.
- **R2 — session window.** 24 hours / 30 sessions / ≥2 human turns are
  starting bounds; tune on `doctor` evidence.

## Explicitly backlogged

- Proposing *topic file* content (multi-line notes) — this version proposes single
  lines only.
- Reading the context-intelligence graph server instead of local files —
  optional accelerator, promote only if local reads become slow.

## Conformance

- Timer unit installs/uninstalls cleanly; nothing resident after a run.
- Discriminating pair on a fixture transcript: an explicit standing
  correction → appears in `inbox.md` with its verbatim quote; a task
  instruction in the same transcript → does not.
- A candidate whose quote is absent from human turns is rejected and counted
  (poisoning arm). A candidate matching `declined.md` or `MEMORY.md` is not
  proposed.
- Accept writes via the shared writer (commit carries writer `suggestion`,
  quote, session); decline appends to `declined.md`; a declined text is not
  re-proposed on the next run over the same transcript.
- 31-day-old inbox item is dropped and counted.
- Substrate missing → no inbox write, degraded state in `doctor`, run log
  line present.

## Changelog

- **2026-09-07 — v2 locked.** Ratified by the steward ("ratified",
  2026-09-07) from `suggestions.v1.v2-candidate.md`:
  - Core 2 makes "a human interlocutor" checkable: a session is read only
    when its recorded origin is `human` (no record counts as `human`) AND it
    has ≥2 human turns of typed text in 24 hours — a lane brief and a
    system-reminder-only continuation are not typed text.
  - Core 3 names which model answers the question: the instance's
    `config.yaml` `llm: judge:`, else the role (`fast` as shipped, never a
    provider id), else the app's inherited default.
  - Core 8 `doctor` names the judge, including an inherited default and its
    measured per-call cost.
  - Core 9's log line counts sessions refused by origin
    (`origin_excluded=N`, beside `sessions=`).
  Supersedes v1, which stays locked as the record of what earlier work was
  built against.
- 2026-09-06 — Initial draft.

- 2026-09-06 — ratified by the intent steward (bkrabach), one word: "ratified", on the
  manager session's ten-clause summary after the draft was refreshed to sit on session.v2
  (the pending line is rendered by code beside the load line; accept uses the v2 writer).
  The steward had already answered the priority call "do it" at 22:48Z: build Phase 2 now,
  waiving R1's day-7 gate — the gate belonged to them, and the reading at the moment of the
  waiver was kept 0 · cited 0/183 loads · baseline not given. Locked in this single write
  (H1 + status + this entry).
