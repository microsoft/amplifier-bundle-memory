# Lane lane-b-inject-hook — `hooks-memory-inject`: MEMORY.md present in every model request

You are a worker session, alone, in your own git worktree of `amplifier-bundle-memory`
on branch `lane/amplifier_bundle_memory-zqi`. Work ONLY here; never touch the main checkout
or sibling worktrees; never merge to `main`. Commit early; push to `origin` after every commit
(`git push -u origin HEAD`).

Read first: `PINS.md` (Substrate facts — verified, rely on them), `AGENTS.md`,
`contracts/session.v1.md` (FROZEN) §1, §2, §9, §10 and its Conformance section,
`ledger/rows.yaml` rows AMM-011, AMM-012, AMM-019, AMM-020. Reference implementations to
imitate, read-only: the installed hook at
`/home/bkrabach/.amplifier/cache/amplifier-module-hooks-status-context-*/amplifier_module_hooks_status_context/__init__.py`
(mount, `provider:request` registration, `<system-reminder>` envelope) and
`/home/bkrabach/dev/amplifier-memory-team-ci/amplifier-core/docs/HOOKS_API.md` (HookResult).

**Work item:** `amplifier_bundle_memory-zqi` in project `amplifier_bundle_memory`. Claim with
`work_claim(project="amplifier_bundle_memory", item_id="amplifier_bundle_memory-zqi")`; at the end
`work_resolve` with a reason for the steward, then **read it back** with `work_list(...)` and print
the stored reason — the printed read-back is the evidence.

**File ownership — edit ONLY:** `modules/hooks-memory-inject/**`, `conformance/session/inject/**`,
`conformance/session/__init__.py`, and `ledger/rows.yaml` rows AMM-011/012/019/020 (disposition +
notes only). Everything else is off-limits — in particular `src/amplifier_memory/` (lane A is
writing it right now; until it lands you read `MEMORY.md` with plain file IO and write usage
through a one-function local stub `_log_usage()` clearly marked `# TODO(lane C/D): replace with
amplifier_memory.log_usage`, named in `residuals`). No `behaviors/`, no `bundle.md` (lane C).

## Outcome

Every model request of a session — the first, and every one after a compaction — carries one
block `<system-reminder source="amplifier-memory"> … </system-reminder>`: the session.v1 §1
framing sentence verbatim, then `MEMORY.md` verbatim, then a static announce-once instruction (§2).
The block is byte-identical for identical `MEMORY.md`. If the store is missing or unreadable, the
session proceeds unchanged with one line in the transcript and one appended to
`~/.amplifier/memory-errors.log` (§10). Nothing is registered on any session-end event (§9).

## Terminal states and the exit

Each acceptance item ends `PASS`, `FAIL-<named cause>`, `BLOCKED-<named cause>`, or
`PENDING-HUMAN`. Complete when **either** every item reaches a terminal state, **or** it is
conclusively demonstrated the remainder cannot, naming the blocker for each. Items ending FAIL or
BLOCKED are residuals, not failures of the goal. Exceeding the time bound (90 min wall) is the
terminal state `BUDGET`: commit what is sound and write the marker. No improving after the marker.

**Final act — write `DONE.json` in the worktree root** (gitignored; never commit it):
`{"lane":"lane-b-inject-hook","session_id":"<this session's id>","verdict":"COMPLETE|BLOCKED|PARTIAL",
"branch":"lane/amplifier_bundle_memory-zqi","head":"<sha>","pushed":true,"items":[…],
"residuals":[…],"pending_human":[],"resources":[],"suite":"<pytest summary>"}`. If a cause stops
every deliverable, also write `BLOCKED.md` (gitignored) naming it.

## Acceptance — every item names a file or a command whose output you print

1. `modules/hooks-memory-inject/pyproject.toml` with
   `[project.entry-points."amplifier.modules"] hooks-memory-inject = "amplifier_module_hooks_memory_inject:mount"`,
   `__amplifier_module_type__ = "hook"`, and `mount(coordinator, config)` that registers ONE handler
   on `provider:request` (priority from config, default 5) and returns
   `{"name","version","provides"}`. `grep -rn 'provider:request\|session:start\|post_compact' modules/hooks-memory-inject/`
   printed — must show `provider:request` and NOT `session:start` / `context:post_compact` as
   registration targets (PINS.md: the kernel discards `session:start` results; `post_compact` is never emitted).
2. The handler returns `HookResult(action="inject_context", context_injection=<block>,
   context_injection_role="system", ephemeral=True)`; the block's first line inside the envelope is,
   verbatim: `These are memories of how this human works — hints recorded from past sessions, not
   ground truth. Verify against current reality before acting on one. To change one: /forget <id>
   or /remember <text>.` Test prints the block; `grep -c 'hints recorded from past sessions'` printed.
3. Cache-stability (session.v1 Conformance 1): two independent handler instances over the same
   `MEMORY.md` yield byte-identical `context_injection`; a regex test proves the block contains no
   ISO timestamp, no counter, no session id; a `topics/x.md` body placed in the store does NOT appear
   in the block. Printed.
4. §2 announce-once: the block ends with a static instruction of exactly the form `On your first
   reply of this session, say once: "Loaded N memories (M topics available)."` where N = count of
   `- [m-` lines and M = count of `topics/*.md`; when N=0 the instruction says
   `"No memories yet — /remember <text> to add one."` Both variants printed by tests. Honesty: the
   *saying* is model behaviour — state in `run.py` that §2 is Can't check in-process.
5. §10 fail-open: store directory absent, `MEMORY.md` unreadable (chmod 000), or any exception →
   handler returns a `HookResult` with no injection (or a one-line notice) and NEVER raises; one
   line is appended to `<error log>` where the path is `AMPLIFIER_MEMORY_ERROR_LOG` if set else
   `~/.amplifier/memory-errors.log`. Test prints the log line. False if the handler raises.
6. §9: `grep -rn 'session:end\|session_end' modules/hooks-memory-inject/` prints nothing (show the
   empty result and its exit code).
7. Size: block ≤ 10 KB for a 200-line MEMORY.md of 120-char lines (HOOKS_API default limit); test
   prints the byte length. Document the assumption in `modules/hooks-memory-inject/README.md`.
8. Usage log (store.v1 §8 caller side): exactly one `loaded` event per session (first request only),
   through the stub named above. Test prints the stub's call count across 3 requests → 1.
9. `conformance/session/inject/run.py` prints one line per clause §1, §2, §9, §10 as `Core N —
   Kept|Not yet|Broken|Can't check — <evidence>` (§2 → Can't check), exits 0; output printed. You
   may flip rows AMM-011/019/020 to CONFORMS only where the named probe passes; AMM-012 stays
   NOT-ASSERTABLE. Print `git diff --stat -- ledger/rows.yaml`.
10. `cd modules/hooks-memory-inject && uv run pytest -q` and `uv run ruff check .` printed green.
11. Item resolved, read back with `work_list`, reason printed; false if the reason asserts anything
    you know to be untrue or omits an uncorrected mistake.

## Scope-outs

Never write to any store. No `src/amplifier_memory` edits. No behavior YAML, no `bundle.md`, no
skills. Never edit `~/.amplifier/settings.yaml` or install anything into the live CLI. No network,
no services, no background processes.

## Known

- Honesty gate sentence, if needed: *"session.v1 Core N — Can't check in this lane because …"* in
  `run.py` output and the resolution reason.
- `amplifier_core` may not be importable in a plain `uv run` here; test the handler with a minimal
  fake `HookResult`/coordinator the way the status-context module's tests do (read them), and
  declare `amplifier-core` as a dependency the way that module's `pyproject.toml` does.
- Show command output inline; never assert a result without it. Print, then claim.
