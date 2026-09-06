# tool-memory

The `memory` tool: `save` · `forget` · `list`.

Serves `contracts/session.v1.md` (FROZEN 2026-09-06) §3, §4, §5, §6 and R2.

## What it does

One tool, three operations, mounted the one legal way:

```python
await coordinator.mount("tools", tool, name=tool.name)   # name == "memory"
```

| Operation | Input | Library call |
|---|---|---|
| `save` | `text`, `quote`, optional `writer` | `amplifier_memory.save(text, quote, writer, session_id, human_turns)` |
| `forget` | `id` | `amplifier_memory.forget(id, session_id=…, writer="human")` |
| `list` | — | `amplifier_memory.list_memories()` |

Every library call goes through `asyncio.to_thread`: the library is
synchronous and does git work, and a session's event loop must not block on
it.

## What this module is allowed to know

AGENTS.md rule 11: all behaviour lives in `src/amplifier_memory/`. This module
carries exactly the three facts a library cannot see from outside a session,
and nothing else:

1. **Whether this is a sub-agent session** — `coordinator.parent_id is not
   None` (session.v1 R2). `save` and `forget` refuse before any library call;
   `list` is allowed, because reading is not writing.
2. **The session's human turns** — §5's evidence. Collected from
   `coordinator.mount_points["context"].get_messages()` (`role == "user"`,
   text blocks flattened), with `transcript.jsonl` as the fallback. They are
   *passed* to `amplifier_memory.save(..., human_turns=…)`; the check itself
   is the library's, and this module never re-implements it.
3. **The session id** — for the store.v1 §6 commit trailer.

It never shells out to the `amplifier-memory` CLI (cli.v1 §9). Two wrappers
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

## Skill frontmatter, verified

The three slash commands are `SKILL.md` files with `user-invocable: true` and
`disable-model-invocation: true`. Those keys are parsed by the **tool-skills**
module, not by `amplifier_app_cli`:

- `amplifier_module_tool_skills/discovery.py:292-306` — `disable-model-invocation`
  and `user-invocable`, each accepting the hyphen or snake_case spelling and
  coerced to `bool`.
- `amplifier_module_tool_skills/discovery.py:317-331` — the optional
  `shortcut:` alias, lowercased and pattern-checked.

(Measured 2026-09-06 in `~/.amplifier/cache/amplifier-bundle-skills-*/modules/tool-skills/`,
which is what the installed CLI loads. A grep for `user-invocable` across the
installed `amplifier_app_cli` package returns nothing — the key never reaches
it, and the app-CLI side only consumes the resulting `SKILL_SHORTCUTS` dict.)

## Development

```
cd modules/tool-memory
uv run pytest -q
uv run ruff check .
```

`pyproject.toml` declares the library as
`amplifier-memory @ git+https://github.com/bkrabach/amplifier-bundle-memory@main`
(AGENTS.md rule 4 — never a relative path, never a bare name). The
`[tool.uv.sources]` entry below it is a **development-only** resolution
override: it lets the suite run against this worktree, offline, and never
reaches the built wheel, which carries the git URL.
