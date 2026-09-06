# Proposal: session.v1 → v2 (CANDIDATE)

**Changes:** `contracts/session.v1.md` (FROZEN 2026-09-06). Written 2026-09-06 by the manager
session from the four reviews in `docs/workflow/reviews/` and the steward's transcript in
`.converge/feedback/2026-09-06-kicked-the-tires-transcript.md`. The original stays the law
until the steward's word lands below.

## Target lines and exact changes

**§2 "Announce the load, once."** — currently: *"The first assistant reply of a session (and
the first after compaction) carries a single line: `Loaded N memories (M topics available).`
When `MEMORY.md` is empty: `No memories yet — /remember <text> to add one.`"*

Replace with:
> **Announce the load, once, in code.** The inject hook renders one line to the human through
> the runtime's user-message channel on the first model request of a session and on the first
> after a compaction — never by instructing the model:
> `3 memories loaded. /memory to see them.` (topics named only when more than zero:
> `3 memories loaded, 2 topics. /memory to see them.`); after a compaction
> `context compacted. 3 memories still loaded.`; when `MEMORY.md` is empty
> `no memories yet. Tell me a standing preference — "never use tabs in YAML" — and I'll keep it
> in every session on this device.` The injected block carries no announce instruction.

**§3 save announce** — currently the literal `Saved memory m-017: "<text>" — /forget m-017 to
undo.` Replace the literal with a three-line receipt rendered by the tool result, never
restated by the model:
> `saved m-017 — /forget m-017 to undo.` then the memory text on its own line, then a
> provenance line: `your words, verbatim` when writer is `human`, or
> `my wording, your go-ahead: "<the quote>"` when writer is `assistant`.

**§6 commands** — currently three commands and *"These are the only commands."* Replace with:
> **`/remember <text>`** writes exactly what the human typed. **`/edit <id> <text>`** replaces
> one memory's text keeping its id; the commit carries the old text (`was:`) and the new; the
> receipt is `edited m-004 — was: "<old>"` then `now: <new>`. **`/forget <id>`** removes the
> line and commits; the receipt is `forgot m-002 — still in git: amplifier-memory why m-002`
> then the removed text on its own line. **`/memory`** renders `MEMORY.md` with ids, `-`
> bullets, and the line `edit by hand: $EDITOR ~/.amplifier/memory/MEMORY.md`; the model does
> not restate it. These are the only commands. Ids are the only names: a bare number `N`
> means `m-00N`, never a position; a destructive command that cannot resolve its id asks
> (`no memory m-004 — forgotten 2026-09-06. Current: m-003, m-005. Say the id.`) and never guesses.

**§8 "Cite at use."** — currently a promise about model behaviour. Replace with:
> **Cite at use, and count it.** When a memory changes what the assistant would otherwise have
> done, it says so inline (`going long here, per m-004`). The tool records each citation as a
> `cited` usage event (store.v1 §8) and `amplifier-memory status` shows the citation rate.
> The rate is a floor, never an estimate; the contract promises the instrument, not the rate.

**Conformance** — add: every receipt above is byte-identical to a fixture and contains no
commit sha, no phase name, no zero-valued subsystem count, no `<placeholder>`; the announce
line renders in a real PTY session exactly once on the first request and once after a
compaction (device-checked); `/memory` costs one model round trip and the listing shown equals
the file.

## Evidence (a cost paid, a failure caught — not a preference)

- **§2:** the announce re-fired mid-session after saves (transcript, `Loaded 3 memories` at
  the head of a reply that was not the first) and was suppressed by a reply constraint in 1 of
  2 one-shot runs (lane E); a byte-identical block cannot know it is the first reply (design
  council B8). The mechanism to render exists: `HookResult.user_message`
  (`hook_dispatch.rs:282-313` → `CLI/ui/display.py:98-128`), already used by this bundle for
  failures. Cost paid: the product's only per-session proof of value ran at about a third.
- **§3:** the mandated literal cannot render 2 of the steward's 5 memories (nested quotes:
  `"When I say "explain" …"`); the receipt showed the assistant's rewrite in quotation marks as
  if it were the human's words (Dana F4, "the single highest-trust-cost behaviour observed").
- **§6:** "Get rid of memory 2 please, update 4 to …" (steward) and "Update memory 2 to say …"
  (Dana): both produced forget + new id; the number the UI taught was retired one turn later.
  cli.v1 §3 already promises `why` prints "creation, edits, and forget" — a verb no contract
  grants. `Forgot m-001.` echoed nothing on the one irreversible operation. `/memory` cost
  $0.19–$0.20 and 28 screen lines for a two-item `cat`.
- **§8:** the string `per m-` appears zero times across every real session (three reviews);
  a memory that says "no preamble" was loaded and the next reply opened with "Hey — good to
  see you". The kept count called that a success.

## What does NOT change

§1 (loaded in every request, byte-identical block, framing sentence), §4 (do not save), §5
(the model proposes; the writer commits; the human-turn check), §7 (recall is reading), §9
(nothing at session end), §10 (fail open), R1, R2, the 200-line cap, the ids `m-NNN` never
reused, the VISION's principles 1–9 and everything under *Deliberately resists*. No confirm
gate is added (unanimous). The quote check stays.

## Steward's word

_ratified · ratified with edits · declined · later_ — and the date: ____________
