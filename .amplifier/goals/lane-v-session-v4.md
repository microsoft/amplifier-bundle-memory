# Lane lane-v-session-v4 — session.v4 in the modules: mount-plan home:/enabled, AMPLIFIER_SESSION_ORIGIN recorded, non-human sessions cannot save

Worker session, alone, in your own worktree of `amplifier-bundle-memory` on branch
`lane/amplifier_bundle_memory-8o4`. Work ONLY here; never merge to `main`; commit early, push after
every commit. **Never touch `~/.amplifier/memory`, `~/.amplifier-memory`, or the device's systemd units;
never run a real model call, a real `service install`, or `update`** — temp instances and injected
runners only (`AMPLIFIER_MEMORY_HOME`, `home=`, `AMPLIFIER_MEMORY_UNIT_DIR`, `runner=`).

Read first: `PINS.md`, `AGENTS.md` (incl. "Lane acceptance criteria are re-derivable from durable
artefacts"), **`contracts/session.v4.md` (FROZEN 2026-09-07) — §2 (load line names a non-default instance), §12 (mount config `home:` + `enabled`), §13 (`AMPLIFIER_SESSION_ORIGIN` → `sessions.jsonl`; non-human: no save/edit/forget, no suggestions line, still injected)**, and the library that lane U just landed on main: `src/amplifier_memory/store.py`
(`store_home(home=)`, `instance_enabled`, `record_session`, `session_origins`), `llm_config.py`
(`load(home)` reads the instance's `config.yaml`), `inbox.py` (declined quote). Use those; do not
re-implement them.

**Work item:** `amplifier_bundle_memory-8o4` — claim it
(`work_claim(project="amplifier_bundle_memory", item_id="amplifier_bundle_memory-8o4")`), read its
description and acceptance IN FULL (they are the spec), resolve with a reason written for the steward,
read it back with `work_list`, and record in DONE.json the sha256 of the stored resolution.

**File ownership — edit ONLY:** `modules/hooks-memory-inject/**`, `modules/tool-memory/**`, `skills/**`, `conformance/session/**` (or the session kit wherever it lives — find it), the two module READMEs. **Off-limits:** `src/amplifier_memory/**` (U, landed), `cli.py`/`doctor.py`/`service.py` (lane W), `suggest.py` (lane X), `conformance/cli/**`, `conformance/suggestions/**`, `conformance/store/**`, `contracts/`, `ledger/`, `docs/workflow/`.
Two sibling lanes run beside you on the same repository; you will not see their work and must not touch
their files. If the spec needs a library change, do NOT make it — write it in `residuals` as a brief defect.

## Terminal states and the exit

Items end `PASS` / `FAIL-<cause>` / `BLOCKED-<cause>` / `PENDING-HUMAN`. 120 min wall → `BUDGET`:
commit what is sound, write the marker. **Final act: `DONE.json`** (valid JSON) in the worktree root:
`{"lane":"lane-v-session-v4","session_id":"…","verdict":"COMPLETE|BLOCKED|PARTIAL","branch":"lane/amplifier_bundle_memory-8o4",
"head":"…","pushed":true,"items":[…],"residuals":[…],"pending_human":[],"resources":[],"suite":"…","resolution_sha256":"…"}`.
On BLOCKED also write `BLOCKED.md` with the cause.

## Acceptance — the item's acceptance, each line re-derivable from a durable artefact

Every criterion in the work item, plus: `uv run pytest -q` green (baseline 316), `uv run ruff check .`
and `uv run ruff format --check .` clean, the named conformance kit(s) exit 0 with the new clauses' probes
Kept, and the resolution sha256 recorded in DONE.json from
`amplifier-work-tracker list --project amplifier_bundle_memory --id amplifier_bundle_memory-8o4 --json`.
Module suites green (hooks-memory-inject baseline 51, tool-memory baseline 75). The hook records origin through `store.record_session` at session start, exactly once per session.
Show command output inline; never assert a result without it.
