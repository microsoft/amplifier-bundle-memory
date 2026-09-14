"""No-model proof for bounded runner plumbing and real tool/library branches."""

from __future__ import annotations

import asyncio
import copy
import importlib
import importlib.util
import json
import os
import subprocess
import sys
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from types import ModuleType, SimpleNamespace

import pytest

import amplifier_memory
from amplifier_memory import inbox


def _load(name: str):
    path = Path(__file__).with_name(f"{name}.py")
    spec = importlib.util.spec_from_file_location(f"{name}_test", path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


class Context:
    def __init__(self, messages):
        self.messages = messages

    async def get_messages(self):
        return self.messages


class Coordinator:
    def __init__(self, messages, session_id="edge-session"):
        self.session_id = session_id
        self.parent_id = None
        self.mount_points = {"context": Context(messages)}


def _user(text: str) -> dict[str, str]:
    return {"role": "user", "content": text}


def _seed(home: Path, count: int = 1):
    amplifier_memory.init(home, timer=False)
    amplifier_memory.record_session(home, "fixture-human", "human")
    return inbox.append(
        home,
        [
            inbox.Candidate(
                text=f"Use native edge fixture {number}.",
                quote=f"For future reference, use native edge fixture {number}.",
                session="fixture-human",
                date="2026-09-13",
            )
            for number in range(1, count + 1)
        ],
    )


def _head(home: Path) -> str:
    return subprocess.check_output(["git", "-C", str(home), "rev-parse", "HEAD"], text=True).strip()


def _real_tool(home: Path, messages):
    module_root = Path(__file__).resolve().parents[2] / "modules" / "tool-memory"
    if str(module_root) not in sys.path:
        sys.path.insert(0, str(module_root))
    module = _tool_module()
    return module, module.MemoryTool(Coordinator(messages), {"home": str(home)})


def _tool_module():
    """Load the real adapter; root evaluator tests only stub its core result type."""

    if "amplifier_core" not in sys.modules:
        core = ModuleType("amplifier_core")

        @dataclass
        class ToolResult:
            success: bool
            output: str
            error: dict | None = None

        core.ToolResult = ToolResult
        sys.modules["amplifier_core"] = core
    return importlib.import_module("amplifier_module_tool_memory")


def _install(monkeypatch, faults, home: Path, item_id: str, ordinal: int, kind: str, telemetry: Path):
    module_root = Path(__file__).resolve().parents[2] / "modules" / "tool-memory"
    if str(module_root) not in sys.path:
        sys.path.insert(0, str(module_root))
    module = _tool_module()
    original_execute = module.MemoryTool.execute
    original_committed = inbox._committed
    monkeypatch.setattr(module.MemoryTool, "execute", original_execute)
    monkeypatch.setattr(inbox, "_committed", original_committed)
    status = faults.install(
        module, inbox, faults.FaultSpec(home.resolve(), item_id, ordinal, kind, telemetry)
    )
    return module, status


def test_plan_prepare_and_help_are_model_free(tmp_path, capsys):
    edge = _load("rationale_edge_cases")
    assert edge.main(["plan"]) == 0
    assert edge.main(["prepare", "--out", str(tmp_path / "prepared"), "--candidate-source", str(Path.cwd())]) == 0
    assert "native_result" in capsys.readouterr().out
    assert edge.plan()["max_actual_cli_turns"] == 14
    assert edge.plan()["suite"] == edge.DEFAULT_SUITE
    assert len(edge.SCENARIOS) == 7
    prepared = json.loads((tmp_path / "prepared" / "preparation.json").read_text())
    assert prepared["loader_control"]["same_execute_object"] is True
    assert prepared["loader_control"]["effective_object_is_wrapper"] is True
    assert prepared["preparation_summary"]["status"] == "NOT YET"


def test_remaining_two_suite_is_fixed_ordered_and_uses_only_four_injected_attempts(tmp_path, monkeypatch):
    edge = _load("rationale_edge_cases")
    out = tmp_path / ".release-verification" / "remaining-two"
    expected = ["invalid-utf8-reason", "committed-decline-readback-failure"]
    assert [item["name"] for item in edge.plan("remaining-two")["scenarios"]] == expected
    assert edge.plan("remaining-two")["max_actual_cli_turns"] == 4
    edge.prepare(out, Path.cwd(), suite="remaining-two")
    prepared = json.loads((out / "preparation.json").read_text())
    assert list(prepared["fixtures"]) == expected
    calls = []

    def factory(base, scenario, _deadline, _provider, _model, _bundle):
        def execute(*, case, user_text, home, resume_session_id):
            calls.append((case, user_text, resume_session_id))
            return base.NativeResult(
                0, "", "", 0.0, None, resume_session_id or f"session-{case}", "review", (), (),
                ("injected",), base.utc_timestamp(), base.utc_timestamp(),
            )
        return execute

    monkeypatch.setenv("PYTEST_CURRENT_TEST", "remaining two test")
    payload = edge.run(
        out, candidate_source=Path.cwd(), provider="p", model="m", bundle="b",
        deadline_utc="2099-01-01T00:00:00Z", executor_factory=factory, suite="remaining-two",
    )
    assert payload["native"] is False
    assert payload["attempt_count"] == payload["actual_attempt_count"] == 4 == len(calls)
    assert payload["attempt_limit"] == payload["max_actual_cli_turns"] == 4
    assert payload["unused_slots"] == 0 and payload["complete"] is True
    assert [call[0] for call in calls] == [expected[0], expected[0], expected[1], expected[1]]
    assert all(case in expected for case, _text, _resume in calls)


def test_blocked_first_attempt_records_unused_slots_without_padding_calls(tmp_path, monkeypatch):
    edge = _load("rationale_edge_cases")
    out = tmp_path / ".release-verification" / "blocked-first"
    edge.prepare(out, Path.cwd(), suite="remaining-two")
    calls = []

    def factory(base, _scenario, _deadline, _provider, _model, _bundle):
        def execute(*, case, user_text, home, resume_session_id):
            calls.append((case, user_text, resume_session_id))
            return base.NativeResult(
                0, "", "", 0.0, "initial review refusal", None, None, (), (), ("injected",),
                base.utc_timestamp(), base.utc_timestamp(),
            )
        return execute

    monkeypatch.setenv("PYTEST_CURRENT_TEST", "blocked first test")
    payload = edge.run(
        out, candidate_source=Path.cwd(), provider="p", model="m", bundle="b",
        deadline_utc="2099-01-01T00:00:00Z", executor_factory=factory, suite="remaining-two",
    )
    assert len(calls) == payload["attempt_count"] == payload["actual_attempt_count"] == 1
    assert payload["unused_slots"] == 3 and payload["complete"] is False
    assert len(payload["runs"][0]["turns"]) == 1
    assert payload["runs"][1]["status"] == "BLOCKED"


def test_run_rejects_incompatible_prepared_suite_and_unsafe_native_cwd(tmp_path):
    edge = _load("rationale_edge_cases")
    out = tmp_path / ".release-verification" / "prepared"
    edge.prepare(out, Path.cwd(), suite="remaining-two")
    with pytest.raises(ValueError, match="prepared suite"):
        edge.run(
            out, candidate_source=Path.cwd(), provider="p", model="m", bundle="b",
            deadline_utc="2099-01-01T00:00:00Z", executor_factory=lambda *_args: None,
        )
    with pytest.raises(ValueError, match="explicit --native-cwd"):
        edge.run(
            out, candidate_source=Path.cwd(), provider="p", model="m", bundle="b",
            deadline_utc="2099-01-01T00:00:00Z", suite="remaining-two",
        )
    with pytest.raises(ValueError, match="must be absolute"):
        edge.run(
            out, candidate_source=Path.cwd(), provider="p", model="m", bundle="b",
            deadline_utc="2099-01-01T00:00:00Z", suite="remaining-two", native_cwd=Path("."),
        )
    with pytest.raises(ValueError, match="must not be the candidate source tree"):
        edge.run(
            out, candidate_source=Path.cwd(), provider="p", model="m", bundle="b",
            deadline_utc="2099-01-01T00:00:00Z", suite="remaining-two", native_cwd=Path.cwd(),
        )


def test_edge_executor_uses_and_restores_explicit_neutral_cwd(monkeypatch, tmp_path):
    edge = _load("rationale_edge_cases")
    base = edge._base()
    native_cwd = tmp_path / "neutral-user-workdir"
    native_cwd.mkdir()
    home = tmp_path / ".release-verification" / "store"
    home.mkdir(parents=True)
    observed = []

    def fake_run(argv, **kwargs):
        observed.append({"argv": argv, "cwd": Path.cwd(), "env": kwargs["env"], "timeout": kwargs["timeout"]})
        return SimpleNamespace(
            returncode=0,
            stdout=json.dumps({"session_id": "observed-session", "response": "review", "execution_trace": []}),
            stderr="",
        )

    monkeypatch.delenv("GIT_CEILING_DIRECTORIES", raising=False)
    monkeypatch.setattr(base.subprocess, "run", fake_run)
    executor = edge.EdgeExecutor(
        base, edge.SCENARIOS[1], datetime.now(UTC) + timedelta(hours=1), "p", "m", "b", native_cwd
    )
    parent_cwd = Path.cwd()
    first = executor(case="invalid-utf8-reason", user_text="/memory review", home=home, resume_session_id=None)
    second = executor(
        case="invalid-utf8-reason", user_text="Decline the suggestion.", home=home,
        resume_session_id=first.session_id,
    )
    assert first.error is None and second.error is None
    assert Path.cwd() == parent_cwd
    assert [call["cwd"] for call in observed] == [native_cwd, native_cwd]
    assert all(call["env"]["GIT_CEILING_DIRECTORIES"] == str(native_cwd) for call in observed)
    assert all(call["timeout"] == edge.DEFAULT_TIMEOUT for call in observed)
    assert observed[1]["argv"][observed[1]["argv"].index("--resume") + 1] == "observed-session"


def test_edge_executor_restores_cwd_after_native_subprocess_error(monkeypatch, tmp_path):
    edge = _load("rationale_edge_cases")
    base = edge._base()
    native_cwd = tmp_path / "neutral-user-workdir"
    native_cwd.mkdir()
    home = tmp_path / ".release-verification" / "store"
    home.mkdir(parents=True)
    monkeypatch.setattr(base.subprocess, "run", lambda *_args, **_kwargs: (_ for _ in ()).throw(OSError("boom")))
    executor = edge.EdgeExecutor(
        base, edge.SCENARIOS[1], datetime.now(UTC) + timedelta(hours=1), "p", "m", "b", native_cwd
    )
    parent_cwd = Path.cwd()
    result = executor(case="invalid-utf8-reason", user_text="/memory review", home=home, resume_session_id=None)
    assert "OSError: boom" in (result.error or "")
    assert Path.cwd() == parent_cwd


def test_import_time_shim_is_inert_without_the_explicit_valid_fault_spec(tmp_path):
    shim = Path(__file__).with_name("fault_shim")
    env = os.environ.copy()
    env.pop("NATIVE_RATIONALE_SYNTHETIC", None)
    env.pop("NATIVE_RATIONALE_FAULT_SPEC", None)
    env["PYTHONPATH"] = os.pathsep.join([str(shim), str(Path(__file__).parent)])
    completed = subprocess.run(
        [
            sys.executable,
            "-c",
            "import sitecustomize; assert sitecustomize.SPEC is None and sitecustomize.STATUS is None",
        ],
        capture_output=True,
        text=True,
        check=False,
        env=env,
    )
    assert completed.returncode == 0, completed.stderr


def test_runner_prepares_then_counts_exact_fixed_attempts_but_non_native_cannot_pass(tmp_path, monkeypatch):
    edge = _load("rationale_edge_cases")
    out = tmp_path / ".release-verification" / "edge"
    edge.prepare(out, Path.cwd())
    calls = []

    def factory(base, scenario, _deadline, _provider, _model, _bundle):
        def execute(*, case, user_text, home, resume_session_id):
            calls.append((case, user_text, resume_session_id))
            trace = (
                {
                    "tool": "memory",
                    "arguments": {"operation": "review", "action": "list"},
                    "result": {"success": True, "output": "review"},
                    "timestamp": "2026-09-13T00:00:00Z",
                },
            )
            return base.NativeResult(
                0, "", "", 0.0, None, resume_session_id or f"session-{case}",
                "review", trace, (), ("injected",), base.utc_timestamp(), base.utc_timestamp(),
            )
        return execute

    monkeypatch.setenv("PYTEST_CURRENT_TEST", "edge test")
    payload = edge.run(
        out, candidate_source=Path.cwd(), provider="p", model="m", bundle="b",
        deadline_utc="2099-01-01T00:00:00Z", executor_factory=factory,
    )
    assert payload["native"] is False
    assert payload["attempt_count"] == edge.MAX_TURNS == len(calls)
    assert all(calls[index][2] is None and calls[index + 1][2] == f"session-{calls[index][0]}" for index in range(0, 14, 2))
    assert edge.check(out, Path.cwd(), [])["status"] == "BLOCKED"


def test_real_noop_wrapper_preserves_arguments_and_receipt(monkeypatch, tmp_path):
    faults = _load("rationale_faults")
    edge = _load("rationale_edge_cases")
    home = tmp_path / ".release-verification" / "noop" / "store"
    item = _seed(home)[0]
    before = edge._snapshot(edge._base(), home)
    module, status = _install(monkeypatch, faults, home, item.id, 1, "noop", tmp_path / "noop.jsonl")
    _, tool = _real_tool(home, [_user("Decline the suggestion.")])
    original = {"operation": "review", "action": "decline", "id": item.id}
    result = asyncio.run(tool.execute(original))
    assert result.success is True
    assert result.output == module.ANNOUNCE_DECLINE.format(id=item.id)
    assert original == {"operation": "review", "action": "decline", "id": item.id}
    after = edge._snapshot(edge._base(), home)
    assert before["head"] != after["head"]
    assert edge._decline_transition(edge._base(), before, after, home)
    tampered = copy.deepcopy(after)
    tampered["staged_index"] = before["staged_index"]
    assert not edge._decline_transition(edge._base(), before, tampered, home)
    assert not inbox.pending(home)
    telemetry = [json.loads(line) for line in (tmp_path / "noop.jsonl").read_text().splitlines()]
    assert telemetry[-1]["original_args"] == telemetry[-1]["forwarded_args"] == original
    assert "reason" not in telemetry[-1]["original_args"]
    assert telemetry[-1]["injected_reason_utf8_bytes"] == 0
    assert status()["activation_count"] == 1


def test_fault_ordinal_counts_all_declines_and_rejects_wrong_or_extra_calls(tmp_path):
    faults = _load("rationale_faults")
    home = tmp_path / ".release-verification" / "ordinal" / "store"
    home.mkdir(parents=True)

    class Tool:
        def home(self):
            return home

        async def execute(self, value):
            return value

    spec = faults.FaultSpec(home.resolve(), "s-002", 2, "unverified", tmp_path / "ordinal.jsonl")
    status = faults.install(
        SimpleNamespace(MemoryTool=Tool, __file__=__file__),
        SimpleNamespace(__file__=__file__),
        spec,
    )
    asyncio.run(Tool().execute({"operation": "review", "action": "decline", "id": "s-002"}))
    with pytest.raises(RuntimeError, match="wrong stable id"):
        asyncio.run(Tool().execute({"operation": "review", "action": "decline", "id": "s-001"}))
    assert status()["all_declines"] == 2
    assert status()["wrong_id_at_ordinal"] is True

    class ExtraTool:
        def home(self):
            return home

        async def execute(self, value):
            return value

    extra = faults.install(
        SimpleNamespace(MemoryTool=ExtraTool, __file__=__file__),
        SimpleNamespace(__file__=__file__),
        faults.FaultSpec(home.resolve(), "s-001", 1, "noop", tmp_path / "extra.jsonl"),
    )
    asyncio.run(ExtraTool().execute({"operation": "review", "action": "decline", "id": "s-001"}))
    asyncio.run(ExtraTool().execute({"operation": "review", "action": "decline", "id": "s-002"}))
    assert extra()["activation_count"] == 1 and extra()["duplicate_or_unused"] is True


@pytest.mark.parametrize("kind", ["invalid-utf8", "overlong", "unverified"])
def test_real_fault_rejections_happen_before_every_mutation(monkeypatch, tmp_path, kind):
    faults = _load("rationale_faults")
    edge = _load("rationale_edge_cases")
    home = tmp_path / ".release-verification" / kind / "store"
    item = _seed(home)[0]
    before = edge._snapshot(edge._base(), home)
    _, status = _install(monkeypatch, faults, home, item.id, 1, kind, tmp_path / f"{kind}.jsonl")
    _, tool = _real_tool(home, [_user("Decline the suggestion.")])
    result = asyncio.run(tool.execute({"operation": "review", "action": "decline", "id": item.id}))
    assert result.success is False
    after = edge._snapshot(edge._base(), home)
    assert after == before
    assert edge._no_write_transition(edge._base(), before, after)
    plumbing_only = copy.deepcopy(after)
    plumbing_only["plumbing_file_sha256"]["usage.jsonl"] = "changed"
    assert edge._no_write_transition(edge._base(), before, plumbing_only)
    altered_data = copy.deepcopy(after)
    altered_data["tracked_file_sha256"]["inbox.md"] = "changed"
    assert not edge._no_write_transition(edge._base(), before, altered_data)
    assert status()["activation_count"] == 1
    event = json.loads((tmp_path / f"{kind}.jsonl").read_text().splitlines()[-1])
    assert event["original_args"].get("reason") is None
    assert event["forwarded_args"]["reason"] != event["original_args"].get("reason")
    assert event["injected_reason_utf8_bytes"] == (None if kind == "invalid-utf8" else 2002 if kind == "overlong" else len(event["forwarded_args"]["reason"].encode()))
    assert event["injected_reason_absent_from_human_provenance"] is (kind == "unverified")


def test_real_partial_and_post_commit_readback_branches(monkeypatch, tmp_path):
    faults = _load("rationale_faults")
    edge = _load("rationale_edge_cases")

    partial_home = tmp_path / ".release-verification" / "partial" / "store"
    first, second = _seed(partial_home, 2)
    original_execute = _tool_module().MemoryTool.execute
    module, status = _install(monkeypatch, faults, partial_home, second.id, 2, "unverified", tmp_path / "partial.jsonl")
    _, tool = _real_tool(partial_home, [_user("Decline both suggestions.")])
    first_result = asyncio.run(tool.execute({"operation": "review", "action": "decline", "id": first.id}))
    second_result = asyncio.run(tool.execute({"operation": "review", "action": "decline", "id": second.id}))
    assert first_result.success is True and first_result.output == module.ANNOUNCE_DECLINE.format(id=first.id)
    assert second_result.success is False
    assert [entry.id for entry in inbox.pending(partial_home)] == [second.id]
    assert len(inbox.declined_records(partial_home)) == 1
    assert status()["all_declines"] == 2 and status()["activation_count"] == 1
    monkeypatch.setattr(module.MemoryTool, "execute", original_execute)

    readback_home = tmp_path / ".release-verification" / "readback" / "store"
    item = _seed(readback_home)[0]
    before = edge._snapshot(edge._base(), readback_home)
    _, readback_status = _install(monkeypatch, faults, readback_home, item.id, 1, "readback", tmp_path / "readback.jsonl")
    assert inbox._committed(readback_home, "declined.md") is not None
    assert readback_status()["readback_count"] == 0
    _, readback_tool = _real_tool(readback_home, [_user("Decline the suggestion.")])
    result = asyncio.run(readback_tool.execute({"operation": "review", "action": "decline", "id": item.id}))
    after = edge._snapshot(edge._base(), readback_home)
    assert result.success is False and result.output == "commit succeeded but decline readback is unverified"
    actual_readback_call = {"result": {"success": result.success, "output": result.output}}
    assert edge._exact_final_fence(f"```\n{result.output}\n```", [actual_readback_call])
    assert not edge._exact_final_fence(result.output, [actual_readback_call])
    assert before["head"] != after["head"] and not inbox.pending(readback_home)
    events = [json.loads(line) for line in (tmp_path / "readback.jsonl").read_text().splitlines()]
    landed = next(event for event in events if event["event"] == "committed-decline-readback")
    assert landed["commit_count"] == "1" and landed["after"]["stable_id_in_inbox"] is False
    assert landed["commit_parent"] == before["head"]
    assert landed["changed_paths"] == ["declined.md", "inbox.md"]
    assert " reason:" not in landed["committed_declined"]
    assert readback_status()["readback_count"] == 1


def _shaped_native_run(edge):
    return {
        "native": True,
        "attempt_count": edge.MAX_TURNS,
        "actual_attempt_count": edge.MAX_TURNS,
        "attempt_limit": edge.MAX_TURNS,
        "max_actual_cli_turns": edge.MAX_TURNS,
        "unused_slots": 0,
        "complete": True,
        "native_cwd": "/tmp/neutral-user-workdir",
        "runs": [
            {
                "case": edge.asdict(scenario),
                "status": "RECORDED",
                "turns": [{}, {}],
            }
            for scenario in edge.SCENARIOS
        ],
    }


def test_first_review_error_or_missing_shim_stops_even_with_session_id(tmp_path):
    edge = _load("rationale_edge_cases")
    result = SimpleNamespace(error="provider failed", session_id="observed", response=None)
    telemetry = tmp_path / "telemetry.jsonl"
    assert edge._first_review_failure(result, telemetry, native=True) == "provider failed"
    result.error = None
    result.response = "actual review page"
    assert edge._first_review_failure(result, telemetry, native=True) == "effective native shim evidence is missing"
    telemetry.write_text(json.dumps({
        "event": "shim-status",
        "effective_object_is_wrapper": True,
        "fingerprints": {"effective_wrapper": True},
    }) + "\n")
    assert edge._first_review_failure(result, telemetry, native=True) is None


@pytest.mark.parametrize(
    "native,expected",
    [(True, "PASS"), (False, "BLOCKED"), (None, "FAIL"), ("injected", "FAIL"), (1, "FAIL")],
)
def test_checker_serialized_shape_and_strict_native_flag(tmp_path, monkeypatch, native, expected):
    """Unit-level shape plumbing only: no CLI or model response is produced."""
    edge = _load("rationale_edge_cases")
    out = tmp_path / ".release-verification" / "serialized-shape"
    edge.prepare(out, Path.cwd())
    payload = _shaped_native_run(edge)
    payload["native"] = native
    edge._write(out / "run.json", payload)
    monkeypatch.setattr(edge, "_loader_is_effective", lambda _preparation: True)
    monkeypatch.setattr(
        edge,
        "_case_check",
        lambda _base, _bindings, item, _mappings: {"case": item["case"]["name"], "status": "PASS", "checks": {}},
    )
    assert edge.check(out, Path.cwd(), [])["status"] == expected


@pytest.mark.parametrize(
    "mutate",
    [
        lambda payload: payload["runs"].pop(),
        lambda payload: payload["runs"].append(copy.deepcopy(payload["runs"][0])),
        lambda payload: payload["runs"].reverse(),
        lambda payload: payload.update(actual_attempt_count=13),
        lambda payload: payload.update(attempt_limit=13),
        lambda payload: payload.update(complete=False),
        lambda payload: payload.update(unused_slots=1),
        lambda payload: payload["runs"][0].update(turns=[{}]),
    ],
    ids=[
        "subset", "extra", "reordered", "wrong-actual-count", "wrong-limit",
        "incomplete", "unused-slots", "missing-attempt",
    ],
)
def test_checker_rejects_every_altered_frozen_measurement_shape(tmp_path, monkeypatch, mutate):
    edge = _load("rationale_edge_cases")
    out = tmp_path / ".release-verification" / "shape"
    edge.prepare(out, Path.cwd())
    payload = _shaped_native_run(edge)
    mutate(payload)
    edge._write(out / "run.json", payload)
    monkeypatch.setattr(edge, "_loader_is_effective", lambda _preparation: True)
    monkeypatch.setattr(
        edge,
        "_case_check",
        lambda _base, _bindings, item, _mappings: {"case": item["case"]["name"], "status": "PASS", "checks": {}},
    )
    checked = edge.check(out, Path.cwd(), [])
    assert checked["status"] == "FAIL"
    assert "frozen selected-suite" in checked["reason"]


def test_target_fault_oracle_rejects_missing_swapped_or_rewritten_telemetry():
    edge = _load("rationale_edge_cases")
    scenario = edge.asdict(edge.SCENARIOS[1])
    calls = [
        {
            "arguments": {"operation": "review", "action": "decline", "id": "s-001"},
            "result": {"success": False, "output": "refused: decline reason is not valid UTF-8"},
        }
    ]
    original = calls[0]["arguments"]
    event = {
        "event": "tool-result",
        "activation": True,
        "all_decline_ordinal": 1,
        "stable_id": "s-001",
        "kind": "invalid-utf8",
        "original_args": original,
        "forwarded_args": {**original, "reason": "\ud800"},
        "injected_reason": "\ud800",
        "injected_reason_utf8_bytes": None,
        "injected_reason_absent_from_human_provenance": False,
    }
    status = {
        "all_declines": 1,
        "activation_count": 1,
        "matched": True,
        "wrong_id_at_ordinal": False,
        "duplicate_or_unused": False,
    }
    assert edge._telemetry_check(scenario, calls, [event], status)
    for key, value in (
        ("activation", False),
        ("stable_id", "s-002"),
        ("original_args", event["forwarded_args"]),
    ):
        mutated = copy.deepcopy(event)
        mutated[key] = value
        assert not edge._telemetry_check(scenario, calls, [mutated], status)