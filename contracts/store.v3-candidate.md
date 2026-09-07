# Proposal — amend `contracts/store.v3.md` in place (wrinkles left by the 2026-09-07 version bump)

target: contracts/store.v3.md

## The exact change

1. Line 3 header: `**Governs:** everything under `~/.amplifier/memory/`` → `**Governs:** everything under a memory instance (default `~/.amplifier-memory/`; §1).`
2. Cross-references to superseded versions → current: `(suggestions.v1)`→`(suggestions.v2)` (§2 inbox.md line), `(session.v2 §7)`→`(session.v4 §7)`, `(cli.v2 §5)`→`(cli.v3 §5)`, `(session.v2 §8)`→`(session.v4 §8)`, `(session.v2 §5)`→`(session.v4 §5)`, `(suggestions.v1 §6)`→`(suggestions.v2 §6)`, `(suggestions.v1 conformance)`→`(suggestions.v2 conformance)`. Clause numbers verified identical across the versions.
3. Changelog: one "amended in place" entry naming this proposal.

## Evidence

The steward, 2026-09-07, after the manager named these wrinkles in the return brief: "Let's fix those wrinkles." The wrinkles are text left by the version bump of 2026-09-07 — a header or cross-reference still naming a superseded document or the pre-v3 default path, and one sentence the ratified cli proposal directed into a block that did not contain it. None of them is a clause change; each is prose that now contradicts a clause in the same locked file (reconciler and builder reports, 2026-09-07).

## What does NOT change

Every numbered clause's meaning and teeth. The H1 and its FROZEN date. Every conformance probe and ledger row (the reconciler's re-pin already targets the current versions).

ratified by owner 2026-09-07 — the steward's words: "Let's fix those wrinkles."
