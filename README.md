# amplifier-bundle-memory

Say a standing preference once. See it saved. Never say it again.

The bundle gives every Amplifier session on this device a small,
always-loaded file of how you work (`~/.amplifier/memory/MEMORY.md`), saved
to the moment you correct the assistant, undone with one command, explained
by `git log`. No database, no daemon, nothing at session end.

Read in this order: [`docs/VISION.md`](docs/VISION.md), then the contracts in
[`contracts/`](contracts/) — `store.v2` (the files), `session.v3` (what
happens in a session), `cli.v2` (the command), `suggestions.v1` (Phase 2,
the daily inbox).

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

# 3. Create the store (a git repo at ~/.amplifier/memory):
amplifier-memory init

# 4. Verify:
amplifier-memory doctor
```

`doctor` exits 0 when the store is healthy, and nonzero before step 3 has run.
To see the session plane itself working, start a session and say a standing
preference: it is saved in that turn and announced with its id and its undo.

To remove all of it:

```bash
amplifier bundle remove 'git+https://github.com/bkrabach/amplifier-bundle-memory@main#subdirectory=behaviors/memory-session.yaml' --app
uv tool uninstall amplifier-memory
rm -rf ~/.amplifier/memory        # deletes your memories
```

Phase 2 (daily suggestion inbox), only after Phase 1 has earned it:

```bash
amplifier-memory service install     # installs the once-a-day timer
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
`~/.amplifier/memory/usage.jsonl`, which git does not track. Every commit in
the store is a change you made or approved.

## The daily suggestion inbox (Phase 2)

Some standing preferences are said in the flow of work and never saved in the
turn. Once a day a timer runs `amplifier-memory suggest`, which reads
yesterday's recorded sessions, asks the model one question per session, checks
in code that every quote it gets back was really said by you, and *proposes*
the survivors. It never writes to `MEMORY.md`.

```
amplifier-memory service install    # a systemd --user timer (launchd on macOS)
amplifier-memory suggest            # run the pass once, now
amplifier-memory review             # walk the inbox, one keystroke each
amplifier-memory review --list      # or just look
amplifier-memory service status     # installed · enabled · last run · last outcome
```

A proposal lives in `~/.amplifier/memory/inbox.md`, two lines, with the words
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

What it costs, and what it will not do: at most 30 model calls a day, one run a
day, nothing resident — the unit is `Type=oneshot` and only the timer starts it.
It reads only root sessions with at least two of your turns in the last 24
hours; it never reads a sub-agent's session, and never one it started itself.
Every run appends one line to `~/.amplifier/memory/suggest.log` — including the
runs that proposed nothing:

```
2026-09-06T09:00:04+00:00 sessions=3 proposed=1 rejected=2 dropped_stale=0 calls=3 provider=luna model=gpt-5.6-luna status=ok
```

### Which model the judge uses

By default the pass inherits the amplifier CLI's own default provider — whatever
`amplifier provider` has starred. To choose one for this job alone, write
`~/.amplifier/memory-config.toml` (or point `AMPLIFIER_MEMORY_CONFIG` elsewhere):

```toml
[llm.judge]
provider = "luna"   # an amplifier provider id -> `amplifier run -p`
model = ""          # optional -> `-m`
bundle = ""         # optional -> `-B`
role = "fast"       # recorded and logged; resolved when the host can
```

It lives *beside* the store, never inside it: `~/.amplifier/memory` holds memories and
nothing else (store.v2 §2). Only the keys you set become flags; with no file, or an empty
one, the job runs exactly the command it always ran. Every run's log line names which
provider it used, and `amplifier-memory doctor`'s `llm judge` row names the resolved
choice — or says it is inheriting.

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
