"""Pure checks for the rationale/context evaluation instrument; no provider calls."""

from __future__ import annotations

import json
import re
import shutil
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path

import pytest
import rationale_context as rc


def _relocated_baseline(tmp_path: Path) -> Path:
    """A complete f509 package copied to a path no maintainer would normally use."""
    repo = Path(__file__).resolve().parents[2]
    package_root = tmp_path / "copied-baseline" / "src" / "amplifier_memory"
    shutil.copytree(repo / "src" / "amplifier_memory", package_root)
    source = package_root / "suggest.py"
    source.write_bytes(
        subprocess.check_output(
            ["git", "-C", str(repo), "show", "f509363:src/amplifier_memory/suggest.py"]
        )
    )
    return source


def _bindings():
    def build_prompt(lines, declined):
        return "candidate prompt"

    def compose_request(prompt, turns, *, assistant_context=(), declined=()):
        return json.dumps(
            {
                "prompt": prompt,
                "turns": turns,
                "assistant_context": list(assistant_context),
                "declined": list(declined),
            },
            default=lambda value: value.__dict__,
        )

    def terminal_json(stdout):
        decoder = json.JSONDecoder()
        candidates = list(re.finditer(r"(?m)^\{", stdout))
        if len(candidates) != 1:
            raise ValueError("expected exactly one terminal JSON envelope")
        offset = candidates[0].start()
        payload, end = decoder.raw_decode(stdout[offset:])
        if stdout[offset + end :].strip():
            raise ValueError("trailing output after terminal JSON envelope")
        return payload

    return {
        "build_prompt": build_prompt,
        "compose_request": compose_request,
        "parse_reply": lambda reply: json.loads(reply),
        "verify": lambda quote, turns: quote in turns,
        "json_object_in": terminal_json,
    }


def _candidate_copy(tmp_path: Path, name: str) -> Path:
    """A self-contained checkout whose package root can differ from this test process."""
    repo = Path(__file__).resolve().parents[2]
    root = tmp_path / name
    shutil.copytree(repo / "src" / "amplifier_memory", root / "src" / "amplifier_memory")
    tool = root / "modules" / "tool-memory" / "amplifier_module_tool_memory"
    tool.parent.mkdir(parents=True)
    shutil.copytree(repo / "modules" / "tool-memory" / "amplifier_module_tool_memory", tool)
    skill = root / "skills" / "memory"
    skill.parent.mkdir(parents=True)
    shutil.copytree(repo / "skills" / "memory", skill)
    subprocess.run(["git", "init", "-q", str(root)], check=True)
    subprocess.run(["git", "-C", str(root), "add", "."], check=True)
    subprocess.run(
        [
            "git",
            "-C",
            str(root),
            "-c",
            "user.name=Fixture",
            "-c",
            "user.email=fixture@example.invalid",
            "commit",
            "-qm",
            "candidate",
        ],
        check=True,
    )
    return root


@contextmanager
def _without_candidate_modules():
    """Restore the test interpreter after intentionally proving sys.modules is fail-closed."""
    saved = {name: module for name, module in sys.modules.items() if name.startswith("amplifier_memory")}
    for name in saved:
        del sys.modules[name]
    try:
        yield
    finally:
        for name in list(sys.modules):
            if name.startswith("amplifier_memory"):
                del sys.modules[name]
        sys.modules.update(saved)


def test_candidate_binding_uses_declared_package_root_and_refuses_ambient_other_root(tmp_path):
    first = _candidate_copy(tmp_path, "first")
    second = _candidate_copy(tmp_path, "second")
    baseline = _relocated_baseline(tmp_path)
    source = first / "src" / "amplifier_memory" / "suggest.py"
    source.write_text(
        source.read_text(encoding="utf-8").replace(
            "From these eligible human turns, list only lasting personal working preferences",
            "candidate-first root is bound: list only lasting personal working preferences",
            1,
        ),
        encoding="utf-8",
    )
    with _without_candidate_modules():
        requests = []

        def runner(request, timeout):
            requests.append((request, timeout))
            return rc.RawCall(0, '{"response":"[]"}', "", 0.0, None)

        args = [
            "--out",
            str(tmp_path / "first-run"),
            "--execute",
            "--baseline-source",
            str(baseline),
            "--candidate-source",
            str(first),
        ]
        assert rc.main(args, runner=runner) == 0
        manifest = json.loads((tmp_path / "first-run" / "manifest.json").read_text())
        assert any("candidate-first root is bound" in request for request, _ in requests)
        assert manifest["candidate"]["resolved_runtime"]["src/amplifier_memory/suggest.py"][
            "path"
        ] == str(source.resolve())
        with pytest.raises(RuntimeError, match="escaped declared root"):
            rc.main(
                [
                    "--out",
                    str(tmp_path / "second-run"),
                    "--execute",
                    "--baseline-source",
                    str(baseline),
                    "--candidate-source",
                    str(second),
                ],
                runner=runner,
            )
        assert len(requests) == 36


def test_manifest_is_the_frozen_36_trial_matrix_and_uses_relocated_read_only_baseline(tmp_path):
    baseline = _relocated_baseline(tmp_path)
    plan = rc.manifest(baseline)
    assert len(plan["trials"]) == 36
    assert len({trial["id"] for trial in plan["trials"]}) == 36
    assert set(plan["frozen_equivalent"].values()) == {True}
    assert plan["baseline"]["baseline_sha"] == "f509363"
    assert str(baseline.parent.parent.parent) in plan["baseline"]["source"]
    assert "lanes/aw-publication" not in plan["baseline"]["source"]
    assert plan["policy"]["retries"] == plan["policy"]["fallbacks"] == 0


def test_fixture_groups_have_two_human_turns_and_non_keyword_positive():
    negative = rc.load_fixture("tool-requirement")
    positive = rc.load_fixture("conditional-preference")
    assert len(negative["human_turns"]) >= 2
    assert "product capability request" in negative["assistant_context"][0]["after"]
    assert "incident report" in positive["human_turns"][0]
    assert "global ban" in positive["declined"][0]["reason"]
    assert positive["declined"][0]["quote"] not in positive["human_turns"]


def test_frozen_arm_retains_old_text_packet_but_candidate_arms_are_feature_scoped():
    fixture = rc.load_fixture("conditional-preference")
    frozen = rc.request_for(fixture, "frozen")
    assert "reason" not in frozen

    seen = {}

    def prompt(lines, declined):
        seen["prompt_declined"] = declined
        return "candidate prompt"

    def compose(prompt, turns, *, assistant_context=(), declined=()):
        seen["context"], seen["declined"] = assistant_context, declined
        return json.dumps({"prompt": prompt, "turns": turns})

    bindings = {"build_prompt": prompt, "compose_request": compose}
    rc.request_for(fixture, "rationale-only", bindings)
    assert seen["prompt_declined"] == []
    assert seen["context"] == []
    assert seen["declined"][0]["reason_state"] == "valid"
    rc.request_for(fixture, "context-only", bindings)
    assert seen["context"] == fixture["assistant_context"]
    assert seen["declined"][0]["reason"] is None


def test_no_overwrite_and_no_execution_under_pytest(tmp_path, monkeypatch):
    target = tmp_path / "record.json"
    rc.write_json_new(target, {"ok": True})
    with pytest.raises(FileExistsError, match="overwrite"):
        rc.write_json_new(target, {"ok": False})
    monkeypatch.setenv("PYTEST_CURRENT_TEST", "test")
    with pytest.raises(RuntimeError, match="refusing provider execution"):
        rc.main(["--out", str(tmp_path / "run"), "--execute"])


def test_judge_invocation_records_utc_timestamps_usage_and_timeout_output(monkeypatch):
    completed = subprocess.CompletedProcess(
        [], 0, '{"response":"[]","usage":{"input_tokens":12,"output_tokens":3}}', ""
    )
    monkeypatch.setattr(rc.subprocess, "run", lambda *args, **kwargs: completed)
    observed = rc.invoke_once("request", timeout=1)
    assert observed.provider_usage == {
        "status": "captured",
        "value": {"input_tokens": 12, "output_tokens": 3},
    }
    assert observed.utc_started and observed.utc_finished
    assert datetime.fromisoformat(observed.utc_started)
    assert datetime.fromisoformat(observed.utc_finished)

    timeout = subprocess.TimeoutExpired([], 1, output=b"partial stdout", stderr=b"partial stderr")
    monkeypatch.setattr(rc.subprocess, "run", lambda *args, **kwargs: (_ for _ in ()).throw(timeout))
    interrupted = rc.invoke_once("request", timeout=1)
    assert interrupted.stdout == "partial stdout"
    assert interrupted.stderr == "partial stderr"
    assert interrupted.provider_usage["status"] == "unavailable"


@pytest.mark.parametrize(
    ("stdout", "status"),
    [
        ('{"status":"success","response":"[]"}', "parsed"),
        (
            (
                "\x1b[32mBundle 'memory' prepared successfully\x1b[0m\n"
                '{"status":"success","response":"[]"}'
            ),
            "parsed",
        ),
        ("Bundle prepared successfully\nnot JSON", "parse-failure"),
        (
            (
                '{"status":"success","response":"[]"}\n'
                '{"status":"success","response":"[]"}'
            ),
            "parse-failure",
        ),
    ],
)
def test_structural_score_accepts_one_terminal_envelope_only(stdout, status):
    result = rc.structural_score(
        rc.RawCall(0, stdout, "diagnostic stderr", 0.1, None),
        {"human_turns": [], "declined": []},
        _bindings(),
    )
    assert result["status"] == status


def test_execute_uses_injected_runner_with_bound_inputs_and_idempotent_resume(tmp_path, monkeypatch):
    baseline = _relocated_baseline(tmp_path)
    repo = Path(__file__).resolve().parents[2]
    calls = []

    def runner(request, timeout):
        calls.append((request, timeout))
        return rc.RawCall(0, '{"status":"success","response":"[]"}', "stderr", 0.01, None)

    monkeypatch.setenv("PYTEST_CURRENT_TEST", "test")
    out = tmp_path / "out"
    args = [
        "--out",
        str(out),
        "--execute",
        "--baseline-source",
        str(baseline),
        "--candidate-source",
        str(repo),
        "--concurrency",
        "4",
    ]
    assert rc.main(args, runner=runner, bindings=_bindings()) == 0
    assert len(calls) == 36
    recorded = json.loads((out / "manifest.json").read_text())
    assert recorded["candidate"]["commit"]
    assert len(recorded["requests_sha256"]) == 36
    assert rc.main([*args, "--resume"], runner=runner, bindings=_bindings()) == 0
    assert len(calls) == 36


def test_resume_refuses_candidate_or_judge_identity_drift(tmp_path, monkeypatch):
    baseline = _relocated_baseline(tmp_path)
    repo = Path(__file__).resolve().parents[2]
    monkeypatch.setenv("PYTEST_CURRENT_TEST", "test")
    out = tmp_path / "out"
    args = [
        "--out", str(out), "--execute", "--baseline-source", str(baseline),
        "--candidate-source", str(repo),
    ]
    runner = lambda request, timeout: rc.RawCall(0, '{"response":"[]"}', "", 0.0, None)
    assert rc.main(args, runner=runner, bindings=_bindings()) == 0
    monkeypatch.setenv("RATIONALE_CONTEXT_JUDGE_MODEL", "changed")
    with pytest.raises(RuntimeError, match="resume refused"):
        rc.main([*args, "--resume"], runner=runner, bindings=_bindings())


def test_resume_refuses_candidate_file_drift(tmp_path, monkeypatch):
    baseline = _relocated_baseline(tmp_path)
    candidate = _candidate_copy(tmp_path, "candidate")
    monkeypatch.setenv("PYTEST_CURRENT_TEST", "test")
    out = tmp_path / "out"
    args = [
        "--out",
        str(out),
        "--execute",
        "--baseline-source",
        str(baseline),
        "--candidate-source",
        str(candidate),
    ]
    runner = lambda request, timeout: rc.RawCall(0, '{"response":"[]"}', "", 0.0, None)
    assert rc.main(args, runner=runner, bindings=_bindings()) == 0
    with (candidate / "skills" / "memory" / "SKILL.md").open("a", encoding="utf-8") as handle:
        handle.write("\nchanged candidate identity\n")
    with pytest.raises(RuntimeError, match="resume refused"):
        rc.main([*args, "--resume"], runner=runner, bindings=_bindings())


def test_atomic_claim_allows_one_concurrent_worker_and_inflight_trial_is_spent(tmp_path):
    claim = tmp_path / "inflight" / "race.json"
    with ThreadPoolExecutor(max_workers=4) as pool:
        claims = list(pool.map(lambda _: rc._claim_trial(claim, {"id": "trial"}, "manifest"), range(4)))
    assert claims.count(True) == 1

    baseline = _relocated_baseline(tmp_path)
    fixtures = {scenario: rc.load_fixture(scenario) for scenario in rc.SCENARIOS}
    bindings = _bindings()
    plan = rc.manifest(
        baseline,
        candidate={"commit": "candidate"},
        config_identity={},
        request_sha256=rc.request_digests(bindings, fixtures),
    )
    trial = plan["trials"][0]
    out = tmp_path / "out"
    marker = out / "inflight" / f"{trial['id']}.json"
    rc.write_json_new(
        marker, {"id": trial["id"], "manifest_sha256": rc.json_digest(plan), "owner_pid": 999999}
    )
    record = rc._run_trial(
        trial,
        out=out,
        plan=plan,
        fixtures=fixtures,
        bindings=bindings,
        runner=lambda request, timeout: pytest.fail("a pre-existing inflight claim must not run"),
        timeout=1,
    )
    assert record["structural"]["status"] == "provider-failure"
    assert "attempt spent" in record["call"]["error"]


def test_summary_is_idempotent_but_refuses_a_different_final_report(tmp_path):
    target = tmp_path / "summary.json"
    rc._write_summary(target, {"attempted": 1})
    rc._write_summary(target, {"attempted": 1})
    with pytest.raises(RuntimeError, match="existing summary differs"):
        rc._write_summary(target, {"attempted": 2})
