# Lane lane-e-install-smoke — install on THIS device, prove it in a real session, finish `update`

You are a worker session, alone, in your own git worktree of `amplifier-bundle-memory` on
branch `lane/amplifier_bundle_memory-16w`. Work ONLY here for edits; never touch the main
checkout or sibling worktrees; never merge to `main`. Commit early; push after every commit
(`git push -u origin HEAD`). **This lane, uniquely, also changes the steward's live machine:**
it installs the CLI and the app bundle and creates the real store, exactly as README steps 1–4
say a user would. That is the point — a repository is not a deployment.

Read first: `PINS.md`, `AGENTS.md` (rules 3, 5, 8, 11 and "Gates before a merge"),
`contracts/cli.v1.md` (FROZEN) §5, §7, `contracts/session.v1.md` (FROZEN) §2, §3, §4, §10 and
its whole **Conformance** section (the real-session items are yours), `README.md`,
`src/amplifier_memory/doctor.py` (`update_plan`, `update_check`, `installed_commit`,
`remote_commit`, `UPDATE_STEPS`), `src/amplifier_memory/cli.py` (`update`),
`modules/tool-memory/README.md` (the `/remember` synthetic-prompt dependency),
`behaviors/memory-session.yaml`, `bundle.md`, `docs/workflow/CHECK-RECORD.md` (what is already
proven — do not re-prove it).

**Work item:** `amplifier_bundle_memory-16w` in project `amplifier_bundle_memory`. Claim with
`work_claim(project="amplifier_bundle_memory", item_id="amplifier_bundle_memory-16w")`. At the end
`work_resolve` with a reason for the steward, then **read it back** with `work_list(...)` and print
the stored reason — the printed read-back is the evidence.

**File ownership — edit ONLY:** `tests/smoke/**`, `src/amplifier_memory/update.py` (new),
`src/amplifier_memory/doctor.py` (ONLY `UPDATE_STEPS`/`update_plan` if the verified argv differs),
`src/amplifier_memory/cli.py` (ONLY the `update` command body), `src/amplifier_memory/__init__.py`
(ONLY to export what `update.py` adds), `tests/test_update.py`, `conformance/cli/run.py` (ONLY
`probe_core_7`), `README.md` (Install section only), `ledger/rows.yaml` rows AMM-011, 012, 013,
016, 017, 026 (disposition/notes only), `.gitignore` (only to ignore smoke scratch). Everything
else is off-limits.

## Outcome

On this device, `amplifier-memory` is installed as a uv tool and the bundle is composed into every
new session; `~/.amplifier/memory` exists as an empty store and `amplifier-memory doctor` exits 0.
A real session started from a shell saved a standing correction in the turn it was stated,
announced it with its id and undo, did NOT save a task-scoped instruction in the same session, and
a second real session announced the memory as loaded — with the transcripts committed as evidence.
`amplifier-memory update` performs cli.v1 §7 end to end. The steward can now open a session and
try it.

## Terminal states and the exit

Each acceptance item ends `PASS`, `FAIL-<named cause>`, `BLOCKED-<named cause>`, or
`PENDING-HUMAN`. Complete when **either** every item reaches a terminal state, **or** it is
conclusively demonstrated the remainder cannot, naming the blocker for each. Items ending FAIL or
BLOCKED are residuals, not failures of the goal. Time bound 100 min wall → terminal state `BUDGET`:
commit what is sound, write the marker. No improving after the marker.

**Final act — write `DONE.json` in the worktree root** (gitignored; never commit it):
`{"lane":"lane-e-install-smoke","session_id":"<this session's id>","verdict":"COMPLETE|BLOCKED|PARTIAL",
"branch":"lane/amplifier_bundle_memory-16w","head":"<sha>","pushed":true,"items":[…],"residuals":[…],
"pending_human":[…],"resources":[…],"suite":"<pytest summary>"}`. **`resources` must list every
change made to this machine outside the worktree** — the uv tool, the app-bundle entry, the real
store — each with its exact removal command. If a cause stops every deliverable, also write
`BLOCKED.md` (gitignored) naming it.

## Acceptance — every item names a file or a command whose output you print

1. **CLI installed (README step 2).** `uv tool install git+https://github.com/bkrabach/amplifier-bundle-memory@main`
   (the repo is private; https works through the user's git credential helper — if it does not,
   that is a BLOCKED item naming the auth error verbatim, and the remedy options: make the repo
   public, or an SSH URL). Then, from a fresh `bash -lc`, `amplifier-memory --help` lists the eight
   verbs. Printed. `resources` gets `uv tool uninstall amplifier-memory`.
2. **Bundle installed (README step 1).** Run README's `amplifier bundle add … --app` line exactly.
   Verify: `grep -n 'amplifier-bundle-memory' ~/.amplifier/settings.yaml` printed. Then prove it
   composes: with `AMPLIFIER_MEMORY_HOME` set to a temp store holding exactly one memory line,
   run `amplifier run "Reply with one line: the exact announce sentence you were instructed to say about memories, or NONE."`
   and print the output — it must contain `Loaded 1 memories`. If the root-bundle URI composes
   nothing, try `…@main#subdirectory=behaviors/memory-session.yaml`, and if THAT is what works,
   fix README step 1 and say so (AGENTS rule 5 — verified against reality, not the doc).
   `resources` gets the exact `amplifier bundle remove …` (verify the verb in `amplifier bundle --help`).
3. **Real store (README steps 3–4).** `amplifier-memory doctor` BEFORE init (real path, no store)
   → nonzero exit, printed; `amplifier-memory init` → creates `~/.amplifier/memory` (printed
   `git -C ~/.amplifier/memory log --oneline`, one line); `amplifier-memory doctor` AFTER → exit 0,
   all rows printed, the update row reading OK or INFO (say which and why). `resources` gets
   `rm -rf ~/.amplifier/memory` with the note that it is the steward's store from now on.
   **Never write a memory into the real store** — every smoke session below uses a temp store.
4. **Real-session smoke, save (AGENTS gate; session.v1 Conformance items 3 and 2).**
   `tests/smoke/real_session.sh`: `export AMPLIFIER_MEMORY_HOME=$(mktemp -d)`; `amplifier-memory init`;
   session 1: `amplifier run "For future reference: never use tabs in YAML files you write for me; always two-space indentation. Separately, for this task only, reply with exactly the word ok."`
   Save the full output to `tests/smoke/evidence/session-1.txt`. PASS iff the output contains
   `No memories yet` (the §2 empty-store announce) AND `Saved memory m-001` AND
   `MEMORY.md` in the temp store has exactly ONE `- [m-` line about tabs/YAML (the task-scoped
   "reply with exactly ok" produced NO save — discriminating pair) AND
   `git -C $AMPLIFIER_MEMORY_HOME log -1 --format=%B` carries `quote:` with the human's words.
   Print all four. **Falsifier:** any of the four missing, or the evidence file not produced by
   this run (echo the store path and `date` into the file's first line).
5. **Real-session smoke, load (session.v1 Conformance item 2).** Session 2, same temp store:
   `amplifier run "In one line: what standing preferences of mine do you have loaded, and cite the memory id."`
   → `tests/smoke/evidence/session-2.txt` contains `Loaded 1 memories` and `m-001`. Printed.
6. **`/remember` from a shell session.** Session 3, same store:
   `amplifier run "/remember always run make check before pushing"` → output contains
   `Saved memory m-002` and the store's `MEMORY.md` has the line with `writer: human` in its
   commit. Printed. If the skill shortcut does not fire in a one-shot `amplifier run` (a known
   possibility: shortcuts snapshot at startup — see `modules/tool-memory/README.md`), record the
   exact observed output, mark the item `FAIL-shortcut-not-fired-in-one-shot`, and say what a
   human sees in an interactive session instead — that becomes `pending_human`.
7. **Exit latency (Conformance).** `time amplifier run "reply ok"` ×3 with the temp store, and ×3
   as control with `AMPLIFIER_MEMORY_HOME=/nonexistent` (hook fails open, injects nothing — the
   closest available "without the bundle"; if `amplifier run --help` offers a way to exclude the
   app bundle, use that instead and say so). Print the six wall times to
   `tests/smoke/evidence/latency.txt`; PASS iff the medians differ by < 2 s. Say honestly that
   this is a 1-turn proxy for the contract's 2-turn wording if that is what you ran.
8. **Store unwritable (session.v1 §10).** `chmod 000 $AMPLIFIER_MEMORY_HOME`; `amplifier run "reply ok"`
   → completes, output has no traceback, one line appended to `~/.amplifier/memory-errors.log`
   (print `tail -1`); `chmod 755` back. Printed.
9. **`update` for real (cli.v1 §7).** `src/amplifier_memory/update.py`: `run_update()` executes
   `uv tool upgrade amplifier-memory` (verify the argv against `uv tool upgrade --help` in a test
   that prints it), refreshes the app bundle (find the real verb in `amplifier bundle --help` —
   likely `amplifier bundle update` or a remove+add; print the help you relied on), restarts the
   timer only if `service_status` says one is installed (Phase 1: none), then runs `doctor`, and
   prints the stale-in-memory note. `cli.py`'s `update` body becomes one call to it. Run
   `amplifier-memory update` on this device and print the whole output; `probe_core_7` in
   `conformance/cli/run.py` now exercises `run_update` with the subprocess calls injected (no
   network in tests) and prints Kept. `tests/test_update.py` green.
10. **Ledger.** AMM-026 → CONFORMS naming `conformance/cli/run.py::probe_core_7`. AMM-011/012/013
    (session.v1 §2, §3, §4) stay NOT-ASSERTABLE in-process but their `notes` now cite the smoke
    evidence file and date that showed them Kept in a real session; AMM-016/017 (§7, §8) note
    honestly whether the smoke exercised them (it likely did not — say so). Print
    `git diff --stat -- ledger/rows.yaml`.
11. `uv run pytest -q` (root) and `uv run ruff check .` (root) printed green; baseline 74.
12. Item resolved, read back with `work_list`, reason printed. The reason names, for the steward,
    exactly what is now installed on their machine, how to try it (`amplifier`, say a standing
    preference, watch for `Saved memory m-001`), and how to remove it. False if it asserts anything
    you know to be untrue.

## Scope-outs

Never write a memory into `~/.amplifier/memory` (smoke sessions use temp stores; the real store
stays empty for the steward). Never edit `~/.amplifier/settings.yaml` by hand — only through the
`amplifier bundle` CLI. Do not touch `modules/`, `skills/`, `behaviors/`, `bundle.md`, contracts,
docs. Do not kill or attach to any tmux session. Do not run `amplifier` interactively.

## Known

- Honesty gate: for anything a one-shot `amplifier run` cannot show, the sentence is
  *"<item> — Can't check headless; what a human sees interactively is …"* and it goes in the
  evidence file, `run.py`'s output where relevant, and `pending_human`.
- `amplifier run "<prompt>"` runs a headless one-shot session and exits when the turn ends (the
  goal-batch skill measured this). Each such run takes 30–90 s; budget accordingly.
- The bundle composes into NEW sessions only. Your own session started before the install and is
  unaffected; the manager's too. Every smoke `amplifier run` is a new session and gets it.
- Session output may include API keys? It should not — but grep every evidence file for
  `sk-`/`key`/`token` before committing and redact if found (say so).
- The repo is private; `git ls-remote https://github.com/bkrabach/amplifier-bundle-memory.git`
  worked non-interactively for the manager on this host (credential helper).
- Show command output inline; never assert a result without it. Print, then claim.
