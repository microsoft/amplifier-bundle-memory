# model-class — which model does the `suggest` judge need?

`src/amplifier_memory/suggest.py` is a daily job. For each recorded session it sends
**one** request to a model —
`compose_request(build_prompt(memory_lines, declined), human_turns)` — asking for the
standing preferences the human stated, as a JSON list of `{"text", "quote"}`. Code then
`parse_reply`s it and `verify`s every quote verbatim against that session's human turns.

Everything after the model is deterministic. The model is the only variable, and today it
is whatever `amplifier run --output-format json` happens to default to. This evaluation
answers the question that leaves open: **which model class is good enough for this one
job, and what does each one cost?**

## What it measures

Three scenarios, each isolating one way the judge can be wrong.

| scenario | fixture | a correct model returns | it measures |
| --- | --- | --- | --- |
| `planted` | 10 real sessions, each with 1–2 standing preferences inserted as new human turns | exactly those, quoted verbatim | **recall** — does it find a preference that is really there? |
| `pure_task` | 10 *different* real sessions, untouched, screened to contain no standing preference | `[]` | **restraint** — does it invent one when there is none? |
| `already_known` | the 10 planted sessions again, with every planted text already in `memory_lines` | `[]` | **deduplication** — does it honour §3's "anything already in this list"? |

Metrics per variant (`summary.md` / `summary.json`):

- **shape ok %** — replies `parse_reply` accepts. A model that writes prose fails the job
  outright: `run_suggest` counts a malformed reply as rejected and proposes nothing.
- **verbatim %** — candidates whose quote passes `verify`. A quote that fails is a
  fabrication the job's poisoning gate throws away (AGENTS.md rule 7).
- **recall** — planted preferences found / planted.
- **extras** — candidates matching no planted sentence. Not automatically errors: a real
  session may hold a real preference the planting did not add. `judge_extras.py` labels
  them and turns that into **precision**.
- **pure_task FP/session** — candidates per screened, preference-free session.
- **already_known dedupe** — fraction of `already_known` calls that returned `[]`.
- **mean in tok · mean $ · total $ · mean latency s · model seen** — read off the CLI's
  own stderr usage block, not estimated.

`precision = planted_hits / (planted_hits + extras judged non-preference)`, added as a
column by `judge_extras.py`.

## The shelled argv

`amplifier run -p <variant> [-B <bundle>] --output-format json "<request>"` — the job's
own `suggest.RUN_ARGV` with the flags inserted, built by `harness.build_argv`. Verified
against the CLI's `--help` on this device 2026-09-06 (AGENTS.md rule 5):

```
$ amplifier run --help
Usage: amplifier run [OPTIONS] [PROMPT]

  Execute a prompt or start an interactive session.

Options:
  -B, --bundle TEXT               Bundle to use for this session
  -p, --provider TEXT             LLM provider to use
  -m, --model TEXT                Model to use (provider-specific)
  --max-tokens INTEGER            Maximum output tokens
  --mode [chat|single]            Execution mode
  --resume TEXT                   Resume specific session with new prompt
  -v, --verbose                   Verbose output
  --output-format [text|json|json-trace]
                                  Output format: text (markdown), json
                                  (response only), json-trace (full execution
                                  detail)
  --help                          Show this message and exit.
```

Variants are provider names. The ones on this host (`amplifier provider list`):
`haiku` (small) · `sonnet` (mid) · `opus` (large) · `sol` (gpt-5.6) · `gemini`.

**stdout's `"model"` key is not the model that answered.** Measured on this device
2026-09-06: a `-p haiku` call printed `"model": "sol/gpt-5.6-sol"` on stdout while stderr
said `anthropic/claude-haiku-4-5`. The harness records the **stderr** string, from the
CLI's usage block:

```
│  📊 Token Usage (anthropic/claude-haiku-4-5) [2.7s]
└─ Input: 86,854 (69% cached) | Output: 167 | Total: 87,021 | Cost: $0.04
```

## Building the fixtures

```bash
cd amplifier-bundle-memory
uv run python evaluations/model-class/build_fixtures.py --seed 7
```

Reads **real** sessions from `suggest.substrate_root()` through the job's own
`read_session`, keeping only root sessions (`is_root_session_id`) that this job did not
spawn (`spawned_by_this_job`), with 3–12 human turns of 20–1500 characters each, whose
bundle does not contain `evaluation`. The directory list is shuffled with a seeded RNG
*before* anything is read, so the sample is random, reproducible, and does not require
reading every transcript on the device.

`pure_task` candidates are then **screened**: one `amplifier run -p opus` call each asking
`"Does any of these human turns state a standing preference or correction meant to hold
beyond this task? Reply only YES or NO."` Only a clear NO is kept; the run stops at 10
kept or 25 screens, whichever comes first, and every screen is recorded in
`fixtures/screening.json`. Cost: **≤25 opus calls**.

Output, all under `evaluations/model-class/fixtures/`:
`planted.json` · `pure_task.json` · `already_known.json` · `screening.json`.

Measured on this device 2026-09-06 with `--seed 7`: **6,901** root session directories
walked, **2,409** transcripts read, **44** usable sessions kept (the rest lost to 1,710
with the wrong number of human turns, 4,471 unreadable or without a transcript, 381
`evaluation` bundles, 274 with an out-of-range turn, 21 transcripts over 8 MB). Screening
stopped at **10 calls** — every one came back `NO` — for **$2.73** total.

> **The fixtures are the steward's own session text and are git-ignored.** They are never
> committed, and `build_fixtures.py` refuses to write into a directory `git check-ignore`
> does not cover. Only `preferences.json` — invented sentences — is committed.

## Running it

```bash
cd amplifier-bundle-memory

# smoke — 1 real haiku call on 1 planted fixture. Proves the wiring, costs cents.
uv run python evaluations/model-class/harness.py --smoke

# pilot — 3 variants × 3 scenarios × 10 fixtures = 90 calls.
uv run python evaluations/model-class/harness.py \
  --variants haiku,sonnet,opus \
  --scenarios planted,pure_task,already_known \
  --limit 10 --concurrency 4

# full — 5 variants × 3 scenarios × 10 fixtures = 150 calls.
uv run python evaluations/model-class/harness.py \
  --variants haiku,sonnet,opus,sol,gemini \
  --scenarios planted,pure_task,already_known \
  --limit 10 --concurrency 4

# then label the extras and add the precision column (one opus call per session
# that produced extras — pass --dry-run first to see how many that is).
uv run python evaluations/model-class/judge_extras.py <results-dir> --dry-run
uv run python evaluations/model-class/judge_extras.py <results-dir>
```

Flags: `--variants` · `--scenarios` · `--limit N` (fixtures per scenario) ·
`--concurrency N` (default 4) · `--bundle NAME` (passed through as `-B`) · `--out DIR` ·
`--smoke`.

Calls are retried **once** on a nonzero exit or a 300 s timeout, and the retry is recorded
— a variant that needs a second attempt half the time is telling you something about its
fitness for an unattended daily job.

## Cost expectations

Two calls were actually metered on this device on 2026-09-06, and they set the scale:

| call | input tok | output tok | latency | cost |
| --- | --- | --- | --- | --- |
| smoke, `-p haiku`, one planted fixture | 87,200 | 874 | 8.4 s | **$0.11** |
| fixture screen, `-p opus`, one session, replies `NO` | ~87,000 | ~5 | — | **$0.27** |

**The request is a few thousand tokens; the other ~85,000 are the bundle's own system
prompt, and every call pays for them.** That is the dominant cost term, not the model's
answer, which is why `--bundle` is the biggest lever here.

Extrapolating from those two (a real run's opus and sonnet answers will be longer than a
bare `NO`, so treat these as ranges, not quotes):

| run | calls | budget |
| --- | --- | --- |
| smoke | 1 haiku | **$0.11**, measured |
| fixture build | ≤25 opus | $0.27 each → ≤ **$6.75** (**$2.73** actual, 10 screens) |
| pilot (3 variants × 30) | 90 | **$20–40**, dominated by the opus third |
| full (5 variants × 30) | 150 | **$35–70** |
| `judge_extras` | 1 opus per session with extras | ~$0.30 each |

Levers: `--bundle` (a smaller bundle means a smaller system prompt on every call) and
`--limit`. Run `--limit 2` first if the budget is tight — the shape of the answer usually
shows up there. The CLI prints `Cost: $…` to two decimals, so read **totals**, not single
calls.

## Where results land

`~/dev/amplifier-memory-team-ci/.amplifier/evaluation/amplifier-bundle-memory/<YYYYMMDD-HHMMSS>-model-class/`
(override with `--out`; `.amplifier/` is git-ignored at the workspace root):

```
<variant>/<scenario>/<session8>.json   the request, the raw reply, every candidate,
                                       usage, retries — one file per call
summary.json                           every metric, per variant and per scenario
summary.md                             the readable table
judged.json                            judge_extras.py's labels (second pass)
```

## Tests

```bash
uv run pytest -q evaluations/model-class
```

Pure functions only — usage-line parsing against real ANSI-laden stderr, planted matching,
summary math, precision math. **No test makes a model call**: `harness.run_amplifier`,
`build_fixtures.screen` and `judge_extras.main` all pass through
`harness.refuse_under_pytest`, and one test asserts `--smoke` refuses to run under pytest.
This is the same door `suggest.default_model_call` already bolts shut.
