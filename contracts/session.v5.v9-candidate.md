target: contracts/session.v5.md

# session.v5.v9 candidate — conversational prior-memory management (DRAFT)

> **Sanitized publication copy.** Original SHA-256:
> `b35f89c73f7b417e7236b7d2a8c8a0f04b4b89ff3f6748ce455091e96ed11205`.
> Only nonnormative evidence and ratification prose has been redacted. Every
> `Replacement:` fenced block was verified byte-identical against the retained
> private original. This is neither a new ratification nor a contract version or
> lock.

## Exact change, sentence by sentence

### Change 1 — Core 6, `list` and displayed prior-memory addressing

Current text:

```
- **`list [<page>]`** — `MEMORY.md` as markdown, rendered by the library:
  a bold header `**N memories**` (singular `1 memory`; `, T topics` only
  when more than zero; `— page P of Q` only when paged), one line per
  memory as `- **m-NNN** <text>`, topic pointers as they stand, and the
  closing line `edit by hand: $EDITOR <instance>/MEMORY.md` (the instance's
  real path, store.v3 §1).
  Paged by the §6 paging rule at 20 lines a page.
```

Replacement:

```
- **`list [<page>]`** — `MEMORY.md` as markdown, rendered by the library:
  a bold header `**N memories**` (singular `1 memory`; `, T topics` only
  when more than zero; `— page P of Q` only when paged), one line per
  memory as `- **m-NNN** <text>`, topic pointers as they stand, and the
  closing line `edit by hand: $EDITOR <instance>/MEMORY.md` (the instance's
  real path, store.v3 §1).
  Paged by the §6 paging rule at 20 lines a page. **Conversational
  prior-memory addressing:** after rendering a `list` page, the assistant
  may resolve one clear natural request to reword, remove, or consolidate a
  displayed prior-memory entry from that shown snapshot. A memory is resolved
  to its displayed stable `m-NNN` id. A topic pointer is read-only, never an
  edit or forget target; the assistant reads and displays the topic's contents
  before resolving a reference to an actual `m-NNN` line within it.
  The reference may give that stable id, an
  unambiguous displayed text or content description, or an explicit position
  in the shown snapshot such as `#2` or `the first memory`.
  This is not a latest-entry rule: any shown memory or topic-memory
  entry may be selected, including an older entry, a nonconsecutive id, or an
  entry on a later rendered page. Before a mutation, the assistant resolves
  the stated target and action to a frozen action-to-target map. A bare number
  is never treated as a current live list position inside a tool call; tool,
  shell, and literal slash-command syntax keep their stable-id-only rule.
  With an unambiguous displayed target and clear reword or remove action, the
  assistant performs the mapped existing single-entry operation without an
  extra confirmation. An ambiguous description, a lost snapshot/map, or a
  conflicting target gets one concise clarification question and no guessed
  mutation. A missing or stale target remains a refusal: the assistant does
  not reread, rebind, or retarget the position or any remaining action after
  that failure.
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
other save. **Outside conversational review and conversational prior-memory
addressing, ids are the only names:** tool and shell commands, and literal
non-review `/memory edit` and `/memory forget` syntax, use stable ids; a bare
number `N` means `m-00N`, never a position in a list. A destructive command
that cannot resolve its id asks (`no memory m-004 — forgotten 2026-09-06.
Current: m-003, m-005. Say the id.`) and never guesses. Conversational review
addressing, including its ratified corrected-accept exception, remains the
narrow exception in this clause's `review` paragraph: it resolves only from
the actual rendered page and its frozen action-to-id map, not from the live
positional inbox; tool and shell calls retain the stable-id-only rule.
Conversational prior-memory addressing is the separate narrow exception in
this clause's `list` paragraph: it resolves only from the actual shown list
snapshot and its frozen action-to-target map. It supplies no positional tool,
shell, or literal slash-command form, does not turn a bare number into a live
position, and never rereads, rebinds, or retargets after a missing or stale
failure.
```

### Change 3 — Core 6, consolidation transaction and provenance

Current text:

```
- **`forget <id>`** — removes the line and commits; the receipt is
  `forgot m-002 — still in git: amplifier-memory why m-002` then the
  removed text on its own line.
- **`edit <id> <text>`** — replaces one memory's text keeping its id; the
  commit carries the old text (`was:`) and the new; the receipt is
  `edited m-004 — was: "<old>"` then `  now: <new>`.
```

Replacement:

```
- **`forget <id>`** — removes the line and commits; the receipt is
  `forgot m-002 — still in git: amplifier-memory why m-002` then the
  removed text on its own line.
- **`edit <id> <text>`** — replaces one memory's text keeping its id; the
  commit carries the old text (`was:`) and the new; the receipt is
  `edited m-004 — was: "<old>"` then `  now: <new>`. A conversational
  reword uses this existing operation after list-snapshot resolution. Its
  required quote remains the actual verbatim human correction authorizing the
  change; when the assistant derives replacement wording, writer is
  `assistant` and that derived wording is never passed off as the human's
  quote.
- **Conversational consolidation** — is a preview over existing `edit` and
  `forget` operations, not a bulk-store feature or new command. Before any
  mutation, the assistant shows the exact survivor `m-NNN`, the
  assistant-derived survivor text, the actual human correction quote, and the
  named duplicate `m-NNN` removal ids. A clear approval of that immediately
  displayed exact map, such as `yes` or `do it`, is enough; ids need not be
  retyped. A declined or unapproved preview leaves every original unchanged.
  On approval, the assistant edits the survivor first, then forgets the named
  duplicates sequentially. It does not remove any source before the survivor
  edit succeeds. On an edit failure, it stops before removal; on a later
  removal failure, it stops immediately. In either case it relays every actual
  prior receipt and the later refusal unchanged, does not claim the batch was
  atomic, and does not reread, rebind, or retarget a failed or remaining
  target. The survivor edit preserves the human correction quote and the
  `assistant` writer for assistant-derived text; each forget remains its
  existing operation and receipt.
```

### Change 4 — Conformance, displayed prior-memory management

Current text:

```
- `/remember` and every `/memory` first word behave as §6; `edit` keeps the
  id and `why` shows `was:`/`now:`; `forget` of an unknown id is the §6
  one-line refusal naming the current ids; an unknown first word yields the
  `help` table.
```

Replacement:

```
- `/remember` and every `/memory` first word behave as §6; `edit` keeps the
  id and `why` shows `was:`/`now:`; `forget` of an unknown id is the §6
  one-line refusal naming the current ids; an unknown first word yields the
  `help` table. A full-conversation evaluation renders list snapshots with
  older and nonconsecutive `m-NNN` ids, a later page, and displayed `m-NNN`
  lines within a topic; a topic pointer alone is never a mutation target. It
  checks clear reword and removal by id, unambiguous displayed text/content
  description, and explicit shown-snapshot position; each maps once to the
  intended existing single-entry operation with no needless confirmation. It
  checks that a bare number in a tool, shell, or literal slash command remains
  an id form rather than a live position. It checks ambiguous descriptions and
  lost maps receive one clarification with no mutation, and that missing or
  stale targets refuse with no relist, rebind, retarget, or extra mutation.
  It checks consolidation previews name the exact survivor id, derived text,
  human correction quote, and duplicate removal ids; approval of that
  immediately displayed map edits the survivor before sequential forgets;
  decline leaves originals intact; an edit failure causes no source removal;
  and a removal failure preserves and relays earlier actual receipts plus the
  refusal without an atomicity claim. The provenance controls verify the
  actual human correction quote and `assistant` writer for derived survivor
  text.
```

## Evidence — failure caught, examples, and check plan

A controlled investigation found a natural revision request that could not
reach the existing ID-only edit path while preserving its human correction
quote. The observed provenance defect is distinct from target resolution, and
the earlier corrected-accept partial-write failure remains governed by v8.
This candidate therefore limits itself to displayed-list addressing and
preview-first consolidation.

Public regression coverage is in `tests/test_prior_memory_harness.py` and
`modules/tool-memory/tests/test_tool_memory.py`. It exercises displayed stable
id mapping, topic read/display ordering, ambiguity and stale-target refusal,
approval-gated consolidation, and sequential failure boundaries without
reproducing private conversations.

## What does NOT change

- `contracts/session.v5.md` remains locked and untouched; this proposal is a
  sibling amendment only. The ratified v8 decision record remains its own
  corrected-accept authority and is not superseded or broadened here.
- `/memory review` keeps its existing rendered-review, frozen-map, stable
  `s-NNN`, and corrected-accept behavior. This exception is for displayed
  `/memory list` snapshots, not the live inbox.
- Tool calls, shell commands, and literal `/memory edit <id> <text>` and
  `/memory forget <id>` syntax still use stable ids. No live positional API,
  reread/rebind recovery, new command, bulk operation, store feature, or
  batch-atomicity promise is added.
- Existing single-entry edit and forget semantics, receipts, quote checks,
  writer checks, caps, locks, and failure handling remain in force. Topic
  files retain their existing handling; this adds only snapshot-based
  conversational reference resolution, not a topic bulk writer.

## Steward's word

The retained private original records the bounded ratification without
reproducing the interaction, timing, or workflow references here. Ratification
applies to the four exact replacements above; none has changed in this
publication copy. The locked target and earlier corrected-acceptance addenda
remain byte-identical. This is bounded implementation authority, not a locked
successor or evidence of live conformance. No publication, activation, or
real-store change is authorized.
