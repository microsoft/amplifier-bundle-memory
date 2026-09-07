# Proposal: amend store.v2 in place (CANDIDATE)

target: contracts/store.v2.md

**Changes:** `contracts/store.v2.md` (FROZEN 2026-09-06). Written 2026-09-07 by the manager
session alongside `session.v2.v3-candidate.md` Part B. Wording only — the commands session v3
renames are quoted here in five places. No promise is added, removed or weakened, so this
amends v2 in place rather than minting a v3. The original stays the law until the steward's
word lands below.

## Target lines and exact changes

### Change 1 — §3, ids (lines 40–41)

Current text:

```
   `m-NNN` is a stable id assigned by code, never reused after `/forget`,
   and kept across `/edit`. Lines may be grouped under `## headings` chosen
```

Replacement:

```
   `m-NNN` is a stable id assigned by code, never reused after a forget,
   and kept across an edit. Lines may be grouped under `## headings` chosen
```

### Change 2 — §4, the cap remedy (line 49)

Current text:

```
   remedy (consolidate into a topic file, or `/forget` something). The
```

Replacement:

```
   remedy (consolidate into a topic file, or `/memory forget` something). The
```

### Change 3 — §6, the writer field (lines 58–59)

Current text:

```
   justified it, the session id, the writer (`human` for `/remember` and
   `/edit`, `assistant` for in-turn saves, `suggestion` for accepted inbox
```

Replacement:

```
   justified it, the session id, the writer (`human` for `/remember` and
   `/memory edit`, `assistant` for in-turn saves, `suggestion` for accepted inbox
```

### Change 4 — Conformance (lines 115–116)

Current text:

```
- `/forget` removes the line and commits; the id is never reassigned.
  `/edit` keeps the id.
```

Replacement:

```
- `/memory forget` removes the line and commits; the id is never reassigned.
  `/memory edit` keeps the id.
```

## Evidence

The same as session v3 Part B: the steward's slash list this session showed `/edit` beside
`/code-review` (*"is /edit for editing files?"*), and the consolidation renames the commands
this contract quotes. A store contract that names commands the session no longer ships is
drift by definition; the check would read *Broken* on the day session v3 locks.

## What does NOT change

Everything this contract actually promises: the location, the git repo, the line grammar,
the ids never reused, the 200-line cap enforced by the writer, provenance in every commit,
`usage.jsonl`, topic files under `topics/`, the 50-topic cap, `declined.md`, `inbox.md`,
`doctor --repair`.

## Steward's word

ratified by owner — 2026-09-07, in conversation, the single word "ratified" (together with
`session.v2.v3-candidate.md`). Applied in place to `contracts/store.v2.md` with a changelog
entry in the same write.
