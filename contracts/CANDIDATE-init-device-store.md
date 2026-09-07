# Proposal: amend cli.v2 in place (CANDIDATE) — `init` installs the timer for the device store

target: contracts/cli.v2.md

**Changes:** `contracts/cli.v2.md` (FROZEN 2026-09-06; §8 amended 2026-09-07). Written
2026-09-07 by the manager session from lane 14-B's honest residual. One sentence narrows §8's
"installs the timer" to the store a device-wide timer can actually serve. The code already
behaves this way (merged 11d25fa); this proposal is how the contract catches up or the code is
pulled back — the steward's word decides which. Legacy `CANDIDATE-<topic>.md` name because
`cli.v2-candidate.md` is the ratified proposal that landed an hour earlier.

## Target lines and exact changes

### Change 1 — §8, one sentence added after "…with nothing further to type."

Current text:

```
   `service install` does (§6) — a fresh install gets suggestions by
   default, with nothing further to type. It ends with two lines: what it
```

Replacement:

```
   `service install` does (§6) — a fresh install gets suggestions by
   default, with nothing further to type. The timer is installed only when
   the store is the device's own, `~/.amplifier/memory`: a `--user` timer
   exists once per device and runs against whatever the store resolves to
   later, so an `init` pointed at any other path (a test, a kit, a redirected
   `AMPLIFIER_MEMORY_HOME`) creates the store, installs nothing, and says
   `timer not installed for a store outside ~/.amplifier/memory — run
   amplifier-memory service install if you want one`. It ends with two lines: what it
```

### Change 2 — Conformance, extend the `init` bullet

Current text:

```
- A fresh `init` on a Phase 2 host leaves the timer installed and enabled
```

Replacement:

```
- A fresh `init` on a Phase 2 host against `~/.amplifier/memory` leaves the
  timer installed and enabled; the same `init` against a temp store creates
  the store, writes no unit, and prints the outside-store line (this is what
  keeps every conformance kit from enabling a real timer);
```

## Evidence (a cost paid, twice)

- **2026-09-06, twice:** a plain shell run of a conformance kit that builds a temp store and
  calls `init` would have written units into `~/.config/systemd/user` and enabled a real daily
  timer — lane 14-B's resolution names both incidents. Every kit (`store`, `suggestions`,
  `session/tool`) calls `init` on a temp store; without the gate, §8-as-written turns each
  test run into an installer.
- **The gate is the smallest thing that prevents it:** one path comparison, no config, no
  flag. The alternative — every test and kit threading a `--no-timer` — is the kind of
  advice-not-enforcement store.v2 §4 refuses for the cap.
- **Its visible cost is named, not hidden:** a steward who permanently redirects
  `AMPLIFIER_MEMORY_HOME` gets no timer from `init` and is told the one command that gives them
  one. `doctor` already shows whether a timer is installed.

## What does NOT change

Everything else in §8 (the two closing lines, idempotence, `--no-timer`, the Phase 1 arm) and
§6. `service install` / `uninstall` are unchanged and remain available for any store. The
default path — a fresh install on a device — gets its timer exactly as the ratified §8 says.

## Steward's word

ratified by owner — 2026-09-07, in conversation: "ratified.  Then go ahead and monitor until done."
Applied in place to `contracts/cli.v2.md` §8 with a changelog entry in the same write.
