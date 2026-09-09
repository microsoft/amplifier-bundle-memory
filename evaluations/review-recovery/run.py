"""Real-provider, real-tool review tests; malformed cases replay a failure boundary.

Run each case in its own process, inside an isolated test environment with
amplifier-core, amplifier-module-provider-openai, and this repository installed.
Supply a private OpenAI-compatible JSON provider configuration with api_key
and default_model. Raw results belong outside the repo.

Example:
  python evaluations/review-recovery/run.py --repo . --case recovery \
    --provider-config /private/provider.json --out /private/results/recovery

Cases: normal, recovery, disabled, user-missing-id.
Use --items 17 --page 2 to check paged recovery.

The harness loads the shipped skill and executes the real MemoryTool. Recovery
replays an assistant's malformed call and its real refusal before invoking the
model. This does not test the CLI slash parser or natural error frequency.
"""

import argparse
import asyncio
import hashlib
import json
import os
import subprocess
import sys
import traceback
from datetime import UTC, datetime
from pathlib import Path
from types import SimpleNamespace


def fingerprint(home):
    files = {
        str(p.relative_to(home)): hashlib.sha256(p.read_bytes()).hexdigest()
        for p in sorted(home.rglob("*"))
        if p.is_file() and ".git" not in p.relative_to(home).parts
    }
    head = subprocess.check_output(["git", "-C", str(home), "rev-parse", "HEAD"], text=True).strip()
    return {"files": files, "head": head}


def no_calls_after_first_failure(calls):
    first = next((i for i, call in enumerate(calls) if not call["success"]), None)
    return first is not None and first == len(calls) - 1


async def main(args):
    repo = Path(args.repo).resolve()
    sys.path[:0] = [str(repo / "src"), str(repo / "modules/tool-memory")]
    from amplifier_core import ChatRequest, Message, ToolCallBlock, ToolSpec
    from amplifier_module_provider_openai import OpenAIProvider
    from amplifier_module_tool_memory import MemoryTool

    import amplifier_memory
    from amplifier_memory import inbox

    out = Path(args.out).resolve()
    if out == repo or repo in out.parents:
        raise ValueError("Keep evaluation output outside the source repository")
    out.mkdir(parents=True, exist_ok=False)
    home = out / "store"
    os.environ["AMPLIFIER_MEMORY_HOME"] = str(home)
    os.environ["AMPLIFIER_PROJECTS_HOME"] = str(out / "projects")
    os.environ["AMPLIFIER_CONTEXT_INTELLIGENCE_BASE_PATH"] = str(out / "capture")
    os.environ["AMPLIFIER_SESSION_ORIGIN"] = "human"
    home.mkdir()
    await asyncio.to_thread(subprocess.run, ["git", "init", "-q", str(home)], check=True)
    amplifier_memory.init(home, timer=False)
    inbox.append(
        home,
        [
            inbox.Candidate(
                text=f"Use whole crates for fictional inventory example {i}.",
                quote=(
                    f"For future reference, use whole crates for fictional inventory example {i}."
                ),
                session=f"synthetic-review-{i}",
                date=datetime.now(UTC).date().isoformat(),
            )
            for i in range(1, args.items + 1)
        ],
    )
    if args.case == "disabled":
        (home / "config.yaml").write_text("enabled: false\n")
    expected = inbox.render_review_page(args.page, home) if args.case != "disabled" else None
    user = f"/memory review{f' {args.page}' if args.page != 1 else ''}"
    if args.case == "user-missing-id":
        user = "/memory review skip"

    class Context:
        async def get_messages(self):
            return [{"role": "user", "content": user}]

    coordinator = SimpleNamespace(
        session_id="synthetic-review-probe",
        parent_id=None,
        mount_points={"tools": {}, "context": Context()},
    )
    tool = MemoryTool(coordinator, {"home": str(home)})
    skill = (repo / "skills/memory/SKILL.md").read_text()
    skill_args = user.removeprefix("/memory ").strip()
    loaded_skill = skill.replace("$ARGUMENTS", skill_args)
    specs = [
        ToolSpec(
            name="load_skill",
            description=(
                "Load the memory skill when the user invokes /memory. "
                "Pass the rest of the command as arguments."
            ),
            parameters={
                "type": "object",
                "properties": {
                    "skill_name": {"type": "string", "enum": ["memory"]},
                    "arguments": {"type": "string"},
                },
                "required": ["skill_name", "arguments"],
            },
        ),
        ToolSpec(name="memory", description=tool.description, parameters=tool.input_schema),
    ]
    messages = [
        Message(
            role="system",
            content=(
                "You are Amplifier. Carry out the user's command using "
                "the available tools and loaded skill."
            ),
        ),
        Message(role="user", content=user),
    ]
    before = fingerprint(home)
    calls = []
    terminal_result = None

    async def execute(name, arguments, seeded=False):
        nonlocal terminal_result
        if name == "load_skill":
            if arguments.get("skill_name") != "memory":
                raise AssertionError("Unexpected skill")
            if arguments.get("arguments") != skill_args:
                raise AssertionError("Skill arguments did not match the user's command")
            output = json.dumps({"content": loaded_skill, "skill_name": "memory"})
            success = True
        elif name == "memory":
            result = await tool.execute(arguments)
            output, success = result.output, result.success
            if not success:
                terminal_result = str(output)
        else:
            raise AssertionError("Unexpected tool")
        calls.append(
            {
                "name": name,
                "arguments": arguments,
                "seeded": seeded,
                "success": success,
                "output": output,
            }
        )
        return str(output)

    def assistant_call(name, arguments, call_id):
        return Message(
            role="assistant",
            content=[ToolCallBlock(type="tool_call", id=call_id, name=name, input=arguments)],
        )

    if args.case in ("recovery", "user-missing-id"):
        # Replay the recorded boundary with actual skill text and the real refusal.
        # No extra user message changes the original intent.
        for name, arguments, call_id in [
            ("load_skill", {"skill_name": "memory", "arguments": skill_args}, "call_seed_skill"),
            (
                "memory",
                {"operation": "review", "action": "skip", "id": "", "page": args.page},
                "call_seed_bad",
            ),
        ]:
            messages.append(assistant_call(name, arguments, call_id))
            output = await execute(name, arguments, seeded=True)
            messages.append(Message(role="tool", tool_call_id=call_id, content=output))
        assert calls[-1]["success"] is False and "needs the suggestion id" in calls[-1]["output"]
        assert fingerprint(home) == before

    config = json.loads(Path(args.provider_config).read_text())
    model = config["default_model"]
    credential = config.pop("api_key")
    for key in ("id", "module", "source", "priority"):
        config.pop(key, None)
    config["timeout"] = 90
    config["raw"] = False
    provider_coordinator = SimpleNamespace(get_capability=lambda name: None)
    provider = OpenAIProvider(api_key=credential, config=config, coordinator=provider_coordinator)
    final = ""
    usage = []
    error = None
    error_frames = []
    try:
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
            if response.usage:
                usage.append(response.usage.model_dump(mode="json"))
            tool_calls = response.tool_calls or []
            if not tool_calls:
                final = "".join(b.text for b in response.content if b.type == "text")
                break
            # Preserve the real provider's reasoning blocks across tool calls.
            messages.append(Message(role="assistant", content=response.content))
            for call in tool_calls:
                output = await execute(call.name, call.arguments)
                messages.append(Message(role="tool", tool_call_id=call.id, content=output))
        else:
            error = "Model exceeded the six-response limit"
    except Exception as exc:  # noqa: BLE001 — record failure without credential-bearing messages
        error = type(exc).__name__
        error_frames = [
            {"file": Path(f.filename).name, "line": f.lineno, "function": f.name}
            for f in traceback.extract_tb(exc.__traceback__)
        ]
    after = fingerprint(home)
    real_calls = [c for c in calls if not c["seeded"]]
    real_memory = [c for c in real_calls if c["name"] == "memory"]
    checks = {"store_unchanged": before == after, "completed": error is None and bool(final)}
    if args.case in ("normal", "recovery"):
        checks.update(
            {
                "one_safe_listing": len(real_memory) == 1
                and real_memory[0]["arguments"].get("operation") == "review"
                and real_memory[0]["arguments"].get("action") == "list"
                and real_memory[0]["arguments"].get("page", 1) == args.page
                and real_memory[0]["success"],
                "page_verbatim": final.strip() == expected.strip(),
            }
        )
        if args.case == "normal":
            checks["skill_loaded"] = bool(real_calls) and real_calls[0]["name"] == "load_skill"
        else:
            checks["only_one_retry"] = len(real_calls) == 1
    elif args.case == "disabled":
        checks["one_refusal"] = len(real_memory) == 1 and not real_memory[0]["success"]
        checks["no_post_refusal_calls"] = no_calls_after_first_failure(real_calls)
        checks["refusal_relay"] = (
            bool(terminal_result) and final.strip().strip("`").strip() == terminal_result.strip()
        )
    elif args.case == "user-missing-id":
        checks["no_retry"] = not real_calls
        checks["refusal_relay"] = (
            bool(terminal_result) and final.strip().strip("`").strip() == terminal_result.strip()
        )
    tool_source = Path(sys.modules["amplifier_module_tool_memory"].__file__)
    result = {
        "case": args.case,
        "page": args.page,
        "model": model,
        "scope": (
            "real-provider/tool integration; failure-boundary replay for seeded cases, "
            "not CLI slash-parser validation"
        ),
        "source": str(repo),
        "tool_source_sha256": hashlib.sha256(tool_source.read_bytes()).hexdigest(),
        "skill_sha256": hashlib.sha256(skill.encode()).hexdigest(),
        "checks": checks,
        "passed": all(checks.values()),
        "calls": calls,
        "final": final,
        "before": before,
        "after": after,
        "usage": usage,
        "error": error,
        "error_frames": error_frames,
    }
    (out / "result.json").write_text(json.dumps(result, indent=2) + "\n")
    print(
        json.dumps(
            {
                "case": args.case,
                "page": args.page,
                "passed": result["passed"],
                "checks": checks,
                "error": error,
            }
        )
    )
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", required=True)
    parser.add_argument("--out", required=True)
    parser.add_argument("--provider-config", required=True)
    parser.add_argument(
        "--case", choices=["normal", "recovery", "disabled", "user-missing-id"], required=True
    )
    parser.add_argument("--items", type=int, default=2)
    parser.add_argument("--page", type=int, default=1)
    raise SystemExit(asyncio.run(main(parser.parse_args())))
