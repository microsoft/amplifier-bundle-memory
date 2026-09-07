# Lane lane-13b-two-skills — `/remember` and `/memory <word>`: two skills, first-word dispatch, help

Worker session, alone, in your own worktree of `amplifier-bundle-memory` on branch
`lane/amplifier_bundle_memory-42s`. Work ONLY here; never merge to `main`; commit early, push after
every commit. **Never touch `~/.amplifier/memory`.** You write markdown and YAML; you run no model.

Read first: `PINS.md`, `AGENTS.md` (non-negotiable 9: retcon docs as always-true — no "previously /
now"), **`contracts/session.v3.md` (FROZEN 2026-09-07 — §6 is your whole specification; §11 caps the
two skill lines; the Conformance bullet "Nothing the model is given asserts what the human can or cannot
see of a tool call")**, the four current `skills/*/SKILL.md` (you are replacing them), `bundle.md`,
`behaviors/memory-session.yaml`, `modules/tool-memory/README.md`, `modules/hooks-memory-inject/README.md`.

**Work item:** `amplifier_bundle_memory-42s` — claim it
(`work_claim(project="amplifier_bundle_memory", item_id="amplifier_bundle_memory-42s")`), read its
description and acceptance in full, resolve with a reason written for the steward, read it back with
`work_list(project="amplifier_bundle_memory", item_id="amplifier_bundle_memory-42s")`, print it.

**File ownership — edit ONLY:** `skills/**` (delete `skills/edit/` and `skills/forget/` with `git rm`),
`bundle.md`, `behaviors/memory-session.yaml`, `modules/tool-memory/README.md`,
`modules/hooks-memory-inject/README.md`, the repo `README.md`. **Off-limits:** every `__init__.py`, every
test, `src/`, `conformance/`, `ledger/`, `contracts/`, `docs/workflow/`. Lane 13-A is adding
`operation=overview` to the tool in the same wave — write the skill against that operation name and
the exact §6 rendering; do not wait for it.

## Outcome

Two user-invocable skills, `disable-model-invocation: true` on both:

- **`/remember <text>`** — unchanged behaviour: `memory(operation="save", text=<text>, quote=<text>,
  writer="human")`.
- **`/memory`** — dispatch on the first word of `$ARGUMENTS`:
  - bare → `memory(operation="overview")`
  - `list` → `memory(operation="list")`
  - `review [accept|decline|skip <s-NNN>]` → `memory(operation="review", …)` exactly as today
  - `forget <id>` → `memory(operation="forget", id=…)`
  - `edit <id> <text>` → `memory(operation="edit", id=…, text=…, quote=<text>, writer="human")`
  - `remember <text>` → the same call as `/remember`
  - `help` → print, from the skill body itself (no tool call), the command table and ONE paragraph on
    how memory works: what is loaded into every request, when the assistant saves on its own, where
    the store lives (`~/.amplifier/memory`, a git repo you can `cat` and edit), and that a ruleset
    longer than one line goes to a topic file with a pointer line in `MEMORY.md`.
  - anything else → the `help` table.
  Ids are the only names: a bare number `N` means `m-00N`, never a position; never guess an id.

Every skill step that follows a tool call reads **"Relay the tool's result exactly as it stands."** —
never "Say nothing", never any sentence about what the human reads, sees, or is shown. The rule is
relay-verbatim-never-reword and nothing else.

The two frontmatter lines, rendered as `- **name**: description`, total ≤ 70 tokens (cl100k). Write the
descriptions for a user reading a slash-command list: `/memory` — "Your memory store: overview,
list, review, forget, edit, help." is the register.

`bundle.md`: the command table becomes two rows; the `/memory` row names the first words. Every
doc you own that carried `/edit <id> <text>` or `/forget <id>` now reads `/memory edit …` / `/memory
forget …`, and every receipt table drops the "the human reads" / "counted, not read" phrasing in
favour of "relayed verbatim". Written as always-true (AGENTS.md 9).

## Honesty gate — say this if it is true

"The conformance kit in `conformance/session/tool/run.py` still asserts `/edit registered in
behaviors/memory-session.yaml and bundle.md`; on this branch that assertion fails because I removed
`/edit` as §6 requires — the assertion belongs to lane 13-A's files and is a residual here." Put it in
`DONE.json`'s `residuals`. Touching `conformance/` to make it green is the falsifier.

## Terminal states and the exit

Items end `PASS` / `FAIL-<cause>` / `BLOCKED-<cause>`. 90 min wall → `BUDGET`: commit what is sound,
write the marker. **Final act: `DONE.json`** (valid JSON) in the worktree root — **never `git add` it**:
`{"lane":"lane-13b-two-skills","session_id":"…","verdict":"COMPLETE|BLOCKED|PARTIAL",
"branch":"lane/amplifier_bundle_memory-42s","head":"…","pushed":true,"items":[…],"residuals":[…],
"suite":"…"}`. On BLOCKED also write `BLOCKED.md`. Two exits and no third: **A) SUCCESS** — every item
met with evidence printed, committed and pushed, queue item resolved and read back; **B) BLOCKED** — a
named cause that stops every deliverable. A criterion outside your file ownership is a residual, exit A.

## Acceptance — every item names a file or a command whose output you print, and its falsifier

1. `ls skills/` prints exactly `memory` and `remember`; `git status` shows `skills/edit/` and
   `skills/forget/` deleted. Printed. **False if** either directory survives in the committed tree.
2. `skills/memory/SKILL.md` documents every first word (bare, list, review with accept/decline/skip,
   forget, edit, remember, help) and the unknown-word → help rule; `grep -n "operation=\"overview\"\|operation=\"list\"\|operation=\"review\"\|operation=\"forget\"\|operation=\"edit\"\|operation=\"save\"" skills/memory/SKILL.md` prints all six. **False if** any first word lacks the exact tool
   call it maps to.
3. `grep -rn "Say nothing\|the human reads\|counted, not read\|what the human reads" skills/ bundle.md behaviors/ modules/tool-memory/README.md modules/hooks-memory-inject/README.md README.md`
   prints nothing; `grep -rn "Relay the tool's result exactly as it stands" skills/` prints at least
   one hit per skill. **False if** the output is not from the committed state.
4. A three-line Python snippet (print it and its output) renders both frontmatter lines as
   `- **name**: description` and prints their combined tiktoken cl100k count; the number is ≤ 70.
   **False if** the snippet reads anything but the two committed SKILL.md files.
5. `bundle.md`'s command table has exactly two rows and `behaviors/memory-session.yaml` registers
   exactly two skills — `grep -n "/remember\|/memory\|/edit\|/forget" bundle.md behaviors/memory-session.yaml` printed, with no `/edit` or `/forget` hit outside a `/memory edit` / `/memory forget` phrase.
6. `uv run --offline pytest -q` at the repo root and `ruff check .` — printed. If a root test fails
   only because it asserts the old four commands from inside `conformance/` or `modules/**/tests`, name
   the test as a residual (13-A's files) rather than touching it.
7. Queue item `42s` resolved, then read back with `work_list` and printed. **False if** the printed
   reason asserts something you know to be untrue or omits a residual you recorded.
