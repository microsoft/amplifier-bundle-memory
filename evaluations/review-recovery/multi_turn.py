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

The harness deliberately has no parser, positional backend API, or persistent
conversation state. It supplies only a real rendered page and the actual skill;
the provider must decide how to answer the next human turn.
"""

from __future__ import annotations

import argparse
import asyncio
import importlib.util
import json
import os
import re
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path
from types import SimpleNamespace
from typing import Any

PAGE_IDS = re.compile(r"\*\*(s-\d{3})\*\*")


def fingerprint(home: Path) -> dict[str, Any]:
    """Use the legacy harness's common store-fingerprint implementation."""
    source = Path(__file__).with_name("run.py")
    spec = importlib.util.spec_from_file_location("review_recovery_legacy", source)
    assert spec and spec.loader
    legacy = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(legacy)
    return legacy.fingerprint(home)


def memory_calls(calls: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [call for call in calls if call["name"] == "memory" and not call.get("seeded")]


def actual_skill_loaded(calls: list[dict[str, Any]]) -> bool:
    return (
        bool(calls)
        and calls[0]["name"] == "load_skill"
        and calls[0]["arguments"].get("skill_name") == "memory"
        and calls[0]["arguments"].get("arguments") in {"review", "review 2"}
    )


def action_trace(calls: list[dict[str, Any]]) -> list[tuple[str, str]]:
    return [
        (call["arguments"].get("action", "list"), call["arguments"].get("id", ""))
        for call in memory_calls(calls)
        if call["arguments"].get("action", "list") != "list"
    ]


def exact_actions(calls: list[dict[str, Any]], expected: list[tuple[str, str]]) -> bool:
    """True only for the expected action sequence: no extra, reordered, or duplicate writes."""
    return action_trace(calls) == expected


def exact_review_trace(calls: list[dict[str, Any]], expected: list[tuple[str, str]]) -> bool:
    """The initial real listing plus exactly the requested stable-id calls."""
    trace = [
        (call["arguments"].get("action", "list"), call["arguments"].get("id", ""))
        for call in memory_calls(calls)
    ]
    return trace == [("list", ""), *expected]


def no_relist_after_mutation(calls: list[dict[str, Any]]) -> bool:
    trace = [
        (call["arguments"].get("action", "list"), call["arguments"].get("id", ""))
        for call in memory_calls(calls)
    ]
    first_mutation = next(
        (index for index, (action, _) in enumerate(trace) if action != "list"), None
    )
    return first_mutation is None or all(
        action != "list" for action, _ in trace[first_mutation + 1 :]
    )


def receipts_together(
    final: str, calls: list[dict[str, Any]], expected: list[tuple[str, str]]
) -> bool:
    receipts = [
        call["output"]
        for call in memory_calls(calls)
        if (call["arguments"].get("action"), call["arguments"].get("id")) in expected
        and call["success"]
    ]
    if not receipts:
        return False
    positions = [final.find(receipt) for receipt in receipts]
    return (
        all(position >= 0 for position in positions)
        and positions == sorted(positions)
        and final.count("```") == 2
        and "confirm" not in final.lower()
    )


def concise_clarification(final: str) -> bool:
    lowered = final.lower()
    return (
        bool(final.strip())
        and "?" in final
        and any(word in lowered for word in ("which", "clarify", "suggestion"))
    )


def terminal_missing_id(final: str, calls: list[dict[str, Any]], expected_id: str) -> bool:
    actions = action_trace(calls)
    failed = [call for call in memory_calls(calls) if not call["success"]]
    return (
        actions == [("accept", expected_id)]
        and len(failed) == 1
        and expected_id in failed[0]["output"]
        and failed[0]["output"].strip() in final
    )


def no_calls_after_failure(calls: list[dict[str, Any]]) -> bool:
    first_failure = next((index for index, call in enumerate(calls) if not call["success"]), None)
    return first_failure is not None and first_failure == len(calls) - 1


def grade_case(
    *,
    case: str,
    calls: list[dict[str, Any]],
    initial_page: str,
    rendered_page: str,
    final: str,
    before_second: dict[str, Any],
    after: dict[str, Any],
    expected: list[tuple[str, str]],
) -> dict[str, bool]:
    """Deterministic terminal graders; model text is never treated as an assertion."""
    initial = memory_calls(calls)
    checks = {
        "actual_skill_loaded": actual_skill_loaded(calls),
        "actual_page_displayed": bool(initial)
        and initial[0]["arguments"].get("action", "list") == "list"
        and initial[0]["success"]
        and initial_page.strip() == rendered_page.strip(),
        "exact_review_trace": exact_review_trace(calls, expected),
        "no_relist_after_mutation": no_relist_after_mutation(calls),
    }
    if case in {"numbered-batch", "yes-map", "paged-nonconsecutive", "natural-text"}:
        checks["receipts_together"] = receipts_together(final, calls, expected)
        checks["store_changed_only_for_actions"] = before_second != after
        checks["expected_actions_succeeded"] = all(
            call["success"]
            for call in memory_calls(calls)
            if (call["arguments"].get("action"), call["arguments"].get("id")) in expected
        )
    elif case == "ambiguous":
        checks["no_writes"] = before_second == after and not action_trace(calls)
        checks["one_clarification"] = concise_clarification(final)
    elif case == "stale-id":
        checks["no_substitute_target"] = terminal_missing_id(final, calls, expected[0][1])
        checks["no_post_failure_calls"] = no_calls_after_failure(calls)
        checks["external_change_only"] = before_second == after
    else:
        raise ValueError(f"Unknown case {case!r}")
    return checks


def _case_reply(case: str, page_ids: list[str], page: str) -> tuple[str, list[tuple[str, str]]]:
    assert len(page_ids) >= 2, page_ids
    if case == "numbered-batch":
        return "accept #1, decline #2", [("accept", page_ids[0]), ("decline", page_ids[1])]
    if case == "yes-map":
        return "yes", [("accept", page_ids[0]), ("decline", page_ids[1])]
    if case == "ambiguous":
        return "accept that one", []
    if case == "stale-id":
        return "accept #1", [("accept", page_ids[0])]
    if case == "paged-nonconsecutive":
        return "accept #1, decline #2", [("accept", page_ids[0]), ("decline", page_ids[1])]
    if case == "natural-text":
        text = re.search(r"\*\*s-\d{3}\*\* (.+)", page)
        assert text, page
        return f'accept the one that says "{text.group(1)}"', [("accept", page_ids[0])]
    raise ValueError(case)


def _seed_sparse(inbox, home: Path, count: int) -> None:
    """Synthetic fixture setup only; renderer and mutations remain the real library."""
    items = [
        inbox.Suggestion(
            id=f"s-{(index + 1) * 101:03d}",
            text=f"Keep fictional review preference {index + 1} distinct.",
            quote=f"For future reference, keep fictional review preference {index + 1} distinct.",
            session=f"synthetic-{index + 1}",
            date=datetime.now(UTC).date().isoformat(),
        )
        for index in range(count)
    ]
    (home / "inbox.md").write_text(
        "\n".join(item.render() for item in items) + "\n", encoding="utf-8"
    )
    subprocess.run(["git", "-C", str(home), "add", "inbox.md"], check=True)
    subprocess.run(
        ["git", "-C", str(home), "commit", "-qm", "evaluation: sparse review fixture"], check=True
    )


async def main(args: argparse.Namespace) -> int:
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

    home = out / "store"
    os.environ.update(
        {
            "AMPLIFIER_MEMORY_HOME": str(home),
            "AMPLIFIER_PROJECTS_HOME": str(out / "projects"),
            "AMPLIFIER_SESSION_ORIGIN": "human",
        }
    )
    home.mkdir()
    await asyncio.to_thread(subprocess.run, ["git", "init", "-q", str(home)], check=True)
    amplifier_memory.init(home, timer=False)
    page_number = 2 if args.case == "paged-nonconsecutive" else 1
    _seed_sparse(inbox, home, 9 if page_number == 2 else 2)
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
            assert arguments.get("skill_name") == "memory"
            output, success = (
                json.dumps({"content": skill.replace("$ARGUMENTS", arguments["arguments"])}),
                True,
            )
        elif name == "memory":
            result = await tool.execute(arguments)
            output, success = str(result.output), result.success
        else:
            raise AssertionError(f"Unexpected tool {name}")
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

    async def turn(user_text: str) -> str:
        history.append({"role": "user", "content": user_text})
        messages.append(Message(role="user", content=user_text))
        for _ in range(6):
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
                timeout=110,
            )
            if not response.tool_calls:
                return "".join(block.text for block in response.content if block.type == "text")
            messages.append(Message(role="assistant", content=response.content))
            for call in response.tool_calls:
                output = await execute(call.name, call.arguments)
                messages.append(Message(role="tool", tool_call_id=call.id, content=output))
        raise RuntimeError("Model exceeded six-response limit")

    try:
        initial_page = await turn(f"/memory review{f' {page_number}' if page_number != 1 else ''}")
        rendered_page = inbox.render_review_page(page_number, home)
        if initial_page.strip() != rendered_page.strip():
            raise AssertionError("Initial response was not the actual rendered review page")
        page_ids = PAGE_IDS.findall(rendered_page)
        reply, expected = _case_reply(args.case, page_ids, rendered_page)
        if args.case == "yes-map":
            replay = (
                "Replay only: complete reviewed map is accept "
                + page_ids[0]
                + ", then decline "
                + page_ids[1]
                + "."
            )
            messages.append(Message(role="assistant", content=replay))
        if args.case == "stale-id":
            inbox.decline(page_ids[0], home)
        before_second = fingerprint(home)
        final = await turn(reply)
        after = fingerprint(home)
        checks = grade_case(
            case=args.case,
            calls=calls,
            initial_page=initial_page,
            rendered_page=rendered_page,
            final=final,
            before_second=before_second,
            after=after,
            expected=expected,
        )
        error = None
    except Exception as exc:  # noqa: BLE001
        final, after, checks, error = (
            "",
            fingerprint(home),
            {"completed": False},
            type(exc).__name__,
        )
    result = {
        "case": args.case,
        "checks": checks,
        "passed": all(checks.values()),
        "calls": calls,
        "final": final,
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
