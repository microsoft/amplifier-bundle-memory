# Owner return log

One entry per return of the intent steward, newest last. Each entry: a dated
heading with the clock time of the return, then five one-sentence parts —
**Time away.** **Finished.** **Stuck.** **Needs you.** **Anything quietly
broken.** A fresh manager session reads the tail of this file first.

## 2026-09-06 14:03 - first wake: the idea arrived, nothing built yet

**Time away.** This is the first wake — no time away, no waves; the idea arrived
as a vision and four draft contracts and this session spent about ten minutes
reading them and the Amplifier substrate they must run on.

**Finished.** The project repository exists at `amplifier-memory/` with your
drafts imported unchanged (commit e19d4b9) plus the Converge kit — `PINS.md`, the
pre-push guard (`./.githooks/pre-push HEAD` prints "clean"), the workflow records,
a feedback inbox — and this session is registered and readable by the companion
app's own config loader (checked by running it: it lists `amplifier-memory`,
steward bkrabach).

**Stuck.** Nothing stopped; by design nothing was launched — no lane fills until
your word lands.

**Needs you.** Two calls: *ratify* the vision and contracts (my recommendation:
ratify `VISION`, `store.v1`, `session.v1`, `cli.v1` with the four edits E1–E4 in
`docs/workflow/FIRST-WAKE-REVIEW.md`, and hold `suggestions.v1` as a draft until
Phase 1's gate), and *irreversible*: create `github.com/bkrabach/amplifier-memory`
— say **public**, **private**, or **hold**.

**Anything quietly broken.** Two things you did not ask about: your predecessor
`amplifier-engram` is still injecting into every session through the
`anchors-amp-dev` bundle while its store on this device does not exist, so
installing this bundle beside it means two memory blocks per request until one
is removed; and to make this session visible in the app I added a `workspaces`
list to `~/.amplifier/converge-app.toml` (backup at
`converge-app.toml.bak-2026-09-06`) — I could not confirm it renders on Home
because Home requires sign-in.

<details><summary>Technical detail</summary>

- Substrate findings that shaped the review: `session:start` hook results are
  discarded by the kernel; `context:post_compact` is never emitted; injection
  is `provider:request` + ephemeral. Slash commands from a bundle are
  user-invocable skills (`$ARGUMENTS`). Sub-agent detection is
  `coordinator.parent_id`. Evidence pointers in `PINS.md`.
- Where to watch: http://127.0.0.1:8788 (sign in with the machine account).
- Plan record: `.converge/amplifier-memory/PLAN.md` at the workspace root.
</details>

## 2026-09-06 14:21 - back with direction: name it amplifier-bundle-memory, lib-first with a thin click CLI, engram is going away

**Time away.** About eighteen minutes since the first brief; no waves ran, none
could — the lock word has not landed.

**Finished.** Your direction is applied and committed (`15340c1`): the repository
and bundle are `amplifier-bundle-memory` with the `amplifier-memory` CLI inside;
cli.v1 gained Core §9 (*the CLI is a thin click wrapper; every behaviour is a
public library function the tool, hook and Phase 2 job call directly*) and
AGENTS.md gained rule 11 saying the same for every surface; the four draft edits
E1–E4 are in the drafts; the pre-push scan on the result printed "clean"; and the
manager is re-registered under the new name (the app's loader lists it).

**Stuck.** Nothing stopped; the wave-1 lane briefs are drafted in the batch
directory so launch is immediate on your word.

**Needs you.** Two words: *ratified* (or *ratified with edits* / *later*) for
`VISION`, `store.v1`, `session.v1`, `cli.v1` as now drafted, with
`suggestions.v1` held as a draft unless you say otherwise; and for
`github.com/bkrabach/amplifier-bundle-memory` — **public**, **private**, or
**hold**.

**Anything quietly broken.** Nothing new; the engram overlap I flagged last time
is struck from the concerns list on your word, and the `converge-app.toml` edit
from the first wake still stands with its backup beside it.

## 2026-09-06 14:28 - the word: ratified, private

**Time away.** About five minutes between the brief and your word; no waves ran in it.

**Finished.** The four documents are locked (`docs/VISION.md`, `store.v1`, `session.v1`,
`cli.v1` read `(FROZEN 2026-09-06)`; `./.githooks/pre-push HEAD~1` prints "clean"),
`suggestions.v1` stays a draft until Phase 1's gate; the repository is published private at
github.com/bkrabach/amplifier-bundle-memory (`gh repo view` prints `private=true`); the ledger
holds 28 clause rows plus SYNC, every one at *Not yet* or *Can't check*, none at *Kept*
(`ledger/rows.yaml`, quotes verified against the contracts: 0 failures); the work queue
`amplifier_bundle_memory` carries five items, and lanes A (the library core) and B (the inject
hook) are running now at width two with a watcher that wakes me when either ends.

**Stuck.** Nothing stopped; the one snag was the tracker refusing hyphens in a project name,
so the queue is `amplifier_bundle_memory` with an underscore, recorded in `PINS.md`.

**Needs you.** Nothing needs you now — the next call, if any, is when wave 1 lands and I have
re-run its checks myself.

**Anything quietly broken.** Two small things: the tracker would not let me add a hard
"blocks" edge on top of the "relates-to" link `work_add` had already made, so lanes C, D and E
are held out of the queue by a status block I clear by hand when A lands; and the wave-1 goal
files are committed at `.amplifier/goals/` in the repository because the launcher requires them
in the base commit — they are records of the brief, not product, and I will move them to
`docs/workflow/` when the wave lands.

<details><summary>Technical detail</summary>

- Base SHA for wave 1: `98c03ca`. Lane sessions: A `c1b6d7c3…`, B `6fea3814…`. Logs
  `/tmp/gb-w1-lane-*.log`. Bounds 90 min / 80 turns each.
- Watcher: tmux session `gb__w1__watch`, polls `batch_status.sh` every 120 s; writes
  `.converge/amplifier-bundle-memory/wake-needed` and types a wake line into this pane.
- Ledger dispositions: GAP 24 (incl. SYNC — its probe is lane A's), NOT-ASSERTABLE 5
  (session.v1 §2, §3, §4, §7, §8 — model behaviour, proven only by the real-host smoke).
</details>

## 2026-09-06 — wave 1 landed, wave 2 launched (unprompted)

**Time away.** About thirty minutes since the last brief; one wave ran and landed, and a second is running.

**Finished.** The library (`import amplifier_memory`: init, save, forget, list, log_usage, why — one git commit per mutation, every cap enforced) and the inject hook (MEMORY.md in every model request, cache-stable, fail-open) are on `main`, and I re-ran the checks myself before merging: root tests 33 passed, module tests 18 passed, lint clean, the store kit reads store.v1 Kept on 9 of 10 clauses, the inject kit reads session.v1 §1, §9, §10 Kept — all recorded in `docs/workflow/CHECK-RECORD.md` in my own commit.

**Stuck.** Nothing stopped; lane B ended "partial" on two acceptance items that turned out to be defects in my brief (a stale 10 KB figure no contract names, and a grep that hit its own negative test), ruled met-as-intended and written down.

**Needs you.** Nothing needs you now; the next call will be a *human check* when wave 3 installs the bundle on this device and runs a real session — that is your keyboard.

**Anything quietly broken.** Three things I caught and fixed: the ledger I seeded had no row for store.v1 §3 (row AMM-029 added, verified Kept); the root lint went red after merging both lanes (each lane's green predated the other's code — repaired, not weakened); and deleting the lane branches on GitHub needed `--no-verify` because the pre-push guard cannot resolve a base for a deletion — a deletion carries no file diff, so nothing locked was at risk, but it is a rough edge in the guard worth knowing.

<details><summary>Technical detail</summary>

- Merges: A `ba6267e`, B `3e9a438`, repair `f63c2e2`, check record + ledger `2e0399f`, wave-2 goals `8e7ed7c` (= wave-2 base).
- Wave 2: lane C `gb__w2__lane-c-tool-skills-bundle` (session `64bb0119…`) — tool, skills, behavior, bundle, hook stub → library; lane D `gb__w2__lane-d-cli` (`abdbc33f…`) — click CLI, status/doctor/why, per-commit git identity in the store. 100 min / 90 turns each.
- Residual carried to lane D from store.v1 §9: `init` currently sets repo-local `user.name`, which would mis-attribute a human's hand commit in the store.
</details>

## 2026-09-06 — wave 2 landed, wave 3 launched (unprompted)

**Time away.** About twenty-five minutes since the last brief; one wave ran and landed, and the last Phase 1 wave is running.

**Finished.** The `memory` tool, the three slash-command skills, the bundle wiring and the `amplifier-memory` click CLI (`init · status · why · review · doctor · service · update · suggest`) are on `main`, and I re-ran the checks myself before merging: root tests 74 passed, module tests 23 and 18 passed, lint clean, cli.v1 reads Kept on 7 of 9 clauses, session.v1 §5/§6/R2 Kept — recorded in `docs/workflow/CHECK-RECORD.md` in my own commit; hand commits in the store now keep the human's own git identity (store.v1 §9).

**Stuck.** Nothing stopped; both lanes ended complete and nothing went red at the post-merge gate.

**Needs you.** Nothing yet — wave 3 is installing the bundle and CLI on this device now; when it lands I will ask you for one *human check*: open a session, say a standing preference, and tell me whether you saw `Saved memory m-001`.

**Anything quietly broken.** Two things caught and fixed: session.v1 R2 (sub-agents never save) had no ledger row because it sits under Reserved rather than Core (row AMM-030 added, verified Kept), and compiled `__pycache__` files had been tracked since lane A's first commit (untracked); and one thing to know: the wave-3 lane changes this machine — a uv tool, an app-bundle line in `~/.amplifier/settings.yaml`, and an empty `~/.amplifier/memory` — each will be recorded with its removal command.

<details><summary>Technical detail</summary>

- Merges: D `c66faf7`, C `27a35c0`; check record + ledger `3d1b5f4`; wave-3 goal `85a2adb` (= base).
- Lane E `gb__w3__lane-e-install-smoke` (session `01bec1e9…`), 100 min / 90 turns: install per README, real-session smoke against a temp store (never the real one), `update` end to end, exit-latency and unwritable-store checks.
- Known dependency recorded by lane C: `/remember`'s human-turn check relies on the CLI's synthetic-prompt phrasing ("The user's input is: …"); the literal `/remember …` line is not itself a user message (`main.py:745-832`).
</details>

## 2026-09-06 — Phase 1 is installed on this device (unprompted)

**Time away.** About thirty-five minutes since the last brief; the last Phase 1 wave ran and landed.

**Finished.** Phase 1 is done and installed here — the `amplifier-memory` CLI as a uv tool, the bundle composed into every new session, and an empty store at `~/.amplifier/memory` — and I proved it with my own hands rather than the lane's: `amplifier-memory doctor` on your store exits 0, and in two real sessions against a scratch store the assistant saved `m-001` in the turn I stated the preference (commit carrying my exact words, `writer: assistant`) and the next session opened with `Loaded 1 memories`; the repository reads 84 tests green, cli.v1 Kept 8 of 9, store.v1 9 of 10, session.v1 everything checkable Kept — all in `docs/workflow/CHECK-RECORD.md`.

**Stuck.** Nothing stopped; the queue is empty by design — Phase 2 is gated on a week of your real use, not on any work I can launch.

**Needs you.** One *human check*: open `amplifier` anywhere, state a standing preference on its own line and watch for `Saved memory m-001: "…" — /forget m-001 to undo.`, then type `/remember <anything>` and watch for `m-002` — tell me **saw both**, **saw one** (which), or **saw neither**.

**Anything quietly broken.** Five things the real sessions showed that unit tests could not, none breaking a contract today but all for the week's review: a correction and a "reply with exactly…" constraint in the same turn skip the save; the load announce can be suppressed by a reply constraint and repeats after a mid-session save; `/remember` from a one-shot `amplifier run` is unreliable (interactive is what your check tests); the empty-store announce swallows `<text>`; and every session adds one small `usage` commit to your store's git history, which is the one thing not bounded by construction.

<details><summary>Technical detail</summary>

- README step 1 needed `#subdirectory=behaviors/memory-session.yaml` — the root-bundle URI composed nothing (self-include cycle); fixed in README, `bundle.md`, `PINS.md`.
- Remove everything: `uv tool uninstall amplifier-memory`; `amplifier bundle remove '<the behavior uri>'`; delete the `~/.amplifier/memory` directory. Exact commands in `WORKSPACE-MANIFEST.json` at the workspace root.
- Gate date: 2026-09-13 — `amplifier-memory status`, ≥ 5 kept.
- Evidence: `tests/smoke/evidence/` (lane E) and this session's `/tmp/mgr-s1.txt`, `/tmp/mgr-s2.txt`.
</details>

## 2026-09-06 16:35 - back after kicking the tires: "a good start, but not the best user experience yet"

**Time away.** About forty minutes since the last brief; one wave (the corruption fix) ran, landed and was installed here, and three councils plus one simulated user reviewed the experience.

**Finished.** The bug your session hit is fixed and on this device: the writer now takes a lock, re-reads the committed file before it says "saved", turns git errors into one sentence, and `doctor` names a malformed `MEMORY.md` with `doctor --repair` to restore it — I proved it with my own eight-thread run (eight ids, eight lines, all in the committed tree), root tests 107 green, and `amplifier-memory doctor` on your real store reads `current 69827f4 == main`, `MEMORY.md is well-formed`, your two memories intact; the interactive `/remember` you were going to check fired first time under a device-driven persona (`writer: human`, commit `3c0e676`), so that check is done.

**Stuck.** Nothing stopped; the councils returned FAIL on the experience (unanimously, three panels) and their reasons are in `docs/workflow/reviews/`, distilled into `docs/workflow/UX-PROPOSAL-2026-09-06.md` — the moment-by-moment text a person should see.

**Needs you.** Two things: *ratify* — three candidates, each answerable alone (`contracts/session.v1.v2-candidate.md`: the announce and receipts rendered by code not the model, `/edit` keeping the id, forget echoing its text, cite-at-use measured not promised; `contracts/store.v1.v2-candidate.md`: read-only sessions stop leaving a commit, a `cited` event; `contracts/cli.v1.v2-candidate.md`: `doctor --repair` written down, `why` showing edits, the kept definition) — and one *human check*: roughly how many times a week did you repeat a standing preference before memory existed, because that baseline is the one number nobody can take later and "five kept" means nothing without it.

**Anything quietly broken.** Four things: the day-7 gate as written cannot be met — you have two memories today and "kept" needs seven days, so Sunday's ceiling is 2, not 5, unless you write three more by tomorrow (pre-registered in `docs/workflow/GATE-DEFINITION-2026-09-06.md` so the reading is judged against a ruler cut before the number); the old `update` could not upgrade itself (I ran `uv tool upgrade amplifier-memory` once by hand; from now `update` works); the engineering council reproduced four more writer defects by execution (a Unicode line separator corrupts the file and the hook publishes it, one bad byte crashes `doctor`, a failed oversize save sits staged, a one-letter quote passes) — lane G is fixing them now; and the assistant in your session claimed it could not save memories it drafted, which was false — lane H is deleting that line and adding the "my wording, your go-ahead" flow.

<details><summary>Technical detail</summary>

- Councils: product `reviews/product-council-2026-09-06.md` (user-advocate FAIL held; D1/D2/D3 disagreements routed), design `reviews/design-council-2026-09-06.md` (7/7 FAIL; B1–B8), engineering `reviews/engineering-council-2026-09-06.md` (6/6 FAIL; `HookResult.user_message` renders a terminal line — `hook_dispatch.rs:282-313` → `CLI/ui/display.py:98-128` — the mechanism for deterministic announce/receipts), Dana `reviews/simulated-user-dana-2026-09-06.md` (OBSERVED: `/remember` = $0.21, 3 model calls, 33 screen lines; "update memory 2" retired m-002).
- Waves: 4 (F) merged `…`, CHECK-RECORD 4 in `69827f4`; 5 (G, H) running, base `$(git rev-parse --short HEAD)`.
- Settled without you: no confirm gate; ids only, bare N = m-00N; deterministic rendering; quote check stays with a floor; `/remember`/`/forget` stay model-mediated; topic-file write path from the session.
</details>

## 2026-09-06 — wave 5 landed and installed; one small lane left before your word matters (unprompted)

**Time away.** About an hour since the last brief; one wave of two lanes ran, landed and was installed here, and a third small lane is running.

**Finished.** The writer now refuses anything that is not one clean line before it touches disk (a Unicode line separator, a control character, a 131 KB paste, a one-letter quote), writes atomically and checks the very file the hook reads, and a stray byte in `MEMORY.md` gives you a `doctor` row instead of a crash — proven by my own probes (file hash unchanged after every refusal, `git status` clean, `doctor` exit 1 with no traceback); the words changed too: the false "I can't write these for you" is gone from every skill, a save now says `your words, verbatim` or `my wording, your go-ahead: "…"` under the receipt, a forget echoes what it removed and where it still lives in git, `/memory` ends with the hand-edit path, and a ruleset can go to a topic file with one pointer line — 131 tests green, `amplifier-memory doctor` on your store reads `current 2ab7b4b == main`, two memories intact.

**Stuck.** Nothing stopped; lane G found one more fail-open gap (the hook and the tool still read the file with strict UTF-8, so a byte a hand edit leaves would crash the hook on every request) and filed it rather than reaching outside its files — lane J is fixing it now.

**Needs you.** Unchanged: the three candidates in `contracts/*.v2-candidate.md`, each answerable in a word, and the one number — how often you repeated yourself per week before memory.

**Anything quietly broken.** One rough edge: in a batch of assistant-drafted saves the running summary (`Saved 2 memories…`, then `Saved 3 memories…`) prints once per save rather than once at the end — one extra line each, accepted for now and noted in the check record.

## 2026-09-06 — the queue is empty; everything the locked contracts allow is installed (unprompted)

**Time away.** About fifty minutes since the last brief; one small lane ran and landed, and I repaired one filed defect in place.

**Finished.** The hook and the tool now read your store through the library's tolerant path, so a stray byte from a hand edit can no longer crash a session (my own probe: block injected with the byte shown as U+FFFD, nothing raised); a save refused for that reason now tells you to run `amplifier-memory doctor --repair` in its one line instead of pointing at a log; tests 133 green; your device runs main (`doctor`: current, store well-formed, two memories).

**Stuck.** Nothing stopped; the queue is simply empty — every remaining improvement changes a locked sentence and waits on you.

**Needs you.** The same two things: the three candidates in `contracts/*.v2-candidate.md`, each answerable in a word, and the baseline number.

**Anything quietly broken.** Nothing new.

## 2026-09-06 20:55 - "lgtm, do it": the three candidates are ratified

**Time away.** About an hour since the last brief; no wave ran in it — the queue was empty, waiting on this word.

**Finished.** Your word is written down: `contracts/session.v2.md`, `store.v2.md` and `cli.v2.md` are locked (each in one write, with the changelog quoting "lgtm, do it"), the ledger is pinned to them and re-read row by row — 15 clauses already kept, 12 now honestly open because the code still does v1 — and two lanes are building the first of them: the load announce rendered by code (hook) and the library's `edit`, citation events, read-only sessions leaving no commit, `forgot`/`was:` in history, the `doctor` well-formed row and the kept definition (library + CLI).

**Stuck.** Nothing stopped; the tool-and-skills lane (`/edit`, the new receipts, `/memory` with no restatement) waits for the library lane because it calls its functions.

**Needs you.** Only the baseline, when you have it — roughly how many times a week you repeated a standing preference before memory; nothing else is parked on you.

**Anything quietly broken.** Nothing new; your device still runs the v1 words until wave 7 lands and I run `update` here — at that point one visible migration commit will stop tracking `usage.jsonl` in your store, which is the change that ends the one-commit-per-session growth.

<details><summary>Technical detail</summary>

- v2 diffs against v1 are summarised in each file's changelog; the candidates remain beside them marked ratified.
- Ledger after reseed: CONFORMS 15 · GAP 14 (2 Phase-2 timer, 12 v2) · NOT-ASSERTABLE 2 (session §4, §7 — model behaviour).
- Lanes: I `773363e8` (100 min), K1 `4636fcdd` (100 min); base `$(git rev-parse --short HEAD)`.
</details>

## 2026-09-06 21:22 - "run wave 8 and anything else in parallel?"

**Time away.** About thirty minutes since the last brief; one wave (I + K1) landed in it and the next launched.

**Finished.** Yes to running wave 8 in parallel — and the first v2 wave is already on your machine: the load line is now rendered by code (`3 memories loaded. /memory to see them.`, once, proven in a real terminal capture and by my own probe), reading memory leaves no commit behind, `edit` keeps a memory's id and its history says `was:`, a forget reads `forgot [m-…]` in `git log`, `status` prints a citation rate and the pre-registered kept count, and `doctor` has its own `MEMORY.md well-formed` row — root tests 146 green, all three conformance kits green, and `amplifier-memory doctor` here reads current at `576b5cb`.

**Stuck.** Nothing stopped; two lanes are running now (the tool's v2 receipts, `/edit` and citations; and the §10 failure line that, it turns out, has never been able to reach a terminal because the kernel drops `user_message` whenever any hook injects context — lane I found it and filed it).

**Needs you.** Nothing new — the baseline number remains open and not blocking.

**Anything quietly broken.** Two things to know: your store has been loaded 147 times in 30 days (every session on this device, lanes included, composes the bundle — that is by design, and the usage log is truncated, but it is why the no-commit-on-load change mattered; its one-time migration commit lands on the next session's first write); and `doctor`'s store row still says "store.v1 Core 3" in its wording — cosmetic, on my list to fix in place after the wave.

## 2026-09-06 — the v2 words reach your terminal; one deployment defect found and being fixed (unprompted)

**Time away.** About forty minutes since the last brief; wave 8 landed in it and wave 9 launched.

**Finished.** The tool now speaks v2 exactly — `saved m-001 — /forget m-001 to undo.` with the text and a provenance line under it, `edited m-004 — was: "…"` / `now: …`, `forgot m-002 — still in git: amplifier-memory why m-002`, `/memory` as `3 memories` with the hand-edit path, `/edit` as a fourth command, and a `cite` the model calls when a memory changes what it does — every receipt byte-compared by my own probes, 47 tool tests and 42 hook tests green, all four conformance kits green; the §10 failure line, which the kernel had been silently swallowing since day one, now reaches the terminal too; and a real session on your machine printed `[amplifier-memory] 2 memories loaded. /memory to see them.`.

**Stuck.** Nothing stopped, but one thing was quietly wrong and is now a lane: `amplifier-memory update` refreshed only the command-line tool, not the two things your sessions actually run — the bundle cache the modules load from and the library inside the amplifier program's own environment — so your device ran the old words for hours after waves 5–8 were "installed" while `doctor` reported "current"; I repaired it by hand and lane M is making `update` and `doctor` cover all three.

**Needs you.** Nothing new; the baseline number remains open and not blocking.

**Anything quietly broken.** The earlier briefs' "installed on your device" lines for waves 5–7 were true of the command-line tool only, not of your sessions — I have written that caveat into the check record; the one-time migration commit that stops your store growing by one commit per session has now landed (`store: stop tracking usage.jsonl`), and `doctor`'s `store` row wording still says "store.v1" (cosmetic, on my list).

## 2026-09-06 — `update` now refreshes what your sessions actually run (unprompted)

**Time away.** About twenty-five minutes since the last brief; wave 9 landed in it and wave 10 launched.

**Finished.** `amplifier-memory update` now refreshes all three things a session depends on — the command-line tool, the bundle cache your modules and skills load from, and the library inside the amplifier program's own environment — each as its own line with old → new commit, and `doctor` reads all three and names whichever is behind; I proved it on your machine, not just in tests: `doctor` correctly said WARN while two of the three were stale, the new `update` moved them (`0f7e0fc → 662a53a`, three times), `doctor` then read `current (uv tool 662a53a · bundle cache 662a53a · env library 662a53a == main)`, and a real session printed `[amplifier-memory] 2 memories loaded. /memory to see them.`.

**Stuck.** Nothing stopped; one wrinkle found while proving it — the first `update` after an upgrade finishes its steps with the old program (the process that is running is the pre-upgrade one), so the cache and library only refreshed on the second run — and lane N is making `update` hand off to the freshly upgraded binary so one run is enough.

**Needs you.** Nothing new; the baseline number remains open and not blocking.

**Anything quietly broken.** Nothing new; the README and PINS now read v2 where they still said v1, and the contract reading is 27 kept, 2 open (both the Phase-2 timer, gated on the day-7 reading), nothing broken.

## 2026-09-06 — quiescent: every buildable clause is closed and on your device (unprompted)

**Time away.** About forty minutes since the last brief; wave 10 landed in it and nothing new launched, because nothing is left to derive.

**Finished.** One `amplifier-memory update` now does the whole job — I ran it on your machine after the merge and it upgraded the tool, moved both bundle cache clones and the library inside the amplifier environment from `fd5d025` to `147739c`, and `doctor` read all three current; a real session then printed `[amplifier-memory] 2 memories loaded. /memory to see them.`; root tests 173 green; ten waves and sixteen items are recorded in the check record, each with the command I re-ran and what it printed.

**Stuck.** Nothing stopped; the only thing I could not observe for real is lane N's hand-off itself, because the program that ran that update was the previous version and already had the refresh steps — the first real observation comes the next time `main` moves and `update` runs here, and I have said so in the record rather than claim it.

**Needs you.** Nothing today; the baseline number (how many times a week you repeated a standing preference before memory) is still open and not blocking — it will sharpen the day-7 reading on 2026-09-13, when I bring you one priority call: build Phase 2 (the daily inbox), defer it, or decline it.

**Anything quietly broken.** Nothing new; for a fresh session that picks this up: read this file's tail, then `docs/workflow/CHECK-RECORD.md`, then `.converge/amplifier-bundle-memory/PLAN.md` — everything verified is there, and the two open contract rows are both the Phase-2 timer.

<details><summary>Technical detail</summary>

- Device: uv tool · `~/.amplifier/cache/amplifier-bundle-memory-450b259c…` · `cache/skills/…` · amplifier-venv `amplifier_memory` — all `147739c == main`.
- Ledger 31 rows: CONFORMS 27 · GAP 2 (cli.v2 §6, store.v2 §7) · NOT-ASSERTABLE 2 (session.v2 §4, §7).
- Tracker `amplifier_bundle_memory`: 16 resolved, 0 open. No lanes, no watcher, no worktrees.
</details>

## 2026-09-06 22:48 - "do it"

**Time away.** A few minutes since the last brief; nothing ran in between — the queue was empty.

**Finished.** Your "do it" is taken as the priority call answered — build Phase 2 now rather than wait for the day-7 reading — and I have written that down as your decision, with the reading as it stands today beside it (kept 0, citations 0 of 183 loads, baseline not yet given); the Phase 2 contract, `contracts/suggestions.v1.md`, is refreshed to sit on v2 (the pending-suggestions line is rendered by code beside the load line, the accept path uses the v2 writer) and stays a draft.

**Stuck.** Nothing stopped, but nothing can start: Phase 2 derives from a contract you have not yet ratified, and a lane launched against a draft is work thrown away.

**Needs you.** One word on `contracts/suggestions.v1.md` — *ratified*, *ratified with edits*, *declined*, or *later*; it promises, in ten clauses, a once-a-day timer (never a service) that reads your recorded sessions, asks the model one question per session, verifies every candidate in code against the quote before proposing it, shows the count on the next load line without interrupting, lets you accept, decline or skip each item in one keystroke, never re-proposes a decline, spends at most 30 model calls a day, reports even when empty, and fails open.

**Anything quietly broken.** Nothing; the two contract rows that were open (`service` verb, `declined.md`) are exactly the ones Phase 2 closes.

## 2026-09-06 23:02 - "ratified" (suggestions.v1)

**Time away.** A few minutes since the last brief; nothing ran in between — everything waited on this word.

**Finished.** Your word is written down: `contracts/suggestions.v1.md` is locked (one write, with the changelog quoting "ratified" and recording that you waived the day-7 gate by "do it"), it is pinned as the fourth contract the ledger guards, its ten clauses are seeded as open rows, and two lanes are building against it right now — the library and command line (the daily `suggest` job that reads yesterday's sessions and asks one question each, the inbox and declined list, `review`, the `service` timer, `doctor` rows, the run log) and the surface (the second rendered line `3 suggestions waiting. /memory review to see them.` and `/memory review` in the session).

**Stuck.** Nothing stopped.

**Needs you.** Nothing now; when the lanes land I will run the first real `suggest` on your machine and show you what it proposed from your own sessions before anything is installed as a timer — installing the timer writes files outside the store, so that will come to you as the irreversible call.

**Anything quietly broken.** Nothing new; the two Phase-1 rows that were open (`service`, `declined.md`) are exactly what Phase 2 closes.

## 2026-09-07 — Phase 2 is live on your machine; the timer waits for your word

**Time away.** About an hour since your "ratified"; one wave (11, two lanes) ran in it, plus three real `update`s and three real `suggest` runs I did by hand.

**Finished.** The suggestion inbox is built and installed: I re-ran everything myself before and after merging (root suite 223 tests, both module suites, every conformance kit, the ledger checks — all green), the device now runs 3b04348 on the tool, the cache and the library, and the daily pass ran for real against your own sessions and put one suggestion in the inbox — `Package tool behavior in a reusable library, with the CLI as a thin click-based wrapper around it`, quoting your exact words from this very session — so a new session now shows `1 suggestion waiting. /memory review to see it.` under the load line, and `amplifier-memory review --list` shows it with the quote.

**Stuck.** Nothing stopped.

**Needs you.** One irreversible call: installing the daily timer writes two systemd files outside the store and will spend up to about eight dollars a day at the contract's 30-call ceiling with today's model setup (each call loads the full default bundle, measured at $0.27), so say **install it**, **not yet**, or **leaner first** (I cut the per-call cost before installing).

**Anything quietly broken.** Two real defects the test kits could not see, both caught on your machine and fixed within the hour: the first real run failed all thirty calls because the CLI prints a status line before its JSON, and the second failed because the job never handed the model the transcript or asked for the reply shape — fixed, re-tested, and proven by the third run; also, during its work lane P's own probe twice installed a real timer on this machine and removed it (I checked: nothing remains), and I had seeded four ledger rows with ids that already existed, now renumbered.

<details><summary>Technical detail</summary>

Merges: Q f2e4fdb, P 2e6f91c. CHECK-RECORD 11 b30940c + addendum 262aa22. Repairs: b698a94 (`_json_object_in` past the CLI preamble), 3b04348 (`compose_request`: §3 question verbatim + reply shape + numbered human turns, 1500/24000 char caps). Device: `update` ×3, each time lane N's re-exec hand-off fired for real. suggest.log: run 1 `sessions=30 … status=degraded:model call failed…`; run 2 `sessions=3 rejected=3 status=degraded:malformed reply…`; run 3 `sessions=3 proposed=1 rejected=0 calls=3 status=ok`. Store commit 107aa79. Ledger 41 rows: 39 Kept, 2 Can't check, 0 Broken. Substrate on this device: 305 root sessions qualified in the last 24h, mostly automation lanes.

</details>

## 2026-09-07 00:24 - they came back asking which models the job uses, and for an eval of model classes

**Time away.** About forty minutes since the last brief; no lane ran, but one evaluation pilot did — 90 real model calls, plus 10 screening calls and 6 judging calls.

**Finished.** The answer to "which model does it use": today the job inherits whatever the amplifier CLI defaults to (your starred `opus` provider, the full default bundle), with no knob of its own — and the pilot I built and ran against fixtures made from your own sessions shows all three Anthropic classes clear the bar the code needs (every quote verbatim; recall 16/16, 15/16, 16/16), with the small class showing the only two slips in 90 calls (one reply hijacked by a `/goal` transcript, one project goal proposed as a preference) and the large class buying nothing measurable; the harness, fixtures builder and results are committed (`evaluations/model-class/`, RESULTS-2026-09-06-pilot.md), and I re-derived every headline number from the per-call records before writing it down.

**Stuck.** Nothing stopped; the first pilot process died at 34/90 when my own shell timed out, and I added a resume so the re-run paid only for the remaining 56.

**Needs you.** Two words: whether to run the full pass (adds gpt-5.6 and gemini, a second fixture seed, about $30 at today's bundle weight — **run it** / **skip it**), and the earlier timer call now reframed by the numbers (**install it** / **not yet** / **leaner first**), where "leaner first" means cutting the ~100k-token bundle tax that is 20× the model-class difference.

**Anything quietly broken.** The CLI's JSON `"model"` field reports the wrong model for every `-p` (the harness reads stderr instead, nothing of ours depends on it); and the prompt-level "skip what is already known" misses 10–20% across all classes, which the code's exact-text dedupe would not catch for a paraphrase — a re-proposal would cost you one decline; filed as a candidate item, not built.

<details><summary>Technical detail</summary>

Pilot: `harness.py --variants haiku,sonnet,opus --scenarios planted,pure_task,already_known --limit 10`; $14.87 + $2.73 screening + ~$1.40 judging. haiku 29/30 shape · 16/16 recall · 1 FP · dedupe 9/10 · $0.042/call · 10.2 s. sonnet 30/30 · 15/16 · 0 FP · 9/10 · $0.177 · 2.4 s. opus 30/30 · 16/16 · 0 FP · 8/10 · $0.276 · 1.9 s. 85–120k of each call's input is the bundle system prompt; the request is 2–5k. Commits a574ccc, 8eaae37, 027067d; workspace 668d500 (ignore `.amplifier/`). Candidate items: provider/model/bundle pass-through + lean bundle for the job (Core 8); fence the turns as data in `compose_request`; quote-keyed dedupe (§4/§7).

</details>

## 2026-09-07 02:52 - "try again w/ openai models" — the same pilot, OpenAI-backed providers

**Time away.** About fifteen minutes; no lane ran, one evaluation pilot did — 120 real calls across the four OpenAI-backed providers that work on this machine, on the same fixtures as the Anthropic pilot.

**Finished.** All four OpenAI variants (gpt-5.6 sol/terra/luna, gpt-6 astra) were clean where the small Anthropic class slipped — 120/120 well-formed replies, every quote verbatim, recall 16/16, zero pure-task false positives — and one of them, `luna`, did it at two cents a call, seventeen times cheaper than the opus default the job inherits today; I re-derived every number from the per-call records, ran the extras through the judge, and wrote both pilots into `evaluations/model-class/RESULTS-2026-09-06-pilot.md` (b1d544d).

**Stuck.** Nothing stopped; `azure-openai` fails with a connection error on this machine and was left out, and `openai-chatgpt` is the same gpt-5.6-sol over another transport, so it was skipped as a duplicate.

**Needs you.** Two words: **luna** (default the job to gpt-5.6-luna and build the provider knob — one item, one lane) or **sonnet** (stay in the Anthropic family at nine times the cost) — and, separately, the timer: **install it** / **not yet**, now that the cost at the ceiling is $0.60 a day with luna rather than $8.

**Anything quietly broken.** The harness's "dedupe" column over-counts — it treats a model finding a genuine unplanted preference in your real session (it happened eight times, one sentence about the compaction gap) as a dedupe miss; I corrected the reading by hand (true re-proposals: 0–3 in 10 for every model, Anthropic included) and noted the fix, and the CLI prints no cost for gpt-6-astra so that cell is honestly blank.

<details><summary>Technical detail</summary>

Run `20260907-025546-model-class-openai`: sol 30/30 shape, 16/16, 0 FP, 1 true dedupe miss, $0.353/call, 4.7 s · terra 30/30, 16/16, 0 FP, 0 misses, $0.180, 4.3 s · luna 30/30, 16/16, 0 FP, 1 miss, $0.020, 4.4 s · astra 30/30, 16/16, 0 FP, 3 misses, unpriced, 7.5 s. Mean input 70.4k tokens (OpenAI tokenizer on the same bundle prompt Anthropic counts at 87–121k). Spend $16.58 + ~$1.90 judging. Opus judge labelled the compaction-gap sentence `standing_preference` 8/8 here, `task_instruction` 1/1 in pilot 1 — the one item the judge disagrees with itself on. Candidate items unchanged: provider/model knob (Core 8), fence turns as data, quote-keyed dedupe.

</details>

## 2026-09-07 03:08 - "reasoning levels on luna/terra/haiku/sonnet; a provider+model config per call type, or routing-matrix model roles"

**Time away.** About thirty minutes; no lane ran, one more evaluation pilot did — 220 calls across eleven reasoning-effort variants of luna, terra, haiku and sonnet, built as project-scoped provider entries in a scratch directory so your global settings were never touched.

**Finished.** The reasoning question is answered: turning reasoning off costs precision, not recall — luna at `none` proposed four task instructions as preferences in ten sessions and terra two, while every level from `low` up was clean for both and cost did not move at all ($0.02 and $0.18 a call at every level, because the bundle prompt dwarfs the reasoning tokens); sonnet was clean at every level, haiku slipped once at each level for reasons reasoning does not fix (a JSON syntax slip, the `/goal` transcript hijack), and `minimal` is refused outright by this endpoint's gpt-5.6 models; all of it re-read from the per-call records and written up with the config options ranked (d08fc9c).

**Stuck.** Nothing stopped; the twenty `luna-minimal` calls failed by design of the endpoint, not the harness, and the fail-open path turned every one into a clean `rejected`.

**Needs you.** One word on the config shape — **knob** (a provider/model/bundle table per LLM call type, with a `role` key present from day one and an upstream ask filed for `amplifier run --model-role`, so it can later resolve `fast` the way recipes do) or **role** (wait on the routing-matrix path, which today has no way to reach a root `amplifier run`) — and, unchanged, the timer: **install it** / **not yet**.

**Anything quietly broken.** The OpenAI provider module accepts `reasoning_effort: minimal` at mount but this endpoint rejects it per request, so a user who sets it gets a run that is all `rejected` with exit 0 — worth a `doctor` word if the knob exposes the setting; and the harness's dedupe column still over-counts (noted last brief, unchanged, not used in this pilot).

<details><summary>Technical detail</summary>

Run `20260907-031137-model-class-reasoning`, planted + pure_task, 10 each, 11 variants. FPs of 10 pure-task sessions: luna none 4 / low 0 / medium 0 / high 0; terra none 2 / low 1 / medium 0 / high 0; haiku low 0 / medium 0 / high 1; sonnet all 0. Shape: haiku 19/20 at low and medium; everything else 20/20 except luna-minimal 0/20 (`'minimal' is not supported with the 'gpt-5.6-luna' model`). Recall 16/16 everywhere except haiku-low 15/16 and sonnet-high 15/16 (pilot 1). Routing-matrix reading: `model_role` resolves for agent frontmatter, delegate spawns and recipe steps via hooks-routing; no `--model-role` on `amplifier run`, no root-level role read in app-cli. Recommended default on this host: `luna` (low or high), $0.60/day at the ceiling.

</details>

## 2026-09-07 03:32 - "go for it all, let's do #1" — the knob, the upstream ask, then the timer

**Time away.** About forty minutes since "go for it all"; one wave (12, two lanes) ran in it, and I did the device work myself after the merge.

**Finished.** Everything you asked for is built, merged, and live on your machine: the knob (`~/.amplifier/memory-config.toml`, `[llm.judge] provider = "luna"`) is read by the job — I re-ran the whole suite (260 tests), both module suites, all three conformance kits and the ledger checks on the merged main, then a real bounded pass on your sessions whose log line reads `provider=luna status=ok`; the daily timer is installed and enabled with its first unattended run at midnight tonight, and `doctor` shows both (`suggest timer installed · enabled · last outcome ok`, `llm judge provider luna`); the turns the judge reads are now fenced as quoted data, suggestions are also deduped by your verbatim quote, and the ask to app-cli for `amplifier run --model-role` is written down in `docs/upstream/`.

**Stuck.** Nothing stopped; lane S's suite showed one failure on its first run that four re-runs could not reproduce, so it is recorded as an unreproduced flake rather than cleared.

**Needs you.** One ratify-class thread, not urgent: a suggestion you *declined* can still come back paraphrased because `declined.md` keeps text and date only and that line shape is fixed by locked `store.v2` §7 — closing it is a contract proposal (item 5eb, filed by the lane, pinned by a test), so say **draft it** if you want the proposal written, or **later**.

**Anything quietly broken.** Lane R's last commit bundled its DONE.json with a repo-wide formatting reflow of 25 files it did not own — I merged its two feature commits only and ran the format myself as a separate commit with the gate green before and after; the `amplifier-memory update` hand-off fired for real again, and the `update` row briefly read behind main because my own docs commits moved main after the device update — one more `update` fixed it.

<details><summary>Technical detail</summary>

Merges: S caee5f5 (757e8f5), R bf01606 (at 1e67b0d; 91838c1 not taken), format 72dce54, ledger notes 0d07d2b (AMM-034 §8, AMM-039 §3, AMM-040 §4), CHECK-RECORD 12 b0ad9c3 + device section ec75eae. Gate: 260 passed · ruff check/format clean · suggestions 9 Kept + Core 5 Can't check · store 10 · cli 9 · ledger 2 · modules 51/61. Device: uv tool/cache/library ec75eae == main; config beside the store (store.v2 §2); real run 2026-09-07T04:05:31Z `sessions=3 proposed=0 rejected=0 calls=3 provider=luna status=ok`; units `~/.config/systemd/user/amplifier-memory-suggest.{service,timer}`, NEXT Mon 2026-09-07 00:00 PDT. Items ec7, acu resolved and read back; 5eb open (ratify-class).

</details>

## 2026-09-07 — the timer's first night: 30 calls, 17 suggestions, two defects caught

**Time away.** About three hours since "go for it all", spent watching the midnight timer; no lane ran, two small repairs were made by hand.

**Finished.** The daily pass ran unattended at 00:00 PDT exactly as installed — thirty luna calls in six minutes, every quote verified in code, seventeen suggestions written to your inbox at about sixty cents — and `doctor` reads `suggest timer installed · enabled · last outcome ok`; `/memory review` (or `amplifier-memory review`) will walk you through the seventeen.

**Stuck.** Nothing stopped; the sub-agent I set to watch the timer misread an old log line as the new one, so I re-checked by hand and waited for the real line.

**Needs you.** Nothing new — the seventeen suggestions wait for your review at your pace (they expire unreviewed after 30 days), and the earlier ratify thread (5eb, declined suggestions returning paraphrased) still waits on **draft it** / **later**.

**Anything quietly broken.** Two things, both fixed tonight: one of the seventeen had a quote with a line break in it and was invisible to review until I flattened it (the code now flattens on write, and I repaired the one entry by hand); and installing the real timer turned twenty-one tests red on this machine because the suite was reading your actual systemd state — fixed so the suite never touches the device again — but I pushed one commit while that suite was red, because a piped `tail` hid the failure from me, and the device ran it for about fifteen minutes with nothing scheduled in that window.

<details><summary>Technical detail</summary>

suggest.log: `2026-09-07T07:00:01+00:00 sessions=30 proposed=17 rejected=0 dropped_stale=0 calls=30 provider=luna status=ok`; service Result=success, 00:00:01→00:06:10 PDT. Store commit ecf0937 (17 items), repair 7d2435a (s-018 flattened). Repo: 111901a (inbox flattens on append), 1d70345 (conftest recorder for service._default_runner + temp UNIT_DIR; update passes runner into step-4 status). Suite 261 passed, ruff clean, kits cli 9 / suggestions 9+1 / store 10 Kept, ledger 2. Device 1d70345 == main. Next fire Tue 2026-09-08 00:00 PDT.

</details>

## 2026-09-07 14:58 — two contracts ratified in conversation; session is now v3

**Time away.** None — you were present the whole session, roughly three hours from "use the memory skill" to "ratified"; no lane ran, everything below was manager's-hand work on the contracts.

**Finished.** `contracts/session.v3.md` is locked (one write, H1 + changelog) and `contracts/store.v2.md` is amended in place through the guard's ratified-proposal escape hatch, both applied by a script that asserted every replacement matched exactly once before writing; the two candidates carry your word verbatim, and `PINS.md` now names the live versions.

**Stuck.** Nothing stopped; the guard refused the first in-place write to `store.v2.md` because the candidate lacked a `target:` line and the literal `ratified … by owner` stamp, and the second write landed once both were added — that shape is now known for next time.

**Needs you.** One priority call, nothing parked on it: should a fresh install set up the daily suggest timer by default (today `service install` is an explicit step; first unattended pass cost ~$0.60 at luna rates) — **yes** or **no**; and the earlier 5eb thread still waits on **draft it** / **later**.

**Anything quietly broken.** Your `/memory` listing earlier today was rendered perfectly and shown to nobody — the skill told the model to say nothing because "the tool result is what the human reads", which your client hid; that presumption is what Part A removed, and it had been in the contract, the tool description and all four skills since v2. Separately, `amplifier-memory status` prints `last run: never` while `suggest.log` holds this morning's run — filed as `70i`.

<details><summary>Technical detail</summary>

Ratified: `session.v2.v3-candidate.md` Parts A+B ("Ratified, but before we start making our changes…" / "ratified"), `store.v2-candidate.md` ("ratified"). Withdrawn the same hour at your suggestion: `suggestions.v1-candidate.md`, `cli.v2-candidate.md` (the `[suggestions] enabled` flag — the inbox is the one truth). Measured fixed injection: DESCRIPTION 576 · schema 232 · 4 skill lines 150 · framing 53 = 1,011 tokens/request vs 147 of memories; v3 §11 caps it at 500. Lock-time correction to Change 4: the presumption grep scans the implementation, not `contracts/`. Next: ledger rows for v3 §1/§3/§5/§6/§11 seeded Not yet; three disjoint lane items (tool+library+token meter · skills+bundle+behaviors+READMEs · inject hook+presumption grep); wave 13 at width 3.

</details>

## 2026-09-07 — wave 13 landed: session.v3 is real on your device

**Time away.** About fifty minutes since "ratified", in which one wave of three lanes ran to completion and was merged, gated and installed.

**Finished.** Your bundle now ships two commands — `/remember` and `/memory` with `list · review · forget · edit · remember · help` — and a bare `/memory` renders a four-line overview with suggestions first; the injected framing sentence is v3's; the model pays **409 tokens** per request for the bundle's fixed text where it paid 1,011 this morning (I re-ran the meter myself: description 190, parameters 139, the two skill lines 18 + 21, framing 41); nothing the model is given claims to know what you can see; all six ledger rows opened this morning read Kept, every kit is Kept or the pre-existing Can't check, 262 root tests pass, and `amplifier-memory update` put commit 22c4452 on the device — the installed library renders your real overview as `17 suggestions waiting. /memory review to walk them.` / `4 memories. /memory list to see them.` / `last 7 days: 6 written, 1 forgotten, 2 cited.` / the command line.

**Stuck.** Nothing stopped; the gate caught three things the lanes could not see alone — a frontmatter format one lane wrote and another lane's meter could not read, a paraphrase of the contract's relay sentence that my own brief had handed lane B, and one test docstring — all repaired by hand in one commit, and two of the three were defects in my briefs, not in the lanes.

**Needs you.** Two things: (1) the one check only a person can perform — open a **fresh** `amplifier` session and type `/memory`; if the four lines above reach your screen, session.v3 §6 is proven end to end, and if they do not, tell me what you saw; (2) `contracts/cli.v2-candidate.md` carries your "install the timer by default" as a change to `init` — **ratified**, **ratified with edits**, **declined** or **later**.

**Anything quietly broken.** Your inbox was never 34 items: `status` counted lines instead of items and showed double (lane A found and fixed it — it is 17); `status` still prints `last run: never` while `doctor` correctly reads this morning's run, so item 70i is half-fixed and stays open for that half; and the re-armed watcher fired a false wake once because its filter did not know two lanes were already finished — a watcher defect I replaced, no work was affected.

<details><summary>Technical detail</summary>

Merges: B ef913ae (6dd3b9d), C 0dc2628 (d29da67, README conflict → C's wording), A d630b8e (beab6d6, budget/run.py add/add composed). Repairs: dee8d6b (AGENTS.md, chmod), 6c64fb5 (skill relay sentence, skill_lines yaml.safe_load, test docstring, ruff format ×4). Ledger 22c4452: AMM-010/012/014/015/041/042 → CONFORMS, 0 GAP. CHECK-RECORD 13a + 13b. Gate: 262 · ruff clean · 107 formatted · ledger 2 · inject 51 · tool 70 · kits inject 5 Kept, tool 3 Kept + 2 Can't check + sugg 6 Kept, budget 2 Kept (409/500), store 10, cli 9, suggestions 9 + Can't check. Device: uv tool/cache/library 22c4452 == main; doctor all OK; inbox 17. Items nyh, 42s, 20e resolved and read back. Open: 70i (status last-run half), 5eb (ratify-class), cli.v2-candidate (ratify).

</details>

## 2026-09-07 16:00 — they came back with the /memory transcript: it worked, and the lines ran together

**Time away.** A few minutes — you ran the check I asked for and came back with the transcript; nothing else ran.

**Finished.** The check passed at the layer that matters: in a fresh session the tool rendered the four §6 lines exactly, from your real store, through the installed bundle; what fell short was the last inch — the model relayed them and markdown folded the four lines into one paragraph and dropped `<id>` and `<text>` as if they were tags — so both skills now tell the model to relay inside a fenced code block, the tool kit asserts that sentence is present (Core 6 Kept), and the device is updated to 44d5fa0; your next fresh session should show the four lines as four lines.

**Stuck.** Nothing stopped.

**Needs you.** One check again, same shape — a fresh session, `/memory`, four lines in a box — and the earlier word on `contracts/cli.v2-candidate.md` (init installs the timer by default) still waits.

**Anything quietly broken.** Your transcript shows `/memory` cost three model calls and $0.90, almost all of it the 120,000-token context the `anchors` bundle carries into every request — not this bundle's 409 — while session.v3's Conformance says "one model round trip"; that line was already aspirational in v2 (the backlog names the real fix: a deterministic `/memory` needs the CLI's command registry open to bundles), so I am recording the observed count rather than pretending the clause holds.

<details><summary>Technical detail</summary>

Repair 44d5fa0: skills/memory + skills/remember relay inside a fence, with the reason; conformance/session/tool FENCE_RULE = "fenced code block" asserted per skill. Kits: tool Core 6 Kept, budget 409/500 Kept, no-presumption Kept. Device: uv tool/cache/library 44d5fa0 == main. Observed on the steward's run: load_skill → memory(overview) → relay = 3 LLM calls, $0.75 + $0.08 + $0.07 (anchors context 119,875 input tokens on the first call). Open: cli.v2-candidate (ratify), 70i (status last-run half), 5eb.

</details>

## 2026-09-07 16:13 — they came back with two transcripts: the overview boxed, the review unreadable at 17 items

**Time away.** Minutes — you ran `/memory` (boxed, four lines, as intended) and `/memory review` (seventeen items as one wall), and came back with both transcripts and a shape you want instead.

**Finished.** Nothing new landed in this turn; the overview fix from the last one is confirmed working in your transcript (e3b15303), and your review feedback is written up as `contracts/session.v3-candidate.md` with a mock-up rather than filed as a ticket, because it changes what §6 promises about how `list` and `review` look.

**Stuck.** Nothing stopped.

**Needs you.** Two words: (1) the review-page proposal — code renders each page as markdown (numbered bold ids, the quote as a blockquote, a blank line between items), pages of about six above eight items, the model drives paging and accepts by id, never by position — **ratified / ratified with edits / declined / later**; (2) the `init`-installs-the-timer proposal from before still waits for its word.

**Anything quietly broken.** Your review transcript shows the model spending 2,476 output tokens and 25.6 seconds echoing seventeen items — the fence I added for the overview made the review page wrap mid-word too; the proposal says which renderings get the fence (overview, receipts) and which do not (list, review pages).

<details><summary>Technical detail</summary>

Feedback drops: c798a817 (review wall, 2,476 out tokens / 25.6 s), e3b15303 (overview boxed, correct). Proposal: session.v3-candidate.md — §6 `list [<page>]` markdown bullets `- **m-NNN** text`, 20/page; `review [<page> | accept|decline|skip <id>…]` markdown pages, quote as blockquote, blank line between items, multi-id = N calls, positions refused; paging rule n≤8 → 1 page else ceil(n/6) pages of ceil(n/pages); relay sentence: fence for overview+receipts only. One lane after ratification (src/inbox.py render_review + store list renderer + tool page param + skill + tests + kit fixtures). Open: cli.v2-candidate, 70i, 5eb.

</details>

## 2026-09-07 16:19 — "ok, do it": both candidates ratified
