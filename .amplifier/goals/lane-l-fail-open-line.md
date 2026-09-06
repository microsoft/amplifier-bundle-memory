# Lane lane-l-fail-open-line — the §10 failure line reaches the human

Worker session, alone, in your own worktree of `amplifier-bundle-memory` on branch
`lane/amplifier_bundle_memory-87j`. Work ONLY here; never merge to `main`; commit early, push after
every commit. **Never touch `~/.amplifier/memory`**.

Read first: `contracts/session.v2.md` §10 (FROZEN), the work item's description (lane I measured the
kernel aggregation seven ways), `modules/hooks-memory-inject/amplifier_module_hooks_memory_inject/__init__.py`
— `_render` (~:285, the display-system path lane I built for the announce) and `_fail_open`
(~:343, still returning a `user_message` the kernel drops), `tests/smoke/evidence/announce-rendered-why-not-user_message.txt`,
`conformance/session/inject/run.py` (`check_core_10`).

**Work item:** `amplifier_bundle_memory-87j` — claim it, resolve with a reason for the steward, read
it back with `work_list`, print it.

**File ownership — edit ONLY:** `modules/hooks-memory-inject/**`, `conformance/session/inject/**`,
`tests/smoke/evidence/failopen-*.txt` (new), `ledger/rows.yaml` row AMM-019 (notes only). Off-limits:
everything else — lane K2 is in `modules/tool-memory` and `skills/`.

## Outcome

When the store cannot be read or the writer errors, the human sees one line —
`amplifier-memory: memories not loaded (<reason>); session continues.` — rendered through the same
display-system path as the announce, and the session proceeds unchanged; the error log still gets
its one line. Nothing about the working path changes.

## Exit

PASS / FAIL-<cause> / BLOCKED-<cause>; complete when every item is terminal or shown impossible;
60 min → BUDGET. **Final act: `DONE.json`** in the worktree root with lane `lane-l-fail-open-line`,
branch `lane/amplifier_bundle_memory-87j`, verdict, items, residuals, suite.

## Acceptance — print the evidence

1. `_fail_open` routes its line through `_render` (display system first, `user_message` fallback
   when there is no display system); the line text is exactly session.v2 §10's shape with the
   reason in parentheses, one line, no traceback. `grep -n "_render" …/__init__.py` printed.
2. Test with a spy display system AND a second injecting hook registered on the same event: the
   line reaches the spy once; the error log gains one line; the session's block is absent (fail
   open). Printed.
3. Test: a decodable store with a bad byte does NOT trigger the line (that is U+FFFD + doctor's job,
   lane J) — printed.
4. PTY proof: `AMPLIFIER_MEMORY_HOME` pointing at a directory with no `MEMORY.md`, real `amplifier`
   session, turn 1 shows the one line; save to `tests/smoke/evidence/failopen-turn1.txt`; quote it.
5. `conformance/session/inject/run.py` Core 10 asserts the rendered line (printed, exit 0);
   module pytest + ruff green; root pytest (baseline 146) + ruff green.
6. AMM-019 note updated naming the probe; item resolved and read back.

## Known

- Honesty gate: *"session.v2 §10 — Can't check in this lane because …"*.
- Show command output inline; never assert a result without it.
