# Lane lane-14b-init-timer — `init` installs the daily suggest timer by default

Worker session, alone, in your own worktree of `amplifier-bundle-memory` on branch
`lane/amplifier_bundle_memory-78h`. Work ONLY here; never merge to `main`; commit early, push after
every commit. **Never touch `~/.amplifier/memory`, `~/.config/systemd/user/`, or `~/Library/
LaunchAgents/`; never run the real `amplifier-memory init` or `service install`** — temp homes, a
temp `UNIT_DIR`, and the fake runner the service tests already use (`conftest` recorder for
`service._default_runner`). The manager runs the real thing on the device after merge.

Read first: `PINS.md`, `AGENTS.md` (11: one home for logic; cli.v2 §9: the CLI carries none),
**`contracts/cli.v2.md` §8 and §6 as amended 2026-09-07 — your specification, word for word**,
`contracts/suggestions.v1.md` §1 (the timer) and §8 (cost, the config knob), `src/amplifier_memory/
cli.py` (`init`), `src/amplifier_memory/store.py` (`init`, `InitResult`), `src/amplifier_memory/
service.py` (install path, `ServiceResult`, `_default_runner`, the Phase-2-present predicate),
`tests/test_service*.py` and `tests/conftest.py` (the recorder), `conformance/cli/run.py` (Core 6
and Core 8 probes), `README.md` lines 20–60 and 105–115.

**Work item:** `amplifier_bundle_memory-78h` — claim it (`work_claim(project="amplifier_bundle_memory",
item_id="amplifier_bundle_memory-78h")`), read its description and acceptance in full, resolve with a
reason written for the steward, read it back with `work_list(...)`, print it.

**File ownership — edit ONLY:** `src/amplifier_memory/cli.py`, `src/amplifier_memory/service.py`,
`src/amplifier_memory/store.py` **only `init`/`InitResult`** (lane 14-A owns the list renderer in the
same file this wave — touch nothing else there and say in the resolution exactly what you changed),
`README.md`, `tests/test_cli.py`, `tests/test_service*.py`, `tests/test_init*.py`, `tests/conftest.py`
(recorder only if it must learn one more thing), `conformance/cli/run.py`. **Off-limits:** `inbox.py`,
`status.py`, `modules/**`, `skills/**`, `conformance/session/**`, `ledger/`, `contracts/`,
`docs/workflow/`.

## Outcome

A fresh install gets suggestions without a second command. `amplifier-memory init` creates the
store as today, then calls **the same library function `service install` calls** (one install
implementation — never a subprocess to the CLI, cli.v2 §9), and ends with two lines:

    installed the daily suggest timer (systemd --user, next run 00:00). Off: amplifier-memory service uninstall.
    which model it uses, and what it costs, is yours to set: ~/.amplifier/memory-config.toml

(Wording yours; the two facts — the opt-out command and the config path — are the contract's.)
A second `init`: `store exists · timer installed`, and nothing written (hash before == after, the
runner saw no call). `init --no-timer`: store only, no unit. On a host where Phase 2 is not
installed (the same predicate `service install` uses today): §6's no-service line, no unit.
`README.md`: step 3 is the only setup; the standalone `service install` lines say it is what `init`
already did, and how to redo it after `service uninstall`.

## Honesty gate — say this if it is true

"Every install in this lane went to a temp `UNIT_DIR` through the fake runner; no real unit was
written; `systemctl --user list-timers` on this host is unchanged (printed before and after)." A
real unit file appearing under `~/.config/systemd/user/` during this lane is the falsifier — print
`ls -la ~/.config/systemd/user/amplifier-memory-suggest.*` at start and end and show they match.

## Terminal states and the exit

Items end `PASS` / `FAIL-<cause>` / `BLOCKED-<cause>`. 90 min wall → `BUDGET`: commit what is sound,
write the marker. **Final act: `DONE.json`** (valid JSON) in the worktree root — **never `git add`
it**: `{"lane":"lane-14b-init-timer","session_id":"…","verdict":"COMPLETE|BLOCKED|PARTIAL",
"branch":"lane/amplifier_bundle_memory-78h","head":"…","pushed":true,"items":[…],"residuals":[…],
"suite":"…"}`. On BLOCKED also write `BLOCKED.md`. Two exits and no third: **A) SUCCESS** — every
item met with evidence printed, committed and pushed, queue item resolved and read back; **B)
BLOCKED** — a named cause that stops every deliverable. A criterion outside your file ownership is a
residual, exit A.

## Acceptance — every item names a file or a command whose output you print, and its falsifier

1. Temp home + fake runner: `init` creates the store (initial commit present), the runner saw
   `daemon-reload` and `enable --now` for the timer, both unit files exist under the temp
   `UNIT_DIR`, and the last two printed lines carry `amplifier-memory service uninstall` and
   `~/.amplifier/memory-config.toml`. Test printed. **False if** the units were written by anything
   but the function `service install` calls.
2. Second `init` on that home prints `store exists · timer installed`; runner saw nothing; every
   file's hash unchanged. Printed.
3. `init --no-timer`: store exists, no unit file, runner saw nothing. Printed.
4. Phase 1 arm (Phase 2 predicate false): `init` prints §6's exact no-service line and creates no
   unit. Printed. **False if** the predicate is a new one rather than the one `service install` uses.
5. `python conformance/cli/run.py` prints `Core 8 — Kept` naming all four arms, `Core 6 — Kept`,
   `Core 1 — Kept` (verb surface unchanged — no new verb). Printed. **False if** the kit was
   weakened or the arms run against the real home.
6. `grep -n "subprocess\|amplifier-memory service" src/amplifier_memory/cli.py` prints nothing for
   the init path; `grep -n "def install\|def install_timer" src/amplifier_memory/service.py` shows
   the one function both callers use. Printed.
7. `README.md`: `grep -n "init\|service install" README.md` printed; step 3 reads as the only setup,
   the `service install` lines defer to `init`.
8. `ls -la ~/.config/systemd/user/amplifier-memory-suggest.*` and `systemctl --user list-timers
   --no-pager | grep -c amplifier` at lane start and lane end — identical, printed.
9. Root `uv run --offline pytest -q` and `ruff check .` — printed, green.
10. Item `78h` resolved, read back with `work_list`, printed. **False if** the printed reason asserts
    something you know to be untrue or omits a residual you recorded (including the exact
    `store.py` lines touched, if any).
