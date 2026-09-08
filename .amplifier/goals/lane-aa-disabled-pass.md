# Lane lane-aa-disabled-pass — store.v3 §11: a disabled instance costs nothing

Worker session, alone, in your own worktree of `amplifier-bundle-memory` on branch
`lane/amplifier_bundle_memory-h8o`. Work ONLY here; never merge to `main`; commit early, push after every
commit. **Never touch `~/.amplifier-memory`, the device's systemd units, or any real store; never make a
real model call** — temp instances (`AMPLIFIER_MEMORY_HOME`, `home=`), `AMPLIFIER_MEMORY_UNIT_DIR` and an
injected `model_call=` only.

`main` is now PROTECTED: you cannot push to it and you must not try. Your branch + DONE.json is the whole
delivery; the manager opens the PR.

Read first: `PINS.md`, `AGENTS.md` (incl. the file-ownership rule: a brief whose list lacks the file you
need is a brief defect — write it in `residuals`, do not edit around it), **`contracts/store.v3.md` §11**,
**`contracts/suggestions.v2.md` Core 2, 8, 9, 10**, `src/amplifier_memory/suggest.py::run_suggest` and its
docstring, `src/amplifier_memory/store.py::instance_enabled`.

**Work item:** `amplifier_bundle_memory-h8o` — claim it
(`work_claim(project="amplifier_bundle_memory", item_id="amplifier_bundle_memory-h8o")`), read its
description and acceptance IN FULL (the measured reproduction is in there), resolve it with a reason
written for the steward, read it back with `work_list`, and record the stored resolution's sha256 in DONE.json.

**File ownership — edit ONLY:** `src/amplifier_memory/suggest.py`, `tests/test_suggest.py`,
`conformance/suggestions/run.py`, `conformance/store/run.py`, and `src/amplifier_memory/store.py` ONLY if
`instance_enabled` needs a read-only helper (do not change its semantics). Off-limits: everything else —
`cli.py`, `doctor.py`, `service.py`, `inbox.py`, `llm_config.py`, `modules/**`, `contracts/`, `ledger/`,
`docs/workflow/`, `behaviors/`, `skills/`.

## The defect, reproduced

With `config.yaml` `enabled: false`, `run_suggest` still mined and called the judge **30 times**; only the
write-side refused, and the run reported `degraded:expire failed (InstanceDisabled…)`. store.v3 §11 says
"no timer runs against it" — so this clause is Broken today.

## Outcome

1. **Red first.** Add the failing test/probe that reproduces 30 calls against a disabled instance, and show
   its red output in the commit message or the test's docstring. Then fix.
2. **A disabled instance costs nothing.** `run_suggest` against `enabled: false` makes zero model calls,
   reads nothing from the session capture, attempts no inbox write, exits 0, and emits ONE log line that
   names the instance as deliberately disabled — **not** `degraded:` (that word is for failures; this is a
   choice). Pick the wording to match Core 9's line shape and say what you chose in DONE.json.
3. **Unchanged when enabled.** `enabled: true` behaviour is byte-identical to today.
4. **Checkable.** A conformance probe asserts the discriminating pair — enabled → calls made; disabled →
   none — so store.v3 §11 stops being a promise nobody tests.

## Terminal states and the exit

Items end `PASS` / `FAIL-<cause>` / `BLOCKED-<cause>`. 90 min wall → `BUDGET`: commit what is sound, write
the marker. **Final act: `DONE.json`** (valid JSON) in the worktree root:
`{"lane":"lane-aa-disabled-pass","session_id":"…","verdict":"COMPLETE|BLOCKED|PARTIAL",
"branch":"lane/amplifier_bundle_memory-h8o","head":"…","pushed":true,"items":[…],"residuals":[…],
"pending_human":[],"resources":[],"suite":"…","resolution_sha256":"…","log_line_wording":"…"}`.

## Acceptance — each re-derivable from a durable artefact

- The red-then-green test named in DONE.json, with the red output quoted.
- `uv run pytest -q` green (baseline 343); `uv run ruff check .` and `uv run ruff format --check .` clean.
- `conformance/suggestions/run.py` and `conformance/store/run.py` exit 0 with the new probe Kept and its
  evidence line quoting the call counts it measured (enabled vs disabled).
- `env -u PYTEST_CURRENT_TEST … conformance/cli/run.py` still exit 0 — and the device's timer stamp
  (`systemctl --user show amplifier-memory-suggest-amplifier-memory-c0195169.timer -p ActiveEnterTimestamp`)
  byte-identical before and after your run; print both.
- Item resolved, sha256 recorded.
- Show command output inline; never assert a result without it.
