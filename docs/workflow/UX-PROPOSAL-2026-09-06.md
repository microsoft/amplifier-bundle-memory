# The updated experience — proposal after the first real day

Synthesised by the manager session from four reviews run on 2026-09-06 against the steward's
own transcript (`.converge/feedback/2026-09-06-kicked-the-tires-transcript.md`):

- **Product council** (6 lenses; user-advocate FAIL held; three standing disagreements) —
  session `727da7ac…`, summary in `reviews/product-council-2026-09-06.md`.
- **Design council** (7 lenses; FAIL 7/7) — `reviews/design-council-2026-09-06.md`.
- **Engineering council** (6 lenses; FAIL 6/6; four blockers reproduced by execution) —
  `reviews/engineering-council-2026-09-06.md`.
- **Simulated user "Dana"** driving the real interactive CLI through a PTY —
  `reviews/simulated-user-dana-2026-09-06.md` (OBSERVED vs SIMULATED).

Where the councils disagreed, the disagreement is kept, named, and routed: to a lane (when
the contract already permits it), to a candidate (when a locked document must change), or to
the steward (when only a person can decide).

## What the reviews agree the product got right

Zero-effort save on a plain sentence, with the id and the undo in one line ("the strongest
thing here" — Dana; "the one original idea in this product" — design). The store as a plain
git repo anyone can `cat`, `git log`, and recover from. The human-turn check as an
anti-poisoning boundary. Load in the next session. Interactive `/remember` fires with
`writer: human` first time (device-checked, commit `3c0e676` in the Dana store).

## The experience, moment by moment (the exact text)

Every line below is **rendered by code, not spoken by the model**, through
`HookResult.user_message` — the mechanism the engineering council located
(`hook_dispatch.rs:282-313` → `CLI/ui/display.py:98-128`) and which this bundle already uses
for failures. The model never restates a receipt; the model's prose is only the model's prose.
Nothing in a receipt is a `<placeholder>`, a commit sha, a phase, or a subsystem count of zero.

| Moment | The human sees |
|---|---|
| Session start, empty store | `no memories yet. Tell me a standing preference — "never use tabs in YAML" — and I'll keep it in every session on this device.` |
| Session start, loaded | `3 memories loaded. /memory to see them.` (topics named only when > 0: `3 memories loaded, 2 topics. /memory to see them.`) |
| After a context compaction | `context compacted. 3 memories still loaded.` |
| Save, human's own words | `saved m-006 — /forget m-006 to undo.` / `  never use tabs in YAML; two-space indent` / `  your words, verbatim` |
| Save, assistant's wording | `saved m-004 — /forget m-004 to undo.` / `  When I say "explain" or "walk me through", go long with headers.` / `  my wording, your go-ahead: "Great remember these for me"` |
| Batch save (drafted, approved) | `saved 3 memories — my wording, your go-ahead. Reword any line and I'll replace it; /forget <id> drops one.` then the three lines |
| Edit (id kept) | `edited m-004 — was: "When I say explain, go long."` / `  now: When I say "explain" or "walk me through", go long with headers.` |
| Forget | `forgot m-002 — still in git: amplifier-memory why m-002` / `  Point time estimates at whoever actually runs the steps, not at the reader.` |
| `/memory` | `3 memories · edit by hand: $EDITOR ~/.amplifier/memory/MEMORY.md` then the lines, ids first, `-` bullets, never re-rendered by the model |
| Cite at use (model prose) | `going long here, per m-004.` — cited when the memory changed what the assistant would otherwise have done |
| Refusal: cap | `not saved — MEMORY.md is full (200 of 200 lines). /forget one you no longer need, or ask me to move a group into a topic file.` |
| Refusal: duplicate | `already remembered as m-003 — nothing changed.` |
| Refusal: unknown id | `no memory m-004 — forgotten 2026-09-06. Current: m-003, m-005. Say the id.` |
| Refusal: no human words | `can't save that one — you haven't said it in your own words yet. Type it and I'll record it verbatim.` |
| Any failure | `not saved — nothing changed, nothing lost. Details: ~/.amplifier/memory-errors.log` |
| Ambiguous "update 4" | ids only; a bare `N` means `m-00N`, never a position; the receipt echoes what was resolved; never guess |

What disappears: `(committed b5fb8cd to MEMORY.md)` · `(Phase 1 records none)` ·
`(0 topics available)` when zero · `1 memories` · "I can't write these for you" (false — the
writer accepted the save one turn later; 5 of 6 product lenses named it the worst line) ·
the model repairing the store with `bash` (there is now `doctor --repair`).

## Decisions the reviews settled (no steward call needed)

1. **No confirm gate on saves** — unanimous across product and design ("a confirm is a
   preamble"). Announce-and-undo stays; the receipt gets legible enough to catch a bad line.
2. **Ids only; holes stay; ordinals are input, never identity** — settled by a fact: "update 4"
   was typed when three memories were on screen; an ordinal would have deleted the ADHD line.
3. **Deterministic rendering beats model instruction** for announce and receipts — the
   mechanism exists; two model-behaviour guarantees each ran at roughly a third.
4. **The quote check stays** as an anti-poisoning boundary — and gets a floor (`quote='e'`
   passes today). It is not the product's differentiator; "the preference travels" is.
5. **Slash commands stay model-mediated** for `/remember` and `/forget` (engineering 6–0 after
   its author withdrew: the model call *is* the human-turn check). `/memory` is the one worth
   making free: a hook renders the listing and the model is told not to restate it. Pre-registered
   acceptance: one model round trip, no restatement, listing byte-identical to the file.
6. **Topic files need a write path from the session** — the highest-value miss: the steward
   asked to move a 1.4K-token ruleset into memory and was handed a suitcase; the library
   already has `save(..., topic=)`; the tool does not expose it.

## Three calls that are the steward's (see the candidates and the brief)

- **D1 — hints or instructions?** (VISION principle 3). Product: 3 for changing, 2 against,
  1 abstaining; the proposer attached a falsifier — *ship citation counting; if the week shows
  kept memories cited and obeyed under the hints framing, withdraw.* Recommendation: **keep
  principle 3, measure citations, decide on day 7.** No candidate filed for it.
- **D2 — `edit` now or after day 7?** Both councils want `edit` (6–1, 6–0); they split on
  timing. Recommendation: **now** — cli.v1 §3 already promises `why` shows "edits", so the verb's
  absence is itself drift between two locked documents, and Dana's step 5 showed the harm
  (referring to a number retired the number). Candidate filed (session.v1 §6, cli.v1 §3).
- **D3 — pre-register the gate definition now?** Recommendation: **yes, as a note, not a
  contract** (`GATE-DEFINITION-2026-09-06.md`): a refinement keeps its original write date;
  kept = present at day 7 counting edits as continuity. VISION principle 9 amended in the
  day-7 batch, not before the number is read.

## What changes where

**Lanes now (derivable from the locked contracts; running at width 2):**
- **G — writer hardening** (store.v1 §1, §3, §6; session.v1 §5): atomic temp+`os.replace`
  writes with the assert on the working tree the hook reads; the encoding/argv floor
  (`splitlines()` set, tolerant reads, `git commit -F -`, bounded id regex, byte cap);
  `repair_store` names what it discards; a quote floor. Four blockers the engineering council
  reproduced by execution.
- **H — the words and the seams** (session.v1 §2–§6 as written; store.v1 §5, §9): the skill
  text (delete the false line; batch-save flow; ids-only and bare-N rules; `$EDITOR` line);
  receipts stripped of sha/phase/zero-topics; forget echoes its text on a second line;
  `list` renders `-` bullets and the model is told never to restate; the tool exposes
  `topic=` so a ruleset becomes `topics/<slug>.md` + one pointer line; `1 memories` fixed.

**Candidates (locked text changes; the steward's word):**
- `contracts/session.v1.v2-candidate.md` — §2 rendered by the hook via `user_message`, once,
  and after compaction; §3/§6 receipt shapes above; §6 adds `edit`; §8 cite-at-use becomes
  measured (a `cited` usage event and a rate in `status`), not promised.
- `contracts/store.v1.v2-candidate.md` — §1 exception: usage events append without a commit
  (one `usage: loaded` commit per session is the one unbounded surface; measured 4 in one
  afternoon); §8 gains the `cited` event.
- `contracts/cli.v1.v2-candidate.md` — §3 names `edit` as a real operation; §5 records
  `doctor --repair` as the explicit, printed, opt-in mutation.
- No VISION candidate yet: principle 9's counting rule is pre-registered as a note and amended
  on day 7 with the number in hand; principle 3 waits on the citation data.

**Asked of the steward besides the word:** the baseline — roughly how many times a week you
currently repeat a standing preference to the assistant. It is the one number that cannot be
taken later, and without it "five kept" is uninterpretable.
