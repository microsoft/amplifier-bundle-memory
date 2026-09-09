"""Real-provider multi-turn checks for session.v5 conversational review addressing.

Each command creates a fresh synthetic store and writes results outside the
repository. A private OpenAI-compatible provider config with ``api_key`` and
``default_model`` is required; this harness makes no provider call under pytest.

Commands (run one case at a time):

    python evaluations/review-recovery/multi_turn.py --repo . --case numbered-batch --provider-config /private/provider.json --out /private/numbered
    python evaluations/review-recovery/multi_turn.py --repo . --case yes-map --provider-config /private/provider.json --out /private/yes
    python evaluations/review-recovery/multi_turn.py --repo . --case ambiguous --provider-config /private/provider.json --out /private/ambiguous
    python evaluations/review-recovery/multi_turn.py --repo . --case stale-id --provider-config /private/provider.json --out /private/stale
    python evaluations/review-recovery/multi_turn.py --repo . --case paged-nonconsecutive --provider-config /private/provider.json --out /private/paged
    python evaluations/review-recovery/multi_turn.py --repo . --case natural-text --provider-config /private/provider.json --out /private/text

The harness deliberately has no parser or positional backend API. It supplies
only a real rendered page and the actual skill, preserves that assistant page
in the provider transcript, and requires the provider to decide how to answer
the next human turn.
"""

from __future__ import annotations

import argparse
import asyncio
import base64
import dataclasses
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import time
from datetime import date
from pathlib import Path
from types import SimpleNamespace
from typing import Any

DISPLAYED_ITEM = re.compile(
    r"^\*\*(?P<number>\d+)\. (?P<id>s-\d{3})\*\* — (?P<text>.+)$", re.MULTILINE
)
FENCED_PAYLOAD = re.compile(
    r"\A[ \t\r\n]*```[^\r\n]*\r?\n(?P<payload>.*?)(?:\r?\n)?```[ \t\r\n]*\Z",
    re.DOTALL,
)


@dataclasses.dataclass(frozen=True)
class DisplayedReviewItem:
    """One position and stable id as the real renderer showed them."""

    number: int
    id: str
    text: str


@dataclasses.dataclass(frozen=True)
class ExpectedCall:
    """One complete expected tool call, including its terminal success state."""

    name: str
    arguments: dict[str, Any]
    success: bool


def parse_displayed_review_items(rendered_page: str) -> list[DisplayedReviewItem]:
    """Read the numbered stable ids from the library's actual markdown shape."""
    items = [
        DisplayedReviewItem(int(match["number"]), match["id"], match["text"])
        for match in DISPLAYED_ITEM.finditer(rendered_page)
    ]
    if not items:
        raise ValueError("The rendered review page has no numbered suggestion items")
    numbers = [item.number for item in items]
    if numbers != list(range(numbers[0], numbers[0] + len(items))):
        raise ValueError("The rendered review page has non-contiguous item numbers")
    if len({item.id for item in items}) != len(items):
        raise ValueError("The rendered review page repeats a stable suggestion id")
    return items


def expected_review_trace(page: int, actions: list[tuple[str, str, bool]]) -> list[ExpectedCall]:
    """The only permitted trace: skill, one rendered page, then frozen actions."""
    skill_args = "review" if page == 1 else f"review {page}"
    list_arguments = {"operation": "review", "action": "list"}
    if page != 1:
        list_arguments["page"] = page
    return [
        ExpectedCall("load_skill", {"skill_name": "memory", "arguments": skill_args}, True),
        ExpectedCall("memory", list_arguments, True),
        *[
            ExpectedCall(
                "memory", {"operation": "review", "action": action, "id": suggestion_id}, success
            )
            for action, suggestion_id, success in actions
        ],
    ]


def exact_tool_trace(calls: list[dict[str, Any]], expected: list[ExpectedCall]) -> bool:
    """Reject every call not in the complete, ordered canonical trace."""
    return len(calls) == len(expected) and all(
        call["name"] == wanted.name
        and call["arguments"] == wanted.arguments
        and call["success"] is wanted.success
        for call, wanted in zip(calls, expected, strict=True)
    )


def successful_receipts(calls: list[dict[str, Any]]) -> list[str]:
    """Return action receipts by canonical trace position, never by id membership."""
    return [
        call["output"]
        for call in calls[2:]
        if call["name"] == "memory"
        and call["arguments"].get("action") != "list"
        and call["success"]
    ]


def exact_fenced_receipts(final: str, receipts: list[str]) -> bool:
    """One fence may add only outer whitespace and an optional fence language."""
    if not receipts:
        return False
    match = FENCED_PAYLOAD.fullmatch(final)
    return match is not None and match["payload"] == "\n".join(receipts)


def exact_refusal_relay(final: str, refusal: str) -> bool:
    """A terminal refusal is bare or the sole payload of one receipt fence."""
    if final == refusal:
        return True
    match = FENCED_PAYLOAD.fullmatch(final)
    return match is not None and match["payload"] == refusal


def concise_clarification(final: str) -> bool:
    lowered = final.lower()
    return (
        bool(final.strip())
        and final.count("?") == 1
        and any(word in lowered for word in ("which", "clarify", "suggestion"))
        and len(final) <= 240
    )


def terminal_missing_id(final: str, calls: list[dict[str, Any]], expected_id: str) -> bool:
    """The expected unknown-id receipt is relayed without rewriting or continuation."""
    failed = [call for call in calls if not call["success"]]
    return (
        len(failed) == 1
        and expected_id in failed[0]["output"]
        and exact_refusal_relay(final, failed[0]["output"])
    )


def _git_messages(home: Path) -> list[str]:
    """Chronological commit messages are stable evidence; commit hashes are not."""
    raw = subprocess.check_output(
        ["git", "-C", str(home), "log", "--reverse", "--format=%B%x00"],
        text=True,
    )
    return [message for message in raw.split("\0") if message]


def store_proof(home: Path) -> dict[str, Any]:
    """All non-git bytes and semantic commit identities for an isolated test store."""
    files = {
        str(path.relative_to(home)): {
            "bytes": len(content := path.read_bytes()),
            "sha256": hashlib.sha256(content).hexdigest(),
        }
        for path in sorted(home.rglob("*"))
        if path.is_file() and ".git" not in path.relative_to(home).parts
    }
    protected = {
        name: base64.b64encode((home / name).read_bytes()).decode("ascii")
        for name in ("MEMORY.md", "inbox.md", "declined.md")
    }
    messages = _git_messages(home)
    return {
        "files": files,
        "protected_contents_b64": protected,
        "commit_count": len(messages),
        "commit_messages": messages,
    }


def grade_case(
    *,
    case: str,
    calls: list[dict[str, Any]],
    initial_page: str,
    rendered_page: str,
    final: str,
    before_second: dict[str, Any],
    after: dict[str, Any],
    oracle_after: dict[str, Any],
    expected: list[ExpectedCall],
) -> dict[str, bool]:
    """Deterministic terminal graders; model text is never treated as an assertion."""
    checks = {
        "actual_page_displayed": initial_page == rendered_page,
        "exact_tool_trace": exact_tool_trace(calls, expected),
        "expected_store_state": after == oracle_after,
    }
    if case in {"numbered-batch", "yes-map", "paged-nonconsecutive", "natural-text"}:
        checks["receipts_together"] = exact_fenced_receipts(final, successful_receipts(calls))
        checks["state_changed"] = before_second != after
    elif case == "ambiguous":
        checks["no_writes"] = before_second == after
        checks["one_clarification"] = concise_clarification(final)
    elif case == "stale-id":
        checks["no_substitute_target"] = terminal_missing_id(
            final, calls, expected[-1].arguments["id"]
        )
        checks["external_change_only"] = before_second == after
    else:
        raise ValueError(f"Unknown case {case!r}")
    return checks


def _case_reply(
    case: str, items: list[DisplayedReviewItem]
) -> tuple[str, list[tuple[str, str, bool]]]:
    assert len(items) >= 2, items
    if case == "numbered-batch":
        return (
            f"accept #{items[0].number}, decline #{items[1].number}",
            [("accept", items[0].id, True), ("decline", items[1].id, True)],
        )
    if case == "yes-map":
        return "yes", [("accept", items[0].id, True), ("decline", items[1].id, True)]
    if case == "ambiguous":
        return f"accept #{items[0].number}, decline that one", []
    if case == "stale-id":
        return (
            f"accept #{items[0].number}, decline #{items[1].number}",
            [("accept", items[0].id, False)],
        )
    if case == "paged-nonconsecutive":
        return (
            f"accept #{items[0].number}, decline #{items[1].number}",
            [("accept", items[0].id, True), ("decline", items[1].id, True)],
        )
    if case == "natural-text":
        return (
            f'accept the one that says "{items[0].text}"',
            [("accept", items[0].id, True)],
        )
    raise ValueError(case)


def _seed_sparse(inbox, home: Path, count: int) -> None:
    """Synthetic fixture setup only; renderer and mutations remain the real library."""
    items = [
        inbox.Suggestion(
            id=f"s-{(index + 1) * 101:03d}",
            text=f"Keep fictional review preference {index + 1} distinct.",
            quote=f"For future reference, keep fictional review preference {index + 1} distinct.",
            session=f"synthetic-{index + 1}",
            date="2026-09-09",
        )
        for index in range(count)
    ]
    (home / "inbox.md").write_text(
        "\n".join(item.render() for item in items) + "\n", encoding="utf-8"
    )
    subprocess.run(["git", "-C", str(home), "add", "inbox.md"], check=True)
    subprocess.run(
        [
            "git",
            "-C",
            str(home),
            "-c",
            "user.name=Review Fixture",
            "-c",
            "user.email=review-fixture@example.invalid",
            "commit",
            "-qm",
            "evaluation: sparse review fixture",
        ],
        check=True,
    )


def _apply_oracle(inbox, home: Path, actions: list[tuple[str, str, bool]]) -> None:
    """Apply only known successful stable-id actions to the isolated oracle store."""
    for action, suggestion_id, success in actions:
        if not success:
            continue
        if action == "accept":
            inbox.accept(suggestion_id, home, session_id="synthetic-natural-review")
        elif action == "decline":
            inbox.decline(suggestion_id, home)
        elif action == "skip":
            inbox.skip(suggestion_id, home)
        else:
            raise ValueError(f"Unknown oracle action {action!r}")


async def main(args: argparse.Namespace) -> int:
    case_started = time.monotonic()
    if args.total_deadline <= 0:
        raise ValueError("--total-deadline must be positive")
    repo = Path(args.repo).resolve()
    out = Path(args.out).resolve()
    if out == repo or repo in out.parents:
        raise ValueError("Keep evaluation output outside the source repository")
    out.mkdir(parents=True, exist_ok=False)
    sys.path[:0] = [str(repo / "src"), str(repo / "modules/tool-memory")]
    from amplifier_core import ChatRequest, Message, ToolSpec
    from amplifier_module_provider_openai import OpenAIProvider
    from amplifier_module_tool_memory import MemoryTool

    import amplifier_memory
    from amplifier_memory import inbox

    # Both stores must render an identical synthetic decline date even across midnight.
    original_today = inbox._today
    inbox._today = lambda now=None: date(2026, 9, 9)
    baseline = out / "baseline"
    home = out / "store"
    oracle = out / "oracle"
    os.environ.update(
        {
            "AMPLIFIER_MEMORY_HOME": str(home),
            "AMPLIFIER_PROJECTS_HOME": str(out / "projects"),
            "AMPLIFIER_SESSION_ORIGIN": "human",
        }
    )
    baseline.mkdir()
    await asyncio.to_thread(subprocess.run, ["git", "init", "-q", str(baseline)], check=True)
    amplifier_memory.init(baseline, timer=False)
    page_number = 2 if args.case == "paged-nonconsecutive" else 1
    _seed_sparse(inbox, baseline, 9 if page_number == 2 else 2)
    shutil.copytree(baseline, home)
    shutil.copytree(baseline, oracle)
    history: list[dict[str, str]] = []

    class Context:
        async def get_messages(self):
            return list(history)

    tool = MemoryTool(
        SimpleNamespace(
            session_id="synthetic-natural-review",
            parent_id=None,
            mount_points={"context": Context(), "tools": {}},
        ),
        {"home": str(home)},
    )
    skill = (repo / "skills" / "memory" / "SKILL.md").read_text(encoding="utf-8")
    calls: list[dict[str, Any]] = []
    messages = [
        Message(
            role="system",
            content="You are Amplifier. Carry out the user's command using available tools and loaded skills.",
        )
    ]
    specs = [
        ToolSpec(
            name="load_skill",
            description="Load a requested skill.",
            parameters={
                "type": "object",
                "properties": {"skill_name": {"type": "string"}, "arguments": {"type": "string"}},
                "required": ["skill_name", "arguments"],
            },
        ),
        ToolSpec(name="memory", description=tool.description, parameters=tool.input_schema),
    ]

    async def execute(name: str, arguments: dict[str, Any]) -> str:
        if name == "load_skill":
            success = arguments.get("skill_name") == "memory" and isinstance(
                arguments.get("arguments"), str
            )
            output = (
                json.dumps({"content": skill.replace("$ARGUMENTS", arguments["arguments"])})
                if success
                else "refused: only the memory skill is available"
            )
        elif name == "memory":
            result = await tool.execute(arguments)
            output, success = str(result.output), result.success
        else:
            output, success = f"refused: unexpected tool {name!r}", False
        calls.append({"name": name, "arguments": arguments, "success": success, "output": output})
        return output

    config = json.loads(Path(args.provider_config).read_text(encoding="utf-8"))
    api_key, model = config.pop("api_key"), config.pop("default_model")
    for key in ("id", "module", "source", "priority"):
        config.pop(key, None)
    config.update({"timeout": 90, "raw": False})
    provider = OpenAIProvider(
        api_key=api_key, coordinator=SimpleNamespace(get_capability=lambda _: None), **config
    )

    provider_calls: list[dict[str, Any]] = []
    turn_number = 0

    async def turn(user_text: str) -> str:
        nonlocal turn_number
        turn_number += 1
        history.append({"role": "user", "content": user_text})
        messages.append(Message(role="user", content=user_text))
        for attempt in range(1, 7):
            remaining = args.total_deadline - (time.monotonic() - case_started)
            if remaining <= 0:
                raise TimeoutError("Total case deadline exceeded before provider call")
            started = time.monotonic()
            try:
                response = await asyncio.wait_for(
                    provider.complete(
                        ChatRequest(
                            messages=messages,
                            tools=specs,
                            model=model,
                            max_output_tokens=4000,
                            stream=False,
                        )
                    ),
                    timeout=min(110, remaining),
                )
            finally:
                provider_calls.append(
                    {
                        "turn": turn_number,
                        "attempt": attempt,
                        "elapsed_s": round(time.monotonic() - started, 6),
                    }
                )
            if not response.tool_calls:
                final = "".join(block.text for block in response.content if block.type == "text")
                # Preserve the real assistant reply before receiving the next human turn.
                messages.append(Message(role="assistant", content=response.content))
                history.append({"role": "assistant", "content": final})
                return final
            messages.append(Message(role="assistant", content=response.content))
            for call in response.tool_calls:
                output = await execute(call.name, call.arguments)
                messages.append(Message(role="tool", tool_call_id=call.id, content=output))
        raise RuntimeError("Model exceeded six-response limit")

    baseline_proof = store_proof(baseline)
    before_second: dict[str, Any] = {}
    oracle_after: dict[str, Any] = {}
    after: dict[str, Any] = {}
    initial_page = ""
    rendered_page = ""
    expected: list[ExpectedCall] = []
    replay_metadata: dict[str, Any] = {}
    try:
        remaining_case = args.total_deadline - (time.monotonic() - case_started)
        if remaining_case <= 0:
            raise TimeoutError("Total case deadline exceeded during setup")
        async with asyncio.timeout(remaining_case):
            initial_page = await turn(
                f"/memory review{f' {page_number}' if page_number != 1 else ''}"
            )
            rendered_page = inbox.render_review_page(page_number, home)
            if initial_page != rendered_page:
                raise AssertionError("Initial response was not the actual rendered review page")
            displayed = parse_displayed_review_items(rendered_page)
            reply, expected_actions = _case_reply(args.case, displayed)
            expected = expected_review_trace(page_number, expected_actions)
            if args.case == "yes-map":
                replay = f"Accept {displayed[0].id}; decline {displayed[1].id}?"
                messages.append(Message(role="assistant", content=replay))
                history.append({"role": "assistant", "content": replay})
                replay_metadata = {"seeded_failure_boundary_replay": True}
            if args.case == "stale-id":
                inbox.decline(displayed[0].id, home)
                inbox.decline(displayed[0].id, oracle)
            before_second = store_proof(home)
            _apply_oracle(inbox, oracle, expected_actions)
            oracle_after = store_proof(oracle)
            final = await turn(reply)
            after = store_proof(home)
        checks = grade_case(
            case=args.case,
            calls=calls,
            initial_page=initial_page,
            rendered_page=rendered_page,
            final=final,
            before_second=before_second,
            after=after,
            oracle_after=oracle_after,
            expected=expected,
        )
        error = None
    except Exception as exc:  # noqa: BLE001
        final = ""
        after = store_proof(home)
        checks = {"completed": False}
        error = type(exc).__name__
    finally:
        inbox._today = original_today
    result = {
        "case": args.case,
        "total_deadline_s": args.total_deadline,
        "total_elapsed_s": round(time.monotonic() - case_started, 6),
        "checks": checks,
        "passed": all(checks.values()),
        "calls": calls,
        "provider_calls": provider_calls,
        "final": final,
        "state_proofs": {
            "baseline": baseline_proof,
            "before_second": before_second,
            "oracle_after": oracle_after,
            "actual_after": after,
        },
        "expected_trace": [dataclasses.asdict(call) for call in expected],
        "metadata": replay_metadata,
        "error": error,
    }
    (out / "result.json").write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(
        json.dumps(
            {"case": args.case, "passed": result["passed"], "checks": checks, "error": error}
        )
    )
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", required=True)
    parser.add_argument("--out", required=True)
    parser.add_argument("--provider-config", required=True)
    parser.add_argument("--total-deadline", type=float, default=240)
    parser.add_argument(
        "--case",
        required=True,
        choices=[
            "numbered-batch",
            "yes-map",
            "ambiguous",
            "stale-id",
            "paged-nonconsecutive",
            "natural-text",
        ],
    )
    raise SystemExit(asyncio.run(main(parser.parse_args())))
