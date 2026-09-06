# amplifier-bundle-memory

Say a standing preference once. See it saved. Never say it again.

The bundle gives every Amplifier session on this device a small,
always-loaded file of how you work (`~/.amplifier/memory/MEMORY.md`), saved
to the moment you correct the assistant, undone with one command, explained
by `git log`. No database, no daemon, nothing at session end.

Read in this order: [`docs/VISION.md`](docs/VISION.md), then the contracts in
[`contracts/`](contracts/) — `store.v1` (the files), `session.v1` (what
happens in a session), `cli.v1` (the command), `suggestions.v1` (Phase 2,
the daily inbox).

## Install

```bash
# 1. Session plane (load + save + /remember /forget /memory), composed into all sessions.
#    Point --app at the behavior file, not at the root bundle: the root bundle includes
#    this same behavior, so an --app install of it is a self-include the loader skips
#    ("Circular Include Skipped"), leaving a session with no hook and no memory tool.
amplifier bundle add 'git+https://github.com/bkrabach/amplifier-bundle-memory@main#subdirectory=behaviors/memory-session.yaml' --app

# 2. The CLI (`amplifier-memory`, a thin click wrapper over the `amplifier_memory`
#    library: init · status · review · why · format_why · doctor · update_check ·
#    update_plan · service_status · suggest_status — cli.py adds only parsing,
#    printing and exit codes):
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
/forget m-017
/memory
```

Or just correct the assistant — it saves and tells you:
`Saved memory m-017: "…" — /forget m-017 to undo.`

From a shell: `amplifier-memory status` (what you wrote, kept and forgot,
plus how often a memory was actually cited) · `amplifier-memory why m-017`
(the commits behind one memory: the creation, each refinement as
`was:` → `now:`, and the forget if there was one) · `amplifier-memory doctor`
(health; never writes — and `doctor --repair`, the one exception, restores a
damaged `MEMORY.md` from the last clean commit and prints what it discards
first) · `amplifier-memory review` (pending suggestions) ·
`amplifier-memory init` · `amplifier-memory update` (alias `upgrade`).
`service` and `suggest` are Phase 2 and say so.

Reading memory leaves no commit behind: loads and citations are appended to
`~/.amplifier/memory/usage.jsonl`, which git does not track. Every commit in
the store is a change you made or approved.

## What success looks like

`amplifier-memory status` after a week of real use shows at least five
memories you kept. If it does not, that is the bug report.
