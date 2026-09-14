target: contracts/store.v3.md

# store.v3.v4 candidate — declined-reason provenance (RATIFIED 2026-09-13 — bounded implementation addendum)

> **SANITIZED PUBLICATION COPY.** The retained private original has SHA256 `e9a61907eeadd613fba375a061fc46ef932170fce1fc46673e644eeb31295cc5`. Redactions are limited to nonnormative evidence and identifying metadata; all normative clauses and exact-change blocks are byte-identical. This copy is not a new version, lock, or ratification.

## Ratification record

The intent steward answered **“ratified”** to the coupled three-file set on
2026-09-13.
Together with `session.v5.v10-candidate.md` and
`suggestions.v3.v6-candidate.md`, this authorizes the specified bounded
implementation and isolated evaluation only. Publication, live installation,
production-job reruns, existing-decline backfill, and workspace teardown remain
outside that approval. All exact-change blocks below are unchanged from the
reviewed proposal; the frozen parent contracts remain untouched.

## Exact change

### Change 1 — §6, insert after the unique ending

Insertion anchor:

```
   `amplifier-memory why m-017` is `git log --grep '\[m-017\]'`. No separate
   provenance store exists.
```

Insertion:

```

   A reason-bearing decline additionally records its frozen source `s-NNN`, the
   original suggestion text and quote, the actual declining human's session id,
   `reason: <JSON string>`, and the human writer of that reason. The original
   quote supports the original proposal; the explicit decline plus frozen id map
   authorizes the decline action; the optional reason is nonauthorizing feedback.
   The library writer validates the reason against actual human-turn evidence
   before persisting it. Ordinary declines without a reason retain their existing
   schema and need no session id or new parameter.
```

### Change 2 — §7, optional verified reason on the existing declined record

Current text:

```
7. **declined.md** is an append-only list of declined suggestions, one per line:
   `- <YYYY-MM-DD> <text>  quote: "<quote>"` — the verbatim human quote after the
   text. Older two-field lines (`- <YYYY-MM-DD> <text>`) stay readable and keep
   working. It is fed back to the Phase 2 prompt and matched exactly by code on
   **text OR quote**, so a declined suggestion returning paraphrased is blocked. Declining is not forgetting: a declined suggestion was
   never in MEMORY.md.
```

Replacement:

```
7. **declined.md** is an append-only list of declined suggestions, one per line:
   `- <YYYY-MM-DD> <text>  quote: "<quote>"` — the verbatim human quote after the
   text — with optional appended `  reason: <JSON string>`. The model passes a raw
   reason string, never JSON input; the library writer validates it against actual
   human-turn evidence before mutation, then JSON-encodes it for storage. Its
   decoded UTF-8 value is the exact human words, not a summary, is at most 2,000
   bytes, and is encoded control-safely (including quotes, backslashes, and
   newlines). A known bad reason (unverified, overbound, or unsafe) is refused
   before any mutation, never silently dropped or truncated. Blank or absent
   reason is an ordinary decline and asks no extra question.

   Older two-field lines (`- <YYYY-MM-DD> <text>`) and current text-and-quote
   lines stay readable and keep working. A new reader distinguishes an absent,
   valid, and invalid stored reason; malformed stored JSON is invalid reason data,
   not malformed raw input. Where its base text and quote remain recoverable, it
   preserves their exact text-or-quote deduplication, omits the invalid reason
   from judge input, and reports only an invalid-reason count, never reason text
   in logs. If base fields are unrecoverable, existing malformed-store
   refusal/degraded-reporting behavior applies. A new reader must read legacy
   lines; forward compatibility with an old binary is not required. Matching
   remains exact on **text OR quote**, so a declined suggestion returning
   paraphrased is blocked. Declining is not forgetting: a declined suggestion was
   never in MEMORY.md.

   A valid reason is private feedback for future suggestion passes in the same instance only.
   It is not an active personal rule or itself an injected, suggested, or cited
   memory. Its feedback scope is judged against the paired item; it does not
   automatically create a global ban. No new file, database, or MEMORY.md entry
   is created. The existing one-item lock and inbox-plus-declined-change/one-
   commit semantics remain. Success is reported only after committed state is
   verified; a failed post-commit readback follows existing unknown-outcome
   failure behavior and never claims no change or rollback after a landed commit.
   Partial batches remain non-atomic with per-item results. Human hand editing
   and reversal remain available as for every declined record; reasons are never
   automatically reaped.
```

### Change 3 — Conformance, append after the current `declined.md` bullet

Insertion anchor:

```
- `declined.md` exact-match blocks re-proposal (suggestions.v2 conformance).
```

Insertion:

```
- A new reader accepts legacy two-field and text-and-quote declined lines, and
  distinguishes absent, valid, and malformed stored reasons. A valid reason
  round-trips JSON escaping to exact human words; a hand-edited malformed reason
  preserves recoverable text-or-quote blocking, is omitted from judge input, and
  increments only the invalid-reason report.
- A raw unverified, over-2,000-decoded-UTF-8-byte, or unsafe reason refuses before
  inbox removal, declined-record change, or commit. The accepted path supplies
  actual human-turn evidence, not an adapter assertion. A reason stays scoped
  feedback, not a rule or guaranteed semantic-repeat prevention.
```

## Evidence

An audited bounded run exposed a persistence and provenance failure: decline
reasons were not retained with the declined record or supplied to a later
suggestion pass. The retained private original holds the nonnormative observation.
That is a cost against the product capability requirement and architecture
acknowledgement, not a preference. The observation does not establish a causal
explanation for earlier proposals. The current two-field declined format is
encoded in public `src/amplifier_memory/inbox.py` parser and decline-writer paths.

## Coupled proposal dependencies

This amendment is persistence and provenance only. Consumption and bounded
context belong to `suggestions.v3.v6-candidate.md`; optional tool reason, batch
binding, and receipt behavior belong to `session.v5.v10-candidate.md`. If the
combined set is ratified, that authorizes only bounded implementation and
evaluation of these exact changes—not live installation, job rerun, memory
migration, or publication. No candidate alone authorizes activation; this DRAFT
currently authorizes none.

## What does NOT change

- The five existing locked-document pins remain byte-identical now; this draft
  neither freezes nor ratifies anything, and makes no changelog claim.
- Existing two-field and text-and-quote declined records, ordinary no-reason
  declines, their receipts, and exact text-or-quote deduplication stay unchanged.
- There is no migration, synthesis, or backfill for existing declines, and no
  live-store write, code, ledger, lock, or test change is authorized by this
  draft.
- One-item locking, inbox-plus-declined-change/one-commit semantics, committed-
  state success verification, and per-item partial-batch behavior remain.
- No independent rule database or automatic MEMORY.md rule is added; scoped
  feedback is not guaranteed to prevent semantic repeats.

## Steward's word

Coupled set: **ratified** · **ratified with edits** · **declined** · **later**
