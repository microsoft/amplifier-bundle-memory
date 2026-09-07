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
