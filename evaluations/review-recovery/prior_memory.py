"""Recorded-trace checks for conversational prior-memory management.

``record_conversation`` is provider-free. A scripted responder receives the
literal skill and prior rendered replies, and reaches the real ``MemoryTool``
only through the callback supplied by the recorder. Model provenance
(``scripted``) is distinct from actual tool evidence.
"""

from __future__ import annotations

import json
import re
import subprocess
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

MEMORY_LINE = re.compile(rb"^- \[(m-\d{3,})\] .*\n?", re.MULTILINE)
_RECORDED = object()
_ACTUAL = object()


@dataclass(frozen=True)
class Snapshot:
    """Complete fixture bytes and ordered git evidence at one boundary."""

    files: dict[str, bytes]
    head: str
    history: tuple[str, ...]
    changed_paths: tuple[str, ...] = ()

    def complete(self) -> bool:
        return bool(self.files) and bool(self.head) and bool(self.history)


def _git(root: Path, *arguments: str) -> str:
    return subprocess.check_output(["git", "-C", str(root), *arguments], text=True)


def capture_snapshot(store_root: Path) -> Snapshot:
    """Capture every fixture file (outside .git), HEAD, full history and paths."""
    files = {
        path.relative_to(store_root).as_posix(): path.read_bytes()
        for path in sorted(store_root.rglob("*"))
        if path.is_file() and ".git" not in path.relative_to(store_root).parts
    }
    head = _git(store_root, "rev-parse", "HEAD").strip()
    history = tuple(
        item.strip("\n")
        for item in _git(store_root, "log", "--reverse", "--format=%H%x1f%P%x1f%B%x1e").split("\x1e")
        if item.strip()
    )
    changed_paths = tuple(
        line
        for line in _git(store_root, "diff-tree", "--no-commit-id", "--name-only", "-r", head).splitlines()
        if line
    )
    return Snapshot(files, head, history, changed_paths)


@dataclass(frozen=True)
class TraceCall:
    """One callback invocation with snapshots immediately before and after."""

    name: str
    arguments: dict[str, Any]
    result: Any
    before: Snapshot | None = None
    after: Snapshot | None = None
    session_id: str | None = None
    evidence: str = "synthetic"
    _token: object | None = field(default=None, repr=False)

    @classmethod
    def from_tool_result(
        cls, name: str, arguments: dict[str, Any], result: Any,
        before: Snapshot | None = None, after: Snapshot | None = None, session_id: str | None = None,
    ) -> TraceCall:
        try:
            from amplifier_core import ToolResult
        except ImportError as exc:
            raise TypeError("runtime evidence requires MemoryTool's actual ToolResult") from exc
        if not isinstance(result, ToolResult):
            raise TypeError("runtime evidence requires MemoryTool's actual ToolResult")
        return cls(name, dict(arguments), result, before, after, session_id, "actual", _ACTUAL)


def scripted_call(
    arguments: dict[str, Any], *, success: bool = True, output: str = "receipt", name: str = "memory",
    before: Snapshot | None = None, after: Snapshot | None = None,
) -> TraceCall:
    """Synthetic negative-test control; never runtime evidence."""
    result = type("ScriptedToolResult", (), {"success": success, "output": output})()
    return TraceCall(name, dict(arguments), result, before, after)


@dataclass(frozen=True)
class Turn:
    role: str
    text: str
    snapshot: Snapshot
    calls: tuple[TraceCall, ...] = ()


@dataclass(frozen=True)
class ConversationTrace:
    turns: tuple[Turn, ...]
    model_source: str
    tool_evidence: str
    _token: object | None = field(default=None, repr=False)

    @classmethod
    def recorded(cls, turns: list[Turn], *, model_source: str) -> ConversationTrace:
        return cls(tuple(turns), model_source, "actual", _RECORDED)


def scripted_trace(turns: list[Turn]) -> ConversationTrace:
    return ConversationTrace(tuple(turns), "synthetic", "synthetic")


@dataclass(frozen=True)
class ExpectedCall:
    name: str
    arguments: dict[str, Any]
    success: bool


@dataclass(frozen=True)
class CaseExpectation:
    """Scenario facts, never caller-provided states or self-attested booleans."""

    calls: tuple[ExpectedCall, ...]
    user_turns: tuple[str, ...]
    topic_path: str | None = None
    topic_body: str | None = None
    topic_position: int | None = None
    preview: tuple[str, str, str, tuple[str, ...]] | None = None
    approved: bool = True
    final_text: str | None = None


async def record_conversation(
    *,
    user_turns: list[str],
    responder: Callable[[list[dict[str, str]], Callable[[str, dict[str, Any]], Awaitable[Any]]], Awaitable[str]],
    memory_tool: Any,
    skill_text: str,
    store_root: Path,
    read_file: Callable[[dict[str, Any]], Awaitable[Any]] | None = None,
    model_source: str = "scripted",
) -> ConversationTrace:
    """Run and record a bounded scripted conversation with real tool results."""
    context = memory_tool.coordinator.mount_points["context"]
    turns: list[Turn] = []
    history: list[dict[str, str]] = [{"role": "system", "content": skill_text}]
    for user_text in user_turns:
        context.append({"role": "user", "content": user_text})
        before_response = capture_snapshot(store_root)
        turns.append(Turn("user", user_text, before_response))
        history.append({"role": "user", "content": user_text})
        calls: list[TraceCall] = []

        async def execute(name: str, arguments: dict[str, Any], _calls: list[TraceCall] = calls) -> Any:
            before = capture_snapshot(store_root)
            if name == "memory":
                result = await memory_tool.execute(dict(arguments))
            elif name == "read_file" and read_file is not None:
                result = await read_file(dict(arguments))
            else:
                raise ValueError(f"unexpected tool {name!r}")
            after = capture_snapshot(store_root)
            _calls.append(
                TraceCall.from_tool_result(
                    name, arguments, result, before, after, getattr(memory_tool.coordinator, "session_id", None)
                )
            )
            return result

        response = await responder([dict(message) for message in history], execute)
        if not isinstance(response, str):
            raise TypeError("responder must return verbatim text")
        context.append({"role": "assistant", "content": response})
        response_snapshot = capture_snapshot(store_root)
        turns.append(Turn("assistant", response, response_snapshot, tuple(calls)))
        history.append({"role": "assistant", "content": response})
    return ConversationTrace.recorded(turns, model_source=model_source)


def _replace_line(files: dict[str, bytes], memory_id: str, text: str | None) -> tuple[dict[str, bytes], str] | None:
    matches = [
        (path, match)
        for path, body in files.items()
        for match in MEMORY_LINE.finditer(body)
        if match.group(1).decode() == memory_id
    ]
    if len(matches) != 1:
        return None
    path, match = matches[0]
    body = files[path]
    changed = dict(files)
    replacement = b"" if text is None else f"- [{memory_id}] {text}\n".encode()
    changed[path] = body[:match.start()] + replacement + body[match.end():]
    return changed, path


def _commit(entry: str) -> tuple[str, str, str] | None:
    parts = entry.split("\x1f", 2)
    return (parts[0], parts[1], parts[2]) if len(parts) == 3 else None


def _valid_recorded_trace(trace: ConversationTrace) -> bool:
    if trace._token is not _RECORDED or trace.tool_evidence != "actual" or not trace.turns or len(trace.turns) % 2:
        return False
    previous: Snapshot | None = None
    failed = False
    for index in range(0, len(trace.turns), 2):
        user, assistant = trace.turns[index : index + 2]
        if user.role != "user" or assistant.role != "assistant" or not user.snapshot.complete():
            return False
        if previous is not None and user.snapshot != previous:
            return False
        state = user.snapshot
        for call in assistant.calls:
            try:
                from amplifier_core import ToolResult
            except ImportError:
                return False
            if (
                call.evidence != "actual" or call._token is not _ACTUAL or call.before != state
                or call.before is None or call.after is None or not call.before.complete()
                or not call.after.complete() or failed or call.name not in {"memory", "read_file"}
                or not isinstance(call.result, ToolResult)
            ):
                return False
            if call.name == "read_file" and set(call.arguments) != {"file_path"}:
                return False
            if (
                (call.name == "read_file" or call.arguments.get("operation") == "list")
                and str(call.result.output) not in assistant.text
            ):
                return False
            if not call.result.success and call.after != call.before:
                return False
            failed = failed or not call.result.success
            state = call.after
        if assistant.snapshot != state:
            return False
        previous = assistant.snapshot
    return True


def _valid_transition(call: TraceCall) -> bool:
    if call.before is None or call.after is None:
        return False
    operation = call.arguments.get("operation")
    if call.name == "read_file" or operation in {"list", "overview", "cite"}:
        return call.after == call.before
    if operation not in {"edit", "forget"} or not call.result.success:
        return call.after == call.before
    memory_id = call.arguments.get("id")
    if not isinstance(memory_id, str):
        return False
    changed = _replace_line(
        call.before.files, memory_id,
        str(call.arguments["text"]) if operation == "edit" and "text" in call.arguments else None,
    )
    if changed is None:
        return False
    expected_files, path = changed
    if call.after.files != expected_files or call.after.history[:-1] != call.before.history:
        return False
    if len(call.after.history) != len(call.before.history) + 1 or call.after.changed_paths != (path,):
        return False
    commit = _commit(call.after.history[-1])
    if commit is None:
        return False
    sha, parents, body = commit
    if call.after.head != sha or parents != call.before.head or memory_id not in body:
        return False
    if operation == "edit":
        quote = call.arguments.get("quote")
        session = call.session_id
        old_line = next(
            (
                line.decode().rstrip("\n")
                for source in call.before.files.values()
                for line in source.splitlines(keepends=True)
                if line.startswith(f"- [{memory_id}] ".encode())
            ),
            "",
        )
        old_text = old_line.split("] ", 1)[1] if "] " in old_line else ""
        return bool(
            call.arguments.get("writer") == "assistant" and isinstance(quote, str)
            and f"quote: {json.dumps(quote)}" in body and "writer: assistant" in body
            and f"session: {session}" in body and "action: edit" in body
            and f"was: {json.dumps(old_text)}" in body
            and f"[{memory_id}] {call.arguments.get('text')}" in body
        )
    return "action: forget" in body


def _preview_text(preview: tuple[str, str, str, tuple[str, ...]]) -> str:
    survivor, replacement, correction, duplicates = preview
    return "\n".join((survivor, replacement, correction, *duplicates))


def _topic_sequence(trace: ConversationTrace, expected: CaseExpectation) -> bool:
    """Bind this three-step case to the selected pointer, read, display and edit."""
    if len(trace.turns) != 6 or expected.topic_body is None:
        return False
    listed, opened, mutated = trace.turns[1::2]
    if not all(len(turn.calls) == 1 for turn in (listed, opened, mutated)):
        return False
    listing, read, mutation = (turn.calls[0] for turn in (listed, opened, mutated))
    if listing.name != "memory" or listing.arguments.get("operation") != "list":
        return False
    pointers = re.findall(
        r"^- \*\*m-\d{3,}\*\* .+ → (topics/[a-z0-9][a-z0-9._-]*\.md)$",
        listed.text, re.MULTILINE,
    )
    instance = re.search(r"^edit by hand: \$EDITOR (.+)/MEMORY\.md$", listed.text, re.MULTILINE)
    position = expected.topic_position
    if instance is None or position is None or not 1 <= position <= len(pointers):
        return False
    selected_path = str(Path(instance.group(1)) / pointers[position - 1])
    target = mutation.arguments.get("id")
    return bool(
        listed.text == str(listing.result.output)
        and selected_path == expected.topic_path
        and read.name == "read_file"
        and read.arguments == {"file_path": selected_path}
        and read.result.success
        and opened.text == str(read.result.output) == expected.topic_body
        and mutation.name == "memory"
        and mutation.arguments.get("operation") in {"edit", "forget"}
        and isinstance(target, str)
        and re.search(rf"^- \[{re.escape(target)}\] ", opened.text, re.MULTILINE)
    )


def grade_trace(trace: ConversationTrace, expectation: CaseExpectation) -> dict[str, bool]:
    """Grade all turns/calls and derive every claimed state directly from trace."""
    structural = _valid_recorded_trace(trace)
    calls = [call for turn in trace.turns for call in turn.calls]
    exact_turns = tuple(turn.text for turn in trace.turns if turn.role == "user") == expectation.user_turns
    exact_calls = structural and exact_turns and len(calls) == len(expectation.calls) and all(
        call.name == wanted.name and call.arguments == wanted.arguments
        and bool(call.result.success) is wanted.success
        for call, wanted in zip(calls, expectation.calls, strict=True)
    )
    boundaries = structural and all(_valid_transition(call) for call in calls)
    final_turn = trace.turns[-1] if trace.turns else None
    final = final_turn.text if final_turn else ""
    final_exact = bool(
        final_turn
        and final
        == (
            expectation.final_text
            if expectation.final_text is not None
            else "```\n" + "\n".join(str(call.result.output) for call in final_turn.calls) + "\n```"
        )
    )
    topic_ok = True
    if expectation.topic_path is not None:
        topic_ok = structural and _topic_sequence(trace, expectation)
    preview_ok = True
    if expectation.preview is not None:
        shown = [turn for turn in trace.turns if turn.role == "assistant" and _preview_text(expectation.preview) in turn.text]
        preview_ok = bool(
            len(shown) == 1 and not shown[0].calls
            and shown[0].snapshot == trace.turns[trace.turns.index(shown[0]) - 1].snapshot
        )
        if preview_ok:
            index = trace.turns.index(shown[0])
            following = trace.turns[index + 1 : index + 3]
            preview_ok = (
                len(following) == 2
                and following[0].role == "user"
                and following[0].text.strip().lower() in {"yes", "do it"}
                and following[1].role == "assistant"
                and bool(following[1].calls)
            ) if expectation.approved else not any(
                call.arguments.get("operation") in {"edit", "forget"} for call in calls[index:]
            )
    return {
        "recorded_scripted_model_and_actual_tool_evidence": structural and trace.model_source == "scripted",
        "whole_trace_has_exact_expected_calls": exact_calls,
        "every_boundary_has_complete_exact_state_and_git_evidence": boundaries,
        "topic_read_is_the_selected_recorded_call_and_is_displayed": topic_ok,
        "preview_is_inert_exact_map_before_immediate_approval": preview_ok,
        "final_text_is_actual_receipts_and_refusal_in_one_fence": final_exact,
    }