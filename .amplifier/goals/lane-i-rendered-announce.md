# Lane lane-i-rendered-announce — the load announce is rendered by the hook, once, in code

Worker session, alone, in your own worktree of `amplifier-bundle-memory` on branch
`lane/amplifier_bundle_memory-22v`. Work ONLY here; never merge to `main`; commit early, push after
every commit (`git push -u origin HEAD`). **Never touch `~/.amplifier/memory`**; tests and PTY runs
use temp stores via `AMPLIFIER_MEMORY_HOME`.

Read first: `PINS.md`, `AGENTS.md`, `contracts/session.v2.md` (FROZEN — §1, §2, Conformance; the
exact strings live there), `docs/workflow/UX-PROPOSAL-2026-09-06.md`,
`docs/workflow/reviews/engineering-council-2026-09-06.md` (the user_message finding, with
file:line evidence), `modules/hooks-memory-inject/amplifier_module_hooks_memory_inject/__init__.py`
(ANNOUNCE_PREFIX ~:58, the block builder ~:130, `on_provider_request` ~:189, the existing
`user_message` use ~:234 — that is the channel), `conformance/session/inject/run.py`,
`tests/smoke/real_session.sh` (how lane E drove real sessions).

**Work item:** `amplifier_bundle_memory-22v` — claim it
(`work_claim(project="amplifier_bundle_memory", item_id="amplifier_bundle_memory-22v")`), read its
description (the exact strings and the evidence), and at the end `work_resolve` with a reason
written for the steward, then read it back with `work_list(...)` and print the stored reason.

**File ownership — edit ONLY:** `modules/hooks-memory-inject/**`, `conformance/session/inject/**`,
`tests/smoke/evidence/announce-*.txt` (new), `ledger/rows.yaml` rows AMM-010 and AMM-011
(disposition/notes only). Off-limits: `src/**`, `cli`, `tests/*.py` at the root, `modules/tool-memory`,
`skills/**`, contracts, docs — lane K1 runs beside you in `src/` and `cli`.

## Outcome

The first thing a human reads about memory in a session is one line the hook rendered — not a
sentence the model was told to say — and it never repeats: `3 memories loaded. /memory to see
them.` on the first request, `context compacted. 3 memories still loaded.` after a compaction,
the empty-store invitation on an empty store. The injected block carries no announce instruction
and stays byte-identical across sessions with the same `MEMORY.md`. A reply constraint on the
human's first turn cannot suppress the line, because it is not the model's to suppress.

## Terminal states and the exit

Items end `PASS` / `FAIL-<cause>` / `BLOCKED-<cause>` / `PENDING-HUMAN`. Complete when every item
is terminal or the remainder is conclusively shown impossible with the blocker named. 90 min
wall → `BUDGET`: commit what is sound, write the marker. **Final act: `DONE.json`** in the worktree
root (gitignored): `{"lane":"lane-i-rendered-announce","session_id":"…","verdict":"COMPLETE|BLOCKED|PARTIAL",
"branch":"lane/amplifier_bundle_memory-22v","head":"…","pushed":true,"items":[…],"residuals":[…],
"pending_human":[],"resources":[],"suite":"…"}`.

## Acceptance — every item names a file or a command whose output you print

1. **No instruction in the block.** `grep -n "ANNOUNCE_PREFIX\|say once" modules/hooks-memory-inject/**/__init__.py`
   prints nothing; the block for a store with 3 memories is byte-identical across two hook
   instances (sha256 printed) and contains the framing sentence from session.v2 §1 (the new
   sentence with `/edit`).
2. **Rendered once.** On the first `provider:request` the returned `HookResult.user_message` is
   exactly `3 memories loaded. /memory to see them.` (printed); on the second request
   `user_message` is `None` (printed).
3. **Variants, byte-compared to fixtures:** `1 memory loaded.` · `3 memories loaded, 2 topics.
   /memory to see them.` · `1 memory loaded, 2 topics. /memory to see them.` · empty store →
   the exact §2 empty text · after a simulated compaction (drive the hook the way the existing
   first-after-compaction detection works — read it; do not invent a new signal) →
   `context compacted. 3 memories still loaded.` All printed.
4. **Renderer-safe.** Push each string through the CLI's own Markdown/console path
   (`amplifier_app_cli.console` — lane F did exactly this for ANNOUNCE_EMPTY; find that test) and
   show the rendered text equals the intended text.
5. **Real terminal, by device.** Drive `amplifier` in a PTY against a temp store (terminal
   inspector, or `tmux` + `script`): turn 1 `Hi!` shows the rendered line once; turn 2 shows no
   memory line; a fresh session whose turn 1 is `Reply with exactly: ok` still shows the line.
   Save the captures to `tests/smoke/evidence/announce-rendered-{turn1,turn2,constraint}.txt`
   and quote the relevant lines. If the runtime does not render `user_message` for
   `provider:request` in this CLI build, that is a BLOCKED item with the file:line proof — do
   not fall back to instructing the model.
6. **Conformance kit.** `conformance/session/inject/run.py` — Core 1 and Core 2 Kept (Core 2
   no longer "Can't check": it asserts user_message on request 1, None on request 2, the
   compaction variant, and the block's byte-identity). Printed, exit 0.
7. `cd modules/hooks-memory-inject && uv run pytest -q && uv run ruff check .` green; root
   `uv run pytest -q` (baseline 133) and `uv run ruff check .` green — printed.
8. AMM-010/AMM-011 flipped to CONFORMS naming the probes; `git diff --stat -- ledger/rows.yaml`.
9. Item resolved and read back; a printed reason you know to be false is not evidence.

## Scope-outs

No edits under `src/`, `cli.py`, `modules/tool-memory`, `skills/`; the receipts (save/forget/edit
text) are lane K2's. Never touch the real store. No installs.

## Known

- Honesty gate: *"session.v2 §N — Can't check in this lane because …"* in `run.py` and the reason.
- `user_message_level`: use the level the runtime renders as a plain informational line
  (the existing failure path uses "warning"; find the right one for a normal notice and cite the
  file:line in `amplifier_app_cli` that renders it).
- Show command output inline; never assert a result without it.
