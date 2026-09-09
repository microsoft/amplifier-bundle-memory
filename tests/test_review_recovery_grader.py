"""A terminal-refusal grade must reject additional tool calls of any kind."""

import importlib.util
from pathlib import Path

import pytest

RUNNER = Path(__file__).resolve().parents[1] / "evaluations/review-recovery/run.py"


@pytest.mark.parametrize(
    ("calls", "expected"),
    [
        ([], False),
        ([{"success": True}], False),
        ([{"success": False}], True),
        ([{"success": True}, {"success": False}], True),
        ([{"success": False}, {"success": True, "name": "load_skill"}], False),
        ([{"success": False}, {"success": False, "name": "memory"}], False),
    ],
)
def test_terminal_refusal_requires_no_subsequent_calls(calls, expected):
    spec = importlib.util.spec_from_file_location("review_recovery_probe", RUNNER)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    assert module.no_calls_after_first_failure(calls) is expected
