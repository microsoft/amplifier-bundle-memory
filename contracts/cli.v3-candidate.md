# Proposal — amend `contracts/cli.v3.md` in place (a Conformance bullet the v3 lock left behind)

target: contracts/cli.v3.md

## The exact change

1. Conformance bullet "A fresh `init` on a Phase 2 host against `~/.amplifier/memory` leaves the timer installed and enabled; the same `init` against a temp store creates the store, writes no unit, and prints the outside-store line (this is what keeps every conformance kit from enabling a real timer);" → "A fresh `init` against any instance builds it and installs that instance's own timer (§8) — in a kit, only ever through an injected runner and unit dir, so no probe reaches the device's `systemctl` (the kit's standalone run proves it: the device timer's activation stamp is byte-identical before and after);". The rest of the bullet is unchanged.
2. Changelog: one "amended in place" entry naming this proposal.

## Evidence

Lane W's DONE.json residual (2026-09-07, merge 4c4b53a): the v3 lock changed §8 to per-instance timers but left this v2-era bullet, which now contradicts §8 ("writes no unit" vs "installs a per-instance timer"). The steward, 2026-09-07: "Take care of that residue." No clause changes; the Conformance section describes how §8 is checked.

## What does NOT change

Every numbered clause. The H1 and its FROZEN date. The Changelog's history entries (2026-09-07's earlier amendments stay as written).

ratified by owner 2026-09-07 — the steward's words: "Take care of that residue."
