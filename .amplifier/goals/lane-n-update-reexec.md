# Lane lane-n-update-reexec — one `update` is enough

Worker session, alone, in your own worktree of `amplifier-bundle-memory` on branch
`lane/amplifier_bundle_memory-4h6`. Work ONLY here; never merge to `main`; commit early, push after
every commit. **Never touch `~/.amplifier/memory`; never run the real `amplifier-memory update`,
`uv tool`, `uv pip`, or `amplifier bundle` against this device** — fake runner and monkeypatched
`os.execv` only. The manager runs the real update after merge.

Read first: `PINS.md`, `AGENTS.md`, `contracts/cli.v2.md` §7 (FROZEN — your spec),
`docs/workflow/CHECK-RECORD.md` (wave 9: the two-run measurement that filed this item),
`src/amplifier_memory/update.py` (`run_update`, the injectable runner, the step list lane M added),
`src/amplifier_memory/cli.py` (the `update` command), `tests/test_update.py`, `tests/test_cli.py`
(`test_update_runs_its_steps_and_ends_in_doctor`), `conformance/cli/run.py` (`probe_core_7`).

**Work item:** `amplifier_bundle_memory-4h6` — claim it (`work_claim(project="amplifier_bundle_memory",
item_id="amplifier_bundle_memory-4h6")`), read its description (the measured first-run/second-run
transcript), resolve with a reason for the steward, read it back with `work_list`, print it.

**File ownership — edit ONLY:** `src/amplifier_memory/update.py`, `src/amplifier_memory/cli.py` (the
hidden `--after-upgrade` flag only), `tests/test_update.py`, `tests/test_cli.py` (the update test
only), `conformance/cli/run.py`, `ledger/rows.yaml` row AMM-026 (notes only), `README.md` (the
`update` sentence only). Off-limits: everything else, `doctor.py` included.

## Outcome

A steward runs `amplifier-memory update` once. If the uv-tool step upgraded the CLI, the process
re-executes the freshly installed binary with `update --after-upgrade`, which skips the uv-tool step
and runs the cache and env-library refreshes plus `doctor` with the NEW code. The steward reads one
report and it is true. When re-exec is impossible, one INFO line says so and names the remedy.

## Exit

PASS / FAIL-<cause> / BLOCKED-<cause>; complete when every item is terminal or shown impossible;
60 min → BUDGET. **Final act: `DONE.json`** (valid JSON — escape control characters) in the worktree
root with lane `lane-n-update-reexec`, branch `lane/amplifier_bundle_memory-4h6`, verdict, items,
residuals, suite.

## Acceptance — print the evidence

1. Detect "upgraded": compare the installed commit before the uv-tool step with the one after
   (`doctor.installed_commit()` re-read, or the dist's `direct_url.json`); a fake runner + a fake
   dist layout drives both branches. Printed.
2. Upgraded → `os.execv(<amplifier-memory path>, [<path>, "update", "--after-upgrade"])` is called
   and NOTHING after the uv-tool step runs in the old process (monkeypatch `os.execv`; assert the
   recorded argv and the step list). Printed.
3. `--after-upgrade` → the uv-tool step is skipped (one line says `skipped — already upgraded by
   the previous process`) and the refresh steps + doctor run. Printed.
4. Not upgraded → no re-exec; every step runs in-process exactly as lane M left it. Printed.
5. Re-exec impossible (`shutil.which` returns None, or `--after-upgrade` already set with a
   changed commit) → one INFO line `upgraded in place — the steps below ran with the previous
   version; run update once more`, printed exactly once and only when the commits differ.
6. `conformance/cli/run.py` Core 7 probe extended (fake device: upgrade → re-exec argv). Exit 0,
   Kept. Root `uv run pytest -q` (baseline 167) + `uv run ruff check .` green; `cli.py` imports
   only `click` and `amplifier_memory` (printed grep).
7. AMM-026 note names the probe; README's `update` sentence says one run is enough. Item resolved
   and read back.

## Known

- Honesty gate: *"cli.v2 §7 — Can't check in this lane because …"*.
- Show command output inline; never assert a result without it.
