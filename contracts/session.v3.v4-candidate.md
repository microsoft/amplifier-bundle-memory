# Proposal: session.v3 → v4 (CANDIDATE)

target: contracts/session.v3.md

**Changes:** `contracts/session.v3.md` (FROZEN 2026-09-07, amended in place the same day), which
stays the law until the steward's word lands below. **A version bump, not an amendment:** two new
clauses change which store a session reads and who inside a session may write — v4. Vocabulary
matches today's siblings `contracts/store.v2.v3-candidate.md` (an INSTANCE is a directory holding
the memories plus its own `config.yaml`; `sessions.jsonl` is plumbing; `enabled: false` makes an
instance inert) and `docs/VISION.v2-candidate.md`.

## The exact change, sentence by sentence

### Change 1 — new §12, module configuration

New text (nothing to replace; §1–§11 keep their numbers):

```
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
```

### Change 2 — new §13, session origin

New text (nothing to replace):

```
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
    hook renders beside §2's (suggestions.v1 §5) is not rendered, and the
    suggest job treats the session as having no human interlocutor: its turns
    are not mined for standing preferences. This is a convention, not a
    capability — any app, launcher, tmux wrapper or recipe honours it by
    exporting one variable, and a launcher that exports nothing is treated as
    human, exactly as today. An upstream ask stands for amplifier-app-cli to
    record the origin in `metadata.json` natively; the variable works without
    it.
```

### Change 3 — §2, the load line names a non-default instance

Current text — §2's closing sentence only (`session.v3.md:36-38`); every line of §2 above it is
unchanged:

```
   still loaded.`; when `MEMORY.md` is empty `no memories yet. Tell me a
   standing preference — "never use tabs in YAML" — and I'll keep it in every
   session on this device.`
```

Replacement:

```
   still loaded.`; when `MEMORY.md` is empty `no memories yet. Tell me a
   standing preference — "never use tabs in YAML" — and I'll keep it in every
   session on this device.` When the session's instance (§12) is not the
   default one, the line names it — `3 memories loaded from
   ~/.amplifier-agent/memory. /memory to see them.` — so a human never has to
   guess which store answered. The default instance is never named: the common
   line stays byte-identical to today's.
```

## The evidence

**The steward's own words, 2026-09-07, verbatim:**

- "Add the config value to the hook and/or tool or wherever appropriate in the config that works across no matter what
  app is used (so consider the amplifier-core mount plan level support), that points to an instance of our memory system"
- "or I could configure `enabled: false` in the config and disable both read/write and even advertisement of the memory
  features in a given config"
- "many of the memory suggestions have come from sessions that my 'manager' sessions created as 'worker' sessions … The
  worker sessions are full tmux-launched sessions, so they don't have a parent session id"
- "what is something that _anything_ could do to the start of a new session via the app the user uses, to make it clear
  which instances either should or should not be considered 'human' user?"

**A cost already paid, measured (§13).** The first unattended timer night (2026-09-07 07:00Z) wrote 17 suggestions;
**6 came from session 6bafabaf**, whose first turn is a manager's brief — "Claim drumbeat-d4h from the drumbeat
work-tracker project…" — not a human's. `metadata.json` carries no parent id and no origin, and R2's guard cannot see it
either: it tests `coordinator.parent_id`, and a tmux-launched worker *is* a root session
(`modules/tool-memory/amplifier_module_tool_memory/__init__.py:586`, refusal at `:670`).

**The second cost (§12).** Neither module can be pointed at an instance: the hook resolves `$AMPLIFIER_MEMORY_HOME` else
one fixed path and reads exactly one mount-plan key, `priority`
(`modules/hooks-memory-inject/amplifier_module_hooks_memory_inject/__init__.py:154`, `:296`); the tool's `mount()` takes
no `home` from config at all (`modules/tool-memory/amplifier_module_tool_memory/__init__.py:1007`). So a second app
cannot have its own memory, and a project cannot turn memory off.

## What does NOT change

§1's framing sentence and its cache-stable block — byte-identical across sessions, no path inside it, no announce
instruction. The two commands and every first word of §6, receipts and refusals byte-for-byte. §11's 500-token ceiling.
Relay-verbatim-never-reword, everywhere it appears. R2 stands untouched: a sub-agent still never saves — §13 adds a
second class of session that may not write, it does not relax the first. §3/§6's no-presumption rule and the grep behind
it; §9's nothing at session end; §10's fail open. And a session with no `home:` and no `AMPLIFIER_SESSION_ORIGIN` —
every session running today — behaves exactly as it does now: same store, same injection, same saves, same line.

## Steward's word

Answer in one word: **ratified** · **ratified with edits** · **declined** · **later**.

>
