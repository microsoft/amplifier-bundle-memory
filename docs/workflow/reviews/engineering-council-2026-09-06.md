# Engineering Council — the engineering shape of `amplifier-bundle-memory`

**Target:** the code, the modules, the contracts, and the mechanisms — judged against the UX
findings after the first real day.
**Evidence:** `.converge/feedback/2026-09-06-kicked-the-tires-transcript.md` ·
`docs/workflow/UX-REVIEW-BRIEF-2026-09-06.md` · `docs/workflow/reviews/design-council-2026-09-06.md` ·
the locked contracts · the source at `69827f4` · the installed Amplifier CLI, core, and
`loop-streaming` orchestrator · the steward's live store.
**Method:** six orthogonal lenses, cold isolated fan-out (Round 1), full uncurated
cross-examination (Rounds 2 and 3), synthesis with recorded dissent.
**Date:** 2026-09-06. **Read-only review.** This file is the only artifact written.
**Out of scope by instruction:** the concurrency corruption fixed in wave 4. Not re-litigated.

---

## ROSTER MANIFEST

| Lens | R1 | R2 | R3 | Moved |
|---|---|---|---|---|
| intent-keeper | CONCERN | CONCERN *(trip-wire named)* | **FAIL** | ✔ changed |
| cranky-old-sam | CONCERN | CONCERN | **FAIL** | ✔ changed |
| crusty-old-engineer | CONCERN | **FAIL** | FAIL | ✔ changed |
| restless-old-brian | CONCERN | **FAIL** | FAIL | ✔ changed |
| user-advocate | **FAIL** | FAIL *(re-based)* | not re-convened | — |
| tester-breaker | **FAIL** | FAIL | not re-convened | — |

**Consulted: all six.** Both conditional lenses were included, with reasons:
- **user-advocate — INCLUDED.** The target has a user surface (three slash commands, a CLI, a
  named human steward whose transcript is the evidence).
- **tester-breaker — INCLUDED.** The target is a runnable repo with a writer that owns data the
  human cannot reconstruct.

**UNAVAILABLE: none. ERRORED: none. N/A (abstention): none.**

**Method deviation, disclosed:** Round 3 was run with four lenses, not six. `user-advocate` and
`tester-breaker` held FAIL in Round 2 and every position they took was adopted or explicitly
ruled on by the four who were re-convened; they were not re-polled. Their Round 2 words are
quoted below as their final positions. No lens was dropped from the record.

## PANEL VERDICT: **FAIL — unanimous, 6 of 6.**

Four verdict changes across three rounds, **every one of them downward, and every one of them on
evidence the changing lens went and produced itself.** Nobody moved on headcount, and two lenses
said so explicitly while moving.

> **crusty-old-engineer:** *"I said in Round 1 that the write path was the most trustworthy thing
> in the repo. Then I typed one character the human never sees and watched it write a corrupt file
> to disk while telling me it hadn't written anything. I was wrong, and I was wrong in the specific
> way that matters: I graded the machinery by the care that went into it instead of by what it does
> when the input isn't the one in the docstring."*

> **restless-old-brian:** *"I checked that the fix was **installed**. tester-breaker checked whether
> it **holds**. Those are different questions, and mine was the easier one. I verified a `grep -c`
> and called it proof — that is the code confirming the code, wearing my badge."*

> **cranky-old-sam:** *"I vouched for the verify-after-commit code because it had a scar. It turns
> out it was watching the committed tree while the hook fed the model from the working tree. When
> the one component I defended is pointed at the wrong file, I don't get to stay at CONCERN."*

> **intent-keeper:** *"I set my own trip-wire on the wrong variable. I made it a matter of days when
> it was always a matter of state — and the state was frozen into the vision before a line of code
> was written."*

---

# PART 1 — THE HEADLINE

## Three lenses, three routes, one root: **the code confirming the code**

This is the finding that subsumes the others, and it was reached independently by
`tester-breaker` (from breakage), `restless-old-brian` (from verification), and `intent-keeper`
(from goal-tracing) before any of them saw the others' work.

> **tester-breaker (F21):** *"Every assertion in this repo is made one layer inside where the bug
> lives. The team verifies the layer it controls and the bugs are all one layer out — in the
> terminal, in the working tree, in the argv, in the byte encoding."*

Four instances, each independently verified:

1. **A rendering fix was proven by asserting a source constant.** `ANNOUNCE_EMPTY` gained its
   backticks in `818ddbb`; wave 4's stated proof was `conformance/session/inject/run.py` printing
   *"both variants are correct (yes)"*. **All six smoke evidence files still show the broken
   render** — `session-A0-empty-announce.txt:22`, `session-B-correction.txt:9`,
   `session-A-task-scoped.txt:11`, `correction-alone-control.txt:8`,
   `pair-in-one-turn-run1.txt:11`, `pair-in-one-turn-run2.txt:10`. Evidence dir last touched
   `36c27b1`, before the fix. **The first line this product ever shows a human has never been
   rendered on a real terminal since it was fixed.**
2. **The safety net and the load path read different files.** `_assert_saved` verifies
   `git show HEAD:<target>` (`store.py:888-910`). The inject hook reads the working tree
   (`hooks-memory-inject/…/__init__.py:193`). Reproduced by `crusty-old-engineer`: committed tree
   clean and empty, working tree corrupt, and the hook would have injected the corrupt line into
   every request of that session.
3. **The argv is verified from a docstring.** `_git.py:68` passes the whole commit message as
   `-m <argv>`; nothing tests it against `MAX_ARG_STRLEN`.
4. **The encoding is never tested against a byte.** `grep -rl "u2028|surrogate|UnicodeDecode|latin-1|errors="`
   across `tests/`, `conformance/`, and both module suites returns **nothing**.

`intent-keeper` traced the same root upstream, to before any code existed:

> *"The substitution is not in the code — it is in the frozen vision, in two consecutive sentences.
> `VISION.md:60-62`: 'Only the human's own words become memory' is the goal. 'Code checks the quote
> exists' is the stand-in. Both were written on the same day, locked side by side, and every builder
> downstream read the first and correctly built the second. **You cannot test your way to a guarantee
> your contract never made.**"*

---

# PART 2 — UNRESOLVED BLOCKERS

Surfaced at the top and not downgraded. Every one was **reproduced by execution**, not read.

## B1 · The writer writes corruption to disk, reports that it did not write, and publishes it

`store.py:811` rejects only `"\n"`. `str.splitlines()` splits on eight more characters.
`store.py:864` writes with no temp file and no rollback. `store.py:867-869` then raises
`WriteNotLanded` **after** the write.

Reproduced independently by `tester-breaker`, `crusty-old-engineer`, and `restless-old-brian`
against the **installed** library at `~/.local/share/uv/tools/amplifier-memory/`:

```
RAISED: WriteNotLanded — write to MEMORY.md did not land; refusing to commit
FILE ON DISK: b'- [m-001] never use tabs\xe2\x80\xa8always two-space\n'   <-- IT LANDED
COMMITTED:    b''
SUBSEQUENT SAVE -> StoreMalformed: refused … 1 malformed line(s)          <-- WEDGED
```

`restless-old-brian` established that this is worse than stranded corruption:

> *"The malformed line is left in the **working tree**, which is exactly what
> `hooks-memory-inject/__init__.py:190` reads on every `provider:request`. So a save reported as
> 'did not land' is fed to the model as a memory on the very next request, indefinitely.
> **Corruption with a delivery mechanism is worse than corruption.**"*

> **tester-breaker:** *"That is the steward's day-one bug wearing a clean shirt."*

**`os.replace`, `NamedTemporaryFile`, and `tempfile` appear ZERO times in `src/` or either module
tree** (`crusty-old-engineer`, verified by grep).

> **crusty-old-engineer:** *"`os.replace` appears zero times in a tool whose entire job is custody
> of data the human cannot reconstruct. That is not a missing optimisation. That is the difference
> between a program that stores things and a program that intends to."*

## B2 · One accented byte kills six functions, including the designated remedy

`store.py:464` and `store.py:533` call `read_text(encoding="utf-8")` with no `errors=`.
`cli.py:19-22` catches only `MemoryError`; `UnicodeDecodeError` is not one.

Reproduced, six for six: `save` · `verify_store` · `repair_store` · `doctor` · `list_memories` ·
`status`.

> **restless-old-brian:** *"`José`. A name. Not a fuzzing artifact — a colleague. One accented byte
> in a hand-edited `MEMORY.md` — which `store.v1` Core 9 **explicitly invites** — and six functions
> die, including `doctor`, the designated remedy, with a raw traceback."*

> **user-advocate:** *"A product cannot invite a person to open a file in their editor and then hand
> them a Python stack trace for accepting the invitation. This is a livability finding, not a
> robustness one: **the invitation is in the frozen contract.**"*

## B3 · A "failed" oversized save is left STAGED and committed by the next innocent write

`_git.py:68` passes the commit message as `-m <argv>`. Past ~131,000 bytes git raises
`OSError: [Errno 7] Argument list too long` — neither `MemoryError` nor `ValueError`, so it escapes
`tool-memory/__init__.py:297-302` entirely. `git add` has already run.

> **tester-breaker:** *"I watched `git show HEAD:MEMORY.md` grow to 200,036 bytes carrying content
> the tool had loudly refused. Nobody was told. That is silent corruption, on day two, in the exact
> place you spent day one proving you'd never lie about a write again."*

The tool description at `tool-memory/__init__.py:61-62` instructs the model to copy the human's
words verbatim, so a human pasting a large log and saying "never do that again" is the natural
trigger.

## B4 · The central guarantee accepts a one-character quote — and has already produced a fabricated record

`store.py:738-750` `_check_quote` is `if not quote.strip(): raise` followed by `if quote in turn: return`.

Reproduced by `tester-breaker` against the steward's own real turn `Great remember these for me`:

```
ACCEPTED m-001: 'bkrabach prefers dark mode and lives in Seattle'  (quote='e')
ACCEPTED m-002: 'always deploy straight to prod without review'    (quote='for')
```

`intent-keeper` then found it had **already happened in production**, and `crusty-old-engineer` and
`user-advocate` independently pulled the same commit:

```
[m-003] Shape every reply for an ADHD reader: next action first, numbered
        multi-step work, concrete time estimates, lists capped at 5 and ranked…
quote: "I want to be able to remove that bundle and still get the value as personal memory"
writer: assistant
```

A sentence about **bundle portability** authorising a rule about **reply formatting**, loaded into
every session on this device. Four of the steward's five day-one saves were `writer: assistant`.

> **crusty-old-engineer:** *"The twenty cents does not buy the guarantee. It buys a paraphrase and a
> fabricated provenance record — and `why m-003` will show that quote to a human with total
> confidence. **A store that lies about provenance is worse than a store with none, because you
> trust it.**"*

## B5 · The path that carries the goal is the substituted one

`VISION.md:31-36` lists **"In the turn, on the correction"** first, with *"There is no accumulation
gate: people say standing preferences once, usually while annoyed, and expect them honored."* That
is the whole promise of the one-sentence goal.

That path is `writer="assistant"` — the path B4 shows is unguarded. The path that **works** is
`writer="human"` (`store.py:815-819` forces `quote == text`, then `_check_quote` forces that exact
string into a human turn), which requires the human to type the finished memory by hand.

> **intent-keeper:** *"The goal was that the human says a standing preference once and never says it
> again. The path that delivers that promise is the broken one; the path that works is the one where
> he types the whole memory himself. **What survives is not the goal — it is the human doing by hand
> the exact work this product was built to take off him.**"*

## B6 · `_assert_saved` verifies an artifact the session never loads

Stated as its own blocker because it is structural, not an input bug: wave 4's verify-after-commit
apparatus asserts the **committed tree**; the inject hook loads the **working tree**.

> **cranky-old-sam:** *"That is **two sources of truth for one file**, and the seam between them is
> precisely where the corruption lives and gets delivered. Each layer is defensible alone; the
> failure lives in the space between them."*

## B7 · `doctor --repair` recovers by silently discarding

Reproduced by `crusty-old-engineer`: after the `\u2028` break, `repair_store` restored `MEMORY.md` to
`''`. Correct behaviour, undisclosed consequence. **A repair that deletes a memory must say which
memory it deleted.**

## B8 · The inject hook has no sub-agent gate at all

`grep parent_id modules/hooks-memory-inject/` returns **nothing** (`tester-breaker`, F19). The tool
beside it gates writes on `parent_id` (`tool-memory/__init__.py:260-265`); the hook gates nothing.
Every sub-agent mounts, sets `_load_logged`, and makes a git commit. This is the mechanical cause of
**92 distinct session ids** recorded in `usage.jsonl` for one human's afternoon.

Related, and worse: `_is_sub_agent` does `except Exception: return False`.

> **crusty-old-engineer:** *"That is a fail-**open** on an authorisation question, in a module that
> otherwise fails open correctly on availability questions. Confusing 'the store is unreadable,
> proceed' with 'I can't tell if I'm allowed, proceed' is a category error."*

---

# PART 3 — THE FIVE QUESTIONS

---

## Q1 — Can the load announce, the receipts, and the `/memory` listing be rendered deterministically?

### **YES. All three. Unanimous, 6–0. The design council's blocking question is answered.**

The design council (`design-council-2026-09-06.md`, PART 2 and PART 6) split 1 YES / 2 NO /
1 UNMEASURED on *"can a deterministic hook render to the human at all?"* and blocked two open items
on it. **The answer is yes, the mechanism is public, and this bundle already ships it — wired to the
one line the human hopes never to see.**

### The mechanism, traced end to end

`HookResult.user_message` — field at `CORE/models.py:286-299`, with `user_message_level` and
`user_message_source`. The kernel dispatches it at
`KSRC/bindings/python/src/coordinator/hook_dispatch.rs:282-313`, and the comment there is decisive:

> *"Fires on `result.user_message` FIELD being truthy, **NOT on action field**."*

Guarded only by `if action != "ask_user"`. So a single `HookResult` can carry `action="inject_context"`
**and** print a line. It calls `display_system.show_message(msg, level, f"hook:{source}")`, rendered
at `CLI/ui/display.py:98-128`:

```
[memory] Loaded 2 memories (0 topics available).
```

`[memory]` in cyan (SGR 36), body in default colour. **Rendered with Rich markup, NOT
`rich.markdown.Markdown`** — which means `<text>` survives, and the backtick workaround at
`hooks-memory-inject/__init__.py:59-67` becomes dead code.

### The event whitelist — the fact the design council was missing

`show_message` fires only where the orchestrator calls `coordinator.process_hook_result(...)`.
Verified by grep across all cached modules; that is exactly:

| Event | Call site |
|---|---|
| `prompt:submit` | `LOOP:2894-2902` |
| `provider:request` (turn start) | `LOOP:2996-3005` |
| `provider:request` (in-loop) | `LOOP:3204-3212` |
| `tool:pre` | `LOOP:4322`, `:4496` |
| `tool:post` | `LOOP:4414`, `:4571` |
| goal judge / summary / evaluator | `LOOP:2393`, `:2642`, `:2814` |

A `user_message` on `session:start`, `mode:activated`, or `orchestrator:complete` is **never
displayed** — which is very likely why an earlier lane concluded the mechanism did not exist.

### The bundle already uses it — for failures only

`modules/hooks-memory-inject/amplifier_module_hooks_memory_inject/__init__.py:227-235` returns
`HookResult(action="continue", user_message="amplifier-memory: memories not loaded (…)",
user_message_level="warning")`, registered on `provider:request` (`:181-187`) — a whitelisted event.

> **cranky-old-sam:** *"You already have the mechanism. It is in your own file, on the right event,
> and you use it only to apologise."*

> **user-advocate:** *"The one channel that always tells him the truth is wired up exclusively to bad
> news."*

### What to do, by surface

| Surface | Mechanism | Cost |
|---|---|---|
| **Load announce** | `user_message=` added to the existing `HookResult` at `__init__.py:207-212`, gated on the existing `self._load_logged` flag (`:178, 200-201`) | one field; **deletes** `ANNOUNCE_PREFIX`, `ANNOUNCE_EMPTY`, `announce_instruction()` (`:58, 67, 127-134`) |
| **Save / forget receipts** | a `tool:post` handler filtered to `tool_name == "memory"`, rendering from the tool's own `ToolResult`, which already contains the contracted sentence verbatim (`tool-memory/__init__.py:51-52, 340`) | ~20 lines |
| **`/memory` listing** | `prompt:submit` deny + `user_message` — see Q2 | ~15 lines + a drift assert |

### The side effect that matters most

Moving the count **out** of the injected block makes `session.v1 §1`'s byte-identity requirement
true by construction — which retires the mid-session re-fire the steward saw, and dissolves the
`§1`/`§2` contradiction the design council named as B8. **One field on one `HookResult` retires the
re-fire bug, the swallowed `<text>` placeholder, and a contract self-contradiction.**

### Standing conditions the council attaches — all six lenses, none optional

1. **Escape Rich markup.** `display.py:122/125` interpolates the message **unescaped**. The
   `MarkupError` wrapper at `CLI/console.py:93-107` catches *malformed* markup only.
   `user-advocate` verified the case that matters: *"`[red]` is **valid** markup, raises nothing,
   and gets silently consumed. A receipt that shows him something different from what was saved, in
   the one place whose entire job is telling him the truth about what was saved. That is worse than
   the crash."* `escape_markup` already exists at `CLI/utils/error_format.py:69` and is unused on
   this path.
2. **Pre-flatten.** `display.py:127` silently drops blank lines. A receipt designed with breathing
   room arrives without it.
3. **It is not universal.** `process_hook_result` appears only in `loop-streaming`. A delegated
   sub-session under another orchestrator renders **nothing**, with no error.
4. **It is a different visual channel** — no `Amplifier:` label, no leading blank line, above the
   assistant's prose, in the same lane as tool chatter.

### The cost `user-advocate` named while still recommending it — recorded, not resolved

> *"**The save receipt is the entire consent mechanism of this product — VISION principle 1 says
> awareness is him seeing the save happen — and I am recommending you move it into the channel a
> person learns to ignore.** I still recommend it, for one reason: a boring line that is *always
> there* beats a prose sentence that showed up two times out of three. He can learn to glance at a
> fixed position. He cannot learn to trust a model's discretion."*

### The argument that reframes it, from `tester-breaker`

> *"`user_message` doesn't just make the announce reliable, it **moves the assertion to the layer the
> bug is in.** You can pty-capture rendered output and diff it. You cannot pty-capture a model's
> willingness. The reason to take the mechanism is not fewer tokens — it's that it's the only version
> of this behaviour you can point a probe at."*

---

## Q2 — The cheapest reliable path for the three slash commands

### **Split by direction. Reads go deterministic; writes stay on the model. 6–0 after two reversals.**

This was the panel's sharpest conflict — 3-for / 3-against at the end of Round 1 — and it resolved
completely, because **its own author withdrew it and two more lenses followed.**

### The measured facts

`/memory` is not in `COMMANDS` (the hardcoded 17-entry table, `CLI/main.py:528-587`), and not in
`MODE_SHORTCUTS`, so it falls to `SKILL_SHORTCUTS` (`:816-817`). `_load_skill` makes **no LLM call
and does not read `SKILL.md`** — two dict lookups (`:3163, 3171`) returning
`(True, 'Use the load_skill tool to load the skill "memory".')` (`:3194-3195`). That synthetic
sentence goes to the model, which then calls `load_skill` (RT1), reads the skill body, calls
`memory(list)` (RT2), and restates the list (RT3). Transcript L421-469: **3 LLM calls, $0.20, ~7.2 s
to `cat` three lines.**

`prompt:submit` deny is a genuine zero-token short-circuit (`LOOP:2894-2902`) — `execution:start`
(2923), `_select_provider` (2936), `PROVIDER_RESOLVE` (2968), `PROVIDER_REQUEST` (2995/3205) and
every `provider.complete/stream` (3584/4138) are past the `return`.

### The full option table, as the panel ruled it

| Option | Ruling |
|---|---|
| **`prompt:submit` deny** | **ADOPT — for `/memory` only.** Zero tokens. `"Operation denied: "` is welded into the f-string at `LOOP:2901`; no flag suppresses it. `Processing…` still prints (`main.py:4049`); the `💰 Turn: $0.00` footer still prints (`LOOP:1656-1657`); the token-usage block does not. |
| **`user_message` on a whitelisted event** | **ADOPT — for the announce and both receipts.** Public field, already depended on, no new coupling. |
| **Mode-shortcut** | **REJECT, and document as a landmine.** It is the only genuinely zero-model local-print registry (`main.py:784-795, 1042-1047, 4057-4062`), but the printed text is fixed frontmatter, so it structurally cannot carry live store contents — *and* `MODE_SHORTCUTS` is checked at `:784` **before** `SKILL_SHORTCUTS` at `:816`, so shipping `modes/memory.md` would **shadow the `/memory` skill entirely**. |
| **A CLI verb in another pane** | **REJECT as the primary path; ADOPT as the signpost.** `user-advocate`: *"Asking him to leave the conversation to inspect the subject of the conversation is a downgrade."* But `cat ~/.amplifier/memory/MEMORY.md` is instant, free, complete at 200 lines — and VISION principle 7 promises "inspectable by `cat`" while advertising it **nowhere**. Put it in the `/memory` output. |
| **Ask the CLI team for a registry** | **ADOPT, in parallel, today.** `COMMANDS` is a hardcoded literal; two bundles already want the same thing. The deny path is a workaround with an expiry, and workarounds nobody is trying to retire become architecture. |

### Why `/remember` and `/forget` stay on the model path

**`intent-keeper` proposed the deterministic write path in Round 1 and withdrew it in Round 2**,
having checked the mechanism it had asserted:

> *"I withdraw because crusty's counter is right and my round-1 argument was factually **wrong**,
> not merely outweighed. `skills/remember/SKILL.md` passes `writer="human"`, and `store.py:815-819`
> then refuses unless `quote == text`, after which `_check_quote` refuses unless that exact string
> appears verbatim in a human turn. **A model paraphrase of `/remember` text cannot survive both
> checks — it gets refused. The $0.20 I wanted to save was buying the one check I claimed it was
> destroying. I had the mechanism backwards.**"*

`crusty-old-engineer` ran the three-way probe in Round 3 and confirmed it:

```
A: paraphrase of /remember text, writer=human      -> REFUSED (QuoteNotHuman)
B: verbatim text,               writer=human      -> SAVED m-001
C: paraphrase + unrelated quote, writer=assistant  -> SAVED m-002
```

`restless-old-brian` withdrew on a different ground:

> *"A deny-hook handling `/remember always read @AGENTS.md` would receive an *expanded* string and
> commit it as 'the human's own words, verbatim.' **That is the `Great remember these for me` bug
> rebuilt deliberately, by me, in the name of saving six seconds.** I proposed a mechanism that
> manufactures exactly the defect this review exists to close. Withdrawn without reservation."*

And `tester-breaker` supplied the mechanism that makes it unownable — **F18**, the finding the
council rates as the decisive one on this question:

> *"When the `/memory` match breaks, the prompt falls through to the model, costs 20¢, and is
> *correct*. When the `/remember` match breaks, `rsplit` finds no sentinel and returns the entire
> synthetic prompt — a ~300-character blob of the CLI's own `load_skill` boilerplate — which is then
> saved as `text` with `writer='human'`, `quote == text`. And `_check_quote` passes, **because the
> hook's only available evidence for `human_turns` is the very string it sliced from. The check
> becomes a tautology at the exact moment the slice becomes wrong.**"*

Plus **F17**: `/remember The user's input is: never use tabs` → `rsplit` takes the *last* occurrence
and silently saves only `never use tabs`.

`crusty-old-engineer`, who had conceded *to* the deterministic write path in Round 2 before seeing
any of this, withdrew in Round 3:

> *"A check whose input is derived from the thing it is checking is not a check. I price a control
> that silently becomes a tautology at infinity, because you cannot budget for a failure that
> reports success."*

**The rule the panel adopted, in `tester-breaker`'s words:**

> **"A read shortcut fails expensive. A write shortcut fails *convincing*."**

`cranky-old-sam` answered its own lens's question and withdrew last:

> *"'Which is the simpler system?' The model path costs $0.20 and buys three checks that already
> exist, are already tested, and compose. The deny path costs ~40 new lines, ownership of two
> undocumented upstream f-strings, **and it removes a safety property.** More parts, fewer
> guarantees. I proposed replacing a check I hadn't understood with code I'd have to maintain."*

### The condition on shipping the `/memory` deny — non-negotiable, 6–0

A conformance probe that **imports the installed `_load_skill`, calls it (with and without
arguments), and asserts the returned string byte-for-byte.** Proposed independently by
`crusty-old-engineer` and `tester-breaker`. `restless-old-brian` escalated its placement, and the
panel adopted the escalation:

> *"A test proves it on this device at test time. The breakage happens at `amplifier update`, in the
> steward's shell, weeks later. `cli.v1 §7` already says `update` ends by running `doctor` — so the
> assert belongs **in `doctor`, as a row**, alongside the test. **Put the alarm where the fire
> starts, not where the fire drill is.**"*

### One correction to the record

`tester-breaker` withdrew its own F15 in Round 2: `/remember` with an `@mention` is **not** broken
today. `mentions/loader.py:127-130` **prepends** context blocks and preserves the instruction body
verbatim. *"My attack failed and I say so."* The residual is a message defect, not a function one —
when a refusal is caused by expansion, say so: `refused: your text contained @AGENTS.md, which was
expanded before the memory tool saw it; retype it without the @`.

---

## Q3 — Should `edit` exist as a tool operation?

### **YES — and it is a debt, not a feature request. 6–0, after a veto was raised and then lifted.**

`contracts/cli.v1.md:30` — **LOCKED** — says `why` prints *"creation, **edits**, and forget if any."*
Tool operations are `save · forget · list` (`tool-memory/__init__.py:77`). **A frozen document is
currently describing behaviour that does not exist.**

> **intent-keeper:** *"`edit` is not a feature request. It is a locked contract describing behaviour
> that does not exist, and a frozen document that is not true is a worse problem than a missing
> operation."*

`cranky-old-sam` supplied the argument that has nothing to do with convenience:

> *"`status.py:139-141` computes `kept` as *the save commit is ≥7 days old and the id is still
> present*. Edit-as-forget-plus-save resets the clock. **So a human refining a memory on day six
> destroys the project's own success metric.** Every polish resets the Phase 1 gate to zero.
> Forget+save is not equivalent; it is actively hostile to measurement."*

### The minimal deterministic design — almost all of it is already built

```
operation="edit" { id, text, quote }     # writer="human" in v1
```

1. Inside the existing `_exclusive(path)` lock (`store.py:324-364`) and `_require_wellformed`
   (`:633-641`).
2. `_check_quote` unchanged (`:738-750`) — an edit needs a human quote for the same reason a save
   does.
3. Locate `- [m-NNN] `, **replace the text in place, same id, same line position**. One write, not
   two — on a store with this history, halving the writes is a safety argument.
4. Commit with `action: edit` plus a new `previous: <old text>` field. **`_commit_message` already
   takes `action` as a parameter and already writes it** (`store.py:677-691`).
5. `_assert_edited` — a ~15-line mirror of `_assert_saved` asserting the new line present **and**
   the old absent.
6. **`why` requires zero changes.** It already greps `\[m-NNN\]` (`store.py:701-705`) and already
   parses and returns `action` (`:728`), so creation → edit → forget surfaces in order for free, and
   `cli.v1 §3` becomes true with no work at all.
7. `_next_id` untouched (`:669-671`) — no id issued, no hole created.

**~30–70 lines in `store.py`, one enum value, one CLI verb.**

### The veto, and why it was lifted

`tester-breaker` blocked in Round 1:

> *"Right now the model can invent a memory; give it `edit` and it can rewrite a real one **while
> keeping the id and inheriting the honest human quote that justified the original.** Do not ship
> `edit` before the quote check has a real floor. I expect that to be an unpopular position; I'd
> hold it anyway."*

`intent-keeper` had independently proposed `writer="human"` for v1 from the opposite direction.
`tester-breaker` verified the mechanism in Round 2 and lifted:

> *"`store.py:815-819` forces `quote == text` for `writer="human"`, and `_check_quote` then requires
> that exact text to appear in a human turn. A model cannot compose an edit under that constraint. I
> also checked the obvious escape hatch: could the injected memory block itself count as a human turn
> and launder the composition? **No** — `hooks-memory-inject:210` sets
> `context_injection_role="system"`, and both turn-gatherers filter `role == "user"`
> (`tool-memory:190, 221`). That door is shut. **intent-keeper walked to the same floor from the
> opposite direction, which is the best evidence either of us was right.**"*

### Acceptance criteria the council attaches

1. **`writer="human"` only in v1.** `writer="assistant"` edit: later, or never — nobody showed a need.
2. **`was: <old text>` in the receipt, verbatim** (`user-advocate`). *"There is no undo verb for an
   edit anywhere. Until a real `undo` exists, printing `was:` makes the recovery one paste of
   `/remember`."*
3. **The duplicate scan must exclude the line being replaced.** `store.py:834-840` walks `existing`,
   which still contains the target — naive reuse raises `DuplicateMemory` against itself.
4. **Assert the id is unique across `["MEMORY.md", *topic_files(path)]` before editing.** `forget`
   returns on first match (`store.py:972`); an `edit` inheriting that would pass `_assert_edited`
   while a hand-added duplicate survives in a topic file.
5. **Do not run `save`'s cap check** — line count is unchanged.
6. **Ships after the byte floor and the quote floor**, not before. See the ranked list.

### The cost `user-advocate` refused to hide

> *"`writer="human"` would **not** have served the sentence he actually typed. He said *'update 4 to
> set the default to be concise, clear, approachable…'* — he described the change rather than
> dictating the line. Under `writer="human"`, that save is refused; he has to type the finished
> sentence himself. That is genuinely less than he asked for. I take the trade. But nobody should
> record this as 'shipped what he wanted.'"*

### `tester-breaker`'s standing residual, recorded

> *"Nobody should read my lifted veto as 'the quote check is fixed.' `edit` is now exactly as safe as
> `save` is, and **`save` still accepts `quote='e'`**."*

---

## Q4 — What is over-built, what is missing, what would you delete?

### DELETE — with proof, and with the order the panel ruled on

| What | Where | Lines | Why | Ruling |
|---|---|---|---|---|
| **The `usage: loaded` commit** | `store.py:1041-1047`, `hooks-memory-inject:200-205` | 1 kwarg | **96–110 of 103–113 commits.** `read_usage` reads the **working tree** (`store.py:1053-1054`), never `git show` — the commits buy *nothing* | **DO IT.** `commit=False`. Free, not a tradeoff |
| **Sub-agent load logging** | `hooks-memory-inject` (no `parent_id` anywhere) | ~5 | 56–59% of the volume; sub-agents can never write (§R2) | **DO IT** |
| **`update.py`'s executor** | `update.py` (197) + `tests/test_update.py` (176) | ~373 | Shells `uv tool upgrade` + `amplifier bundle add/remove` — owns two external CLIs' failure modes for one user | **DO IT — after amending `cli.v1 §7`, in the same commit.** Keep the installed-vs-remote CHECK |
| **Phase-2 placeholders** | `doctor.py:165-173, 215-229, 243-300`; `cli.py` `service`/`suggest` | ~85 | `_oldest()` documents its own defect at `:168-173`: *"suggestions.v1 is still DRAFT, so there is no entry format to date. Guessing one…"* | **DO IT — after amending `cli.v1 §1/§6`** |
| **Topic WRITE path** | `store.py:763-789`, `save(topic=…)`, `include_topics` | ~80 | **Zero non-test callers.** The tool schema has no `topic` field (`tool-memory:70-96`) | **DO IT** |
| **`ANNOUNCE_PREFIX` / `ANNOUNCE_EMPTY` / `announce_instruction()`** | `hooks-memory-inject:58, 67, 127-134` | ~15 | Dead once Q1 lands. The backtick workaround evaporates — the `[memory]` channel is not markdown | **DO IT with Q1** |
| **`(committed 8c75df6 to MEMORY.md)`** | `tool-memory:343, 365` | 2 | He will never type that sha | **DO IT** |
| **`0 pending suggestions (Phase 1 records none)`** | `tool-memory:373-376` | 1 | Advertises a feature with no entrance | **DO IT** |
| **8 of 10 exception subclasses** | `store.py:108-177` | ~50 | No caller discriminates | **HOLD — inverted order.** See below |
| **The `/memory` skill** | `skills/memory/SKILL.md` | 42 | 42 lines teaching a model to read a file to learn how to call a tool that prints a list | **DO IT — keep the command, delete the scaffolding** |

**Total ≈ 650 lines**, none of it load-bearing, all of it queued behind the floors.

### Two deletions that were proposed and DEFEATED — recorded

**`usage.jsonl` itself.** `cranky-old-sam` proposed deleting the file (~120 lines) and withdrew:
it is the only durable home for the `cited` event that Q5's §8 fix requires, and `cli.v1 §2`'s
`kept` — the project's success metric — is computed from it.

**~500 lines of conformance duplication.** `restless-old-brian` proposed folding
`conformance/session/tool/run.py` (430) and `conformance/session/inject/run.py` (286) into the
module suites beside them, then withdrew in Round 2 on evidence it went and found:

> *"It would lose the **contract-drift detector**, and that is load-bearing. The kits re-extract
> clause text from the *locked contract file* and byte-compare it against the code constant —
> `FRAMING_SENTENCE` (`hooks-memory-inject:44-48`), `ANNOUNCE_SAVE` (`tool-memory:51`). A module test
> asserts the constant against itself; **only the kit asserts it against the contract.** Delete that
> and prose and code drift apart silently, which is the failure mode this whole repo exists to
> prevent. I missed it in Round 1. Withdrawn."*

### The over-build finding, restated correctly by all four lenses that touched it

**It is aim, not size.** `crusty-old-engineer` defended the suite in Round 1 (*"56% of this tree is
tests and conformance kits, and that is exactly why the concurrency bug died in a week"*);
`tester-breaker` withdrew the word "over-built" in Round 2; `intent-keeper` and `cranky-old-sam`
said the same thing from their own axes.

> **tester-breaker:** *"Three thousand six hundred and sixty-two lines of tests and conformance, and
> **not one of them hands this writer a hostile byte.** That's not a testing gap — the tests are
> excellent at proving the code does what the contract says. It's that nobody in the room had yet
> asked what happens when the input isn't the one in the docstring."*

> **cranky-old-sam:** *"Here the cheapest correction is **addition, not subtraction**. One
> hostile-input probe — a non-UTF-8 byte, a 200 KB line, a one-character quote — catches three of
> tester-breaker's worst for about forty lines. Forty lines that buy more than the five hundred
> brian wants back. **Add before you subtract, and don't let a tidying exercise jump the queue ahead
> of the door that doesn't lock.**"*

**Ruling: keep every extraction probe. Delete the probes that print "Can't check" (a probe that can
never fail is not a probe). Add ~120–150 lines of hostile-input corpus applied to every entry point.
Net roughly line-neutral; goal coverage up.**

### The exception-class ruling — order inverted, `cranky-old-sam` conceding the sequence

> *"`OSError` and `UnicodeDecodeError` escape because those catch sets are too narrow. Ten subclasses
> do not help with that. Neither would twenty. The hierarchy and the escape are unrelated defects.
> **But I will not endorse 'widen the catch sets,' which is the obvious fix and the wrong one.**
> Widen to `except Exception` in the tool and a genuine `TypeError` in your own code gets served to
> the human as a polite refusal. You'd trade a crash for a lie, and this project's whole scar is
> about a writer that reported success for a line that never landed."*
>
> *"**The correct fix is: convert at the boundary, don't widen at the caller.** The library wraps its
> own foreseeable failures — the non-UTF-8 read, the oversized argv, the git that died — into
> `MemoryError` *inside* `store.py`, so that `except MemoryError` is sufficient **by construction**.
> The module that knows what can go wrong owns saying so. Boundary conversion first; hierarchy
> collapse second. His fix ships before mine."*

### MISSING — what he reached for and did not find

1. **A trustworthy write.** B1, B2, B3. `crusty-old-engineer` prices the whole floor at **~50 lines
   against 15 reproduced breaks:** `git commit -F -` via stdin (~3) · temp + `os.replace` +
   revert-on-failure (~25) · `_assert_saved` also asserts the working tree (~5) · reject the full
   `splitlines()` set (~3) · tolerant reads + boundary conversion (~10) · bound `_ID_RE` to
   `m-\d{1,9}` (1) · a per-line byte cap (~5).
2. **A quote floor.** Minimum length, word-boundary or proportional containment, not naked `in`.
3. **`edit`.** He asked for it by name in the first hour.
4. **An undo for forget.** `/forget` is undo for save. Nothing is undo for forget, and he used forget
   twice in one sentence, on trust, with one receipt arriving as a raw subprocess error.
5. **Deterministic rendering.** Q1.
6. **Any evidence memory is working.** `per m-017` fired zero times with a reply-shaping memory
   loaded. The Phase 1 gate has **no instrument**.
7. **Root-session filtering.** `intent-keeper`'s finding 10: *"92 distinct session_ids for a
   two-memory store used by one human. Nothing in this system distinguishes 'the human's sessions'
   from 'sub-agent mounts,' which means every number the project reports about its own use —
   including the Phase 1 gate — is computed over a population that is mostly not the human."*
8. **A `grep` on the id scan.** `_known_ids` → `_git.log_records(home)` with **no `--max-count`, no
   `--grep`** (`_git.py:145-150`) parses every commit body on every save, inside the write lock.
   Measured at 4 ms over 113 commits; at the observed accrual rate that is ~34,700 commits in a year.
   **Fix: pass `grep=r"\[m-"`. One argument, no new state.**

`crusty-old-engineer` proposed a `NEXT-ID` cache file and withdrew in Round 3 to `cranky-old-sam`'s
rule:

> **cranky-old-sam:** *"Don't add a cache file to make a slow walk fast. Delete the ninety-five
> commits that made it slow. **The fix that removes state beats the fix that adds it, every single
> time.** A `NEXT-ID` file is new state that can disagree with git, on a store whose entire value
> proposition is that git is the truth."*

### On build ORDER — `restless-old-brian`'s finding

> *"It was built back-to-front. The store plane got locked, contracted, conformance-kitted and
> concurrency-hardened before a single human-facing line had been rendered once on a real terminal.
> **You don't stock the pantry to the ceiling before you've checked the front door opens.**"*

---

## Q5 — Should the contracts stop promising model behaviour?

### **YES for the promise. NO for the goal. Stop promising; start measuring. 6–0 after `cranky-old-sam` conceded.**

`cranky-old-sam` proposed deleting `§8` outright and reversed in Round 2:

> *"intent-keeper landed a hit and I'm not going to pretend otherwise. My replacement §8 — 'a wrong
> memory dies at the store, `why` works' — describes a path the human can only walk **after he
> already suspects**. That's a dodge and the open item names it correctly. **I was right about the
> clause and wrong about the need.**"*

> **intent-keeper:** *"Sam, your replacement is a good clause about **remedy**. §8 was never a clause
> about remedy — it is a clause about **detection**. `/forget <id>` is what the human does *after*
> they know a memory is wrong; §8 is the only mechanism by which they *come to know*. **You are
> deleting the smoke alarm and pointing at the fire extinguisher** — and `m-003` is smouldering on
> this device right now, reading perfectly well, invisible to everything except a `git log` nobody
> has a reason to run."*

> **user-advocate:** *"Here I break with the tidy answer. Deleting the clause because a model ignores
> it removes his single feedback loop and **leaves the codebase cleaner and the human blinder.**"*

### Proposed `session.v1 §2` — replaces the current clause

> **2. Announce the load, once — rendered by code.**
> The inject hook emits the load line itself, on the session's first `provider:request`, as a
> `user_message` on the same `HookResult` that carries the block:
> `Loaded N memories (M topics available).` — or `No memories yet — /remember <text> to add one.`
> when `MEMORY.md` is empty. It is emitted exactly once per mounted session and is not an
> instruction to the assistant. **The counts live in that line and never inside the injected block**,
> which stays byte-identical for an identical `MEMORY.md` (§1).
> *Conformance:* with the model stubbed to emit no text at all, the line still appears in captured
> terminal output exactly once per session; the injected block is byte-identical across five
> simulated requests for an unchanged store.

### Proposed `session.v1 §8` — demoted to Reserved, and instrumented

> **R3 — Cite at use.** When a memory shapes an action, naming it inline (`per m-017`) would let a
> wrong memory die the first time it is used instead of months later. This is model behaviour and is
> **not promised in v1**. What the bundle guarantees is that compliance is **measurable**: each
> `per m-NNN` observed in a completed turn is recorded to `usage.jsonl` as a `cited` event, and
> `amplifier-memory status` reports per-memory citation counts over the last 30 days. A memory with
> zero citations after 30 days is reported as **unverified** — never deleted.
> Promote to Core only when observed above 50% over ≥20 real sessions.
> *Conformance:* a turn whose assistant text contains `m-017` produces exactly one `cited` event for
> `m-017`; a turn containing none produces none; `status` reports the count. **The rate is reported,
> not asserted.**

Note: recording has **no whitelist** — only *display* does. A hook on `orchestrator:complete` can
record the citation perfectly well (`cranky-old-sam`).

### And the one clause the panel puts above the others

`intent-keeper`, asked for a single clause that makes the root cause un-repeatable:

> **Conformance is asserted at the outermost layer the claim reaches.**
> A clause is proven only by an artifact captured at the boundary the clause names: a rendered line
> by captured terminal output; a stored file by reading the path its reader reads; an invocation by
> the process's own recorded argv; an encoding by the bytes on disk. **An assertion made against a
> value the same process just constructed proves the constructor, not the clause, and is recorded
> NOT-ASSERTABLE — never CONFORMS.** Where the outermost layer cannot be captured, the row says so
> and names the artifact that would capture it.

> *"That clause retires all four instances the panel found, from three different directions. It also
> does the thing that matters most — **it routes the failure to NOT-ASSERTABLE instead of green**,
> which is the exact mechanism by which '24 CONFORMS' survived alongside a first line the human could
> not read. And it settles §2 as a consequence rather than a preference: `user_message` becomes the
> only admissible implementation, because a rendered line can be captured and diffed and a model's
> willingness cannot."*

### Two record-accuracy defects, opposite in sign, on one page

`restless-old-brian` established that wave 4 both **over-claimed** (a string-constant assertion
accepted as proof of a terminal rendering) and **under-claimed** (asserted the steward's device
lacked a fix that `grep -c _exclusive → 7` says it has, in both the cache at
`amplifier-bundle-memory-450b259c7cb6895f` = `69827f4` and the uv-tool copy).

> *"Same root: this record verifies constants and reasons about consequences. One direction it
> flatters the work, the other it defames it; both times nobody ran the thing."*

Proposed rule, matched independently by `cranky-old-sam`'s N4:

> **CHECK-RECORD may record only what was observed running.** Every row names the command and pastes
> what it printed. A claim about the device is accompanied by the command that read the device.
> Anything asserted from source reading goes to the ledger as *Can't check*, never to the record as
> verified.

**Action item:** correct wave 4's stale device claim in `docs/workflow/CHECK-RECORD.md`.

### Also required by the same logic

- **`cli.v1 §3`** already promises `why` prints "creation, **edits**, and forget" — the code must
  catch up, or the clause must. The council says: code (Q3).
- **`ledger` row AMM-023 is `CONFORMS` for a clause whose probe silently dropped the word "edits"**
  (`tester-breaker`, F14). Proposed rule: *a probe must quote the **full** clause text it asserts,
  and any load-bearing word not covered by an assertion downgrades the row to GAP.* That check is
  itself mechanical.
- **`VISION.md:60-62`** states the goal and its stand-in in consecutive sentences. `store.v1 §6`
  widens the gap to *"the verbatim human quote that **justified** it"* — a word no code implements.
  These need candidates.
- **`store.v1 §9`** invites hand editing; B2 shows what that does. Either the invitation gets a
  floor under it or the clause needs a warning.

---

# PART 4 — THE RANKED LIST

Smallest change, largest effect. Ordering ruled by `restless-old-brian` as the order lens, with the
gates each other lens attached. Every item names the one command that proves it.

| # | Change | Size | Proof command | Pass condition |
|---|---|---|---|---|
| **0** *(parallel lane, steward)* | File candidates: `VISION.md:60-62` · `cli.v1 §3` "edits" · `session.v1 §2/§8` · `store.v1 §9` · `cli.v1 §7` (before any `update.py` deletion) | prose | `ls contracts/*.v2-candidate.md` | siblings exist; **no locked file modified in place** |
| **1** | **Atomic write** — temp + `os.replace` + revert-on-failure at `store.py:864`, and **`_assert_saved` also asserts the working tree** | ~30 | the `\u2028` probe, against the **installed** lib | refusal *before* any write · `git status --porcelain` clean · `MEMORY.md` byte-identical · next save succeeds |
| **2** | **Encoding + argv floor** — reject the full `splitlines()` set (`store.py:811`); tolerant reads in all six readers; boundary conversion to `MemoryError`; `git commit -F -` via stdin (`_git.py:68`); bound `_ID_RE` to `m-\d{1,9}`; per-line byte cap | ~25 | `printf '\xe9' >> MEMORY.md && amplifier-memory doctor; echo $?` | a **FAIL row** naming the byte and the remedy · nonzero exit · **zero traceback** |
| **3** | **`repair_store` names what it discarded** | ~10 | `amplifier-memory doctor --repair` on the wedged store | prints the discarded line verbatim before committing |
| **4** | **`log_usage(commit=False)`** + **sub-agent gate in the hook** + **`grep=r"\[m-"` on `log_records`** | 3 lines | `git -C ~/.amplifier/memory rev-list --count HEAD` before/after a working day | delta ≈ saves, not loads |
| **5** | **Quote floor** at `store.py:743-745` — minimum length + real containment | ~15 | `save(..., quote='e', human_turns=["Great remember these for me"])` | `QuoteNotHuman` |
| **6** | **Deterministic announce + receipts** — `user_message` on `provider:request` and `tool:post`, markup-escaped, pre-flattened; delete `ANNOUNCE_PREFIX`/`ANNOUNCE_EMPTY`/`announce_instruction()` | ~40 net −15 | pty-capture `amplifier run` against an empty store, then a 2-memory store | literal `[memory] …` lines · `<text>` intact · exactly once per session |
| **7** | **`/memory` via `prompt:submit` deny** + the byte-for-byte `_load_skill` assert **as a `doctor` row** + `cat ~/.amplifier/memory/MEMORY.md` in the output | ~30 | `/memory` in the REPL | `💰 Turn: $0.00` |
| **8** | **`edit`** — `writer="human"`, `action: edit`, `previous:` in the commit, `was:` in the receipt | ~70 | `amplifier-memory why m-004` | three rows: save · edit · forget |
| **9** | **`cited` events + citation rate in `status`** — the §8 instrument | ~40 | `status` after a session containing `per m-003` | non-null rate; unverified flag at 30 days |
| **10** | **Re-aim conformance** — delete the un-failable probes, keep every extraction probe, add the hostile-input corpus | ~+150 −250 | `uv run pytest -q` + the kits | drift detector present · hostile corpus green |
| **11** | **The ~650 lines of deletion** — executor, Phase-2 placeholders, topic write path, `/memory` skill, exception collapse | −650 | `uv run pytest -q` + `ruff check .` | green, with the contract candidates from #0 landed **in the same commit** |
| **12** | **Correct `CHECK-RECORD`** and adopt the observed-running rule | prose | — | wave 4's device claim corrected |

**Gates the panel attached, and they are not optional:**
- **Nothing on the deletion list (#11) moves until #1–#3 land AND #6 is confirmed by a human looking
  at a real terminal.** (`cranky-old-sam`, adopted by `restless-old-brian`.)
- **#8 is gated on #1, #2 and #5.** (`tester-breaker`'s lifted veto, `restless-old-brian`'s ordering.)
- **The `cli.v1 §7` amendment and the `update.py` deletion land in the same commit** — not first,
  not later. (`intent-keeper`, conceded by `cranky-old-sam` and `crusty-old-engineer`.)
- **Phase 2 stays parked** until #1–#6 are real. Unanimous.

### On running the doc lane in parallel — `restless-old-brian`'s ruling, since it is his own discipline

> *"My rule against two-things-at-once is about one builder's attention on one critical path — it is
> not a ban on an independent lane that shares no files. Different actor, different artifact, and
> decisively: **the doc is upstream of the code.** Leaving `VISION.md:60-62` wrong while you fix the
> code it produced means you are manufacturing new defects at the same rate you're clearing old
> ones. **A wrong contract isn't a parallel task, it's a leak upstream of the work — you close it
> while the pumps run, not after.**"*

### What moves the panel off FAIL

> **restless-old-brian:** *"It is items 1–3 re-run against the **installed** library and coming back
> clean: the `\u2028` script refusing before it writes, `doctor` surviving one accented byte with a
> row instead of a traceback, and `repair_store` naming what it deleted. **Three scripts, three
> refusals, one file unchanged — that is the whole distance between here and CONCERN.**"*

---

# PART 5 — RECORDED DISSENT AND STANDING COSTS

The panel converged on every open item by Round 3. There is **no standing unresolved
disagreement** — which is unusual and is stated plainly rather than manufactured. What follows is
what lenses gave up, and what they refused to hide while recommending.

### Positions reversed, with attribution

| Lens | Position | Reversed to | On what |
|---|---|---|---|
| intent-keeper | deterministic `/remember`+`/forget` | model path stays | verified `writer="human"` already forces `quote == text` — *"I had the mechanism backwards"* |
| intent-keeper | CONCERN with a time-based trip-wire | FAIL | *"I set my own trip-wire on the wrong variable — a matter of days when it was always a matter of state"* |
| cranky-old-sam | delete `§8` | demote and instrument | *"I was right about the clause and wrong about the need"* |
| cranky-old-sam | delete `usage.jsonl` | keep it, `commit=False` | the `cited` event needs a home; and `read_usage` never reads git, so the commits were free to delete |
| cranky-old-sam | delete `/memory` | keep it, make it free | *"I tried to delete the human's only window onto a store he cannot otherwise see, because the window was expensive"* |
| cranky-old-sam | CONCERN | FAIL | its own Round-1 endorsement of the verify-after-commit machinery was falsified — it guards the wrong file |
| crusty-old-engineer | *"the write path is the most trustworthy thing in the repo"* | retracted | reproduced the `\u2028` break himself |
| crusty-old-engineer | refuse the `/memory` deny hack | adopt it with the tripwire | *"a coupling with a test that fails loudly on a Tuesday is a pin; without one it is a mortgage — I drew that distinction and then declined to apply it to my own proposal"* |
| crusty-old-engineer | adopt deterministic `/remember` | withdraw | *"I adopted intent-keeper's argument at the exact moment he abandoned it, without running the three-line probe that settles it"* |
| crusty-old-engineer | `NEXT-ID` cache file | withdrawn | Sam's *"the fix that removes state beats the fix that adds it"* |
| restless-old-brian | −500 lines of conformance | withdrawn | found the contract-drift detector is load-bearing |
| restless-old-brian | deny for all three commands | `/memory` only | *"That is the `Great remember these for me` bug rebuilt deliberately, by me"* |
| restless-old-brian | CONCERN | FAIL | *"I checked that the fix was installed; tester-breaker checked whether it holds"* |
| user-advocate | finding 7 (the fix is not on his device) | withdrawn | brian's measurement; *"I took a project artifact's word for the state of a real person's machine instead of walking over and looking"* |
| tester-breaker | veto on `edit` | lifted | verified `writer="human"` + `context_injection_role="system"` close the door |
| tester-breaker | F15 (`@mention` breaks `/remember`) | withdrawn | *"expansion prepends and preserves; my attack failed and I say so"* |
| tester-breaker | "the conformance suite is over-built" | withdrew the word | *"I used the wrong word. Aim, not size."* |

### Standing costs — recommended **anyway**, and named so the steward can price them

1. **The save receipt moves into a channel a person learns to ignore.** `user-advocate` recommends
   it and refuses to pretend otherwise: *"a boring line that is always there beats a prose sentence
   that showed up two times out of three."*
2. **`"Operation denied: "` is welded to the `/memory` output** at `LOOP:2901`. No flag suppresses
   it. The human will read a denial above their own memory list. Mitigable only by writing a reason
   that absorbs the prefix as a sentence.
3. **`Processing…` still prints and the `💰 Turn: $0.00` footer still prints** on a denied
   `/memory` — the ceremony of a turn that cost nothing. The footer is arguably the receipt.
4. **`writer="human"` `edit` does not serve the sentence the steward actually typed.** He described
   the change; under v1 he must dictate the line. *"Nobody should record this as 'shipped what he
   wanted.'"*
5. **`tester-breaker`'s lifted veto is not an all-clear.** *"`edit` is now exactly as safe as `save`
   is, and `save` still accepts `quote='e'`."*
6. **The deny path couples the bundle to a private f-string** (`CLI/main.py:3183-3195`) that no
   contract protects. It belongs in `PINS.md` with an expiry note and a `doctor` row, and the
   registry ask belongs upstream **today**.
7. **`user_message` does not render under another orchestrator.** `process_hook_result` appears only
   in `loop-streaming`. A delegated sub-session renders nothing, silently. Needs a probe.
8. **This council read code, ran probes against throwaway stores, and did not run a full interactive
   session.** The Q1 recommendation rests on a rendering that, as of this review, **has still never
   been observed on a real terminal.**

---

# PART 6 — WHAT THE PANEL SAYS IS RIGHT

Not one lens disputed these, and the review would be dishonest without them.

- **The architecture.** *"A git repo of one-line markdown, injected verbatim, written by code and
  read by a human with `cat`. That is the correct shape."* — cranky-old-sam
- **The lock.** `_exclusive` (`store.py:324-364`) held under every attack. `tester-breaker`
  volunteered six honest failed attacks and credited four of them to it: the 200-line boundary is
  exactly correct (200th saves, 201st refused), four concurrent forgets give one clean success and
  three clean `UnknownId`s, the double-`init` race is correctly re-checked under the lock, and `why`
  with regex metacharacters degrades cleanly.
- **`cli.py`.** 135 lines, imports two things, every verb is parse → one library call → print.
  *"Genuinely minimal, leave alone."*
- **The fail-open path** (`hooks-memory-inject:213-235`). Correct, and it is the proof that the
  deterministic rendering mechanism works.
- **The commit format already carries `action:`** (`store.py:677-691`) and `why` already parses it
  (`:728`) — `edit`'s provenance is free.
- **The ledger's honesty.** *"That ledger is why this council could read the truth in ten minutes
  instead of a day — it's the thing that honestly says §2 fired 1-of-2 and §3 fired 0-of-2. Nobody
  writes that down about their own work unless they mean it. Keep the ledger."* — restless-old-brian
- **The one-sentence goal.** *"This team can produce the sentence, and it is a good one. That is rare
  and it earns them the benefit of the doubt on most of what follows."* — intent-keeper

---

# PART 7 — THE VERDICT IN ONE LINE PER LENS

> **intent-keeper — FAIL:** *"The substitution is not in the code — it is in the frozen vision, in
> two consecutive sentences, written before any code. You cannot test your way to a guarantee your
> contract never made."*

> **cranky-old-sam — FAIL:** *"I vouched for the verify-after-commit code because it had a scar. It
> was watching the committed tree while the hook fed the model from the working tree — two sources
> of truth for one file, and the corruption lives in the gap between them."*

> **crusty-old-engineer — FAIL:** *"The writer writes corrupt data to disk while reporting that it
> did not write, and nothing in 3,662 lines of verification looks at the file the session actually
> loads."*

> **restless-old-brian — FAIL:** *"A memory store that writes corruption it reports as unwritten,
> feeds that corruption to the model from the working tree its own safety net never checks, and dies
> on a colleague's name is not real yet — fix 1 through 3 and I'll flip it myself, gladly."*

> **user-advocate — FAIL:** *"The machinery that protects his file is proven and installed; the one
> line he actually reads has never been rendered on a real terminal, not once — hardened where he
> can't see, unproven where he looks."*

> **tester-breaker — FAIL:** *"I spent an afternoon constructing `quote='e'` as a hypothetical. It
> had already happened, four times, on day one, on the machine we're reviewing."*

---

*Six lenses. Three rounds. Unanimous FAIL, with four verdict changes and thirteen recorded
self-reversals — every one on evidence the reversing lens went and produced itself. The design
council's one blocking question is answered with file:line evidence: a bundle-shipped hook CAN
render deterministically to the human, on a documented public field, on a whitelisted event, using a
mechanism this bundle already ships and currently uses only to apologise.*
