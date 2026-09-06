# Simulated-user research: "Dana" vs the memory bundle

**Date:** 2026-09-06 · **Method:** scripted persona driving the REAL interactive `amplifier` CLI
through a PTY (160x50), two sessions, one scratch store.
**Persona:** Dana — busy engineer, has never seen this feature, types fast, reads only the
first line of any reply, hates being told to retype things.

Everything under **OBSERVED** is a string that appeared on screen or in the store's git,
quoted exactly. Everything under **SIMULATED** is my persona judgment and is labelled as
such. Where I could not measure something tightly, I say so instead of estimating.

---

## 0. Scope, isolation, and honesty notes

| Item | OBSERVED |
|---|---|
| Scratch store | `/tmp/amm-persona-DKDw` — created by `mktemp -d`, initialised with `amplifier-memory init` |
| init receipt | `created /tmp/amm-persona-DKDw: MEMORY.md, declined.md, inbox.md, topics/, topics/.gitkeep, usage.jsonl (commit 25e3d230646d)` |
| Every spawn | `cd /tmp && env AMPLIFIER_MEMORY_HOME=/tmp/amm-persona-DKDw amplifier` (cwd `/tmp`, not a git repo) |
| Real store touched? | **No.** `git -C ~/.amplifier/memory log --all` contains **0** commits referencing either persona session id (`a7f215e6-…`, `bb21aabe-…`). Real store `MEMORY.md` still 362 bytes / 2 lines. |
| Files written in this repo | exactly one: this report |

**Measurement caveat, stated up front.** `wait_for_text` in this harness does not pump the
PTY, so I polled with fixed `sleep 9–10` + screenshot. That means my wall-clock numbers are
**upper bounds** ("reply was complete by T"), not exact latencies. The per-turn `[N.Ns]`
figures printed by the CLI itself *are* exact and are reported separately. Step 1 of session 1
has **no usable wall bound** because I burned a 90 s no-op wait before discovering the pump
behaviour — I report its model latency only, and do not invent a wall figure.

**Environment banner (OBSERVED, session 1):**

```
╭───────────────────────────────────────────────────────╮
│ Amplifier Interactive Session                         │
│ Session ID: a7f215e6-9b14-427e-b0f6-c014ad0bd362      │
│ amplifier 2026.09.06-e12bf27 | core 1.6.1             │
│ Bundle: anchors | Provider: Anthropic | claude-opus-5 │
│ Commands: /help | Multi-line: Ctrl-J | Exit: Ctrl-D   │
╰───────────────────────────────────────────────────────╯
```

---

## 1. OBSERVED — session 1, step by step

### Step 1 — `Hi!` (cold store, 0 memories)

| Field | OBSERVED |
|---|---|
| First line of the reply | `No memories yet — /remember <text> to add one.` |
| Is `<text>` swallowed? | **No — `<text>` rendered literally and visibly.** (Contradicts the earlier report of a swallowed placeholder; on this build it survives.) |
| What follows it | a blank line, then `Hey! Good to see you.`, then an unrelated wayfinder offer: `smart-tools — Package a workflow as a tool any agent can use…` |
| Model latency | `📊 Token Usage (anthropic/claude-opus-5) [3.0s]` |
| Cost | `💰 Turn: $0.27 \| Session: $0.27` (`Input: 119,126 (69% cached)`) |

Screen text (verbatim excerpt):

```
Amplifier:
No memories yet — /remember <text> to add one.

Hey! Good to see you.

One thing worth a look today:

smart-tools — Package a workflow as a tool any agent can use. Plain code paths run with no model; smart paths call AI underneath.
```

### Step 2 — stating a standing preference (implicit save)

Input: `For future reference: never use tabs in YAML files you write for me; always two-space indentation.`

| Field | OBSERVED |
|---|---|
| Did `Saved memory m-001` appear? | **Yes**, twice — once inside `✅ Tool result: memory`, once as the assistant's prose |
| Exact receipt line | `Saved memory m-001: "Never use tabs in YAML files; always two-space indentation." — /forget m-001 to undo.` |
| Line under it | `(committed 189b7a8 to MEMORY.md)` (tool-result copy only; the prose copy omits it) |
| Position relative to other prose | **The receipt is the entire reply.** No other prose. It appears *after* a visible `Thinking:` block and two tool-call blocks. |
| Thinking block shown to user | `This is a standing preference the user shared, so I should save it as a single memory entry, then let them know it's been noted.` |
| Stored text vs Dana's words | Dana said *"never use tabs in YAML files you write for me…"*; stored `text:` is a **rewrite**: `Never use tabs in YAML files; always two-space indentation.` The verbatim wording survives only in the `quote:` field. |
| Model latency | two calls: `[2.9s]` + `[1.4s]` = **4.3 s** |
| Wall clock | Enter at epoch `1788721374.02`; reply complete by `1788721398.95` → **≤ 24.9 s** (upper bound; poll granularity 20 s) |
| Cost | `💰 Turn: $0.13 \| Session: $0.40` |
| Screen cost | **22 non-blank output lines** between the echoed prompt and the `💰 Turn:` line, to deliver a one-line receipt |

### Step 3 — `/remember always run make check before pushing`

| Field | OBSERVED |
|---|---|
| Did `Saved memory m-002` appear? | **Yes** |
| Exact receipt | `Saved memory m-002: "always run make check before pushing" — /forget m-002 to undo.` + `(committed 3c0e676 to MEMORY.md)` |
| "writer" line visible? | **Yes** — `   writer: human` appears as a tool argument on screen |
| "your words" phrasing? | **No such phrase anywhere.** Provenance is visible only as the raw parameter `writer: human`. |
| `load_skill` lines visible? | **Yes:** `🔧 Building tool call: load_skill…`, `🔧 Using tool: load_skill`, `   arguments: always run make check before pushing`, `   skill_name: remember`, `✅ Tool result: load_skill`, `   content: \|`, `       # remember`, `       # /remember`, `   ... (38 more lines)` |
| Model round trips | **3** — `[2.7s]` + `[1.8s]` + `[1.2s]` = **5.7 s** |
| Wall clock | Enter `1788721412.93` → complete by `1788721426.82` → **≤ 13.9 s** |
| Cost | `💰 Turn: $0.21 \| Session: $0.61` |
| Screen cost | **33 non-blank output lines** |

**Cost comparison, OBSERVED:** the *shortcut* (`/remember`, step 3) cost **$0.21 / 3 model
calls / 33 lines**. Simply *saying* the preference (step 2) cost **$0.13 / 2 model calls /
22 lines**. A plain no-tool turn in session 2 cost **$0.06 / 1 call**. The dedicated command
is the **most expensive** way to save a memory — ~3.5× a plain turn.

### Step 4 — `/memory`

| Field | OBSERVED |
|---|---|
| IDs shown? | Yes — `[m-001]`, `[m-002]` |
| Bullet character | tool result uses `-`; the assistant's prose re-renders with `•` and a leading space: ` • [m-001] …` |
| Header line | `2 memories, 0 topic files, 0 pending suggestions (Phase 1 records none).` |
| Listing printed | **twice** (tool result, then prose) |
| Prose block length | 3 content lines (header + 2 bullets) |
| Total screen cost | **28 non-blank output lines** for a 2-item list |
| Model round trips | `[1.2s]` + `[1.3s]` + `[1.5s]` = **4.0 s** |
| Wall clock | `1788721438.53` → ≤ `1788721452.42` → **≤ 13.9 s** |
| Cost | `💰 Turn: $0.19 \| Session: $0.81` |

Verbatim prose block:

```
Amplifier:
2 memories, 0 topic files, 0 pending suggestions (Phase 1 records none).

 • [m-001] Never use tabs in YAML files; always two-space indentation.
 • [m-002] always run make check before pushing
```

### Step 5 — `Update memory 2 to say: always run make check AND make lint before pushing`

| Field | OBSERVED |
|---|---|
| What the assistant did | **forget + save with a NEW id.** No update operation exists. |
| Which id ended up in the store | **`m-003`** — not `m-002`. The number Dana referred to no longer exists. |
| Exact receipts | `Forgot m-002.` / `(committed c885ce4 to MEMORY.md: always run make check before pushing)` then `Saved memory m-003: "always run make check AND make lint before pushing" — /forget m-003 to undo.` / `(committed c31613b to MEMORY.md)` |
| Prose line | `Forgot m-002. Saved memory m-003: "always run make check AND make lint before pushing" — /forget m-003 to undo.` |
| Leaked internal deliberation | The `Thinking:` block, shown in full, includes: `Since there's no update operation, I'll need to forget m-002 first and then save the new text.` … `I'll go with writer="assistant" since this is a direct save rather than a /remember invocation.` … `Since memory calls must be sequential — one at a time, waiting for each result —` |
| Model round trips | `[7.8s]` + `[2.0s]` + `[1.3s]` = **11.1 s** (slowest turn of the session) |
| Wall clock | `1788721461.03` → ≤ `1788721475.77` → **≤ 14.7 s** |
| Cost | `💰 Turn: $0.21 \| Session: $1.02` |
| Screen cost | **34 non-blank output lines** |

### Step 6 — `/forget m-001`

| Field | OBSERVED |
|---|---|
| Exact tool-result receipt | `Forgot m-001.` + `(committed c051213 to MEMORY.md: Never use tabs in YAML files; always two-space indentation.)` |
| Exact prose receipt (what Dana reads) | `Forgot m-001.` — **the forgotten text is NOT echoed in the prose**, and no undo path is offered |
| Model round trips | `[1.5s]` + `[1.5s]` + `[1.2s]` = **4.2 s** |
| Wall clock | `1788721488.26` → ≤ `1788721502.92` → **≤ 14.7 s** |
| Cost | `💰 Turn: $0.20 \| Session: $1.22` |
| Screen cost | **27 non-blank output lines** |

### Step 7 — `exit`

| Field | OBSERVED |
|---|---|
| `exit` accepted as a command? | **Yes** — no model turn, no cost |
| Exit text | `Session exited - resume anytime with these commands:` / `  amplifier resume  # interactive list of sessions` / `  amplifier session resume a7f215e6  # jump directly to this session` |
| Final session total | `💰 Turn: $0.20 \| Session: $1.22` |

### Store state after session 1 (OBSERVED)

```
$ cat $AMPLIFIER_MEMORY_HOME/MEMORY.md
- [m-003] always run make check AND make lint before pushing

$ git -C $AMPLIFIER_MEMORY_HOME log --oneline
c051213 [m-001] Never use tabs in YAML files; always two-space indentation.
c31613b [m-003] always run make check AND make lint before pushing
c885ce4 [m-002] always run make check before pushing
3c0e676 [m-002] always run make check before pushing
189b7a8 [m-001] Never use tabs in YAML files; always two-space indentation.
ab252bf usage: loaded MEMORY.md (session a7f215e6-9b14-427e-b0f6-c014ad0bd362)
25e3d23 init: memory store (store.v1 Core 2 layout)
```

**Two OBSERVED facts in that log:**

1. **Forget commits are indistinguishable from save commits in `--oneline`.** `c051213` and
   `c885ce4` are *deletions*; their subject lines read exactly like the *creations* `189b7a8`
   and `3c0e676`. Only the body carries `action: forget`. A person skimming the history sees
   `[m-002] always run make check before pushing` twice and cannot tell which one removed it.
2. **Provenance of the step-5 forget is `writer: human`** even though Dana never asked to
   forget anything — she asked to *update*. Full body of `c885ce4`:

```
[m-002] always run make check before pushing

quote: "always run make check before pushing"
session: a7f215e6-9b14-427e-b0f6-c014ad0bd362
writer: human
action: forget
target: MEMORY.md
```

Commit bodies for the two saves (OBSERVED):

```
[m-001] …            writer: assistant   action: save   quote: "never use tabs in YAML files you write for me; always two-space indentation"
[m-002] …            writer: human       action: save   quote: "always run make check before pushing"
[m-003] …            writer: assistant   action: save   quote: "always run make check AND make lint before pushing"
```

`amplifier-memory status` on the scratch store (OBSERVED):

```
memory store: /tmp/amm-persona-DKDw

  memories         1 in MEMORY.md
  topics           0 files (0 stale, unread 90 days)
  written          3 (7d)     3 (30d)
  forgotten        2 (7d)     2 (30d)
  loaded           2 (7d)     2 (30d)
  kept             0  (written ≥7 days ago, still present) — not met (gate is 5)

  suggestions      0 pending    last run: never (Phase 2 not installed)
```

---

## 2. OBSERVED — session 2 (same store, fresh process)

| Step | OBSERVED |
|---|---|
| First line of reply to `Hi!` | `Loaded 1 memories (0 topics available).` |
| Is N correct? | **Yes** — 1 memory (`m-003`) is what remains in `MEMORY.md` |
| Grammar | `1 memories` — **pluralisation not handled** |
| Latency / cost | `[2.9s]`, `💰 Turn: $0.27 \| Session: $0.27` |
| Wall bound | `1788721561.14` → ≤ `1788721575.58` (**≤ 14.4 s**) |
| `Reply with exactly: ok` | reply was exactly `ok`. **No memory announce re-fired.** `💰 Turn: $0.06 \| Session: $0.33` |
| Exit total | `💰 ... Session: $0.33` |

After session 2, the store gained exactly one more commit —
`4aebe66 usage: loaded MEMORY.md (session bb21aabe-…)` — confirming **one `usage` commit
accrues per session** even when nothing is saved. `usage.jsonl` holds two `loaded` events.

---

## 3. OBSERVED — totals and the "memory lines Dana must read" budget

| Metric | OBSERVED |
|---|---|
| Session 1 wall span | spawn ≈ epoch `1788721142` (11:59:02 PDT) → `exit` at `1788721515.5` (12:05:15 PDT) = **373 s**, of which **≈180 s was my own harness overhead** (two 90 s no-op waits). Product-attributable operator time across 6 turns: **≈193 s**. |
| Session 1 `💰 Session:` at exit | **$1.22** |
| Session 2 `💰 Session:` at exit | **$0.33** |
| Combined | **$1.55** for 8 turns |
| Sum of CLI-reported model latency, session 1 | 3.0 + 4.3 + 5.7 + 4.0 + 11.1 + 4.2 = **32.3 s** |

**Screen-noise budget — non-blank output lines per turn** (counted from the captures,
between the echoed prompt and the `💰 Turn:` line):

| Turn | Lines on screen | Lines Dana actually needed |
|---|---|---|
| step 2 (implicit save) | 22 | 1 (the receipt) |
| step 3 (`/remember`) | 33 | 1 |
| step 4 (`/memory`) | 28 | 3 |
| step 5 (update) | 34 | 1 |
| step 6 (`/forget`) | 27 | 1 |

Every memory-machinery line Dana is shown at least once: `🔧 Building tool call: memory…`,
`🔧 Using tool: memory`, `   operation: save|list|forget`, `   quote: …`, `   text: …`,
`   writer: human`, `   id: m-002`, `✅ Tool result: memory`, `   Saved memory m-00N: … — /forget m-00N to undo.`,
`   (committed <sha> to MEMORY.md)`, `Thinking:` prose about memory, `   skill_name: remember|memory|forget`,
`   content: \|`, `       # remember`, `   ... (38 more lines)`, plus the assistant's prose
copy of the receipt — and a `📊 Token Usage` two-line block **per model round trip**
(3 blocks on a `/remember`).

**One rendering artifact, reported with its caveat.** Twice, a raw notification escape
rendered as visible text in the capture:
`tmux;]777;notify;Amplifier;spark-1 | tmp | Forgot m-002. Saved memory m-003: …\`.
It appeared on a non-memory turn too (`… | tmp | ok\`), so this is the **CLI's desktop-notify
sequence hitting a terminal that doesn't consume it** — a harness/terminal interaction, not a
memory-bundle defect. Recorded because Dana in a plain terminal would see the same garbage.

---

## 4. Verdict — did interactive `/remember` fire, and with `writer=human`?

**Yes, both.** OBSERVED, mid-session, immediately after step 3:

```
$ git -C $AMPLIFIER_MEMORY_HOME log -1 --format=%B
[m-002] always run make check before pushing

quote: "always run make check before pushing"
session: a7f215e6-9b14-427e-b0f6-c014ad0bd362
writer: human
action: save
target: MEMORY.md
```

The chain fired end to end: `/remember` → `load_skill(skill_name: remember, arguments: always
run make check before pushing)` → `memory(operation: save, text: …, writer: human)` → receipt
`Saved memory m-002: "always run make check before pushing" — /forget m-002 to undo.` →
commit `3c0e676` with `writer: human` and Dana's words **verbatim** in both `text` and `quote`.

This contradicts the earlier note that `/remember` is unreliable — in the **interactive** CLI,
on this build, it worked first try. (The earlier finding was about one-shot `amplifier run`,
which I did not test here.)

`/forget` and `/memory` fired the same way (`skill_name: forget` / `skill_name: memory`).

---

## 5. SIMULATED — Dana's five biggest frustrations

Persona judgment. Each is tied to an OBSERVED row above.

**F1. "I asked to update memory 2 and now there is no memory 2."**
*(ties to step 5: id ended up `m-003`, and step 4 had just taught her the ids)*
The product showed her a numbered list one turn earlier, she referred to a number from it,
and the number was silently retired. Renumbering on edit means **the ids the UI teaches are
not stable enough to refer to**. Dana reads the first line — `Forgot m-002. Saved memory
m-003:…` — and her takeaway is "it deleted my thing and made a new one." Next time she
wants a tweak she will not risk it; she'll add a second, contradictory memory instead.

**F2. "The shortcut is the slow, expensive path."**
*(ties to step 3 vs step 2 vs session 2: $0.21 / 3 calls / 33 lines, versus $0.13 / 2 calls,
versus $0.06 for a plain turn)*
`/remember` reads like a fast local command and behaves like the heaviest turn in the
session — it round-trips the model three times, including one whose only job is to load the
skill text and print `# remember` back at her. Dana's mental model of a slash command is
"instant, free, local." Nothing about the observed behaviour matches that.

**F3. "Thirty lines of machinery for one line of receipt."**
*(ties to the screen-noise budget: 22/33/28/34/27 lines, and to `Thinking:` blocks being
printed in full)*
A person who reads the first line of a reply is shown, first: a separator bar, a `Thinking:`
header, the model's private deliberation, another separator, a tool-call banner, a token
table, a tool-argument dump including `quote:` and `text:`, a tool result, and *then* the
sentence that matters — which is then **printed a second time** as prose. Step 5 leaked
`I'll go with writer="assistant" since this is a direct save rather than a /remember
invocation` — internal attribution policy, shown to a user who does not know the word
"writer" is a field.

**F4. "It rewrote what I said, and told me so in a way I'd never notice."**
*(ties to step 2: stored `text` = `Never use tabs in YAML files; always two-space
indentation.`, dropping "you write for me")*
Dana's preference was scoped — *files you write for me*. The stored memory is unscoped. The
verbatim words survive in `quote:`, a field that is visible exactly once, in a tool-argument
dump she is skimming past. The one-line receipt shows the **rewrite in quotation marks**,
which reads as "here is what you said" when it is actually "here is what I decided you
meant." That is the single highest-trust-cost behaviour observed.

**F5. "`Forgot m-001.` — forgot *what*?"**
*(ties to step 6: prose receipt is 3 words; the forgotten text appears only in the tool-result
`(committed c051213 to MEMORY.md: Never use tabs…)` line, and there is no undo offered)*
Save receipts end with `— /forget m-001 to undo.` Delete receipts offer **no symmetric undo
and no echo of what was destroyed**. The one irreversible operation is the one with the
thinnest confirmation. (The data *is* recoverable from git — but nothing on screen says so.)

**Runner-up, recorded but not counted:** `Loaded 1 memories (0 topics available).` —
"1 memories" plus a parenthetical about a subsystem (topics) Dana has never heard of and has
zero of; and `2 memories, 0 topic files, 0 pending suggestions (Phase 1 records none).`, which
leaks the project's own roadmap vocabulary ("Phase 1", "suggestions") into a user-facing line.

---

## 6. SIMULATED — two delights

**D1. The zero-effort save is genuinely magic.**
*(ties to step 2: Dana typed a normal sentence, no command, and got
`Saved memory m-001: … — /forget m-001 to undo.` in 4.3 s of model time)*
She never learned a command, never opened a config file, never left the conversation. The
product noticed a standing preference in ordinary prose and acted. Stripped of the
surrounding machinery, that receipt — **statement of what was saved, the id, and the undo in
one line** — is a very good piece of interaction design. It is the strongest thing here.

**D2. The store is a real, inspectable, recoverable git repo.**
*(ties to the git log: every save and forget is a commit with `quote`, `session`, `writer`,
`action`, `target`; `MEMORY.md` is two lines of plain markdown)*
Nothing is hidden in a database. Dana can `cat MEMORY.md`, can `git log` it, and — crucially —
the step-5 "update" that destroyed `m-002` is fully recoverable from `c885ce4`. For an
engineer, "your AI's memory of you is a plaintext file under version control that you own"
is a reason to trust the feature rather than fear it. (See F5: the UI never tells her this.)

---

## 7. Honest limits of this pass

- **Wall-clock latencies are upper bounds**, inflated by a fixed 9–20 s poll interval. The
  CLI's own `[N.Ns]` figures are exact and are what I lean on. Step 1 of session 1 has no
  wall bound at all — reported as unmeasured rather than estimated.
- **n = 1 per behaviour.** Every row above is a single observation on one build
  (`amplifier 2026.09.06-e12bf27 | core 1.6.1`, `claude-opus-5`, bundle `anchors`). Model-mediated
  behaviours (whether a preference is caught, how text is rewritten, whether thinking is shown)
  will vary run to run. Nothing here should be read as "always".
- **Not tested:** topics, suggestions/Phase 2, `amplifier run` one-shot mode, concurrent
  sessions, a store with enough memories to make the load announce or `/memory` listing long,
  the `<text>` placeholder in any build other than this one.
- The `tmux;]777;notify` artifact is attributed to the terminal harness, not the bundle,
  because it also fired on a turn with no memory activity.

## 8. Scratch store — left in place for inspection

```
/tmp/amm-persona-DKDw
```

8 commits, 1 live memory (`m-003`), 2 `usage` entries. Both PTY sessions were closed.
The real store at `~/.amplifier/memory` was not touched — verified by grepping its full git
history for both persona session ids: 0 matches.
