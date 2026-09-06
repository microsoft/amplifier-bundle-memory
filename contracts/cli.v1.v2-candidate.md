# Proposal: cli.v1 → v2 (CANDIDATE)

**Changes:** `contracts/cli.v1.md` (FROZEN 2026-09-06). Written 2026-09-06 by the manager
session. The original stays the law until the steward's word lands below.

## Target lines and exact changes

**§3 `why <id>`** — currently *"creation, edits, and forget if any."* Keep the sentence; add:
> `edit` is a real operation (session.v1 §6): `why` shows each edit as `was:` → `now:` with
> its date, session and writer. Forget entries are marked `forgot` in the first line so a
> removal is never mistaken for a creation.

**§5 `doctor`** — currently *"`doctor` never mutates."* Replace with:
> `doctor` never mutates. `doctor --repair` is the one explicit exception: it restores
> `MEMORY.md` from the last commit whose file parsed clean, prints the diff and every line it
> discards before committing, and commits `repair: …` visibly. It is the sanctioned repair;
> the model never edits the store by hand.
> Add a row: `MEMORY.md well-formed` — every line parses as store.v1 §3, or FAIL naming the line.

**§2 `status`** — add the citation rate (`cited` events / `loaded` events, 30 days) beside the
kept count, and print `kept` with the pre-registered definition: written ≥ 7 days ago and still
present, where an `edit` keeps the original write date.

## Evidence

- The steward's assistant repaired a corrupted `MEMORY.md` with `printf` and `git commit` in
  chat ("I'll use bash to write the file rather than going through the read_file/write_file
  gate") because no sanctioned repair existed — VISION principle 4 broken by plan. Lane F built
  `doctor --repair`; the contract must say so or `doctor` is in breach of its own §5.
- `git log --oneline` in the Dana store shows `[m-002] always run make check before pushing`
  twice — one is the save, one the forget.
- cli.v1 §3 has promised "edits" since it was locked; no contract grants the verb (four
  product lenses and one design lens found this independently).

## What does NOT change

§1 verbs (`edit` is a session command, not a CLI verb — `/edit` in the session, hand edits in
`$EDITOR`), §4, §6, §7, §8, §9 thin wrapper. `doctor` without `--repair` is still byte-identical
before/after.

## Steward's word

_ratified · ratified with edits · declined · later_ — and the date: ____________
