# UX review brief — amplifier-bundle-memory after its first real day

For the product council, the design council, the engineering council and a simulated-user
pass. Read this file, then the evidence it points at. Judge the **experience** the steward
had, and propose what the updated experience should be. Do not judge the code.

## What the product is (in one breath)

A human working with the Amplifier CLI says a standing preference once ("never use tabs in
YAML"), sees it saved in the same turn, and never says it again — in any session, any project,
on this device. Memory is one file, `~/.amplifier/memory/MEMORY.md`, capped at 200 lines, kept
in git, loaded verbatim into every model request as *hints*, written only through a
deterministic writer from the human's own words. Three slash commands (`/remember`, `/forget`,
`/memory`), one CLI (`amplifier-memory init · status · why · doctor · …`). No daemon, nothing at
session end. Success metric: memories the human still keeps after a week (≥ 5).

Governing documents (locked): `docs/VISION.md`, `contracts/store.v1.md`,
`contracts/session.v1.md`, `contracts/cli.v1.md`. Read the VISION's *Principles* and
*Deliberately resists* sections — a proposal that crosses one of those needs to say so and why.

## The evidence

`.converge/feedback/2026-09-06-kicked-the-tires-transcript.md` — the steward's own two
sessions, verbatim. Read it whole. What happened, in order:

1. First reply of the session opened with `No memories yet — /remember  to add one.` — the
   `<text>` placeholder was swallowed by the terminal's markup, and the line sat above an
   unrelated "wayfinder" promotional paragraph.
2. The steward asked how to get "more of" an always-on behaviour bundle "as a memory". The
   assistant produced a good table (bundle context vs memory) and four candidate `/remember`
   lines, then said: **"Constraint: I can't write these for you. The memory tool refuses any
   quote that doesn't appear in one of your own messages. You type them."** — the steward had
   to be told to paste four commands.
3. The steward instead said "Great remember these for me…" (plus reshaping instructions). The
   assistant saved three — using "Great remember these for me" as the quote for text the
   assistant itself wrote — and **fired the three saves in parallel; the store was corrupted**
   (one reported success without landing, one reported failure but landed, one landed as a
   headless fragment). The assistant repaired `MEMORY.md` by hand with bash, then re-saved
   serially. The steward saw a 300-word incident report in their chat. (A fix lane is already
   running — the council should assume the writer becomes safe; judge the *experience* around
   saves, not the bug.)
4. After the saves, the assistant's reply began with `Loaded 3 memories (0 topics available).`
   — the "announce once" line re-fired because the count changed mid-session.
5. Next session: `/memory` cost a model round-trip (load a skill, call the tool, restate the
   list) — about $0.20 and 6 seconds for a `cat`.
6. The steward said "Get rid of memory 2 please, update 4 to …". There is no *update*: the
   assistant forgot m-004 and saved m-005 (new id), and the parallel forgets raised a raw
   `Command '['git', … 'commit' …]` error in the chat although both had landed.
7. Session cost: $1.90 for the first session, of which the memory incident was most of one turn.
8. What worked: the save-in-turn with verbatim quote and undo hint; the load in the next
   session; the human's exact words in the commit; `/memory` showed the store; forget worked.

## The design as it stands (so you can propose against it)

- **Load:** a hook injects `MEMORY.md` verbatim into every model request inside a
  `<system-reminder>` block that also carries an *instruction to the model*: "On your first
  reply of this session, say once: Loaded N memories (M topics available)." — the announce is
  model behaviour, not a rendered line.
- **Save:** the model calls the `memory` tool with `text` (its one-line imperative) and
  `quote` (a verbatim substring of a human turn). The library checks the quote appears in a
  human turn, assigns `m-NNN`, enforces caps, commits `[m-NNN] text / quote / session /
  writer`. Contract: "Only the human's own words become memory" (VISION principle 5) — in
  practice the *quote* must be the human's; the *text* is the model's distillation.
- **Commands:** `/remember`, `/forget`, `/memory` are user-invocable *skills* — the CLI hands
  the line to the model, which calls the tool. The CLI's command registry is closed to bundles.
- **Ids:** `m-NNN`, stable, never reused; there is no edit — forget + new save. `why m-NNN`
  reads git for creation/edits/forget.
- **CLI:** `amplifier-memory status` shows written/kept/forgotten counts — "the only thing that
  matters".

## Questions for the councils (answer each; disagree with each other on purpose)

1. **The save moment.** When the assistant has drafted candidate memories and the human says
   "yes, remember these", what should happen, and what should the human see? Is the quote check
   (a human substring) the right guarantee, or theatre? Should there be a `Remember this?`
   confirm, given VISION principle 1 says "announce and undo, not approve"?
2. **Load announce.** Should "Loaded N memories" be a line the *tool* renders (deterministic,
   once, cache-safe) rather than something the model is told to say? What should the very first
   session with an empty store show, and where?
3. **Edit.** "Update memory 4 to …" is a natural request. Should there be `edit` (same id,
   provenance in git), and should `/forget` + new id remain the only path?
4. **Command cost.** `/memory`, `/forget m-002` should be free and instant. Within the
   constraint that a bundle cannot add CLI commands, what is the best achievable path (skill
   that forbids the model from restating; deterministic hook; CLI verb the user runs in another
   pane; ask the Amplifier CLI for a registry)? Which do you recommend and why?
5. **Noise.** Tool results say "(committed b5fb8cd to MEMORY.md)" and "(Phase 1 records none)".
   Announce lines sit above unrelated promotional text. What should the human see per save, per
   forget, per load — exactly, in characters?
6. **Trust after a failure.** After the corruption the steward read a 300-word incident report.
   What should a failure look like to the human (one line? where?), and what must never happen?
7. **Names.** `m-003`, `m-005` — after a forget the numbers have holes. Fine, or should the
   human see ordinals? Should `/memory` show ids at all?
8. **What is missing** that the transcript shows the steward reaching for and not finding.

Deliver: for each question a verdict, the dissent, and — where you change the experience — the
exact text the human sees, so the manager can write it into a contract candidate. Stay inside
the VISION unless you name the principle you would change and the cost that justifies it.
