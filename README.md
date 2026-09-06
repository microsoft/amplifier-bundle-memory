# amplifier-memory

Say a standing preference once. See it saved. Never say it again.

`amplifier-memory` gives every Amplifier session on this device a small,
always-loaded file of how you work (`~/.amplifier/memory/MEMORY.md`), saved
to the moment you correct the assistant, undone with one command, explained
by `git log`. No database, no daemon, nothing at session end.

Read in this order: [`docs/VISION.md`](docs/VISION.md), then the contracts in
[`contracts/`](contracts/) — `store.v1` (the files), `session.v1` (what
happens in a session), `cli.v1` (the command), `suggestions.v1` (Phase 2,
the daily inbox).

## Install

```bash
# 1. Session plane (load + save + /remember /forget /memory), composed into all sessions:
amplifier bundle add git+https://github.com/bkrabach/amplifier-memory@main --app

# 2. The CLI:
uv tool install git+https://github.com/bkrabach/amplifier-memory@main

# 3. Create the store (a git repo at ~/.amplifier/memory):
amplifier-memory init

# 4. Verify:
amplifier-memory doctor
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

From a shell: `amplifier-memory status` · `amplifier-memory why m-017` ·
`amplifier-memory doctor`.

## What success looks like

`amplifier-memory status` after a week of real use shows at least five
memories you kept. If it does not, that is the bug report.
