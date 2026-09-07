# Upstream ask: `amplifier run --model-role <role>`

**To:** amplifier-app-cli · **From:** amplifier-bundle-memory · **Date:** 2026-09-07
**Status:** filed, not yet raised upstream · **Blocks:** nothing (this bundle ships the
provider knob today and works without it)

## The ask

Give a **root** `amplifier run` a way to name a *semantic role* instead of a concrete
provider:

```bash
amplifier run --model-role fast --output-format json "<prompt>"
```

resolving through the active routing matrix exactly the way `model_role:` already
resolves on a recipe step and in agent frontmatter — through the `model_role_resolver`
capability `amplifier-bundle-routing-matrix`'s `hooks-routing` registers. Same
vocabulary, same matrices, same precedence shape as a delegate:

- an explicit `-p` / `-m` wins over `--model-role` (a hard pin stays a hard pin);
- `--model-role` with no routing bundle installed is a no-op, not an error — the run
  falls back to the CLI default, exactly as an agent's `model_role:` does today;
- a list is as welcome as a scalar (`--model-role vision --model-role general`), matching
  the fall-through agents already have.

## Why — the gap, measured on this device

`amplifier run` has flags for *which provider* but none for *what kind of model*:

```
$ amplifier run --help
  -B, --bundle TEXT               Bundle to use for this session
  -p, --provider TEXT             LLM provider to use
  -m, --model TEXT                Model to use (provider-specific)
      --max-tokens INTEGER        Maximum output tokens
      --mode [chat|single]        Execution mode
      --resume TEXT               Resume specific session with new prompt
  -v, --verbose                   Verbose output
      --output-format [text|json|json-trace]
```

Verified 2026-09-07 against `amplifier, version 2026.09.07-be25afd (core 1.6.1)`:

| Claim | How it was checked | Result |
|---|---|---|
| `amplifier run` has no role flag | `amplifier run --help` | no `--model-role` (above) |
| the `run` command reads no role | `grep -n model_role amplifier_app_cli/main.py` | **0 hits** |
| roles exist, but only off the spawn path | `grep -rln model_role amplifier_app_cli` | `session_spawner.py`, `agent_config.py`, `session_runner.py`, `runtime/config.py`, `lib/routing_provenance.py`, `utils/settings_manager.py` |
| `session_runner`'s role parameter is the sub-session one | `grep -n model_role session_runner.py` | 2 hits, both inside `resume_capability` (mirroring `spawn_capability`) |
| the resolver's own consumers are named in code | `hooks-routing/__init__.py:371` | `# Consumers: tool-delegate, hooks-session-naming, tool-recipes, tool-skills` |
| `fast` is always available to ask for | `routing/*.yaml` (9 matrices) | "Required roles: `general` and `fast` must be defined in every matrix" |

So the capability, the vocabulary and the matrices are all present and shipped — a root
`amplifier run` is simply not one of the four consumers. Roles resolve for **agents**
(`meta.model_role` in frontmatter, at `session:start`), for **delegations**
(`model_role=` on the spawn) and for **recipe steps** (`model_role:`). There is no
root-level role to read.

## The cost this bundle paid for it

`amplifier-memory suggest` makes one LLM call per recorded session, up to 30 a night
(suggestions.v1 Core 8). Until this wave it ran `amplifier run --output-format json` with
no provider flag at all, so it inherited whatever the CLI's starred provider happened to
be. Measured across 7 variants and 210 real calls
(`evaluations/model-class/RESULTS-2026-09-06-pilot.md`):

- inherited default on this device: **$0.276/call** (opus) — $8.30/night at the ceiling;
- a measured-clean alternative: **$0.02/call** (`gpt-5.6-luna`, perfect scorecard —
  30/30 shape, 16/16 recall, 0 false positives) — $0.60/night;
- the judging task does not need a large model: 6 of 7 variants had perfect recall and
  verbatim quotes.

A factor of **17×** on the same task, invisible to the user, decided by a default nobody
chose for this job.

This bundle now ships the knob (`${AMPLIFIER_MEMORY_CONFIG:-~/.amplifier/memory-config.toml}`,
`[llm.judge] provider = "luna"`), which closes the cost hole. What it cannot close is
portability, and that is what this ask is for:

> **A provider id is local to one device; a role is not.**

`luna` is an entry in *this* steward's amplifier settings. This bundle is installed by
URL on other machines, where that id may not exist. So the shipped default has to be
"inherit the CLI default" — i.e. the expensive one, again — and every user has to
discover the pilot's findings and hand-write a provider id of their own. `role = "fast"`
would be a default we could actually ship: portable, resolved locally by whatever matrix
that device runs, and already the exact word every matrix is required to define.

## What we did instead, and why the alternatives lose

Three shapes were considered (pilot 3, "Where the model choice can live"):

1. **A provider knob now, role-ready** — shipped. One TOML table per LLM call type;
   `provider`/`model`/`bundle` become `-p`/`-m`/`-B`; **`role` is recorded and logged from
   day one** so nothing changes shape when the flag arrives.
2. **Resolve the matrix ourselves in the job** — read the active matrix's `fast`
   candidates and pick the first installed provider. Rejected: it re-implements the
   resolver and its pin/priority subtleties (`hooks-routing/role_pin.py`), and goes stale
   the moment the matrix format moves. Duplicating a resolver that already exists as a
   registered capability is exactly the kind of moving part this repo refuses (AGENTS.md
   non-negotiable 1).
3. **Make the judge a delegate with `model_role: fast`** inside a tiny job bundle — the
   ecosystem-native route, and the one that would work today. Rejected on cost: it needs
   a root session *plus* a child per call, i.e. two bundle loads, and the bundle system
   prompt is already 70–120k of the ~75–125k input tokens per call. It doubles the
   dominant cost of a job whose entire point is one cheap call.

## How this bundle will use the flag, the day it lands

`src/amplifier_memory/llm_config.py` already carries the key:

```toml
[llm.judge]
provider = "luna"   # -> `amplifier run -p`
model = ""          # -> `-m`
bundle = ""         # -> `-B`
role = "fast"       # recorded and logged today; resolved when the host can
```

`doctor`'s `llm judge` row already prints it, honestly, as
`role fast (recorded; not resolved — `amplifier run` has no --model-role)`.

When the flag exists, one function changes: `suggest.build_argv` appends
`--model-role <role>` when the config names a role and no explicit provider —
provider stays the override, role becomes the portable default. No schema change, no
migration, no new config key. The shipped default can then move from "inherit whatever is
starred" to `role = "fast"`, which is both cheaper and correct on a machine nobody here
has seen.

## Not asked for

- Reasoning effort. That is a property of a *provider entry*
  (`config.providers[].config.reasoning_effort`), not of `amplifier run`, and the pilots
  show it belongs there: "luna at low" is an entry named `luna-low`, selected with `-p`.
  Measured caveat for whoever documents it: `minimal` is accepted at provider mount but
  refused at request time by this endpoint's gpt-5.6 models.
- Any change to how roles resolve. The matrices, the fall-through and the precedence are
  fine; the ask is only that a root run be allowed to participate.
