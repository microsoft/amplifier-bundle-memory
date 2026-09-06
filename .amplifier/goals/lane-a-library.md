# Lane lane-a-library — the `amplifier_memory` library: store writer, `init`, public API

You are a worker session, alone, in your own git worktree of `amplifier-bundle-memory`
on branch `lane/amplifier_bundle_memory-3q5`. Work ONLY here; never touch the main
checkout or sibling worktrees; never merge to `main`. Commit early; push to `origin`
after every commit (`git push -u origin HEAD`).

Read first, in this order: `PINS.md`, `AGENTS.md`, `contracts/store.v1.md`
(FROZEN — the law for this lane), `contracts/cli.v1.md` §9, `ledger/rows.yaml`
(rows AMM-001…AMM-010 are yours).

**Work item:** `amplifier_bundle_memory-3q5` in project `amplifier_bundle_memory`.
Claim it with `work_claim(project="amplifier_bundle_memory", item_id="amplifier_bundle_memory-3q5")`.
At the end, `work_resolve` it with a reason written for the steward, then **read it
back** with `work_list(project="amplifier_bundle_memory", item_id="amplifier_bundle_memory-3q5")`
and print the stored reason. The printed read-back is the evidence; the resolve call is not.

**File ownership — edit ONLY:** `pyproject.toml`, `uv.lock`, `src/amplifier_memory/__init__.py`,
`src/amplifier_memory/store.py`, `src/amplifier_memory/_git.py` (optional),
`src/amplifier_memory/py.typed`, `tests/conftest.py`, `tests/test_store.py`,
`conformance/store/**`, `conformance/__init__.py`, `ledger/checks/test_row_amm_000_sync.py`
plus the `ledger/rows.yaml` rows AMM-000…AMM-010 (disposition + notes only). Everything
else is off-limits — `src/amplifier_memory/cli.py`, `modules/`, `skills/`, `behaviors/`,
`bundle.md`, `contracts/`, `docs/`, `README.md`. A change you need outside this set is a
**residual**: record it, do not make it.

## Outcome

`import amplifier_memory` gives any caller — the click CLI (lane D), the memory tool and
inject hook (lanes B/C), the Phase 2 job — the whole store behaviour with **no dependency
on click or on Amplifier**: `init`, `save`, `forget`, `list_memories`, `log_usage`, `why`,
`store_home`, and the exceptions a refusal raises. Every mutation is exactly one git commit
whose message carries id · text · verbatim human quote · session id · writer. Every cap in
store.v1 is enforced by this code, not by advice. cli.v1 §9: this library IS the reference
implementation.

## Terminal states and the exit

Each acceptance item ends `PASS`, `FAIL-<named cause>`, `BLOCKED-<named cause>`, or
`PENDING-HUMAN`. Complete when **either** every item reaches a terminal state, **or** it is
conclusively demonstrated the remainder cannot, naming the blocker for each. Items ending
FAIL or BLOCKED are residuals, not failures of the goal. Exceeding the time bound (90 min
wall) is the terminal state `BUDGET`: commit what is sound and write the marker — never rush
or skip the commit. There is no improving after the marker is written.

**Final act — write `DONE.json` in the worktree root** (it is gitignored; never commit it):
`{"lane":"lane-a-library","session_id":"<this session's id>","verdict":"COMPLETE|BLOCKED|PARTIAL",
"branch":"lane/amplifier_bundle_memory-3q5","head":"<sha>","pushed":true,
"items":[{"id":"1","state":"PASS","note":"…"},…],"residuals":[…],"pending_human":[],
"resources":[],"suite":"<pytest summary line>"}`. `verdict` is exactly one of those three words.
If a cause stops every deliverable, also write `BLOCKED.md` (gitignored) naming it.

## Acceptance — every item names a file or a command whose output you print

1. `pyproject.toml`: `[project] name = "amplifier-memory"`, hatchling build,
   `[project.scripts] amplifier-memory = "amplifier_memory.cli:main"`, dependency `click`
   (declared now; lane D writes `cli.py`); `[tool.hatch.metadata] allow-direct-references = true`.
   `uv sync && uv run python -c "import amplifier_memory, sys; print(amplifier_memory.__all__)"`
   printed. **False if** the import pulls in click or anything from `amplifier_*`
   (prove: `uv run python -c "import amplifier_memory, sys; print([m for m in sys.modules if m.startswith(('click','amplifier_core','amplifier_foundation'))])"` prints `[]`).
2. `src/amplifier_memory/__init__.py` `__all__` is exactly
   `["init","save","forget","list_memories","log_usage","why","store_home","MemoryError","CapExceeded","DuplicateMemory","UnknownId","QuoteNotHuman","StoreMissing"]`.
   Print it. False if the printed list differs from the committed file.
3. store.v1 §1–§2, cli.v1 §8: `init(home)` creates exactly `MEMORY.md`, `topics/`,
   `declined.md`, `inbox.md`, `usage.jsonl` (and `topics/.gitkeep` so the dir is tracked)
   plus ONE initial commit, sets `user.name`/`user.email` in the store repo's own config, and a
   second `init` changes nothing and returns a result whose `.existed` is True. Test prints the
   store's `git log --oneline` after both calls (one line). False if the second call adds a commit.
4. store.v1 §3–§4 discriminating pair: the 200th `MEMORY.md` line saves; the 201st raises
   `CapExceeded` whose message contains `200` and both remedies ("topic file", "/forget").
   Headings and blank lines count toward the cap. Printed.
5. store.v1 §5: the 151st line of a topic file and the 51st topic file raise `CapExceeded`.
   Printed.
6. store.v1 §6: every writer commit message carries `[m-NNN]`, the text, `quote: "<verbatim>"`,
   `session: <id>`, `writer: human|assistant|suggestion`; `why("m-001")` parses them back from
   `git log --grep '\[m-001\]'`. Print one real commit message from the test store. False if any
   of the five fields is absent from the printed message.
7. store.v1 conformance bullets 3–4: exact duplicate line → `DuplicateMemory`; `forget("m-001")`
   removes the line and commits; the next id after a forget is strictly greater than every id
   ever issued (ids never reused — track the high-water mark in the git history, not in a
   counter file; store.v1 §2 says no other files are memory). Printed.
8. store.v1 §8: `log_usage(event, target, session_id)` appends one JSON line
   `{ts, event, target, session_id}` and drops entries older than 90 days on each write; test
   seeds a 91-day-old line and prints line counts before/after.
9. session.v1 §5 / store.v1 §6: `save(text, quote, writer, session_id, human_turns)` raises
   `QuoteNotHuman` unless `quote` is a substring of at least one string in `human_turns` — the
   library owns the check; callers supply the turns. For `writer="human"` the quote is the text
   itself and must still appear in `human_turns`. Discriminating pair printed.
10. `StoreMissing` is raised (never a bare OSError) when the home has no `MEMORY.md`; `store_home()`
    honours `AMPLIFIER_MEMORY_HOME` and defaults to `~/.amplifier/memory`. Printed.
11. `conformance/store/run.py` runs against a fresh temp store and prints exactly one line per
    store.v1 Core clause 1–10 in the form `Core N — Kept|Not yet|Broken|Can't check — <one-line
    evidence>`, exits 0, and its printed output is shown. False if a clause prints Kept without a
    check in that file that could have failed, or the run is stubbed or patched.
12. `ledger/checks/test_row_amm_000_sync.py` asserts the sha256 of the three locked contract files
    equals the SYNC row; you may update rows AMM-000…AMM-010 to `CONFORMS` ONLY where the
    matching probe in `conformance/store/run.py` passes, and each such row's `assertion.ref` names
    that probe function. Print `git diff --stat -- ledger/rows.yaml`. False if any row flips to
    CONFORMS without a passing probe named in it.
13. `uv run pytest -q` and `uv run ruff check .` printed, green, with counts. False if a test was
    skipped or a check weakened to get green, or the output is not this run's.
14. Item resolved, read back with `work_list`, stored reason printed. False if the printed reason
    asserts anything you know to be untrue or omits a correction you made after storing it and
    that is not reachable from the reason itself.

## Scope-outs

No `click` import anywhere in your files. No Amplifier imports. Never touch
`~/.amplifier/memory` — tests set `AMPLIFIER_MEMORY_HOME` to `tmp_path` (put that in
`tests/conftest.py` as an autouse fixture that also guards against the real path). No network. No
services, containers or background processes. Do not edit contracts or docs; a contract you
believe is wrong is a residual naming the clause and the cost.

## Known

- Honesty gate: if a clause cannot be proven by a check that could have failed, the sentence
  is *"store.v1 Core N — Can't check in this lane because …"*, printed by `conformance/store/run.py`
  and repeated in the resolution reason.
- Git via `subprocess.run([...], cwd=home, check=True, capture_output=True)`; `_git.py` is a good
  place. AGENTS.md rule 10: assert the post-state before you commit; gate the commit on the assert.
- AGENTS.md rule 5: any argv you shell (`git`) is verified against `git --help`-level truth in your
  tests by running it, not by assuming.
- Python 3.11+; `uv` is on PATH; `hatchling` for the build.
- Show command output inline in your work; never assert a result without it. Print, then claim.
