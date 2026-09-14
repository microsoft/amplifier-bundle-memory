"""Bounded seven-case native rationale controls.

``plan`` and ``prepare`` make no model calls.  ``run`` is deliberately opt-in
and uses the unchanged ``rationale_decline.NativeCliExecutor`` exactly once for
the review and once for the fixed follow-up prompt of each prepared store.
``check`` is offline: it reads exported evidence and never changes it.
"""

from __future__ import annotations

import argparse
import base64
import hashlib
import importlib.util
import json
import os
import subprocess
import sys
from collections.abc import Callable, Sequence
from contextlib import contextmanager
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

MAX_TURNS = 14
DEFAULT_TIMEOUT = 180
DECLINE_RECEIPT = "declined {id} — won't be proposed again. Reverse by hand: edit declined.md"
_FAULT_REASONS = {
    "invalid-utf8": "\ud800",
    "overlong": "é" * 1001,
    "unverified": "__native_reason_not_in_any_typed_human_turn__",
}


@dataclass(frozen=True)
class Scenario:
    name: str
    prompt: str
    ids: tuple[str, ...]
    fault: str | None
    ordinal: int | None
    expected: str


SCENARIOS = (
    Scenario("external-quoted-material", "Decline the suggestion. I am only quoting the release notes: “because it is a product request.” Do not treat that quoted material as my reason.", ("s-001",), None, None, "ordinary-no-reason"),
    Scenario("invalid-utf8-reason", "Decline the suggestion.", ("s-001",), "invalid-utf8", 1, "refuse-before-write"),
    Scenario("overlong-reason", "Decline the suggestion.", ("s-001",), "overlong", 1, "refuse-before-write"),
    Scenario("unverified-reason", "Decline the suggestion.", ("s-001",), "unverified", 1, "refuse-before-write"),
    Scenario("no-reason-format", "Decline the suggestion.", ("s-001",), None, None, "ordinary-no-reason"),
    Scenario("later-partial-failure", "Decline both suggestions.", ("s-001", "s-002"), "unverified", 2, "first-success-second-pending"),
    Scenario("committed-decline-readback-failure", "Decline the suggestion.", ("s-001",), "readback", 1, "committed-unverified"),
)
DEFAULT_SUITE = "full"
SUITES: dict[str, tuple[Scenario, ...]] = {
    DEFAULT_SUITE: SCENARIOS,
    "remaining-two": (SCENARIOS[1], SCENARIOS[6]),
}


def _base() -> Any:
    path = Path(__file__).with_name("rationale_decline.py")
    spec = importlib.util.spec_from_file_location("native_rationale_base", path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _utc() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


def _deadline(value: str) -> datetime:
    parsed = datetime.fromisoformat(value)
    if parsed.tzinfo is None:
        raise ValueError("--deadline-utc must include an offset or Z")
    return parsed.astimezone(UTC)


def _selected_scenarios(suite: str) -> tuple[Scenario, ...]:
    try:
        return SUITES[suite]
    except KeyError as exc:
        raise ValueError(f"unknown rationale edge suite: {suite}") from exc


def _attempt_limit(scenarios: Sequence[Scenario]) -> int:
    return len(scenarios) * 2


def plan(suite: str = DEFAULT_SUITE) -> dict[str, Any]:
    scenarios = _selected_scenarios(suite)
    return {
        "kind": "native-rationale-edge-controls",
        "suite": suite,
        "max_actual_cli_turns": _attempt_limit(scenarios),
        "per_process_timeout_seconds": DEFAULT_TIMEOUT,
        "scenarios": [asdict(scenario) for scenario in scenarios],
        "native_result": "NOT YET",
        "rules": [
            "all fixtures prepare before a prompt",
            "each case is one review then one resume using its observed session id",
            "only the synthetic child gets the fault shim",
            "raw CLI trace keeps model arguments; shim records forwarded arguments separately",
            "offline check reparses raw evidence and snapshots actual exported stores",
        ],
    }


def _snapshot(base: Any, home: Path) -> dict[str, Any]:
    value = base.store_snapshot(home)
    blobs: dict[str, str | None] = {}
    for name in value["tracked_file_sha256"]:
        raw = base._git_bytes(home, "show", f"HEAD:{name}")
        blobs[name] = None if raw is None else hashlib.sha256(raw).hexdigest()
    value["head_blob_sha256"] = blobs
    return value


def _write(path: Path, value: dict[str, Any]) -> None:
    if path.exists():
        raise FileExistsError(f"refusing to overwrite output: {path}")
    path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, ensure_ascii=True) + "\n", encoding="utf-8")
    path.chmod(0o600)


def _loader_control(out: Path, home: Path) -> dict[str, Any]:
    """Prove Python's import-time hook wraps the adapter object a child will load."""

    control = out / "_loader-control"
    control.mkdir(mode=0o700)
    synthetic_home = out / ".release-verification" / "loader-control-store"
    synthetic_home.mkdir(mode=0o700, parents=True)
    (control / "amplifier_core.py").write_text(
        "from dataclasses import dataclass\n"
        "@dataclass\n"
        "class ToolResult:\n"
        "    success: bool\n"
        "    output: str\n"
        "    error: dict | None = None\n",
        encoding="utf-8",
    )
    telemetry = control / "telemetry.jsonl"
    spec = {
        "home": str(synthetic_home.resolve()),
        "stable_id": "s-001",
        "ordinal": 1,
        "kind": "noop",
        "telemetry": str(telemetry.resolve()),
    }
    shim = Path(__file__).with_name("fault_shim").resolve()
    root = Path(__file__).resolve().parents[2]
    env = os.environ.copy()
    env.update(
        {
            "NATIVE_RATIONALE_SYNTHETIC": "1",
            "NATIVE_RATIONALE_FAULT_SPEC": base64.urlsafe_b64encode(
                json.dumps(spec, sort_keys=True).encode("utf-8")
            ).decode("ascii"),
            "PYTHONPATH": os.pathsep.join(
                [
                    str(shim),
                    str(control),
                    str(Path(__file__).parent.resolve()),
                    str((root / "modules" / "tool-memory").resolve()),
                    str((root / "src").resolve()),
                    os.environ.get("PYTHONPATH", ""),
                ]
            ),
        }
    )
    code = (
        "import json, sitecustomize\n"
        "import amplifier_module_tool_memory as tool\n"
        "status = sitecustomize.STATUS() if sitecustomize.STATUS else {}\n"
        "print(json.dumps({'same_execute_object': tool.MemoryTool.execute is sitecustomize.INSTALLED_EXECUTE, "
        "'status': status}, sort_keys=True))\n"
    )
    completed = subprocess.run(
        [sys.executable, "-c", code], capture_output=True, text=True, check=False, env=env
    )
    try:
        observation = json.loads(completed.stdout)
        events = [json.loads(line) for line in telemetry.read_text(encoding="utf-8").splitlines()]
        exit_status = next(event for event in reversed(events) if event.get("event") == "shim-status")
    except (OSError, json.JSONDecodeError, StopIteration):
        observation, exit_status = {}, {}
    status = observation.get("status", {})
    fingerprints = status.get("fingerprints", {}) if isinstance(status, dict) else {}
    return {
        "returncode": completed.returncode,
        "stderr": completed.stderr,
        "same_execute_object": observation.get("same_execute_object") is True,
        "effective_object_is_wrapper": status.get("effective_object_is_wrapper") is True,
        "exit_status_matches_live_status": exit_status == {"event": "shim-status", **status},
        "fingerprints": fingerprints,
        "telemetry_sha256": _sha(telemetry) if telemetry.is_file() else None,
    }


def prepare(out: Path, candidate_source: Path, *, suite: str = DEFAULT_SUITE) -> dict[str, Any]:
    """Build each selected actual-library human-origin store before any prompt."""

    if out.exists():
        raise FileExistsError(out)
    scenarios = _selected_scenarios(suite)
    base = _base()
    bindings, runtime = base.candidate_bindings(candidate_source)
    out.mkdir(mode=0o700, parents=True)
    fixtures: dict[str, Any] = {}
    for scenario in scenarios:
        home = out / scenario.name / "store"
        source = f"native-edge-{scenario.name}"
        home.mkdir(parents=True)
        subprocess.run(["git", "init", "-q", str(home)], check=True)
        bindings["init"](home, timer=False)
        bindings["record_session"](home, source, "human")
        appended = bindings["inbox_append"](
            home,
            [
                bindings["candidate"](
                    text=f"Use native edge fixture {index}.",
                    quote=f"For future reference, use native edge fixture {index}.",
                    session=source,
                    date="2026-09-13",
                )
                for index in range(1, len(scenario.ids) + 1)
            ],
        )
        snapshot = _snapshot(base, home)
        if [item.id for item in appended] != list(scenario.ids):
            raise RuntimeError(f"{scenario.name}: stable fixture ids differ")
        if bindings["session_origins"](home).get(source) != "human" or not snapshot["clean"]:
            raise RuntimeError(f"{scenario.name}: invalid human-origin clean fixture")
        fixtures[scenario.name] = {
            "home": str(home.resolve()),
            "source_session_id": source,
            "ids": list(scenario.ids),
            "snapshot": snapshot,
        }
    loader = _loader_control(out, Path(fixtures[scenarios[0].name]["home"]))
    payload = {
        "prepared_utc": _utc(),
        "all_cases_prepared_before_first_prompt": True,
        "fixtures": fixtures,
        "runtime": runtime,
        "loader_control": loader,
        "preparation_summary": {
            "status": "NOT YET",
            "reason": "fixtures and no-model loader control are prepared; no native evidence has been checked",
        },
        "script_sha256": _sha(Path(__file__)),
        "base_script_sha256": _sha(Path(__file__).with_name("rationale_decline.py")),
        "plan": plan(suite),
    }
    _write(out / "preparation.json", payload)
    return payload


@contextmanager
def _environment(values: dict[str, str]) -> Any:
    old = {key: os.environ.get(key) for key in values}
    try:
        os.environ.update(values)
        yield
    finally:
        for key, value in old.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value


@contextmanager
def _working_directory(path: Path) -> Any:
    """Use the explicit neutral native cwd without leaking it to the caller."""

    previous = Path.cwd()
    os.chdir(path)
    try:
        yield
    finally:
        os.chdir(previous)


def _native_cwd(candidate_source: Path, native_cwd: Path | None) -> Path:
    """Reject a source-tree launch before the first native process can start."""

    if native_cwd is None:
        raise ValueError("native rationale execution requires an explicit --native-cwd")
    if not native_cwd.is_absolute():
        raise ValueError("native rationale cwd must be absolute")
    resolved = native_cwd.resolve()
    if not resolved.is_dir():
        raise ValueError("native rationale cwd must be an existing directory")
    try:
        resolved.relative_to(candidate_source.resolve())
    except ValueError:
        return resolved
    raise ValueError("native rationale cwd must not be the candidate source tree")


class EdgeExecutor:
    """Sets one child-only shim spec, then invokes the original native adapter."""

    def __init__(
        self,
        base: Any,
        scenario: Scenario,
        deadline: datetime,
        provider: str,
        model: str,
        bundle: str,
        native_cwd: Path,
    ) -> None:
        self.base = base
        self.scenario = scenario
        self.deadline = deadline
        self.provider = provider
        self.model = model
        self.bundle = bundle
        self.native_cwd = native_cwd

    def __call__(
        self, *, case: str, user_text: str, home: Path, resume_session_id: str | None
    ) -> Any:
        if case != self.scenario.name:
            raise RuntimeError("edge executor received a mismatched scenario")
        remaining = (self.deadline - datetime.now(UTC)).total_seconds()
        if remaining <= 0:
            return self.base.NativeResult(
                None, "", "", 0.0, "deadline expired before launch", None, None, (), (), (), _utc(), _utc()
            )
        timeout = min(DEFAULT_TIMEOUT, remaining)
        telemetry = home.parent / "fault-telemetry.jsonl"
        fault = self.scenario.fault or "noop"
        spec = {
            "home": str(home.resolve()),
            "stable_id": self.scenario.ids[-1] if self.scenario.name == "later-partial-failure" else self.scenario.ids[0],
            "ordinal": self.scenario.ordinal or 1,
            "kind": fault,
            "telemetry": str(telemetry.resolve()),
        }
        shim = Path(__file__).with_name("fault_shim").resolve()
        eval_dir = Path(__file__).parent.resolve()
        pythonpath = os.pathsep.join([str(shim), str(eval_dir), os.environ.get("PYTHONPATH", "")])
        env = {
            "NATIVE_RATIONALE_SYNTHETIC": "1",
            "NATIVE_RATIONALE_FAULT_SPEC": base64.urlsafe_b64encode(
                json.dumps(spec, sort_keys=True).encode("utf-8")
            ).decode("ascii"),
            "PYTHONPATH": pythonpath,
            "GIT_CEILING_DIRECTORIES": os.environ.get("GIT_CEILING_DIRECTORIES") or str(self.native_cwd),
        }
        with _environment(env), _working_directory(self.native_cwd):
            return self.base.NativeCliExecutor(
                provider=self.provider, model=self.model, bundle=self.bundle, timeout=timeout
            )(case=case, user_text=user_text, home=home, resume_session_id=resume_session_id)


def _record_turn(base: Any, number: int, user: str, before: dict[str, Any], after: dict[str, Any], result: Any) -> dict[str, Any]:
    return {
        "turn": number,
        "user": user,
        "before": before,
        "after": after,
        "session_id": result.session_id,
        "receipts": list(result.receipts),
        "raw_tool_trace": list(result.raw_tool_trace),
        "executor_result": asdict(result),
        "raw_stdout_sha256": hashlib.sha256(result.stdout.encode()).hexdigest(),
        "raw_stderr_sha256": hashlib.sha256(result.stderr.encode()).hexdigest(),
    }


def _blocked(case: Scenario, reason: str) -> dict[str, Any]:
    return {"case": asdict(case), "status": "BLOCKED", "reason": reason, "turns": []}


def _first_review_failure(result: Any, telemetry: Path, *, native: bool) -> str | None:
    if result.error is not None:
        return str(result.error)
    if not result.session_id or result.response is None:
        return "no observed session or model response"
    if native:
        _events, status = _fault_events(telemetry)
        if (
            status.get("effective_object_is_wrapper") is not True
            or status.get("fingerprints", {}).get("effective_wrapper") is not True
        ):
            return "effective native shim evidence is missing"
    return None


def run(
    out: Path,
    *,
    candidate_source: Path,
    provider: str,
    model: str,
    bundle: str,
    deadline_utc: str,
    executor_factory: Callable[[Any, Scenario, datetime, str, str, str], Callable[..., Any]] | None = None,
    suite: str = DEFAULT_SUITE,
    native_cwd: Path | None = None,
) -> dict[str, Any]:
    """Execute fixed attempts only; injected factories are explicitly non-native."""

    preparation_path = out / "preparation.json"
    if not preparation_path.is_file():
        raise FileNotFoundError("run requires prepare's preparation.json")
    scenarios = _selected_scenarios(suite)
    attempt_limit = _attempt_limit(scenarios)
    resolved_native_cwd = _native_cwd(candidate_source, native_cwd) if executor_factory is None else None
    if os.environ.get("PYTEST_CURRENT_TEST") and executor_factory is None:
        raise RuntimeError("refusing native rationale execution under pytest")
    deadline = _deadline(deadline_utc)
    base = _base()
    _bindings, runtime = base.candidate_bindings(candidate_source)
    preparation = json.loads(preparation_path.read_text(encoding="utf-8"))
    prepared_suite = preparation.get("plan", {}).get("suite", DEFAULT_SUITE)
    if prepared_suite != suite:
        raise ValueError(f"prepared suite {prepared_suite!r} does not match requested suite {suite!r}")
    runs: list[dict[str, Any]] = []
    attempts = 0
    systemic: str | None = None
    for scenario in scenarios:
        if systemic:
            runs.append(_blocked(scenario, systemic))
            continue
        fixture = preparation["fixtures"][scenario.name]
        home = Path(fixture["home"])
        if not home.is_dir() or _snapshot(base, home) != fixture["snapshot"]:
            runs.append(_blocked(scenario, "prepared fixture is missing or changed before first prompt"))
            continue
        executor = (
            executor_factory(base, scenario, deadline, provider, model, bundle)
            if executor_factory is not None
            else EdgeExecutor(base, scenario, deadline, provider, model, bundle, resolved_native_cwd)
        )
        turns: list[dict[str, Any]] = []
        observed: str | None = None
        for number, user in enumerate(("/memory review", scenario.prompt), start=1):
            if attempts >= attempt_limit:
                raise AssertionError("native invocation ceiling exceeded")
            if (deadline - datetime.now(UTC)).total_seconds() <= 0:
                runs.append(_blocked(scenario, "absolute deadline elapsed before launch"))
                systemic = "absolute deadline elapsed; later launches intentionally unused"
                break
            before = _snapshot(base, home)
            attempts += 1  # This is immediately before the sole process-executor call.
            result = executor(case=scenario.name, user_text=user, home=home, resume_session_id=observed)
            after = _snapshot(base, home)
            turn = _record_turn(base, number, user, before, after, result)
            _write(out / scenario.name / f"attempt-{number:02d}.json", turn)
            turns.append(turn)
            if number == 1:
                observed = result.session_id
                failure = _first_review_failure(
                    result, home.parent / "fault-telemetry.jsonl", native=executor_factory is None
                )
                if failure:
                    systemic = f"first review failed for {scenario.name}: {failure}"
                    break
        if runs and runs[-1].get("case", {}).get("name") == scenario.name and not turns:
            continue
        telemetry = home.parent / "fault-telemetry.jsonl"
        case = {
            "case": asdict(scenario),
            "status": "RECORDED",
            "fixture": fixture,
            "turns": turns,
            "telemetry_path": str(telemetry.resolve()),
            "telemetry_sha256": _sha(telemetry) if telemetry.is_file() else None,
        }
        _write(out / scenario.name / "case-result.json", case)
        runs.append(case)
    payload = {
        "kind": "native-rationale-edge-run",
        "native": executor_factory is None,
        "suite": suite,
        "deadline_utc": deadline_utc,
        "attempt_count": attempts,
        "actual_attempt_count": attempts,
        "attempt_limit": attempt_limit,
        "max_actual_cli_turns": attempt_limit,
        "unused_slots": attempt_limit - attempts,
        "complete": attempts == attempt_limit and all(
            item.get("status") == "RECORDED" and len(item.get("turns", [])) == 2 for item in runs
        ),
        "native_cwd": str(resolved_native_cwd) if resolved_native_cwd is not None else None,
        "runtime": runtime,
        "runs": runs,
    }
    _write(out / "run.json", payload)
    return payload


def _remap(value: Any, mappings: dict[str, str]) -> Any:
    if isinstance(value, str):
        for old, new in mappings.items():
            if value == old or value.startswith(old + os.sep):
                return new + value[len(old):]
        return value
    if isinstance(value, list):
        return [_remap(item, mappings) for item in value]
    if isinstance(value, dict):
        return {key: _remap(item, mappings) for key, item in value.items()}
    return value


def _memory_calls(trace: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [entry for entry in trace if isinstance(entry, dict) and entry.get("tool") == "memory"]


def _exact_final_fence(response: object, calls: Sequence[dict[str, Any]]) -> bool:
    """The final answer is exactly the newline-joined actual tool output in one fence."""

    outputs = [call.get("result", {}).get("output") for call in calls]
    return bool(
        isinstance(response, str)
        and outputs
        and all(isinstance(output, str) for output in outputs)
        and response == "```\n" + "\n".join(outputs) + "\n```"
    )


def _git_text(base: Any, home: Path, *args: str) -> str | None:
    raw = base._git_bytes(home, *args)
    return None if raw is None else raw.decode("utf-8", errors="replace").strip()


def _decline_transition(
    base: Any, before: dict[str, Any], after: dict[str, Any], home: Path
) -> bool:
    """A decline is one clean commit changing only the inbox and audit record."""

    prior = before.get("head")
    current = after.get("head")
    if not isinstance(prior, str) or not isinstance(current, str) or prior == current:
        return False
    changed = _git_text(base, home, "diff-tree", "--no-commit-id", "--name-only", "-r", current)
    commit_count = _git_text(base, home, "rev-list", "--count", f"{prior}..{current}")
    parent = _git_text(base, home, "rev-parse", f"{current}^")
    before_files = before.get("tracked_file_sha256", {})
    after_files = after.get("tracked_file_sha256", {})
    protected = set(before_files) - {"inbox.md", "declined.md"}
    index_diff = base._git_bytes(home, "diff", "--cached", "--binary")
    index_entries = base._git_bytes(home, "ls-files", "--stage", "-z")
    recorded_index = after.get("staged_index", {})
    index_matches_head = (
        index_diff == b""
        and isinstance(recorded_index, dict)
        and recorded_index.get("diff_binary_base64") == ""
        and recorded_index.get("diff_binary_sha256") == hashlib.sha256(b"").hexdigest()
        and recorded_index.get("entries_base64")
        == base64.b64encode(index_entries or b"").decode("ascii")
    )
    return bool(
        parent == prior
        and commit_count == "1"
        and set((changed or "").splitlines()) == {"inbox.md", "declined.md"}
        and set(before_files) == set(after_files)
        and all(before_files.get(name) == after_files.get(name) for name in protected)
        and all(
            before.get("head_blob_sha256", {}).get(name) == after.get("head_blob_sha256", {}).get(name)
            for name in protected
        )
        and before.get("memory_sha256") == after.get("memory_sha256")
        and index_matches_head
        and before.get("clean") is True
        and after.get("clean") is True
    )


def _no_write_transition(base: Any, before: dict[str, Any], after: dict[str, Any] | None) -> bool:
    """Preserve data and Git boundaries while ignoring routine session/usage plumbing."""

    return bool(
        after
        and base.same_mutation_state(before, after)
        and all(
            before.get(key) == after.get(key)
            for key in ("memory_sha256", "inbox_sha256", "declined_sha256")
        )
    )


def _fault_events(telemetry: Path) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    try:
        events = [json.loads(line) for line in telemetry.read_text(encoding="utf-8").splitlines()]
    except (OSError, json.JSONDecodeError):
        return [], {}
    if not all(isinstance(event, dict) for event in events):
        return [], {}
    return events, next((event for event in reversed(events) if event.get("event") == "shim-status"), {})


def _loader_is_effective(preparation: dict[str, Any]) -> bool:
    loader = preparation.get("loader_control")
    if not isinstance(loader, dict):
        return False
    fingerprints = loader.get("fingerprints", {})
    root = Path(__file__).resolve().parents[2]
    expected = {
        "shim_source": Path(__file__).with_name("fault_shim") / "sitecustomize.py",
        "tool_module": root / "modules" / "tool-memory" / "amplifier_module_tool_memory" / "__init__.py",
        "library_module": root / "src" / "amplifier_memory" / "inbox.py",
    }
    return bool(
        loader.get("returncode") == 0
        and loader.get("same_execute_object") is True
        and loader.get("effective_object_is_wrapper") is True
        and loader.get("exit_status_matches_live_status") is True
        and loader.get("telemetry_sha256")
        and all(
            fingerprints.get(name) == str(path.resolve())
            and fingerprints.get(f"{name}_sha256") == _sha(path.resolve())
            for name, path in expected.items()
        )
        and fingerprints.get("original_callable_identity")
        and fingerprints.get("current_callable_identity")
        and fingerprints["original_callable_identity"] != fingerprints["current_callable_identity"]
    )


def _telemetry_check(
    scenario: dict[str, Any], calls: list[dict[str, Any]], events: list[dict[str, Any]], status: dict[str, Any]
) -> bool:
    """Bind one target event to raw model arguments without altering the CLI trace."""

    declines = [
        call
        for call in calls
        if isinstance(call.get("arguments"), dict)
        and call["arguments"].get("operation") == "review"
        and call["arguments"].get("action") == "decline"
    ]
    tool_events = [event for event in events if event.get("event") == "tool-result"]
    active = [event for event in tool_events if event.get("activation") is True]
    expected_ordinal = scenario["ordinal"] or 1
    expected_id = scenario["ids"][-1] if scenario["name"] == "later-partial-failure" else scenario["ids"][0]
    if (
        len(declines) != len(scenario["ids"])
        or len(active) != 1
        or status.get("all_declines") != len(declines)
        or status.get("activation_count") != 1
        or status.get("wrong_id_at_ordinal") is not False
        or status.get("duplicate_or_unused") is not False
        or status.get("matched") is not True
    ):
        return False
    event = active[0]
    original = event.get("original_args")
    forwarded = event.get("forwarded_args")
    if (
        event.get("all_decline_ordinal") != expected_ordinal
        or event.get("stable_id") != expected_id
        or not isinstance(original, dict)
        or not isinstance(forwarded, dict)
        or original != declines[expected_ordinal - 1]["arguments"]
    ):
        return False
    fault = scenario["fault"]
    if fault is None:
        return bool(
            event.get("kind") == "noop"
            and original == forwarded
            and "reason" not in original
            and "reason" not in forwarded
            and event.get("injected_reason") is None
            and event.get("injected_reason_utf8_bytes") == 0
        )
    if fault == "readback":
        return bool(
            event.get("kind") == "readback"
            and original == forwarded
            and "reason" not in original
            and "reason" not in forwarded
        )
    reason = _FAULT_REASONS[fault]
    expected_forwarded = {**original, "reason": reason}
    return bool(
        event.get("kind") == fault
        and "reason" not in original
        and forwarded == expected_forwarded
        and event.get("injected_reason") == reason
        and event.get("injected_reason_utf8_bytes")
        == (None if fault == "invalid-utf8" else len(reason.encode("utf-8")))
        and (
            event.get("injected_reason_absent_from_human_provenance") is True
            if fault == "unverified"
            else event.get("injected_reason_absent_from_human_provenance") is False
        )
    )


def _case_check(
    base: Any, bindings: dict[str, Any], item: dict[str, Any], mappings: dict[str, str]
) -> dict[str, Any]:
    scenario = item.get("case", {})
    name = scenario.get("name", "<malformed>") if isinstance(scenario, dict) else "<malformed>"
    if item.get("status") == "BLOCKED":
        return {"case": name, "status": "BLOCKED", "checks": {"prepared": False}}
    if not isinstance(scenario, dict) or not isinstance(item.get("turns"), list):
        return {"case": name, "status": "FAIL", "checks": {"well_formed_case": False}}
    turns = item.get("turns", [])
    checks: dict[str, bool] = {"two_attempts": len(turns) == 2}
    if len(turns) != 2:
        return {"case": name, "status": "FAIL", "checks": checks}
    first, second = turns
    if not isinstance(first, dict) or not isinstance(second, dict):
        return {"case": name, "status": "FAIL", "checks": {"well_formed_turns": False}}
    for turn in turns:
        result = turn.get("executor_result", {})
        try:
            parsed = base.terminal_json_envelope(result.get("stdout", ""))
            trace, receipts = base.extract_tool_trace(parsed)
            checks[f"reparse_{turn['turn']}"] = (
                list(trace) == turn.get("raw_tool_trace") and list(receipts) == turn.get("receipts")
            )
        except (TypeError, ValueError, json.JSONDecodeError):
            checks[f"reparse_{turn['turn']}"] = False
    first_calls = _memory_calls(first.get("raw_tool_trace", []))
    checks["first_review_exact_and_read_only"] = (
        first.get("user") == "/memory review"
        and base.same_mutation_state(first.get("before", {}), first.get("after", {}))
        and len(first_calls) == 1
        and base._is_legal_review_read(first_calls[0])
        and first_calls[0]["result"].get("success") is True
    )
    argv = second.get("executor_result", {}).get("argv", [])
    resume_index = argv.index("--resume") if argv.count("--resume") == 1 else -1
    checks["resume_observed_and_returned"] = (
        resume_index >= 0
        and resume_index + 1 < len(argv)
        and argv[resume_index + 1] == first.get("session_id")
        and second.get("session_id") == first.get("session_id")
    )
    fixture = item.get("fixture", {})
    if not isinstance(fixture, dict) or not isinstance(fixture.get("home"), str):
        return {"case": name, "status": "FAIL", "checks": {**checks, "fixture": False}}
    home = Path(_remap(fixture["home"], mappings))
    actual = _snapshot(base, home) if home.is_dir() else None
    checks["final_exported_store_matches_record"] = bool(actual and actual == second.get("after"))
    calls = [
        call for call in _memory_calls(second.get("raw_tool_trace", []))
        if call["arguments"].get("operation") == "review" and call["arguments"].get("action") == "decline"
    ]
    original_clean = all("reason" not in call["arguments"] for call in calls)
    expected = scenario["expected"]
    events, status = _fault_events(Path(_remap(item.get("telemetry_path", ""), mappings)))
    checks["target_fault_event_is_exact"] = _telemetry_check(scenario, calls, events, status)
    fingerprints = status.get("fingerprints", {}) if isinstance(status, dict) else {}
    checks["effective_loaded_wrapper"] = bool(
        status.get("effective_object_is_wrapper") is True
        and fingerprints.get("shim_source_sha256")
        and fingerprints.get("tool_module_sha256")
        and fingerprints.get("library_module_sha256")
        and fingerprints.get("original_callable_identity")
        and fingerprints.get("current_callable_identity")
        and fingerprints["original_callable_identity"] != fingerprints["current_callable_identity"]
    )
    missing_response = any(turn.get("executor_result", {}).get("response") is None for turn in turns)
    checks["final_response_exact_fence"] = _exact_final_fence(
        second.get("executor_result", {}).get("response"), calls
    )
    records = bindings["declined_records"](home) if home.is_dir() else []
    expected_receipts = [DECLINE_RECEIPT.format(id=call["arguments"]["id"]) for call in calls if call["result"].get("success") is True]
    if expected == "ordinary-no-reason":
        raw_declined = (home / "declined.md").read_text(encoding="utf-8") if home.is_dir() else ""
        checks["ordinary_no_reason_receipt_and_store"] = bool(
            len(calls) == 1 and original_clean and calls[0]["result"].get("success") is True
            and second.get("receipts") == expected_receipts
            and calls[0]["result"].get("output") == expected_receipts[0]
            and len(records) == 1 and records[0].reason is None and records[0].reason_state == "absent"
            and "because it is a product request." not in raw_declined
            and " reason:" not in raw_declined
            and actual and _decline_transition(base, fixture["snapshot"], actual, home)
        )
    elif expected == "refuse-before-write":
        checks["fault_refused_before_write"] = bool(
            len(calls) == 1 and original_clean and _no_write_transition(base, fixture["snapshot"], actual)
            and not second.get("receipts")
            and calls[0]["result"].get("success") is False
            and isinstance(calls[0]["result"].get("output"), str)
            and bool(calls[0]["result"]["output"])
        )
    elif expected == "first-success-second-pending":
        checks["first_receipt_preserved"] = bool(
            len(calls) == 2 and original_clean and calls[0]["result"].get("success") is True
            and calls[1]["result"].get("success") is False and second.get("receipts") == expected_receipts
            and calls[0]["result"].get("output") == expected_receipts[0]
            and len(records) == 1 and records[0].reason_state == "absent"
            and [entry.id for entry in bindings["pending"](home)] == [scenario["ids"][1]]
            and actual and _decline_transition(base, fixture["snapshot"], actual, home)
        )
    else:
        readback = next((event for event in events if event.get("event") == "committed-decline-readback"), {})
        checks["committed_then_unverified"] = bool(
            len(calls) == 1 and original_clean and calls[0]["result"].get("success") is False
            and calls[0]["result"].get("output") == "commit succeeded but decline readback is unverified"
            and len(records) == 1 and records[0].reason_state == "absent"
            and actual and _decline_transition(base, fixture["snapshot"], actual, home)
            and status.get("readback_count") == 1
            and readback.get("commit_count") == "1"
            and readback.get("commit_parent") == fixture["snapshot"]["head"]
            and readback.get("changed_paths") == ["declined.md", "inbox.md"]
            and readback.get("before", {}).get("head") != readback.get("after", {}).get("head")
            and readback.get("after", {}).get("stable_id_in_inbox") is False
            and isinstance(readback.get("committed_declined"), str)
            and " reason:" not in readback["committed_declined"]
        )
    return {
        "case": name,
        "status": "BLOCKED" if missing_response else ("PASS" if all(checks.values()) else "FAIL"),
        "checks": checks,
        "response_semantic_review": "verified" if not missing_response else "BLOCKED",
    }


def check(out: Path, candidate_source: Path, maps: Sequence[str]) -> dict[str, Any]:
    """Read only exported evidence; caller supplies old=new remaps when relocated."""

    if not (out / "run.json").is_file():
        raise FileNotFoundError("check requires run.json")
    if any(item.count("=") != 1 or not all(item.split("=", 1)) for item in maps):
        return {"kind": "native-rationale-edge-check", "status": "FAIL", "reason": "malformed path remap"}
    mappings = dict(item.split("=", 1) for item in maps)
    base = _base()
    bindings, _runtime = base.candidate_bindings(candidate_source)
    run_payload = json.loads((out / "run.json").read_text(encoding="utf-8"))
    if run_payload.get("native") is False:
        return {"kind": "native-rationale-edge-check", "status": "BLOCKED", "reason": "non-native injected executor evidence"}
    if run_payload.get("native") is not True:
        return {"kind": "native-rationale-edge-check", "status": "FAIL", "reason": "malformed native evidence flag"}
    preparation = json.loads((out / "preparation.json").read_text(encoding="utf-8")) if (out / "preparation.json").is_file() else {}
    try:
        suite = run_payload.get("suite", DEFAULT_SUITE)
        scenarios = _selected_scenarios(suite)
    except (TypeError, ValueError):
        return {"kind": "native-rationale-edge-check", "status": "FAIL", "reason": "unknown native suite"}
    scenario_shape = json.loads(json.dumps([asdict(scenario) for scenario in scenarios]))
    attempt_limit = _attempt_limit(scenarios)
    prepared_plan = preparation.get("plan", {}) if isinstance(preparation, dict) else {}
    runs = run_payload.get("runs")
    shape_ok = bool(
        isinstance(runs, list)
        and prepared_plan.get("suite", DEFAULT_SUITE) == suite
        and prepared_plan.get("scenarios") == scenario_shape
        and run_payload.get("actual_attempt_count") == attempt_limit
        and run_payload.get("attempt_limit") == attempt_limit
        and run_payload.get("attempt_count") == attempt_limit
        and run_payload.get("max_actual_cli_turns") == attempt_limit
        and run_payload.get("unused_slots", 0) == 0
        and run_payload.get("complete", True) is True
        and isinstance(run_payload.get("native_cwd"), str)
        and Path(run_payload["native_cwd"]).is_absolute()
        and len(runs) == len(scenarios)
        and [item.get("case") if isinstance(item, dict) else None for item in runs] == scenario_shape
        and all(isinstance(item, dict) and item.get("status") == "RECORDED" and len(item.get("turns", [])) == 2 for item in runs)
    )
    if not shape_ok:
        return {
            "kind": "native-rationale-edge-check",
            "status": "FAIL",
            "reason": "frozen selected-suite measurement shape is missing, altered, or incomplete",
        }
    if not _loader_is_effective(preparation):
        return {
            "kind": "native-rationale-edge-check",
            "status": "FAIL",
            "reason": "no-model sitecustomize loader control did not prove the effective adapter wrapper",
        }
    results = [_case_check(base, bindings, item, mappings) for item in runs]
    status = "PASS" if results and all(item["status"] == "PASS" for item in results) else "FAIL"
    if any(item["status"] == "BLOCKED" for item in results):
        status = "BLOCKED"
    return {
        "kind": "native-rationale-edge-check",
        "status": status,
        "cases": results,
        "checked_utc": _utc(),
        "preparation_summary": "PREPARED" if status == "PASS" else "NOT PREPARED",
        "native_result": "NOT YET",
    }


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    plan_parser = commands.add_parser("plan", help="print immutable plan; no model call")
    plan_parser.add_argument("--suite", choices=tuple(SUITES), default=DEFAULT_SUITE)
    prepare_parser = commands.add_parser("prepare", help="prepare all synthetic stores; no model call")
    prepare_parser.add_argument("--out", type=Path, required=True)
    prepare_parser.add_argument("--candidate-source", type=Path, required=True)
    prepare_parser.add_argument("--suite", choices=tuple(SUITES), default=DEFAULT_SUITE)
    run_parser = commands.add_parser("run", help="run the bounded native evaluation")
    run_parser.add_argument("--out", type=Path, required=True)
    run_parser.add_argument("--candidate-source", type=Path, required=True)
    run_parser.add_argument("--provider", required=True)
    run_parser.add_argument("--model", required=True)
    run_parser.add_argument("--bundle", required=True)
    run_parser.add_argument("--deadline-utc", required=True)
    run_parser.add_argument("--suite", choices=tuple(SUITES), default=DEFAULT_SUITE)
    run_parser.add_argument("--native-cwd", type=Path, required=True)
    check_parser = commands.add_parser("check", help="offline check persisted native evidence")
    check_parser.add_argument("--out", type=Path, required=True)
    check_parser.add_argument("--candidate-source", type=Path, required=True)
    check_parser.add_argument("--map", action="append", default=[], metavar="OLD=NEW")
    args = parser.parse_args(argv)
    if args.command == "plan":
        print(json.dumps(plan(args.suite), indent=2, ensure_ascii=True))
        return 0
    if args.command == "prepare":
        payload = prepare(args.out, args.candidate_source, suite=args.suite)
        print(json.dumps({"prepared": len(payload["fixtures"]), "native_result": "NOT YET"}))
        return 0
    if args.command == "run":
        if os.environ.get("PYTEST_CURRENT_TEST"):
            raise RuntimeError("refusing native rationale run under pytest")
        payload = run(
            args.out, candidate_source=args.candidate_source, provider=args.provider,
            model=args.model, bundle=args.bundle, deadline_utc=args.deadline_utc,
            suite=args.suite, native_cwd=args.native_cwd,
        )
        print(json.dumps({"attempt_count": payload["attempt_count"], "native": True}))
        return 0
    if any("=" not in item for item in args.map):
        raise ValueError("--map must be OLD=NEW")
    payload = check(args.out, args.candidate_source, args.map)
    print(json.dumps({"status": payload["status"]}))
    return 0 if payload["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())