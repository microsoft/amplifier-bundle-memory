# Lane lane-13c-inject-framing — the §1 framing sentence for v3, and the no-presumption probe

Worker session, alone, in your own worktree of `amplifier-bundle-memory` on branch
`lane/amplifier_bundle_memory-20e`. Work ONLY here; never merge to `main`; commit early, push after
every commit. **Never touch `~/.amplifier/memory`.** Tests use `AMPLIFIER_MEMORY_HOME` → temp dir.

Read first: `PINS.md`, `AGENTS.md`, **`contracts/session.v3.md` (FROZEN 2026-09-07 — §1 is the exact
framing sentence; §11 counts it toward the ceiling; the Conformance bullet "Nothing the model is given
asserts what the human can or cannot see of a tool call … checked by grep … across `modules/`,
`skills/`, `behaviors/` and `bundle.md`; the kit excludes its own source")**,
`modules/hooks-memory-inject/amplifier_module_hooks_memory_inject/__init__.py` (the framing constant
near line 76; docstrings), its tests, `conformance/session/inject/run.py` (Core 1 re-extracts the §1
sentence from the locked contract and compares byte-for-byte — it must now read `session.v3.md`).

**Work item:** `amplifier_bundle_memory-20e` — claim it
(`work_claim(project="amplifier_bundle_memory", item_id="amplifier_bundle_memory-20e")`), read its
description and acceptance in full, resolve with a reason written for the steward, read it back with
`work_list(project="amplifier_bundle_memory", item_id="amplifier_bundle_memory-20e")`, print it.

**File ownership — edit ONLY:** `modules/hooks-memory-inject/**`, `conformance/session/inject/**`, and
in NEW `conformance/session/budget/run.py` ONLY the function `probe_no_presumption` (lane 13-A owns
`probe_core_11` and `main()` in the same file this wave: if the file is absent when you start, create
it with a two-line `main()` that calls every `probe_*` in the module; if present, add your function
and nothing else). **Off-limits:** `modules/tool-memory/**`, `src/`, `skills/**`, `bundle.md`,
`behaviors/**`, every `README.md`, `ledger/`, `contracts/`, `docs/workflow/`.

## Outcome

The injected block's framing sentence is session.v3 §1, byte-for-byte:

    These are memories of how this human works — hints recorded from past sessions, not ground truth.
    Verify against current reality before acting on one. To change one: `/remember <text>` or `/memory`.

(One paragraph; the contract shows it wrapped as a blockquote — the constant is the unwrapped sentence
exactly as the existing test already extracts it.) The module's docstrings say what the code does —
"renders", "returns", "the line the hook emits" — never what the human reads or sees.
`conformance/session/inject/run.py` re-extracts §1 from `contracts/session.v3.md`.

`conformance/session/budget/run.py::probe_no_presumption` walks `modules/`, `skills/`, `behaviors/`,
`bundle.md` (not `contracts/`, not its own file), greps for the presuming phrases — `the human reads`,
`Say nothing`, `counted, not read`, `what the human reads`, `the human reads nothing` — prints every
hit as `path:line: text`, and exits non-zero on any hit, zero on none.

## Honesty gate — say this if it is true

"On this branch `probe_no_presumption` is red: the phrases still exist in `modules/tool-memory/`,
`skills/`, and the module READMEs, which lanes 13-A and 13-B own — here is the printed hit list. The
probe itself is proven green against a fixture tree with no hits." Both printed runs go in the lane
log; the sentence goes in `DONE.json`'s `residuals`. A probe that is green on this branch today is the
falsifier: it is not looking where the phrases are.

## Terminal states and the exit

Items end `PASS` / `FAIL-<cause>` / `BLOCKED-<cause>`. 90 min wall → `BUDGET`: commit what is sound,
write the marker. **Final act: `DONE.json`** (valid JSON) in the worktree root — **never `git add` it**:
`{"lane":"lane-13c-inject-framing","session_id":"…","verdict":"COMPLETE|BLOCKED|PARTIAL",
"branch":"lane/amplifier_bundle_memory-20e","head":"…","pushed":true,"items":[…],"residuals":[…],
"suite":"…"}`. On BLOCKED also write `BLOCKED.md`. Two exits and no third: **A) SUCCESS** — every item
met with evidence printed, committed and pushed, queue item resolved and read back; **B) BLOCKED** — a
named cause that stops every deliverable. A criterion outside your file ownership is a residual, exit A.

## Acceptance — every item names a file or a command whose output you print, and its falsifier

1. `python conformance/session/inject/run.py` prints `Core 1 — Kept` and names `contracts/session.v3.md`
   as the source of the re-extracted sentence; `grep -n "session.v2" conformance/session/inject/run.py modules/hooks-memory-inject -r` prints nothing. Printed. **False if** the kit compares against a
   literal instead of re-extracting from the contract.
2. `cd modules/hooks-memory-inject && uv run --offline pytest -q` — green, printed — including the
   existing byte-identity-across-instances test and the framing-sentence test updated to v3 §1.
   **False if** any test was deleted rather than updated.
3. `grep -rn "the human reads\|human reads\|what the human sees" modules/hooks-memory-inject` prints
   nothing. Printed. **False if** the output is not from the committed state.
4. `python conformance/session/budget/run.py` (or `python -c "from conformance.session.budget.run import probe_no_presumption; probe_no_presumption()"` if `main()` is not yet yours to run) against
   the current tree prints the hit list with `path:line` and exits non-zero; against a temp fixture
   tree containing `modules/x.py` with no hits it exits zero — both runs printed. **False if** the
   probe scans `contracts/` or its own source, or the fixture run is not shown.
5. `uv run --offline pytest -q` at the repo root and `ruff check .` — printed, green (a root-level
   failure that depends on 13-A/13-B files is a named residual).
6. Queue item `20e` resolved, then read back with `work_list` and printed. **False if** the printed
   reason asserts something you know to be untrue or omits a residual you recorded.
