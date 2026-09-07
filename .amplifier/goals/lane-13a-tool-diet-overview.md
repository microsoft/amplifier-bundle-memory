# Lane lane-13a-tool-diet-overview — the tool's description diet, the `overview` operation, v3 receipts, the token meter

Worker session, alone, in your own worktree of `amplifier-bundle-memory` on branch
`lane/amplifier_bundle_memory-nyh`. Work ONLY here; never merge to `main`; commit early, push after
every commit. **Never touch `~/.amplifier/memory` or `~/.amplifier/memory-config.toml`; never run a
real model call.** Tests use `AMPLIFIER_MEMORY_HOME` pointed at a temp dir, as every test here does.

Read first: `PINS.md`, `AGENTS.md` (non-negotiables 1, 9, 11 especially), **`contracts/session.v3.md`
(FROZEN 2026-09-07 — §3 receipt text, §5 refusal text, §6 the bare `/memory` overview, §11 the 500-token
ceiling, and the Conformance bullets; every string below is quoted from it)**, `contracts/cli.v2.md` §2
(`status` — the overview reads the SAME figures), `modules/tool-memory/amplifier_module_tool_memory/__init__.py`
(`DESCRIPTION`, `INPUT_SCHEMA`, the operation dispatch), `src/amplifier_memory/status.py` (or wherever
`status` computes its numbers), `conformance/session/tool/run.py` and `receipts.py`.

**Work item:** `amplifier_bundle_memory-nyh` — claim it
(`work_claim(project="amplifier_bundle_memory", item_id="amplifier_bundle_memory-nyh")`), read its
description and acceptance in full, resolve with a reason written for the steward, read it back with
`work_list(project="amplifier_bundle_memory", item_id="amplifier_bundle_memory-nyh")`, print it.

**File ownership — edit ONLY:** `modules/tool-memory/**`, `src/amplifier_memory/**`,
`conformance/session/tool/**`, and NEW `conformance/session/budget/run.py` — in that file you own
`probe_core_11` (the token meter) and a minimal `main()`; lane 13-C adds `probe_no_presumption` to the
same file, so keep each probe a self-contained function and `main()` a two-line dispatcher, so the
merge is trivial. **Off-limits:** `skills/**`, `bundle.md`, `behaviors/**`, `modules/hooks-memory-inject/**`,
every `README.md`, `ledger/`, `contracts/`, `docs/workflow/`. Where `conformance/session/tool/run.py`
today asserts things about `skills/` or `bundle.md` (around lines 630 and 989: `/edit registered`,
`skills/memory/SKILL.md documents /memory review`), rewrite those assertions for the two-skill world
described in §6 — you assert, lane 13-B makes them true; if they fail on your branch because 13-B has
not landed, that is a **residual**, not a blocker (name it in `DONE.json`).

## Outcome

The model pays for what it needs every turn and nothing more. `DESCRIPTION` teaches: when to save,
when not to, one call at a time, the verbatim quote, relay-never-reword, relay refusals — and stops.
The slash-command mapping, the review paragraph, the topic-file paragraph and most of the batch
paragraph leave (the skills teach them). `review` stays in the `operation` enum as one word with one
clause of parameter text. `INPUT_SCHEMA` descriptions no longer repeat the DESCRIPTION. A new
`operation=overview` renders §6's bare `/memory` — at most four lines, from the same figures
`amplifier-memory status` prints, through ONE library function (AGENTS.md 11: one home for logic;
`status` and `overview` are two renderings of one dataclass, never two computations). Receipts name
`/memory forget`. `conformance/session/budget/run.py::probe_core_11` measures the four injected sources
with tiktoken cl100k, prints each, and fails above 500.

The exact strings (session.v3):

- §3: `saved m-017 — /memory forget m-017 to undo.` · batch tail `Reword any line and I'll replace it;
  /memory forget <id> drops one.`
- §5: `not saved — MEMORY.md is full (200 of 200 lines). /memory forget one you no longer need, or ask
  me to move a group into a topic file.`
- §6 overview, in order, each line present only under its condition:
  1. `34 suggestions waiting. /memory review to walk them.` — singular `1 suggestion waiting. /memory
     review to walk it.`; **absent when the inbox is empty**.
  2. `4 memories, 0 topics. /memory list to see them.` — singular `1 memory`; `, N topics` only when
     more than zero (so `4 memories. /memory list to see them.` at zero topics).
  3. `last 7 days: 6 written, 1 forgotten, 2 cited.` — a zero-valued term is dropped; the line is
     absent when all three are zero.
  4. `/memory list · review · forget <id> · edit <id> <text> · help` — `review` present only while
     suggestions are waiting.
  No receipt carries a commit sha, a phase name, a zero-valued count, or a `<placeholder>`.

## Honesty gate — say this if it is true

"The token meter reads the skill lines from `skills/*/SKILL.md` frontmatter; on this branch there are
still four skills, so the measured total is above 500 until lane 13-B lands — the probe is correct and
currently red, here is its printed breakdown." Put that sentence, if true, in `DONE.json`'s
`residuals` and in the resolution. A green probe on a four-skill tree is the falsifier: it means the
meter is not measuring the skills.

## Terminal states and the exit

Items end `PASS` / `FAIL-<cause>` / `BLOCKED-<cause>`. 120 min wall → `BUDGET`: commit what is sound,
write the marker. **Final act: `DONE.json`** (valid JSON) in the worktree root — **never `git add` it**:
`{"lane":"lane-13a-tool-diet-overview","session_id":"…","verdict":"COMPLETE|BLOCKED|PARTIAL",
"branch":"lane/amplifier_bundle_memory-nyh","head":"…","pushed":true,"items":[…],"residuals":[…],
"suite":"…"}`. On BLOCKED also write `BLOCKED.md` with the cause. Two exits and no third: **A) SUCCESS**
— every item below met with its evidence printed, work committed and pushed, queue item resolved and
read back; **B) BLOCKED** — a named cause that stops every deliverable; whatever is sound is committed.
A criterion you cannot meet from inside your file ownership is a residual, and the exit is still A.

## Acceptance — every item names a file or a command whose output you print, and its falsifier

1. `python conformance/session/budget/run.py` prints one line per source — `DESCRIPTION`, `INPUT_SCHEMA
   text`, each `skills/*/SKILL.md` name+description line, the hook's framing sentence (import the
   constant from `amplifier_module_hooks_memory_inject`; do not edit that module) — with its cl100k
   count and the total, and exits non-zero above 500. Printed. **False if** the breakdown omits a
   source, or reads the DESCRIPTION from anywhere but the installed module object.
2. `DESCRIPTION` + `INPUT_SCHEMA` text together measure ≤ 330 tokens (print the two numbers), contain
   the six teachings above, contain no slash command, no `/memory review` paragraph, no topic-file
   paragraph, and none of: `the human reads`, `Say nothing`, `counted, not read`. Evidence: the
   probe's two lines and `grep -n "the human reads\|Say nothing\|counted, not read\|/memory\|/edit\|/forget\|/remember" modules/tool-memory src` printing nothing. **False if** the grep output is
   not from the committed state.
3. `operation=overview` exists; `src/amplifier_memory/` gains one function that renders it from the
   same dataclass `status` renders (name the function and the shared type in the resolution). A test
   builds a temp store with 4 memories, 0 topics, an inbox of 34, and usage events for 6 written / 1
   forgotten / 2 cited in 7 days, and asserts the four exact lines above; a second test with an empty
   inbox asserts three lines with no `review` in line 4; a third with one inbox item asserts the
   singular line 1. `cd modules/tool-memory && uv run --offline pytest -q` printed. **False if** the
   overview computes any figure by a path `status` does not use.
4. Save, batch and cap-refusal receipts carry `/memory forget` exactly as quoted; the fixtures in
   `conformance/session/tool/` are updated and `python conformance/session/tool/run.py` prints
   `Core 3 — Kept`, `Core 5 — Kept`, `Core 6 — Kept` (or names the exact residual that depends on
   13-B). Printed. **False if** the kit was weakened to pass.
5. `uv run --offline pytest -q` at the repo root and `ruff check .` — printed, green.
6. Queue item `nyh` resolved, then read back with `work_list` and printed. **False if** the printed
   reason asserts something you know to be untrue or omits a residual you recorded in `DONE.json`.
