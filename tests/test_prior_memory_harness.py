"""Provider-free negative controls for the prior-memory recorder checker.

Positive evidence belongs to ``modules/tool-memory`` because this root suite
does not depend on ``amplifier_core``.  These controls prove a hand-built trace
cannot become an alternate green path.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

RUNNER = Path(__file__).resolve().parents[1] / "evaluations/review-recovery/prior_memory.py"
SPEC = importlib.util.spec_from_file_location("prior_memory_probe", RUNNER)
module = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
sys.modules[SPEC.name] = module
SPEC.loader.exec_module(module)


def snapshot() -> object:
    return module.Snapshot({"MEMORY.md": b"- [m-014] old\n"}, "before", ("fixture",))


def expectation() -> object:
    return module.CaseExpectation(
        (module.ExpectedCall("memory", {"operation": "list"}, True),),
        ("/memory list",),
        final_text="display",
    )


def test_synthetic_trace_never_counts_as_recorded_actual_tool_evidence():
    trace = module.scripted_trace(
        [
            module.Turn("user", "/memory list", snapshot()),
            module.Turn(
                "assistant",
                "display",
                snapshot(),
                (module.scripted_call({"operation": "list"}, output="display"),),
            ),
        ]
    )
    checks = module.grade_trace(trace, expectation())
    print(checks)
    assert not all(checks.values())


def test_unknown_tool_missing_boundary_and_extra_call_are_rejected_without_raising():
    trace = module.scripted_trace(
        [
            module.Turn("user", "/memory list", snapshot()),
            module.Turn(
                "assistant",
                "display",
                snapshot(),
                (
                    module.scripted_call({"operation": "list"}, name="memory"),
                    module.scripted_call({"operation": "forget", "id": "m-014"}, name="shell"),
                ),
            ),
        ]
    )
    checks = module.grade_trace(trace, expectation())
    print(checks)
    assert not all(checks.values())