# Lane lane-m-update-refreshes-all-three — `update` refreshes what sessions actually run

Worker session, alone, in your own worktree of `amplifier-bundle-memory` on branch
`lane/amplifier_bundle_memory-bbh`. Work ONLY here; never merge to `main`; commit early, push after
every commit. **Never touch `~/.amplifier/memory`, never run `amplifier-memory update` or
`amplifier bundle …` against this device** — every test uses temp dirs standing in for the cache,
the venv and the store. The manager runs the real update after merge.

Read first: `PINS.md`, `AGENTS.md` (rules 10, 11), `contracts/cli.v2.md` §5 and §7 (FROZEN — your
spec), `docs/workflow/CHECK-RECORD.md` (the wave-8 addendum: the measurement that filed this item),
`src/amplifier_memory/update.py` (`StepResult` ~:73, `UpdateReport` ~:103, `run_update` ~:137 with
its injectable runner), `src/amplifier_memory/doctor.py` (`installed_commit` ~:82, `remote_commit`
~:103, `update_check` ~:108, `doctor` ~:190), `tests/test_update.py`, `tests/test_doctor.py`,
`conformance/cli/run.py`.

**Work item:** `amplifier_bundle_memory-bbh` — claim it (`work_claim(project="amplifier_bundle_memory",
item_id="amplifier_bundle_memory-bbh")`), read its description (the measured table of three installed
things and the two commands that repaired them), resolve with a reason for the steward, read it back
with `work_list`, print it.

**File ownership — edit ONLY:** `src/amplifier_memory/update.py`, `src/amplifier_memory/doctor.py`,
`src/amplifier_memory/cli.py` (formatting only), `tests/test_update.py`, `tests/test_doctor.py`,
`conformance/cli/**`, `ledger/rows.yaml` rows AMM-024 and AMM-026 (disposition/notes only),
`README.md` (the `update` and `doctor` paragraphs only). Off-limits: everything else.

## Outcome

`amplifier-memory update` leaves a device actually running `main`: the uv tool, the bundle cache
the modules and skills load from, AND the `amplifier_memory` library inside the amplifier CLI's
own environment are each refreshed and each reported as its own line with old → new commit.
`doctor`'s update row compares all three against `git ls-remote` and names the one that is behind.
A steward who runs `update` and reads `current` can trust that a new session shows the change.

## Terminal states and the exit

Items end `PASS` / `FAIL-<cause>` / `BLOCKED-<cause>` / `PENDING-HUMAN`. Complete when every item is
terminal or the remainder is conclusively shown impossible with the blocker named. 90 min wall →
`BUDGET`: commit what is sound, write the marker. **Final act: `DONE.json`** in the worktree root
(gitignored): `{"lane":"lane-m-update-refreshes-all-three","session_id":"…","verdict":"COMPLETE|BLOCKED|PARTIAL",
"branch":"lane/amplifier_bundle_memory-bbh","head":"…","pushed":true,"items":[…],"residuals":[…],
"pending_human":[],"resources":[],"suite":"…"}`.

## Acceptance — every item names a file or a command whose output you print

1. **Locate the three.** Library functions (public, importable): `bundle_cache_dirs(app_bundle_uri,
   amplifier_home=None) -> list[Path]` — both `~/.amplifier/cache/<name>-<hash>` and
   `~/.amplifier/cache/skills/<name>-<hash>` for the registered app bundle URI (read how amplifier
   derives the hash, or match by the clone's `origin` URL — print which you chose and why);
   `amplifier_env_python() -> Path | None` — `shutil.which("amplifier")` → resolve the symlink →
   the venv's `bin/python`; `commit_of_cache(dir)`, `commit_of_env_library(python)` (the git
   revision uv recorded for the installed `amplifier-memory` dist; print where uv records it).
   Tests with fake layouts; printed.
2. **`update` refreshes all three, each a `StepResult` line:** `upgrade the CLI` (unchanged) ·
   `refresh the bundle cache: <dir> <old7> → <new7>` for each cache dir (`git fetch origin` then
   `git reset --hard origin/<pinned ref>`; if a dir is not a git clone, fall back to the existing
   remove/add and say so) · `refresh the library in the amplifier environment: <old7> → <new7>`
   (`uv pip install --python <venv python> --refresh --reinstall-package amplifier-memory
   "amplifier-memory @ git+<REPO_URL>@<ref>"`; when no amplifier venv is found, one WARN line and the
   other steps still run). All shell-outs through the injectable runner so tests never touch the
   network or the device. Printed with a fake runner recording the argv.
3. **`doctor` update row reads all three.** `update_check` takes the three installed commits and
   the remote; OK names all three equal (`uv tool 0f7e0fc · bundle cache 0f7e0fc · env library
   0f7e0fc == main`); WARN names WHICH is behind (`bundle cache 0afc6a8 behind main 0f7e0fc`) with
   remedy `amplifier-memory update`; INFO offline unchanged; a missing venv or cache is INFO
   `not found`, never RED. `doctor` stays read-only (byte-identical store before/after). Printed.
4. **Stale-in-memory note** stays at the end of `update`. Printed.
5. **Conformance.** `conformance/cli/run.py` Core 5 and Core 7 probes extended for the three-way
   check and the three refresh lines (fake layouts); exit 0, Kept (printed). Root `uv run pytest -q`
   (baseline 146) + `uv run ruff check .` green; `cli.py` still imports only `click` and
   `amplifier_memory` (printed grep).
6. Rows AMM-024/AMM-026 flipped GAP → CONFORMS naming the probes; `git diff --stat --
   ledger/rows.yaml` printed.
7. Item resolved and read back; a printed reason you know to be false is not evidence.

## Scope-outs

No edits under `modules/`, `skills/`, `store.py`. Never run the real `update`, `uv tool`, `uv pip`,
or `amplifier bundle` commands against this device — fake runner only. No installs.

## Known

- Honesty gate: *"cli.v2 §N — Can't check in this lane because …"* in `run.py` and the reason.
- The manager repaired this device by hand at 22:00Z with exactly the two commands in the item —
  they are proven to work; encode them, do not redesign them.
- Show command output inline; never assert a result without it.
