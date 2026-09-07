# Proposal: suggestions.v1 → v2 (CANDIDATE)

target: contracts/suggestions.v1.md

**Changes:** `contracts/suggestions.v1.md` (FROZEN 2026-09-06), which stays the law until the steward's
word lands below. Written 2026-09-07 by the manager session. **A version bump, not an amendment:** Core 2
narrows what may be read — sessions that reach the inbox today would stop — so v2. Vocabulary matches today's
siblings `store.v2.v3-candidate.md` (an INSTANCE is a directory with its own `config.yaml`; `sessions.jsonl`
is plumbing, `{session_id, origin, first_seen}`) and `session.v3.v4-candidate.md` §13
(`AMPLIFIER_SESSION_ORIGIN` — `human · worker · recipe · agent · eval` — recorded at start; unset = `human`).

## The exact change, sentence by sentence
### Change 1 — Core 2, which sessions are read
Current text — Core 2's second half; the clause's first sentence and path are unchanged:
```
   a **required** dependency of Phase 2, never of Phase 1. Only root
   sessions (a human interlocutor) with ≥2 human turns of activity in the
   last 24 hours are read; sessions spawned by this job or by sub-agents
   are excluded. At most 30 sessions per run, most recent first.
```
Replacement:
```
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
```
### Change 2 — Core 3, which model is the judge
Current text — the question itself is untouched, byte for byte; its last sentence gains a successor:
```
   (text + verbatim quote). The judge never invents criteria beyond that
   question.
```
Replacement:
```
   (text + verbatim quote). The judge never invents criteria beyond that
   question. **Which model answers it** is resolved from the instance's
   `config.yaml` `llm: judge:`, in this order: `provider`/`model`/`bundle`
   when set; else the **role** — `fast` as shipped — resolved through the
   host's routing when it can (`amplifier run --model-role`); else the app's
   own default, inherited. **The shipped default is a role, never a provider
   id:** a provider id names one machine's account.
```
### Change 3 — Core 8, bounded cost, visible
Current text — Core 8 after its ≤30 ceiling sentence, which is unchanged:
```
   `doctor` shows last run, sessions read, candidates proposed, rejected by
   verification, and inbox size. Exceeding any bound skips and reports; it
   never queues.
```
Replacement:
```
   `doctor` shows last run, sessions read, candidates proposed, rejected by
   verification, and inbox size — **and names the judge**: the configured
   provider/model, or the role it resolved through, or `inherited` with the
   app's default and its measured per-call cost, so an unattended night's
   bill is never learned afterwards. Exceeding any bound skips and reports;
   it never queues.
```
### Change 4 — Core 9, the log line
Current text — Core 9's field list:
```
   `~/.amplifier/memory/suggest.log`: sessions read, proposed, rejected,
```
Replacement:
```
   `~/.amplifier/memory/suggest.log`: sessions read, **sessions refused by
   origin (`origin_excluded=N`, beside `sessions=`)**, proposed, rejected,
```
## The evidence — a cost already paid
**The steward's own words, 2026-09-07, verbatim:**
- "many of the memory suggestions have come from sessions that my 'manager' sessions created as 'worker'
  sessions (or some may _also_ be subagent sessions, hard to tell, or recipe sessions or other 'spawned'
  sessions). The worker sessions are full tmux-launched sessions, so they don't have a parent session id, etc."
- "What is the shipped value for llm.judge? Since that is tied my provider id's, that obviously can't be what
  we ship, so I'm curious how that value is determined/set, per the contracts/code?"

**The first unattended timer night (2026-09-07 07:00Z)** logged `sessions=30 proposed=17
rejected=0 calls=30 provider=luna status=ok`. **6 of those 17 proposals came from one session,
6bafabaf** — a tmux-launched *worker* whose first "human" turn is a manager's brief ("Claim drumbeat-d4h
from the drumbeat work-tracker project…"). It passed every filter: `is_root_session_id` accepts a plain UUID
(`suggest.py:262-264`); `spawned_by_this_job` tests only this job's bundle markers and prompt prefix
(`:267-276`); `read_session` reads only `created`/`bundle` (`:216-259`) — no parent id exists on disk.

**The judge's model, measured.** `llm_config.py:62-64` carries `role` with `DEFAULT_ROLE = "fast"`,
but `flags()` emits only `-p/-m/-B` (`:85-99`), so the role never reaches the host and an unset
config silently inherits the app default. Three pilots, 430 calls, 7 models: every class at or above
low reasoning passes; **gpt-5.6-luna is perfect at $0.02/call**, the **inherited default (opus)
costs $0.276/call** — 13×, for no measured gain, chosen by nobody.
## What does NOT change
One question, one call per session, the prompt's sentence byte-identical (§3). Code verifies before
it proposes — verbatim quote in a human turn, no `MEMORY.md`/`declined.md` match, duplicates merged
— and the `inbox.md` line shape (§4). The pending line (§5). Review's three keystrokes and the 30-day
expiry (§6). Never re-propose a decline (§7). The 30-call ceiling, one run a day, skip-and-report over
budget (§8). Fail open (§10). The log's path and every field already in its line keep their spelling and
order. R1, R2, the backlog and Conformance stand — and against today's capture, where no `sessions.jsonl`
exists yet, a run reads exactly what it reads today.
## Steward's word
Answer in one word: **ratified** · **ratified with edits** · **declined** · **later**.

>
