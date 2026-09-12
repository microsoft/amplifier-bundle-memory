target: contracts/suggestions.v3.md

# suggestions.v3.v5 candidate — corrected acceptance of a pending suggestion (DRAFT)

> **Sanitized publication copy.** Original SHA-256:
> `5d7a8997ab9f7b2f76765108671898ccdd1443f08e855b2c5aefbf99864a5d4d`.
> Only nonnormative evidence and ratification prose has been redacted. Every
> `Replacement:` fenced block was verified byte-identical against the retained
> private original. This is neither a new ratification nor a contract version or
> lock.

## Exact change, sentence by sentence

**Deciding summary.** This is a narrow amendment to the current locked `contracts/suggestions.v3.md` on this branch. It adds one atomic corrected-accept path for a pending, HUMAN-origin stable suggestion id while preserving ordinary accept, decline, and skip. It is not adoption of unpublished agent autonomy; the reserved v4/v7 work is out of scope.

### Change 1 — Core 6, review and corrected acceptance

In revise-only cases, declining the proposed rewrite leaves the source pending;
an explicit `review decline s-NNN` still declines the source item normally.

Current text:

```
6. **Review is one keystroke per item.** `/memory review` (or
   `amplifier-memory review`) walks the inbox: **accept** writes the line
   through the same writer as session.v4 §5 (writer `suggestion`, quote and
   session carried into the commit) and removes it from the inbox;
   **decline** appends the text to `declined.md` with the date and removes
   it; **skip** leaves it. Items unreviewed for 30 days are dropped and
   counted in the next run's report.
```

Replacement:

```
6. **Review is one keystroke per item.** `/memory review` (or
   `amplifier-memory review`) walks the inbox: **accept** writes the line
   through the same writer as session.v4 §5 (writer `suggestion`, quote and
   session carried into the commit) and removes it from the inbox;
   **decline** appends the text to `declined.md` with the date and removes
   it; **skip** leaves it. For one existing pending, HUMAN-origin stable
   `s-NNN`, a clear natural authorization to accept corrected text — for
   example, `accept it but ...` — is **corrected accept**, not a new command
   and not ordinary accept. It must verify that the correction quote appears
   verbatim in a human turn; the required commit metadata maps quote to that
   actual verbatim human correction, session to that correction's session, and
   writer to `assistant`. The model may derive the corrected memory text from
   the correction, but it must never record the output as words the human said.
   In that same atomic commit, additional metadata retains separately the
   source suggestion id, original source quote, and original source session,
   without a separate provenance store and without overwriting, relabeling, or
   rewriting the original evidence. The one read-modify-write-commit writes
   only the corrected memory and removes the source `s-NNN` together; it never
   writes an accepted original-text intermediate, nor mutates the inbox after
   commit. A clear revision request resolved against a rendered stable `s-NNN`
   under the existing no-retarget rules is revise-only: it displays
   assistant-derived proposed corrected text and the actual verbatim human
   correction quote, but makes no memory, inbox, or id mutation and emits no
   success receipt. A later `yes` or `do it` approves the immediately displayed
   exact proposal-to-id map without retyping; a missing, ambiguous, or stale
   map, or no approval, leaves the source pending. Before commit succeeds, any
   validation, write, or commit failure restores unchanged memory, HEAD,
   pending source, and next id, with no success receipt. If commit succeeds but
   combined-state readback fails, it emits no success receipt and reports
   `commit succeeded but readback is unverified`; it must not claim unchanged,
   blindly retry, roll back, or create another id, and explicit inspection is
   the recovery. A reported commit error whose outcome is unknown likewise
   requires inspection rather than an assumption that nothing was written.
   Readback verifies the combined committed corrected-memory and source-removal
   state. In a multiple-item request, receipts for earlier completed items
   remain relayed and a later refusal is relayed too. Items unreviewed for 30
   days are dropped and counted in the next run's report.
```

### Change 2 — Conformance, review outcomes and audit preservation

Current text:

```
- Accept writes via the shared writer (commit carries writer `suggestion`,
  quote, session); decline appends to `declined.md`; a declined text is not
  re-proposed on the next run over the same transcript.
```

Replacement:

```
- Ordinary accept writes via the shared writer (commit carries writer
  `suggestion`, quote, session); decline appends to `declined.md`; a declined
  text is not re-proposed on the next run over the same transcript.
- A direct `accept it but ...` for a pending HUMAN-origin stable `s-NNN`
  succeeds only with a verbatim human correction quote. Its one atomic commit
  writes only corrected text, removes that `s-NNN`, and maps required metadata
  quote to the actual correction quote, session to the correction session, and
  writer to `assistant`; the same commit additionally retains separately the
  source suggestion id, original source quote, and original source session.
  Fresh-session readback verifies that combined committed state and no original
  unwanted memory was activated.
- A clear revision request resolves only against the rendered stable `s-NNN`
  under existing no-retarget rules and displays assistant-derived proposed
  corrected text with the actual human correction quote. It makes no
  memory/inbox/id mutation and emits no success receipt until a later `yes` or
  `do it` approves the immediately displayed exact proposal-to-id map. Missing,
  ambiguous, or stale maps, no approval, decline, and refusal leave the source
  pending with no write.
- Each injected validation, write, or known-unsuccessful commit failure before
  commit succeeds restores unchanged memory, HEAD, pending source, and next id,
  with no success receipt. A separate injected postcommit-readback failure
  proves that the receipt is suppressed and the report is exactly `commit
  succeeded but readback is unverified`; recovery is explicit inspection, not a
  claim of unchanged state, blind retry, rollback, or another id. A reported
  commit error with unknown outcome likewise requires inspection. In a
  multiple-item request, completed earlier receipts and a later refusal are
  both relayed.
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

- Ordinary accept remains exactly the existing `writer=suggestion` path; plain accept, decline, and skip semantics remain intact.
- Core 4's original quote verification, the existing caps and lock, stable ids, and no-retarget behavior remain intact.
- The source suggestion's original quote and session remain original audit facts; corrected output is never relabeled as a verbatim human quote.
- This adds neither a broad pipeline, per-user configuration, nor a service, and does not adopt reserved v4/v7 agent-autonomy work.
- No implementation, lock modification, or live proof is claimed by this decision record.

## Observable conformance

Success is observable when a direct `accept it but ...` or a later `yes`/`do it` for the immediately displayed exact proposal-to-id map accepts a pending HUMAN-origin stable `s-NNN`, the corrected text is the only memory written, and one atomic commit both removes that source and maps required metadata quote to the actual verbatim human correction, session to the correction session, and writer to `assistant`, while additionally retaining the source suggestion id, original source quote, and original source session. Committed readback — including from a fresh session — verifies that combined state and that no original unwanted memory was activated. Revise-only is observable when a clear reference under the existing no-retarget rules displays assistant-derived proposed corrected text and the actual human correction quote without a write, inbox/id mutation, or receipt; absent approval, a missing/ambiguous/stale map, decline, or refusal likewise leaves the candidate pending. Before commit succeeds, injected validation, write, and commit failures are observable when memory, HEAD, pending source, and next id are unchanged and no success receipt is emitted. A separate postcommit-readback failure is observable when it emits no success receipt and reports `commit succeeded but readback is unverified`; explicit inspection is then required, with no unchanged claim, blind retry, rollback, or new id. A reported commit error with unknown outcome also requires inspection. A batch is observable when it relays each earlier successful receipt and also relays a later refusal.

## Steward's word

The retained private original records the bounded ratification without
reproducing the interaction or its timing here. Ratification applies to the
exact replacements above and the paired `session.v5.v8-candidate.md`.
The separate prior-memory conversational requirement is independent; no
unwritten clause is approved by this record. The locked target stays
byte-identical. This bounded implementation authority is not a locked successor
or evidence of live conformance. No publication, activation, or real-store
change is authorized.
