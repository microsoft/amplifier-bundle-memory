# Lane lane-g-writer-hardening — atomic writes, encoding floor, honest repair, quote floor

Worker session, alone, in your own worktree of `amplifier-bundle-memory` on branch
`lane/amplifier_bundle_memory-6lp`. Work ONLY here; never merge to `main`; commit early, push
after every commit (`git push -u origin HEAD`). **Never touch `~/.amplifier/memory`** — tests use
`AMPLIFIER_MEMORY_HOME=tmp_path` (conftest guards this; keep the guard).

Read first: `PINS.md`, `AGENTS.md` (rules 1, 5, 10, 11), `contracts/store.v1.md` (FROZEN) §1, §3,
§6, R2, `contracts/session.v1.md` §5, `docs/workflow/reviews/engineering-council-2026-09-06.md`
(sections on atomic write, encoding/argv floor, repair, quote floor — read the reproductions),
`src/amplifier_memory/store.py`, `_git.py`, `doctor.py`, `tests/test_concurrency.py` (lane F's
lock + assert — build on it, do not undo it), `docs/workflow/CHECK-RECORD.md` (wave 4).

**Work item:** `amplifier_bundle_memory-6lp` — claim it (`work_claim(project="amplifier_bundle_memory",
item_id="amplifier_bundle_memory-6lp")`), read its description (the exact defects and fixes), and at
the end `work_resolve` with a reason written for the steward, then read it back with `work_list`
and print the stored reason.

**File ownership — edit ONLY:** `src/amplifier_memory/{store,_git,doctor,__init__}.py`,
`tests/test_store.py`, `tests/test_concurrency.py`, `tests/test_hostile.py` (new), `tests/test_doctor.py`,
`conformance/store/run.py`. Off-limits: `modules/**`, `skills/**` (lane H is there now), `cli.py`
(unless a doctor row needs one printed line — then only that), contracts, docs, README.

## Outcome

A save can no longer leave the store in a state the hook would publish but the writer would deny:
the writer writes atomically, asserts the working tree it just wrote (the same file the hook reads)
parses clean and carries the line, and reverts on any failure so nothing half-written is ever
staged. A hostile text — a Unicode line separator, a control character, a stray byte, an oversize
line — is refused in one sentence before anything touches disk, and a store that already carries
one is named by `doctor` with the offset, never a traceback. `repair` shows what it throws away.
A quote of one letter no longer passes the human-turn check.

## Terminal states and the exit

Items end `PASS` / `FAIL-<cause>` / `BLOCKED-<cause>` / `PENDING-HUMAN`. Complete when either every
item is terminal or the remainder is conclusively shown impossible with the blocker named. 90 min
wall → `BUDGET`: commit what is sound, write the marker. **Final act: `DONE.json` in the worktree
root** (gitignored): `{"lane":"lane-g-writer-hardening","session_id":"…","verdict":"COMPLETE|BLOCKED|PARTIAL",
"branch":"lane/amplifier_bundle_memory-6lp","head":"…","pushed":true,"items":[…],"residuals":[…],
"pending_human":[],"resources":[],"suite":"…"}`.

## Acceptance — every item names a file or a command whose output you print

1. **Atomic + working-tree assert.** `store.py` writes `MEMORY.md`/topic files via a temp file in
   the same directory + `os.replace`, inside lane F's lock; after `git commit`, `_assert_saved`
   re-reads the **working tree** file (not only `HEAD:`) and asserts every line parses and the
   new line is present; on any failure after the write, the working file is restored from `HEAD`
   and `git status --porcelain` is empty. Fault-injection test prints the revert.
2. **Separators refused before writing.** A memory text containing any of Python's
   `str.splitlines()` separators beyond `\n` (`\r`, `\x0b`, `\x0c`, `\x1c`–`\x1e`, `\x85`,
   `\u2028`, `\u2029`) or any C0 control char is refused with one sentence naming the character
   (e.g. `refused: memory text contains a line separator (U+2028); one memory is one line`);
   `sha256sum MEMORY.md` identical before/after, printed.
3. **Tolerant reads, honest doctor.** With one raw `\xe9` byte appended to `MEMORY.md`:
   `list_memories` returns the parseable lines and reports the bad one; `amplifier-memory doctor`
   prints `[FAIL] MEMORY.md well-formed — byte offset N is not UTF-8` and exit 1 with **no
   traceback** (printed). Every read of store files uses an explicit `encoding="utf-8"` with a
   decode-error path that never raises out of the library.
4. **Argv floor.** Commit messages go through `git commit -F -` (stdin), never argv; the id regex
   is bounded (`m-\d{3,6}`); a memory line is capped at 2,000 bytes with the cap named in the
   refusal (store.v1 R2 leaves per-line length open; say in the docstring that the cap is a
   safety bound, not a style rule). A 131 KB text is refused before writing; `git status` clean;
   printed.
5. **Repair names what it discards.** `repair_store` prints each discarded line (truncated to
   120 chars) and the restoring commit before committing; test prints it.
6. **Quote floor.** `save(...)` refuses a `quote` shorter than 15 characters or fewer than 3 words
   with the existing one-line `QuoteNotHuman` wording plus `(too short to identify a human turn)`;
   `quote='e'` and `quote='ok'` refused; a real sentence still passes. Printed pair.
7. **Hostile corpus in conformance.** `conformance/store/run.py::probe_core_3` runs the corpus
   (items 2–4, 6) and prints Kept; `probe_core_1`'s 8-thread probe still Kept. Output printed.
8. `uv run pytest -q` (root, baseline 107) and `uv run ruff check .` printed green.
9. Item resolved and read back; a printed reason you know to be false is not evidence.

## Scope-outs

No edits under `modules/` or `skills/`. Never touch the real store. No network. Do not change
the receipt wording (lane H owns the tool's words; the library's refusal sentences are yours).

## Known

- Honesty gate: *"store.v1 Core N — Can't check in this lane because …"* in `run.py` and the reason.
- Lane F's `flock` + `_assert_saved` landed at `store.py` ~line 347; extend, don't replace.
- Show command output inline; never assert a result without it.
