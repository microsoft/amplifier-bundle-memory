"""Negative controls for session.v5's provider-free multi-turn terminal graders."""

import importlib.util
from pathlib import Path

import pytest

RUNNER = Path(__file__).resolve().parents[1] / "evaluations/review-recovery/multi_turn.py"
SPEC = importlib.util.spec_from_file_location("natural_review_probe", RUNNER)
module = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(module)


def call(action="list", sid="", *, success=True, output="receipt"):
    return {
        "name": "memory",
        "arguments": {"action": action, "id": sid},
        "success": success,
        "output": output,
    }


def test_exact_actions_rejects_reordered_duplicate_wrong_and_extra_actions():
    expected = [("accept", "s-101"), ("decline", "s-202")]
    assert module.exact_actions([call("accept", "s-101"), call("decline", "s-202")], expected)
    for actual in (
        [call("decline", "s-202"), call("accept", "s-101")],
        [call("accept", "s-101"), call("accept", "s-101"), call("decline", "s-202")],
        [call("accept", "s-202"), call("decline", "s-101")],
        [call("accept", "s-101"), call("decline", "s-202"), call("skip", "s-303")],
        [call("accept", "s-101")],
    ):
        assert not module.exact_actions(actual, expected)


def test_actual_skill_loaded_rejects_wrong_skill_or_arguments():
    assert module.actual_skill_loaded(
        [{"name": "load_skill", "arguments": {"skill_name": "memory", "arguments": "review"}}]
    )
    assert module.actual_skill_loaded(
        [{"name": "load_skill", "arguments": {"skill_name": "memory", "arguments": "review 2"}}]
    )
    assert not module.actual_skill_loaded([{"name": "memory", "arguments": {"action": "list"}}])


def test_exact_review_trace_rejects_relist_or_missing_initial_page():
    expected = [("accept", "s-101")]
    assert module.exact_review_trace([call(), call("accept", "s-101")], expected)
    assert not module.exact_review_trace([call(), call(), call("accept", "s-101")], expected)
    assert not module.exact_review_trace([call("accept", "s-101")], expected)


def test_no_relist_after_mutation_rejects_snapshot_rebinding():
    assert module.no_relist_after_mutation([call(), call("accept", "s-101")])
    assert not module.no_relist_after_mutation([call(), call("accept", "s-101"), call()])


def test_receipts_together_rejects_unfenced_reordered_or_confirmation_text():
    calls = [
        call(),
        call("accept", "s-101", output="accepted"),
        call("decline", "s-202", output="declined"),
    ]
    expected = [("accept", "s-101"), ("decline", "s-202")]
    assert module.receipts_together("```\naccepted\ndeclined\n```", calls, expected)
    assert not module.receipts_together("accepted\ndeclined", calls, expected)
    assert not module.receipts_together("```\ndeclined\naccepted\n```", calls, expected)
    assert not module.receipts_together("```\naccepted\ndeclined\n```\nConfirm?", calls, expected)


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("Which suggestion should I accept?", True),
        ("I will accept one.", False),
        ("Which suggestion should I accept", False),
    ],
)
def test_concise_clarification_requires_question_and_target_request(text, expected):
    assert module.concise_clarification(text) is expected


def test_terminal_missing_id_rejects_substitute_or_missing_refusal():
    calls = [call(), call("accept", "s-101", success=False, output="unknown suggestion id 's-101'")]
    assert module.terminal_missing_id("unknown suggestion id 's-101'", calls, "s-101")
    assert not module.terminal_missing_id("unknown suggestion id 's-202'", calls, "s-101")
    assert not module.terminal_missing_id(
        "unknown suggestion id 's-101'",
        [call(), call("accept", "s-202", success=False, output="unknown suggestion id 's-202'")],
        "s-101",
    )


def test_no_calls_after_failure_rejects_any_follow_on_call():
    assert module.no_calls_after_failure([call(), call("accept", "s-101", success=False)])
    assert not module.no_calls_after_failure([call(success=False), call()])
