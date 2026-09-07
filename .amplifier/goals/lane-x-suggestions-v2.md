# Lane lane-x-suggestions-v2 — suggestions.v2 in the job: human-origin + typed-text sessions only, judge from config.yaml (provider → role fast → inherited, named), origin_excluded= in the log line

Worker session, alone, in your own worktree of `amplifier-bundle-memory` on branch
`lane/amplifier_bundle_memory-h3r`. Work ONLY here; never merge to `main`; commit early, push after
every commit. **Never touch `~/.amplifier/memory`, `~/.amplifier-memory`, or the device's systemd units;
never run a real model call, a real `service install`, or `update`** — temp instances and injected
runners only (`AMPLIFIER_MEMORY_HOME`, `home=`, `AMPLIFIER_MEMORY_UNIT_DIR`, `runner=`).

Read first: `PINS.md`, `AGENTS.md` (incl. "Lane acceptance criteria are re-derivable from durable
artefacts"), **`contracts/suggestions.v2.md` (FROZEN 2026-09-07) — Core 2 (recorded origin `human` or no record; ≥2 human turns of TYPED TEXT — not a lane brief (>1500 chars / lane markers), not a system-reminder-only continuation turn; existing exclusions kept), Core 3 (judge from `config.yaml` `llm: judge:`: provider/model/bundle → else role `fast` when the host can → else inherited and NAMED; role never a provider id), Core 8 (doctor names the judge — coordinate by reading `doctor.py`, do not edit it; expose a library function W can call), Core 9 (`origin_excluded=N` beside `sessions=`)**, and the library that lane U just landed on main: `src/amplifier_memory/store.py`
(`store_home(home=)`, `instance_enabled`, `record_session`, `session_origins`), `llm_config.py`
(`load(home)` reads the instance's `config.yaml`), `inbox.py` (declined quote). Use those; do not
re-implement them.

**Work item:** `amplifier_bundle_memory-h3r` — claim it
(`work_claim(project="amplifier_bundle_memory", item_id="amplifier_bundle_memory-h3r")`), read its
description and acceptance IN FULL (they are the spec), resolve with a reason written for the steward,
read it back with `work_list`, and record in DONE.json the sha256 of the stored resolution.

**File ownership — edit ONLY:** `src/amplifier_memory/suggest.py`, `tests/test_suggest.py`, `conformance/suggestions/run.py`, `evaluations/model-class/harness.py` ONLY if `build_argv`/request signature changes, README suggestions section. **Off-limits:** `store.py`/`inbox.py`/`llm_config.py`/`config.py` (U, landed — call them), `modules/**` (lane V), `cli.py`/`doctor.py`/`service.py`/`status.py` (lane W), `conformance/cli/**`, `conformance/session/**`, `conformance/store/**`, `contracts/`, `ledger/`, `docs/workflow/`.
Two sibling lanes run beside you on the same repository; you will not see their work and must not touch
their files. If the spec needs a library change, do NOT make it — write it in `residuals` as a brief defect.

## Terminal states and the exit

Items end `PASS` / `FAIL-<cause>` / `BLOCKED-<cause>` / `PENDING-HUMAN`. 120 min wall → `BUDGET`:
commit what is sound, write the marker. **Final act: `DONE.json`** (valid JSON) in the worktree root:
`{"lane":"lane-x-suggestions-v2","session_id":"…","verdict":"COMPLETE|BLOCKED|PARTIAL","branch":"lane/amplifier_bundle_memory-h3r",
"head":"…","pushed":true,"items":[…],"residuals":[…],"pending_human":[],"resources":[],"suite":"…","resolution_sha256":"…"}`.
On BLOCKED also write `BLOCKED.md` with the cause.

## Acceptance — the item's acceptance, each line re-derivable from a durable artefact

Every criterion in the work item, plus: `uv run pytest -q` green (baseline 316), `uv run ruff check .`
and `uv run ruff format --check .` clean, the named conformance kit(s) exit 0 with the new clauses' probes
Kept, and the resolution sha256 recorded in DONE.json from
`amplifier-work-tracker list --project amplifier_bundle_memory --id amplifier_bundle_memory-h3r --json`.
Measured shapes to test against: worker session 6bafabaf (first turn "Claim drumbeat-d4h from the drumbeat work-tracker project…"); a /goal transcript whose "human" turns are `<system-reminders>` blocks. Retire the 2 `memory-config.toml`/`tomllib` docstring mentions in suggest.py (lane U residual). Never call a real model: inject `model_call`.
Show command output inline; never assert a result without it.
