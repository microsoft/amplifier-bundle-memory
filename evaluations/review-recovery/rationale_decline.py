"""Bounded, headless native-decline capture for the post-integration DTU lane.

The default command only writes a plan.  ``--execute`` is deliberately a two-step
opt-in: it needs an isolated-run flag/environment and its provider/model/bundle
configuration.  The adapter invokes the real ``amplifier run`` CLI twice per
case, resuming its observed first session rather than inventing a session id.
"""

from __future__ import annotations

import argparse
import base64
import dataclasses
import hashlib
import importlib
import json
import os
import re
import subprocess
import sys
import time
from collections.abc import Callable, Sequence
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

CASES: dict[str, list[str]] = {
    "single-reason": [
        "/memory review",
        "Decline the suggestion about fictional release labels because that is a one-time report format, not my standing preference.",
    ],
    "shared-batch-reason": [
        "/memory review",
        "Decline both fictional release-label suggestions: those are one-time report formats, not standing preferences.",
    ],
    "distinct-reasons": [
        "/memory review",
        "Decline the first fictional suggestion because it is a product request; decline the second because it only acknowledges this rollout.",
    ],
    "ambiguous-reason": [
        "/memory review",
        "Decline both fictional suggestions: one is a product request, and one only acknowledges this rollout.",
    ],
}
EXPECTED_REASONS: dict[str, tuple[str, ...]] = {
    "single-reason": ("that is a one-time report format, not my standing preference.",),
    "shared-batch-reason": ("those are one-time report formats, not standing preferences.",) * 2,
    "distinct-reasons": ("it is a product request", "it only acknowledges this rollout."),
    "ambiguous-reason": (),
}
MAX_TURNS = 8


@dataclasses.dataclass(frozen=True)
class NativeResult:
    """One actual CLI process result, including only the trace's typed evidence."""

    returncode: int | None
    stdout: str
    stderr: str
    elapsed_s: float
    error: str | None
    session_id: str | None
    response: str | None
    raw_tool_trace: tuple[dict[str, Any], ...]
    receipts: tuple[str, ...]
    argv: tuple[str, ...]
    utc_started: str | None = None
    utc_finished: str | None = None
    provider_usage: dict[str, Any] = dataclasses.field(
        default_factory=lambda: {
            "status": "unavailable",
            "reason": "injected executor did not capture provider usage",
        }
    )


Executor = Callable[..., NativeResult]


def plan() -> dict[str, Any]:
    return {
        "kind": "native-rationale-decline-capture",
        "max_actual_cli_turns": MAX_TURNS,
        "cases": CASES,
        "requirements": [
            "fresh isolated store",
            "preflight actual human records and pending suggestions with library APIs",
            "drive the real memory skill and MemoryTool through a provider, without a mocked assistant",
            "capture before/after HEAD, index, declined bytes, receipts, ordered actual tool calls",
            "ambiguous reason must make zero writes",
        ],
        "excluded": [
            "ordinary no-reason compatibility is deterministic unit coverage",
            "no direct inbox.decline oracle",
        ],
    }


def _run_git(home: Path, *args: str) -> str | None:
    """A missing git repository is captured as evidence, not silently treated as clean."""
    try:
        return subprocess.check_output(
            ["git", "-C", str(home), *args], text=True, stderr=subprocess.DEVNULL
        ).strip()
    except (OSError, subprocess.CalledProcessError):
        return None


def _file_sha256(path: Path) -> str | None:
    return hashlib.sha256(path.read_bytes()).hexdigest() if path.is_file() else None


def _git_bytes(home: Path, *args: str) -> bytes | None:
    """Return git's exact bytes; index evidence must not be reduced to a flag."""
    try:
        return subprocess.check_output(
            ["git", "-C", str(home), *args], stderr=subprocess.DEVNULL
        )
    except (OSError, subprocess.CalledProcessError):
        return None


def _encoded(value: bytes | None) -> str | None:
    return None if value is None else base64.b64encode(value).decode("ascii")


def write_json_new(path: Path, value: dict[str, Any]) -> None:
    """Persist private evidence without replacing an earlier observed record."""
    if path.exists():
        raise FileExistsError(f"refusing to overwrite output: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    path.chmod(0o600)


def store_snapshot(home: Path) -> dict[str, Any]:
    """Capture mutation oracle inputs separately from routine store plumbing."""
    tracked_paths = (_git_bytes(home, "ls-files", "-z") or b"").split(b"\0")
    tracked_names = {name.decode("utf-8") for name in tracked_paths if name}
    tracked = {
        name: _file_sha256(home / name)
        for name in sorted(tracked_names)
    }
    plumbing = {
        str(path.relative_to(home)): _file_sha256(path)
        for path in sorted(home.rglob("*"))
        if path.is_file()
        and ".git" not in path.relative_to(home).parts
        and str(path.relative_to(home)) not in tracked_names
    }
    index_diff = _git_bytes(home, "diff", "--cached", "--binary")
    index_entries = _git_bytes(home, "ls-files", "--stage", "-z")
    return {
        "home": str(home),
        "head": _run_git(home, "rev-parse", "HEAD"),
        "tracked_file_sha256": tracked,
        "staged_index": {
            "diff_binary_sha256": None if index_diff is None else hashlib.sha256(index_diff).hexdigest(),
            "diff_binary_base64": _encoded(index_diff),
            "entries_base64": _encoded(index_entries),
        },
        "plumbing_file_sha256": plumbing,
        "memory_sha256": _file_sha256(home / "MEMORY.md"),
        "inbox_sha256": _file_sha256(home / "inbox.md"),
        "declined_sha256": _file_sha256(home / "declined.md"),
        "clean": _run_git(home, "status", "--porcelain") == "",
    }


def same_mutation_state(before: dict[str, Any], after: dict[str, Any]) -> bool:
    """Ignore expected session/usage plumbing while retaining real git state."""
    return all(
        before.get(key) == after.get(key)
        for key in ("head", "tracked_file_sha256", "staged_index")
    )


def candidate_bindings(candidate_source: Path) -> tuple[dict[str, Any], dict[str, dict[str, str]]]:
    """Import only the declared candidate source, refusing an ambient package."""
    root = candidate_source.resolve()
    source_root = root / "src"
    expected = {
        "src/amplifier_memory/__init__.py": source_root / "amplifier_memory" / "__init__.py",
        "src/amplifier_memory/inbox.py": source_root / "amplifier_memory" / "inbox.py",
    }
    if not source_root.is_dir():
        raise RuntimeError(f"candidate source has no import root: {source_root}")
    sys.path.insert(0, str(source_root))
    try:
        memory = importlib.import_module("amplifier_memory")
        inbox = importlib.import_module("amplifier_memory.inbox")
    finally:
        # Remove precisely the entry we inserted, even if the caller already had it later.
        del sys.path[0]
    resolved = {
        "src/amplifier_memory/__init__.py": Path(memory.__file__ or "").resolve(),
        "src/amplifier_memory/inbox.py": Path(inbox.__file__ or "").resolve(),
    }
    if resolved != expected:
        detail = ", ".join(f"{name}={path}" for name, path in resolved.items())
        raise RuntimeError(f"candidate import escaped declared root {root}; resolved {detail}")
    runtime = {
        name: {"path": str(path), "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}
        for name, path in resolved.items()
    }
    return {
        "init": memory.init,
        "record_session": memory.record_session,
        "session_origins": memory.session_origins,
        "pending": inbox.pending,
        "declined_records": inbox.declined_records,
        "inbox_append": inbox.append,
        "candidate": inbox.Candidate,
    }, runtime


def _fixture_candidates(bindings: dict[str, Any], case: str, session_id: str) -> list[Any]:
    candidate = bindings["candidate"]
    count = 1 if case == "single-reason" else 2
    return [
        candidate(
            text=f"Use fictional release label {number}.",
            quote=f"For future reference, use fictional release label {number}.",
            session=session_id,
            date="2026-09-13",
        )
        for number in range(1, count + 1)
    ]


def prepare_fixture(home: Path, case: str, bindings: dict[str, Any]) -> dict[str, Any]:
    """Use the candidate writers and prove a clean human/pending starting state."""
    source_session_id = f"native-rationale-{case}"
    bindings["init"](home, timer=False)
    bindings["record_session"](home, source_session_id, "human")
    suggestions = bindings["inbox_append"](
        home, _fixture_candidates(bindings, case, source_session_id)
    )
    origins = bindings["session_origins"](home)
    pending = bindings["pending"](home)
    before = store_snapshot(home)
    expected_count = 1 if case == "single-reason" else 2
    if origins.get(source_session_id) != "human":
        raise RuntimeError(f"{case}: fixture session did not retain human origin")
    if [item.id for item in pending] != [item.id for item in suggestions] or len(pending) != expected_count:
        raise RuntimeError(f"{case}: fixture did not retain exactly its pending suggestions")
    if bindings["declined_records"](home):
        raise RuntimeError(f"{case}: fixture unexpectedly has declined suggestions")
    if not before["clean"]:
        raise RuntimeError(f"{case}: fixture store is not clean before native execution")
    return {
        "source_session_id": source_session_id,
        "suggestion_ids": [item.id for item in suggestions],
        "initial": before,
    }


def terminal_json_envelope(stdout: str) -> dict[str, Any]:
    """Accept one terminal JSON object after a known human-readable CLI prelude."""
    starts = list(re.finditer(r"(?m)^\{", stdout))
    if len(starts) != 1:
        raise ValueError("stdout needs exactly one terminal JSON envelope")
    start = starts[0].start()
    value, end = json.JSONDecoder().raw_decode(stdout[start:])
    if stdout[start + end :].strip() or not isinstance(value, dict):
        raise ValueError("stdout has no single terminal JSON object")
    return value


def utc_timestamp() -> str:
    """Produce an unambiguous observation timestamp for a process attempt."""
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


def provider_usage_observation(stdout: str) -> dict[str, Any]:
    """Retain reported provider usage, or why this CLI output cannot provide it."""
    try:
        payload = terminal_json_envelope(stdout)
    except (TypeError, ValueError, json.JSONDecodeError):
        return {
            "status": "unavailable",
            "reason": "CLI stdout has no parseable terminal JSON envelope from which provider usage can be read",
        }
    usage = payload.get("usage")
    if usage is None:
        return {
            "status": "unavailable",
            "reason": "CLI JSON envelope has no provider usage field",
        }
    return {"status": "captured", "value": usage}


def extract_tool_trace(payload: dict[str, Any]) -> tuple[tuple[dict[str, Any], ...], tuple[str, ...]]:
    """Validate native trace entries and retain only receipts actually returned by memory."""
    trace = payload.get("execution_trace")
    if not isinstance(trace, list):
        raise TypeError("native CLI JSON has no execution_trace list")
    calls: list[dict[str, Any]] = []
    receipts: list[str] = []
    for entry in trace:
        if not isinstance(entry, dict) or entry.get("type") != "tool_call":
            continue
        tool, arguments, result, timestamp = (
            entry.get("tool"), entry.get("arguments"), entry.get("result"), entry.get("timestamp")
        )
        if not isinstance(tool, str) or not isinstance(arguments, dict) or not isinstance(result, dict):
            raise TypeError("native tool trace entry has invalid tool, arguments, or result")
        if not isinstance(timestamp, str) or not timestamp:
            raise TypeError("native tool trace entry has no timestamp")
        call = {"tool": tool, "arguments": arguments, "result": result, "timestamp": timestamp}
        calls.append(call)
        output = result.get("output")
        if (
            tool == "memory"
            and arguments.get("operation") == "review"
            and arguments.get("action") == "decline"
            and result.get("success") is True
            and isinstance(output, str)
        ):
            receipts.append(output)
    return tuple(calls), tuple(receipts)


class NativeCliExecutor:
    """The actual headless CLI adapter; no retry, fallback, or synthetic session exists."""

    def __init__(self, *, provider: str, model: str, bundle: str, timeout: float):
        self.provider = provider
        self.model = model
        self.bundle = bundle
        self.timeout = timeout

    def __call__(
        self,
        *,
        case: str,
        user_text: str,
        home: Path,
        resume_session_id: str | None,
    ) -> NativeResult:
        del case  # Case isolation is represented by the unique store passed in the environment.
        argv = [
            "amplifier",
            "run",
            "--output-format",
            "json-trace",
            "-p",
            self.provider,
            "-m",
            self.model,
            "-B",
            self.bundle,
        ]
        if resume_session_id is not None:
            argv.extend(["--resume", resume_session_id])
        argv.append(user_text)
        env = os.environ.copy()
        env["AMPLIFIER_MEMORY_HOME"] = str(home)
        started = time.monotonic()
        started_utc = utc_timestamp()
        try:
            completed = subprocess.run(
                argv, capture_output=True, text=True, timeout=self.timeout, check=False, env=env
            )
        except (OSError, subprocess.TimeoutExpired) as exc:
            raw_stdout = getattr(exc, "stdout", None) or getattr(exc, "output", None) or ""
            raw_stderr = getattr(exc, "stderr", None) or ""
            if isinstance(raw_stdout, bytes):
                raw_stdout = raw_stdout.decode("utf-8", errors="replace")
            if isinstance(raw_stderr, bytes):
                raw_stderr = raw_stderr.decode("utf-8", errors="replace")
            return NativeResult(
                None,
                str(raw_stdout),
                str(raw_stderr),
                round(time.monotonic() - started, 6),
                f"{type(exc).__name__}: {exc}",
                None,
                None,
                (),
                (),
                tuple(argv),
                started_utc,
                utc_timestamp(),
                provider_usage_observation(str(raw_stdout)),
            )
        error = None if completed.returncode == 0 else f"exit {completed.returncode}"
        usage = provider_usage_observation(completed.stdout)
        session_id: str | None = None
        response: str | None = None
        calls: tuple[dict[str, Any], ...] = ()
        receipts: tuple[str, ...] = ()
        if error is None:
            try:
                payload = terminal_json_envelope(completed.stdout)
                session = payload.get("session_id")
                response_value = payload.get("response")
                if not isinstance(session, str) or not session.strip():
                    raise TypeError("native CLI JSON has no session_id")
                if not isinstance(response_value, str):
                    raise TypeError("native CLI JSON has no string response")
                session_id = session
                response = response_value
                calls, receipts = extract_tool_trace(payload)
            except (TypeError, ValueError, json.JSONDecodeError) as exc:
                error = f"{type(exc).__name__}: {exc}"
        return NativeResult(
            completed.returncode,
            completed.stdout,
            completed.stderr,
            round(time.monotonic() - started, 6),
            error,
            session_id,
            response,
            calls,
            receipts,
            tuple(argv),
            started_utc,
            utc_timestamp(),
            usage,
        )


def _memory_calls(result: NativeResult) -> list[dict[str, Any]]:
    return [call for call in result.raw_tool_trace if call["tool"] == "memory"]


def _is_legal_review_read(call: dict[str, Any]) -> bool:
    """Accept equivalent normal list forms, including an explicit page one."""
    arguments = call["arguments"]
    if arguments.get("operation") != "review" or arguments.get("action") not in (None, "", "list"):
        return False
    if set(arguments) - {"operation", "action", "page"}:
        return False
    page = arguments.get("page", 1)
    return isinstance(page, int) and not isinstance(page, bool) and page >= 1


def _reason_is_human_substring(value: object, explanation: str) -> bool:
    """A raw reason can retain punctuation or a harmless leading ``because``."""
    if not isinstance(value, str) or not value.strip():
        return False
    raw = value.strip()
    candidates = [raw]
    if raw.casefold().startswith("because "):
        candidates.append(raw[8:].lstrip())
    return any(candidate and candidate in explanation for candidate in candidates)


def _reason_map_matches(
    expected: tuple[str, ...], stored: list[object], tool_values: list[object]
) -> bool:
    """Bind each persisted/tool reason to its own human explanation, not another's."""
    if len(stored) != len(expected) or stored != tool_values:
        return False
    for index, (value, explanation) in enumerate(zip(stored, expected, strict=True)):
        if not _reason_is_human_substring(value, explanation):
            return False
        if len(set(expected)) > 1:
            other_explanations = expected[:index] + expected[index + 1 :]
            if any(_reason_is_human_substring(value, other) for other in other_explanations):
                return False
    return True


def _prohibited_mutation(result: NativeResult) -> bool:
    prohibited = {"save", "edit", "retarget", "forget", "accept"}
    for call in result.raw_tool_trace:
        if call["tool"] in prohibited:
            return True
        if call["tool"] == "memory" and str(call["arguments"].get("operation", "")) in prohibited:
            return True
        if call["tool"] == "memory" and str(call["arguments"].get("action", "")) in prohibited:
            return True
    return False


def _record_turn(number: int, user: str, before: dict[str, Any], after: dict[str, Any], result: NativeResult) -> dict[str, Any]:
    """Keep raw output private (the 0600 result) while exposing typed evidence separately."""
    return {
        "turn": number,
        "user": user,
        "before": before,
        "after": after,
        "session_id": result.session_id,
        "receipts": list(result.receipts),
        "raw_tool_trace": list(result.raw_tool_trace),
        "executor_result": dataclasses.asdict(result),
    }


def _validate_case(run: dict[str, Any], bindings: dict[str, Any]) -> dict[str, bool]:
    """Fail closed on malformed trace, unexpected writes, or a wrong decline map."""
    fixture = run["fixture"]
    turns = run["turns"]
    case = run["case"]
    first = turns[0] if turns else None
    second = turns[1] if len(turns) > 1 else None
    checks: dict[str, bool] = {
        "two_turns_or_recorded_missing_second": len(turns) == 2 or run.get("missing_second_turn") is True,
        "first_result_valid": bool(first and first["executor_result"]["error"] is None and first["session_id"]),
        "first_review_is_read_only": False,
        "no_prohibited_mutation_calls": all(
            not _prohibited_mutation(NativeResult(**turn["executor_result"])) for turn in turns
        ),
        "second_result_valid": bool(second and second["executor_result"]["error"] is None),
        "resumed_observed_session": bool(
            second and first and second["executor_result"]["argv"].count("--resume") == 1
            and second["executor_result"]["argv"][second["executor_result"]["argv"].index("--resume") + 1]
            == first["session_id"]
        ),
        "resumed_session_returned": bool(
            second and first and second["session_id"] == first["session_id"]
        ),
        "memory_unchanged": False,
        "expected_pending_and_declines": False,
        "receipts_from_actual_declines": False,
    }
    if first:
        first_result = NativeResult(**first["executor_result"])
        first_memory = _memory_calls(first_result)
        checks["first_review_is_read_only"] = (
            same_mutation_state(first["before"], first["after"])
            and len(first_memory) == 1
            and _is_legal_review_read(first_memory[0])
            and first_memory[0]["result"].get("success") is True
        )
    if not second:
        return checks
    second_result = NativeResult(**second["executor_result"])
    expected_ids = fixture["suggestion_ids"]
    expected_reasons = EXPECTED_REASONS[case]
    memory_calls = _memory_calls(second_result)
    declines = [
        call for call in memory_calls
        if call["arguments"].get("operation") == "review"
        and call["arguments"].get("action") == "decline"
    ]
    actual_pending = bindings["pending"](Path(fixture["initial"]["home"]))
    actual_declined = bindings["declined_records"](Path(fixture["initial"]["home"]))
    expected_decline_ids = expected_ids[: len(expected_reasons)]
    checks["memory_unchanged"] = second["before"]["memory_sha256"] == second["after"]["memory_sha256"]
    checks["expected_pending_and_declines"] = (
        [item.id for item in actual_pending] == expected_ids[len(expected_reasons) :]
        and len(actual_declined) == len(expected_reasons)
        and [item.text for item in actual_declined]
        == [f"Use fictional release label {number}." for number in range(1, len(expected_reasons) + 1)]
        and _reason_map_matches(
            expected_reasons,
            [item.reason for item in actual_declined],
            [call["arguments"].get("reason") for call in declines],
        )
    )
    checks["receipts_from_actual_declines"] = (
        [call["arguments"].get("id") for call in declines] == expected_decline_ids
        and len(second_result.receipts) == len(expected_reasons)
    )
    if case == "ambiguous-reason":
        checks["expected_pending_and_declines"] = (
            not declines
            and not second_result.receipts
            and same_mutation_state(second["before"], second["after"])
            and len(actual_pending) == 2
            and not actual_declined
        )
    return checks


def execute(out: Path, executor: Executor, bindings: dict[str, Any]) -> dict[str, Any]:
    """Run up to eight process attempts; a first-turn failure never creates a replacement session."""
    runs: list[dict[str, Any]] = []
    invocation_count = 0
    prepared: dict[str, dict[str, Any]] = {}
    for case in CASES:
        home = out / case / "store"
        home.mkdir(parents=True)
        prepared[case] = prepare_fixture(home, case, bindings)
    write_json_new(
        out / "preflight.json",
        {
            "kind": "native-rationale-preflight",
            "cases": prepared,
            "all_cases_prepared_before_first_prompt": True,
        },
    )
    for case, turns in CASES.items():
        home = out / case / "store"
        fixture = prepared[case]
        turn_records: list[dict[str, Any]] = []
        observed_session_id: str | None = None
        for turn_number, user_text in enumerate(turns, start=1):
            if invocation_count >= MAX_TURNS:
                raise AssertionError(f"native invocation ceiling exceeded: {invocation_count}>={MAX_TURNS}")
            before = store_snapshot(home)
            invocation_count += 1  # Count attempted launches, including failure/timeout/bad JSON.
            result = executor(
                case=case,
                user_text=user_text,
                home=home,
                resume_session_id=observed_session_id,
            )
            after = store_snapshot(home)
            turn = _record_turn(turn_number, user_text, before, after, result)
            write_json_new(out / case / f"turn-{turn_number:02d}.json", turn)
            turn_records.append(turn)
            if turn_number == 1:
                observed_session_id = result.session_id
                if not observed_session_id:
                    break
        run = {"case": case, "fixture": fixture, "turns": turn_records}
        if len(turn_records) == 1 and not observed_session_id:
            run["missing_second_turn"] = True
        run["checks"] = _validate_case(run, bindings)
        run["passed"] = all(run["checks"].values())
        write_json_new(out / case / "case-result.json", run)
        runs.append(run)
    return {
        "kind": "native-rationale-decline-capture",
        "invocation_count": invocation_count,
        "max_actual_cli_turns": MAX_TURNS,
        "runs": runs,
        "passed": all(run["passed"] for run in runs),
    }


def _require_live_opt_in(args: argparse.Namespace) -> None:
    if args.isolated_run or os.environ.get("NATIVE_RATIONALE_DECLINE_ISOLATED") == "1":
        return
    raise RuntimeError(
        "native execution needs --isolated-run or NATIVE_RATIONALE_DECLINE_ISOLATED=1"
    )


def main(
    argv: Sequence[str] | None = None,
    *,
    executor: Executor | None = None,
    bindings: dict[str, Any] | None = None,
) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--execute", action="store_true", help="run the bounded native CLI evaluation")
    parser.add_argument("--isolated-run", action="store_true", help="acknowledge the caller prepared an isolated DTU")
    parser.add_argument("--provider", help="configured provider passed to amplifier run -p")
    parser.add_argument("--model", help="configured model passed to amplifier run -m")
    parser.add_argument("--bundle", help="prepared memory bundle passed to amplifier run -B")
    parser.add_argument("--timeout", type=float, default=120.0, help="per CLI process timeout in seconds")
    parser.add_argument("--candidate-source", type=Path, help="candidate checkout supplying fixture APIs")
    args = parser.parse_args(argv)
    if args.timeout <= 0:
        raise ValueError("--timeout must be positive")
    if args.execute and os.environ.get("PYTEST_CURRENT_TEST") and executor is None:
        raise RuntimeError("refusing native execution under pytest without an injected executor")
    if not args.execute:
        args.out.mkdir(mode=0o700, parents=True, exist_ok=False)
        payload: dict[str, Any] = plan()
        payload["plan_sha256"] = hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()
        target = args.out / "manifest.json"
        target.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
        target.chmod(0o600)
        print(json.dumps({"dry_run": True, "cases": len(CASES), "max_turns": MAX_TURNS}))
        return 0

    if executor is None:
        _require_live_opt_in(args)
        required = {"--provider": args.provider, "--model": args.model, "--bundle": args.bundle}
        missing = [flag for flag, value in required.items() if not value]
        if missing:
            raise ValueError(f"native execution requires {' '.join(missing)}")
        if args.candidate_source is None:
            raise ValueError("native execution requires --candidate-source")
        active_bindings, runtime = candidate_bindings(args.candidate_source)
        active_executor: Executor = NativeCliExecutor(
            provider=args.provider, model=args.model, bundle=args.bundle, timeout=args.timeout
        )
    else:
        if not os.environ.get("PYTEST_CURRENT_TEST"):
            raise RuntimeError("injected executors are permitted only under pytest")
        if bindings is None:
            raise ValueError("injected executor tests need explicit bindings")
        active_bindings = bindings
        runtime = {"mode": "injected-test-bindings"}
        active_executor = executor
    args.out.mkdir(mode=0o700, parents=True, exist_ok=False)
    payload = execute(args.out, active_executor, active_bindings)
    payload["runtime"] = runtime
    target = args.out / "result.json"
    target.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    target.chmod(0o600)
    print(json.dumps({"executed": True, "invocations": payload["invocation_count"], "passed": payload["passed"]}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
