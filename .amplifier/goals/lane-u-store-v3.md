# Lane lane-u-store-v3 — store.v3 in the library: instances, config.yaml, sessions.jsonl, declined quote, inert

Worker session, alone, in your own worktree of `amplifier-bundle-memory` on branch
`lane/amplifier_bundle_memory-6x6`. Work ONLY here; never merge to `main`; commit early, push after
every commit. **Never touch `~/.amplifier/memory`, `~/.amplifier-memory`, or `~/.amplifier/memory-config.toml`;
never run the real `amplifier-memory` verbs, a real model call, or `update`** — temp homes only
(`AMPLIFIER_MEMORY_HOME` / explicit `home=`), fake HOME dirs for the resolution tests.

Read first: `PINS.md`, `AGENTS.md` (incl. "Lane acceptance criteria are re-derivable from durable
artefacts"), **`contracts/store.v3.md` (FROZEN 2026-09-07 — §1 Location, §2 Fixed layout, §7 declined.md,
§11 enabled; its Changelog names what changed from v2)**, `contracts/session.v4.md` §12–§13 and
`contracts/cli.v3.md` §8 (only to keep the library API they will call: `store_home(home=)`,
`instance_enabled(home)`, `record_session(home, session_id, origin)`, `session_origins(home)`,
`llm_config.load(home)`), `src/amplifier_memory/{store,inbox,llm_config}.py`, `conformance/store/run.py`.

**Work item:** `amplifier_bundle_memory-6x6` — claim it
(`work_claim(project="amplifier_bundle_memory", item_id="amplifier_bundle_memory-6x6")`), read its
description and acceptance in full, resolve with a reason written for the steward, read it back
with `work_list`, print it, and record in DONE.json the sha256 of the stored resolution.

**File ownership — edit ONLY:** `src/amplifier_memory/{store,inbox,llm_config}.py`, a new
`src/amplifier_memory/config.py` if cleaner, `src/amplifier_memory/__init__.py` (re-exports),
`tests/test_store.py`, `tests/test_inbox.py`, `tests/test_llm_config.py`, new `tests/test_config.py`,
`tests/conftest.py` (only to point defaults at temp dirs), `conformance/store/run.py`,
`conformance/suggestions/run.py` (only where a probe reads declined lines), `pyproject.toml` (only
if a YAML dependency is genuinely absent — check first), `README.md` store section. Off-limits:
`modules/**` (V), `cli.py`/`doctor.py`/`service.py` (W), `suggest.py` (X), `contracts/`, `ledger/`,
`docs/workflow/`, `evaluations/**`.

## Outcome

The library speaks store.v3: a memory INSTANCE is resolved caller `home` → `$AMPLIFIER_MEMORY_HOME`
→ `~/.amplifier-memory` (an existing `~/.amplifier/memory` still found when the default is absent);
the instance carries `config.yaml` (`enabled`, `llm: judge:`) and append-only `sessions.jsonl`
plumbing; `declined.md` lines carry the verbatim quote and dedupe matches on it; an instance with
`enabled: false` refuses every write with one line. Everything the hook, tool, CLI and job will
build on next wave exists here first, with tests and probes.

## Terminal states and the exit

Items end `PASS` / `FAIL-<cause>` / `BLOCKED-<cause>` / `PENDING-HUMAN`. 120 min wall → `BUDGET`:
commit what is sound, write the marker. **Final act: `DONE.json`** (valid JSON) in the worktree
root: `{"lane":"lane-u-store-v3","session_id":"…","verdict":"COMPLETE|BLOCKED|PARTIAL",
"branch":"lane/amplifier_bundle_memory-6x6","head":"…","pushed":true,"items":[…],"residuals":[…],
"pending_human":[],"resources":[],"suite":"…","resolution_sha256":"…"}`. On BLOCKED also write
`BLOCKED.md` with the cause.

## Acceptance — each names a durable artefact and the command that re-derives it

1. `store_home()` resolution order, all four cases, in `tests/test_store.py` (fake HOME via
   monkeypatch): `uv run pytest -q tests/test_store.py -k store_home` green.
2. `config.yaml` written by the library init with `enabled: true` and
   `llm: judge: {role: fast, provider: "", model: "", bundle: ""}`; `llm_config.load(home)` reads
   it; malformed YAML → defaults + one reason (tests in `tests/test_llm_config.py`). The TOML path
   and `memory-config.toml` are gone from `src/` (`grep -rn "memory-config.toml\|tomllib" src/` prints nothing).
3. `record_session` idempotent per session_id; `session_origins` reads back (`tests/test_config.py`
   or `test_store.py`); `sessions.jsonl` is treated as plumbing exactly as §2 says (tracked or
   ignored — quote the clause line in the test docstring).
4. `inbox.decline` writes `- <date> <text>  quote: "<quote>"`; old two-field lines still parse;
   `inbox.append` drops a candidate whose quote matches a declined quote;
   `test_declined_dedupe_is_text_only_today` is replaced by the positive test.
5. `enabled: false`: `store.save/edit/forget` and `inbox.append/accept/decline` refuse with one line
   naming the instance as inert; nothing written; no commit (tests).
6. `conformance/store/run.py`: probes for §1, §2, §7, §11 → Kept; exit 0. `conformance/suggestions/run.py` exit 0.
7. `uv run pytest -q` green (baseline 297), `uv run ruff check .` and `uv run ruff format --check .` clean.
8. Item resolved; `sha256` of `.items[0].resolution` from `amplifier-work-tracker list --project
   amplifier_bundle_memory --id amplifier_bundle_memory-6x6 --json` recorded in DONE.json.

## Known

- `contracts/store.v3.md:3` still reads "Governs: everything under ~/.amplifier/memory/" — the
  manager owns that header defect; do not touch the locked file.
- PyYAML: check `pyproject.toml`/`uv.lock` before adding it; the modules have their own pyprojects.
- Show command output inline; never assert a result without it.
