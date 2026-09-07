# Proposal: cli.v2 → v3 (CANDIDATE)

target: contracts/cli.v2.md

**Changes:** `contracts/cli.v2.md` (FROZEN 2026-09-06, amended in place twice on 2026-09-07 —
its Changelog, line 133). Written 2026-09-07 by the manager session; the original stays the law
until the steward's word lands below. **A version bump, not an amendment:** §8's default store
path changes and the config file it names is renamed and moved — v3. Siblings
`contracts/store.v2.v3-candidate.md` and `docs/VISION.v2-candidate.md` carry the same INSTANCE
vocabulary; this is its shell face and lands with them or not at all.

## The exact change, sentence by sentence

### Change 1 — Core 1, Verbs (a flag is added; the verb list does not grow)

Current text:

```
1. **Verbs.** `init` · `status` · `why <id>` · `review` · `doctor` ·
   `service {install,uninstall,start,stop,restart,status,logs}` · `update`
   (alias `upgrade`) · `suggest` (Phase 2; in Phase 1 it prints "Phase 2 not
   installed" and exits 0). Nothing else. Read verbs work with nothing
   installed but the store.
```

Replacement:

```
1. **Verbs.** `init` · `status` · `why <id>` · `review` · `doctor` ·
   `service {install,uninstall,start,stop,restart,status,logs}` · `update`
   (alias `upgrade`) · `suggest` (Phase 2; in Phase 1 it prints "Phase 2 not
   installed" and exits 0). Nothing else — exactly these eight; **a flag is
   not a verb**. Every verb takes `--home <instance>`, naming the instance it
   acts on; without it the instance resolves as the store contract says
   (`$AMPLIFIER_MEMORY_HOME`, else the default `~/.amplifier-memory`).
   `--help` shows `--home` once, on the group, not once per verb. Read verbs
   work with nothing installed but the store.
```

### Change 2 — §8, `init` (any instance, its own `config.yaml`, one question)

Current text:

```
8. **`init`** creates the store.v2 layout at the store location and makes
   the initial commit, then installs the daily suggest timer exactly as
   `service install` does (§6) — a fresh install gets suggestions by
   default, with nothing further to type. The timer is installed only when
   the store is the device's own, `~/.amplifier/memory`: a `--user` timer
   exists once per device and runs against whatever the store resolves to
   later, so an `init` pointed at any other path (a test, a kit, a redirected
   `AMPLIFIER_MEMORY_HOME`) creates the store, installs nothing, and says
   `timer not installed for a store outside ~/.amplifier/memory — run
   amplifier-memory service install if you want one`. It ends with two lines: what it
   installed, and how to turn it off (`amplifier-memory service uninstall`)
   or steer its cost (`~/.amplifier/memory-config.toml`, suggestions §8).
   Idempotent: a second run reports the store exists and the timer is
   installed, and changes nothing. Where Phase 2 is not installed it says
   so in the §6 words and installs no timer. `--no-timer` skips the timer
   for a host that must not run one. It is the README's step 3 and the only
   setup needed.
```

Replacement:

```
8. **`init`** builds the instance at the resolved home (`--home`, else
   `$AMPLIFIER_MEMORY_HOME`, else the default `~/.amplifier-memory`) and
   makes the initial commit. When the default does not exist and
   `~/.amplifier/memory` does, it offers to move the older store to the
   default and prints what it did — never a silent move. It writes
   `config.yaml` inside the instance with the shipped defaults:
   `enabled: true`, and `llm: judge: {role: fast, provider: "", model: "",
   bundle: ""}` — a role, never a provider id (§5). It asks **one** question,
   `What kinds of things should I remember for you?`, offering a default
   answer verbatim in the prompt ("Standing preferences and corrections meant
   to hold beyond one task — not task steps, not facts about the code"), and
   saves what the human types or accepts as `m-001`, writer=human, that text
   also being the quote — only the human's own words become memory, so
   nothing is minted; with no TTY it takes the default and says so. It then
   installs the daily suggest timer for **this** instance exactly as
   `service install` does (§6); the unit name carries the instance, so `init`
   works for any instance rather than only the device store, and a kit's temp
   instance gets its own unit instead of touching the device's. It ends with
   two lines: what it installed, and how to turn it off (`amplifier-memory
   service uninstall --home <instance>`) or steer its cost (`config.yaml`
   inside the instance, suggestions §8). Idempotent: a second run reports the
   store exists and the timer is installed, asks nothing, and changes
   nothing. Where Phase 2 is not installed it says so in the §6 words and
   installs no timer. `--no-timer` skips the timer for a host that must not
   run one. It is the README's step 3 and the only setup needed.
```

### Change 3 — §6, `service` is per instance

Current text:

```
6. **`service`** manages only the Phase 2 suggest timer (systemd `--user` /
   launchd). `install` renders units, `daemon-reload → enable --now`, and
   rolls back written units if any step fails. Phase 1 has no service; the
   verb reports that plainly. `init` (§8) calls the same install; `service
   uninstall` is the opt-out for a store that `init` set up.
```

Replacement:

```
6. **`service`** manages only the Phase 2 suggest timer (systemd `--user` /
   launchd), **per instance**: `install`, `uninstall`, `status`, `restart`
   and the rest act on the instance `--home` resolves to, and each unit name
   is derived from that instance's path — so two instances never collide and
   neither can silently uninstall the other's timer. `install` renders units,
   `daemon-reload → enable --now`, and rolls back written units if any step
   fails. `status` lists every installed instance timer, not only the
   resolved one. Phase 1 has no service; the verb reports that plainly.
   `init` (§8) calls the same install; `service uninstall` is the opt-out for
   an instance that `init` set up.
```

### Change 4 — the cost/steering sentence, and making an inherited price visible

**4a — §8's steering sentence (line 76).** Applied *inside* Change 2's block above, not
separately; shown alone here because it is the sentence that moves the knob.

Current text:

```
   or steer its cost (`~/.amplifier/memory-config.toml`, suggestions §8).
```

Replacement:

```
   (`config.yaml` inside the instance, suggestions §8). The shipped default
   is the ROLE `fast` — never a provider id, which is one device's word.
```

**4b — §5, one new `doctor` row.** Current text:

```
   line or byte offset and the last commit whose file parsed clean · stale
   topics count · inbox size and oldest · suggest timer
   installed/enabled/last run/last outcome (Phase 2) · substrate present
```

Replacement:

```
   line or byte offset and the last commit whose file parsed clean · stale
   topics count · inbox size and oldest · suggest timer
   installed/enabled/last run/last outcome (Phase 2) · **judge model** — the
   provider and model the daily pass will use, or, while the host cannot
   resolve a role for `amplifier run`, `inherits the app's default` naming
   that default and the last run's measured cost, so an inherited price is
   visible rather than silent (Phase 2) · substrate present
```

## The evidence

**The steward's own words, 2026-09-07, verbatim:**

- "I appreciate having a seperate/single ~/.amplifier/memory-config.toml (though we typically
  use .yaml)"
- "we _can_ still have a default (maybe in ~/.amplifier-memory) that works w/o specifying a
  location/instance"
- On seeding: "I wonder if we should seed the memory file w/ a personalized (or default to be
  personalized) preference for the kinds of things to capture as memories for that user?" —
  and, told that only the human's own words become memory so `init` would ask one question and
  save the answer as `m-001` writer=human: "sure, sounds good".
- On the judge's model: "What is the shipped value for llm.judge? Since that is tied my
  provider id's, that obviously can't be what we ship".

**A cost already paid, measured.** With no config file the job adds no `-p/-m/-B` and inherits
the app's starred provider (`llm_config.py:80-99`) — here opus at **$0.276/call**, while
`gpt-5.6-luna` was a perfect scorecard at **$0.02/call** over 3 pilots
(`evaluations/model-class/RESULTS-2026-09-06-pilot.md`). Nothing printed that 50× difference:
`render()` says only "inherits the CLI default", naming neither what was inherited nor its cost.
Shipping `provider = "luna"` cannot fix it — `llm_config.py:14-19` ships an amplifier provider
id, one device's naming, not a portable value. Hence the role `fast`, already carried but
unresolved (`amplifier run` has no `--model-role`; the ask is
`docs/upstream/amplifier-run-model-role.md`).

**A second cost.** `init` takes no target at all today (`cli.py:48`: one `--no-timer` flag), and
§8 installs a timer only for `~/.amplifier/memory`. A second app — amplifier-agent at
`~/.amplifier-agent` — can be handed an instance by the store proposal and still not be set up
from a shell, and its timer has nowhere to be named.

## What does NOT change

The **eight verbs** of Core 1 — `--home` is a flag, not a ninth. `status`'s numbers and
one-screen shape (§2, with R1's pre-registered "kept"). `why`'s output — text, quote, session,
writer, action, date, `was:` → `now:`, the `forgot` marker (§3). `review`'s shape and empty-inbox
exit 0 (§4). `doctor` **never mutates**, `--repair` still the one sanctioned exception (§5).
`update`'s steps in order: the uv tool, the bundle refresh, the timer restart, the closing
`doctor`, the stale-in-memory note (§7). Core 9's thin-wrapper rule. Exit codes — nonzero only on
failed checks, unknown verb a one-line error. `--no-timer` keeps working. Every existing store
keeps working: `~/.amplifier/memory` is still found, with or without `AMPLIFIER_MEMORY_HOME`, and
a shell that types no `--home` behaves as it does today.

## Steward's word

Answer in one word: **ratified** · **ratified with edits** · **declined** · **later**.

>
