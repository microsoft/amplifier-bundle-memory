# Lane lane-d-cli — `amplifier-memory`: click over the library, plus status/doctor/why

You are a worker session, alone, in your own git worktree of `amplifier-bundle-memory` on
branch `lane/amplifier_bundle_memory-5hg`. Work ONLY here; never touch the main checkout or
sibling worktrees; never merge to `main`. Commit early; push after every commit
(`git push -u origin HEAD`).

Read first: `PINS.md`, `AGENTS.md` (rules 4, 5, 9, 10, 11), `contracts/cli.v1.md` (FROZEN — the
law for this lane) all of it, `contracts/store.v1.md` §6, §8, §9, `docs/VISION.md` §9 (the numbers
`status` exists to show), `src/amplifier_memory/__init__.py`, `store.py`, `_git.py` (the library
you extend and wrap; 33 tests in `tests/test_store.py` must stay green), `conformance/store/run.py`
(the kit shape to copy for `conformance/cli/run.py`).

**Work item:** `amplifier_bundle_memory-5hg` in project `amplifier_bundle_memory`. Claim with
`work_claim(project="amplifier_bundle_memory", item_id="amplifier_bundle_memory-5hg")`. At the end
`work_resolve` with a reason for the steward, then **read it back** with `work_list(...)` and print
the stored reason — the printed read-back is the evidence.

**File ownership — edit ONLY:** `src/amplifier_memory/**` (add `status.py`, `doctor.py`, `cli.py`;
edit `__init__.py`, `store.py`, `_git.py` as the items below require), `tests/test_cli.py`,
`tests/test_status.py`, `tests/test_doctor.py`, `tests/test_store.py` (ONLY for the identity change
in item 9), `tests/conftest.py` (fixtures only), `conformance/cli/**`, `conformance/store/run.py`
(ONLY if item 9 needs it), `README.md` (ONLY the "Use" → "From a shell" lines and the CLI comment
in Install step 2), and `ledger/rows.yaml` rows AMM-020…AMM-028 (disposition + notes only).
Off-limits: `modules/**`, `skills/**`, `behaviors/**`, `bundle.md`, `conformance/session/**`,
`contracts/`, `docs/`. Lane C is editing `modules/` right now.

## Outcome

`amplifier-memory` is a `click` group whose every command is: parse → one call into
`amplifier_memory` → print → exit code. `status` shows the VISION §9 numbers from git and
`usage.jsonl`; `why <id>` formats the commit history of one memory; `doctor` never mutates and
runs the update-check trio; `init` creates the store or says it exists; `review`, `service`,
`update`, `suggest` say honestly what Phase 1 does not have. Every behaviour is a public library
function first (cli.v1 §9). Hand commits inside the store keep the human's own git identity
(store.v1 §9).

## Terminal states and the exit

Each acceptance item ends `PASS`, `FAIL-<named cause>`, `BLOCKED-<named cause>`, or
`PENDING-HUMAN`. Complete when **either** every item reaches a terminal state, **or** it is
conclusively demonstrated the remainder cannot, naming the blocker for each. Items ending FAIL or
BLOCKED are residuals, not failures of the goal. Exceeding the time bound (100 min wall) is the
terminal state `BUDGET`: commit what is sound and write the marker. No improving after the marker.

**Final act — write `DONE.json` in the worktree root** (gitignored; never commit it):
`{"lane":"lane-d-cli","session_id":"<this session's id>","verdict":"COMPLETE|BLOCKED|PARTIAL",
"branch":"lane/amplifier_bundle_memory-5hg","head":"<sha>","pushed":true,"items":[…],"residuals":[…],
"pending_human":[],"resources":[],"suite":"<pytest summary>"}`. If a cause stops every deliverable,
also write `BLOCKED.md` (gitignored) naming it.

## Acceptance — every item names a file or a command whose output you print

1. cli.v1 §1 verb surface: `uv run amplifier-memory --help` lists exactly `init status why review
   doctor service update suggest` (plus click's help); `uv run amplifier-memory bogus` prints a
   one-line error and exits 2; `upgrade` is an alias of `update`. Printed.
2. cli.v1 §9 thin wrapper: `grep -n '^import\|^from' src/amplifier_memory/cli.py` prints only
   `click` and `amplifier_memory` imports (and stdlib `sys` if needed — say so); every command body
   is ≤ ~10 lines: parse, one library call, print. `__all__` gains `status`, `doctor`, `review`,
   `update_check` (or the names you choose — list them in the README line). Print `__all__`.
3. cli.v1 §2 `status`: `amplifier_memory.status(home) -> StatusReport` computed from git and
   `usage.jsonl`: memories in MEMORY.md; written / forgotten in the last 7 and 30 days; **kept**
   (written ≥ 7 days ago and still present); topics and how many are stale (no `read` event in
   90 days); pending suggestions (inbox.md line count, 0 in Phase 1); last suggest run (none).
   Fixture: a temp store whose git history you construct with backdated commits
   (`GIT_AUTHOR_DATE`/`GIT_COMMITTER_DATE`) — assert exact numbers; print the one-screen output.
   False if numbers come from anywhere but git + usage.jsonl.
4. cli.v1 §3 `why m-001`: prints text, verbatim quote, session id, writer and date for the creation
   commit and the forget commit if any; unknown id → one-line error, nonzero exit. Printed pair.
5. cli.v1 §4 `review`: empty inbox → says so, exit 0. Printed.
6. cli.v1 §5 `doctor`: rows — store present and is a git repo · cap headroom (MEMORY.md N/200,
   topics N/50) · stale topics · inbox size and oldest · suggest timer (INFO "Phase 2 not installed")
   · substrate (INFO) · update check. Never mutates: `sha256sum` of every store file before/after
   is identical (printed). Exit code nonzero only on a failed check (store missing → nonzero;
   printed). Update-check trio: `amplifier_memory.update_check(installed_sha, remote_sha)` → WARN
   with remedy when behind / OK when current / INFO "not checkable" when offline — three printed
   cases with the network call injectable so tests need no network.
7. cli.v1 §6, §7, §1: `service <verb>` prints "Phase 1 has no service; the suggest timer arrives
   with Phase 2" and exits 0; `suggest` prints "Phase 2 not installed" exit 0; `update` in this lane
   prints what it will do (uv tool upgrade + app-bundle refresh + doctor + stale-in-memory note) and
   runs ONLY `doctor` — the real upgrade path is lane E's. Printed.
8. cli.v1 §8 `init`: creates the store; second run prints the store-exists message, changes
   nothing (printed `git log --oneline` before/after). Uses `amplifier_memory.init`.
9. store.v1 §9 identity (carried from wave 1): `init` no longer writes `user.name`/`user.email`
   into the store repo's config; the writer passes identity per commit
   (`git -c user.name=amplifier-memory -c user.email=… commit …`) so a human's own `git commit` in
   the store carries the human's identity. Test: after `init`, `git config --get user.name` in the
   store fails (unset) AND a writer commit's author is `amplifier-memory`. All 33 existing tests
   green. Printed.
10. `conformance/cli/run.py` prints one line per cli.v1 Core clause 1–9 as `Core N — Kept|Not
    yet|Broken|Can't check — <evidence>` (Core 7 `update`'s real path → Not yet, lane E), exits 0;
    printed. Flip rows AMM-020…AMM-028 to CONFORMS only where the named probe passes; print
    `git diff --stat -- ledger/rows.yaml`.
11. `uv run pytest -q` (root) and `uv run ruff check .` (root) printed green with counts; the
    wave-1 baseline is 33 passed. False if a test was skipped or a check weakened.
12. Item resolved, read back with `work_list`, reason printed; false if the reason asserts anything
    you know to be untrue.

## Scope-outs

Never touch `~/.amplifier/memory`; tests use `AMPLIFIER_MEMORY_HOME=tmp_path` (conftest already
guards this — keep the guard). No network in tests (inject the remote lookup). Never
`uv tool install` or `amplifier bundle add` anything. Do not edit `modules/`, `skills/`,
`behaviors/`, `bundle.md`, contracts or docs.

## Known

- Honesty gate: *"cli.v1 Core N — Can't check in this lane because …"* in `run.py` and the reason.
- AGENTS rule 5: every shelled argv (`git`, `uv tool`) is verified against that CLI's `--help` in
  your tests by running it, output shown — `amplifier run --once` shipped once without existing.
- `click` is already a declared dependency (`pyproject.toml`); the console script
  `amplifier-memory = "amplifier_memory.cli:main"` is declared — you write `main`.
- Show command output inline; never assert a result without it. Print, then claim.
