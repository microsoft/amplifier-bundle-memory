# hooks-memory-inject

Puts `MEMORY.md` in front of the model on every request.

Serves `contracts/session.v3.md` (FROZEN 2026-09-07) §1, §2, §9, §10.

## What it does

On every `provider:request` the hook reads
`${AMPLIFIER_MEMORY_HOME:-~/.amplifier/memory}/MEMORY.md` and returns one
`inject_context` result, role `system`, `ephemeral=True`, carrying:

```
<system-reminder source="amplifier-memory">
These are memories of how this human works — hints recorded from past sessions, not ground truth. Verify against current reality before acting on one. To change one: `/remember <text>` or `/memory`.

<MEMORY.md, verbatim>
</system-reminder>
```

That is the whole block. **It instructs nobody and carries no counts**, so it
is byte-identical across sessions with the same `MEMORY.md` (§1) by
construction rather than by care — which is what retired the announce
re-firing mid-session after a save.

Topic **bodies** are never injected (§1). The pointer lines inside
`MEMORY.md` ride along because they are part of `MEMORY.md`.

## The line rendered to the human (§2)

On the session's **first** `provider:request`, and on the first request after
a compaction, the hook renders exactly one line:

| when | the rendered line |
|---|---|
| 3 memories, no topics | `3 memories loaded. /memory to see them.` |
| 3 memories, 2 topics | `3 memories loaded, 2 topics. /memory to see them.` |
| 1 memory | `1 memory loaded.` |
| empty store | `no memories yet. Tell me a standing preference — "never use tabs in YAML" — and I'll keep it in every session on this device.` |
| after a compaction | `context compacted. 3 memories still loaded.` |

Every one of them is in `tests/fixtures/announce-lines.txt`, byte for byte,
and `conformance/session/inject/run.py` checks each `contract`-origin line
against the locked §2 (the two `derived` ones are reported as derived, never
as contract text).

It is rendered **by code**. The model is never asked to say it, so a reply
constraint on the human's first turn cannot suppress it — the exact failure
lane E measured 1-of-2 under v1. Device-checked:
`tests/smoke/evidence/announce-rendered-{turn1,turn2,constraint}.txt`.

### How it reaches the terminal, and why not `user_message`

The hook calls `coordinator.display_system.show_message(line, "info",
"amplifier-memory")` directly — the same `DisplaySystem`
(`amplifier_core/display.py`) that `process_hook_result` would call, one
aggregation earlier. Where there is no display system it falls back to
`HookResult.user_message`, so exactly one line is produced in either world.

`user_message` alone does **not** work here, measured against core 1.6.1: the
kernel aggregates all handlers' results for an event, and as soon as **any**
handler returns `action="inject_context"` the aggregate's `user_message` is
`None`. This hook injects by definition. The measurements, and the live
session that rendered nothing, are in
`tests/smoke/evidence/announce-rendered-why-not-user_message.txt`; the probe
is kept as a test, so the day the kernel changes, it fails.

### Detecting a compaction

`context:post_compact` is declared and never emitted, and context-simple's
compaction is *ephemeral* — the message list a hook can read never shrinks.
The one public signal is the context manager's own `context:compaction` event
(`amplifier_module_context_simple/__init__.py:1753-1755`, hooks wired at
:118). The handler for it only arms a flag; the line is rendered on the next
`provider:request`.

## Why `provider:request`

`session:start` is the intuitive event and the wrong one: the kernel
discards a `session:start` HookResult. `provider:request` fires immediately
before every model call, so "present in the first request and in every
request after a compaction" (§1) holds by construction for the **block** —
no first-turn flag, nothing to get out of sync. (PINS.md, "Substrate facts",
verified 2026-09-06.) The §2 **line** does keep per-session state, because
"once" is what §2 asks for; it lives in the hook instance, which is
session-scoped by mount.

## No cache

The block is rebuilt from disk on every request. `MEMORY.md` is capped at
200 lines (store.v2 §3) so the read is cheap, and a memory saved mid-session
shows up on the next request without any invalidation mechanism existing.
Cache-stability (§1) comes from the block being a pure function of store
content — not from caching.

## Size

**The block is as large as `MEMORY.md`, by contract.** §1 says *verbatim*,
and store.v2 §3 caps `MEMORY.md` at 200 lines with no per-line limit. At the
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
- one line goes to the user via `user_message` — **which the kernel's
  aggregation currently swallows**; see the §2 section above and the filed
  item `amplifier_bundle_memory-87j`. The error-log line is unaffected.

Deduplicated per distinct reason per session, so a store that is missing all
session costs one line and not one per request. The handler never raises —
including when the error log itself is unwritable.

## Usage log

`log_usage("loaded", "MEMORY.md", session_id)` is called exactly once per
session, on the first request, and goes straight through to
`amplifier_memory.log_usage` — the one home for logic (AGENTS.md rule 11).

**Cadence: once per session = one commit per session per store.** The library
commits by default, and this is the cheapest cadence that still answers
store.v2 §8's question, "was this store loaded in that session?". Per-request
logging would put dozens of commits in a store capped at 200 lines and answer
nothing extra. Batching to session end is not an option at all: nothing runs
at session end (session.v3 §9).

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
