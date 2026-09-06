# Lane lane-j-tolerant-reads — the hook and the tool read the store through the library

Worker session, alone, in your own worktree of `amplifier-bundle-memory` on branch
`lane/amplifier_bundle_memory-gux`. Work ONLY here; never merge to `main`; commit early, push after
every commit. **Never touch `~/.amplifier/memory`**; tests use temp stores.

Read first: `PINS.md`, `AGENTS.md` rule 11 (no wrapper carries logic), `contracts/session.v1.md`
(FROZEN) §1, §10 (fail open, never block), `contracts/store.v1.md` §9 (hand edits are legitimate),
`src/amplifier_memory/store.py` (`_read_text` at ~523 — the tolerant read; `list_memories`,
`verify_store`), `modules/hooks-memory-inject/amplifier_module_hooks_memory_inject/__init__.py:193`,
`modules/tool-memory/amplifier_module_tool_memory/__init__.py:330`.

**Work item:** `amplifier_bundle_memory-gux` — claim it, read its description (lane G filed it with
the exact lines), resolve with a reason for the steward, read back with `work_list`, print it.

**File ownership — edit ONLY:** `src/amplifier_memory/__init__.py` and `store.py` (ONLY to add
one public accessor, e.g. `read_memory_text(home) -> str` / `read_store_file(home, name)`,
tolerant, documented), `modules/hooks-memory-inject/**` (ONLY the read at :193 and its tests),
`modules/tool-memory/**` (ONLY the read at :330 and its tests), `tests/test_store.py` (the
accessor's test). Do NOT change the announce text, the receipts, or any wording — those are
another lane's and a contract candidate's.

## Outcome

One raw non-UTF-8 byte in `MEMORY.md` — the kind a human leaves with an editor — no longer
raises inside the inject hook on every model request or inside the memory tool. Both read the
store through one public library accessor; the hook injects the block with the undecodable byte
shown as U+FFFD (session.v1 §10: the session proceeds unchanged), the tool reports the store
problem in one sentence naming `amplifier-memory doctor`.

## Exit

PASS / FAIL-<cause> / BLOCKED-<cause>; complete when every item is terminal or shown impossible;
60 min → BUDGET. **Final act: `DONE.json`** in the worktree root (lane `lane-j-tolerant-reads`,
branch `lane/amplifier_bundle_memory-gux`, verdict, items, residuals, suite).

## Acceptance — print the evidence

1. `amplifier_memory.read_memory_text(home)` exists in `__all__`, is the tolerant read
   (`errors="replace"`), documented as the one read path wrappers use; `tests/test_store.py`
   asserts a `\xe9` byte comes back as U+FFFD and nothing raises. Printed.
2. `grep -n 'read_text(encoding' modules/hooks-memory-inject/**/__init__.py modules/tool-memory/**/__init__.py`
   prints nothing (show it); both call the accessor.
3. Hook test: store with one raw `\xe9` byte → `on_provider_request` returns an inject_context
   result whose block contains `\ufffd` and NO exception; error log untouched (a decodable file
   with a bad byte is not a failure). Printed. `cd modules/hooks-memory-inject && uv run pytest -q` green.
4. Tool test: same store → `list` returns the lines with U+FFFD and appends one line
   `store has a byte that is not UTF-8 — run amplifier-memory doctor`; `save` still works (lane G's
   library handles it). Printed. `cd modules/tool-memory && uv run pytest -q` green.
5. Root `uv run pytest -q` (baseline 131) and `uv run ruff check .` green, printed.
6. Item resolved and read back; a false printed reason is not evidence.

## Known

- Honesty gate: *"session.v1 §10 — Can't check in this lane because …"* if anything cannot be proven.
- Show command output inline; never assert a result without it.
