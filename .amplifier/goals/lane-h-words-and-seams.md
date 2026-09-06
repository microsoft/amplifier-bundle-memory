# Lane lane-h-words-and-seams — the words the human reads, and the topic-file path

Worker session, alone, in your own worktree of `amplifier-bundle-memory` on branch
`lane/amplifier_bundle_memory-8b9`. Work ONLY here; never merge to `main`; commit early, push after
every commit. **Never touch `~/.amplifier/memory`**; tests use temp stores.

Read first: `PINS.md`, `AGENTS.md`, `contracts/session.v1.md` (FROZEN) §3–§8 — **the literals in
§3 and §6 are law; you keep them and ADD lines under them, you never change them** —
`contracts/store.v1.md` §5, §9, `docs/workflow/UX-PROPOSAL-2026-09-06.md` (the exact text table —
use it where it does not conflict with a locked literal), `docs/workflow/reviews/simulated-user-dana-2026-09-06.md`
(what a real screen showed), `modules/tool-memory/amplifier_module_tool_memory/__init__.py`,
`skills/*/SKILL.md`, `src/amplifier_memory/store.py` (`save(..., topic=, topic_purpose=)` — read
its signature; you call it, you do not edit it).

**Work item:** `amplifier_bundle_memory-8b9` — claim it, read its description (changes (a)–(e) with
their evidence), resolve with a reason for the steward, read it back with `work_list`, print it.

**File ownership — edit ONLY:** `modules/tool-memory/**`, `skills/**`, `conformance/session/tool/**`,
`ledger/rows.yaml` rows AMM-012…AMM-017 (notes only). Off-limits: `src/**` (lane G is there now),
`modules/hooks-memory-inject/**` (the announce is gated on a contract candidate), contracts, docs,
README, behaviors, bundle.md.

## Outcome

A human reads one receipt per event, once, and it tells the truth about provenance: the human's
words are marked as theirs, the assistant's wording is marked as the assistant's with the
approving quote. Forgetting echoes what was removed and where it still lives. Listing is the
file, with the hand-edit path under it. Ids are the only names and are never guessed. A ruleset
goes into a topic file with one pointer line instead of being squeezed into one line. The
assistant never says it cannot save what the human approved, and never restates a receipt.

## Terminal states and the exit

As the other lanes: PASS / FAIL-<cause> / BLOCKED-<cause> / PENDING-HUMAN; complete when every
item is terminal or the remainder is shown impossible; 90 min → BUDGET. **Final act:
`DONE.json` in the worktree root** with lane `lane-h-words-and-seams`, branch
`lane/amplifier_bundle_memory-8b9`, verdict COMPLETE|BLOCKED|PARTIAL, items, residuals, suite.

## Acceptance — every item names a file or a command whose output you print

1. `grep -rn "can't write these\|cannot write these\|You type them\|refuses any quote" skills/ modules/tool-memory/`
   prints nothing (show the empty output and exit code).
2. The tool description and `skills/remember/SKILL.md` carry, verbatim: `Ids are the only names.
   A bare number N means m-00N, never a position in a list. Never guess an id: if it cannot be
   resolved, list the current ids and ask.` and `Never restate a memory receipt or listing in
   your own words; the tool result is what the human reads.` Printed grep.
3. Batch flow in the description: when the human approves drafted lines, save ONE per call
   (lane F's rule stays), writer `assistant`, quote = the approval phrase; the LAST result of
   the batch is `Saved N memories — my wording, your go-ahead: "<quote>". Reword any line and
   I'll replace it; /forget <id> drops one.` followed by the lines. Test with 3 saves printed.
4. Save receipt: first line is EXACTLY session.v1 §3's literal
   `Saved memory m-017: "<text>" — /forget m-017 to undo.`; second line `your words, verbatim`
   when writer=human, `my wording, your go-ahead: "<quote>"` when writer=assistant. No
   `(committed …)` line anywhere. Printed for both writers.
5. Forget receipt: first line EXACTLY `Forgot m-002.`; second line the removed text; third
   `still in git: amplifier-memory why m-002`. Printed.
6. `list`: header `N memories` (correct singular/plural: `1 memory`), `-` bullets with ids
   first, no `topic files` clause when zero (`, 2 topics` when > 0), no `pending suggestions`
   clause in Phase 1, last line `edit by hand: $EDITOR ~/.amplifier/memory/MEMORY.md`
   (render the real `AMPLIFIER_MEMORY_HOME` path when set). Printed.
7. Topic path: `save` accepts `topic` (slug) and `topic_purpose`; the description says a
   ruleset or multi-line content goes to `topics/<slug>.md` plus ONE pointer line
   `- [m-NNN] <what> → topics/<slug>.md`; receipt names both files. Test against a temp store
   prints `MEMORY.md` and `topics/<slug>.md`.
8. Refusals, one line each, exact text from the proposal table: cap · duplicate
   (`already remembered as m-003 — nothing changed.`) · unknown id (`no memory m-004 — forgotten
   <date>. Current: m-003, m-005. Say the id.` — derive the date from `why`) · no human words ·
   any other failure (`not saved — nothing changed, nothing lost. Details: ~/.amplifier/memory-errors.log`).
   Printed for each.
9. `modules/tool-memory/README.md` records: `/remember` fires reliably in the interactive CLI
   (Dana, commit 3c0e676) and unreliably in one-shot `amplifier run` (lane E) — with the reason.
10. `conformance/session/tool/run.py` exit 0, §5/§6/R2 Kept, printed; module pytest + ruff
    green; root `uv run ruff check .` green (measured twice before: a module clean under its own
    config raised root findings — run both).
11. Item resolved and read back; a printed reason you know to be false is not evidence.

## Scope-outs

Do not change session.v1's literals. Do not touch the hook (announce), `src/`, contracts or
docs. Never touch the real store. No installs.

## Known

- The `<text>` placeholder in the announce is the hook's (not yours) and is fine on this build.
- Show command output inline; never assert a result without it.
