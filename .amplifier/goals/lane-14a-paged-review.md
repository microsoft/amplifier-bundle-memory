# Lane lane-14a-paged-review — review and list as paged markdown; status's last-run line

Worker session, alone, in your own worktree of `amplifier-bundle-memory` on branch
`lane/amplifier_bundle_memory-0jk`. Work ONLY here; never merge to `main`; commit early, push after
every commit. **Never touch `~/.amplifier/memory`.** Tests use `AMPLIFIER_MEMORY_HOME` → temp dir.

Read first: `PINS.md`, `AGENTS.md` (11: one home for logic — the paging arithmetic exists exactly
once), **`contracts/session.v3.md` §6 as amended 2026-09-07 — the `list` and `review` items, the
`Paging.` paragraph, and the relay sentence (fence for overview + receipts only) are your whole
specification**, `contracts/suggestions.v1.md` §4 (the inbox item's two-line shape; the quote is
the human's bytes) and §6, `src/amplifier_memory/inbox.py` (`InboxItem.render_review`,
`waiting()`, `review_one`, `review_action`), `src/amplifier_memory/status.py` (`StatusReport`,
`render_overview`, line 352 `last_suggest_run=None`), `src/amplifier_memory/store.py`
(`list_memories`), `src/amplifier_memory/doctor.py` (how it reads `suggest.log`'s last run),
`modules/tool-memory/amplifier_module_tool_memory/__init__.py` (the `list`/`review` operations,
`REVIEW_HOW`), `skills/memory/SKILL.md`, `conformance/session/tool/run.py` + `receipts.py`.

**Work items, claimed in this order:** `amplifier_bundle_memory-0jk` (the pages), then
`amplifier_bundle_memory-70i` (status's `last run: never`). Claim each with `work_claim(project=
"amplifier_bundle_memory", item_id=…)`, read its description and acceptance in full, resolve with a
reason written for the steward, read it back with `work_list(project="amplifier_bundle_memory",
item_id=…)`, print it.

**File ownership — edit ONLY:** `src/amplifier_memory/inbox.py`, `src/amplifier_memory/status.py`,
`src/amplifier_memory/store.py` (the list renderer only — lane 14-B may touch `init`/`InitResult` in
the same file; stay out of those), `src/amplifier_memory/__init__.py` (re-exports),
`modules/tool-memory/**`, `skills/memory/SKILL.md`, `conformance/session/tool/**`, `tests/test_inbox.py`,
`tests/test_status.py`, `tests/test_store.py` (list tests only). **Off-limits:** `src/amplifier_memory/cli.py`,
`service.py`, `README.md`, `conformance/cli/**`, `tests/test_cli.py`, `tests/test_service*.py`,
`skills/remember/`, `ledger/`, `contracts/`, `docs/workflow/`, `modules/hooks-memory-inject/`.

## Outcome

The steward's transcript c798a817: `/memory review` with 17 waiting came out as one wall, the model
spent 2,476 output tokens and 25.6 s echoing it, and the fence wrapped it mid-word. Afterwards:

`review` (page omitted = 1) with 17 waiting returns **markdown**, rendered by the library:

    **17 suggestions waiting** — page 1 of 3

    **1. s-002** — Prioritize improving the attractor bundle as a general-purpose builder …
    > "Our priority is on making a better attractor bundle that helps us build better attractors …"
    > — session d9c3bf04, 2026-09-07

    **2. s-003** — Credit Amplifier by default for anything built with an Amplifier-powered system.
    > "Uh, for author, keep our default (talk to git-ops agent for details) …"
    > — session d9c3bf04, 2026-09-07

    … (6 on this page)

    `accept s-002 s-003` · `decline s-005` · `skip s-004` · `next` — or `/memory review accept s-002`

The quote is the inbox's bytes, whole — never truncated (it is the whole of the trust story). The
`k.` numbers are for the eye; **`accept 2` is refused in one line naming the ids on that page**,
because a position changes when the inbox does (§6: ids are the only names). Several ids in one
breath are several single-id tool calls, in order, receipts relayed together — the tool's
accept/decline/skip stay single-id; the skill makes the calls. Empty inbox: one line, as today.

**Paging** lives in ONE function — `page_bounds(n, page, *, base=6, single=8)` (name yours; one
home) — used by both `review` (items) and `list` (lines, `base=20`): `n ≤ single` → one page;
else `pages = ceil(n / base)`, `size = ceil(n / pages)`. 17 → 6·6·5; 13 → 5·4·4; 9 → 5·4; 8 → 1
page. A page beyond the last is refused in one line naming the last page.

`list [<page>]` returns markdown too: `**4 memories**` (singular `1 memory`; `, T topics` only when
> 0; `— page P of Q` only when paged), one `- **m-NNN** <text>` per memory (topic pointers as they
stand), then `edit by hand: $EDITOR ~/.amplifier/memory/MEMORY.md`.

The **skill** relays list and review pages **bare** (markdown must render) and keeps the fence
**only** around the overview and every receipt (their `<id>`/`<text>` placeholders die outside
one). `next` → the same call with `page + 1`. Several ids → several calls.

**Item 70i** (after 0jk): `status.py:352` hard-codes `last_suggest_run=None`, so `status` prints
`last run: never` while `doctor` reads this morning's run from `suggest.log`. Read the last
`status=` line through the SAME helper `doctor` uses (move it to a shared place if it lives in
`doctor.py`; one home), so `status` prints `last run: 2026-09-07T07:00:01+00:00 · ok`. No log →
`never` as today. Test with lane R's line shape (`… calls=30 provider=luna status=ok`).

## Honesty gate — say this if it is true

"The budget kit measures the skill's *description line*, not its body; the body grew by the fence
and paging rules and that is not counted — here is the kit's printed total, still ≤ 500." If the
description line itself grew, print the new number and say so. A page fixture that passes because
the renderer was fed pre-rendered text is the falsifier: every fixture must be produced from a real
temp inbox/store through the public function.

## Terminal states and the exit

Items end `PASS` / `FAIL-<cause>` / `BLOCKED-<cause>`. 120 min wall → `BUDGET`: commit what is
sound, write the marker. **Final act: `DONE.json`** (valid JSON) in the worktree root — **never
`git add` it**: `{"lane":"lane-14a-paged-review","session_id":"…","verdict":"COMPLETE|BLOCKED|PARTIAL",
"branch":"lane/amplifier_bundle_memory-0jk","head":"…","pushed":true,"items":[…],"residuals":[…],
"suite":"…"}`. On BLOCKED also write `BLOCKED.md`. Two exits and no third: **A) SUCCESS** — every
item below met with evidence printed, committed and pushed, both queue items resolved and read
back; **B) BLOCKED** — a named cause that stops every deliverable. A criterion outside your file
ownership is a residual, exit A.

## Acceptance — every item names a file or a command whose output you print, and its falsifier

1. A unit test asserts `page_bounds` for n = 8, 9, 13, 17 (1 page; 5·4; 5·4·4; 6·6·5) and for the
   list base (45 lines → 15·15·15). Printed. **False if** the arithmetic exists in two places.
2. From a temp inbox of 17 real items, `review` page 1 renders exactly 6 items in the shape above
   with quotes byte-identical to `inbox.md`; page 3 renders 5; page 4 is a one-line refusal; the
   header carries `— page 1 of 3`; with 8 items no page suffix. `cd modules/tool-memory && uv run
   --offline pytest -q` printed. **False if** a fixture was hand-written rather than rendered.
3. `review` with a bare-number id (`2`) is refused in one line that names the ids on the current
   page and writes nothing (inbox hash unchanged). Printed test. **False if** the refusal guesses.
4. `list` from a temp store of 4 renders the header, four `- **m-NNN**` bullets and the edit-by-hand
   line; from 45, `— page 1 of 3` with 15 bullets. Printed.
5. `skills/memory/SKILL.md`: `grep -n "fenced\|next\|several" skills/memory/SKILL.md` shows the fence
   scoped to overview + receipts, pages bare, `next` = page+1, several ids = several calls. The
   description line is unchanged (print it). Printed. **False if** any sentence claims what the human
   can see.
6. `python conformance/session/tool/run.py` (from the tool module env) prints `Core 6 — Kept` against
   the new fixtures; `conformance/session/budget/run.py` prints `Core 11 — Kept` and the total.
   Printed. **False if** either kit was weakened.
7. `amplifier-memory status` on a temp store whose `suggest.log` ends `… provider=luna status=ok`
   stamped T prints `last run: <T> · ok`; with no log, `never`. `uv run --offline pytest -q
   tests/test_status.py` printed; the helper is imported by both `status.py` and `doctor.py` (grep
   printed). **False if** status re-parses the log with its own code.
8. Root `uv run --offline pytest -q` and `ruff check .` — printed, green.
9. Items `0jk` and `70i` resolved, read back with `work_list`, printed. **False if** a printed
   reason asserts something you know to be untrue or omits a residual you recorded.
