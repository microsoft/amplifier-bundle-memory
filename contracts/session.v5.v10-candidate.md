target: contracts/session.v5.md

# session.v5.v10 candidate — conversational decline rationale capture (RATIFIED 2026-09-13 — bounded implementation addendum)

> **SANITIZED PUBLICATION COPY.** The retained private original has SHA256 `4abe57168a0a9c0970b42b40113ac8887026ec5325d9335fb0f6954fa7e7ea7e`. Redactions are limited to nonnormative evidence and identifying metadata; all normative clauses and exact-change blocks are byte-identical. This copy is not a new version, lock, or ratification.

## Ratification record

The intent steward answered **“ratified”** to the coupled three-file set on
2026-09-13.
Together with `store.v3.v4-candidate.md` and
`suggestions.v3.v6-candidate.md`, this authorizes the specified bounded
implementation and isolated evaluation only. Publication, live installation,
production-job reruns, existing-decline backfill, and workspace teardown remain
outside that approval. All exact-change blocks below are unchanged from the
reviewed proposal; the frozen parent contracts remain untouched.

## Exact change, sentence by sentence

### Change 1 — Core 6, append to `review` immediately before `forget`

Current text:

```
   - **`forget <id>`** — removes the line and commits; the receipt is
```

Replacement:

```
     **Conversational decline rationale:** A clear human decline resolved to a
     frozen action-to-id map authorizes that decline's existing state change; no
     new `authorization` argument or extra round trip is required. The original
     suggestion quote remains old-proposal provenance. In the same declining
     session, the human may also supply an optional reason as nonauthorizing
     feedback: reason text alone cannot trigger a decline or any memory save.
     Before the first mapped batch write, the assistant freezes an unambiguous
     reason-to-id map together with the action-to-id map, then calls
     `memory(review, action=decline, id=stableid, reason=<raw human string>)`.
     One exact clear reason may apply to several stated declines; distinct
     reasons stay attached to their respective ids. If action and ids are clear
     but a supplied reason's binding is ambiguous, the assistant asks one
     targeted clarification before any mapped batch write. With no reason,
     ordinary decline asks no question and remains byte-compatible. A reason is
     valid only for decline: a reason supplied to accept or skip refuses without
     mutation.

     The writer validates the raw reason before any write: at most 2,000 decoded
     UTF-8 bytes, verbatim evidence in the current session's observed typed
     human channel. The assistant resolves decline authorization through the
     existing conversational action-to-id map; this adds no natural-language
     intent parser or new authorization argument to the library.
     That provenance check establishes the observed channel, not infallible
     authorship; the model is instructed not to extract a reason from quoted
     external material, and conformance discriminates that case. On invalid,
     overlong, or unverified reason it refuses with no change. It stores the
     reason paired with that item's original text and quote, JSON-escaping it
     only for storage and receipt. Existing origin, sub-agent, and write guards
     remain unchanged. Each successful decline keeps its existing lock and
     atomic inbox/declined-state commit. A later refusal cannot undo earlier
     successes, and after a stale failure the assistant never relists, rebinds,
     or retargets. If a commit succeeds but readback fails, it reports that
     state as unverified rather than claiming no change.

     The existing no-reason decline receipt is unchanged. A reason-bearing
     successful decline relays the existing fenced receipt followed by exactly
     `  reason: <JSON string>`; JSON escaping preserves quotes and newlines
     without forging receipt lines. Guidance for `reason` appears only in the
     memory tool and memory skill; no CLI flag is required. Rationale feedback
     is not always-loaded memory: per the paired suggestions change it is only
     available to future suggestion passes in the same instance, and no general
     assistant-context injection is added.

   - **`forget <id>`** — removes the line and commits; the receipt is
```

### Change 2 — Conformance, insert a separate rationale check before existing checks

Current text:

```
## Conformance
```

Replacement:

```
## Conformance

- A full-conversation evaluation loads the actual memory skill and renders a
  real review page from a fresh synthetic store. It checks that a natural,
  current-turn reason with a clear decline needs no extra confirmation;
  shared-reason and distinct-reason batches bind correctly; an ambiguous
  supplied reason has no write; quoted external material is not extracted as a
  reason; an invalid, overlong, or unverified reason has zero change before
  write; a plain review and no-reason decline retain their exact format; and a
  later rejection preserves earlier successful ordered receipts. Readback
  failure after a committed decline is reported as unverified, not unchanged.
  `store.v3.v4-candidate.md` owns the decoded-byte cap, paired storage, and
  commit checks. `suggestions.v3.v6-candidate.md` owns broader-context
  consumption and its three judge quality groups; this contract adds no
  evaluation taxonomy.
```

## Evidence — failure caught and cost paid

A bounded review exposed that decline feedback was not retained for a later
suggestion pass. The retained private original holds the nonnormative observation.
The paid cost was feedback that could not inform that later review. Missing
assistant context is only one plausible contributor to earlier false positives;
this evidence does not establish their cause. Directional user agreement is not
exact ratification.

## What does NOT change

- The locked target remains untouched. Both insertion anchors occur once in
  `session.v5.md`. The `forget` anchor is unchanged at the start of v9's
  replacement; the new rationale paragraph is inserted before it. The
  Conformance heading is unaffected by both prior addenda. The v8 corrected-
  acceptance and v9 prior-memory flows and their checks remain unchanged;
  this draft adds rationale behavior and checks rather than replacing theirs.
- Plain decline behavior and its receipt remain byte-compatible when no reason
  is supplied. Existing tool and shell commands continue to work; no review
  page, help format, CLI verb, or required CLI flag is added.
- The original human quote, window, origin, and writer gates are not relaxed.
  There is no global-memory change, hand-edited tool context, automatic
  `MEMORY.md` save, historical backfill, or general assistant-context injection.
- Already-declined records receive no backfill in this release;
  future declines only are in scope unless the human later explicitly corrects
  them.

## Coupled ratification request

This is one inseparable three-candidate set with `store.v3.v4-candidate.md` and
`suggestions.v3.v6-candidate.md`. All three must be ratified to license their
bounded implementation and evaluation within these agreed changes. That joint
ratification authorizes no live activation, publication, or actual-store
backfill.

## Steward's word

Decision (select one):

- [ ] ratified
- [ ] ratified with edits
- [ ] declined
- [ ] later

Steward notes:
