# Proposal: session.v2 → v3 (CANDIDATE)

**Changes:** `contracts/session.v2.md` (FROZEN 2026-09-06). Written 2026-09-07 by the
manager session from the steward's transcript of 2026-09-07 (this session). The original
stays the law until the steward's word lands below.

Two parts. **Part A** (changes 1–4) removes the presumption that the human can see a tool
result. **Part B** (changes 5–10) consolidates the four commands into two, gives `/memory`
an overview, and puts a ceiling on what this bundle injects into every model request. Part B
removes two top-level commands from §6's *"These are the only commands"*, so together they
are a **new version**, `session.v3.md`, with the migration note at the end. One sibling
proposal for the same lock: `store.v2-candidate.md` (wording only; no promise removed, so it
amends in place). A `[suggestions] enabled` config flag and matching `suggestions.v1` /
`cli.v2` amendments were drafted and **withdrawn** the same day — see Part B evidence.

---

## Part A — relay verbatim, never reword

### Change 1 — Purpose ¶ (lines 11–14)

Current text:

```
The session plane does exactly three things: load memories at the start,
save a memory the moment the human states one, and announce both. It does
nothing at session end. What the human reads about memory is rendered by
code, once, and is never restated by the model.
```

Replacement:

```
The session plane does exactly three things: load memories at the start,
save a memory the moment the human states one, and announce both. It does
nothing at session end. Every receipt about memory is rendered by code,
once, and the model relays that text verbatim rather than rewording it.
```

### Change 2 — §3, the save receipt (lines 45–46)

Current text:

```
   quote from the human's message. The tool result is the receipt, three
   lines, never restated by the model:
```

Replacement:

```
   quote from the human's message. The tool result is the receipt, three
   lines, relayed verbatim and never reworded:
```

### Change 3 — §6, `/memory` (line 92)

Current text:

```
   ~/.amplifier/memory/MEMORY.md`; the model does not restate it. These are
```

Replacement:

```
   ~/.amplifier/memory/MEMORY.md`; the model relays it verbatim and never
   rewords it. These are
```

(Superseded in full by Change 8 below; kept so Part A reads on its own.)

### Change 4 — Conformance, one added bullet (after line 153)

Insert:

```
- No clause, tool description, or skill asserts what the human can or cannot
  see of a tool call. The rule is stated only as "relay verbatim, never
  reword", checked by grep for the presuming phrases ("the human reads",
  "say nothing", "counted, not read") across `contracts/`, `modules/`,
  `skills/` and `conformance/`.
```

### Part A evidence (a cost paid, caught in the steward's own session)

- **2026-09-07, this session.** The steward ran `/memory`. `skills/memory/SKILL.md` step 2
  reads *"Say nothing. The tool's result **is** the listing the human reads"*, and the
  assistant obeyed: its entire reply was `The listing above is your memory store.` The
  steward could not see any listing. Their report: *"many hide the tool calls and
  intermediate responses and some show them collapsed and it's up to the user to scroll
  back and expand them."* The three-memory listing was rendered exactly, and delivered to
  nobody.
- **Silent in both directions.** Neither the tool nor the model learns whether a receipt
  was displayed. On a hiding client every §3, §5, §6 receipt lands in a channel the human
  never opens, and the transcript looks identical to a success.
- **Defeats the v1 → v2 fix rather than completing it.** v2 moved rendering into code so
  receipts would be byte-exact. Exactness without delivery is worse than v1, which at least
  had the model speak.
- **Puts §8 out of reach.** *"A wrong memory should die the first time it is used"* needs
  the human to see the receipt naming it. A receipt they never see kills nothing, and the
  citation rate keeps scoring it a success.

**Steward's word on Part A: ratified** — 2026-09-07, in conversation: "Ratified, but before
we start making our changes…".

---

## Part B — two commands, an overview, a token ceiling

### Change 5 — §1, the framing sentence (lines 22–25)

Current text:

```
   > These are memories of how this human works — hints recorded from past
   > sessions, not ground truth. Verify against current reality before
   > acting on one. To change one: `/forget <id>`, `/edit <id> <text>` or
   > `/remember <text>`.
```

Replacement:

```
   > These are memories of how this human works — hints recorded from past
   > sessions, not ground truth. Verify against current reality before
   > acting on one. To change one: `/remember <text>` or `/memory`.
```

### Change 6 — §3, the undo hint in the save receipt (lines 47 and 55)

Current text (line 47):

```
   saved m-017 — /forget m-017 to undo.
```

Replacement:

```
   saved m-017 — /memory forget m-017 to undo.
```

Current text (line 55):

```
   Reword any line and I'll replace it; /forget <id> drops one.` followed by
```

Replacement:

```
   Reword any line and I'll replace it; /memory forget <id> drops one.`
   followed by
```

### Change 7 — §5, the cap refusal (lines 76–77)

Current text:

```
   `not saved — MEMORY.md is full (200 of 200 lines). /forget one you no
   longer need, or ask me to move a group into a topic file.` ·
```

Replacement:

```
   `not saved — MEMORY.md is full (200 of 200 lines). /memory forget one you
   no longer need, or ask me to move a group into a topic file.` ·
```

### Change 8 — §6, Commands, the whole clause (lines 83–99)

Current text:

```
6. **Commands.** **`/remember <text>`** writes exactly what the human typed
   (the quote is the text itself). **`/edit <id> <text>`** replaces one
   memory's text keeping its id; the commit carries the old text (`was:`)
   and the new; the receipt is `edited m-004 — was: "<old>"` then
   `  now: <new>`. **`/forget <id>`** removes the line and commits; the
   receipt is `forgot m-002 — still in git: amplifier-memory why m-002` then
   the removed text on its own line. **`/memory`** renders `MEMORY.md` with
   ids, `-` bullets, `N memories` (singular `1 memory`), topics named only
   when more than zero, and the line `edit by hand: $EDITOR
   ~/.amplifier/memory/MEMORY.md`; the model does not restate it. These are
   the only commands; they are user-invocable skills shipped by the bundle,
   and the writer applies §5's human-turn check to them like any other save.
   **Ids are the only names:** a bare number `N` means `m-00N`, never a
   position in a list; a destructive command that cannot resolve its id asks
   (`no memory m-004 — forgotten 2026-09-06. Current: m-003, m-005. Say the
   id.`) and never guesses. No receipt carries a commit sha, a phase name, a
   zero-valued count, or a `<placeholder>`.
```

Replacement:

```
6. **Commands.** Two, and only two, user-invocable skills ship with the
   bundle. **`/remember <text>`** writes exactly what the human typed (the
   quote is the text itself). **`/memory`** is everything else, by its first
   word:
   - **bare** — the overview, four lines at most, rendered by the library
     from the same figures as `amplifier-memory status` (cli §2):
     `34 suggestions waiting. /memory review to walk them.` (singular
     `1 suggestion`; the line is absent when the inbox is empty) · `4
     memories, 0 topics. /memory list to see them.` (singular `1 memory`;
     `, N topics` only when more than zero) · `last 7 days: 6 written, 1
     forgotten, 2 cited.` (a zero-valued term is dropped; the line is absent
     when all three are) · `/memory list · review · forget <id> · edit <id>
     <text> · help` (`review` present only while suggestions are waiting).
     The inbox is the one truth for everything suggestion-shaped; there is
     no separate on/off switch. To stop suggestions arriving, `amplifier-memory
     service uninstall` (cli §6); to start them, `service install`.
   - **`list`** — `MEMORY.md` with ids, `-` bullets, `N memories` (singular
     `1 memory`), topics named only when more than zero, and the line `edit
     by hand: $EDITOR ~/.amplifier/memory/MEMORY.md`.
   - **`review [accept|decline|skip <id>]`** — suggestions §6. With an
     empty inbox it says so in one line.
   - **`forget <id>`** — removes the line and commits; the receipt is
     `forgot m-002 — still in git: amplifier-memory why m-002` then the
     removed text on its own line.
   - **`edit <id> <text>`** — replaces one memory's text keeping its id; the
     commit carries the old text (`was:`) and the new; the receipt is
     `edited m-004 — was: "<old>"` then `  now: <new>`.
   - **`remember <text>`** — the same as `/remember <text>`.
   - **`help`** — the command table above and one paragraph on how memory
     works: what is loaded, when the assistant saves, where the store lives,
     and that a ruleset longer than a line goes to a topic file.
   Every rendering is relayed verbatim and never reworded. The writer
   applies §5's human-turn check to `remember` and `edit` like any other
   save. **Ids are the only names:** a bare number `N` means `m-00N`, never
   a position in a list; a destructive command that cannot resolve its id
   asks (`no memory m-004 — forgotten 2026-09-06. Current: m-003, m-005.
   Say the id.`) and never guesses. An unknown first word answers with the
   `help` table. No receipt carries a commit sha, a phase name, a
   zero-valued count, or a `<placeholder>`.
```

### Change 9 — new Core clause 11, the injection ceiling (after line 119, before `## Reserved`)

Insert:

```
11. **What this bundle injects into every model request is bounded.** The
    memory tool's description and parameter text, the two skills' names and
    descriptions, and §1's framing sentence together total **at most 500
    tokens** (cl100k), measured by conformance; the `MEMORY.md` body is the
    product and is not counted. The tool description teaches only what the
    model needs on every turn — when to save, when not to, one call at a
    time, the verbatim quote, relay-never-reword, relay refusals. Slash
    commands, review, batches and topic files are taught by the skills and by
    `/memory help`, loaded on demand. The tool's `review` operation is one
    word in the enum and one clause of parameter text; the review procedure
    lives in the skill.
```

### Change 10 — Conformance, the command bullets (lines 161–164)

Current text:

```
- `/remember`, `/edit`, `/forget`, `/memory` behave as §6; `/edit` keeps the
  id and `why` shows `was:`/`now:`; `/forget` of an unknown id is the §6
  one-line refusal naming the current ids.
- `/memory` costs one model round trip and the listing shown equals the file.
```

Replacement:

```
- `/remember` and every `/memory` first word behave as §6; `edit` keeps the
  id and `why` shows `was:`/`now:`; `forget` of an unknown id is the §6
  one-line refusal naming the current ids; an unknown first word yields the
  `help` table.
- Bare `/memory` is at most four lines, suggestions first, and every figure
  equals `amplifier-memory status` run in the same second; `/memory list`
  equals the file. Each costs one model round trip.
- With an empty inbox: bare `/memory` has no suggestions line and no
  `review` in its command line; `/memory review` says so in one line. With
  one item: the suggestions line is first and singular, and `review` appears.
- The injected total of §11 is measured (cl100k) and is ≤ 500 tokens;
  conformance prints the per-source breakdown.
```

### Part B evidence (costs paid, measured 2026-09-07)

- **Command collision.** The steward's own slash list this session: `/code-review`,
  `/mass-change`, `/session-debug`, `/council`, `/edit`, `/forget`, `/memory`, `/remember`.
  Four of thirteen belong to this bundle, and `/edit` beside `/code-review` reads as "edit
  a file". Steward: *"is /edit for editing files?"* and *"only create as many as we want
  users to have to remember."*
- **Undefined surface.** §6 defines two forms of `/memory` (bare, `review`). `/memory forget
  m-3` today has no rule; the skill would improvise.
- **Reviews go unreviewed.** `amplifier-memory status`, 2026-09-07: **34 pending**. A
  listing-first `/memory` never shows them. Steward: *"since we want to encourage the
  reviewing of memories, please put those first."*
- **Token cost, measured with tiktoken cl100k against the shipped bundle:** tool
  `DESCRIPTION` 576 · tool `INPUT_SCHEMA` text 232 · four skill lines 150 · framing
  sentence 53 = **1,011 tokens of fixed overhead on every request**, against 147 tokens of
  actual memories. The description spends ~60 of those teaching topic files; the steward's
  `topics/` directory holds 0 files. Steward: *"minimize the # of tokens needed for any of
  the things always injected."*
- **Two truths would drift — the flag was drafted and withdrawn.** A `[suggestions]
  enabled` config key (default on, with `suggestions.v1` §11 and `cli.v2` amendments) was
  written 2026-09-07 and withdrawn the same hour. `service install` / `uninstall` already
  exist (cli §6); `inbox.md` already gates the waiting line (suggestions §5) and `review`
  (cli §4); a key that must be kept in step with the timer's installed state is a second
  source of truth, the kind AGENTS.md non-negotiable 1 exists to refuse. Steward: *"just
  let the presence of suggestions be the one truth here."* What the flag would have bought
  — hiding `review` from the tool schema — is worth ~5 tokens once the description diet
  lands, and the skill teaches `review` only when asked.

### What does NOT change in Part B

- **§2**, the announce line and its channel — untouched (suggestions §5's second line is
  gated by the new flag, but its text is the same).
- **§3–§5** save semantics, the writer, the human-turn check; **§7** recall is reading — the
  topic-file mechanism stays exactly as store §3/§4 define it, it merely leaves the
  always-on tool description; **§8–§10**; **R1–R3**.
- **`/remember <text>`** — same name, same receipt.
- **`/memory review`** — same keystrokes, same receipts (suggestions §6).
- **The `list` rendering** — byte-identical to today's bare `/memory`.
- **The tool's six operations** in the library, `review` included.
- **`suggestions.v1` and `cli.v2`** — untouched. No new module, hook, resident process, or
  config key.

### Migration note (this is a new version)

Everyone who typed `/edit <id> <text>` types `/memory edit <id> <text>`; `/forget <id>` is
`/memory forget <id>`; the old bare `/memory` is `/memory list`. Receipts that named
`/forget` now name `/memory forget`. `hooks-memory-inject`'s framing sentence changes once,
costing one prompt-cache miss per session on the first request after upgrade. Nothing on
disk changes; store.v2 is amended for wording only.

---

## Downstream edits this unlocks (code, after ratification)

| File | Change |
|---|---|
| `contracts/session.v3.md` | this proposal applied; v2 stays as history |
| `modules/tool-memory/…/__init__.py` | `DESCRIPTION` cut to the §11 core (~220 tok); schema text deduplicated (~110); new `overview` operation |
| `src/amplifier_memory/` | `overview()` rendered from the same figures `status` reads |
| `modules/hooks-memory-inject/…/__init__.py:76` | framing sentence (Change 5) |
| `skills/memory/SKILL.md`, `skills/remember/SKILL.md` | two skills; `edit/` and `forget/` removed; first-word dispatch; `help` body |
| `bundle.md`, `behaviors/memory-session.yaml`, READMEs | two commands registered; tables retconned as always-true |
| tests + `conformance/session/**` | fixtures for the new receipts; empty-vs-one-item inbox pair; the token meter with per-source breakdown |

## Steward's word on Part B

**ratified** — 2026-09-07, in conversation, the single word "ratified", after the
`[suggestions]` flag was withdrawn at the steward's own suggestion ("let the presence of
suggestions be the one truth"). Locked as `contracts/session.v3.md`.
