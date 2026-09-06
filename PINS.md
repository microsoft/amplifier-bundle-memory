# Pins — hard facts for this repository

Read this before your first command. Every line is a fact you may rely on.

## Where things are

| Thing | Exact location |
|---|---|
| Vision | `docs/VISION.md` |
| Contracts | `contracts/store.v1.md` · `contracts/session.v1.md` · `contracts/cli.v1.md` · `contracts/suggestions.v1.md` |
| Standing rules for sessions | `AGENTS.md` |
| Conformance ledger | `ledger/rows.yaml` (derived after ratification; absent until then) |
| Conformance kits | `conformance/<contract>/run.py` (one per contract, written with the code) |
| Real-host smoke | `tests/smoke/` — runs `amplifier` on this device; the merge gate AGENTS.md names |
| Integration branch | `main` |
| Return log | `docs/workflow/OWNER-RETURN-LOG.md` |
| Check record | `docs/workflow/CHECK-RECORD.md` |
| Feedback inbox | `.converge/feedback/` |
| First-wake investigation and contract review | `docs/workflow/FIRST-WAKE-REVIEW.md` |

## Naming

- A proposal to change a contract is `<contract>.vN-candidate.md`, in the same
  folder as the contract it changes.
- A locked contract carries `(FROZEN <date>)` in its first heading line. A draft
  carries `(DRAFT)`. Status appears nowhere else in the file.
- Memory ids are `m-NNN`; suggestion ids are `s-NNN`. Neither is ever reused.

## The store this code manages

- `${AMPLIFIER_MEMORY_HOME:-~/.amplifier/memory}` — a git repository. Tests
  always set `AMPLIFIER_MEMORY_HOME` to a temp dir; nothing under `tests/`
  touches the real store.
- The real store on this device is created only by `amplifier-memory init`,
  run by the steward or by the real-host smoke with the steward's knowledge.

## Substrate facts (verified 2026-09-06 against the checkouts in this workspace)

- Hook results on `session:start` are discarded by the kernel; injection
  happens on `provider:request`, `ephemeral=True`, `role="system"`.
  `context:post_compact` is declared but nothing emits it.
- Tool access: `coordinator.session_id`; `coordinator.parent_id` (None for a
  root session); `coordinator.mount_points["context"].get_messages()` returns
  `list[dict]` with `role`/`content`. Disk fallback:
  `~/.amplifier/projects/<slug>/sessions/<id>/transcript.jsonl`.
- Slash commands from a bundle are user-invocable skills: `SKILL.md` with
  `user-invocable: true` and `disable-model-invocation: true`; the rest of
  the line arrives as `$ARGUMENTS`. The CLI's built-in command registry is
  closed to bundles.
- Module entry-point group: `[project.entry-points."amplifier.modules"]`.
  `mount(coordinator, config)`; tools mount via
  `await coordinator.mount("tools", tool, name=tool.name)`.
- App-bundle install: `amplifier bundle add <uri> --app` appends the uri to
  `bundle.app` in `~/.amplifier/settings.yaml`; point `--app` at a behavior
  file, not the root bundle.

## The pre-push guard

- The hook lives at `.githooks/pre-push`. Enable it once per clone:

  ```
  git config core.hooksPath .githooks
  ```

- It refuses any push whose diff touches a file whose first heading contains
  `(FROZEN`, unless the same push also contains a sibling `*-candidate.md`.
- Run it by hand against a base: `./.githooks/pre-push <base-ref>`.

## Work tracking

- Work-tracker project: `amplifier-memory`.
- Every work item names the contract clause it serves.

## Commands that must work

```
uv run pytest                      # in-process conformance, all contracts
uv run ruff check                  # lint
amplifier-memory doctor            # on this device, after install; exit 0
tests/smoke/real_session.sh        # one real session saves, one loads; on this device
```
