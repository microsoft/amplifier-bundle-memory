# Check record

The manager session's own re-runs of the contract check, one entry per
integrated wave, committed by the manager session itself — never through a
lane merge. Each entry names: what it covers (the merges), the exact command
run, and what it printed. The ledger (`ledger/rows.yaml`) says what the
contracts currently read; this file says who verified it and when.


## 2026-09-06 — wave 1 (lanes A and B) integrated on `main`

**Covers:** merge `ba6267e` (lane A, item `amplifier_bundle_memory-3q5`, branch tip
`5785412`) and merge `3e9a438` (lane B, item `amplifier_bundle_memory-zqi`, tip
`ea9c9fa`), plus the manager's in-place repair `f63c2e2` (three `noqa` lines and
`chmod +x` on the conformance kits) and this commit's ledger repair.

**Run by the manager session, on `main` after both merges** (`AMPLIFIER_MEMORY_HOME`
pointed at a temp dir; the real store `~/.amplifier/memory` does not exist and was not
touched):

| Command | Printed |
|---|---|
| `uv run pytest -q` | `33 passed in 1.76s` |
| `uv run ruff check .` | `All checks passed!` (after repairing 4 findings lane B's kit raised under the root ruleset — EXE001 ×1, BLE001 ×3, all in `conformance/session/inject/run.py`) |
| `cd modules/hooks-memory-inject && uv run pytest -q` | `18 passed in 0.05s` |
| `uv run python conformance/store/run.py` | exit 0 — Core 1, 2, 3, 4, 5, 6, 8, 9, 10 **Kept**; Core 7 **Can't check** (declined.md's append path is suggestions.v1, DRAFT) |
| `uv run python conformance/session/inject/run.py` (from the module dir) | exit 0 — Core 1, 9, 10 **Kept**; Core 2 **Can't check** (the announce line is model behaviour; real-host smoke, lane E) |
| `python -c "import amplifier_memory, sys; …"` | `__all__` as contracted; modules matching `click`/`amplifier_core`/`amplifier_foundation`: `[]` |

**Contract reading after this wave** (ledger `ledger/rows.yaml`, 30 rows):
store.v1 — Kept 9 of 10, Can't check 1 (Core 7). session.v1 — Kept 3 (§1, §9, §10),
Can't check 1 (§2), Not yet 6 (§3–§8, lane C). cli.v1 — Not yet 9 (lanes D, E).
Nothing Broken. Nothing Pinned open.

**What verification caught that the lanes did not self-report:**
- Root `ruff check .` was red after merging B (4 findings) — each lane's green predated
  the other's code; repaired in place, not weakened.
- The ledger had no row for store.v1 Core 3 (the manager's seeding regex missed a bold
  lead spanning a line break). Row `AMM-029` added, CONFORMS, probe `probe_core_3`
  re-run by the manager. Coverage now: every Core clause of the three locked contracts
  has a row (checked by script; 0 quote failures).
- `AMM-027` (cli.v1 §8, the `init` **verb**) carried lane A's item; lane A implemented
  the library `init()`, not the verb. Work moved to lane D (5hg); disposition stays Not yet.

**Rulings on lane B's PARTIAL** (acceptance items 6 and 7, neither a lane defect):
- Item 7 asked for a ≤10 KB block. No contract names that number; it came from a stale
  line in `amplifier-core/docs/HOOKS_API.md`, and the lane measured
  `injection_size_limit=None` on amplifier-core 1.6.0 with a 24 KB injection accepted.
  store.v1 R2 deliberately leaves per-line length unbounded. Ruled: brief defect, item
  met as intended; block overhead over `MEMORY.md` measured at 361 bytes.
- Item 6's `grep` hit only the negative test naming its own needles. Ruled: brief
  literalism; module source is clean (exit 1 on the module package).

**Residuals carried into wave 2 briefs:** hook's `_log_usage` stub → real
`amplifier_memory.log_usage`, once per session (lane C, with a dependency on the library
via the self-referential git URL); `init` sets repo-local `user.name` so a human's hand
commit in the store would be attributed to the tool — store.v1 §9 wants git to attribute
hand edits, so the writer should pass identity per commit instead (lane D, `store.py`);
`save()` grew `topic`/`topic_purpose` kwargs to enforce store.v1 §5 — accepted, noted for
the API review; module suites are not discovered by root `pytest` — the gate runs both
commands, recorded in `PINS.md`.

## 2026-09-06 — wave 2 (lanes D and C) integrated on `main`

**Covers:** merge of lane D (`amplifier_bundle_memory-5hg`, tip `697f8c2`, 3 commits) then
lane C (`amplifier_bundle_memory-yvu`, tip `3158803`, 6 commits), in that order (ascending
churn), plus this commit's repairs: tracked `__pycache__/*.pyc` untracked (they had ridden in
with lane A's first commit, before the ignore rule), and ledger row `AMM-030` added for
session.v1 R2.

**Run by the manager session on `main` after both merges** (`AMPLIFIER_MEMORY_HOME` at a temp
dir; `~/.amplifier/memory` still does not exist):

| Command | Printed |
|---|---|
| `uv run pytest -q` (root) | `74 passed in 4.95s` (wave-1 baseline 33) |
| `uv run ruff check .` (root) | `All checks passed!` |
| `cd modules/tool-memory && uv run pytest -q` · `ruff check .` | `23 passed` · `All checks passed!` |
| `cd modules/hooks-memory-inject && uv run pytest -q` | `18 passed` |
| `uv run python conformance/cli/run.py` | exit 0 — cli.v1 Core 1, 2, 3, 4, 5, 8, 9 **Kept**; Core 6 (`service`) and 7 (`update`) **Not yet** (Phase 2 timer; upgrade path is lane E) |
| `conformance/session/tool/run.py` (module dir) | exit 0 — session.v1 Core 5, 6, R2 **Kept**; Core 3, 4, 7, 8 **Can't check** (model behaviour → real-host smoke) |
| `conformance/store/run.py` · `conformance/session/inject/run.py` | unchanged: 9 Kept / 1 Can't check · 3 Kept / 1 Can't check |
| `uv run amplifier-memory --help` · `amplifier-memory bogus` | eight verbs exactly · one line on stderr, exit 2 |
| `grep -n '^import\|^from' src/amplifier_memory/cli.py` | `import click` · `import amplifier_memory` — nothing else (cli.v1 §9) |
| `grep -n 'source:' behaviors/*.yaml bundle.md` | three `git+https://…` sources, none relative or bare (AGENTS rule 4) |

**Contract reading after this wave** (ledger 31 rows: CONFORMS 23, GAP 3, NOT-ASSERTABLE 5):
store.v1 — Kept 9/10, Can't check 1 (§7, Phase 2). session.v1 — Kept §1, §5, §6, §9, §10, R2;
Can't check §2, §3, §4, §7, §8 (all model behaviour, all proven only by a real session).
cli.v1 — Kept 7/9; Not yet §6 (Phase 2), §7 (lane E). Nothing Broken. Nothing Pinned open.

**What verification caught that the lanes did not self-report:** nothing red this wave — the
lanes had both learned wave 1's lesson and run root ruff themselves. Caught by the coverage
script: session.v1 R2 had no ledger row (it sits under Reserved, and the seed covered Core
only); added as `AMM-030`, probe `check_r2`, verified Kept by the manager.

**Residuals carried to wave 3 (lane E):** cli.v1 §7's real `update` path (uv tool upgrade +
app-bundle refresh + doctor); the AGENTS.md merge gate — one real session that saves and one
that loads, on this device; the four session.v1 model-behaviour clauses; module `pyproject`s
carry a dev-only `[tool.uv.sources]` path override beside the git dependency (delete if the
steward wants none — the module suites then need network); `bundle.md`'s `default_behavior:`
is inert against the installed stack (documented in the file); `/remember`'s human-turn check
depends on the CLI's synthetic-prompt phrasing ("The user's input is: …"), recorded in
`modules/tool-memory/README.md`.
