target: contracts/suggestions.v2.md

# suggestions.v3 candidate — tune the suggestion question (DRAFT)

## Exact change, sentence by sentence

### Change 1 — Core 3, the exact question and its ratification migration

Current text:

```
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
```

Replacement:

```
3. **One question, one call per session.** The prompt asks exactly: "From
   these human turns, list only lasting personal working preferences the
   human explicitly stated and clearly intended to guide future tasks.
   Conditional preferences qualify; no `always` or `never` keyword is
   required. Preserve each preference's stated scope, and let the latest
   explicit correction win. Each line must make sense on its own; omit it
   if its subject or scope is unclear. Do not mistake a request, design, configuration
   decision, or tentative exploration about the current project for a
   preference. Skip semantic duplicates of known or declined preferences.
   Quote each verbatim from a human turn. Known preferences: <MEMORY.md>.
   Declined preferences: <declined.md>." Output is structured (text +
   verbatim quote). The judge never invents criteria beyond that question.
   **Which model answers it** is resolved from the instance's `config.yaml`
   `llm: judge:`, in this order: `provider`/`model`/`bundle` when set; else
   the **role** — `fast` as shipped — resolved through the host's routing
   when it can (`amplifier run --model-role`); else the app's own default,
   inherited. **The shipped default is a role, never a provider id:** a
   provider id names one machine's account. The exact-prefix implementation
   of Core 2 keeps recognising the v1 and v2 question prefixes as well as
   this v3 prefix, so sessions spawned by any of those job versions remain
   excluded. On ratification, prompt-targeted tests and the suggestions
   conformance kit migrate their contract reference and exact-question
   extraction to `suggestions.v3.md`.
```

## Evidence — a cost paid

The accepted 2026-09-08 source analysis recorded 14 newly pending suggestions.
Most described the current project's scoped work, configuration, or workflow
rather than a lasting personal preference; one tentative workspace idea was
expanded into a universal teardown rule; and one concise-prompt suggestion
repeated an existing brevity memory. The same analysis found the input filter
passing older typed turns from a still-active long-running session. The latter
is a separately conforming recency fix: send and verify only typed turns in the
window, capped to the newest subset while preserving chronology. It needs no
candidate and is not changed here.

The underlying session text and raw evaluation output remain private; only
aggregate findings are reported here.
The first isolated comparison made 30 successful model attempts: eight real
session snapshots across three variants, plus three synthetic discriminating
cases across two variants. The revised question retained both planted
preferences and rejected a known paraphrase. It still emitted one
context-dependent line with an unresolved subject. That observed failure
motivates the standalone-line sentence above, whose follow-up results are
recorded separately. Eleven follow-up attempts with that sentence retained
the one confirmed real-session preference and both planted preferences,
rejected the known paraphrase, and omitted the unresolved-reference proposal.
The follow-up reused the already-inspected holdout: it is revalidation, not
a fresh unseen test. These small samples are not a general quality guarantee.

## What does NOT change

- Capture remains global across qualifying sessions, using local files only;
  per-store origins remain authoritative and an absent origin record still
  counts as `human`.
- The existing 24-hour, 30-session, two-typed-turn, call-count, and request
  bounds remain fixed. The independently conforming recency fix only limits
  which in-window typed turns are sent and verified.
- Human approval remains required before any memory write; structured text and
  a verbatim human-turn quote remain required; one model call is still made per
  session; and no persona inference is introduced.
- Code keeps the existing exact verification and duplicate mechanisms. The new
  semantic-duplicate instruction is for the single judge question, not a new
  semantic code heuristic.
- This file is experimental only. `suggestions.v2.md`, including its pinned
  Core 3 question, remains untouched unless the steward ratifies this proposal.

## Steward's word

- [x] ratified
- [ ] ratified with edits
- [ ] declined
- [ ] later

## Ratification record

- 2026-09-08 — The Core 3 replacement question was ratified.