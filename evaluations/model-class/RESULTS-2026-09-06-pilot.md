# Pilot — which model class does the `suggest` judge need? (2026-09-06)

Run: `harness.py --variants haiku,sonnet,opus --scenarios planted,pure_task,already_known --limit 10 --concurrency 4`
— 90 real `amplifier run -p <variant>` calls against fixtures built from the steward's own recorded
sessions (10 planted / 10 pure-task / 10 already-known; seed 7). Results dir (not in git):
`.amplifier/evaluation/amplifier-bundle-memory/20260906-174307-model-class/`. Total spend: $14.87
(+ $2.73 fixture screening, + ~$1.40 judging extras).

| variant | shape ok | verbatim | recall (16 planted) | pure-task FP | already-known dedupe | precision | mean in tok | $/call | latency |
|---|---|---|---|---|---|---|---|---|---|
| haiku (small)  | 29/30 | 100% | 16/16 | 1 in 10 | 9/10 | 0.94 | 90.6k  | $0.042 | 10.2 s |
| sonnet (mid)   | 30/30 | 100% | 15/16 | 0 in 10 | 9/10 | 0.94 | 121.2k | $0.177 | 2.4 s |
| opus (large)   | 30/30 | 100% | 16/16 | 0 in 10 | 8/10 | 0.94 | 121.1k | $0.276 | 1.9 s |

(`summary.json` is the source; the numbers above were re-derived from the per-call records by hand
before writing this — the one discrepancy checked, opus dedupe 0.8, was a transcription slip in a
monitor's paste, not a harness bug.)

## Reading

1. **All three classes pass the bar the code needs.** Every quote any model returned was verbatim
   (`verify` 100%); recall on planted preferences was 16/16, 15/16, 16/16. With n=10 per scenario
   a one-item difference is noise, not a ranking.
2. **The small class has the one failure mode that matters.** haiku's single non-JSON reply
   (`pure_task/d34d7b31`) was not a formatting slip: the session's own human turns were a `/goal`
   transcript, and haiku *followed them* ("This goal cannot be achieved…") instead of judging them.
   Content in the turns steered the judge. The job's Core 10 path catches it (one `rejected`, run
   `degraded`), so nothing wrong reaches the inbox — but it is the class of failure a lean prompt
   must guard against: fence the turns as data, not instructions. haiku also produced the only
   pure-task false positive (a project goal proposed as a preference). Both are 1-in-30 events.
3. **Prompt-level "skip what is already in this list" is 80–90% across ALL classes** — and opus
   was worst (8/10). The four misses re-proposed a planted sentence with a paraphrased `text`; the
   code-side dedupe (`inbox.append`, exact normalized `text` against MEMORY.md/declined) would not
   catch a paraphrase, so a re-proposal can reach the inbox and cost the steward one decline.
   Candidate item (suggestions.v1 §4/§7): also key the known-set on the verbatim `quote`.
4. **Model class is not the cost lever; bundle weight is.** 85–120k of every call's input tokens is
   the default bundle's system prompt (behaviors attached from `settings.yaml`); the judging
   request itself is 2–5k tokens. `-B foundation` still loaded 115k. At today's weight a daily
   pass at the Core 8 ceiling is $1.3 (haiku) / $5.3 (sonnet) / $8.3 (opus). A bundle-free call
   path would cut every class by ~20×.
5. **Latency inverts expectation**: haiku 10 s mean vs opus 1.9 s. Measured, not explained
   (provider routing on this host); irrelevant for a nightly timer.
6. A CLI quirk, recorded for whoever debugs this later: `amplifier run --output-format json`'s
   `"model"` field printed `sol/gpt-5.6-sol` for every variant; the stderr usage line named the real
   model. The harness records stderr.

## What the job does today, and how a user would steer it

`default_model_call` runs `amplifier run --output-format json "<request>"` with **no** `-p/-m/-B`
— the job inherits the amplifier CLI's default provider, model and bundle (here: the starred
`opus` provider; 15 providers active). There is no amplifier-memory knob yet; users change the
model by changing the CLI's default (`amplifier provider`). `amplifier run` accepts
`-p PROVIDER -m MODEL -B BUNDLE`, so a pass-through is small. The contract does not freeze the
model (Reserved names only the gate and the session window); Core 8 asks for bounded, visible cost.

## Recommendation (pending the full pass)

- Default class: **mid (sonnet)** — clean shape and zero false positives in this sample at 60% of
  opus's cost; the large class buys nothing measurable here.
- Small (haiku) is acceptable *if* the request fences the turns as data and the run tolerates
  ~3% rejected replies — at ~15% of opus's cost. Worth one more scenario before choosing it.
- Cut bundle weight before choosing anything: it is 20× the model-class difference.

## Next

Full pass: `--variants haiku,sonnet,opus,sol,gemini` (adds gpt-5.6 and gemini), two seeds
(`build_fixtures.py --seed 8` for a fresh planted set), ≈ $30 at today's weight. Then decide the
default and file: (a) `--provider/--model/--bundle` pass-through + a lean bundle for the job,
(b) fence the turns in `compose_request`, (c) quote-keyed dedupe.

---

# Second pilot — the OpenAI-backed providers (2026-09-07)

Same fixtures (seed 7), same three scenarios, same `--limit 10`; 120 real calls. Results dir:
`.amplifier/evaluation/amplifier-bundle-memory/20260907-025546-model-class-openai/`. Spend: $16.58
priced (+ astra, which the CLI does not price) + ~$1.90 judging extras. Providers smoke-tested
first: `azure-openai` fails (`LLMError: Connection error`) and was left out; `openai-chatgpt` is
`gpt-5.6-sol` over a second transport and was left out as a duplicate.

| variant (model) | shape ok | verbatim | recall (16 planted) | pure-task FP | already-known: true dedupe misses | $/call | latency |
|---|---|---|---|---|---|---|---|
| sol (gpt-5.6-sol, reasoning high) | 30/30 | 100% | 16/16 | 0 in 10 | 1/10 | $0.353 | 4.7 s |
| terra (gpt-5.6-terra)             | 30/30 | 100% | 16/16 | 0 in 10 | 0/10 | $0.180 | 4.3 s |
| luna (gpt-5.6-luna)               | 30/30 | 100% | 16/16 | 0 in 10 | 1/10 | $0.020 | 4.4 s |
| astra (gpt-6-astra)               | 30/30 | 100% | 16/16 | 0 in 10 | 3/10 | unpriced | 7.5 s |

Numbers re-derived from the per-call records (summary.md agrees). Mean input **70.4k tokens** for
every OpenAI variant — the same bundle prompt the Anthropic tokenizer counted at 87–121k.

## Reading

1. **Every OpenAI variant was clean where the small Anthropic class slipped:** 120/120 replies were
   well-formed JSON, every quote verbatim, recall 16/16 across the board, zero pure-task false
   positives — no transcript hijack, no goal-as-preference.
2. **The harness's "dedupe" column over-counts.** It calls any non-empty `already_known` reply a
   miss. Reading the extras: one real sentence from the steward's own session (`e62af442`,
   "Strike the compaction gap issue, that is a 'how we wield it' issue …") was proposed by sol,
   terra and luna in `planted` **and** by terra and luna in `already_known` — that is the model
   finding a genuine, unplanted standing view, not a dedupe failure (the opus judge labelled it
   `standing_preference` eight times; in the first pilot it labelled the same sentence
   `task_instruction` once — the one item on which the judge itself disagrees). True re-proposals
   of a *known* planted line: sol 1, terra 0, luna 1, astra 3 — the same 0–30% band as Anthropic
   (haiku 1, sonnet 1, opus 2). Prompt-level dedupe is unreliable in every class; the fix is code.
3. **luna is the outlier that matters: $0.02 per call with a perfect scorecard** — 17× cheaper
   than opus, 9× cheaper than sonnet, 2× cheaper than haiku, and without haiku's two slips. A
   daily pass at the Core 8 ceiling costs **$0.60/day** at today's bundle weight, without any
   bundle work at all.
4. Reasoning-tier latency (4–12 s/call) is 2–6× the Anthropic large class. Irrelevant for a
   nightly timer; 30 calls at concurrency 1 is still under seven minutes.
5. astra (gpt-6) was the weakest on dedupe (7/10 empty) and the CLI prints no cost for it;
   nothing else distinguishes it here.

## Recommendation, both pilots together (7 variants, 210 calls, seed 7)

- **Default the job to a small, cheap model class and rely on the code's guards** — the eval says
  the judging task does not need a large model: 6 of 7 variants had perfect recall and verbatim
  quotes; the one shape failure and the one false positive in 210 calls both came from haiku and
  both were caught by Core 10 / `verify` before anything reached the inbox.
- Concretely, on this host: **`-p luna`** (gpt-5.6-luna) — $0.60/day at the ceiling, clean. For a
  user without an OpenAI-backed provider, **sonnet**; haiku only after fencing the turns as data.
- **The job needs a provider knob** to make that choice real: `amplifier-memory suggest
  --provider/--model` (persisted for the timer). Today it can only inherit the CLI default, which
  on this host is the most expensive variant measured ($0.276 opus).
- Bundle weight remains a real lever (70–120k of ~75k–125k input tokens is the system prompt) but
  with luna it is no longer the gating cost.
- Fix dedupe in code (quote-keyed as well as text-keyed): a prompt-level miss rate of 0–30% held
  across all seven models.

Caveat carried honestly: n = 10 sessions per scenario, one seed, fixtures from one person's
sessions. The ordering "cheap is enough" is supported by 210 calls; a 1-in-30 failure rate is not
distinguishable from zero at this size. A second seed and 20 sessions per scenario would tighten it
(~$5 with luna as the only variant).

---

# Third pilot — reasoning effort (2026-09-07)

Same fixtures (seed 7), scenarios `planted` + `pure_task` (the two that discriminate), `--limit 10`
→ 20 calls per variant, 220 calls. Variants are project-scoped provider entries (a scratch
`.amplifier/settings.yaml` under `.amplifier/evaluation/scope-reasoning/`, never the steward's
global settings) that copy luna/terra/haiku/sonnet and change only `reasoning_effort`. The
already-measured `high` rows from pilots 1–2 are repeated for comparison. Results dir:
`20260907-031137-model-class-reasoning/`. Spend ≈ $22.

| variant | shape ok | recall | pure-task FPs (of 10 sessions) | $/call | latency |
|---|---|---|---|---|---|
| luna none    | 20/20 | 16/16 | **4** | $0.02 | 3.2 s |
| luna minimal | 0/20 — endpoint rejects it: `'minimal' is not supported with the 'gpt-5.6-luna' model` | – | – | – | – |
| luna low     | 20/20 | 16/16 | 0 | $0.02 | 3.7 s |
| luna medium  | 20/20 | 16/16 | 0 | $0.02 | 3.9 s |
| luna high (pilot 2) | 30/30 | 16/16 | 0 | $0.02 | 4.4 s |
| terra none   | 20/20 | 16/16 | **2** | $0.18 | 3.2 s |
| terra low    | 20/20 | 16/16 | 1 | $0.18 | 3.6 s |
| terra medium | 20/20 | 16/16 | 0 | $0.18 | 3.7 s |
| terra high (pilot 2) | 30/30 | 16/16 | 0 | $0.18 | 4.3 s |
| haiku low    | 19/20 (a JSON syntax slip) | 15/16 | 0 | $0.041 | 8.0 s |
| haiku medium | 19/20 (the `/goal` hijack again) | 16/16 | 0 | $0.042 | 9.2 s |
| haiku high (pilot 1) | 29/30 | 16/16 | 1 | $0.042 | 10.2 s |
| sonnet low   | 20/20 | 16/16 | 0 | $0.22 | 1.6 s |
| sonnet medium| 20/20 | 16/16 | 0 | $0.19 | 1.6 s |
| sonnet high (pilot 1) | 30/30 | 15/16 | 0 | $0.18 | 2.4 s |

Extras re-read by hand from the per-call records (the judge pass was not re-run — the six
`none`/`low` false positives are unambiguous task talk: "I DO NOT want that session on the
team-shared, are you able to delete it?", "remember our goal is to create beautiful mock-ups…",
"Wait, why not design-gauntlet?"; the one genuine unplanted preference — the compaction-gap
sentence — surfaced again for six of ten variants and is not counted as a false positive).

## Reading

1. **Turning reasoning off costs precision, not recall.** With `none`, luna proposed four task
   instructions as preferences in ten pure-task sessions and terra two; every level from `low`
   up returned luna to zero and terra to ≤1. Recall was 16/16 at every level for the OpenAI
   models. The judge needs *some* deliberation to tell "always do X" from "do X now".
2. **Reasoning effort does not move cost here** — luna is $0.02 at every level, terra $0.18 —
   because the bundle system prompt (70k tokens) dwarfs the reasoning tokens. Latency rises
   ~0.2 s per step. So the cheapest *safe* setting on this host is **luna at `low`** (or the
   existing `high` entry; indistinguishable in this sample).
3. **haiku's slips are not a reasoning-level problem**: one malformed-JSON reply at `low`, one
   `/goal`-transcript hijack at `medium`, one hijack + one FP at `high` — 4 in 70 calls across
   levels, all caught by Core 10 / `parse_reply`. Fencing the turns as data is the fix, not
   more thinking.
4. **sonnet is clean at every level** (60/60 shape, 47/48 recall, 0 FP); `medium` is the cheapest
   of its levels.
5. `minimal` is a documented `reasoning_effort` value the OpenAI provider module accepts at mount,
   but this endpoint's gpt-5.6 models refuse it at request time; the job's fail-open path
   turned all 20 into `rejected`, exit 0. Worth a note in whichever knob exposes the setting.

## Where the model choice can live — the config question

What exists today: the job runs `amplifier run --output-format json` with no `-p/-m/-B`, so it
inherits the CLI default (starred provider + default bundle). Reasoning effort is a property of a
*provider entry* (`config.providers[].config.reasoning_effort`), not of `amplifier run`, so
"luna at low" means an entry like `luna-low` in the user's amplifier settings (global or project
scope), then `-p luna-low`.

What `amplifier-bundle-routing-matrix` offers: semantic roles (`fast`, `general`, …) mapped to
ranked provider/model candidates per matrix (`balanced`, `openai`, `economy`, …), resolved by
`hooks-routing` at session start — for **agents** (`meta.model_role` in frontmatter), for
**delegations** (`model_role` on the spawn), and for **recipe steps** (`model_role:`). It has
**no path for a root `amplifier run`**: there is no `--model-role` flag and app-cli reads no
root-level role. So today the job cannot say "fast" and be routed; it can only name a provider.

Three shapes, ranked:

1. **Knob now, role-ready.** One config table per LLM call type (today there is exactly one,
   the §3 judge): `provider` (an amplifier provider id → `-p`), optional `model` (→ `-m`),
   optional `bundle` (→ `-B`), and `role` (default `fast`) recorded for when the host can resolve
   it. Unset → inherit the CLI default, as now; the `suggest.log` line names what it used.
   `doctor` shows the resolved choice and its last measured cost. Serves Core 8 directly.
2. **Role via the matrix, resolved in the job** — read the active matrix's `fast` candidates
   and pick the first installed provider. Reuses the curated data but re-implements the
   resolver (and its pin/priority subtleties, see `role_pin.py`); brittle against matrix changes.
3. **Judge as a delegate with `model_role: fast`** inside a tiny job bundle — the ecosystem-native
   route, but it costs a root session *plus* a child per call (two bundle loads), doubling the
   dominant cost, for a job whose whole point is one cheap call.

Recommendation: **1**, with the `role` key present from day one and an upstream ask filed for
`amplifier run --model-role` (the same convention recipes use per step) so the knob can later
resolve `role` instead of `provider` without a schema change. Default on this host: `luna`
(gpt-5.6-luna) — at `low` or `high`, $0.02/call, $0.60/day at the Core 8 ceiling.
