# Proposal: store.v2 → v3 (CANDIDATE)

target: contracts/store.v2.md

**Changes:** `contracts/store.v2.md` (FROZEN 2026-09-06, amended 2026-09-07). Written
2026-09-07 by the manager session; the original stays the law until the steward's word lands
below. **A version bump, not an amendment:** §1's default path changes — v3, not an amend.

## The exact change, sentence by sentence

### Change 1 — §1, Location

Current text — §1's opening sentences only; the clause continues "Every mutation is one
commit. …", unchanged:
```
1. **Location.** `${AMPLIFIER_MEMORY_HOME:-~/.amplifier/memory}` — a git
   repository initialized by `amplifier-memory init`.
```
Replacement:
```
1. **Location — an instance.** A store is a directory, and there may be more than
   one. Resolved in order: an explicit `home` from the caller (the modules'
   mount-plan `config: home:`, or the CLI's `--home`), else `$AMPLIFIER_MEMORY_HOME`,
   else the default `~/.amplifier-memory`. Each is an independent instance — its own
   git repository, initialized by `amplifier-memory init`. **Migration:** when the
   default does not exist and `~/.amplifier/memory` does, the older path is the
   default; `init` offers to move it, and says so.
```

### Change 2 — §2, Fixed layout (two files added, both explicitly not memory)

Current text — the tail of the layout block and the sentence under it:
````
   usage.jsonl        append-only reads/loads/citations log (§8)
   ```
   No other files are part of the contract. A file not listed here is not
   memory. `.lock` and `.gitignore` inside the store are plumbing, not
   memory.
````
Replacement:
````
   usage.jsonl        append-only reads/loads/citations log (§8)
   config.yaml        this instance's configuration (§11) — NOT memory
   sessions.jsonl     one line per session seen — NOT memory
   ```
   No other files are part of the contract. A file not listed here is not
   memory. `.lock`, `.gitignore`, `config.yaml` and `sessions.jsonl` inside the
   store are plumbing, not memory: never injected, never suggested, never cited.
   `config.yaml` holds what shipped as `~/.amplifier/memory-config.toml` —
   `[llm.judge]` becomes `llm: judge:`, plus `enabled: true|false` (§11); the
   `.toml` is retired. `sessions.jsonl` records `{session_id, origin,
   first_seen}`, appended by the session hook at start, read by the suggest job.
````

### Change 3 — §7, declined.md

Current text — §7's first three sentences; it continues "Declining is not forgetting…", unchanged:
```
7. **declined.md** is an append-only list of suggestion texts (with the date
   and a one-line reason if given) that the human rejected. It is fed back
   to the Phase 2 prompt and matched exactly by code so nothing declined is
   proposed again.
```
Replacement:
```
7. **declined.md** is an append-only list of declined suggestions, one per line:
   `- <YYYY-MM-DD> <text>  quote: "<quote>"` — the verbatim human quote after the
   text. Older two-field lines (`- <YYYY-MM-DD> <text>`) stay readable and keep
   working. It is fed back to the Phase 2 prompt and matched exactly by code on
   **text OR quote**, so a declined suggestion returning paraphrased is blocked.
```

### Change 4 — new §11, an inert instance

New text (nothing to replace):
```
11. **`enabled: false` makes the instance inert.** Nothing injects, no memory
    tool is offered, no skills are advertised, and no timer runs against it.
    `doctor` names the instance as disabled rather than reporting it healthy.
```

## The evidence

**The steward's own words, 2026-09-07, verbatim:**

- "giving the option for multiple memory stores/instances that can be pointed to via the
  AmplifierSession/modules config per app (or even project dir) should be permitted."
- "in the case of my amplifier-app-cli usage, I might point it to ~/.amplifier/memory and within that
  dir is the same stuff that is there today, but maybe also the config.yaml? Then I could also have a
  ~/.amplifier-agent/memory dir for those sessions. Or I could create a ~/.amplifier-memory dir and use it in multiple apps"
- "we _can_ still have a default (maybe in ~/.amplifier-memory) that works w/o specifying
  a location/instance"
- "I appreciate having a seperate/single ~/.amplifier/memory-config.toml (though we typically use .yaml)"

**A cost already paid.** The shipped knob sits at `~/.amplifier/memory-config.toml`, *beside*
the store rather than in it, only because §2 forbids a file inside it (`AGENTS.md:49-50`;
`tests/test_init_timer.py:108` pins the outside path; `store.py:461` resolves the one store).
A second app — amplifier-agent at `~/.amplifier-agent` — cannot have its own store today. The
first unattended timer night wrote 17 suggestions, a third from a worker session; nothing on
disk tells the suggest job whose sessions those were — that is what `sessions.jsonl` fixes.

**Declines, measured** (item `amplifier_bundle_memory-5eb`; 3 pilots, 210 calls, 7 models): every
model re-proposed a known declined line 0–30% of the time, with a paraphrased text and the same
verbatim quote. `declined.md` carries text + date only (`inbox.py:106`, `:707`) and `is_declined`
normalizes only the text (`:425-432`) — so a paraphrased return reaches the inbox.

## What does NOT change

Git-per-mutation and the `usage.jsonl` exception (§1). The caps — 200 MEMORY.md lines, 150 lines
per topic, 50 topics, 2,000 bytes per line — refused by the writer (§3–§5, R1, R2). The MEMORY.md
line shape and `m-NNN` id rules (§3). Topic files and pointer lines (§5). Provenance in git commits
(§6). `usage.jsonl`'s events, 90-day truncation, never-committed rule (§8). Two writers, one path,
the lock (§9). `inbox.md`'s shape and the 30-day expiry (suggestions.v1). Every existing store keeps
working: `~/.amplifier/memory` is still found, with or without `AMPLIFIER_MEMORY_HOME`.

## Steward's word

Answer in one word: **ratified** · **ratified with edits** · **declined** · **later**.

>
