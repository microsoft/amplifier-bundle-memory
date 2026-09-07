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

## 2026-09-06 — wave 9 (lane M) integrated on `main` — `update` refreshes what sessions run

**Covers:** merge of lane M (`amplifier_bundle_memory-bbh`) — `update` refreshes the uv tool, both
bundle cache clones, and the `amplifier_memory` library inside the amplifier CLI venv, each as its
own line; `doctor`'s update row compares all three against `git ls-remote` (cli.v2 §5, §7).

**Run by the manager session on the lane branch before merge:** `uv run pytest -q` → `167 passed`
(baseline 146); `uv run ruff check .` → clean; `conformance/cli/run.py` → Core 5 Kept, Core 7 Kept
(against a fake device: temp cache clones off a local-disk origin, temp venv).

**Then the REAL thing on this device (662a53a on main):**

| Step | Printed |
|---|---|
| `amplifier-memory update` — first run | ran the OLD binary's steps (`upgrade the CLI` · `drop the old app-bundle entry` · `refresh the app bundle`) and the OLD single-leg doctor row `[OK] update current (662a53a == main)` — the process that runs `update` is the pre-upgrade CLI until it exits |
| `amplifier-memory doctor` — after that run | `[WARN] update behind — bundle cache 0f7e0fc behind main 662a53a; env library 0f7e0fc behind main 662a53a; remedy: amplifier-memory update` — the NEW three-leg check, telling the truth |
| `amplifier-memory update` — second run | `refresh the bundle cache: …/amplifier-bundle-memory-450b259c… 0f7e0fc → 662a53a` · `refresh the bundle cache: …/cache/skills/… 0f7e0fc → 662a53a` · `refresh the library in the amplifier environment: 0f7e0fc → 662a53a` · `[OK] update current (uv tool 662a53a · bundle cache 662a53a · env library 662a53a == main)` |
| The three commits, read directly | cache clone `662a53a` · skills clone `662a53a` · venv `direct_url.json` `662a53a` |
| `amplifier run … "Reply with exactly: ok"` | `[amplifier-memory] 2 memories loaded. /memory to see them.` then `ok` |

**Contract reading after this wave** (ledger 31 rows: CONFORMS 27, GAP 2, NOT-ASSERTABLE 2):
cli.v2 §5 and §7 back to Kept; the only GAPs are the Phase-2 timer clauses. Nothing Broken.

**Found while verifying, filed as `amplifier_bundle_memory-<N>` (lane N):** the first `update`
after an upgrade runs the rest of its steps with the old code, so the cache and venv legs only
run on the second invocation. `doctor` now catches it (WARN above), but `update` should re-exec
the freshly upgraded binary after the uv-tool step so one run is enough.

**Lane residuals accepted:** `tests/test_cli.py` edited outside declared ownership (its old
assertion pinned the remove/add argv and could not survive); the three locators are public on
`amplifier_memory.doctor` but not re-exported from `__init__` (fine — no consumer yet).

## 2026-09-06 — wave 10 (lane N) integrated on `main` — one `update` is enough

**Covers:** merge of lane N (`amplifier_bundle_memory-4h6`) — after the uv-tool step upgrades the
CLI, `update` re-execs the freshly installed binary with `update --after-upgrade` so the cache and
env-library refreshes and `doctor` run with the NEW code; `--after-upgrade` skips the uv-tool step;
when re-exec is impossible, one `[info]` line names the remedy (cli.v2 §7).

**Run by the manager session on the lane branch before merge:** `uv run pytest -q` → `173 passed`
(baseline 167); `uv run ruff check .` → clean; `conformance/cli/run.py` Core 7 → **Kept** ("with the
installed commit moving across step 1, the old process ran step 1 and NOTHING else, then handed
off"); `cli.py` imports only `click` and `amplifier_memory`; `--after-upgrade` present in `cli.py`;
`os.execv` and the fallback text present in `update.py`.

**Then the REAL `update` on this device (installed 662a53a → main 147739c):** one run printed
`upgrade the CLI` · `refresh the bundle cache: … fd5d025 → 147739c` (×2) · `refresh the library in
the amplifier environment: fd5d025 → 147739c` · `[OK] update current (uv tool 147739c · bundle
cache 147739c · env library 147739c == main)`; `doctor` afterwards reads the same; a real session
printed `[amplifier-memory] 2 memories loaded. /memory to see them.`

**Honest limit of that run:** the binary that executed it was lane M's (662a53a), which already
carried the three refresh steps, so all four steps ran in the old process and **lane N's re-exec did
not fire** — it could not: the running code predates it, and no `[info]` hand-off line appeared. N's
behaviour is proven by the Core 7 probe against a fake device; the first real observation will be
the next time `main` moves past 147739c and `update` is run here — the old process should print
step 1 and hand off. Recorded so the next reader does not mistake this run for that proof.

**Contract reading after this wave** (ledger 31 rows: CONFORMS 27, GAP 2, NOT-ASSERTABLE 2):
unchanged from wave 9 — cli.v2 §7 stays Kept with the stronger probe; the two GAPs are the Phase-2
timer clauses (cli.v2 §6, store.v2 §7), gated on the 2026-09-13 reading. Nothing Broken. **The
derivable queue is empty.**

## 2026-09-06 — wave 11 (lanes P and Q) integrated on `main` — Phase 2 exists

**Covers:** merge of lane Q (`amplifier_bundle_memory-862`, f2e4fdb) and lane P
(`amplifier_bundle_memory-b0g`, 2e6f91c), plus the manager's in-place repairs in the commit that
carries this entry: four duplicate ledger ids renumbered (the suggestions.v1 Core 1–4 rows I seeded
as AMM-027..030 collided with the existing cli.v2/store.v2 rows; now AMM-037..040), rows AMM-031/032
flipped to CONFORMS after the gate below, the store kit's Core 7 probe refreshed to exercise the
decline path that now exists (it had said "Phase 1 has no decline path"), and two stale "Phase 2
(DRAFT)" sentences in `status.py` and the store kit replaced.

**Run by the manager on each lane branch before merge.** Q: `modules/hooks-memory-inject` →
`51 passed`; `modules/tool-memory` → `60 passed, 1 skipped` (the real-library arm, skipped with its
reason); ruff clean; `conformance/session/inject/run.py` and `.../tool/run.py` exit 0 with
`suggestions.v1 Core 5 — Can't check` / `Core 6 — Can't check` (no `amplifier_memory.inbox` on that
branch) — the honest form. P: `uv run pytest -q` → `220 passed` (baseline 173); `uv run ruff check .`
→ clean; `conformance/suggestions/run.py` exit 0 — Core 1, 2, 3, 4, 6, 7, 8, 9, 10 **Kept**, Core 5
Can't check there; `conformance/cli/run.py` Core 4 and Core 6 **Kept**; `conformance/store/run.py`
exit 0; `cli.py` imports only `click` and `amplifier_memory`.

**Post-merge gate on `main` (two lanes, one repository):** `uv run pytest -q` → `220 passed`;
`ruff check . modules/…` → clean; hook module `51 passed`; tool module **`61 passed`** (Q's skipped
arm now runs against P's real inbox); `conformance/session/inject/run.py` →
`suggestions.v1 Core 5 — Kept — 3 waiting → ['3 memories loaded. /memory to see them.',
'3 suggestions waiting. /memory review to see them.' …]`; `conformance/session/tool/run.py` →
`suggestions.v1 Core 6 — Kept — three waiting: byte-identical to fixtures/listing_three …`;
`ledger/checks` → `2 passed`; after the repairs the store kit prints `Core 7 — Kept — decline
appended '- 2026-09-06 never use tabs in YAML files' to declined.md; the same text offered again was
not proposed (append returned [])`.

**Device safety, checked before and after the kits ran here:** `systemctl --user list-unit-files`
and `~/.config/systemd/user/` carry no `amplifier-memory-suggest.*`; no `suggest.log` in
`~/.amplifier/memory`; `inbox.md` and `declined.md` there are 0 bytes and the store's git status is
clean. Lane P's own residual reports that during its run a conformance probe twice called `service
install` without injection and enabled a real `--user` timer on this device, then removed it; the
checks above confirm nothing of that remains. Recorded as quietly broken and fixed, not hidden.

**Contract reading after this wave** (ledger 41 rows: CONFORMS 39, NOT-ASSERTABLE 2, GAP 0):
suggestions.v1 Core 1–10 **Kept**; cli.v2 Core 6 (`service`) **Kept**; store.v2 §7 (`declined.md`)
**Kept**. The two Can't-check rows are unchanged (session.v2 Core 7/8's model-behaviour halves).
Nothing Broken. **The derivable queue is empty.** Not yet done: the installed device still runs
147739c — `update` and the first real `suggest` follow this commit, and the timer install is the
steward's irreversible call.

### Addendum — the first real runs on the device, and two defects the kits could not see

**`update` here, twice** (installed 147739c → main 835870a, then 835870a → b698a94 → 3b04348):
each run printed `[info] hand off to the upgraded binary: re-running amplifier-memory update
--after-upgrade …` and then `[skip] upgrade the CLI: skipped — already upgraded by the previous
process` — **lane N's re-exec, observed for real for the first time**, exactly as its Core 7 probe
predicted. `doctor` afterwards: `update current (uv tool 3b04348 · bundle cache 3b04348 · env
library 3b04348 == main)`; new rows `suggest timer not installed — remedy: amplifier-memory
service install` and `substrate readable at ~/.amplifier/projects (2126 project(s) recorded)`.

**First real `amplifier-memory suggest` (23:57Z):** `sessions=30 proposed=0 rejected=0 calls=30
status=degraded:model call failed for … (amplifier run --output-format json did not print JSON:
Expecting value: line 1 column 1)` ×30, exit 0, no inbox write — fail-open held (Core 10), and
the cause was measured: `amplifier run --output-format json` prints `Bundle 'anchors' prepared
successfully` on its own line **before** the JSON object. Repaired in place (b698a94:
`_json_object_in` reads the object past the preamble; test added).

**Second real run (00:04Z, bounded to 3 sessions via the library):** `proposed=0 rejected=3
status=degraded:malformed reply … not JSON` — the model answered in prose because the request
carried **only** the §3 sentence: no reply shape and, worse, no transcript. The kit's fake
`model_call` returned fixture JSON regardless of the request, so it could not see this.
Repaired in place (3b04348: `compose_request` = the §3 question, character for character and
first, then "Reply with a JSON list of {text, quote} objects and nothing else", then the
session's human turns, numbered, capped at 1500 chars each / 24000 total; `verify` still checks
quotes against the full turns; two tests added, one of which asserts the model is handed the turns).

**Third real run (00:08Z, bounded to 3 sessions):** `sessions=3 proposed=1 rejected=0
dropped_stale=0 calls=3 status=ok`. The inbox now holds `[s-001] Package tool behavior in a
reusable library, with the CLI as a thin click-based wrapper around it` with the steward's
verbatim quote from session 8dddffa7 (this manager session) — a real standing preference, said
once, found by the job. Store commit `107aa79 inbox: propose 1 suggestion(s)`. A real
`amplifier run` then printed both rendered lines to stderr: `[amplifier-memory] 2 memories
loaded. /memory to see them.` and `[amplifier-memory] 1 suggestion waiting. /memory review to see
it.` (Core 5 on the device); `amplifier-memory review --list` prints the item with its quote.

**Measured cost, for the timer decision:** one `amplifier run` call here loads the default bundle
— ~120k input tokens, **$0.27 per call** (the CLI's own usage line) — so a full daily pass at the
Core 8 ceiling is ≤30 × $0.27 ≈ **$8/day**, and on this device 305 root sessions qualified in the
last 24h, most of them automation lanes rather than the steward's own conversations. Nothing in
the contract is broken by that; it is the number the steward needs before `service install`.

**Contract reading after the addendum:** unchanged — 39 Kept, 2 Can't check, 0 Broken. Suite
after the repairs: `223 passed`, ruff clean, suggestions kit 9 Kept + Core 5 honest.

## 12 — wave 12: the LLM-call knob, fenced turns, quote-keyed dedupe (2026-09-07T04:04:56Z)

**Covers:** merge of lane S `lane/amplifier_bundle_memory-acu` @ 757e8f5 (caee5f5) and lane R
`lane/amplifier_bundle_memory-ec7` **at 1e67b0d** (bf01606), plus the manager's own repo-wide
`ruff format` (72dce54) and ledger notes (0d07d2b). Lane R's head was 91838c1, a third commit that
bundled `DONE.json` with a format reflow of 25 files the lane did not own; it was verified but not
merged — the reflow was taken as a separate manager commit, gate green before and after.

**Verified before merging (my hand, in each worktree):** R @ 91838c1: `uv run pytest -q` → 254
passed; `ruff check` clean; suggestions kit 9 Kept; cli kit 9 Kept. S @ 757e8f5: `uv run pytest -q`
→ **first run 1 failed, 228 passed**; four immediate re-runs (two with `-p no:cacheprovider`) →
229 passed each time and the failing test's name was not captured — recorded as an unreproduced
flake, not cleared; `ruff check` clean; suggestions kit 9 Kept + Core 5 Can't check; store kit 10 Kept.

**One conflict** on merge R: `conformance/suggestions/run.py` log-field list (S reflowed it one per
line; R added `provider`) — resolved to the one-per-line list with `provider` before `status`.

**Post-merge gate (main @ 72dce54):**
```
uv run pytest -q                                   260 passed
uv run ruff check . ; uv run ruff format --check . All checks passed! / 101 files already formatted
conformance/suggestions/run.py                     9 Kept, 1 Can't check (Core 5 — honesty form)
conformance/store/run.py                           10 Kept
conformance/cli/run.py                             9 Kept
uv run pytest -q ledger/checks                     2 passed
modules/hooks-memory-inject · modules/tool-memory  51 passed · 61 passed
```

**Rows:** notes added to AMM-034 (§8 — cost now steerable via the knob), AMM-040 (§4 — quote-keyed
dedupe; declined.md is text+date only, the remaining slip is pinned by test), AMM-039 (§3 — fenced
turns). No verdict changed: §8/§4/§3 were already CONFORMS; the wave hardened them.

**Device (below, appended after the install):** update → memory-config.toml → bounded suggest →
service install.

### Device, after the merge (manager's hand)

```
amplifier-memory update      hand-off fired again (lane N's re-exec); doctor: update current (uv tool b0ad9c3 · bundle cache b0ad9c3 · env library b0ad9c3 == main)
                             new row: llm judge  inherits the CLI default (no memory-config.toml)
write ~/.amplifier/memory-config.toml   [llm.judge] provider = "luna" / role = "fast"   (beside the store, never in it — store.v2 §2)
amplifier-memory doctor      llm judge  provider luna (memory-config.toml) · role fast (recorded; not resolved — `amplifier run` has no --model-role)
run_suggest(max_sessions=3)  2026-09-07T04:05:31+00:00 sessions=3 proposed=0 rejected=0 dropped_stale=0 calls=3 provider=luna status=ok
                             — the first real run through the knob: three luna calls, $0.06, nothing new to propose (the earlier s-001 was already reviewed)
amplifier-memory service install   [ok] write 2 unit file(s) · daemon-reload · enable --now amplifier-memory-suggest.timer
systemctl --user list-timers NEXT Mon 2026-09-07 00:00:00 PDT (2h 52min)  amplifier-memory-suggest.timer → amplifier-memory-suggest.service
amplifier-memory doctor      suggest timer  installed · enabled · last run 2026-09-07T04:05:31+00:00 · last outcome ok
                             llm judge      provider luna … · last run used provider=luna
```

The timer's first unattended pass is at 00:00 PDT tonight; its line lands in `~/.amplifier/memory/suggest.log`.

### The first unattended timer pass (2026-09-07, manager watched it land)

```
systemctl --user list-timers   LAST Mon 2026-09-07 00:00:01 PDT   NEXT Tue 2026-09-08 00:00:00 PDT
service                        ExecMainStart 00:00:01 PDT · ExecMainExit 00:06:10 PDT · Result=success · ExecMainStatus=0
suggest.log                    2026-09-07T07:00:01+00:00 sessions=30 proposed=17 rejected=0 dropped_stale=0 calls=30 provider=luna status=ok
inbox.md                       17 items s-002..s-018 written; `pending()`/doctor read 16 — s-018's verbatim quote carried a newline (a multi-line human turn), which broke the two-line §4 shape (a real defect, fixed below; the earlier draft of this line blamed dedupe — wrong)
doctor                         suggest timer installed · enabled · last run 2026-09-07T07:00:01+00:00 · last outcome ok
                               llm judge provider luna (memory-config.toml) · last run used provider=luna
                               inbox 16 pending, oldest 2026-09-07
```

Thirty luna calls in 6 min 9 s, ≈ $0.60, at the Core 8 ceiling. Every quote verified in code (rejected=0).
Honest note on the watching: the delegated monitor reported DONE on a misread (it took the old
`00:08:05` line for a post-07:00 one); the manager re-checked inline and waited for the real line.

### Two defects the first pass exposed, both fixed before sleep (manager's hand)

1. **A multi-line quote hid an item.** `inbox.append` now flattens `text` and `quote` to one line
   (111901a; test `test_append_flattens_a_multiline_quote_so_the_item_stays_readable`). The device's
   s-018 entry was repaired by hand in the store (commit 7d2435a); `pending()` → 17, doctor `inbox 17
   pending`.
2. **The suite depended on the machine's real timer.** 21 update/cli tests went red the moment a
   timer was installed here: `update` step 4 and `service.status()` reached `service._default_runner`,
   whose pytest guard refuses. `tests/conftest.py` now swaps that runner for the recorder and points
   `AMPLIFIER_MEMORY_UNIT_DIR` at a temp dir; `update` passes its injected runner into the step-4
   status query (1d70345). Suite 261 passed; cli kit Core 7 back to Kept; all kits exit 0.

**Quietly broken, by me:** 111901a was pushed while the suite was red — a piped `| tail -1` masked
pytest's exit code. Caught on the next read of the same output, fixed within the hour; the device
ran 111901a for ~15 minutes, during which nothing scheduled fired.

**Device now:** uv tool / bundle cache / env library `1d70345 == main`; next timer fire Tue 2026-09-08 00:00 PDT.

## 13a — wave 13, lanes B and C landed; A still running (2026-09-07T15:39:13Z)

**Covers:** merge of lane 13-B `lane/amplifier_bundle_memory-42s` @ 6dd3b9d (ef913ae) and lane 13-C
`lane/amplifier_bundle_memory-20e` @ d29da67 (0dc2628), plus the manager's in-place repairs
(AGENTS.md layout line; `chmod +x` on the new budget kit). Lane 13-A (`nyh`, the tool description
diet + `overview` + token meter) is still working at the time of this entry; a 13b entry follows it.

**Verified before merging (my hand, in each worktree):** B @ 6dd3b9d — `ls skills/` → memory,
remember; the presumption grep over skills/ bundle.md behaviors/ READMEs printed nothing; `Relay the
tool's result exactly as it stands` present in both skills; dispatch covers
overview/list/review/forget/edit/save; the two skill lines total **43 cl100k tokens** (cap 70; was
150). C @ d29da67 — framing constant is the v3 §1 sentence; no `session.v2` or `human reads` in
tracked module files; module suite 51 passed; inject kit `Core 1 — Kept — framing sentence
byte-identical to contracts/session.v3.md §1 … two instances byte-identical (337 chars)`.

**One conflict** on merge C: `modules/hooks-memory-inject/README.md` heading + table header — both
lanes retconned the same two "the human reads/sees" lines with different words. My brief listed the
file in both ownerships (a brief defect, mine). Resolved to C's wording (the module's owner).

**Post-merge gate (main @ this commit's parent):**
```
uv run --offline pytest -q                                    261 passed
uv run --offline ruff check . ; ruff format --check .          All checks passed! / 107 files already formatted
uv run --offline pytest -q ledger/checks                       2 passed
modules/hooks-memory-inject · modules/tool-memory              51 passed · 61 passed
conformance/session/inject/run.py                              Core 1, 2, 9, 10 Kept; suggestions Core 5 Kept
conformance/session/tool/run.py                                Core 5 Kept; Core 6 BROKEN (asserts the v2 four-command world — lane 13-A's file); Core 4/7 Can't check
conformance/session/budget/run.py::probe_no_presumption        BROKEN — 7 hits remain, all in modules/tool-memory (4 in __init__.py, 3 in tests) — lane 13-A's files; B's 10 skill hits are gone
```

**Rows:** AMM-010 (§1 framing) → the code now matches v3 and the kit says Kept; row flips on the 13b
entry once the whole wave is in, so the ledger moves once. AMM-015 (§6) skills half done, tool half
pending A. AMM-042 partially cleared (skills), pending A.

## 13b — wave 13 complete: lane A landed; session.v3 is Kept end to end (2026-09-07T16:05Z)

**Covers:** merge of lane 13-A `lane/amplifier_bundle_memory-nyh` @ beab6d6 (d630b8e) on top of 13a's
B + C, plus the manager's gate repairs (6c64fb5) and the ledger flip.

**Verified before merging (my hand, in A's worktree @ beab6d6):** 2 commits beyond base, pushed,
DONE.json uncommitted; tool suite 70 passed; `DESCRIPTION` 190 tokens (was 576), `INPUT_SCHEMA` text
139 (was 232); `operation` enum gains `overview`; budget kit honestly red on the lane's own four-skill
tree (524, breakdown printed) — the honesty gate the brief asked for. A also fixed a doubled
pending-suggestions count (`34` was 17×2) so the overview and `status` agree — half of item 70i.
A edited `conformance/store/run.py` and `tests/test_store.py` outside its list (the store.v2 amendment
renamed the cap remedy; nobody else owned those) — accepted.

**One conflict** on merge A: `conformance/session/budget/run.py` add/add — A created the file with
`probe_core_11`; C had already added `probe_no_presumption`. Composed: A's header, constants and probe;
C's constants, helpers and probe; C's auto-discovering `main()`; A's exit-2-on-crash guard.

**Three pair interactions the gate caught, none visible to a lane alone (all repaired in 6c64fb5):**
1. A's `skill_lines()` regex read only folded `description: >-` frontmatter; B wrote a quoted one-liner
   → the kit crashed with exit 2. Now `yaml.safe_load`.
2. A's tool kit asserts the contract's literal `relayed verbatim and never reworded` (§6); B's skills
   carried the paraphrase my brief gave them → `Core 6 — Broken`. Both skills now carry the contract's
   words. **Brief defect, mine.**
3. One `The human reads nothing.` test docstring (tool-memory tests:951) that A's own grep missed →
   `probe_no_presumption` red. Removed.

**Post-merge gate (main @ 6c64fb5):**
```
uv run --offline pytest -q                                    262 passed
uv run --offline ruff check . ; ruff format --check .          All checks passed! / 107 files already formatted
uv run --offline pytest -q ledger/checks                       2 passed
modules/hooks-memory-inject · modules/tool-memory              51 passed · 70 passed
conformance/session/inject/run.py                              Core 1, 2, 9, 10 Kept; suggestions Core 5 Kept
conformance/session/tool/run.py                                Core 3, 5, 6 Kept; suggestions Core 6 Kept; Core 4/7 Can't check (honesty form, unchanged)
conformance/session/budget/run.py                              Core 11 Kept — 409 of 500 (DESCRIPTION 190 · schema 139 · memory 18 · remember 21 · framing 41); probe_no_presumption Kept
conformance/store · cli · suggestions                          10 Kept · 9 Kept · 9 Kept + Core 5 Can't check
```

**Rows:** AMM-010, 012, 014, 015, 041, 042 → CONFORMS (each note names the lane, the command and what
it printed). No GAP rows remain against session.v3. **Not yet checked on the device:** the installed
bundle; `amplifier-memory update` follows this entry, and the steward typing `/memory` in a fresh
session is the one check only a person can perform (clause 11 #3).

## 14 — wave 14: paged markdown review/list, status's last run, init installs the timer (2026-09-07T17:10Z)

**Covers:** merge of lane 14-B `lane/amplifier_bundle_memory-78h` @ 22758fe (11d25fa) and lane 14-A
`lane/amplifier_bundle_memory-0jk` @ 4e0b4c4 (579f659), plus the two `cli.v2` §8 amendments the
steward ratified between them (e5a0307 "ok, do it"; and the device-store narrowing, "ratified.").

**Verified before merging (my hand, in each worktree):** B — `tests/test_init_timer.py` + `test_cli.py`
30 passed; `conformance/cli/run.py` Core 1–9 Kept (Core 8: fresh init installs · second init no-op ·
`--no-timer` · Phase 1 arm, all through the fake runner + temp UNIT_DIR); no shell-out from `init`;
one `service.install`; the real units under `~/.config/systemd/user` untouched (mtime 21:07 09-06;
1 timer listed before and after). A — tool suite 75 passed; tool kit Core 5/6 + suggestions Core 6
Kept against fixtures rendered from a real temp inbox; budget kit `Core 11 — Kept — 422 of 500`
(the `page` parameter cost 12 tokens); `probe_no_presumption` Kept; root 287; ruff clean; the skill
scopes the fence to overview + receipts and sends pages bare.

**One conflict** on merge A: `src/amplifier_memory/store.py` line 83 — both lanes added one `typing`
import on the same line (`TYPE_CHECKING` / `NamedTuple`). Kept both. Nothing else in the file
collided: B's edits are the `init`/`InitResult` region, A's a new `page_bounds` section at the end.

**A lane's honest residual became a contract amendment, not a buried deviation:** B added a
`device_store()` gate (timer only for `~/.amplifier/memory`) that §8 did not name, because a
temp-store `init` in any kit would otherwise enable a real device timer — twice on 09-06. Proposed
as `CANDIDATE-init-device-store.md`, ratified by the steward, applied to §8 through the guard.

**Post-merge gate (main @ 579f659):**
```
uv run --offline pytest -q                                    296 passed
uv run --offline ruff check . ; ruff format --check .          All checks passed! / 113 files already formatted
uv run --offline pytest -q ledger/checks                       2 passed
modules/hooks-memory-inject · modules/tool-memory              51 passed · 75 passed
conformance/session/tool/run.py                                Core 5, 6 Kept; suggestions Core 6 Kept; Core 4/7 Can't check (honesty form)
conformance/session/budget/run.py                              Core 11 Kept — 422 of 500 (78 spare); probe_no_presumption Kept
conformance/session/inject/run.py                              Core 1, 2, 9, 10 Kept; suggestions Core 5 Kept
conformance/cli · store · suggestions                          9 Kept · 10 Kept · 9 Kept + Core 5 Can't check
```

**Rows:** AMM-015 → CONFORMS (paged markdown list/review), AMM-027 → CONFORMS (init installs the
timer, device store only). No GAP rows remain. `status`'s `last run` now reads `suggest.log` through
doctor's own helper (item 70i, lane A's second item). **Device:** `amplifier-memory update` follows
this entry; the `init`-against-a-fresh-device arm is Can't check here (the store already exists) and
is recorded so.
