# session.v4.v5-candidate — natural review addressing (DRAFT)

target: contracts/session.v4.md

## Exact change, sentence by sentence

### Change 1 — Core 6, `/memory review` addressing

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
  relayed together. **Positions are never names:** the page numbers its
  items for the eye, but `accept 2` is refused with the ids that page
  holds, because a position changes when the inbox does. With an empty
  inbox it says so in one line.
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
  before, `yes` approves that map without retyping ids. An unknown, lost, or
  conflicting map receives one concise clarification question and no guessed
  target or mutation. A missing or stale stable id remains a missing-id
  refusal: the assistant does not reread and rebind that position, and never
  retargets remaining actions. Tool and shell commands still require stable
  `s-NNN` ids; `accept 2` there is refused with the ids on that page. With an
  empty inbox it says so in one line.
```

### Change 2 — Core 6, the ids-only rule

Current text:

```
The writer applies §5's human-turn check to `remember` and `edit` like any
other save. **Ids are the only names:** a bare number `N` means `m-00N`, never
a position in a list; a destructive command that cannot resolve its id
asks (`no memory m-004 — forgotten 2026-09-06. Current: m-003, m-005.
Say the id.`) and never guesses.
```

Replacement:

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

### Migration and feasible conformance after ratification

The memory skill's contradictory ids-only review guidance changes only with the
ratified successor; current tool-id conformance tests remain. Add full-
conversation tests for a numbered batch, `yes` after a complete stated map, an
ambiguous reference, a stale id, and nonconsecutive ids across pages, including
a guard against an ID-digit shortcut. No bulk-all policy, new Python parser, or
backend state is introduced. Create `session.v5.md` only after ratification;
`session.v4.md` remains byte-for-byte untouched.

## Evidence — observed cost

Source incident: 2026-09-09, `action:list` from PR8; CLI
`2026.09.08-dfa56a7`, core `1.6.1`, current primary HEAD `e5514a9`. The later
remote slash-completion commit `c7d82b1` is unrelated; this proposal does not
change frontmatter completions. The person reported, verbatim, “I should not
have to be this exact/explicit:”; after a two-item numbered listing, “accept
#1, decline #2” caused an exact accept/decline stable-ID map followed by an
unnecessary request for IDs, and “yes” caused the same demand again. Cost paid:
two additional human turns before the actions.

The previously presented replacement was: “People may refer to the displayed
suggestions naturally; the assistant resolves clear references to stable IDs,
and asks only when the intended target is unclear”. The subsequent “do it” is
recorded as implementation intent and approval of direction, not literal
ratification of this candidate.

## What does NOT change

- Accept and decline effects; writer, quotes, and human-root-only checks.
- Stable-ID permanence; inbox cap, storage, paging, receipt rendering, and
  read-only PR8 recovery.
- The tool's `accept 2` refusal and all tool/shell stable-`s-NNN` APIs.
- No rebind after a missing or stale id; no change to remaining batch targets.
- No lock, publication, implementation, or modification of `session.v4.md`.

## Steward's word

Steward response: `ratified` — 2026-09-09, after this candidate was presented.
The successor may be created and implemented. Its freeze still requires the
conformance kit and worked end-to-end example; the old v4 remains untouched.
