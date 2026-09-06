# Lane lane-k2-tool-skills-v2 — the tool and the skills keep session.v2

Worker session, alone, in your own worktree of `amplifier-bundle-memory` on branch
`lane/amplifier_bundle_memory-5yi`. Work ONLY here; never merge to `main`; commit early, push after
every commit. **Never touch `~/.amplifier/memory`**; tests use temp stores.

Read first: `PINS.md`, `AGENTS.md`, `contracts/session.v2.md` (FROZEN — §3, §5, §6, §8 and
Conformance are your spec; the receipt strings live there and are law), `contracts/store.v2.md` §6,
`docs/workflow/UX-PROPOSAL-2026-09-06.md` (the moment-by-moment table),
`src/amplifier_memory/store.py` — `edit(memory_id, new_text, quote, writer, session_id,
human_turns=None, *, home=None) -> SaveResult` (~:1326) and `record_citation(memory_id, session_id,
home=None) -> dict` (~:1613), both landed on main by lane K1; `modules/tool-memory/amplifier_module_tool_memory/__init__.py`
(the `execute` dispatch, `_refusal`, the description text), `skills/*/SKILL.md`,
`conformance/session/tool/run.py` and `receipts.py`, `behaviors/memory-session.yaml`, `bundle.md`.

**Work item:** `amplifier_bundle_memory-5yi` — claim it (`work_claim(project="amplifier_bundle_memory",
item_id="amplifier_bundle_memory-5yi")`), read its description (parts (1)–(4) with evidence), resolve
with a reason for the steward, read it back with `work_list`, print it.

**File ownership — edit ONLY:** `modules/tool-memory/**`, `skills/**`, `behaviors/memory-session.yaml`,
`bundle.md` (the skills table/registration lines only), `conformance/session/tool/**`, `ledger/rows.yaml`
rows AMM-012, AMM-015, AMM-017 (disposition/notes only). Off-limits: `src/**`, `cli`, root `tests/`,
`conformance/store`, `conformance/cli`, `modules/hooks-memory-inject/**`, `conformance/session/inject`
(lane L is there now), contracts, docs, README.

## Outcome

Every receipt a human reads about memory is the exact v2 text, rendered once by the tool result,
never restated by the model: `saved m-017 — /forget m-017 to undo.` with the text unquoted and a
provenance line; `edited m-004 — was: "<old>"` / `  now: <new>`; `forgot m-002 — still in git:
amplifier-memory why m-002` with the removed text; `/memory` as `N memories`, `-` bullets, the
hand-edit line. `/edit <id> <text>` exists and keeps the id. The tool records a citation when the
assistant names a memory at use, and the skills tell the model when to cite. Refusals are the §5/§6
one-liners exactly.

## Terminal states and the exit

Items end `PASS` / `FAIL-<cause>` / `BLOCKED-<cause>` / `PENDING-HUMAN`. Complete when every item is
terminal or the remainder is conclusively shown impossible with the blocker named. 100 min wall →
`BUDGET`: commit what is sound, write the marker. **Final act: `DONE.json`** in the worktree root
(gitignored): `{"lane":"lane-k2-tool-skills-v2","session_id":"…","verdict":"COMPLETE|BLOCKED|PARTIAL",
"branch":"lane/amplifier_bundle_memory-5yi","head":"…","pushed":true,"items":[…],"residuals":[…],
"pending_human":[],"resources":[],"suite":"…"}`.

## Acceptance — every item names a file or a command whose output you print

1. **Save receipt (§3).** writer=human → exactly three lines: `saved m-001 — /forget m-001 to undo.`,
   `  <text unquoted>`, `  your words, verbatim`; writer=assistant → third line
   `  my wording, your go-ahead: "<quote>"`. Byte-compared to fixtures; printed. No `Saved memory`
   literal, no `(committed …)`, no sha anywhere in a tool result (grep printed).
2. **Batch (§3).** Three assistant-drafted saves with one approval quote → the LAST result ends
   with `saved 3 memories — my wording, your go-ahead: "<quote>". Reword any line and I'll replace
   it; /forget <id> drops one.` followed by the three lines; the first two results carry only their
   own three-line receipt (no running summary). Printed.
3. **Edit (§6).** operation `edit` (id, text, quote, writer) → library `edit()`; receipt
   `edited m-004 — was: "<old>"` / `  now: <new>`; id unchanged in `MEMORY.md`; unknown id →
   `no memory m-004 — forgotten <date>. Current: m-003, m-005. Say the id.` (date from `why`).
   Printed.
4. **Forget (§6).** `forgot m-002 — still in git: amplifier-memory why m-002` / `  <removed text>`.
   Printed.
5. **List (§6).** `N memories` (singular `1 memory`), `, T topics` only when > 0, no `pending
   suggestions` clause, `-` bullets ids first, last line `edit by hand: $EDITOR <real MEMORY.md
   path>`. Printed for 1 and 3 memories, with and without a topic.
6. **Cite (§8).** operation `cite` (memory_id) → `record_citation`; returns an empty/quiet result the
   human never reads (or one line if the id is unknown); `usage.jsonl` gains a `cited` event
   (printed). The tool description and `skills/*/SKILL.md` tell the model: "When a memory changes
   what you would otherwise have done, write `per m-NNN` inline and call `cite` with that id." Grep
   printed.
7. **Refusals (§5).** Exactly: cap · `already remembered as m-003 — nothing changed.` · `can't save
   that one — you haven't said it in your own words yet. Type it and I'll record it verbatim.` ·
   `not saved — nothing changed, nothing lost. Details: ~/.amplifier/memory-errors.log` · a
   malformed store keeps naming `amplifier-memory doctor --repair` (item zp4). Printed.
8. **Skills.** `skills/edit/SKILL.md` (new; `/edit <id> <text>`, writer human, quote = text);
   `/remember`, `/forget`, `/memory` updated to the v2 receipts; every skill carries "Never restate a
   memory receipt or listing; the tool result is what the human reads." and the ids-only / bare-N /
   never-guess rule; registered in `behaviors/memory-session.yaml` and `bundle.md`'s table. Printed.
9. **Conformance.** `conformance/session/tool/run.py` re-aimed at v2 with probes for items 1–7
   (fixtures byte-compared); `receipts.py` demo prints the v2 shapes; exit 0, Core 3/5/6/8 Kept where
   assertable (the model-behaviour halves stay Can't check, said in the honesty form). Module pytest
   + ruff green; root `uv run ruff check .` green. Printed.
10. Rows AMM-012/015/017 flipped to CONFORMS naming the probes; `git diff --stat -- ledger/rows.yaml`.
11. Item resolved and read back; a printed reason you know to be false is not evidence.

## Scope-outs

No edits under `src/`, `cli.py`, root tests, the hook, contracts, docs. Never touch the real store.
No installs.

## Known

- Honesty gate: *"session.v2 §N — Can't check in this lane because …"* in `run.py` and the reason.
- `edit()` with writer=human requires quote == text (the library refuses otherwise); with
  writer=assistant the quote is the human's approval phrase.
- `forget(memory_id, home, *, …)` — read its signature before calling; the manager tripped on it.
- Show command output inline; never assert a result without it.
