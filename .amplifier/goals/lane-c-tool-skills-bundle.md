# Lane lane-c-tool-skills-bundle — `tool-memory`, the three slash-command skills, the bundle

You are a worker session, alone, in your own git worktree of `amplifier-bundle-memory` on
branch `lane/amplifier_bundle_memory-yvu`. Work ONLY here; never touch the main checkout or
sibling worktrees; never merge to `main`. Commit early; push after every commit
(`git push -u origin HEAD`).

Read first: `PINS.md` (Substrate facts), `AGENTS.md` (rules 4, 5, 7, 8, 11),
`contracts/session.v1.md` (FROZEN) §3–§8, R2 and its Conformance section, `contracts/cli.v1.md`
§9, `src/amplifier_memory/__init__.py` + `store.py` (the library you wrap — read `save()`'s
signature: `save(text, quote, writer, session_id, human_turns, *, home, topic, topic_purpose)`,
and `log_usage(event, target, session_id, home=None, *, commit=True)`), and
`modules/hooks-memory-inject/amplifier_module_hooks_memory_inject/__init__.py` (the sibling
module whose stub you replace; imitate its mount/HookResult/test style). Read-only reference for
a tool module: `~/.amplifier/cache/amplifier-engram-*/modules/tool-engram/` and
`amplifier-foundation/docs/BUNDLE_GUIDE.md` §"modules" (mount Iron Law:
`await coordinator.mount("tools", tool, name=tool.name)`); for behavior YAML shape:
`~/.amplifier/cache/amplifier-engram-*/behaviors/engram-session.yaml` and `bundle.yaml`.

**Work item:** `amplifier_bundle_memory-yvu` in project `amplifier_bundle_memory`. Claim with
`work_claim(project="amplifier_bundle_memory", item_id="amplifier_bundle_memory-yvu")`. At the end
`work_resolve` with a reason for the steward, then **read it back** with `work_list(...)` and print
the stored reason — the printed read-back is the evidence.

**File ownership — edit ONLY:** `modules/tool-memory/**`, `modules/hooks-memory-inject/**` (ONLY:
replace the `log_usage` stub with the library call and add the library dependency), `skills/**`,
`behaviors/**`, `bundle.md`, `conformance/session/tool/**`, and `ledger/rows.yaml` rows
AMM-012…AMM-017 (disposition + notes only; AMM-012/013/016/017 stay NOT-ASSERTABLE — model
behaviour — unless you can name an in-process probe that could fail). Off-limits: everything under
`src/`, `tests/` at the root, `conformance/store/`, `conformance/cli/`, `contracts/`, `docs/`,
`README.md`, `pyproject.toml` at the root. Lane D is editing `src/amplifier_memory/` right now.

## Outcome

In a root session, when the human states a standing preference, the assistant calls the `memory`
tool; the tool verifies the quoted words appear in a human turn, refuses in a sub-agent session,
and otherwise writes through `amplifier_memory.save` — one commit, announced with its id and the
undo. `/remember <text>`, `/forget <id>` and `/memory` reach the same tool through three
user-invocable skills. `amplifier bundle add <this repo> --app` composes hook + tool + skills into
every session through `behaviors/memory-session.yaml`. The inject hook logs `loaded` once per
session through the real library. No wrapper carries logic; no wrapper shells out to the CLI.

## Terminal states and the exit

Each acceptance item ends `PASS`, `FAIL-<named cause>`, `BLOCKED-<named cause>`, or
`PENDING-HUMAN`. Complete when **either** every item reaches a terminal state, **or** it is
conclusively demonstrated the remainder cannot, naming the blocker for each. Items ending FAIL or
BLOCKED are residuals, not failures of the goal. Exceeding the time bound (100 min wall) is the
terminal state `BUDGET`: commit what is sound and write the marker. No improving after the marker.

**Final act — write `DONE.json` in the worktree root** (gitignored; never commit it):
`{"lane":"lane-c-tool-skills-bundle","session_id":"<this session's id>","verdict":"COMPLETE|BLOCKED|PARTIAL",
"branch":"lane/amplifier_bundle_memory-yvu","head":"<sha>","pushed":true,"items":[…],"residuals":[…],
"pending_human":[],"resources":[],"suite":"<pytest summary>"}`. If a cause stops every deliverable,
also write `BLOCKED.md` (gitignored) naming it.

## Acceptance — every item names a file or a command whose output you print

1. `modules/tool-memory/pyproject.toml`: entry point
   `[project.entry-points."amplifier.modules"] tool-memory = "amplifier_module_tool_memory:mount"`,
   `__amplifier_module_type__ = "tool"`, dependency
   `amplifier-memory @ git+https://github.com/bkrabach/amplifier-bundle-memory@main` with
   `[tool.hatch.metadata] allow-direct-references = true`. Same dependency added to
   `modules/hooks-memory-inject/pyproject.toml`. `grep -n 'amplifier-memory @' modules/*/pyproject.toml`
   printed. False if either uses a relative path or bare name (AGENTS rule 4).
2. `mount(coordinator, config)` mounts ONE tool named `memory` via
   `await coordinator.mount("tools", tool, name=tool.name)`; `execute(input)` dispatches
   `operation ∈ {save, forget, list}`; tool description tells the model exactly when to save (§3)
   and when not to (§4), in ≤ 12 lines, quoting the announce format
   `Saved memory m-017: "<text>" — /forget m-017 to undo.` Print the description.
3. session.v1 §5 human-turn check: `save` collects `role == "user"` message contents from
   `coordinator.mount_points["context"].get_messages()` (content may be a string or a list of
   blocks — flatten text blocks), falls back to the session's `transcript.jsonl` when the context
   module is absent or the quote is not found there (path
   `~/.amplifier/projects/<slug>/sessions/<session_id>/transcript.jsonl`; discover the slug rule from
   `amplifier_app_cli/session_store.py` in the installed CLI — read it, do not guess), then calls
   `amplifier_memory.save(..., human_turns=...)` via `asyncio.to_thread`. Discriminating pair printed:
   quote present in a user turn → saved; quote present only in an assistant/tool message → refused
   with `QuoteNotHuman` relayed in one line. False if the tool re-implements the check instead of
   passing `human_turns` to the library.
4. R2: `coordinator.parent_id is not None` → `save` refuses with one line naming R2, before any
   library call; `forget` likewise refuses; `list` is allowed. Printed.
5. Refusals from the library (`CapExceeded`, `DuplicateMemory`, `UnknownId`, `StoreMissing`) are
   relayed as one-line tool results, never tracebacks; `StoreMissing` says how to create the store
   (`amplifier-memory init`). Printed for each.
6. `writer` is `"assistant"` for in-turn saves and `"human"` for `/remember`; for `writer="human"`
   the tool passes `quote=text` (the library requires quote == text for human writer — read
   `store.py`). The tool never accepts `writer="suggestion"` in Phase 1 (one-line refusal). Printed.
7. Skills: `skills/remember/SKILL.md`, `skills/forget/SKILL.md`, `skills/memory/SKILL.md`, each with
   frontmatter `user-invocable: true` and `disable-model-invocation: true`, bodies that call the
   `memory` tool with `$ARGUMENTS` (`remember` → save writer=human; `forget` → forget; `memory` →
   list, printed with ids, plus pending-suggestion count = 0 in Phase 1) and announce in one line
   per session.v1 §6 (`Saved memory m-NNN: … — /forget m-NNN to undo.` / `Forgot m-NNN.`).
   `grep -n 'user-invocable\|disable-model-invocation' skills/*/SKILL.md` printed (6 lines).
   Verify against the installed CLI how skill frontmatter is parsed
   (`amplifier_app_cli` `discovery.py`, keys `user-invocable`, `disable-model-invocation`,
   optional `shortcut:`) and cite file:line in the module README. AGENTS rule 5: verified, not assumed.
8. `behaviors/memory-session.yaml` registers `hooks: hooks-memory-inject`, `tools: tool-memory`, and
   adds this repo's `skills/` to `tool-skills`' `config.skills` list (list-typed config values merge;
   the tool-skills module source is
   `git+https://github.com/microsoft/amplifier-bundle-skills@main#subdirectory=modules/tool-skills`),
   every `source:` a `git+https://github.com/bkrabach/amplifier-bundle-memory@main#subdirectory=…`
   URL. `bundle.md` is the root bundle with `default_behavior` naming it. `grep -n 'source:' behaviors/*.yaml bundle.md`
   printed. False if any source is relative or bare.
9. Hook stub replaced: `modules/hooks-memory-inject/.../__init__.py` calls
   `amplifier_memory.log_usage("loaded", "MEMORY.md", session_id)` exactly once per session
   (existing once-per-session guard kept), inside the existing never-fatal try; the hook's tests
   still pass (`cd modules/hooks-memory-inject && uv run pytest -q` printed). Record the cadence
   decision in that module's README: once per session = one commit per session per store.
10. `grep -rn 'subprocess\|amplifier-memory \|cli' modules/tool-memory/amplifier_module_tool_memory/`
    prints no shell-out to the CLI (show the output; a hit in a comment is fine, say so).
11. `conformance/session/tool/run.py` prints one line per clause §3, §4, §5, §6, §7, §8, R2 as
    `Core N — Kept|Not yet|Broken|Can't check — <evidence>` (§3, §4, §7, §8 → Can't check
    in-process, proven by the real-host smoke, lane E), exits 0; output printed. Flip AMM-014 (§5)
    and AMM-015 (§6) to CONFORMS only where the named probe passes; print
    `git diff --stat -- ledger/rows.yaml`.
12. `cd modules/tool-memory && uv run pytest -q` and `uv run ruff check .` printed green; root
    `uv run ruff check .` from the repo root ALSO green (wave 1 measured: a module clean under its
    own config raised 4 root findings — run both).
13. Item resolved, read back with `work_list`, reason printed. Include in the reason the answer to
    the open question: does the CLI record a `/remember …` input as a `role=user` message in the
    transcript? (Read `amplifier_app_cli/main.py` `process_input` / skill-shortcut dispatch and
    say what you found with file:line; if you cannot determine it, say "undetermined" and why.)
    False if the reason asserts anything you know to be untrue.

## Scope-outs

Never write to `~/.amplifier/memory`; tests set `AMPLIFIER_MEMORY_HOME` to `tmp_path`. Never edit
`~/.amplifier/settings.yaml`, never `amplifier bundle add` anything (lane E installs). No network
beyond `git push`. No services, containers or background processes. Do not edit contracts, docs,
`README.md`, or anything under `src/`.

## Known

- Honesty gate sentence: *"session.v1 Core N — Can't check in this lane because …"* in `run.py`
  output and the resolution reason.
- `amplifier_core` is importable inside a module venv that declares it; the hook module's
  `pyproject.toml` and tests show the pattern — copy it.
- Wave 1 measured: `HookResult`/tool signatures are in `amplifier-core/docs/HOOKS_API.md` and
  `amplifier_core/interfaces.py` in this workspace's `amplifier-core` checkout
  (`/home/bkrabach/dev/amplifier-memory-team-ci/amplifier-core`).
- Show command output inline; never assert a result without it. Print, then claim.
