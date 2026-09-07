# Lane lane-w-cli-v3 — cli.v3: --home on every verb, init builds the instance (move offer, config.yaml, the seeding question → m-001, per-instance timer), per-instance service, doctor judge row; fixes azy

Worker session, alone, in your own worktree of `amplifier-bundle-memory` on branch
`lane/amplifier_bundle_memory-l3e`. Work ONLY here; never merge to `main`; commit early, push after
every commit. **Never touch `~/.amplifier/memory`, `~/.amplifier-memory`, or the device's systemd units;
never run a real model call, a real `service install`, or `update`** — temp instances and injected
runners only (`AMPLIFIER_MEMORY_HOME`, `home=`, `AMPLIFIER_MEMORY_UNIT_DIR`, `runner=`).

Read first: `PINS.md`, `AGENTS.md` (incl. "Lane acceptance criteria are re-derivable from durable
artefacts"), **`contracts/cli.v3.md` (FROZEN 2026-09-07, amended in place the same day) — Core 1 (`--home`, still eight verbs), §5 (doctor judge row: configured / role / inherited + last run cost), §6 (service per instance), §8 (init: resolved home, move offer for `~/.amplifier/memory`, `config.yaml` defaults, the ONE seeding question saved as m-001 writer=human — no TTY → default and say so — per-instance timer whose unit name carries the instance)**, and item `amplifier_bundle_memory-azy` (init on a redirected store must never reach the real systemctl; the cli kit Core 8 arm injects runner/config_dir so a STANDALONE kit run is Kept), and the library that lane U just landed on main: `src/amplifier_memory/store.py`
(`store_home(home=)`, `instance_enabled`, `record_session`, `session_origins`), `llm_config.py`
(`load(home)` reads the instance's `config.yaml`), `inbox.py` (declined quote). Use those; do not
re-implement them.

**Work item:** `amplifier_bundle_memory-l3e` — claim it
(`work_claim(project="amplifier_bundle_memory", item_id="amplifier_bundle_memory-l3e")`), read its
description and acceptance IN FULL (they are the spec), resolve with a reason written for the steward,
read it back with `work_list`, and record in DONE.json the sha256 of the stored resolution.

**File ownership — edit ONLY:** `src/amplifier_memory/cli.py`, `src/amplifier_memory/doctor.py`, `src/amplifier_memory/service.py`, `src/amplifier_memory/update.py` (only if --home must thread through), `tests/test_cli.py`, `tests/test_doctor.py`, `tests/test_service.py`, `tests/test_init_timer.py`, `tests/test_update.py`, `tests/test_status.py`, `src/amplifier_memory/status.py`, `conformance/cli/run.py`, README CLI section. **Off-limits:** `store.py`/`inbox.py`/`llm_config.py`/`config.py` (U, landed — extend by calling, not editing), `modules/**` (lane V), `suggest.py` (lane X), `conformance/session/**`, `conformance/suggestions/**`, `contracts/`, `ledger/`, `docs/workflow/`.
Two sibling lanes run beside you on the same repository; you will not see their work and must not touch
their files. If the spec needs a library change, do NOT make it — write it in `residuals` as a brief defect.

## Terminal states and the exit

Items end `PASS` / `FAIL-<cause>` / `BLOCKED-<cause>` / `PENDING-HUMAN`. 120 min wall → `BUDGET`:
commit what is sound, write the marker. **Final act: `DONE.json`** (valid JSON) in the worktree root:
`{"lane":"lane-w-cli-v3","session_id":"…","verdict":"COMPLETE|BLOCKED|PARTIAL","branch":"lane/amplifier_bundle_memory-l3e",
"head":"…","pushed":true,"items":[…],"residuals":[…],"pending_human":[],"resources":[],"suite":"…","resolution_sha256":"…"}`.
On BLOCKED also write `BLOCKED.md` with the cause.

## Acceptance — the item's acceptance, each line re-derivable from a durable artefact

Every criterion in the work item, plus: `uv run pytest -q` green (baseline 316), `uv run ruff check .`
and `uv run ruff format --check .` clean, the named conformance kit(s) exit 0 with the new clauses' probes
Kept, and the resolution sha256 recorded in DONE.json from
`amplifier-work-tracker list --project amplifier_bundle_memory --id amplifier_bundle_memory-l3e --json`.
Standalone (no PYTEST_CURRENT_TEST) `conformance/cli/run.py` exit 0 — the azy proof — with `systemctl --user show amplifier-memory-suggest.timer -p ActiveEnterTimestamp` byte-identical before and after (print both). Also retire the 2 `memory-config.toml`/`tomllib` docstring mentions in doctor.py (lane U residual).
Show command output inline; never assert a result without it.
