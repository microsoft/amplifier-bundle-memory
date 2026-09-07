"""The harness's pure functions, with no model behind them.

Nothing here makes a call: `harness.run_amplifier`, `build_fixtures.screen` and
`judge_extras.judge_one` all pass through `harness.refuse_under_pytest`, and the last
test in this file is the proof that `--smoke` cannot spend money from inside the suite.

`REAL_STDERR` is the verbatim stderr of a real `amplifier run -p haiku --output-format
json` on the steward's device (2026-09-06), colour codes and all. It is the fixture
because the usage regexes exist to read *that*, not a tidied version of it.
"""

from __future__ import annotations

import json

import harness
import judge_extras
import pytest

# --------------------------------------------------------------------------- the CLI's stderr

REAL_STDERR = (
    "[amplifier-memory] 2 memories loaded. /memory to see them.\n"
    "[amplifier-memory] 1 suggestion waiting. /memory review to see it.\n"
    "\n"
    "\x1b[36m\U0001f9e0 Thinking...\x1b[0m\n"
    "\n"
    "================================================================================\n"
    "Thinking:\n"
    "--------------------------------------------------------------------------------\n"
    'The user is asking me to reply with exactly "ok". Took [0.4s] of deliberation.\n'
    "================================================================================\n"
    "\n"
    "\n"
    "\x1b[2m\u2502  \U0001f4ca Token Usage (anthropic/claude-haiku-4-5) [2.7s]\x1b[0m\n"
    "\x1b[2m\u2514\u2500 Input: 86,854 (69% cached) | Output: 167 | Total: 87,021 | "
    "Cost: $0.04\x1b[0m\n"
    "\x1b[2m\U0001f4b0 Turn: $0.04 | Session: $0.04\x1b[0m\n"
)


def test_strip_ansi_removes_the_colour_codes():
    assert "\x1b" not in harness.strip_ansi(REAL_STDERR)
    assert "Token Usage (anthropic/claude-haiku-4-5) [2.7s]" in harness.strip_ansi(REAL_STDERR)


def test_parse_usage_reads_the_real_ansi_laden_usage_block():
    usage = harness.parse_usage(REAL_STDERR)
    assert usage.model == "anthropic/claude-haiku-4-5"
    assert usage.models == ["anthropic/claude-haiku-4-5"]
    assert usage.input_tokens == 86854
    assert usage.output_tokens == 167
    assert usage.cost_usd == pytest.approx(0.04)
    assert usage.latency_s == pytest.approx(2.7)
    assert usage.blocks == 1


def test_parse_usage_ignores_a_bracketed_seconds_outside_the_usage_line():
    """The thinking block above carries `[0.4s]`; only the Token Usage line is a latency."""
    assert harness.parse_usage(REAL_STDERR).latency_s == pytest.approx(2.7)


def test_parse_usage_sums_every_iteration_of_a_multi_block_call():
    stderr = (
        "\u2502  \U0001f4ca Token Usage (anthropic/claude-sonnet-4-5) [1.5s]\n"
        "\u2514\u2500 Input: 1,000 | Output: 10 | Total: 1,010 | Cost: $0.01\n"
        "\u2502  \U0001f4ca Token Usage (anthropic/claude-sonnet-4-5) [2.5s]\n"
        "\u2514\u2500 Input: 2,500 | Output: 40 | Total: 2,540 | Cost: $0.03\n"
    )
    usage = harness.parse_usage(stderr)
    assert usage.blocks == 2
    assert usage.input_tokens == 3500
    assert usage.output_tokens == 50
    assert usage.cost_usd == pytest.approx(0.04)
    assert usage.latency_s == pytest.approx(4.0)
    assert usage.models == ["anthropic/claude-sonnet-4-5"]


def test_parse_usage_of_a_silent_stderr_is_all_none_not_a_crash():
    usage = harness.parse_usage("")
    assert (usage.model, usage.input_tokens, usage.cost_usd, usage.latency_s) == (
        None,
        None,
        None,
        None,
    )
    assert usage.blocks == 0


# --------------------------------------------------------------------------- the argv


def test_build_argv_is_the_jobs_own_argv_with_the_flags_inserted():
    assert harness.build_argv("ask", "haiku") == [
        "amplifier",
        "run",
        "-p",
        "haiku",
        "--output-format",
        "json",
        "ask",
    ]
    assert harness.build_argv("ask", "opus", "anchors") == [
        "amplifier",
        "run",
        "-p",
        "opus",
        "-B",
        "anchors",
        "--output-format",
        "json",
        "ask",
    ]


def test_reply_text_tolerates_the_cli_preamble_before_the_json():
    stdout = 'Bundle \'anchors\' prepared successfully\n{"status": "success", "response": "[]"}\n'
    assert harness.reply_text(stdout) == "[]"


def test_reply_text_refuses_stdout_with_no_assistant_text():
    with pytest.raises(ValueError, match="no string 'response'"):
        harness.reply_text('{"status": "error"}')


# --------------------------------------------------------------------------- planted matching

PLANTED = ["Always run the full test suite before you tell me a change is done."]


def test_match_planted_exact_after_whitespace_normalisation():
    assert harness.match_planted(PLANTED[0], PLANTED) == (0, "exact")
    rewrapped = "Always run the full test suite\n  before you tell me   a change is done."
    assert harness.match_planted(rewrapped, PLANTED) == (0, "exact")


def test_match_planted_accepts_a_verbatim_substring_either_way_and_says_which():
    longer = "He said: Always run the full test suite before you tell me a change is done. Ok?"
    assert harness.match_planted(longer, PLANTED) == (0, "candidate_contains_planted")
    shorter = "Always run the full test suite"
    assert harness.match_planted(shorter, PLANTED) == (0, "planted_contains_candidate")


def test_match_planted_returns_nothing_for_an_unrelated_or_empty_quote():
    assert harness.match_planted("Use tabs, not spaces.", PLANTED) == (None, None)
    assert harness.match_planted("   ", PLANTED) == (None, None)
    assert harness.match_planted(PLANTED[0], []) == (None, None)


def test_match_planted_prefers_the_exact_planted_sentence_over_a_substring_one():
    planted = ["Use uv for Python.", "Use uv for Python, not pip."]
    assert harness.match_planted("Use uv for Python, not pip.", planted) == (1, "exact")


# --------------------------------------------------------------------------- scoring a reply

FIXTURE = {
    "session_id": "11111111-2222-3333-4444-555555555555",
    "human_turns": [
        "Fix the failing import in cli.py.",
        "Always run the full test suite before you tell me a change is done.",
        "Also the retry loop lives in service.py.",
    ],
    "planted": [{"text": "Always run the tests first.", "quote": PLANTED[0]}],
    "memory_lines": [],
}


def test_score_reply_counts_a_planted_hit_and_leaves_no_extras():
    reply = json.dumps([{"text": "Run the tests first", "quote": PLANTED[0]}])
    scored = harness.score_reply(reply, FIXTURE)
    assert scored["shape_ok"] is True
    assert (scored["planted_hits"], scored["planted_total"]) == (1, 1)
    assert scored["extras"] == []
    assert scored["candidates"][0]["verified"] is True
    assert scored["candidates"][0]["match_kind"] == "exact"


def test_score_reply_calls_an_unplanted_candidate_an_extra_and_verifies_it_separately():
    reply = json.dumps(
        [
            {"text": "Tests first", "quote": PLANTED[0]},
            {
                "text": "Retry loop lives in service.py",
                "quote": "the retry loop lives in service.py",
            },
            {"text": "Invented", "quote": "Never deploy on a Friday."},
        ]
    )
    scored = harness.score_reply(reply, FIXTURE)
    assert scored["planted_hits"] == 1
    assert len(scored["extras"]) == 2
    assert [extra["verified"] for extra in scored["extras"]] == [True, False]


def test_score_reply_records_a_malformed_reply_rather_than_guessing_at_it():
    scored = harness.score_reply("Sure! Here are the preferences I found:", FIXTURE)
    assert scored["shape_ok"] is False
    assert "not JSON" in scored["parse_error"]
    assert scored["planted_hits"] == 0
    assert scored["planted_missed"] == ["Always run the tests first."]


def test_score_reply_of_an_empty_list_is_well_shaped_with_no_candidates():
    scored = harness.score_reply("[]", FIXTURE)
    assert (scored["shape_ok"], scored["candidates"], scored["extras"]) == (True, [], [])


# --------------------------------------------------------------------------- summary math


def _record(variant, scenario, **kw):
    base = {
        "variant": variant,
        "scenario": scenario,
        "shape_ok": True,
        "parse_error": None,
        "candidates": [],
        "extras": [],
        "planted_total": 0,
        "planted_hits": 0,
        "retries": 0,
        "error": None,
        "usage": {
            "model": "m",
            "models": ["m"],
            "input_tokens": 1000,
            "output_tokens": 10,
            "cost_usd": 0.02,
            "latency_s": 2.0,
            "blocks": 1,
        },
    }
    base.update(kw)
    return base


def _candidate(quote, *, verified=True, planted_index=None, kind=None):
    return {
        "text": "t",
        "quote": quote,
        "verified": verified,
        "planted_index": planted_index,
        "match_kind": kind,
    }


def test_summarize_variant_computes_recall_dedupe_restraint_and_cost():
    hit = _candidate("q1", planted_index=0, kind="exact")
    extra = _candidate("q9", verified=False)
    records = [
        _record(
            "haiku",
            "planted",
            planted_total=2,
            planted_hits=1,
            candidates=[hit, extra],
            extras=[extra],
        ),
        _record(
            "haiku", "planted", planted_total=2, planted_hits=2, candidates=[hit, hit], extras=[]
        ),
        _record("haiku", "pure_task", candidates=[extra], extras=[extra]),
        _record("haiku", "pure_task", candidates=[], extras=[]),
        _record("haiku", "already_known", candidates=[], extras=[]),
        _record("haiku", "already_known", candidates=[extra], extras=[extra]),
    ]
    row = harness.summarize_variant(records)
    assert row["calls"] == 6
    assert row["shape_ok_pct"] == 100.0
    assert row["recall"] == pytest.approx(3 / 4)  # 3 hits of 4 planted
    assert row["verbatim_pct"] == pytest.approx(100.0 * 3 / 6, rel=1e-3)
    assert row["extras"] == 3
    assert row["pure_task_false_positives"] == 1
    assert row["pure_task_fp_per_session"] == pytest.approx(0.5)
    assert row["already_known_dedupe_rate"] == pytest.approx(0.5)
    assert row["mean_input_tokens"] == pytest.approx(1000)
    assert row["mean_cost_usd"] == pytest.approx(0.02)
    assert row["total_cost_usd"] == pytest.approx(0.12)
    assert row["mean_latency_s"] == pytest.approx(2.0)
    assert row["models_seen"] == ["m"]


def test_summarize_variant_reports_none_rather_than_zero_when_a_scenario_was_not_run():
    row = harness.summarize_variant([_record("opus", "planted", planted_total=1, planted_hits=1)])
    assert row["recall"] == 1.0
    assert row["pure_task_fp_per_session"] is None
    assert row["already_known_dedupe_rate"] is None
    assert row["verbatim_pct"] is None


def test_summarize_variant_counts_a_failed_call_as_not_shape_ok():
    records = [
        _record(
            "haiku", "planted", shape_ok=False, parse_error="call failed: exit 1", error="exit 1"
        ),
        _record("haiku", "planted", planted_total=1, planted_hits=1),
    ]
    row = harness.summarize_variant(records)
    assert (row["shape_ok"], row["shape_ok_pct"], row["failed_calls"]) == (1, 50.0, 1)


def test_summarize_splits_by_variant_and_keeps_a_per_scenario_breakdown():
    summary = harness.summarize(
        [
            _record("haiku", "planted", planted_total=1, planted_hits=1),
            _record("opus", "planted", planted_total=1, planted_hits=0),
            _record("opus", "pure_task"),
        ],
        {"limit": 1},
    )
    assert sorted(summary["variants"]) == ["haiku", "opus"]
    assert summary["variants"]["opus"]["recall"] == 0.0
    assert sorted(summary["variants"]["opus"]["scenarios"]) == ["planted", "pure_task"]
    assert summary["meta"]["calls"] == 3


def _header_row(markdown: str) -> str:
    return next(line for line in markdown.splitlines() if line.startswith("| variant |"))


def test_render_summary_md_has_no_precision_column_until_extras_are_judged():
    summary = harness.summarize([_record("haiku", "planted", planted_total=1, planted_hits=1)])

    plain = harness.render_summary_md(summary)
    assert "precision" not in _header_row(plain)
    assert "haiku" in plain

    judged = harness.render_summary_md(summary, {"haiku": 0.75})
    assert _header_row(judged).rstrip().endswith("| precision |")
    assert "0.75" in judged


# --------------------------------------------------------------------------- judge_extras


def test_parse_labels_reads_a_fenced_json_list_in_index_order():
    reply = '```json\n[{"index": 2, "label": "code_fact"}, {"index": 1, "label": "other"}]\n```'
    assert judge_extras.parse_labels(reply, 2) == ["other", "code_fact"]


def test_parse_labels_of_prose_or_a_bad_label_falls_back_to_other():
    assert judge_extras.parse_labels("They all look like preferences to me!", 3) == ["other"] * 3
    assert judge_extras.parse_labels('[{"index": 1, "label": "vibes"}]', 1) == ["other"]


def test_precision_is_hits_over_hits_plus_judged_noise():
    summary = harness.summarize(
        [
            _record("haiku", "planted", planted_total=4, planted_hits=3),
            _record("opus", "planted", planted_total=4, planted_hits=4),
        ]
    )
    judged = [
        {
            "variant": "haiku",
            "extras": [
                {"label": "task_instruction"},
                {"label": "standing_preference"},
                {"label": "other"},
            ],
        }
    ]
    precision = judge_extras.precision_by_variant(summary, judged)
    assert precision["haiku"] == pytest.approx(3 / 5)  # 3 hits, 2 non-preference extras
    assert precision["opus"] == 1.0


def test_precision_is_none_when_a_variant_found_nothing_at_all():
    summary = harness.summarize([_record("haiku", "pure_task")])
    assert judge_extras.precision_by_variant(summary, [])["haiku"] is None


# --------------------------------------------------------------------------- the money door


def test_smoke_flag_shapes_the_run_without_running_it():
    args = harness.parse_args(["--smoke"])
    assert (args.variants, args.scenarios, args.limit) == ("haiku", "planted", 1)


def test_the_harness_refuses_to_make_a_real_call_from_the_suite():
    with pytest.raises(RuntimeError, match="refusing to run the harness"):
        harness.main(["--smoke"])
    with pytest.raises(RuntimeError, match="refusing to call the model"):
        harness.run_amplifier("ask", "haiku")
    with pytest.raises(RuntimeError, match="refusing to judge extras"):
        judge_extras.main(["/nonexistent"])


def test_an_unknown_scenario_is_refused_by_name():
    with pytest.raises(SystemExit, match="unknown scenario"):
        harness.main(["--scenarios", "planted,made_up"])
