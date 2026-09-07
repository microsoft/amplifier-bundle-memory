# amplifier-bundle-memory

Say a standing preference once. See it saved. Never say it again.

The bundle gives every Amplifier session on this device a small,
always-loaded file of how you work (`~/.amplifier-memory/MEMORY.md`), saved
to the moment you correct the assistant, undone with one command, explained
by `git log`. No database, no daemon, nothing at session end.

Read in this order: [`docs/VISION.v2.md`](docs/VISION.v2.md), then the contracts in
[`contracts/`](contracts/) — `store.v3` (the files), `session.v4` (what
happens in a session), `cli.v3` (the command), `suggestions.v2` (Phase 2,
the daily inbox).

The store is an **instance**: a directory of plain text, its own git repository.
Which one a session uses is resolved in order — an explicit `home` from the caller
(the modules' `config: home:`, or `--home`), else `$AMPLIFIER_MEMORY_HOME`, else the
default `~/.amplifier-memory` (store.v3 §1). A store made before v3 lives at
`~/.amplifier/memory`, and while that is the only one on the device it stays the
default, so nothing moves until `init` offers to move it. Beside the memories the
instance carries two files that are **plumbing, not memory** — never injected, never
suggested, never cited (§2): `config.yaml`, its own configuration, and
`sessions.jsonl`, one line per session seen. Set `enabled: false` in `config.yaml` and
the instance goes **inert**: nothing is injected, no tool is offered, no timer runs,
and every writer refuses in one line (§11).

## Install

```bash
# 1. Session plane (load + save + /remember and /memory), composed into all sessions.
#    Point --app at the behavior file, not at the root bundle: the root bundle includes
#    this same behavior, so an --app install of it is a self-include the loader skips
#    ("Circular Include Skipped"), leaving a session with no hook and no memory tool.
amplifier bundle add 'git+https://github.com/bkrabach/amplifier-bundle-memory@main#subdirectory=behaviors/memory-session.yaml' --app

# 2. The CLI (`amplifier-memory`, a thin click wrapper over the `amplifier_memory`
#    library: init · status · review · why · format_why · doctor · update_check ·
#    update_plan · service_status · run_suggest · pending/accept/decline/skip —
#    cli.py adds only parsing, printing and exit codes):
uv tool install git+https://github.com/bkrabach/amplifier-bundle-memory@main

# 3. Create the store (a git repo at ~/.amplifier-memory) and install the daily
#    suggestion timer. This is the only setup step; `--no-timer` skips the timer.
amplifier-memory init

# 4. Verify:
amplifier-memory doctor
```

Step 3 prints what it installed, how to turn it off
(`amplifier-memory service uninstall`) and where to steer what it costs
(`config.yaml` inside the store — [which model the judge
uses](#which-model-the-judge-uses)). Running it again reports `store exists ·
timer installed` and changes nothing; once you have uninstalled the timer, `init`
leaves it uninstalled.

`doctor` exits 0 when the store is healthy, and nonzero before step 3 has run.
To see the session plane itself working, start a session and say a standing
preference: it is saved in that turn and announced with its id and its undo.

To remove all of it:

```bash
amplifier bundle remove 'git+https://github.com/bkrabach/amplifier-bundle-memory@main#subdirectory=behaviors/memory-session.yaml' --app
uv tool uninstall amplifier-memory
rm -rf ~/.amplifier-memory        # deletes your memories
```

The daily suggestion inbox (Phase 2, below) needs nothing further: step 3
installed its timer. To turn it off, or to put it back afterwards:

```bash
amplifier-memory service uninstall   # no more daily pass; the store is untouched
amplifier-memory service install     # what `init` already did — run it to undo an uninstall
```

## Use

In any session:

```
/remember never use tabs in YAML; two-space indentation
/memory
/memory forget m-017
/memory help
```

Or just correct the assistant — it saves and the receipt reads:

```
saved m-017 — /memory forget m-017 to undo.
  never use tabs in YAML; two-space indentation
  your words, verbatim
```

From a shell: `amplifier-memory status` (what you wrote, kept and forgot,
plus how often a memory was actually cited) · `amplifier-memory why m-017`
(the commits behind one memory: the creation, each refinement as
`was:` → `now:`, and the forget if there was one) · `amplifier-memory doctor`
(health; never writes — and `doctor --repair`, the one exception, restores a
damaged `MEMORY.md` from the last clean commit and prints what it discards
first) · `amplifier-memory review` (pending suggestions) ·
`amplifier-memory init` · `amplifier-memory update` (alias `upgrade`) ·
`amplifier-memory suggest` and `service` (Phase 2, below).

One `amplifier-memory update` is enough: it refreshes all three copies of this
bundle a device runs, and prints each as `<old> → <new>`: the `amplifier-memory`
uv tool (the shell verb), the bundle cache clone(s) under `~/.amplifier/cache/` and
`~/.amplifier/cache/skills/` (what a session loads the modules and skills
from), and the `amplifier_memory` library inside the amplifier CLI's own venv
(what those modules import). `doctor`'s `update` row compares all three
against `git ls-remote` and names which one is behind; a cache or a venv it
cannot find is INFO, never a failure. When the uv-tool step upgrades the CLI,
`update` re-runs itself from the freshly installed binary so the remaining
refreshes happen with the new code — that hand-off is why the second half of
the report shows step 1 skipped. Sessions started before an update keep the
old module code until they restart — nothing is hot-reloaded.

Reading memory leaves no commit behind: loads and citations are appended to
`~/.amplifier-memory/usage.jsonl`, which git does not track. Every commit in
the store is a change you made or approved.

## The daily suggestion inbox (Phase 2)

Some standing preferences are said in the flow of work and never saved in the
turn. Once a day a timer runs `amplifier-memory suggest`, which reads
yesterday's recorded sessions, asks the model one question per session, checks
in code that every quote it gets back was really said by you, and *proposes*
the survivors. It never writes to `MEMORY.md`.

`amplifier-memory init` installed that timer (a systemd `--user` timer, launchd on
macOS) — there is no second setup step. The rest of the verbs:

```
amplifier-memory suggest            # run the pass once, now
amplifier-memory review             # walk the inbox, one keystroke each
amplifier-memory review --list      # or just look
amplifier-memory service status     # installed · enabled · last run · last outcome
amplifier-memory service uninstall  # stop the daily pass; `service install` puts it back
```

A proposal lives in `~/.amplifier-memory/inbox.md`, two lines, with the words
you actually said and where you said them:

```
- [s-042] never use tabs in YAML; two-space indentation
  quote: "never use tabs in YAML files I ask you to write…"  session: bc214bdf  2026-09-05
```

**accept** writes the line through the same writer everything else uses — the
commit carries the quote, the session it came from, and `writer: suggestion`, so
`amplifier-memory why m-NNN` tells you where a memory came from months later.
**decline** appends the text to `declined.md` with the date, and it is never
proposed again (exact match, in code — reversal is deleting the line by hand).
**skip** leaves it. An item nobody reviews for 30 days is dropped, and counted
in the next run's report.

Nothing is proposed twice: a candidate is dropped when its text matches a
`MEMORY.md` line, a decline, or something already pending — **and** when its
verbatim quote matches a pending item or a memory you still have, since a model
that re-proposes something usually rewrites the text while quoting your sentence
word for word. The one case that still gets through: a suggestion you
**declined** and that comes back paraphrased, because `declined.md` records the
text and the date only, so there is no quote left to match it on.

### Whose sessions it reads

Only sessions with **you** in them, and the test is two things at once:

1. **The session says it was started by a human.** Every session records how it
   began in the instance's `sessions.jsonl` — `human`, or `worker` / `recipe` /
   `agent` / `eval` for the ones a launcher started. Only `human` is read. A
   session with **no record counts as human**, so nothing is dropped for being
   unclassified; the filter sharpens as launchers set
   `AMPLIFIER_SESSION_ORIGIN`. Refusals are counted in the run's log line.
2. **At least two of its turns are you actually typing**, in the last 24 hours.
   Two shapes are not typing, and both were measured mining the wrong thing on
   the first timer night: a **lane brief** — a turn addressed to an agent, which
   opens `Claim <id> from the <project> work-tracker project…` — and a
   **continuation turn that is only the harness's own `<system-reminder>`
   blocks**. Neither reaches the judge, and a quote lifted out of one is
   rejected.

It still never reads a sub-agent's session, and never one it started itself.

What it costs: at most 30 model calls a day, one run a day, nothing resident —
the unit is `Type=oneshot` and only the timer starts it. Every run appends one
line to `~/.amplifier-memory/suggest.log` — including the runs that proposed
nothing:

```
2026-09-06T09:00:04+00:00 sessions=3 origin_excluded=4 proposed=1 rejected=2 dropped_stale=0 calls=3 provider=luna model=gpt-5.6-luna status=ok
```

`sessions=` is what it read; `origin_excluded=`, beside it, is what it turned
away for not being a human's session. `provider=` names the model that was
billed — a provider id, `role:<role>`, or `inherited`.

### Which model the judge uses

Three answers, in this order:

1. the `provider` / `model` / `bundle` you set in `config.yaml` (below);
2. else the **role** — `fast` as shipped — resolved by the amplifier CLI, when
   your CLI has `amplifier run --model-role` (the job reads its `--help` to find
   out; today's CLI does not, so this step is skipped);
3. else the CLI's own default, **inherited** — whatever `amplifier provider` has
   starred.

The shipped default is a role, never a provider id: a provider id names one
machine's account. To pin one for this job alone, write the `llm:` block of the
store's own `config.yaml`, which `init` already wrote:

```yaml
enabled: true       # store.v3 §11 - false makes this instance inert
llm:
  judge:
    role: "fast"    # recorded and logged; resolved when the host can
    provider: "luna"  # an amplifier provider id -> `amplifier run -p`
    model: ""       # optional -> `-m`
    bundle: ""      # optional -> `-B`
```

It lives *inside* the store it configures, because a store is an instance and there may
be more than one (store.v3 §1–§2): move the instance and its configuration moves with
it. `config.yaml` is plumbing, not memory — never injected, never suggested, never
cited. Only the keys you set become flags; with no file, or an empty one, the job runs
exactly the command it always ran. Every run's log line names which provider it used,
and `amplifier-memory doctor`'s `llm judge` row names the judge before the night rather
than after it — the provider you pinned, the role it resolved through, or `inherited`
with what that default was **measured** to cost per call, and so what a full 30-call
night can bill you.

What the measurements say (7 model variants, 210 real calls, `evaluations/model-class/`):

- **The judging task does not need a large model.** 6 of 7 variants returned perfect
  recall and verbatim quotes; the one shape failure and the one false positive in 210
  calls were both caught in code before anything reached the inbox.
- **`gpt-5.6-luna` at `low` reasoning or above was clean at $0.02/call** — $0.60 a day at
  the 30-call ceiling, against $0.276/call for the large class. Without an OpenAI-backed
  provider, a mid class (sonnet) is the equivalent.
- **Reasoning effort belongs to the provider entry, not here.** It is
  `config.providers[].config.reasoning_effort` in your amplifier settings, so "luna at
  low" means an entry named e.g. `luna-low`, and `provider = "luna-low"` above. Turning
  reasoning **off** costs precision: at `none`, four task instructions in ten were
  proposed as standing preferences. `low` and up returned that to zero.
- **`minimal` is refused by this endpoint's gpt-5.6 models** at request time even though
  the provider accepts it at mount. A user who sets it sees every session `rejected` and
  the run exit 0 — nothing breaks, and nothing is proposed.

A file that cannot be read — a typo, a broken table — never costs you the night's run:
the pass says so in its log line, inherits the CLI default, and carries on.

If the session capture is missing, or the model is unavailable, or the reply
comes back malformed, the run records that and exits 0. Nothing is written to
the inbox, and `amplifier-memory doctor` shows the degraded state on its
`suggest timer` and `substrate` rows. The pass depends on the
context-intelligence bundle's local session capture
(`~/.amplifier/projects/`); Phase 1 does not.

## What success looks like

`amplifier-memory status` after a week of real use shows at least five
memories you kept. If it does not, that is the bug report.
