# Proposal: amend session.v3 in place (CANDIDATE) — review and list pages, in markdown

target: contracts/session.v3.md

**Changes:** `contracts/session.v3.md` (FROZEN 2026-09-07). Written 2026-09-07 by the manager
session from the steward's two transcripts of the same afternoon. Two renderings change shape;
no promise is added, removed or weakened, so this amends v3 in place. The original stays the law
until the steward's word lands below.

## The decision this settles: code renders, the model drives

The steward asked for a review format that is "cleaner, easier to read/consume", paged "when more
than a dozen or something (but page to smaller than that so we don't [get] 1–2 item pages)", with
"better leverage of markdown", and named "the beauty of the model making the calls and doing the
rendering". Two of those pull apart: a model that renders is a model that can wrap, group and
summarise — and one that costs 2,476 output tokens and 25.6 seconds to echo seventeen items
(session c798a817), and drifts a little every time. This proposal splits the sentence: **the
library renders each page as markdown, once and identically every time; the model makes the
calls** — which page, which ids, accept or decline — and relays what came back. The human still
talks to the model in words ("accept the first two, skip the rest, next page"); the model turns
that into calls. Rendering stays where v2 put it for a reason that has not changed.

## Target lines and exact changes

### Change 1 — §6, the `list` word

Current text:

```
   - **`list`** — `MEMORY.md` with ids, `-` bullets, `N memories` (singular
     `1 memory`), topics named only when more than zero, and the line `edit
     by hand: $EDITOR ~/.amplifier/memory/MEMORY.md`.
```

Replacement:

```
   - **`list [<page>]`** — `MEMORY.md` as markdown, rendered by the library:
     a bold header `**N memories**` (singular `1 memory`; `, T topics` only
     when more than zero; `— page P of Q` only when paged), one line per
     memory as `- **m-NNN** <text>`, topic pointers as they stand, and the
     closing line `edit by hand: $EDITOR ~/.amplifier/memory/MEMORY.md`.
     Paged by the §6 paging rule at 20 lines a page.
```

### Change 2 — §6, the `review` word

Current text:

```
   - **`review [accept|decline|skip <id>]`** — suggestions §6. With an
     empty inbox it says so in one line.
```

Replacement:

```
   - **`review [<page> | accept|decline|skip <id>…]`** — suggestions §6, one
     page at a time, rendered by the library as markdown so it wraps and
     reads: a bold header `**N suggestions waiting** — page P of Q`; each
     item as a numbered bold id and its text, then the verbatim quote as a
     blockquote with its session and date on the quote's own last line, and a
     blank line before the next item; a closing line offering the exact
     commands — `accept s-002 s-003`, `decline s-005`, `skip s-004`, `next` —
     and the shell form. Several ids in one breath are several tool calls,
     in the order given, each producing its own §6 receipt; the receipts are
     relayed together. **Positions are never names:** the page numbers its
     items for the eye, but `accept 2` is refused with the ids that page
     holds, because a position changes when the inbox does. With an empty
     inbox it says so in one line.
```

### Change 3 — §6, the paging rule (new sentence after the `help` word)

Insert after the `help` item:

```
   **Paging.** Up to 8 items is one page. Above that the library divides
   into `ceil(n / 6)` pages of `ceil(n / pages)` items each, so no page
   holds fewer than one less than the others — 17 items are 6 · 6 · 5, 13
   are 5 · 4 · 4, 9 are 5 · 4, never 6 · 6 · 6 · 1. `<page>` selects one;
   `next` in conversation is the model asking for `<page> + 1`.
```

### Change 4 — §6, the relay sentence

Current text:

```
   Every rendering is relayed verbatim and never reworded. The writer
```

Replacement:

```
   Every rendering is relayed verbatim and never reworded: the overview and
   every receipt inside a fenced code block, because their `<id>` and
   `<text>` placeholders and their line breaks do not survive markdown
   outside one; `list` and `review` pages bare, because they are markdown
   and are meant to render as such. The writer
```

### Change 5 — Conformance

Replace:

```
- Bare `/memory` is at most four lines, suggestions first, and every figure
  equals `amplifier-memory status` run in the same second; `/memory list`
  equals the file. Each costs one model round trip.
```

with:

```
- Bare `/memory` is at most four lines, suggestions first, and every figure
  equals `amplifier-memory status` run in the same second. `/memory list`
  carries every line of the file, one `- **m-NNN**` bullet each, across its
  pages. A `review` page with 17 waiting is page 1 of 3 with 6 items, each
  item's quote byte-identical to `inbox.md`'s; `accept 2` is refused naming
  the page's ids; `accept s-002 s-003` produces two receipts. The paging
  rule's four worked examples (8 → 1 page; 9 → 5 · 4; 13 → 5 · 4 · 4;
  17 → 6 · 6 · 5) are asserted. Each `/memory` word costs the skill load,
  one tool call per page or per id, and one relay — never a model-rendered
  listing.
```

## Evidence (costs paid, in the steward's transcripts of 2026-09-07)

- **Session c798a817, `/memory review` with 17 waiting:** one wall of text; the model's echo cost
  **2,476 output tokens and 25.6 seconds**; the fenced relay wrapped mid-word at the terminal's
  column with no reflow. Steward: *"let's make the review format a bit cleaner, easier to
  read/consume … separate the memories and make it more line-wrapping friendly, better leverage of
  markdown."*
- **Paging was asked for with its failure mode named:** *"page the results when more than a dozen
  or something (but page to smaller than that so we don't [get] 1–2 item pages)."* The rule in
  Change 3 is that sentence made arithmetic, with the worked examples an evaluator can check.
- **Session e3b15303, `/memory`:** the fence did its job — four lines, `<id>` intact. The fence
  is right for the overview and wrong for a markdown page; Change 4 says which is which so the
  skill stops guessing.
- **Model-rendered vs code-rendered:** the v1 → v2 evidence stands (`session.v1.v2-candidate.md`
  §3: the model's own literal could not render 2 of 5 memories; "the single highest-trust-cost
  behaviour observed"). A review page is the one place a human decides what becomes memory; the
  quote under each item is the whole of the trust story, and it must be the inbox's bytes.

## What does NOT change

§1–§5, §7–§11, R1–R3. The overview's four lines and the fence around them. Every receipt in §3,
§5 and §6 and its fixture. `remember`, `forget`, `edit`, `help`. suggestions.v1 §6's three verbs
and their receipts — a multi-id `accept` is N single-id calls, nothing new in the tool. The
ids-only rule is strengthened, not touched. cli.v2 §4 `amplifier-memory review` — the shell form
may adopt the same page renderer, but this proposal does not require it.

## Steward's word

_(ratified · ratified with edits · declined · later)_
