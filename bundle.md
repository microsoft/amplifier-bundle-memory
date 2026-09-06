---
bundle:
  name: memory
  version: 0.1.0
  description: A memory that survives the session — MEMORY.md, loaded every request, written only from the human's own words.

includes:
  - bundle: memory:behaviors/memory-session   # own behavior by bundle-name namespace (BUNDLE_GUIDE.md:87); a git-URL self-include is a cycle the loader skips (measured by lane E)

default_behavior: memory-session
---

# amplifier-bundle-memory

One `MEMORY.md`, in a git repository, put in front of the model on every
request, and written only from the human's own words.

Governed by `contracts/session.v1.md` and `contracts/store.v1.md`.

## Install

Point `--app` at the behavior, not at this root bundle — an app bundle is
composed into every session, and the behavior is the composable unit:

```
amplifier bundle add git+https://github.com/bkrabach/amplifier-bundle-memory@main#subdirectory=behaviors/memory-session.yaml --app
amplifier-memory init
```

## What you get

| Piece | What it does | Contract |
|---|---|---|
| `hooks-memory-inject` | `MEMORY.md` in every model request, announced once — with what is waiting | session.v1 §1, §2, §9, §10 · suggestions.v1 §5 |
| `tool-memory` (`memory`) | save · edit · forget · list · cite · review, over the library's writer | session.v2 §3–§6, §8, R2 · suggestions.v1 §6 |
| `/remember <text>` | writes exactly what you typed | session.v2 §6 |
| `/edit <id> <text>` | replaces one memory's text, keeping its id | session.v2 §6 |
| `/forget <id>` | removes one line, commits | session.v2 §6 |
| `/memory` | prints the store with ids | session.v2 §6 |
| `/memory review [accept\|decline\|skip <id>]` | walks what the daily job proposed, one id at a time | suggestions.v1 §6 |
| `amplifier-memory` | the CLI over the same library | cli.v1 |

Nothing runs at session end. Exit cost is zero by construction.

## The one home for logic

`src/amplifier_memory/` holds every behaviour. The CLI is `click` over it; the
tool module and the inject hook import it directly. No wrapper carries logic,
and no wrapper calls another wrapper — the tool never shells out to the CLI
(AGENTS.md rule 11, cli.v1 §9).

## A note on `default_behavior`

The key above names this bundle's behavior for a reader and for any tool that
grows to honour it. Measured 2026-09-06 against the installed stack
(`amplifier`, `amplifier_app_cli`, `amplifier_foundation`, `amplifier_core`):
nothing reads it today — a grep for `default_behavior` across all four returns
only another bundle's own declaration of it. What actually composes this
bundle is the `includes:` entry, and what an `--app` install appends to
`~/.amplifier/settings.yaml` is the URI you passed. Stated plainly here so the
key is never mistaken for the mechanism.
