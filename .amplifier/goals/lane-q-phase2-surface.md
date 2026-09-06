# Lane lane-q-phase2-surface — the pending line and `/memory review`

Worker session, alone, in your own worktree of `amplifier-bundle-memory` on branch
`lane/amplifier_bundle_memory-862`. Work ONLY here; never merge to `main`; commit early, push after
every commit. **Never touch `~/.amplifier/memory`**; temp stores only.

Read first: `PINS.md`, `AGENTS.md`, **`contracts/suggestions.v1.md` (FROZEN) §5, §6 and
`contracts/session.v2.md` §2, §3, §6** (the exact line and receipt shapes),
`modules/hooks-memory-inject/amplifier_module_hooks_memory_inject/__init__.py` (`_render`, the
first-request/compaction state, how the load line is built), `modules/tool-memory/…/__init__.py`
(the `execute` dispatch and receipt helpers), `skills/memory/SKILL.md`, `conformance/session/inject/run.py`,
`conformance/session/tool/run.py`.

**Work item:** `amplifier_bundle_memory-862` — claim it
(`work_claim(project="amplifier_bundle_memory", item_id="amplifier_bundle_memory-862")`), read its
description (the exact strings; the `amplifier_memory.inbox` signatures lane P is building in
parallel), resolve with a reason for the steward, read it back with `work_list`, print it.

**File ownership — edit ONLY:** `modules/hooks-memory-inject/**`, `modules/tool-memory/**`,
`skills/memory/SKILL.md`, `bundle.md` (skills table lines only), `conformance/session/**`,
`ledger/rows.yaml` rows AMM-031, AMM-032 (disposition/notes). Off-limits: `src/**`, `cli`, root
`tests/`, `conformance/suggestions`, `conformance/cli` — lane P is there now.

## Outcome

When suggestions are waiting, the session's first turn shows one extra rendered line under the load
line — `3 suggestions waiting. /memory review to see them.` — and never a suggestion's text in
context; `/memory review` lists them with their quotes and lets the human accept, decline or skip
each by id, with receipts in the v2 shape that the model never restates.

## Exit

PASS / FAIL-<cause> / BLOCKED-<cause>; complete when every item is terminal or shown impossible;
90 min → BUDGET. **Final act: `DONE.json`** (valid JSON) in the worktree root with lane
`lane-q-phase2-surface`, branch `lane/amplifier_bundle_memory-862`, verdict, items, residuals, suite.

## Acceptance — print the evidence

1. **Hook.** On the first request (and first after compaction) with a monkeypatched
   `amplifier_memory.inbox.pending` returning 3 / 1 / 0 items: the spy display receives the load
   line then exactly `3 suggestions waiting. /memory review to see them.` / `1 suggestion waiting.
   /memory review to see it.` / nothing; request 2 renders nothing; the injected block is
   byte-identical to the no-inbox block and contains no suggestion text; `inbox` absent at import →
   no line, no error; `pending` raising → one error-log line, no line, session continues. Printed.
2. **Tool `review`.** Listing shape from the item for 3 items; `no suggestions waiting.` for none;
   `accept s-001` → three-line save receipt with third line `suggested from session <8-hex>,
   accepted by you`; `decline s-001` → `declined s-001 — won't be proposed again. Reverse by hand:
   edit declined.md`; `skip s-001` → `skipped s-001 — still waiting.`; unknown → `no suggestion
   s-042. Waiting: s-043, s-044.`; library absent → `review is not available in this build; run
   amplifier-memory update`. Byte-compared to fixtures; tests needing the real module carry
   `skipif(not hasattr(amplifier_memory, "inbox"))` with the reason. Printed.
3. **Skills.** `skills/memory/SKILL.md` documents `/memory review [accept|decline|skip <id>]` and the
   never-restate rule; `bundle.md` row updated. Printed grep.
4. **Kits.** `conformance/session/inject/run.py` `check_suggestions_5`; `conformance/session/tool/run.py`
   `check_suggestions_6` — exit 0, Kept or honest Can't check. Module pytests + ruff green; root
   `uv run ruff check .` green. Printed.
5. Rows AMM-031/032 updated (CONFORMS where proven, GAP-with-reason where blocked on P). Item
   resolved and read back.

## Known

- Honesty gate: *"suggestions.v1 §N — Can't check in this lane because …"*.
- The kernel drops `HookResult.user_message` when any hook injects (measured, lane I) — render
  through `_render()` (display system), exactly as the load line does.
- Show command output inline; never assert a result without it.
