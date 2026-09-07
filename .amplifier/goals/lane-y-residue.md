# Lane lane-y-residue — four small defects left by wave 15b, fixed together

Worker session, alone, in your own worktree of `amplifier-bundle-memory` on branch
`lane/amplifier_bundle_memory-residue`. Work ONLY here; never merge to `main`; commit early, push after
every commit. **Never touch `~/.amplifier/memory`, `~/.amplifier-memory`, or the device's systemd units;
never run a real model call, a real `service install`, or `update`** — temp instances and injected runners
only (`AMPLIFIER_MEMORY_HOME`, `home=`, `AMPLIFIER_MEMORY_UNIT_DIR`, `runner=`).

Read first: `PINS.md`, `AGENTS.md` (incl. "Lane acceptance criteria are re-derivable from durable artefacts"),
`contracts/cli.v3.md` §5 and §8, `contracts/suggestions.v2.md` Core 3 and Core 8, `docs/workflow/CHECK-RECORD.md`
entry 15b (the residuals this lane closes), `ledger/README.md` or the row shape in `ledger/rows.yaml`.

There is no work item for this lane: the manager derived it from CHECK-RECORD 15b's residuals. Do not file one.

**File ownership — edit ONLY:** `src/amplifier_memory/store.py` (dead timer arm only), `src/amplifier_memory/doctor.py`
(`llm_row` only), `src/amplifier_memory/suggest.py` (only if `judge_detail`/`resolve_judge` need a small signature
tweak for doctor), `src/amplifier_memory/__init__.py` (exports), `tests/test_store.py`, `tests/test_doctor.py`,
`tests/test_suggest.py`, `conformance/cli/run.py` (`probe_core_5` only), `ledger/rows.yaml` (the four `assertion.ref`
fields named below and nothing else). Off-limits: everything else, especially `contracts/`, `docs/workflow/`, `modules/**`.

## Outcome — the four residuals, each with its check

1. **Dead code gone.** `store._install_timer` (and its `device_store()` gate if nothing else calls it) is removed;
   `store.init(timer=…)` either loses the parameter or keeps it only as a documented no-op — pick whichever leaves
   `grep -rn "_install_timer\|device_store" src/ conformance/ tests/` empty except for a changelog-style comment.
   Every caller (`instance.build_instance`, kits, tests) still passes.
2. **One rendering of the judge.** `doctor.llm_row(config=None, *, home=None)` renders through
   `suggest.judge_detail(...)` / `resolve_judge(...)` so doctor and the job say the same thing; the three states
   (configured provider/model · role recorded, not resolvable on this host · inherited + last run's measured cost)
   and the WARN for an unreadable config.yaml are preserved. `tests/test_doctor.py -k llm_row` asserts the
   INHERITED / APP_DEFAULT / `config.yaml` / role / cost words as before.
3. **The kit carries §5.** `conformance/cli/run.py::probe_core_5` asserts the judge row's WORDING for at least the
   inherited state and the configured state (not merely the row's presence) — the reconciler's AMM-024 note says
   exactly which assertions live only in tests today; move them.
4. **Exact ledger refs.** In `ledger/rows.yaml`: AMM-012 and AMM-017 name a bare kit path `conformance/session/tool/run.py`
   — make each `…::<the check function that covers that clause>`; AMM-014 and AMM-015 name a test PREFIX
   (`test_row_amm_014`, `test_row_amm_015`) that resolves to three functions each — name the exact function(s)
   (one `ref` per row is fine if one function alone proves the clause; otherwise list them in `notes` and cite the
   primary). Run `uv run pytest -q ledger/checks` after; do not touch any disposition, quote, or hash.

## Terminal states and the exit

Items end `PASS` / `FAIL-<cause>` / `BLOCKED-<cause>`. 90 min wall → `BUDGET`: commit what is sound, write the
marker. **Final act: `DONE.json`** (valid JSON) in the worktree root:
`{"lane":"lane-y-residue","session_id":"…","verdict":"COMPLETE|BLOCKED|PARTIAL","branch":"lane/amplifier_bundle_memory-residue",
"head":"…","pushed":true,"items":[{"id":"residual-1..4","status":"PASS|…"}],"residuals":[…],"pending_human":[],"resources":[],"suite":"…"}`.

## Acceptance — each re-derivable from a durable artefact

- `uv run pytest -q` green (baseline 337); `uv run ruff check .` and `uv run ruff format --check .` clean.
- `env -u PYTEST_CURRENT_TEST AMPLIFIER_MEMORY_HOME=<tmp> AMPLIFIER_MEMORY_UNIT_DIR=<tmp> uv run python conformance/cli/run.py`
  exit 0 with Core 5 Kept and its evidence line quoting the judge-row wording it checked;
  `conformance/suggestions/run.py` and `conformance/store/run.py` exit 0.
- `grep -rn "_install_timer\|device_store" src/ conformance/ tests/` prints nothing (or only a comment naming the removal).
- `uv run pytest -q ledger/checks` → 2 passed; `git diff main -- ledger/rows.yaml` touches exactly four `ref:` lines
  (+ optional `notes:` additions) and nothing else.
- Show command output inline; never assert a result without it.
