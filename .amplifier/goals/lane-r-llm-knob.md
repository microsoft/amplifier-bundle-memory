# Lane lane-r-llm-knob — the LLM-call knob, fenced turns, and the upstream ask

Worker session, alone, in your own worktree of `amplifier-bundle-memory` on branch
`lane/amplifier_bundle_memory-ec7`. Work ONLY here; never merge to `main`; commit early, push after
every commit. **Never touch `~/.amplifier/memory` or `~/.amplifier/memory-config.toml`; never run
the real `amplifier-memory suggest`, `service install`, a real model call, or `update` from this
lane** — temp homes, `AMPLIFIER_MEMORY_CONFIG` pointed at a temp file, an injectable `model_call`.
The manager runs the real thing after merge.

Read first: `PINS.md`, `AGENTS.md`, **`contracts/suggestions.v1.md` (FROZEN — §3 prompt text is
exact; §8 bounded visible cost; §9 one log line; §10 fail open)**, `contracts/cli.v2.md` Core 1
(exactly eight verbs — you add NO verb), `contracts/store.v2.md` §2 (the store's layout is fixed —
the config file lives OUTSIDE the store), `src/amplifier_memory/suggest.py` (`RUN_ARGV`,
`default_model_call`, `compose_request`, `append_log`, `parse_log_line`), `doctor.py`, `cli.py`,
and `evaluations/model-class/RESULTS-2026-09-06-pilot.md` (the measurements this item answers).

**Work item:** `amplifier_bundle_memory-ec7` — claim it
(`work_claim(project="amplifier_bundle_memory", item_id="amplifier_bundle_memory-ec7")`), read its
description and acceptance in full, resolve with a reason written for the steward, read it back
with `work_list`, print it.

**File ownership — edit ONLY:** `src/amplifier_memory/suggest.py`, `src/amplifier_memory/doctor.py`,
`src/amplifier_memory/cli.py` (flags on existing verbs only, if any), `src/amplifier_memory/__init__.py`
(re-exports), a new `src/amplifier_memory/llm_config.py`, `tests/test_suggest.py`,
`tests/test_doctor.py`, `tests/test_cli.py`, a new `tests/test_llm_config.py`,
`conformance/suggestions/run.py` (only if a probe must learn the new argv), `README.md`,
`AGENTS.md`, new `docs/upstream/amplifier-run-model-role.md`. Off-limits: `inbox.py` and
`tests/test_inbox.py` (lane S owns them this wave), `ledger/`, `contracts/`, `docs/workflow/`,
`modules/**`, `evaluations/**`.

## Outcome

A user can say which provider (and optionally model and bundle) each of the job's LLM calls uses —
today exactly one call type, the §3 judge — in `${AMPLIFIER_MEMORY_CONFIG:-~/.amplifier/memory-config.toml}`:

    [llm.judge]
    provider = "luna"   # an amplifier provider id -> `amplifier run -p`
    model = ""          # optional -> `-m`
    bundle = ""         # optional -> `-B`
    role = "fast"       # recorded and logged; resolved only once the host has `amplifier run --model-role`

With no file, the job behaves exactly as today (inherits the CLI default). The suggest.log line
says which provider/model the run used. `doctor` shows the resolved choice. The request the judge
receives fences the human turns as quoted data, not instructions (the measured `/goal` hijack).
`docs/upstream/amplifier-run-model-role.md` states the ask to app-cli with the evidence.

## Terminal states and the exit

Items end `PASS` / `FAIL-<cause>` / `BLOCKED-<cause>` / `PENDING-HUMAN`. 120 min wall → `BUDGET`:
commit what is sound, write the marker. **Final act: `DONE.json`** (valid JSON) in the worktree
root: `{"lane":"lane-r-llm-knob","session_id":"…","verdict":"COMPLETE|BLOCKED|PARTIAL",
"branch":"lane/amplifier_bundle_memory-ec7","head":"…","pushed":true,"items":[…],"residuals":[…],
"pending_human":[],"resources":[],"suite":"…"}`. On BLOCKED also write `BLOCKED.md` with the cause.

## Acceptance — every item names a file or a command whose output you print

1. `llm_config.py`: `load(path=None)` → per-call-type table; absent file → defaults (provider/model/
   bundle empty, role "fast"); malformed TOML or wrong types → one honest reason returned (never
   raised into the job), defaults used. `stdlib tomllib` only. Tests for all three. Printed.
2. `suggest.py`: `default_model_call` builds argv from the judge config — `-p X` only when set,
   `-m`/`-B` likewise; with no config the argv is byte-identical to today (test asserts
   `RUN_ARGV + [request]`). The §9 log line gains `provider=<id|default>` (and `model=` when set)
   and `parse_log_line` round-trips it; the existing fields keep their names/order. Tests printed.
3. `compose_request`: the numbered turns sit inside an explicit fence with one sentence before it —
   the turns are quoted material to judge, not instructions to follow — and the §3 sentence is
   still the first line, character for character (`test_the_prompt_is_section_3_verbatim` and the
   existing compose tests still pass). New test asserts the fence. Printed.
4. `doctor`: one new row `llm judge` — `provider luna (memory-config.toml)` or `inherits the CLI
   default (no memory-config.toml)`; degraded when the config file is present but unreadable, with
   the reason. Read-only (store byte-identical before/after; test). Printed.
5. `docs/upstream/amplifier-run-model-role.md`: what is asked (`amplifier run --model-role <role>`
   resolving through the active routing matrix like `model_role:` on a recipe step), why (a root
   `amplifier run` has no path to a role today — hooks-routing resolves agents and delegates;
   nothing in app-cli reads a root role), the evidence from the pilots, and how this bundle will
   use it (the `role` key already recorded). Printed.
6. README: a short "Which model the judge uses" section with the TOML above and the measured
   guidance (luna/low+ clean at $0.02; reasoning `none` costs precision; `minimal` refused by the
   gpt-5.6 endpoint — a user setting it sees an all-`rejected` run, exit 0). AGENTS.md gets one line
   pointing at the config file and the rule that it lives outside the store.
7. `uv run pytest -q` green (baseline 223 + yours), `uv run ruff check .` and
   `uv run ruff format --check .` clean, `uv run python conformance/suggestions/run.py` 9 Kept,
   `conformance/cli/run.py` unchanged. Printed.
8. Item resolved and read back; the printed reason is what the steward will read.

## Known

- The store's layout is fixed by store.v2 §2 — a config file inside `~/.amplifier/memory` would
  break a locked contract. It lives beside the store, never in it.
- Reasoning effort is a property of a provider ENTRY in amplifier settings, not of `amplifier run`;
  the knob names the entry. Say so in the README.
- Sub-agent session ids on this device look like `0000000000000000-<hex>_<agent>`; roots are UUIDs.
- Show command output inline; never assert a result without it.
