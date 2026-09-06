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

## 2026-09-06 — wave 3 (lane E) integrated on `main`; Phase 1 installed on this device

**Covers:** merge of lane E (`amplifier_bundle_memory-16w`, tip `b0bf735`, 4 commits), plus
this commit's repairs: `bundle.md`'s self-include changed from a git-URL (a cycle the loader
skips — measured by lane E) to the bundle-name form `memory:behaviors/memory-session`
(BUNDLE_GUIDE.md:87 — documented pattern, **not exercised on this host**: the install path README
and `bundle.md` document points `--app` at the behavior URI directly, which IS exercised);
`#path=` → `#subdirectory=` in `bundle.md`/`PINS.md` (the tested form); goal files moved from
`.amplifier/goals/` to `docs/workflow/goals/` as records of the briefs.

**Run by the manager session** — repository checks on `main` after the merge, and **the
installed thing on this host** (clause 7: a repository is not a deployment):

| Command | Printed |
|---|---|
| `uv run pytest -q` (root) | `84 passed in 11.88s` (wave-2 baseline 74) |
| `uv run ruff check .` | `All checks passed!` |
| `uv run python conformance/cli/run.py` | Core 7 **Kept** — `update` runs `uv tool upgrade amplifier-memory`, `amplifier bundle remove`/`add <behavior uri> --app`, skips the timer (none), ends in `doctor` |
| `bash -lc 'amplifier-memory --help'` (the installed uv tool) | eight verbs |
| `bash -lc 'amplifier-memory doctor'` on the real store | exit 0 — store OK (0/200, 0/50), inbox 0, timer INFO (Phase 2), update **OK** `a7eff90172 == main` |
| `grep -n amplifier-bundle-memory ~/.amplifier/settings.yaml` | line 25: `git+https://github.com/bkrabach/amplifier-bundle-memory@main#subdirectory=behaviors/memory-session.yaml` under `bundle.app` |
| `git -C ~/.amplifier/memory log --oneline` · `grep -c '^- \[m-' MEMORY.md` | `init` + three `usage: loaded` commits · **0 memories** — no smoke ever wrote to the real store |
| **Manager's own real sessions** against a fresh temp store (`/tmp/amm-mgr-smoke-G4NN`): session 1 `amplifier run "For future reference: never use tabs in YAML files you write for me; always two-space indentation."` | `No memories yet — /remember  to add one.` then `Saved memory m-001: "Never use tabs in YAML files; always two-space indentation." — /forget m-001 to undo.`; `MEMORY.md` has exactly 1 memory line; commit carries `quote: "For future reference: never use tabs in YAML files you write for me; always two-space indentation."` and `writer: assistant` |
| session 2 `amplifier run "In one line: what standing preferences of mine do you have loaded? Cite the memory id."` | `Loaded 1 memories (0 topics available).` and `[m-001] Never use tabs in YAML files; …` |
| `usage.jsonl` of that store | two `loaded` events, one per session (store.v1 §8; once-per-session cadence holds) |

**Contract reading after this wave** (ledger 31 rows: CONFORMS 24, GAP 2, NOT-ASSERTABLE 5):
store.v1 — Kept 9/10, Can't check §7 (Phase 2). session.v1 — Kept §1 §5 §6 §9 §10 R2; §2 §3 §4
**Can't check in-process but shown Kept in real sessions** (lane E's evidence files under
`tests/smoke/evidence/`, and the manager's own two sessions above); §7 §8 Can't check, not
exercised (no topic files existed). cli.v1 — Kept 8/9; Not yet §6 (`service` is the Phase 2
timer). Nothing Broken. Nothing Pinned open. **The AGENTS.md merge gate — one real session that
saves and one that loads, on this device — is met, by the manager's own hand.**

**What the real sessions showed that in-process checks could not** (findings, not defects
against any clause as written — each is for the 7-day review, and none changes a contract today):
1. **A standing correction and a literal reply constraint in ONE turn → no save** (lane E,
   2 of 2; my original smoke design conflated them). The correction alone saves 3 of 3 (lane E 1,
   manager 2). session.v1 §3 says "in the same turn"; its Conformance line says the task-scoped
   instruction is "in the same session". Real use will say whether the one-turn case matters.
2. **The §2 announce is an instruction in the injected block**, so a human reply constraint can
   suppress it (1 of 2 in lane E's runs), and after a mid-session save the model re-announces
   `Loaded 1 memories` (seen in my session 1) — "once" is once per count, in practice.
3. **`/remember` from a one-shot `amplifier run` is nondeterministic**: the CLI's skill-shortcut
   interception applies to interactive input, not `amplifier run`; lane E saw one run save via
   the skill (`writer: human`) and one run refuse because the typed line was not among the
   collected human turns. Interactive behaviour is untested — that is the human check below.
4. **Cosmetic:** the empty-store announce renders as `/remember  to add one.` — the `<text>`
   placeholder is swallowed as markup by the terminal renderer.
5. **Store growth:** every new session adds one `usage: loaded` commit to the real store
   (store.v1 §1 + §8 as written). `usage.jsonl` is truncated to 90 days, but git history is not;
   at ten sessions a day that is ~3,600 small commits a year. store.v1 §10 says "bounded by
   construction" — history growth is the one surface that is not. A candidate for store.v1 after
   the 7-day gate if it shows in `du`.

**Ownership note:** lane E edited four test files outside its declared set
(`tests/{conftest,test_cli,test_doctor,test_store}.py`) because its `update` change made their
assertions false, and it fixed a real defect in `test_store.py`'s CONFORMS guard (it matched
probes by bare name across kits, so a cli.v1 row could have read CONFORMS against the store
kit's probe of the same number). Accepted: each edit is named in the lane's DONE.json with its
reason; the brief's ownership was the defect.

**Installed on this machine by lane E, recorded in `WORKSPACE-MANIFEST.json`:** uv tool
`amplifier-memory` 0.1.0 (`uv tool uninstall amplifier-memory`); app-bundle line in
`~/.amplifier/settings.yaml` (`amplifier bundle remove '<uri>'`); the real store
`~/.amplifier/memory` (`rm -rf ~/.amplifier/memory` — it is the steward's from now on);
`~/.amplifier/memory-errors.log` (+4 lines from the unwritable-store checks);
`/tmp/amm-*` temp stores and `/tmp/settings.yaml.lane-e-backup`.

## 2026-09-06 — wave 4 (lane F, the writer under concurrency) integrated on `main`

**Covers:** merge of lane F (`amplifier_bundle_memory-cop`, tip `645071f`, 2 commits) — the
defect from the steward's own session (feedback drop
`2026-09-06-kicked-the-tires-transcript.md`): three parallel saves corrupted `MEMORY.md` and one
reported success without landing. Plus this commit's in-place repairs: the inject kit's
`check_core_2` and the hook README quoted the pre-fix announce string (lane F's residuals,
outside its ownership).

**Run by the manager session on `main` after the merge** (`AMPLIFIER_MEMORY_HOME` at temp dirs;
the steward's real store untouched — it still holds m-003 and m-005):

| Command | Printed |
|---|---|
| `uv run pytest -q` | `107 passed in 17.16s` (wave-3 baseline 84; +23 incl. `tests/test_concurrency.py`) |
| `uv run ruff check .` | `All checks passed!` |
| `conformance/store/run.py` | Core 1 **Kept** — "under concurrency: 8 concurrent saves → 8 well-formed lines"; Core 9 **Kept** — hand commit under the lock interleaved with 4 concurrent saves, both attributed correctly |
| Manager's own 8-thread run (`ThreadPoolExecutor(8)` × `save`) on a fresh store | ids `m-001..m-008`, 8 well-formed lines, every id present in `git show HEAD:MEMORY.md`, 9 commits (init + 8) |
| `amplifier-memory doctor` on a store seeded with the transcript's exact headless fragment | `[FAIL] store … MEMORY.md is not well-formed — 1 malformed line(s): line 2 … last commit whose MEMORY.md parsed clean: e75cc25 … remedy: amplifier-memory doctor --repair` |
| `conformance/session/inject/run.py` (after the residual repair) | Core 2 "both variants are correct (yes)" — still Can't check (model behaviour) |

**Ledger:** AMM-001 (store.v1 §1) and AMM-008 (§9) back from VIOLATION to CONFORMS with the
concurrency probes named. 31 rows: CONFORMS 24, GAP 2, NOT-ASSERTABLE 5. Nothing Broken.

**Two contract-text observations lane F surfaced, carried into the pending candidates (not
edited in place):** session.v1 §2's literal announce sentence now differs from the constant by
two backticks — what *renders* now matches the contract exactly, where before it did not; and
cli.v1 §5 "`doctor` never mutates" versus the new opt-in `doctor --repair` — the plain `doctor`
still never mutates, `--repair` is explicit, prints the diff first, and commits visibly. Both go
to the steward as edits in the session.v1/cli.v1 candidates.

**Honest limit lane F named and I confirm:** a human editing `MEMORY.md` in an editor takes no
lock, so an editor save landing inside a writer's read-modify-write is still last-writer-wins;
`doctor` now names that damage and `doctor --repair` restores it. The steward's device does not
have this fix until `amplifier-memory update` runs (wave-5 install, or the steward's own hand).

## 2026-09-06 — wave 5 (lanes G and H) integrated on `main`

**Covers:** merge of lane G (`amplifier_bundle_memory-6lp`, tip `4c80d9a`, 3 commits) then lane H
(`amplifier_bundle_memory-8b9`, tip `72bc5b9`, 3 commits), ascending churn (977 vs 1067 lines).
Both derived from the four reviews of 2026-09-06 and permitted by the locked text as written.

**Run by the manager session on `main` after both merges** (temp stores; the steward's real store
untouched):

| Command | Printed |
|---|---|
| `uv run pytest -q` (root) | `131 passed in 18.33s` (wave-4 baseline 107; +24 `tests/test_hostile.py`) |
| `uv run ruff check .` (root) | `All checks passed!` |
| `modules/tool-memory` pytest · ruff · `modules/hooks-memory-inject` pytest | `37 passed` · clean · `18 passed` |
| `conformance/store/run.py` | 9 Kept (Core 3 now carries the hostile corpus), Core 7 Can't check |
| `conformance/session/tool/run.py` | Core 5, Core 6, store.v1 Core 5 (topic path), R2 **Kept**; exit 0 |
| Manager's own hostile probes on a fresh store | U+2028 / U+0085 / CR / 131 KB text each **refused before writing** with a one-line reason; `MEMORY.md` sha256 unchanged; `git status --porcelain` empty; `quote='e'` and `'ok'` refused ("appears in a human turn only as a fragment (too short…)"); one raw `\xe9` byte appended → `doctor` exit 1, `[FAIL] store … byte offset 24 is not UTF-8; … remedy: doctor --repair`, **no traceback** |
| `conformance/session/tool/receipts.py` (module venv) | save/human: literal + `your words, verbatim`; save/assistant batch: literal + `my wording, your go-ahead: "…"` + `Saved N memories — …` + lines; list: `4 memories`, `-` bullets, `edit by hand: $EDITOR …/MEMORY.md`; no sha, no "Phase 1" |
| `grep -rn "can't write these\|You type them\|refuses any quote" skills/ modules/tool-memory/` (non-test) | 0 |

**Ledger:** 31 rows, CONFORMS 24, GAP 2 (Phase 2 timer), NOT-ASSERTABLE 5. Nothing Broken.

**Caught / noted:** the batch summary is re-rendered on every save after the first in a batch
(`Saved 2 memories …` then `Saved 3 memories …`) — accepted as running state, one line each;
lane G filed discovered work `amplifier_bundle_memory-gux` (the hook and the tool still read
`MEMORY.md` with strict UTF-8 — one bad byte would crash the hook on every request, a session.v1
§10 fail-open breach) — filed, not fixed, because `modules/**` was lane H's; lane G's quote floor
exempts a quote equal to the whole human turn (a short `/remember ok` still saves — correct); the
doctor byte-offset row lives inside the existing `store` row because cli.v1 §5's row list is
locked (the candidate adds a `well-formed` row).

**Installed on this device after the merge:** see the `update` line below.

## 2026-09-06 — wave 6 (lane J) integrated on `main`

**Covers:** merge of lane J (`amplifier_bundle_memory-gux`, 1 commit) — lane G's discovered
defect: the inject hook and the memory tool read `MEMORY.md` with strict UTF-8, so one byte a hand
edit leaves (store.v1 §9 invites hand edits) would raise inside the hook on every model request
(session.v1 §10 breach).

**Run by the manager session on `main` after the merge:**

| Command | Printed |
|---|---|
| `uv run pytest -q` (root) | `133 passed` (baseline 131) |
| `uv run ruff check .` · module ruff | clean |
| `hooks-memory-inject` pytest · `tool-memory` pytest | `19 passed` · `41 passed` |
| `grep -n 'read_text(encoding' modules/*/…/__init__.py` (MEMORY.md reads) | none — both call `amplifier_memory.read_memory_text` |
| Manager's own probe: store with `- [m-002] caf\xe9 line` appended, `on_provider_request` | no exception; block injected; contains U+FFFD; error log not written (a decodable file with a bad byte is not a failure) |
| `conformance/store/run.py` | 9 Kept, Core 7 Can't check (unchanged) |

**Ledger:** unchanged — 31 rows, CONFORMS 24, GAP 2, NOT-ASSERTABLE 5. Nothing Broken.

**Noted from the lane:** it caught and repaired a test-isolation defect in `modules/tool-memory/tests`
(a refusal-path test appended to the human's REAL `~/.amplifier/memory-errors.log`; the fixture
now sets `AMPLIFIER_MEMORY_ERROR_LOG`); it filed `amplifier_bundle_memory-zp4` (a save refused
because `MEMORY.md` carries a bad byte should name `amplifier-memory doctor`, not the error log) —
queued, small, no lane yet; `Loaded 1 memories` is session.v1 §2's literal — grammar waits on the
candidate.

## 2026-09-06 — wave 7 (lanes I and K1) integrated on `main` — the first v2 wave

**Covers:** merge of lane I (`amplifier_bundle_memory-22v`, tip `acba38f`) — the load announce
rendered by the hook in code (session.v2 §1, §2) — and lane K1 (`amplifier_bundle_memory-zx4`) —
usage without commit, `edit()`, `forgot`/`was:` in history, `record_citation()` + rate, kept per
GATE-DEFINITION, the `MEMORY.md well-formed` doctor row (store.v2 §1 §6 §8 §10; cli.v2 §2 §3 §5).
Merged I first (997436f), then K1; `ledger/rows.yaml` auto-merged (disjoint rows).

**Run by the manager session on `main` after both merges (the post-merge gate):**

| Command | Printed |
|---|---|
| `uv run pytest -q` (root) | `146 passed` (wave-6 baseline 133) |
| `uv run ruff check .` | `All checks passed!` |
| `hooks-memory-inject` pytest · `tool-memory` pytest | `36 passed` · `41 passed` |
| `conformance/session/inject/run.py` | Core 1, 2, 9, 10 **Kept** (Core 2 was Can't check since the first seed) |
| `conformance/store/run.py` · `conformance/cli/run.py` | 9 Kept · 8 Kept |
| Manager's own hook probe (3 memories) | request 1 → display system shows `3 memories loaded. /memory to see them.`; request 2 shows nothing; block carries no announce instruction; framing sentence names `/edit` |
| Manager's own library probes | three `log_usage` calls leave `git rev-list --count HEAD` unchanged, usage.jsonl gains 3 lines; `edit()` keeps `m-001`, commit body carries `action: edit` and `was:`; forget subject `forgot [m-001] point time estimates at whoev…`; `status` prints `citation rate    2 cited / 1 loaded (30d)`; `why m-001` shows `was:`, `now:`, `forgot`; `doctor` prints its own `[OK  ] MEMORY.md well-formed` row |
| PTY evidence (lane I, read by the manager) | `tests/smoke/evidence/announce-rendered-turn1.txt`: `[amplifier-memory] 3 memories loaded. /memory to see them.`; `-turn2.txt`: absent; `-constraint.txt`: present under `Reply with exactly: ok` |

**Contract reading after this wave** (ledger 31 rows: CONFORMS 24, GAP 5, NOT-ASSERTABLE 2):
session.v2 — §1 §2 §5 §6-as-v1 §9 §10 R2 Kept; §3 §6 §8 **Not yet** (lane K2: the tool's receipts,
`/edit`, `cite`); §4 §7 Can't check (model behaviour). store.v2 — Kept 9/10, §7 Not yet (Phase 2).
cli.v2 — Kept 8/9, §6 Not yet (Phase 2 timer). Nothing Broken.

**Found by lane I and not yet fixed (filed `amplifier_bundle_memory-87j`):** the kernel drops
`HookResult.user_message` from the aggregate whenever any handler on the event injects context —
so this bundle's session.v2 §10 fail-open line has **never** been displayable (measured; a session
that failed open printed nothing to the terminal). Lane I rendered the announce through the display
system directly; §10's line still goes the swallowed path. Lane L takes it next.

**Installed on this device after the merge:** `amplifier-memory update` (below) — includes the
one-time migration `store: stop tracking usage.jsonl (store.v2 §1)` on the steward's real store.

## 2026-09-06 — wave 8 (lanes K2 and L) integrated on `main` — the v2 words reach the human

**Covers:** merge of lane L (`amplifier_bundle_memory-87j`) — the session.v2 §10 fail-open line
routed through the display path (it had never been displayable: the kernel drops `user_message`
from the aggregate whenever any handler injects context) — then lane K2
(`amplifier_bundle_memory-5yi`) — the tool's v2 receipts, `/edit`, forget echo, `/memory` render,
`cite`, and the four skills (session.v2 §3 §5 §6 §8). `ledger/rows.yaml` auto-merged (disjoint rows).

**Run by the manager session on `verify/w8` after both merges (the post-merge gate), then
fast-forwarded to `main`:**

| Command | Printed |
|---|---|
| `uv run pytest -q` (root) | `146 passed` (unchanged: module suites are not discovered by the root gate — known, AMM-018/019 caveat) |
| `uv run ruff check .` | `All checks passed!` |
| `hooks-memory-inject` pytest · ruff | `42 passed` · clean |
| `tool-memory` pytest · ruff | `47 passed` · clean |
| `conformance/session/inject/run.py` | Core 1, 2, 9, 10 Kept |
| `conformance/session/tool/run.py` | Core 3 (receipt), 5, 6, store.v2 Core 5, 8 (counting), R2 **Kept**; Core 3 (calling), 4, 7, 8 (citing) Can't check (model behaviour, honesty form); exit 0 |
| `conformance/store/run.py` · `conformance/cli/run.py` | 9 Kept · 8 Kept |
| Manager's own tool probes (fresh store, fake human turns) | save/human → `saved m-001 — /forget m-001 to undo.` / `  never use tabs in YAML files` / `  your words, verbatim`; save/assistant third line `  my wording, your go-ahead: "Great, remember these for me"`; batch of three with `batch_of=3` on each → the LAST result adds `saved 3 memories — my wording, your go-ahead: "…". Reword any line and I'll replace it; /forget <id> drops one.` + the three lines, the first two carry only their receipt; `list` → `3 memories` / `- [m-…]` / `edit by hand: $EDITOR <path>`; `edit` → `edited m-001 — was: "…"` / `  now: …`; `forget` → `forgot m-002 — still in git: amplifier-memory why m-002` / `  <text>`; unknown id → `no memory m-009 — never issued. Current: m-001, m-003. Say the id.`; `cite` → `''` and one `cited` usage event; duplicate → `already remembered as m-001 — nothing changed.` |
| Manager's own hook probe (store missing, spy display) | display shows `amplifier-memory: memories not loaded (StoreMissing: … run \`amplifier-memory init\` first); session continues.`; no block injected; one error-log line |
| PTY evidence (lane L, read by the manager) | `tests/smoke/evidence/failopen-turn1.txt`: `[amplifier-memory] amplifier-memory: memories not loaded (StoreMissing: …` |
| `grep "committed \|Phase 1\|Saved memory" modules/tool-memory/**/*.py` | 0 |

**Contract reading after this wave** (ledger 31 rows: CONFORMS 27, GAP 2, NOT-ASSERTABLE 2):
session.v2 — every clause Kept except §4 and §7 (Can't check: model behaviour) and the model
halves of §3/§8 (measured by the instrument, not promised). store.v2 — Kept 9/10, §7 Not yet
(Phase 2). cli.v2 — Kept 8/9, §6 Not yet (Phase 2 timer). **Nothing Broken. Every v2 gap that a
lane could close is closed.**

**Noted from the lanes, for the manager to repair in place (docs, not code):** README still
prints the v1 receipt and lists the v1 contracts; `tests/test_concurrency.py` docstring quotes the
old receipt as history; rows AMM-013/014/016 quote the kit's old "session.v1" strings in notes;
the display system prefixes the §10 line with its own `[amplifier-memory]` label (cosmetic).
`batch_of` is a model-supplied count — the only party that knows how many lines it is saving.

**Installed on this device after the merge:** `amplifier-memory update` (below).

### Addendum, 2026-09-06 22:05Z — the installed thing was NOT showing the change

Clause 7's third leg failed silently for waves 5–8 and this record says so. After the wave-8
`update` reported `[ok] refresh the app bundle` and `[OK] update current (0f7e0fc == main)`, a real
`amplifier run … "Reply with exactly: ok"` on this device printed **v1's** `Loaded 2 memories (0
topics available).` and the store kept receiving `usage: loaded` commits (last one 21:51Z, after
the update). Three installed things exist; `update` and `doctor` see one:

| Installed thing | State found | Repaired by |
|---|---|---|
| `amplifier-memory` uv tool | current (what `doctor` compares) | — |
| bundle cache `~/.amplifier/cache/amplifier-bundle-memory-450b259c…` (+ `cache/skills/…`) — modules and skills load from here | `0afc6a8` (20:55) through `bundle remove`+`add` and `amplifier bundle update` | `git -C <cache> fetch origin && git reset --hard origin/main` → `0f7e0fc`, skills now `edit,forget,memory,remember` |
| `amplifier_memory` inside the amplifier CLI venv (`~/.local/share/uv/tools/amplifier/lib/python3.13/site-packages/`) — modules import from here | pre-K1 commit; `edit`/`record_citation` absent | `uv pip install --python …/amplifier/bin/python --refresh --reinstall-package amplifier-memory "amplifier-memory @ git+…@main"` → `- 0afc6a8 … + 0f7e0fc` |

After the repair, a real session printed `[amplifier-memory] 2 memories loaded. /memory to see
them.` and `ok`; the steward's store received the one-time `store: stop tracking usage.jsonl
(store.v2 §1)` commit (9c75d95) and `usage.jsonl` is untracked. This is also the cause of lane
I's 21:11 `AttributeError: … read_memory_text` (new hook, old library). Rows AMM-024 and AMM-026
reseeded to GAP; item `amplifier_bundle_memory-bbh` (lane M) makes `update` refresh all three and
`doctor` compare all three. Earlier CHECK-RECORD entries' "installed on this device" lines
(waves 5–7) were true of the uv tool only — read them with this caveat.
