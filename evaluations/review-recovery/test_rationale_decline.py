"""Subprocess-boundary checks for the bounded native rationale driver."""

from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from types import SimpleNamespace

import pytest


def _driver():
    path = Path(__file__).with_name("rationale_decline.py")
    spec = importlib.util.spec_from_file_location("rationale_decline_test", path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _bindings():
    class Candidate:
        def __init__(self, **value):
            self.__dict__.update(value)
            self.id = ""

    def _state(home):
        return json.loads((home / "state.json").read_text(encoding="utf-8"))

    def _commit(home, message):
        subprocess.run(["git", "-C", str(home), "add", "."], check=True)
        subprocess.run(
            [
                "git", "-C", str(home), "-c", "user.name=Fixture",
                "-c", "user.email=fixture@example.invalid", "commit", "-qm", message,
            ],
            check=True,
        )

    def _write(home, state):
        (home / "state.json").write_text(json.dumps(state), encoding="utf-8")
        (home / "inbox.md").write_text(
            "\n".join(f"- [{row['id']}] {row['text']}" for row in state["pending"]) + "\n",
            encoding="utf-8",
        )
        (home / "declined.md").write_text(
            "\n".join(f"- {row['text']} reason: {row['reason']}" for row in state["declined"]) + "\n",
            encoding="utf-8",
        )

    def init(home, *, timer):
        del timer
        subprocess.run(["git", "init", "-q", str(home)], check=True)
        (home / ".gitignore").write_text("sessions.jsonl\n", encoding="utf-8")
        (home / "MEMORY.md").write_text("", encoding="utf-8")
        _write(home, {"pending": [], "declined": []})
        _commit(home, "fixture")

    def record_session(home, session_id, origin):
        (home / "sessions.jsonl").write_text(
            json.dumps({"session_id": session_id, "origin": origin}) + "\n", encoding="utf-8"
        )

    def session_origins(home):
        row = json.loads((home / "sessions.jsonl").read_text(encoding="utf-8"))
        return {row["session_id"]: row["origin"]}

    def inbox_append(home, candidates):
        state = _state(home)
        result = []
        for index, item in enumerate(candidates, start=1):
            item.id = f"s-{index:03d}"
            state["pending"].append({"id": item.id, "text": item.text})
            result.append(item)
        _write(home, state)
        _commit(home, "pending")
        return result

    def pending(home):
        return [SimpleNamespace(**row) for row in _state(home)["pending"]]

    def declined_records(home):
        return [SimpleNamespace(**row) for row in _state(home)["declined"]]

    def decline(home, ids, reasons):
        state = _state(home)
        selected = [row for row in state["pending"] if row["id"] in ids]
        state["pending"] = [row for row in state["pending"] if row["id"] not in ids]
        state["declined"].extend(
            {"text": row["text"], "reason": reason} for row, reason in zip(selected, reasons, strict=True)
        )
        _write(home, state)
        _commit(home, "decline")

    return {
        "init": init,
        "record_session": record_session,
        "session_origins": session_origins,
        "pending": pending,
        "declined_records": declined_records,
        "inbox_append": inbox_append,
        "candidate": Candidate,
        "decline": decline,
    }


def _call(tool, arguments, output="ok"):
    return {
        "tool": tool,
        "arguments": arguments,
        "result": {"success": True, "output": output},
        "timestamp": "2026-09-13T10:15:45Z",
    }


def _passing_executor(driver, bindings, calls):
    def executor(*, case, user_text, home, resume_session_id):
        calls.append({"case": case, "user": user_text, "home": home, "resume": resume_session_id})
        if resume_session_id is None:
            trace = (_call("memory", {"operation": "review", "action": "list"}),)
            return driver.NativeResult(0, "", "", 0.01, None, f"cli-{case}", "review", trace, (), ())
        reasons = driver.EXPECTED_REASONS[case]
        ids = [f"s-{number:03d}" for number in range(1, len(reasons) + 1)]
        if reasons:
            bindings["decline"](home, ids, reasons)
        trace = tuple(
            _call(
                "memory",
                {"operation": "review", "action": "decline", "id": item_id, "reason": reason},
                f"declined {item_id}",
            )
            for item_id, reason in zip(ids, reasons, strict=True)
        )
        return driver.NativeResult(
            0,
            "",
            "",
            0.01,
            None,
            resume_session_id,
            "done",
            trace,
            tuple(f"declined {item_id}" for item_id in ids),
            ("amplifier", "run", "--resume", resume_session_id, user_text),
        )

    return executor


def test_dry_plan_makes_zero_native_executor_calls(tmp_path, monkeypatch):
    driver = _driver()
    monkeypatch.setattr(
        driver.subprocess,
        "run",
        lambda *args, **kwargs: pytest.fail("dry plan must not start a subprocess"),
    )
    assert driver.main(["--out", str(tmp_path / "plan")]) == 0
    assert json.loads((tmp_path / "plan" / "manifest.json").read_text())["max_actual_cli_turns"] == 8


def test_execute_injected_boundary_records_exact_resumes_and_validates_real_store_state(
    tmp_path, monkeypatch
):
    driver = _driver()
    bindings = _bindings()
    calls = []
    monkeypatch.setenv("PYTEST_CURRENT_TEST", "test")
    assert driver.main(
        ["--out", str(tmp_path / "execute"), "--execute"],
        executor=_passing_executor(driver, bindings, calls),
        bindings=bindings,
    ) == 0
    result = json.loads((tmp_path / "execute" / "result.json").read_text())
    assert result["passed"] is True
    assert result["invocation_count"] == driver.MAX_TURNS == len(calls)
    for index in range(0, len(calls), 2):
        assert calls[index]["resume"] is None
        assert calls[index + 1]["resume"] == f"cli-{calls[index]['case']}"
    assert result["runtime"] == {"mode": "injected-test-bindings"}
    assert (tmp_path / "execute" / "preflight.json").is_file()
    assert all((tmp_path / "execute" / case / "turn-01.json").is_file() for case in driver.CASES)
    assert all((tmp_path / "execute" / case / "turn-02.json").is_file() for case in driver.CASES)


def test_native_preflight_prepares_every_store_before_the_first_prompt(tmp_path):
    driver = _driver()
    bindings = _bindings()
    observed = []

    def executor(**kwargs):
        observed.append(kwargs)
        assert (tmp_path / "out" / "preflight.json").is_file()
        assert all((tmp_path / "out" / case / "store" / ".git").is_dir() for case in driver.CASES)
        return driver.NativeResult(
            1, "", "provider unavailable", 0.0, "exit 1", None, None, (), (), ()
        )

    payload = driver.execute(tmp_path / "out", executor, bindings)
    assert len(observed) == len(driver.CASES)
    assert payload["invocation_count"] == len(driver.CASES)


def test_snapshot_separates_ignored_plumbing_from_git_mutation_oracles(tmp_path):
    driver = _driver()
    bindings = _bindings()
    home = tmp_path / "store"
    home.mkdir()
    bindings["init"](home, timer=False)
    bindings["record_session"](home, "human-session", "human")
    before = driver.store_snapshot(home)
    (home / "sessions.jsonl").write_text(
        (home / "sessions.jsonl").read_text(encoding="utf-8") + "{\"usage\": 1}\n",
        encoding="utf-8",
    )
    plumbing_changed = driver.store_snapshot(home)
    assert driver.same_mutation_state(before, plumbing_changed)
    assert before["plumbing_file_sha256"] != plumbing_changed["plumbing_file_sha256"]

    (home / "MEMORY.md").write_text("saved memory\n", encoding="utf-8")
    changed = driver.store_snapshot(home)
    assert not driver.same_mutation_state(plumbing_changed, changed)
    subprocess.run(["git", "-C", str(home), "add", "MEMORY.md"], check=True)
    staged = driver.store_snapshot(home)
    assert staged["staged_index"]["entries_base64"]
    assert staged["staged_index"]["diff_binary_base64"]


def test_native_executor_uses_documented_argv_resume_and_case_store_environment(monkeypatch, tmp_path):
    driver = _driver()
    seen = []
    stdout = json.dumps(
        {
            "status": "success",
            "session_id": "observed-session",
            "response": "done",
            "usage": {"input_tokens": 8, "output_tokens": 2},
            "execution_trace": [
                {
                    "type": "tool_call",
                    **_call("memory", {"operation": "review", "action": "list"}),
                }
            ],
        }
    )

    def run(argv, **kwargs):
        seen.append((argv, kwargs))
        return subprocess.CompletedProcess(argv, 0, stdout, "stderr")

    monkeypatch.setattr(driver.subprocess, "run", run)
    executor = driver.NativeCliExecutor(provider="terra", model="terra-model", bundle="memory", timeout=7)
    first = executor(case="one", user_text="first", home=tmp_path / "store", resume_session_id=None)
    second = executor(
        case="one", user_text="second", home=tmp_path / "store", resume_session_id=first.session_id
    )
    assert first.error is None and second.session_id == "observed-session"
    assert seen[0][0] == [
        "amplifier", "run", "--output-format", "json-trace", "-p", "terra", "-m", "terra-model",
        "-B", "memory", "first",
    ]
    assert seen[1][0][-3:] == ["--resume", "observed-session", "second"]
    assert seen[0][1]["env"]["AMPLIFIER_MEMORY_HOME"] == str(tmp_path / "store")
    assert seen[0][1]["timeout"] == 7
    assert first.provider_usage == {
        "status": "captured",
        "value": {"input_tokens": 8, "output_tokens": 2},
    }
    assert first.utc_started and first.utc_finished
    assert datetime.fromisoformat(first.utc_started)
    assert datetime.fromisoformat(first.utc_finished)


def test_native_executor_rejects_missing_trace_and_provider_failure_is_not_empty_success(monkeypatch, tmp_path):
    driver = _driver()
    outputs = [
        subprocess.CompletedProcess([], 0, '{"session_id":"s","response":"[]"}', ""),
        subprocess.CompletedProcess([], 1, "[]", "provider failed"),
    ]
    monkeypatch.setattr(driver.subprocess, "run", lambda *args, **kwargs: outputs.pop(0))
    executor = driver.NativeCliExecutor(provider="p", model="m", bundle="b", timeout=1)
    missing_trace = executor(case="case", user_text="one", home=tmp_path, resume_session_id=None)
    provider_failure = executor(case="case", user_text="two", home=tmp_path, resume_session_id=None)
    assert "execution_trace" in (missing_trace.error or "")
    assert provider_failure.error == "exit 1"
    assert provider_failure.session_id is None and provider_failure.receipts == ()


def test_failed_first_launch_spends_an_attempt_and_never_launches_a_replacement_second_turn(
    tmp_path, monkeypatch
):
    driver = _driver()
    bindings = _bindings()
    launches = []

    def failing_executor(**kwargs):
        launches.append(kwargs)
        return driver.NativeResult(None, "", "", 0.0, "OSError: unavailable", None, None, (), (), ())

    monkeypatch.setenv("PYTEST_CURRENT_TEST", "test")
    payload = driver.execute(tmp_path / "out", failing_executor, bindings)
    assert payload["invocation_count"] == len(driver.CASES) == len(launches)
    assert all(len(run["turns"]) == 1 and run["missing_second_turn"] for run in payload["runs"])
    assert payload["passed"] is False


def test_ambiguous_case_write_is_rejected_by_postcondition(tmp_path):
    driver = _driver()
    bindings = _bindings()
    calls = []
    executor = _passing_executor(driver, bindings, calls)

    def mutating_ambiguous(**kwargs):
        result = executor(**kwargs)
        if kwargs["case"] == "ambiguous-reason" and kwargs["resume_session_id"] is not None:
            bindings["decline"](kwargs["home"], ["s-001"], ("it is a product request",))
        return result

    payload = driver.execute(tmp_path / "out", mutating_ambiguous, bindings)
    ambiguous = next(run for run in payload["runs"] if run["case"] == "ambiguous-reason")
    assert ambiguous["passed"] is False
    assert ambiguous["checks"]["expected_pending_and_declines"] is False


def test_read_page_one_is_accepted_but_a_different_returned_resume_is_rejected(tmp_path):
    driver = _driver()
    bindings = _bindings()

    def executor(*, case, user_text, home, resume_session_id):
        if resume_session_id is None:
            trace = (_call("memory", {"operation": "review", "action": "list", "page": 1}),)
            return driver.NativeResult(0, "", "", 0.0, None, "observed", "review", trace, (), ())
        return driver.NativeResult(
            0,
            "",
            "",
            0.0,
            None,
            "wrong-session",
            "done",
            (),
            (),
            ("amplifier", "run", "--resume", resume_session_id, user_text),
        )

    payload = driver.execute(tmp_path / "out", executor, bindings)
    assert all(
        not run["checks"]["resumed_session_returned"] and run["checks"]["first_review_is_read_only"]
        for run in payload["runs"]
    )


def test_execute_under_pytest_needs_an_injected_executor(tmp_path, monkeypatch):
    driver = _driver()
    monkeypatch.setenv("PYTEST_CURRENT_TEST", "test")
    with pytest.raises(RuntimeError, match="without an injected executor"):
        driver.main(["--out", str(tmp_path / "execute"), "--execute"])
