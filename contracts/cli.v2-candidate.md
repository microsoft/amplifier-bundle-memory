# Proposal: amend cli.v2 in place (CANDIDATE)

target: contracts/cli.v2.md

**Changes:** `contracts/cli.v2.md` (FROZEN 2026-09-06). Written 2026-09-07 by the manager
session after wave 13 landed, from the steward's word of the same day. One verb learns one more
duty; no verb is added or removed; the opt-out that already exists stays the opt-out. Amends v2
in place. The original stays the law until the steward's word lands below.

## Target lines and exact changes

### Change 1 — §8, `init` (lines 64–67)

Current text:

```
8. **`init`** creates the store.v2 layout at the store location and makes
   the initial commit. Idempotent: a second run reports the store exists and
   changes nothing. It is the README's step 3 and the only setup Phase 1
   needs.
```

Replacement:

```
8. **`init`** creates the store.v2 layout at the store location and makes
   the initial commit, then installs the daily suggest timer exactly as
   `service install` does (§6) — a fresh install gets suggestions by
   default, with nothing further to type. It ends with two lines: what it
   installed, and how to turn it off (`amplifier-memory service uninstall`)
   or steer its cost (`~/.amplifier/memory-config.toml`, suggestions §8).
   Idempotent: a second run reports the store exists and the timer is
   installed, and changes nothing. Where Phase 2 is not installed it says
   so in the §6 words and installs no timer. `--no-timer` skips the timer
   for a host that must not run one. It is the README's step 3 and the only
   setup needed.
```

### Change 2 — §6, `service` (line 58, one sentence added)

Current text:

```
   rolls back written units if any step fails. Phase 1 has no service; the
   verb reports that plainly.
```

Replacement:

```
   rolls back written units if any step fails. Phase 1 has no service; the
   verb reports that plainly. `init` (§8) calls the same install; `service
   uninstall` is the opt-out for a store that `init` set up.
```

### Change 3 — Conformance, one added bullet

Insert in the `## Conformance` section:

```
- A fresh `init` on a Phase 2 host leaves the timer installed and enabled
  (`service status` says so; `doctor`'s suggest-timer row reads installed ·
  enabled) and prints the uninstall command and the config path; `init
  --no-timer` leaves no unit behind; a second `init` prints "store exists ·
  timer installed" and writes nothing; on a Phase 1 host `init` prints §6's
  no-service line and creates no unit.
```

## Evidence (a cost paid, in the steward's own words and on the steward's own device)

- **The steward's word, 2026-09-07:** *"yes, we do want to install the daily timer by default on a
  fresh install."* Asked as a priority call after the `[suggestions]` flag was withdrawn; nothing was
  parked on it; this is the answer.
- **The install was a gate nobody but a manager session could pass.** On this device the timer went
  in only after an explicit irreversible call (`PLAN.md` 2026-09-07T00:09:59Z) and the steward's
  "go for it all". An adopter following the README reaches `init` at step 3 and never sees
  suggestions unless they find `service install` at line 52. The product's second half — the part
  that proposes memories the human did not think to state — is off by default for everyone who
  does not read that far.
- **What it cost here:** the inbox stayed empty for the first day; the first unattended pass
  (2026-09-07T07:00:01Z, 30 calls, 17 suggestions, ~$0.60 at luna rates) happened only because the
  manager installed the timer by hand.
- **The cost is steerable and already visible**, so a default-on timer does not hide a bill: the
  LLM knob (`[llm.judge]`, lane R, item `ec7`) fixes provider/model per call; the suggest log names
  the provider used; `doctor` shows both; §8 of suggestions.v1 bounds a run at 30 calls. The `init`
  receipt names the config path so the first thing a new user reads after install is where the
  cost lever is.

## What does NOT change

§1 — the verb list is unchanged (`init` gains a duty and a flag, not a name). §2 `status`, §3 `why`,
§4 `review`, §5 `doctor`, §7 `update` (already "restarts the timer if installed"). `service
install` / `uninstall` behave exactly as today and remain the way to turn the timer on or off after
the fact. `suggestions.v1` in full: the job, the prompt, the 30-call ceiling, fail-open. `store.v2`
— the units live under `~/.config/systemd/user/`, outside the store, as they do now. Nothing writes
`memory-config.toml`; `init` names it, it does not create it.

## Steward's word

ratified by owner — 2026-09-07, in conversation: "ok, do it", answering a message that listed
both open candidates; read as ratifying the timer-by-default proposal, whose substance the steward had already given in words at 15:33Z ("yes, we do want to install the daily timer by default on a fresh install"). Applied in place with a changelog entry in the
same write.
