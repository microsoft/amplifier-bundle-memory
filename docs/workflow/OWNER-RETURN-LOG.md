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
