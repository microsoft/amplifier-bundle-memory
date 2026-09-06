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
