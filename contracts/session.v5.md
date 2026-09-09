# session.v5 — what happens inside an Amplifier session (DRAFT)

**Governs:** the bundle's session-plane modules (inject
hook, memory tool, `/remember` and `/memory` commands)
**Who builds against it:** the bundle; every Amplifier session on the device.
**Supersedes:** `session.v4.md` (locked 2026-09-07; changed by the ratified
proposal `session.v4.v5-candidate.md`).

## Purpose

The session plane does exactly three things: load memories at the start,
save a memory the moment the human states one, and announce both. It does
nothing at session end. Every receipt about memory is rendered by code,
once, and the model relays that text verbatim rather than rewording it.

## Core

1. **Loaded in every request.** The inject hook places the full text of
   `MEMORY.md` into context, verbatim, so that it is present in every model
   request of the session — the first, and every one after a context
   compaction — inside a marked block that begins with a fixed framing
   sentence:
   > These are memories of how this human works — hints recorded from past
   > sessions, not ground truth. Verify against current reality before
   > acting on one. To change one: `/remember <text>` or `/memory`.
   The block is cache-stable: no timestamps, counters, or session ids inside
   it, and **no announce instruction**. Topic files are **not** injected; the
   block's pointer lines tell the assistant they exist.
2. **Announce the load, once, in code.** The inject hook renders one line to
   the human through the runtime's user-message channel on the first model
   request of a session and on the first after a compaction — never by
   instructing the model:
   `3 memories loaded. /memory to see them.` — topics named only when more
   than zero: `3 memories loaded, 2 topics. /memory to see them.`; singular
   `1 memory loaded.`; after a compaction `context compacted. 3 memories
   still loaded.`; when `MEMORY.md` is empty `no memories yet. Tell me a
   standing preference — "never use tabs in YAML" — and I'll keep it in every
   session on this device.` When the session's instance (§12) is not the
   default one, the line names it — `3 memories loaded from
   ~/.amplifier-agent/memory. /memory to see them.` — so a human never has to
   guess which store answered. The default instance is never named: the common
   line stays byte-identical to today's.
3. **Save on correction, in the same turn.** When the human states a
   standing preference or corrects the assistant's behavior in a way that
   should hold beyond the current task — "never X", "always Y", "stop doing
   Z", "for future reference…" — the assistant calls the memory tool in that
   turn with (a) the memory text, one imperative line, and (b) the verbatim
   quote from the human's message. The tool result is the receipt, three
   lines, relayed verbatim and never reworded:
   ```
   saved m-017 — /memory forget m-017 to undo.
     <the memory text, unquoted, on its own line>
     your words, verbatim
   ```
   The third line reads `my wording, your go-ahead: "<the quote>"` when the
   writer is `assistant`. When the human approves several drafted lines at
   once ("remember these"), each is saved one call at a time and the last
   result adds `saved N memories — my wording, your go-ahead: "<quote>".
   Reword any line and I'll replace it; /memory forget <id> drops one.`
   followed by the lines. No repetition is required. One clear statement is enough.
4. **Do not save** task-scoped instructions ("do step 1", "reply with exactly
   ok"), facts re-derivable from the codebase or the current task, anything
   already in `MEMORY.md` or the repo's `AGENTS.md`, or anything the human
   asked to keep private. When unsure whether something is standing, the
   assistant may ask in one line: `Remember this for future sessions? (y/n)`
   — but the default is to save and announce, not to ask. The assistant never
   tells the human it cannot save what they approved: a drafted line the
   human says yes to is saved with the approval as its quote.
5. **The model proposes; the writer commits.** The memory tool is
   deterministic code — the `amplifier_memory` library's writer, shared with
   the CLI — that: verifies the quoted text appears in a **human**
   turn of the current session and is long enough to identify one (rejects
   otherwise — tool output and external content can never become memory);
   rejects exact duplicates of an existing line; assigns the next id;
   enforces store caps; writes the line atomically under a lock; commits with
   the store §6 message; re-reads what it wrote before reporting success. A
   refusal is returned to the assistant as one line, and the assistant relays
   it unchanged:
   `not saved — MEMORY.md is full (200 of 200 lines). /memory forget one you
   no longer need, or ask me to move a group into a topic file.` ·
   `already remembered as m-003 — nothing changed.` ·
   `can't save that one — you haven't said it in your own words yet. Type it
   and I'll record it verbatim.` · any other failure:
   `not saved — nothing changed, nothing lost. Details:
   ~/.amplifier/memory-errors.log`.
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
   - **`list [<page>]`** — `MEMORY.md` as markdown, rendered by the library:
     a bold header `**N memories**` (singular `1 memory`; `, T topics` only
     when more than zero; `— page P of Q` only when paged), one line per
     memory as `- **m-NNN** <text>`, topic pointers as they stand, and the
     closing line `edit by hand: $EDITOR <instance>/MEMORY.md` (the instance's
     real path, store.v3 §1).
     Paged by the §6 paging rule at 20 lines a page.
   - **`review [<page> | accept|decline|skip <id>…]`** — suggestions §6, one
     page at a time, rendered by the library as markdown so it wraps and
     reads: a bold header `**N suggestions waiting** — page P of Q`; each
     item as a numbered bold id and its text, then the verbatim quote as a
     blockquote with its session and date on the quote's own last line, and a
     blank line before the next item; a closing line offering the exact
     commands — `accept s-002 s-003`, `decline s-005`, `skip s-004`, `next` —
     and the shell form. Several ids in one breath are several tool calls,
     in the order given, each producing its own §6 receipt; the receipts are
     relayed together. **Conversational review addressing:** after rendering a
     review page, the assistant may resolve a clear reference to that rendered
     page — `#1`, `first one`, or unambiguous quoted text — to its stable `s-NNN`
     id. Before its first mutation, it resolves the complete stated batch and
     freezes an action-to-id map; for example, on a rendered page containing
     `1. s-101` and `2. s-202`, `accept #1, decline #2` maps to `accept s-101`,
     then `decline s-202`. It executes those stable ids sequentially in the
     human's stated order and relays the receipts together. No extra
     confirmation is needed when both action and target are clear. If the
     assistant explicitly stated the complete action-to-id map immediately
     before, `yes` approves that map without retyping ids. An unknown, lost, or
     conflicting map receives one concise clarification question and no guessed
     target or mutation. A missing or stale stable id remains a missing-id
     refusal: the assistant does not reread and rebind that position, and never
     retargets remaining actions. Tool and shell commands still require stable
     `s-NNN` ids; `accept 2` there is refused with the ids on that page. With an
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
   **Paging.** Up to 8 items is one page. Above that the library divides
   into `ceil(n / 6)` pages of `ceil(n / pages)` items each, so no page
   holds fewer than one less than the others — 17 items are 6 · 6 · 5, 13
   are 5 · 4 · 4, 9 are 5 · 4, never 6 · 6 · 6 · 1. `<page>` selects one;
   `next` in conversation is the model asking for `<page> + 1`.
   Every rendering is relayed verbatim and never reworded: the overview and
   every receipt inside a fenced code block, because their `<id>` and
   `<text>` placeholders and their line breaks do not survive markdown
   outside one; `list` and `review` pages bare, because they are markdown
   and are meant to render as such. The writer
   applies §5's human-turn check to `remember` and `edit` like any
   other save. **Outside conversational review, ids are the only names:** tool
   and shell commands, and non-review `/memory edit` and `/memory forget`, use
   stable ids; a bare number `N` means `m-00N`, never a position in a list. A
   destructive command that cannot resolve its id asks (`no memory m-004 —
   forgotten 2026-09-06. Current: m-003, m-005. Say the id.`) and never guesses.
   Conversational review addressing is the narrow exception in this clause's
   `review` paragraph, and resolves only from the actual rendered page, not from
   the live positional inbox. An unknown first word answers with the
   `help` table. No receipt carries a commit sha, a phase name, a
   zero-valued count, or a `<placeholder>`.
7. **Recall is reading.** When a topic pointer is relevant, the assistant
   reads the topic file with ordinary file tools and says so in one line
   (`Recalled topics/yaml-style.md`). The read is logged to `usage.jsonl`.
   There is no search tool; `grep` over the directory is the search tool. A
   ruleset or anything longer than one line is saved to `topics/<slug>.md`
   plus one pointer line in `MEMORY.md`, never squeezed into a line.
8. **Cite at use, and count it.** When a memory changes what the assistant
   would otherwise have done, it says so inline (`going long here, per
   m-004`). The tool records each citation as a `cited` usage event (store
   §8) and `amplifier-memory status` shows the citation rate. The rate is a
   floor, never an estimate; this contract promises the instrument, not the
   rate. A wrong memory should die the first time it is used, not months
   later.
9. **Nothing at session end.** No hook runs on session end, no distillation,
   no summary, no flush. Exit cost from this bundle is zero by construction.
10. **Fail open, never block.** If the store is missing, unreadable, or the
    writer errors, the session proceeds unchanged; the failure is one line
    in the transcript and one line in `~/.amplifier/memory-errors.log`. A
    byte that does not decode is shown as U+FFFD and named by `doctor`; it
    never raises inside the hook or the tool.
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
12. **Which instance a session uses is configuration.** Both session-plane
    modules accept in their mount-plan `config:` block a key `home: <path>`
    naming the instance (store §1) they read and write; absent, the store
    contract's resolution order decides, so a session with no `home:` behaves
    exactly as today. Both honour that instance's `config.yaml` `enabled` key.
    When it is false the session plane is silent: the hook injects nothing and
    renders no line, the tool is not mounted — or, where a plan requires it to
    be, refuses every operation with one line, `memory is disabled for this
    instance (<path>: enabled: false).` — neither `/remember` nor `/memory` is
    advertised, and nothing is written. `amplifier-memory doctor` names an
    inert instance rather than reporting it healthy. Both keys are read at
    mount, from the plan the app supplies, so this works under any app.
13. **Which sessions have a human in them.** A session declares its origin at
    start through one environment variable any launcher can export,
    `AMPLIFIER_SESSION_ORIGIN`, one of `human` · `worker` · `recipe` · `agent`
    · `eval`. Unset means `human`. At session start the inject hook appends
    `{session_id, origin, first_seen}` to the instance's `sessions.jsonl`
    (store §2 plumbing — never injected, never suggested, never cited). For
    any origin other than `human`: the §1 block is still injected, because the
    memories still apply — the work is still this human's — BUT the tool
    refuses `save`, `edit` and `forget` exactly the way it refuses a sub-agent
    today (R2's one-line refusal, naming the origin), the suggestions line the
    hook renders beside §2's (suggestions.v2 §5) is not rendered, and the
    suggest job treats the session as having no human interlocutor: its turns
    are not mined for standing preferences. This is a convention, not a
    capability — any app, launcher, tmux wrapper or recipe honours it by
    exporting one variable, and a launcher that exports nothing is treated as
    human, exactly as today. An upstream ask stands for amplifier-app-cli to
    record the origin in `metadata.json` natively; the variable works without
    it.

## Reserved

- **R1 — save-vs-ask default.** v2 keeps save-and-announce (unanimous across
  the 2026-09-06 reviews: "a confirm is a preamble"). A config
  `confirm_saves: true` flips to ask first. Revisit if the owner is
  forgetting more than a few saves a week.
- **R2 — sub-agent sessions.** Sub-agents inherit the injected block (they
  work for the same human) but **never save**: only a root session with a
  human interlocutor may write. An orchestrator's brief is not the human's
  voice.
- **R3 — hints or instructions.** The framing sentence calls memories hints.
  Whether behavioural memories should be framed as instructions is decided by
  the citation data from §8, not before it.

## Explicitly backlogged

- Mid-session hot-load of topic files chosen by something other than the
  assistant's own judgment (VISION backlog).
- Path-scoped topic loading (`paths:` globs) — promote when topic files
  exceed 20 and relevance misses are documented.
- A deterministic `/memory` that costs no model round trip — blocked on the
  CLI's command registry being open to bundles; asked for, not depended on.

## Conformance

- Injected block is byte-identical across two sessions with the same
  `MEMORY.md` (cache-stability); contains the framing sentence; contains no
  topic bodies and no announce instruction.
- The announce line renders in a real PTY session exactly once on the first
  request and once after a compaction (device-checked), with the exact text of
  §2; a reply constraint on the human's turn does not suppress it.
- Every receipt in §3, §5 and §6 is byte-identical to a fixture and contains
  no commit sha, no phase name, no zero-valued count, no `<placeholder>`.
- Nothing the model is given asserts what the human can or cannot see of a
  tool call: the tool description, the skills, the bundle and behavior files
  and the module READMEs state the rule only as relay-verbatim-never-reword.
  Checked by grep for the presuming phrases (the ones Part A of
  `session.v2.v3-candidate.md` removed) across `modules/`, `skills/`,
  `behaviors/` and `bundle.md`; the kit excludes its own source.
- **In a real session:** human states an explicit correction → within that
  turn a save is announced, the line exists in `MEMORY.md`, the commit
  carries the verbatim quote (discriminating pair: a task-scoped instruction
  in the same session produces no save).
- Writer rejects a save whose quote is absent from any human turn or too
  short to identify one (poisoning arm); rejects an exact duplicate; refuses
  at the cap; refuses a text that is not one line.
- `/remember` and every `/memory` first word behave as §6; `edit` keeps the
  id and `why` shows `was:`/`now:`; `forget` of an unknown id is the §6
  one-line refusal naming the current ids; an unknown first word yields the
  `help` table.
- A full-conversation evaluation loads the actual memory skill, renders a real
  review page from a fresh synthetic store, then checks numbered batches, an
  immediately preceding action-to-id-map `yes`, ambiguous references, stale
  ids, page-local nonconsecutive ids, and unambiguous text references. It
  rejects reordered, duplicate, missing, wrong, or extra mutations; direct
  tool and shell position calls remain refused.
- Bare `/memory` is at most four lines, suggestions first, and every figure
  equals `amplifier-memory status` run in the same second. `/memory list`
  carries every line of the file, one `- **m-NNN**` bullet each, across its
  pages. A `review` page with 17 waiting is page 1 of 3 with 6 items, each
  item's quote byte-identical to `inbox.md`'s; `accept 2` is refused naming
  the page's ids; `accept s-002 s-003` produces two receipts. The paging
  rule's four worked examples (8 → 1 page; 9 → 5 · 4; 13 → 5 · 4 · 4;
  17 → 6 · 6 · 5) are asserted. Each `/memory` word costs the skill load,
  one tool call per page or per id, and one relay — never a model-rendered
  listing.
- With an empty inbox: bare `/memory` has no suggestions line and no
  `review` in its command line; `/memory review` says so in one line. With
  one item: the suggestions line is first and singular, and `review` appears.
- The injected total of §11 is measured (cl100k) and is ≤ 500 tokens;
  conformance prints the per-source breakdown.
- A `cited` event is written when the assistant names a memory at use;
  `status` prints the rate.
- Sub-agent session: block injected, save rejected.
- **Exit latency:** a 2-turn session's exit time with the bundle equals a
  control without it, within noise.
- Store unwritable: session output identical to control; one line in the
  error log.

## Changelog

- **2026-09-09 — v5 draft, ratified direction.** The steward's `ratified`
  after `session.v4.v5-candidate.md` permits this successor. Core 6 now has
  the narrow conversational review-addressing exception: clear references to
  an actual rendered page resolve once to frozen stable ids, and `yes`
  approves only an immediately preceding complete map. Tool, shell, and
  non-review stable-id requirements remain unchanged. This stays DRAFT until
  parent live verification and the freeze conditions are met; v4 stays locked
  as the record of earlier work.
- **2026-09-07 — amended in place (still FROZEN 2026-09-07).** The steward's word,
  "Let's fix those wrinkles.", on `session.v4-candidate.md`: §13's cross-reference
  now names suggestions.v2 §5 (the current version), and §6's `/memory` closing line
  names `<instance>/MEMORY.md` — the instance's real path (store.v3 §1) — instead of
  the pre-v3 fixed path. No clause's meaning changed.
- **2026-09-07 — v4 locked.** Ratified by the steward ("ratified",
  2026-09-07) from `session.v3.v4-candidate.md`:
  - New §12: which instance a session uses is configuration — both
    session-plane modules take `home:` from their mount-plan `config:` block
    and honour that instance's `enabled` key; with neither set, a session
    behaves exactly as it does today.
  - New §13: a session declares its origin at start through
    `AMPLIFIER_SESSION_ORIGIN` (`human · worker · recipe · agent · eval`;
    unset means `human`), appended to the instance's `sessions.jsonl`. A
    non-`human` origin still receives the §1 block but may not save, edit or
    forget, renders no suggestions line, and is not mined by the suggest job.
  - §2's load line names the session's instance when it is not the default
    one; the default is never named, so the common line stays byte-identical.
  Supersedes v3, which stays locked as the record of what earlier work was
  built against.
- **2026-09-07 — amended in place (still FROZEN 2026-09-07).** The steward's
  word, verbatim "ok, do it", recorded in `docs/workflow/OWNER-RETURN-LOG.md`
  (entry 2026-09-07, the second return of the afternoon). Applies
  `session.v3-candidate.md`: §6 `list` and `review` are markdown pages
  rendered by the library and driven by the model; the paging rule (≤ 8 one
  page, else `ceil(n/6)` pages of `ceil(n/pages)`); positions are never
  names; the fence is for the overview and receipts only. The Governs line
  names the two commands the bundle ships (it still read v2's four). Evidence:
  the steward's transcripts c798a817 (17 items as one wall; 2,476 output
  tokens to echo) and e3b15303 (the fenced overview, correct).
- **2026-09-07 — v3 locked (FROZEN 2026-09-07).** The steward's word,
  verbatim "ratified" (Part A earlier the same day: "Ratified, but before we
  start making our changes…"), is recorded in
  `docs/workflow/OWNER-RETURN-LOG.md` (entry 2026-09-07). Ratifies
  `session.v2.v3-candidate.md` Parts A and B: Purpose, §3 and §6 say
  relay-verbatim-never-reword and nothing about what the human can see; §1
  framing names `/remember` and `/memory`; §6 collapses four commands to two
  with first-word dispatch, a four-line overview with suggestions first,
  `list`, `help`; §11 caps the bundle's per-request injection at 500 tokens;
  conformance adds the presumption grep, the empty-vs-one-item inbox pair,
  and the token meter. One lock-time correction to the candidate's Change 4:
  the presumption grep scans the implementation, not `contracts/` — a check
  cannot scan the sentence that defines it. A `[suggestions] enabled` flag
  was drafted and withdrawn the same day; the inbox is the one truth.
  Evidence: the steward's transcript of 2026-09-07 (the `/memory` listing
  that reached nobody; the `/edit` collision; 1,011 fixed tokens measured
  against 147 of memories). Migration: `/edit` → `/memory edit`, `/forget` →
  `/memory forget`, old bare `/memory` → `/memory list`.
- **2026-09-06 — v2 locked (FROZEN 2026-09-06).** The steward's word,
  verbatim "lgtm, do it", is recorded in `docs/workflow/OWNER-RETURN-LOG.md`
  (entry 2026-09-06 20:55). Ratifies `session.v1.v2-candidate.md` as written:
  §2 rendered by the hook, not instructed; §3 three-line receipt with
  provenance; §5 refusals as exact one-liners; §6 adds `/edit`, receipts echo
  text, ids-only rule; §7 topic-file path; §8 measured, not promised; §10
  tolerant reads; R3 added. Evidence: the steward's transcript of 2026-09-06
  and the four reviews in `docs/workflow/reviews/`.
- 2026-09-06 — v1 locked; see `session.v1.md`.
