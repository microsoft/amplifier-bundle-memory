# Lane lane-s-quote-dedupe — dedupe suggestions by verbatim quote, honestly

Worker session, alone, in your own worktree of `amplifier-bundle-memory` on branch
`lane/amplifier_bundle_memory-acu`. Work ONLY here; never merge to `main`; commit early, push after
every commit. **Never touch `~/.amplifier/memory`; never run the real `amplifier-memory suggest`,
`review`, or a real model call from this lane** — temp stores only. The manager runs the real
thing after merge.

Read first: `PINS.md`, `AGENTS.md`, **`contracts/suggestions.v1.md` (FROZEN — §4 code verifies before
it proposes; §6 review; §7 never re-propose a decline, exact-match in code)**, `contracts/store.v2.md`
§3 §4 §7 (what MEMORY.md and declined.md lines carry — read the exact line shapes before deciding
anything), `src/amplifier_memory/inbox.py` (`append`, `_norm`, `accept`, `decline`, `memory_texts`,
`declined_texts`), `tests/test_inbox.py`, and the dedupe findings in
`evaluations/model-class/RESULTS-2026-09-06-pilot.md` (pilots 1–3).

**Work item:** `amplifier_bundle_memory-acu` — claim it
(`work_claim(project="amplifier_bundle_memory", item_id="amplifier_bundle_memory-acu")`), read its
description and acceptance in full, resolve with a reason written for the steward, read it back
with `work_list`, print it.

**File ownership — edit ONLY:** `src/amplifier_memory/inbox.py`, `tests/test_inbox.py`,
`conformance/suggestions/run.py` (a probe for the new dedupe, if you add one), `README.md` (one
sentence in the suggestions section). Off-limits: `suggest.py`, `doctor.py`, `cli.py`, `store.py`,
`tests/test_suggest.py` (lane R owns them this wave), `ledger/`, `contracts/`, `docs/workflow/`,
`modules/**`, `evaluations/**`.

## Outcome

A suggestion the model re-proposes with a paraphrased `text` but the same verbatim `quote` as
something already pending, accepted, or declined is dropped in code — wherever the store actually
keeps that quote. Where the store keeps only the text (read the locked contract; do not change a
line shape a locked clause fixes), the limit is written down in the README and pinned by a test
rather than papered over.

## Terminal states and the exit

Items end `PASS` / `FAIL-<cause>` / `BLOCKED-<cause>` / `PENDING-HUMAN`. 90 min wall → `BUDGET`:
commit what is sound, write the marker. **Final act: `DONE.json`** (valid JSON) in the worktree
root: `{"lane":"lane-s-quote-dedupe","session_id":"…","verdict":"COMPLETE|BLOCKED|PARTIAL",
"branch":"lane/amplifier_bundle_memory-acu","head":"…","pushed":true,"items":[…],"residuals":[…],
"pending_human":[],"resources":[],"suite":"…"}`. On BLOCKED also write `BLOCKED.md` with the cause.

## Acceptance — every item names a file or a command whose output you print

1. First, the reading: print the exact line shapes of MEMORY.md, declined.md and inbox.md entries
   (from the contract and from `inbox.py`), and state which of the three carry a quote. This
   decides everything below; do not guess.
2. `inbox.append`: the known-set includes `_norm(quote)` for every source that stores a quote
   (pending inbox items at minimum). Test: pending item with quote Q; candidate with different text
   and quote Q → dropped, counted already-known, store byte-identical, no new commit. Printed.
3. Same-batch duplicates by quote collapse to one (test). Printed.
4. Declined/accepted: if declined.md or MEMORY.md carry the quote, dedupe on it (test). If they do
   not and the locked contract fixes their line shape, add
   `test_declined_dedupe_is_text_only_today` pinning the limit and one README sentence naming it;
   do NOT change the line shape. Printed either way.
5. Every existing dedupe-by-text test still passes; `uv run pytest -q` green; `uv run ruff check .`
   and `ruff format --check .` clean; `uv run python conformance/suggestions/run.py` and
   `conformance/store/run.py` verdicts unchanged (or the new probe Kept). Printed.
6. Item resolved and read back; the printed reason is what the steward will read.

## Known

- Whitespace-normalize quotes the same way `verify`/`_flatten` do in `suggest.py` — but do not
  import from `suggest.py` if that creates a cycle; a tiny local `_norm_quote` is fine and say so.
- Show command output inline; never assert a result without it.
