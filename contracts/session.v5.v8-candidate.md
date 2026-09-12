target: contracts/session.v5.md

# session.v5.v8 candidate — conversational corrected acceptance (DRAFT)

> **Sanitized publication copy.** Original SHA-256:
> `c741a1e163adf15d21e1dbe71c405accc70e73bccc5201b8840055440cec5a10`.
> Only nonnormative evidence and ratification prose has been redacted. Every
> `Replacement:` fenced block was verified byte-identical against the retained
> private original. This is neither a new ratification nor a contract version or
> lock.

## Deciding summary

This is a ratified narrow amendment against this branch's current locked
`contracts/session.v5.md`. It adds one atomic corrected-accept exception to
conversational review for a pending HUMAN-origin stable suggestion id, while
keeping ordinary accept, decline, and skip unchanged. It is not adoption of
unpublished agent autonomy: the reserved v4/v7 work is out of scope. This is a
decision record, not a locked successor, implementation claim, or live proof.

In revise-only cases, declining the proposed rewrite leaves the source pending;
an explicit `review decline s-NNN` still declines the source item normally.

## Exact change, sentence by sentence

### Change 1 — Core 6, `review` conversational addressing and corrected acceptance

Current text:

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
  relayed together. **Conversational review addressing:** after rendering a
  review page, the assistant may resolve a clear reference to that rendered
  page — `#1`, `first one`, or unambiguous quoted text — to its stable `s-NNN`
  id. Before its first mutation, it resolves the complete stated batch and
  freezes an action-to-id map; for example, on a rendered page containing
  `1. s-101` and `2. s-202`, `accept #1, decline #2` maps to `accept s-101`,
  then `decline s-202`. It executes those stable ids sequentially in the
  human's stated order and relays the receipts together. No extra
  confirmation is needed when both action and target are clear. If the
  assistant explicitly stated the complete action-to-id map immediately
  before, `yes` approves that map without retyping ids. An unknown, lost, or
  conflicting map receives one concise clarification question and no guessed
  target or mutation. A missing or stale stable id remains a missing-id
  refusal: the assistant does not reread and rebind that position, and never
  retargets remaining actions. Tool and shell commands still require stable
  `s-NNN` ids; `accept 2` there is refused with the ids on that page. With an
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
  relayed together. **Conversational review addressing:** after rendering a
  review page, the assistant may resolve a clear reference to that rendered
  page — `#1`, `first one`, or unambiguous quoted text — to its stable `s-NNN`
  id. Before its first mutation, it resolves the complete stated batch and
  freezes an action-to-id map; for example, on a rendered page containing
  `1. s-101` and `2. s-202`, `accept #1, decline #2` maps to `accept s-101`,
  then `decline s-202`. It executes those stable ids sequentially in the
  human's stated order and relays the receipts together. No extra
  confirmation is needed when both action and target are clear. If the
  assistant explicitly stated the complete action-to-id map immediately
  before, `yes` approves that map without retyping ids. For one existing,
  pending HUMAN-origin stable `s-NNN` in that frozen map, a clear natural
  authorization to accept corrected text — for example, `accept it but ...` —
  is a **corrected accept** exception, not a new command and not ordinary
  accept. The assistant may derive final text from the human's correction, but
  code receives and verifies a verbatim genuine human correction quote: required
  `quote` is that actual verbatim human correction, required `session` is the
  correction session, and writer is `assistant`, never `human`; derived
  corrected text is never portrayed as human-verbatim. The same atomic commit
  writes only that corrected memory and removes the source `s-NNN`, retaining
  the source-suggestion-id, original source quote, and original source session
  as additional metadata in that same commit. It never creates an
  accepted-original-text intermediate or a separate provenance store.
  **Revise-only flow:** a clear revision request resolved against a rendered
  stable `s-NNN` subject to these no-retarget rules displays assistant-derived
  proposed corrected text, the actual human correction quote, and the exact
  proposal-to-id map, with no memory, inbox, or id mutation and no success
  receipt. A later `yes` or `do it` approves that immediately displayed exact
  proposal-to-id map without retyping; a missing, ambiguous, or stale map, or
  no approval, leaves the candidate pending. Before commit succeeds, any
  validation, write, or commit failure restores unchanged memory, HEAD, pending
  source, and next id, and emits no success receipt. If commit succeeds but
  readback fails, it emits no success receipt and reports `commit succeeded but
  readback is unverified`; it never claims unchanged, blindly retries, rolls
  back, or creates another id, and explicit inspection is the recovery. A
  reported commit error whose outcome is unknown likewise requires inspection,
  not an assumption that nothing was written. Readback verifies the combined
  committed corrected-memory and source-removal state and never mutates the
  inbox afterward. In a batch, completed earlier receipts remain relayed and a
  later refusal is relayed too. An unknown, lost, or conflicting
  map receives one concise clarification question and no guessed target or
  mutation. A missing or stale stable id remains a missing-id refusal: the
  assistant does not reread and rebind that position, and never retargets
  remaining actions. Tool and shell commands still require stable `s-NNN` ids;
  `accept 2` there is refused with the ids on that page. With an empty inbox it
  says so in one line.
```

### Change 2 — Core 6, stable-id boundary

Current text:

```
The writer applies §5's human-turn check to `remember` and `edit` like any
other save. **Outside conversational review, ids are the only names:** tool
and shell commands, and non-review `/memory edit` and `/memory forget`, use
stable ids; a bare number `N` means `m-00N`, never a position in a list. A
destructive command that cannot resolve its id asks (`no memory m-004 —
forgotten 2026-09-06. Current: m-003, m-005. Say the id.`) and never guesses.
Conversational review addressing is the narrow exception in this clause's
`review` paragraph, and resolves only from the actual rendered page, not from
the live positional inbox.
```

Replacement:

```
The writer applies §5's human-turn check to `remember` and `edit` like any
other save. **Outside conversational review, ids are the only names:** tool
and shell commands, and non-review `/memory edit` and `/memory forget`, use
stable ids; a bare number `N` means `m-00N`, never a position in a list. A
destructive command that cannot resolve its id asks (`no memory m-004 —
forgotten 2026-09-06. Current: m-003, m-005. Say the id.`) and never guesses.
Conversational review addressing, including its corrected-accept exception, is
the narrow exception in this clause's `review` paragraph. It resolves only
from the actual rendered page and its frozen action-to-id map, not from the
live positional inbox; tool and shell calls retain the stable-id-only rule.
```

### Change 3 — Conformance, receipts

Current text:

```
- Every receipt in §3, §5 and §6 is byte-identical to a fixture and contains
  no commit sha, no phase name, no zero-valued count, no `<placeholder>`.
```

Replacement:

```
- Every receipt in §3, §5 and §6 is byte-identical to a fixture and contains
  no commit sha, no phase name, no zero-valued count, no `<placeholder>`. A
  corrected-accept success receipt is emitted only after committed readback.
  Before commit succeeds, validation, write, and commit failures emit no
  corrected-accept success receipt; after a successful commit with failed
  readback, no success receipt is emitted and the report is `commit succeeded
  but readback is unverified`.
```

### Change 4 — Conformance, conversational corrected acceptance

Current text:

```
- A full-conversation evaluation loads the actual memory skill, renders a real
  review page from a fresh synthetic store, then checks numbered batches, an
  immediately preceding action-to-id-map `yes`, ambiguous references, stale
  ids, page-local nonconsecutive ids, and unambiguous text references. It
  rejects reordered, duplicate, missing, wrong, or extra mutations; direct
  tool and shell position calls remain refused.
```

Replacement:

```
- A full-conversation evaluation loads the actual memory skill, renders a real
  review page from a fresh synthetic store, then checks numbered batches, an
  immediately preceding action-to-id-map `yes`, ambiguous references, stale
  ids, page-local nonconsecutive ids, and unambiguous text references. For a
  pending HUMAN-origin stable id, it tests direct `accept it but ...` and the
  revise-only flow: a clear revision request displays assistant-derived proposed
  corrected text, the actual verbatim human correction quote, and the exact
  proposal-to-id map without mutation or a success receipt; a later `yes` or
  `do it` accepts that immediately displayed map without retyping. Each accepted
  correction verifies required `quote` is the actual human correction, required
  `session` is the correction session, writer is `assistant`, and the same
  atomic commit preserves source-suggestion-id, original source quote, and
  original source session as additional metadata while writing only corrected
  memory and removing its source. A fresh-session/readback verifies that combined
  committed state. It tests missing, ambiguous, or stale maps, no approval,
  decline, and refusal after revise-only: each leaves the candidate pending with
  no memory, inbox, or id mutation and no success receipt. It tests absent or
  non-verbatim correction quotes and injected validation, write, and pre-success
  commit failures: each restores unchanged memory, HEAD, pending source, and
  next id, with no success receipt. A separate postcommit-readback failure case
  verifies no success receipt, the exact report `commit succeeded but readback
  is unverified`, no claim that state is unchanged, no blind retry, rollback, or
  additional id, and explicit inspection as recovery. A reported commit error
  of unknown outcome likewise requires inspection rather than assuming nothing
  was written. It never activates the unwanted original memory; a batch relays
  completed earlier receipts with a later refusal. It rejects reordered,
  duplicate, missing, wrong, or extra mutations; direct tool and shell position
  calls remain refused.
```

### Change 5 — Conformance, rendered review page

Current text:

```
A `review` page with 17 waiting is page 1 of 3 with 6 items, each
  item's quote byte-identical to `inbox.md`'s; `accept 2` is refused naming
  the page's ids; `accept s-002 s-003` produces two receipts.
```

Replacement:

```
A `review` page with 17 waiting is page 1 of 3 with 6 items, each
  item's quote byte-identical to `inbox.md`'s; `accept 2` is refused naming
  the page's ids; `accept s-002 s-003` produces two receipts. Conversational
  corrected acceptance remains page-local and frozen-map-bound: it cannot
  re-list, rebind, or retarget a missing or stale id.
```

## Evidence — a failure caught and cost paid

A controlled investigation caught a natural revision request handled as
accept-then-edit: acceptance persisted the unwanted source wording before the
edit refused, and the final response did not disclose that partial write. A
separate natural edit also refused when derived wording was supplied in place of
the human correction quote. These are distinct failures. This amendment covers
the corrected-accept limitation; the ordinary natural-edit repair is separate.

Public regression coverage is in `tests/test_corrected_accept.py`,
`tests/test_correction_harness.py`, and
`modules/tool-memory/tests/test_tool_memory.py`. It exercises atomic
corrected acceptance, preserved human-quote provenance, revise-only behavior,
and failure recovery without reproducing private conversation material.

## What does NOT change

- Ordinary accept remains exactly the existing path; plain accept, decline, and
  skip semantics do not change.
- Already-ratified conversational addressing remains: resolution is from the
  rendered page only, the complete action-to-id map freezes before mutation,
  stale ids refuse without re-list, rebind, or retarget, and tool/shell stable
  ids remain required.
- Existing quote verification, caps, lock, stable ids, and no-retarget behavior
  remain in force. The original source quote/session remain distinct evidence;
  corrected output is never relabeled as a human-verbatim quote.
- This adds no broad pipeline, configuration, service, product edit, or new CLI
  verb, and does not adopt reserved v4/v7 agent-autonomy work.

## Observable conformance

Success is observable when a rendered-page, frozen-map pending HUMAN-origin
`s-NNN` receives direct corrected acceptance or a revise-only request followed
by approval of its immediately displayed exact proposal-to-id map; only its
corrected memory and the source removal occur in one atomic commit; and a fresh
session/readback shows required quote as the actual human correction, required
session as the correction session, writer `assistant`, plus source-suggestion-id,
original source quote, and original source session as additional metadata. A
revise-only request without approval, a decline, or a refusal leaves the
candidate pending with no memory, inbox, or id mutation and no success receipt;
it never activates the unwanted original memory. Before commit succeeds,
quote-verification and injected validation/write/commit failures restore
unchanged memory, HEAD, pending source, and next id with no success receipt.
After commit succeeds, a readback failure reports `commit succeeded but readback
is unverified` with no success receipt and is recovered only through explicit
inspection, never an unchanged claim, blind retry, rollback, or another id. A
multi-item request retains and relays earlier successful receipts and also
relays any later refusal.

## Steward's word

The retained private original records the bounded ratification without
reproducing the interaction or its timing here. Ratification applies to the
exact replacements above and the paired `suggestions.v3.v5-candidate.md`.
The separate prior-memory conversational requirement is independent; no
unwritten clause is approved by this record. The locked target stays
byte-identical. This bounded implementation authority is not a locked successor
or evidence of live conformance. No publication, activation, or real-store
change is authorized.
