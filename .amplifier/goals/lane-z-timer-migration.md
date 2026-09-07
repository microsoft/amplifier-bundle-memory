# Lane lane-z-timer-migration — init/service must never name a unit that does not exist; migrate the pre-v3 device-wide timer to the per-instance one

Worker session, alone, in your own worktree of `amplifier-bundle-memory` on branch
`lane/amplifier_bundle_memory-5wc`. Work ONLY here; never merge to `main`; commit early, push after every commit.
**Never touch `~/.amplifier-memory`, `~/.amplifier/memory`, or the device's real systemd units; never run a real
`service install`/`uninstall`, `init` without an injected runner + unit dir, or `update`.** The manager applies the
migration on the device after the merge. Temp instances (`AMPLIFIER_MEMORY_HOME`, `home=`), `AMPLIFIER_MEMORY_UNIT_DIR`
and `runner=` only.

Read first: `PINS.md`, `AGENTS.md` (incl. "Lane acceptance criteria are re-derivable from durable artefacts" and the
file-ownership rule), **`contracts/cli.v3.md` §5, §6, §8**, `src/amplifier_memory/service.py`, `src/amplifier_memory/instance.py`,
`src/amplifier_memory/doctor.py` (suggest-timer row), `conformance/cli/run.py` (Core 6 and Core 8 probes), `tests/test_service.py`,
`tests/test_init_timer.py`.

**Work item:** `amplifier_bundle_memory-5wc` — claim it
(`work_claim(project="amplifier_bundle_memory", item_id="amplifier_bundle_memory-5wc")`), read its description and acceptance IN
FULL (measured evidence from the steward's device is in it), resolve with a reason written for the steward, read it back with
`work_list`, record the sha256 of the stored resolution in DONE.json.

**File ownership — edit ONLY:** `src/amplifier_memory/service.py`, `src/amplifier_memory/instance.py`, `src/amplifier_memory/doctor.py`
(suggest-timer row only), `src/amplifier_memory/cli.py` (only if a verb's wiring must change; cli.v3 §9 — one literal library call),
`tests/test_service.py`, `tests/test_init_timer.py`, `tests/test_doctor.py`, `tests/test_cli.py`, `conformance/cli/run.py`,
README service/init section. Off-limits: `store.py`, `inbox.py`, `llm_config.py`, `suggest.py`, `update.py`, `modules/**`,
`contracts/`, `ledger/`, `docs/workflow/`. If the fix genuinely needs a file outside this list, STOP and write it in `residuals`
as a brief defect — do not edit it (AGENTS.md rule).

## Outcome

1. **The truth about units.** Every unit name `init`, `service install`, `service status` and `doctor` print exists on disk in the
   unit dir at the moment it is printed (assert in tests via the injected runner/unit dir: the printed name is a file in
   `AMPLIFIER_MEMORY_UNIT_DIR`). The measured lie — init printing `amplifier-memory-suggest-amplifier-memory-c0195169.timer` while
   only the Sep-6 `amplifier-memory-suggest.{service,timer}` existed — is reproduced as a test FIRST (red), then fixed.
2. **Migration, said out loud.** When the pre-v3 device-wide pair (`amplifier-memory-suggest.service/.timer`, no `--home`) exists
   and the instance being initialised/installed is the resolved default: write the per-instance pair, enable it, then disable and
   remove the device-wide pair — through the runner — and print exactly what happened ("replaced the device-wide timer with
   this instance's: <unit>"). Result: exactly ONE timer serves the instance. If the instance is NOT the default, leave the
   device-wide pair alone and say that it does not serve this instance.
3. **doctor names the unit.** The suggest-timer row reads `installed · enabled · unit <name> · last run …`.
4. `service status` lists every installed instance timer by unit and instance path (cli.v3 §6) and names the device-wide pair as
   "pre-v3, serves the default only" when present.

## Terminal states and the exit

Items end `PASS` / `FAIL-<cause>` / `BLOCKED-<cause>` / `PENDING-HUMAN`. 100 min wall → `BUDGET`: commit what is sound, write the
marker. **Final act: `DONE.json`** (valid JSON) in the worktree root:
`{"lane":"lane-z-timer-migration","session_id":"…","verdict":"COMPLETE|BLOCKED|PARTIAL","branch":"lane/amplifier_bundle_memory-5wc",
"head":"…","pushed":true,"items":[…],"residuals":[…],"pending_human":[],"resources":[],"suite":"…","resolution_sha256":"…"}`.

## Acceptance — each re-derivable from a durable artefact

- The red-then-green test for the unit-name lie, named in DONE.json, with the red run's output quoted in its docstring or the commit.
- `uv run pytest -q` green (baseline 337); `uv run ruff check .` / `uv run ruff format --check .` clean.
- `env -u PYTEST_CURRENT_TEST AMPLIFIER_MEMORY_HOME=<tmp> AMPLIFIER_MEMORY_UNIT_DIR=<tmp> uv run python conformance/cli/run.py` exit 0,
  Core 6 and Core 8 Kept with evidence lines naming the units they found on disk; `systemctl --user show amplifier-memory-suggest.timer
  -p ActiveEnterTimestamp` byte-identical before and after (print both) — the device untouched.
- Item resolved; sha256 recorded.
- Show command output inline; never assert a result without it.
