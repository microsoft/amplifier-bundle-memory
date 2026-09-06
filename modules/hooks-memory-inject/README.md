# hooks-memory-inject

Puts `MEMORY.md` in front of the model on every request.

Serves `contracts/session.v1.md` (FROZEN 2026-09-06) §1, §2, §9, §10.

## What it does

On every `provider:request` the hook reads
`${AMPLIFIER_MEMORY_HOME:-~/.amplifier/memory}/MEMORY.md` and returns one
`inject_context` result, role `system`, `ephemeral=True`, carrying:

```
<system-reminder source="amplifier-memory">
These are memories of how this human works — hints recorded from past sessions, not ground truth. Verify against current reality before acting on one. To change one: `/forget <id>` or `/remember <text>`.

<MEMORY.md, verbatim>

On your first reply of this session, say once: "Loaded N memories (M topics available)."
</system-reminder>
```

`N` is the number of `- [m-…]` lines; `M` is the number of `topics/*.md`
files. When `N` is 0 the last line instead reads
`… say once: "No memories yet — /remember <text> to add one."`

Topic **bodies** are never injected (§1). The pointer lines inside
`MEMORY.md` ride along because they are part of `MEMORY.md`.

## Why `provider:request`

`session:start` is the intuitive event and the wrong one: the kernel
discards a `session:start` HookResult. `context:post_compact` is declared
but nothing emits it. `provider:request` fires immediately before every
model call, so "present in the first request and in every request after a
compaction" (§1) holds by construction — there is no first-turn flag, no
compaction listener, and nothing to get out of sync. (PINS.md, "Substrate
facts", verified 2026-09-06.)

## No cache

The block is rebuilt from disk on every request. `MEMORY.md` is capped at
200 lines (store.v1 §3) so the read is cheap, and a memory saved mid-session
shows up on the next request without any invalidation mechanism existing.
Cache-stability (§1) comes from the block being a pure function of store
content — not from caching.

## Size

**The block is as large as `MEMORY.md`, by contract.** §1 says *verbatim*,
and store.v1 §3 caps `MEMORY.md` at 200 lines with no per-line limit. At the
brief's stated worst case — 200 lines of 120 characters — the file is
~24 KB and the block is ~24 KB + ~450 bytes of framing. **It cannot be
≤ 10 KB without breaking §1.** What this module guarantees instead, and
tests, is that the block adds under 500 bytes to whatever `MEMORY.md`
already costs.

The 10 KB figure comes from `HOOKS_API.md`, which is stale on this point.
Measured against the installed amplifier-core 1.6.0:

- `coordinator.injection_size_limit` defaults to `None` (unlimited);
  `models.py` agrees ("Unlimited by default"), only `HOOKS_API.md` says
  10 KB.
- A 24 KB `inject_context` result was accepted by
  `process_hook_result` without error.

So nothing breaks today. If an operator ever sets
`session.injection_size_limit` below the block size, the kernel raises
`ValueError` — it does **not** truncate — and the injection is lost. A real
`MEMORY.md` of ~40 memories is around 2 KB; the tests measure both.

## What the `mount()` return actually does

`mount()` returns `{"name", "version", "provides"}`. Measured against
amplifier-core 1.6.0: `_session_init.py` treats any truthy `mount()` return
as a cleanup function and passes it to `coordinator.register_cleanup()`; a
non-callable registration is then skipped silently at cleanup (verified: a
dict was registered alongside a real cleanup, `coordinator.cleanup()` ran
the real one and raised nothing). Nothing of ours runs at session end (§9)
either way. If the kernel ever starts validating that slot, the metadata
should move to the module-level `MODULE_INFO` constant, which already
exists.

## Fail open (§10)

Missing store, unreadable `MEMORY.md`, or any other exception:

- the handler returns `action="continue"` with **no** injection — the
  session proceeds exactly as it would without this module,
- one line goes to `${AMPLIFIER_MEMORY_ERROR_LOG:-~/.amplifier/memory-errors.log}`,
- one line goes to the user via `user_message`.

Deduplicated per distinct reason per session, so a store that is missing all
session costs one line and not one per request. The handler never raises —
including when the error log itself is unwritable.

## Usage log

`log_usage("loaded", "MEMORY.md", session_id)` is called exactly once per
session, on the first request, and goes straight through to
`amplifier_memory.log_usage` — the one home for logic (AGENTS.md rule 11).

**Cadence: once per session = one commit per session per store.** The library
commits by default, and this is the cheapest cadence that still answers
store.v1 §8's question, "was this store loaded in that session?". Per-request
logging would put dozens of commits in a store capped at 200 lines and answer
nothing extra. Batching to session end is not an option at all: nothing runs
at session end (session.v1 §9).

The call sits inside the never-fatal `try` in `on_provider_request`, so every
failure mode inside it — no store, unwritable store, git trouble — is §10
fail-open: the block is still injected, and the session is unaffected.

## Config

| key | default | meaning |
|---|---|---|
| `priority` | `5` | hook priority on `provider:request` |

Store location and error-log location come from the environment
(`AMPLIFIER_MEMORY_HOME`, `AMPLIFIER_MEMORY_ERROR_LOG`), read on every call.

## Tests

```
uv run --offline pytest -q      # --offline: this repo's lanes run without network
uv run --offline ruff check .
```

Add `-s` to see the printed blocks, byte counts and log lines the tests
assert on.
