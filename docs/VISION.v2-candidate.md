# Proposal: VISION → v2 (CANDIDATE)

target: docs/VISION.md

**Changes:** `docs/VISION.md` (FROZEN 2026-09-06), which stays the law until the steward's word lands below. Scope only:
"one human, one device, one store" becomes "one human; each app or project points at an INSTANCE" — vocabulary matching
the sibling `contracts/store.v2.v3-candidate.md`. The Changelog entry is written on landing.

## The exact change, sentence by sentence

### Change 1 — "The one sentence"
Current text:
```
A human working with Amplifier says a standing preference **once**, sees it
saved, and never has to say it again — in any session, on any project, on
this device.
```
Replacement:
```
A human working with Amplifier says a standing preference **once**, sees it
saved, and never has to say it again — in any session, on any project, on
this device, against whichever memory **instance** that app or project points
at.
```
### Change 2 — "What memory IS here", the opening two sentences
Current text — the clause continues "verbatim, framed as *memories — hints to verify against current reality*. …", unchanged:
```
**Memory is a file.** One directory of plain markdown under git:
`~/.amplifier/memory/`. A capped `MEMORY.md` is loaded into every session,
```
Replacement:
```
**Memory is a file.** An **instance** is one directory of plain markdown under
git, holding the memories and its own `config.yaml`; the default is
`~/.amplifier-memory`. An app or a project points at one — an explicit `home:`
in its config, else `$AMPLIFIER_MEMORY_HOME`, else the default — so two apps
keep separate instances, several apps share one, or a project sets
`enabled: false`: nothing injected, no memory tool offered, nothing advertised.
An instance per project is just a `home:`. A capped `MEMORY.md` is loaded into
every session,
```
### Change 3 — "Deliberately resists", the team-memory bullet
Current text:
```
- **Team or shared memory.** This is how *one human* works on *one device*.
  Sharing goes through the repo's `AGENTS.md`, by hand.
```
Replacement:
```
- **Team or shared memory.** This is how *one human* works on *one device*.
  Several apps may share one instance; several humans never do. Sharing
  between people goes through the repo's `AGENTS.md`, by hand.
```
### Change 4 — "Backlogged", the project-scoped bullet is removed
No longer backlogged — Change 2 covers it in the body ("an instance per project is just a `home:`"). The other two bullets
are untouched; **cross-device sync stays backlogged.** Current text — the bullet, plus the line after it for position:
```
- **Project-scoped memory** → the repo's `AGENTS.md` (already loaded by
  Amplifier). Promote when the first memory is clearly project-only and the
  owner asks for `/remember --project`.
- **Mid-session hot-load** of a topic file the assistant did not think to
```
Replacement:
```
- **Mid-session hot-load** of a topic file the assistant did not think to
```

## The evidence
**The steward's own words, 2026-09-07, verbatim:**

- "giving the option for multiple memory stores/instances that can be pointed to via the AmplifierSession/modules config per
  app (or even project dir) should be permitted."
- "I might point it to ~/.amplifier/memory … Then I could also have a ~/.amplifier-agent/memory dir for those sessions. Or I
  could create a ~/.amplifier-memory dir and use it in multiple apps... or I could configure `enabled: false` in the config and
  disable both read/write and even advertisement of the memory features in a given config (where I want to disable memory
  support in an amplifier-app-cli project dir)"
- "since it is amplifier-app-cli that owns the ~/.amplifier dir, and other Amplifier ecosystem experiences have _other_ dirs
  they own (like amplifier-agent uses ~/.amplifier-agent/ for it's global dir)"

**A cost already paid.** The store is found by one env var or one fixed path, in two places — `store_home` at
`src/amplifier_memory/store.py:461-465` and `_memory_home` at
`modules/hooks-memory-inject/amplifier_module_hooks_memory_inject/__init__.py:153-162` — each `$AMPLIFIER_MEMORY_HOME` else
`~/.amplifier/memory`. So a second app cannot have its own memory, a project cannot turn memory off, and the one config knob
had to ship *outside* the store at `~/.amplifier/memory-config.toml` because the fixed layout forbade a config file inside it
(`AGENTS.md:49-50`).

## What does NOT change
**One human** — not team memory, not multi-human sharing, no wire face. **The correction is still the moment of capture**:
written in the turn, announced with its undo. **The three surfaces** stand — the capped `MEMORY.md` injected every session,
topic files read on demand, and **the daily suggestion inbox** that proposes and never mints. **The honesty rules** stand —
memories are hints, only the human's own words become memory, every save/forget/load/refusal is visible, nothing re-derivable
is stored, `git log` is the "why". The 200-line cap, principles 1–9, "nothing runs at session end", and the resisted list
(daemon, consolidation machinery, embeddings, approval gates, automatic deletion) are untouched. Every existing store keeps
working: `~/.amplifier/memory` is still found, with or without `AMPLIFIER_MEMORY_HOME`.

## Steward's word
Answer in one word: **ratified** · **ratified with edits** · **declined** · **later**.

>
