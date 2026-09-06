# Lane lane-k1-library-v2 — the library and the CLI keep store.v2 and cli.v2

Worker session, alone, in your own worktree of `amplifier-bundle-memory` on branch
`lane/amplifier_bundle_memory-zx4`. Work ONLY here; never merge to `main`; commit early, push after
every commit. **Never touch `~/.amplifier/memory`**; tests use temp stores (conftest guards it).

Read first: `PINS.md`, `AGENTS.md` (rules 10, 11), `contracts/store.v2.md` and `contracts/cli.v2.md`
(FROZEN — §1, §6, §8, §10 / §2, §3, §5 and Conformance are your spec),
`docs/workflow/GATE-DEFINITION-2026-09-06.md` (the kept definition), `src/amplifier_memory/store.py`
(`save` ~:1089, `forget` ~:1223, `log_usage` ~:1312, `why` ~:928, `verify_store` ~:706,
`repair_store` ~:757), `doctor.py`, `cli.py`, `conformance/store/run.py`, `conformance/cli/run.py`,
`tests/test_status.py`, `tests/test_doctor.py`.

**Work item:** `amplifier_bundle_memory-zx4` — claim it, read its description (the five parts and
their evidence), resolve with a reason for the steward, read it back with `work_list`, print it.

**File ownership — edit ONLY:** `src/amplifier_memory/**`, root `tests/**`, `conformance/store/**`,
`conformance/cli/**`, `ledger/rows.yaml` rows AMM-001, 005, 007, 009, 021, 022, 024
(disposition/notes only), `README.md` (the CLI section only). Off-limits: `modules/**`, `skills/**`,
`conformance/session/**` — lane I runs beside you in the hook; lane K2 follows you in the tool.

## Outcome

Reading memory leaves no commit behind; every change a human made or approved is still exactly
one commit, and the history now says what each one was — `forgot [m-002] …` for a removal, an
edit that keeps its id and carries `was:`. `edit()` and `record_citation()` exist as public
library functions the tool will call next wave. `status` prints the citation rate and a kept
count that treats a refinement as continuity. `doctor` has its own `MEMORY.md well-formed` row.
The CLI still adds nothing but parsing and formatting.

## Terminal states and the exit

As the other lanes; 100 min → BUDGET. **Final act: `DONE.json`** in the worktree root with lane
`lane-k1-library-v2`, branch `lane/amplifier_bundle_memory-zx4`, verdict, items, residuals, suite.

## Acceptance — every item names a file or a command whose output you print

1. **Usage without commit (store.v2 §1, §8, §10).** `log_usage(...)` appends to `usage.jsonl` and
   does NOT commit; `usage.jsonl` is ignored inside the store (`init` writes it to the store's
   `.gitignore`; on an existing store that tracks it, the first `log_usage` runs `git rm --cached
   usage.jsonl` in one visible commit `store: stop tracking usage.jsonl (store.v2 §1)` and never
   again). Test: init, three loads → `git rev-list --count HEAD` unchanged, three events in the
   file. Printed. The 90-day truncation stays.
2. **`edit()` (store.v2 §6, cli.v2 §3).** `edit(memory_id, new_text, quote, writer, session_id,
   human_turns, home=...)` under the lock: same id, new text, one commit whose subject is
   `[m-004] <new text>` and whose body carries `action: edit`, `was: "<old text>"`, quote, session,
   writer; the same one-line/byte-cap/duplicate/quote-floor refusals as `save`; `_assert_saved`-style
   read-back. Unknown id → `UnknownId` one-liner. Printed: `MEMORY.md` before/after, `git log -1
   --format=%B`.
3. **`forgot` subject (store.v2 §6).** `forget()` commits with subject `forgot [m-002] <text>`;
   `git log --oneline -1` printed.
4. **`why` (cli.v2 §3).** `amplifier-memory why m-004` prints the creation, each edit as
   `was: "<old>"` → `now: <new>` with date/session/writer, and a forget marked `forgot` in its
   first line; unknown id one-line error. Printed for a fixture with save → edit → forget.
5. **Citations (store.v2 §8, cli.v2 §2).** `record_citation(memory_id, session_id, home=...)`
   appends `{ts, event: cited, target: m-NNN, session_id}`; `status` prints the exact line
   `  citation rate    2 cited / 1 loaded (30d)` after two citations and one load (printed;
   choose the column alignment `status` already uses and show it).
6. **Kept (cli.v2 §2, R1).** `status` computes kept with the GATE-DEFINITION rule: an edited
   memory's age is its first write; a forget + re-save of the same text counts once from the
   first write. Fixture with backdated commits (`GIT_COMMITTER_DATE`) printed before/after an
   edit; kept unchanged by the edit.
7. **Doctor row (cli.v2 §5).** `doctor` prints its own `MEMORY.md well-formed` row (OK on a
   clean store; FAIL naming line/offset + last clean commit on a headless fragment and on a
   `\xe9` byte, exit 1), separate from the `store` row; `doctor --repair` unchanged. Printed.
   `cli.v2 §5` lists the rows — the CLI conformance kit's row list is updated to match v2.
8. **Conformance.** `conformance/store/run.py` and `conformance/cli/run.py` re-aimed at v2 in
   their docstrings and probe names, with new/extended probes for items 1–7; both exit 0 with
   the touched clauses Kept (printed). `cli.py` imports only `click` and `amplifier_memory`
   (printed grep). Root `uv run pytest -q` (baseline 133) and `uv run ruff check .` green.
9. Rows AMM-001/005/007/009/021/022/024 flipped to CONFORMS naming the probes;
   `git diff --stat -- ledger/rows.yaml` printed.
10. Item resolved and read back; a printed reason you know to be false is not evidence.

## Scope-outs

No edits under `modules/` or `skills/`. Do not change `save`'s receipt text (the tool renders
receipts; lane K2). Never touch the real store. No installs; do not run `amplifier-memory update`.

## Known

- Honesty gate: *"store.v2 §N — Can't check in this lane because …"* in `run.py` and the reason.
- Lane F's lock and verify-after-commit and lane G's atomic write/encoding floor are the
  foundation; extend them, never bypass them.
- The steward's real store still tracks `usage.jsonl` with ~10 `usage: loaded` commits — your
  migration path (item 1) is what the manager will run there via `amplifier-memory update`;
  make the one-time commit message say so.
- Show command output inline; never assert a result without it.
