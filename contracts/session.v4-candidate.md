# Proposal — amend `contracts/session.v4.md` in place (wrinkles left by the 2026-09-07 version bump)

target: contracts/session.v4.md

## The exact change

1. §13: `(suggestions.v1 §5)` → `(suggestions.v2 §5)`.
2. §6 `/memory` closing line: `edit by hand: $EDITOR ~/.amplifier/memory/MEMORY.md` → `edit by hand: $EDITOR <instance>/MEMORY.md` (the instance's real path, store.v3 §1) — the pre-v3 fixed path in v4 text.
3. Changelog: one "amended in place" entry naming this proposal.

## Evidence

The steward, 2026-09-07, after the manager named these wrinkles in the return brief: "Let's fix those wrinkles." The wrinkles are text left by the version bump of 2026-09-07 — a header or cross-reference still naming a superseded document or the pre-v3 default path, and one sentence the ratified cli proposal directed into a block that did not contain it. None of them is a clause change; each is prose that now contradicts a clause in the same locked file (reconciler and builder reports, 2026-09-07).

## What does NOT change

Every numbered clause's meaning and teeth. The H1 and its FROZEN date. Every conformance probe and ledger row (the reconciler's re-pin already targets the current versions).

ratified by owner 2026-09-07 — the steward's words: "Let's fix those wrinkles."
