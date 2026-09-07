# tool-memory

The `memory` tool: `save` · `edit` · `forget` · `list` · `overview` · `cite` ·
`review`.

Serves `contracts/session.v4.md` (FROZEN 2026-09-07) §3, §4, §5, §6, §8, §12, §13
and R2, and `contracts/suggestions.v2.md` §6.

## What it does

One tool, one mount, the one legal way:

```python
await coordinator.mount("tools", tool, name=tool.name)  # name == "memory"
```

| Operation | Input | Library call |
|---|---|---|
| `save` | `text`, `quote`, optional `writer`, `topic`, `topic_purpose`, `batch_of` | `amplifier_memory.save(text, quote, writer, session_id, human_turns, topic=…, topic_purpose=…)` |
| `edit` | `id`, `text`, optional `quote`, `writer` | `amplifier_memory.edit(id, text, quote, writer, session_id, human_turns)` |
| `forget` | `id` | `amplifier_memory.forget(id, session_id=…, writer="human")` |
| `list` | — | `amplifier_memory.list_memories()` |
| `overview` | — | the library's four-line overview, from the same figures as `amplifier-memory status` (session.v4 §6, cli.v2 §2) |
| `cite` | `id` | `amplifier_memory.record_citation(id, session_id)` |
| `review` | optional `action`, `id` | `amplifier_memory.inbox` — accept · decline · skip, or the listing |

Every library call goes through `asyncio.to_thread`: the library is
synchronous and does git work, and a session's event loop must not block on
it.

## What this module is allowed to know

AGENTS.md rule 11: all behaviour lives in `src/amplifier_memory/`. This module
carries exactly the four facts a library cannot see from outside a session,
and nothing else:

1. **Whether this is a sub-agent session** — `coordinator.parent_id is not
   None` (session.v4 R2). `save`, `edit` and `forget` refuse before any library call;
   `list` and `overview` are allowed, because reading is not writing.
1b. **What this session declares itself to be** — `$AMPLIFIER_SESSION_ORIGIN`,
   read through `amplifier_memory.origin_from_env` (session.v4 §13). Unset means
   `human`. Any other origin refuses the same three operations, in R2's shape
   with the origin in R2's place:

   ```
   refused: session.v4 R2  — a sub-agent session never saves; only a root session with a human interlocutor may write.
   refused: session.v4 §13 — a worker    session never saves; only a      session with a human interlocutor may write.
   ```

   R2 is asked first, because it is the narrower fact: a sub-agent of a human
   session is still not a writer, whatever the launcher exported.
2. **The session's human turns** — §5's evidence. Collected from
   `coordinator.mount_points["context"].get_messages()` (`role == "user"`,
   text blocks flattened), with `transcript.jsonl` as the fallback. They are
   *passed* to `amplifier_memory.save(..., human_turns=…)`; the check itself
   is the library's, and this module never re-implements it.
3. **The session id** — for the store.v2 §6 commit trailer.

It never shells out to the `amplifier-memory` CLI (cli.v2 §9). Two wrappers
over one library is the design; a wrapper calling a wrapper is not.

## The transcript fallback, and why it exists

The live context is asked first. Disk is added when the context module is
absent, or when no live turn contains the quote — a resumed session's earlier
turns may only exist on disk.

Path, verified against the installed CLI:

- `amplifier_app_cli/session_store.py:96-99` —
  `~/.amplifier/projects/<slug>/sessions/<session-id>/`, and
  `_save_transcript` (`session_store.py:133-160`) writes one JSON object per
  line, dropping only `system` and `developer` roles — so `user` turns are
  there.
- `amplifier_app_cli/project_utils.py:22-30` (`get_project_slug`) — the slug
  is the absolute cwd with `/` and `\` replaced by `-`, `:` dropped, and a
  leading `-` guaranteed. `project_slug()` here re-implements that rule
  rather than importing it: a session module must not depend on the app
  package. A session whose cwd moved is still found by the glob fallback.

`AMPLIFIER_PROJECTS_HOME` overrides the root; the tests use it so no test
ever reads the human's real sessions.

## How `/remember` reaches this tool with a valid quote

`/remember <text>` is a user-invocable skill, not a built-in command. In the
installed CLI, `CommandProcessor.process_input` (`amplifier_app_cli/main.py:797-817`)
resolves `/remember` through `SKILL_SHORTCUTS` and returns the `load_skill`
action — **not** the `prompt` action. `_load_skill`
(`main.py:3185-3195`) then returns a *synthetic* prompt, which `main.py:4040-4053`
executes as the turn.

So the literal line `/remember <text>` is **not** what lands in context. What
lands is the synthetic prompt, as a `role: user` message — and it carries the
typed text verbatim inside it:

```
… The user's input is: <text>
```

`amplifier_memory._check_quote` asks whether the quote appears *in* a human
turn (substring, not equality), so a `writer="human"` save whose quote is the
typed text verifies against that synthetic turn. That is why `/remember`
works, and it is a real dependency on the CLI's phrasing — recorded here so
that if the phrasing changes, this is the file that says what broke.

For `writer="human"` the tool sets `quote = text` itself: `store.py` refuses
that writer unless `quote == text`.

### Where `/remember` fires, and where it does not

Measured on this device, 2026-09-06, both arms:

| Surface | Result | Evidence |
|---|---|---|
| Interactive `amplifier` | **Fires, first try.** `/remember always run make check before pushing` → `load_skill(remember)` → `memory(save, writer=human)` → commit `3c0e676`, `writer: human`, the typed line verbatim in both `text` and `quote` | `docs/workflow/reviews/simulated-user-dana-2026-09-06.md` §4 |
| One-shot `amplifier run "…"` | **Unreliable.** One run saved through the skill; one refused, because the typed line was not among the collected human turns | lane E; `docs/workflow/CHECK-RECORD.md` finding 3 |

The reason is dispatch, not the writer. `/remember` is a *skill shortcut*, and
the shortcut interception lives in `CommandProcessor.process_input`
(`amplifier_app_cli/main.py:797-817`) — the **interactive** input path. A
one-shot `amplifier run "<prompt>"` does not go through it, so the leading
`/remember` is just text at the front of an ordinary prompt: whether the skill
loads at all is then a model decision, and when it does not, the typed line
never becomes the synthetic `The user's input is: …` turn the quote check
verifies against. Hence one arm saving and one refusing, from the same command.

No code in this module changes that: the fix, if one is ever wanted, is in the
CLI's dispatch, not here. What this module guarantees either way is that a save
without a matching human turn is **refused** rather than invented.

## The receipts, and why they are shaped this way

Every receipt is fixed by `contracts/session.v4.md` and is never reworded here.
The tool renders it, once, and the model relays it verbatim:

| Receipt | Shape |
|---|---|
| save (§3) | `saved m-017 — /memory forget m-017 to undo.` · the memory, unquoted, indented · `your words, verbatim` or `my wording, your go-ahead: "<quote>"` |
| batch (§3) | on the save that completes the run, `saved N memories — my wording, your go-ahead: "<quote>". Reword any line and I'll replace it; /memory forget <id> drops one.` then the lines |
| edit (§6) | `edited m-004 — was: "<old>"` · `  now: <new>` |
| forget (§6) | `forgot m-002 — still in git: amplifier-memory why m-002` · the removed text |
| list (§6) | `N memories` (`1 memory`; topics only when > 0) · `- [m-NNN] <text>` · `edit by hand: $EDITOR <store>/MEMORY.md` |
| overview (§6) | at most four lines: suggestions waiting (absent on an empty inbox) · `N memories, N topics` · `last 7 days: …` · the `/memory` command line |
| review (suggestions.v2 §6) | the listing, or one line per answer: accepted (§3's three lines) · `declined s-042 …` · `skipped s-042 — still waiting.` |
| cite (§8) | no text at all — the citation is recorded in `usage.jsonl` (store.v2 §8) |

Each line answers a question the 2026-09-06 transcript left open: whose words
these are (the assistant's *rewrite* appeared in quotation marks,
indistinguishable from the human's own sentence); what a forget removed — the
one operation that leaves nothing behind in the store — and that it is
recoverable; that hand edits are legitimate (store.v2 §9).

No receipt carries a commit sha (not a human's business), a phase name, a
zero-valued count, or `1 memories`. §6 forbids all four, and the conformance kit
scans every rendered receipt for them.

## Skill frontmatter, verified

The two slash commands are `SKILL.md` files with `user-invocable: true` and
`disable-model-invocation: true`. Those keys are parsed by the **tool-skills**
module, not by `amplifier_app_cli`:

- `amplifier_module_tool_skills/discovery.py:292-306` — `disable-model-invocation`
  and `user-invocable`, each accepting the hyphen or snake_case spelling and
  coerced to `bool`.
- `amplifier_module_tool_skills/discovery.py:317-331` — the optional
  `shortcut:` alias, lowercased and pattern-checked.
- `amplifier_module_tool_skills/__init__.py:432-455` (`get_shortcuts`) — every
  skill with `user_invocable` is registered under its **canonical name**, and
  additionally under `shortcut:` when one differs. So `skills/remember/` is
  `/remember` with no `shortcut:` field needed, which is why neither of the two
  declares one.

(Measured 2026-09-06 in `~/.amplifier/cache/amplifier-bundle-skills-*/modules/tool-skills/`,
which is what the installed CLI loads. A grep for `user-invocable` across the
installed `amplifier_app_cli` package returns nothing — the key never reaches
it, and the app-CLI side only consumes the resulting `SKILL_SHORTCUTS` dict.)

## Which instance, and whether it is live (§12)

| key | default | meaning |
|---|---|---|
| `home` | unset | the instance every operation reads and writes |

```yaml
modules:
  - source: git+https://github.com/microsoft/amplifier-bundle-memory@main#subdirectory=modules/tool-memory
    config:
      home: ~/.amplifier-agent/memory
```

Read at mount, from the plan the app supplies, so this works under any app. With
no `home:` the store contract's resolution order decides, so a session with no
`home:` behaves exactly as it did before the key existed. Point the hook and the
tool at the same instance: two halves of one session plane.

When that instance's `config.yaml` says `enabled: false`, **every** operation —
reads included — refuses with one line and writes nothing:

```
memory is disabled for this instance (/home/you/.amplifier-agent/memory: enabled: false).
```

That sentence is the library's own (`store.InstanceDisabled`), not a paraphrase
of it, so the tool's refusal, the CLI's and the library's are one sentence.

The tool is still **mounted** on an inert instance. §12 offers two ways to be
silent — "the tool is not mounted — or, where a plan requires it to be, refuses
every operation with one line" — and a plan that names this module requires the
tool to be there: a mount that silently skipped it would fail
`protocol_compliance` for every agent composing this behavior, and the session
would learn nothing about why. What an inert instance does instead is advertise
nothing: `MemoryTool.description` becomes that same one line, so §11's per-request
cost for a switched-off instance is the sentence that says so rather than the
full lesson on saving.

## Development

```
cd modules/tool-memory
uv run pytest -q
uv run ruff check .
```

`pyproject.toml` declares the library as
`amplifier-memory @ git+https://github.com/microsoft/amplifier-bundle-memory@main`
(AGENTS.md rule 4 — never a relative path, never a bare name). The
`[tool.uv.sources]` entry below it is a **development-only** resolution
override: it lets the suite run against this worktree, offline, and never
reaches the built wheel, which carries the git URL.
