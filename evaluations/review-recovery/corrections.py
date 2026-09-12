"""Bounded real-provider checks for natural memory corrections.

Each invocation uses a fresh synthetic store and writes every artifact outside
the repository. It makes no provider call under pytest.

    python evaluations/review-recovery/corrections.py --repo . --case existing \
      --provider-config /private/provider.json --out /private/correction-existing

Cases are independent: ``existing`` checks an existing-memory rewrite and a
fresh-session readback; ``pending`` checks revise-only followed by a corrected
acceptance; ``compound`` checks that a
successful write is relayed before a later edit refusal.
"""

from __future__ import annotations

import argparse
import asyncio
import base64
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import time
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from types import SimpleNamespace
from typing import Any

OLD = (
    "When updating a product catalog, list each record you plan to change and why."
)
CORRECTION = "Please remove the catalog-specific scope and apply this to any document."
PENDING_SOURCE_QUOTE = "For product catalog changes, name the records you expect to modify."
UNRELATED_MEMORIES = {
    "m-003": "Use ISO dates in logs.",
    "m-008": "Keep dependency changes focused.",
}
_TRACE_RESULT_TOKEN = object()


def fixture_memory(case: str) -> str:
    """Keep the correction target last; pending OLD is never already active."""
    lines = [f"- [{memory_id}] {text}\n" for memory_id, text in UNRELATED_MEMORIES.items()]
    if case != "pending":
        lines.append(f"- [m-014] {OLD}\n")
    return "".join(lines)


@dataclass(frozen=True)
class TraceCall:
    """One raw provider call and the ToolResult returned by the actual tool."""

    name: str
    arguments: dict[str, Any]
    result: Any
    _result_token: object | None = field(default=None, repr=False)

    @classmethod
    def from_tool_result(cls, name: str, arguments: dict[str, Any], result: Any) -> TraceCall:
        """Reject a harness-shaped result before it can become evaluation evidence."""
        try:
            from amplifier_core import ToolResult
        except ImportError as exc:
            raise TypeError("evaluation trace requires the MemoryTool's actual ToolResult") from exc
        if not isinstance(result, ToolResult):
            raise TypeError("evaluation trace requires the MemoryTool's actual ToolResult")
        return cls(name, arguments, result, _TRACE_RESULT_TOKEN)

    def as_json(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "arguments": self.arguments,
            "result_type": f"{type(self.result).__module__}.{type(self.result).__name__}",
            "success": self.result.success,
            "output": str(self.result.output),
        }


class SyntheticContext:
    """A standalone context for one synthetic coordinator, never a history closure."""

    def __init__(self, messages: list[dict[str, str]] | None = None):
        self._messages = list(messages or [])

    def append(self, message: dict[str, str]) -> None:
        self._messages.append(dict(message))

    async def get_messages(self) -> list[dict[str, str]]:
        return [dict(message) for message in self._messages]


def _fenced_payload(text: str) -> str | None:
    text = text.strip()
    if not (text.startswith("```") and text.endswith("```")):
        return None
    lines = text.splitlines()
    return "\n".join(lines[1:-1]) if len(lines) >= 2 else None


def _genuine(call: TraceCall) -> bool:
    return call._result_token is _TRACE_RESULT_TOKEN


def _is_call(call: TraceCall, operation: str, *, action: str | None = None) -> bool:
    return (
        _genuine(call)
        and call.name == "memory"
        and call.arguments.get("operation") == operation
        and (action is None or call.arguments.get("action") == action)
    )


def _exact_fenced_results(final: str, calls: list[TraceCall]) -> bool:
    return _fenced_payload(final) == "\n".join(str(call.result.output) for call in calls)


def _unchanged_unrelated(
    after_memory: bytes, unrelated_before: dict[str, bytes], expected_ids: set[str]
) -> bool:
    """Every pre-existing non-target line remains byte-identical and named."""
    after_lines = {
        line.split(b"] ", 1)[0][3:].decode(): line
        for line in after_memory.splitlines(keepends=True)
        if line.startswith(b"- [m-") and b"] " in line
    }
    return set(after_lines) == expected_ids and all(
        after_lines.get(memory_id) == line for memory_id, line in unrelated_before.items()
    )


def grade_existing_correction(
    *,
    calls: list[TraceCall],
    final: str,
    correction: str,
    old: str,
    after: dict[str, Any],
    fresh_readback: str,
    last_commit: str,
    after_memory: bytes,
    unrelated_before: dict[str, bytes],
) -> dict[str, bool]:
    """Require the natural correction's honest provenance and stable id."""
    exact_trace = (
        len(calls) == 2
        and _is_call(calls[0], "list")
        and calls[0].result.success
        and _is_call(calls[1], "edit")
    )
    edit = calls[1] if exact_trace else None
    replacement = str(edit.arguments.get("text", "")) if edit else ""
    return {
        "initial_list_then_one_edit_only": exact_trace,
        "genuine_tool_results": bool(calls) and all(_genuine(call) for call in calls),
        "one_successful_edit": bool(edit and edit.result.success),
        "stable_existing_id": bool(edit and edit.arguments.get("id") == "m-014"),
        "human_instruction_preserved": bool(edit and edit.arguments.get("quote") == correction),
        "derived_text_call_is_assistant_authored": bool(
            edit and edit.arguments.get("writer") == "assistant"
        ),
        "derived_text_is_assistant_authored": "\nwriter: assistant\n" in f"\n{last_commit}\n",
        "replacement_removes_specific_scope": bool(
            replacement and "catalog" not in replacement.lower() and "document" in replacement.lower()
        ),
        "replacement_persisted_at_stable_id": f"- [m-014] {replacement}\n" in after.get("MEMORY.md", ""),
        "old_text_gone": old not in after.get("MEMORY.md", ""),
        "one_stable_id_after": after.get("MEMORY.md", "").count("[m-014]") == 1,
        "unrelated_bytes_and_ids_unchanged": _unchanged_unrelated(
            after_memory, unrelated_before, set(UNRELATED_MEMORIES) | {"m-014"}
        ),
        "stored_provenance_is_actual_commit": (
            "\nwriter: assistant\n" in f"\n{last_commit}\n"
            and f"\nquote: {json.dumps(correction)}\n" in f"\n{last_commit}\n"
        ),
        "fresh_session_reads_replacement": replacement in fresh_readback and old not in fresh_readback,
        "edit_receipt_relayed": bool(edit and _fenced_payload(final) == str(edit.result.output)),
    }


def grade_pending_correction(
    *,
    calls: list[TraceCall],
    proposal: str,
    final: str,
    correction: str,
    before: dict[str, str],
    after_revise: dict[str, str],
    after: dict[str, str],
    before_bytes: dict[str, bytes],
    after_revise_bytes: dict[str, bytes],
    after_memory: bytes,
    calls_before_approval: int,
    before_commit_count: int,
    after_commit_count: int,
    last_commit: str,
    fresh_readback: str,
) -> dict[str, bool]:
    """The proposed rewrite stays inert until its later, exact approval succeeds."""
    exact_trace = (
        len(calls) == 2
        and _is_call(calls[0], "review", action="list")
        and calls[0].result.success
        and _is_call(calls[1], "review", action="accept")
        and calls[1].result.success
    )
    corrected = calls[1] if exact_trace else None
    replacement = str(corrected.arguments.get("text", "")) if corrected else ""
    source = str(corrected.arguments.get("id", "")) if corrected else ""
    receipt = str(corrected.result.output) if corrected else ""
    saved = re.search(rf"^corrected {re.escape(source)} → saved as (m-\d{{3,6}})$", receipt, re.MULTILINE)
    new_id = saved.group(1) if saved else ""
    source_pattern = re.compile(
        rf"^- \[{re.escape(source)}\] {re.escape(OLD)}\n"
        rf'  quote: "{re.escape(PENDING_SOURCE_QUOTE)}"  '
        r"session: synthetic-pending-correction  \d{4}-\d{2}-\d{2}\n?",
        re.MULTILINE,
    )
    source_match = source_pattern.search(before.get("inbox.md", ""))
    inbox_without_source = (
        before["inbox.md"][: source_match.start()] + before["inbox.md"][source_match.end() :]
        if source_match
        else ""
    )
    return {
        "initial_review_then_corrected_accept_only": exact_trace,
        "genuine_tool_results": bool(calls) and all(_genuine(call) for call in calls),
        "zero_correction_turn_calls_before_approval": calls_before_approval == 1,
        "revise_only_state_is_byte_and_head_unchanged": (
            after_revise == before and after_revise_bytes == before_bytes
        ),
        "revise_only_before_approval": (
            source in proposal
            and correction in proposal
            and "saved as" not in proposal.lower()
        ),
        "actual_human_correction_preserved": bool(
            corrected and corrected.arguments.get("quote") == correction
        ),
        "derived_text_is_not_human_verbatim": bool(
            replacement and replacement != correction and "catalog" not in replacement.lower()
        ),
        "source_removed_and_original_never_active": (
            source
            and source_match is not None
            and after.get("inbox.md", "") == inbox_without_source
            and OLD not in after.get("MEMORY.md", "")
            and replacement in after.get("MEMORY.md", "")
        ),
        "one_new_memory_id_matches_displayed_replacement": (
            bool(new_id)
            and after.get("MEMORY.md", "").endswith(f"- [{new_id}] {replacement}\n")
            and _unchanged_unrelated(
                after_memory, {memory_id: f"- [{memory_id}] {text}\n".encode() for memory_id, text in UNRELATED_MEMORIES.items()},
                set(UNRELATED_MEMORIES) | {new_id},
            )
        ),
        "one_commit_only": after_commit_count == before_commit_count + 1,
        "stored_provenance_is_actual_commit": (
            f"\nquote: {json.dumps(correction)}\n" in f"\n{last_commit}\n"
            and "\nwriter: assistant\n" in f"\n{last_commit}\n"
            and "\naction: corrected-accept\n" in f"\n{last_commit}\n"
            and "\nsession: synthetic-natural-correction\n" in f"\n{last_commit}\n"
            and f"\nsource-suggestion-id: {source}\n" in f"\n{last_commit}\n"
            and f"\nsource-suggestion-quote: {json.dumps(PENDING_SOURCE_QUOTE)}\n"
            in f"\n{last_commit}\n"
            and "\nsource-suggestion-session: synthetic-pending-correction\n" in f"\n{last_commit}\n"
        ),
        "fresh_session_reads_corrected_state": replacement in fresh_readback and OLD not in fresh_readback,
        "corrected_receipt_relayed": bool(corrected and _fenced_payload(final) == str(corrected.result.output)),
    }


def grade_compound_outcome(
    *,
    calls: list[TraceCall],
    final: str,
    before: dict[str, Any],
    after: dict[str, Any],
    after_memory: bytes,
    unrelated_before: dict[str, bytes],
) -> dict[str, bool]:
    """A later refusal cannot erase an earlier real receipt from the reply."""
    save, edit = (calls + [None, None])[:2]
    saved_text = str(save.arguments.get("text", "")) if save else ""
    return {
        "exact_two_call_sequence": bool(
            len(calls) == 2 and _is_call(calls[0], "save") and _is_call(calls[1], "edit")
        ),
        "genuine_tool_results": bool(calls) and all(_genuine(call) for call in calls),
        "headings_save_succeeded": bool(
            save
            and _is_call(save, "save")
            and save.result.success
            and "heading" in saved_text.lower()
        ),
        "later_m014_edit_refused": bool(
            edit
            and _is_call(edit, "edit")
            and not edit.result.success
            and edit.arguments.get("id") == "m-014"
        ),
        "prior_saved_text_persisted": saved_text in after.get("MEMORY.md", ""),
        "failed_edit_left_old_m014": OLD in after.get("MEMORY.md", ""),
        "unrelated_bytes_and_ids_unchanged": _unchanged_unrelated(
            after_memory, unrelated_before, set(UNRELATED_MEMORIES) | {"m-014"} | {"m-015"}
        ),
        "prior_write_changed_store": before != after,
        "ordered_receipts_and_refusal_relayed": _exact_fenced_results(final, calls),
        "not_a_blanket_refusal": final.strip().lower() not in {"nothing changed", "not saved"},
    }


def _state(home: Path) -> dict[str, str]:
    state = {
        name: (home / name).read_text(encoding="utf-8")
        for name in ("MEMORY.md", "inbox.md", "declined.md")
        if (home / name).exists()
    }
    state["HEAD"] = subprocess.check_output(
        ["git", "-C", str(home), "rev-parse", "HEAD"], text=True
    ).strip()
    return state


def _bytes_state(home: Path) -> dict[str, bytes]:
    """The exact mutable evaluation files, for pre-approval no-write proof."""
    return {
        name: (home / name).read_bytes()
        for name in ("MEMORY.md", "inbox.md", "declined.md")
        if (home / name).exists()
    }


def _commit_count(home: Path) -> int:
    return int(
        subprocess.check_output(["git", "-C", str(home), "rev-list", "--count", "HEAD"], text=True).strip()
    )


def _copy_state(home: Path, target: Path) -> None:
    target.mkdir()
    for name in ("MEMORY.md", "inbox.md", "declined.md"):
        source = home / name
        if source.exists():
            shutil.copy2(source, target / name)


def _git_metadata(repo: Path, home: Path) -> dict[str, str]:
    def output(*argv: str, cwd: Path) -> str:
        return subprocess.check_output(argv, cwd=cwd, text=True).strip()

    return {
        "source_commit": output("git", "rev-parse", "HEAD", cwd=repo),
        "source_status": output("git", "status", "--short", cwd=repo),
        "store_head": output("git", "rev-parse", "HEAD", cwd=home),
        "store_log": output("git", "log", "--reverse", "--format=%B%x00", cwd=home),
    }


async def main(args: argparse.Namespace) -> int:
    started = time.monotonic()
    if args.total_deadline <= 0:
        raise ValueError("--total-deadline must be positive")
    repo, out = Path(args.repo).resolve(), Path(args.out).resolve()
    if out == repo or repo in out.parents:
        raise ValueError("Keep evaluation output outside the source repository")
    out.mkdir(parents=True, exist_ok=False)
    sys.path[:0] = [str(repo / "src"), str(repo / "modules/tool-memory")]

    import amplifier_module_tool_memory as tool_module
    from amplifier_core import ChatRequest, Message, ToolSpec
    from amplifier_module_provider_openai import OpenAIProvider
    from amplifier_module_tool_memory import MemoryTool

    import amplifier_memory
    from amplifier_memory import inbox

    home = out / "store"
    home.mkdir()
    tool_module.error_log_path = lambda: out / "memory-errors.log"
    os.environ.update(
        {
            "AMPLIFIER_MEMORY_HOME": str(home),
            "AMPLIFIER_PROJECTS_HOME": str(out / "projects"),
            "AMPLIFIER_SESSION_ORIGIN": "human",
        }
    )
    await asyncio.to_thread(subprocess.run, ["git", "init", "-q", str(home)], check=True)
    amplifier_memory.init(home, timer=False)
    (home / "MEMORY.md").write_text(fixture_memory(args.case), encoding="utf-8")
    await asyncio.to_thread(subprocess.run, ["git", "-C", str(home), "add", "MEMORY.md"], check=True)
    await asyncio.to_thread(
        subprocess.run,
        [
            "git",
            "-C",
            str(home),
            "-c",
            "user.name=Correction Fixture",
            "-c",
            "user.email=correction-fixture@example.invalid",
            "commit",
            "-qm",
            "evaluation: existing correction fixture",
        ],
        check=True,
    )
    if args.case == "pending":
        amplifier_memory.record_session(home, "synthetic-pending-correction", "human")
        inbox.append(
            home,
            [
                inbox.Candidate(
                    text=OLD,
                    quote=PENDING_SOURCE_QUOTE,
                    session="synthetic-pending-correction",
                    date=datetime.now(UTC).date().isoformat(),
                )
            ],
        )
    _copy_state(home, out / "before")
    before = _state(home)
    before_bytes = _bytes_state(home)
    before_commit_count = _commit_count(home)
    skill = (repo / "skills/memory/SKILL.md").read_text(encoding="utf-8")
    context = SyntheticContext()

    tool = MemoryTool(
        SimpleNamespace(
            session_id="synthetic-natural-correction",
            parent_id=None,
            mount_points={"context": context, "tools": {}},
        ),
        {"home": str(home)},
    )
    calls: list[TraceCall] = []
    turns: list[dict[str, Any]] = []
    completion_count = 0
    usage: list[Any] = []
    messages = [
        Message(
            role="system",
            content=(
                "You are Amplifier. Follow the loaded memory skill exactly. "
                "Relay tool results exactly as the skill says.\n\n" + skill
            ),
        )
    ]
    spec = ToolSpec(name="memory", description=tool.description, parameters=tool.input_schema)
    config = json.loads(Path(args.provider_config).read_text(encoding="utf-8"))
    api_key, model = config.pop("api_key"), config.pop("default_model")
    provider_instance = str(config.get("id") or config.get("instance") or "OpenAIProvider")
    for key in ("id", "module", "source", "priority"):
        config.pop(key, None)
    config.update({"timeout": 90, "raw": False})
    provider = OpenAIProvider(api_key=api_key, config=config, coordinator=SimpleNamespace(get_capability=lambda _: None))

    async def turn(user_text: str) -> str:
        nonlocal completion_count
        calls_before_turn, completions_before_turn = len(calls), completion_count
        context.append({"role": "user", "content": user_text})
        messages.append(Message(role="user", content=user_text))
        for _ in range(6):
            remaining = args.total_deadline - (time.monotonic() - started)
            if remaining <= 0:
                raise TimeoutError("Total case deadline exceeded")
            response = await asyncio.wait_for(
                provider.complete(
                    ChatRequest(messages=messages, tools=[spec], model=model, max_output_tokens=4000, stream=False)
                ),
                timeout=min(110, remaining),
            )
            completion_count += 1
            response_usage = getattr(response, "usage", None)
            if response_usage is not None:
                usage.append(
                    response_usage.model_dump()
                    if hasattr(response_usage, "model_dump")
                    else dict(response_usage)
                    if isinstance(response_usage, dict)
                    else str(response_usage)
                )
            messages.append(Message(role="assistant", content=response.content))
            if not response.tool_calls:
                final_text = "".join(block.text for block in response.content if block.type == "text")
                turns.append(
                    {
                        "user": user_text,
                        "calls_before": calls_before_turn,
                        "calls_after": len(calls),
                        "completions": completion_count - completions_before_turn,
                    }
                )
                return final_text
            for call in response.tool_calls:
                if call.name != "memory":
                    raise AssertionError(f"unexpected tool {call.name!r}")
                result = await tool.execute(call.arguments)
                record = TraceCall.from_tool_result(call.name, dict(call.arguments), result)
                calls.append(record)
                messages.append(Message(role="tool", tool_call_id=call.id, content=str(result.output)))
        raise RuntimeError("Model exceeded six-response limit")

    final = ""
    initial = ""
    proposal = ""
    fresh_readback = ""
    after_revise = dict(before)
    after_revise_bytes = dict(before_bytes)
    calls_before_approval = 0
    original_edit = amplifier_memory.edit
    unrelated_before = {
        memory_id: f"- [{memory_id}] {text}\n".encode()
        for memory_id, text in UNRELATED_MEMORIES.items()
    }
    try:
        if args.case == "existing":
            initial = await turn("/memory list")
            final = await turn(CORRECTION)
            fresh = MemoryTool(
                SimpleNamespace(
                    session_id="synthetic-fresh-reader",
                    parent_id=None,
                    mount_points={"context": SyntheticContext(), "tools": {}},
                ),
                {"home": str(home)},
            )
            fresh_readback = (await fresh.execute({"operation": "list"})).output
        elif args.case == "pending":
            initial = await turn("/memory review")
            proposal = await turn(
                "Please remove the catalog-specific scope and apply it to any document."
            )
            # This is deliberately between the revise-only turn and its later approval:
            # a post-approval snapshot cannot prove that the proposal itself did not write.
            after_revise = _state(home)
            after_revise_bytes = _bytes_state(home)
            calls_before_approval = len(calls)
            final = await turn("do it")
            fresh = MemoryTool(
                SimpleNamespace(
                    session_id="synthetic-fresh-reader",
                    parent_id=None,
                    mount_points={"context": SyntheticContext(), "tools": {}},
                ),
                {"home": str(home)},
            )
            fresh_readback = (await fresh.execute({"operation": "list"})).output
        else:
            def injected_failure(memory_id, *rest, **kwargs):
                if memory_id == "m-014":
                    raise amplifier_memory.WriteNotLanded("injected evaluation edit failure")
                return original_edit(memory_id, *rest, **kwargs)

            amplifier_memory.edit = injected_failure
            final = await turn(
                "Remember that responses need headings. Please revise m-014 to remove the catalog-specific scope."
            )
        error = None
    except Exception as exc:  # noqa: BLE001 - the result records a bounded failed run
        checks, error = {"completed": False}, type(exc).__name__
    finally:
        amplifier_memory.edit = original_edit
    after = _state(home)
    after_commit_count = _commit_count(home)
    last_commit = await asyncio.to_thread(
        subprocess.check_output,
        ["git", "-C", str(home), "log", "-1", "--format=%B"],
        text=True,
    )
    after_memory = (home / "MEMORY.md").read_bytes()
    if error is None and args.case == "existing":
        checks = grade_existing_correction(
            calls=calls,
            final=final,
            correction=CORRECTION,
            old=OLD,
            after=after,
            fresh_readback=fresh_readback,
            last_commit=last_commit,
            after_memory=after_memory,
            unrelated_before=unrelated_before,
        )
    elif error is None and args.case == "pending":
        checks = grade_pending_correction(
            calls=calls,
            proposal=proposal,
            final=final,
            correction=(
                "Please remove the catalog-specific scope and apply it to any document."
            ),
            before=before,
            after_revise=after_revise,
            after=after,
            before_bytes=before_bytes,
            after_revise_bytes=after_revise_bytes,
            after_memory=after_memory,
            calls_before_approval=calls_before_approval,
            before_commit_count=before_commit_count,
            after_commit_count=after_commit_count,
            last_commit=last_commit,
            fresh_readback=fresh_readback,
        )
    elif error is None:
        checks = grade_compound_outcome(
            calls=calls,
            final=final,
            before=before,
            after=after,
            after_memory=after_memory,
            unrelated_before=unrelated_before,
        )
    _copy_state(home, out / "after")
    trace = {
        "initial": initial,
        "proposal": proposal,
        "final": final,
        "turns": turns,
        "calls": [call.as_json() for call in calls],
        "fresh_readback": fresh_readback,
    }
    (out / "trace.json").write_text(json.dumps(trace, indent=2) + "\n", encoding="utf-8")
    passed = all(checks.values())
    outcome = (
        "corrected"
        if args.case == "existing" and passed
        else "safely_refused_pending_correction"
        if args.case == "pending" and passed
        else "compound_receipts_relayed"
        if args.case == "compound" and passed
        else "failed"
    )
    result = {
        "case": args.case,
        "outcome": outcome,
        "correction_succeeded": args.case == "existing" and passed,
        "source": str(repo),
        "tool_sha256": hashlib.sha256(
            (repo / "modules/tool-memory/amplifier_module_tool_memory/__init__.py").read_bytes()
        ).hexdigest(),
        "skill_sha256": hashlib.sha256(skill.encode()).hexdigest(),
        "checks": checks,
        "passed": passed,
        "error": error,
        "elapsed_s": round(time.monotonic() - started, 6),
        "provider": {"instance": provider_instance, "model": model},
        "completion_count": completion_count,
        "usage": usage or None,
        "integration_scope": "synthetic MemoryTool/coordinator only; not native CLI/fork integration",
        "last_store_commit": last_commit,
        "before_b64": {name: base64.b64encode(value.encode()).decode() for name, value in before.items()},
        "after_b64": {name: base64.b64encode(value.encode()).decode() for name, value in after.items()},
        "preapproval": {
            "state": after_revise,
            "files_b64": {
                name: base64.b64encode(value).decode() for name, value in after_revise_bytes.items()
            },
            "calls_before_approval": calls_before_approval,
        },
        "git": _git_metadata(repo, home),
    }
    (out / "result.json").write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(
        json.dumps(
            {"case": args.case, "outcome": outcome, "passed": passed, "checks": checks, "error": error}
        )
    )
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", required=True)
    parser.add_argument("--out", required=True)
    parser.add_argument("--provider-config", required=True)
    parser.add_argument("--total-deadline", type=float, default=240)
    parser.add_argument("--case", choices=("existing", "pending", "compound"), required=True)
    raise SystemExit(asyncio.run(main(parser.parse_args())))