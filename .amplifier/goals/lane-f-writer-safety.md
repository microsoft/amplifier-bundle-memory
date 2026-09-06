# Lane lane-f-writer-safety — the writer is safe under concurrent calls, and never lies

You are a worker session, alone, in your own git worktree of `amplifier-bundle-memory` on
branch `lane/amplifier_bundle_memory-cop`. Work ONLY here; never touch the main checkout or
sibling worktrees; never merge to `main`. Commit early; push after every commit
(`git push -u origin HEAD`). **Never touch `~/.amplifier/memory`** — that is the steward's real
store, and it was corrupted once already by the bug you are fixing; every test uses
`AMPLIFIER_MEMORY_HOME=tmp_path` (conftest guards this — keep the guard).

Read first: `PINS.md`, `AGENTS.md` (rules 1, 7, 8, 10, 11), `contracts/store.v1.md` (FROZEN) §1,
§3, §4, §6, §9, `contracts/session.v1.md` §5, `.converge/feedback/2026-09-06-kicked-the-tires-transcript.md`
(the steward's real session — the evidence, read it whole), `src/amplifier_memory/store.py`,
`_git.py`, `doctor.py`, `modules/tool-memory/amplifier_module_tool_memory/__init__.py`
(the `execute` path and the tool description), `modules/hooks-memory-inject/.../__init__.py`
(the announce text), `docs/workflow/CHECK-RECORD.md` (what is already proven).

**Work item:** `amplifier_bundle_memory-cop` in project `amplifier_bundle_memory`. Claim with
`work_claim(project="amplifier_bundle_memory", item_id="amplifier_bundle_memory-cop")`; read its
description — it carries the verbatim evidence and the six-part definition of fixed. At the end
`work_resolve` with a reason written for the steward (what changed for them, the honest caveat,
the check they can run), then **read it back** with `work_list(...)` and print the stored reason.

**File ownership — edit ONLY:** `src/amplifier_memory/store.py`, `_git.py`, `doctor.py`,
`__init__.py` (exports only), `cli.py` (ONLY to add `--repair` to `doctor`), `tests/test_store.py`,
`tests/test_concurrency.py` (new), `tests/test_doctor.py`, `tests/test_cli.py` (only the doctor
repair test), `conformance/store/run.py` (add `probe_concurrency`, extend Core 1/Core 9 probes),
`modules/tool-memory/amplifier_module_tool_memory/__init__.py` (ONLY the tool description
text), `modules/hooks-memory-inject/amplifier_module_hooks_memory_inject/__init__.py` (ONLY the
empty-store announce placeholder) and that module's tests for that string, `ledger/rows.yaml`
rows AMM-001 and AMM-008 (disposition/notes only). Everything else is off-limits.

## Outcome

Any number of concurrent `save`/`forget`/`log_usage` calls — threads in one session, or
several sessions at once — serialize on the store and each leaves exactly one well-formed
commit; a call reports success only after re-reading the committed tree and finding its own
line present (save) or absent (forget); a git failure is one plain sentence, never an argv dump;
a store whose `MEMORY.md` is malformed is named by `doctor` with the commit to restore from,
and `doctor --repair` restores it in one visible commit. The model is told to save one memory
per call. Nobody ever repairs the store by hand again.

## Terminal states and the exit

Each acceptance item ends `PASS`, `FAIL-<cause>`, `BLOCKED-<cause>`, or `PENDING-HUMAN`. Complete
when **either** every item reaches a terminal state, **or** it is conclusively demonstrated the
remainder cannot, naming the blocker for each. FAIL/BLOCKED items are residuals. 90 min wall →
terminal `BUDGET`: commit what is sound, write the marker. No improving after the marker.

**Final act — write `DONE.json` in the worktree root** (gitignored):
`{"lane":"lane-f-writer-safety","session_id":"<this session's id>","verdict":"COMPLETE|BLOCKED|PARTIAL",
"branch":"lane/amplifier_bundle_memory-cop","head":"<sha>","pushed":true,"items":[…],"residuals":[…],
"pending_human":[],"resources":[],"suite":"<pytest summary>"}`.

## Acceptance — every item names a file or a command whose output you print

1. **Lock.** `store.py`: every mutating path (`save`, `forget`, `log_usage`, `init`, topic
   writes) runs inside one exclusive `fcntl.flock` on `<home>/.lock` (blocking, bounded wait
   ≤ 10 s, then a one-line `StoreBusy` error). `.lock` is git-ignored inside the store (`init`
   writes the store's `.gitignore`; store.v1 §2 "a file not listed here is not memory" — say in
   the docstring that `.lock` and `.gitignore` are plumbing, not memory). `grep -n flock
   src/amplifier_memory/store.py` printed.
2. **Verify after commit.** After `git commit`, the writer runs `git show HEAD:MEMORY.md` and
   asserts: for `save`, the exact new line is present and every line parses as store.v1 §3
   (`- [m-NNN] text` or a `## heading` or blank); for `forget`, the line is absent. Failure →
   raise `WriteNotLanded` (one sentence), never a success return. Fault-injection test prints
   the raise.
3. **Concurrency probe.** `tests/test_concurrency.py`: 8 saves via `ThreadPoolExecutor(8)` on
   one temp store → `MEMORY.md` has exactly 8 well-formed lines, ids `m-001..m-008` with no gap
   or duplicate, 8 save commits, and each call's returned id is present in `git show
   HEAD:MEMORY.md`. Two concurrent forgets of different ids → both gone, both return truthfully.
   Two concurrent saves of the SAME text → one `m-NNN`, one `DuplicateMemory`. Printed.
4. **Honest git errors.** Any `subprocess.CalledProcessError` from git is wrapped into a
   `MemoryError` subclass whose message is one sentence naming the operation and git's first
   stderr line — never the argv list. "nothing to commit" after a concurrent sweep is reported
   as `already applied by a concurrent write` (not a failure). Test prints both messages.
5. **`doctor` detects; `doctor --repair` restores.** `amplifier_memory.verify_store(home)`
   returns malformed lines with line numbers; `doctor` shows a `[FAIL] MEMORY.md well-formed`
   row naming them and the last commit whose `MEMORY.md` parsed clean, exit 1.
   `amplifier-memory doctor --repair` restores that commit's `MEMORY.md`, commits
   `repair: restore MEMORY.md from <sha> (malformed lines: N)`, prints what it did, and never
   runs without printing the diff first. Test seeds the exact headless fragment from the
   transcript and prints doctor before/after.
6. **Tool description.** `modules/tool-memory` description gains, verbatim: `Save ONE memory
   per call and wait for its result before the next; never issue memory calls in parallel.`
   `grep -n 'ONE memory per call' modules/tool-memory/**/__init__.py` printed. Module pytest green.
7. **Announce placeholder.** The empty-store announce no longer renders `/remember  to add
   one.`: change `<text>` to a form terminals keep (recommend `/remember <your preference>` is
   NOT safe — angle brackets are the problem; use `/remember …your words…` or
   `` `/remember <text>` `` in backticks and prove which survives by printing it through the
   same Rich markup path `amplifier run` uses, or state honestly that you could only verify the
   string in the block). Hook tests updated, green. session.v1 §2's text is exact; if your
   change alters the contract's literal sentence, say so in the resolution — the manager will
   carry it as an edit to the pending session.v1 candidate rather than have you edit a locked
   file.
8. **Conformance.** `conformance/store/run.py::probe_core_1` now includes the concurrency
   probe; `probe_core_9` asserts a hand edit and a writer commit interleaved under the lock both
   land. Output printed, exit 0, Core 1 and Core 9 Kept. Flip AMM-001/AMM-008 from VIOLATION to
   CONFORMS naming the probes; `git diff --stat -- ledger/rows.yaml` printed.
9. `uv run pytest -q` (root, baseline 84) and `uv run ruff check .` printed green; module suites
   green (`cd modules/tool-memory && uv run pytest -q`; same for hooks-memory-inject).
10. Item resolved, read back with `work_list`, stored reason printed. The reason tells the
    steward, in plain words, what the bug was, that their store is now safe, that the two
    memories they kept (m-003, m-005) were not touched by this lane, and that after `amplifier-memory
    update` new sessions get the fix. False if it asserts anything you know to be untrue.

## Scope-outs

Never read or write `~/.amplifier/memory`. Do not run `amplifier-memory update` or install
anything. No edits to contracts, docs, README, skills, behaviors, bundle.md, or `update.py`.

## Known

- Honesty gate: *"store.v1 Core N — Can't check in this lane because …"* in `run.py` and the reason.
- `flock` is advisory and per-process-safe on Linux; use a module-level `threading.Lock` too so
  threads in one process do not share the same fd's flock semantics by accident (flock is
  per-open-file-description — open the lock file per call).
- `git show HEAD:MEMORY.md` reads the committed tree, which is the assertion that matters;
  the working tree can be dirty from a hand edit in progress (store.v1 §9 allows that).
- Show command output inline; never assert a result without it. Print, then claim.
