#!/usr/bin/env python3
"""Print every receipt and every refusal the memory tool can produce.

    cd modules/tool-memory && uv run --offline python ../../conformance/session/tool/receipts.py

Every sentence this bundle renders about memory, shown rather than described —
session.v5 §3, §5, §6 and §8. It asserts nothing; `run.py` is the kit that
judges. It builds a throwaway store under a temp dir and never touches the real
one.
"""

from __future__ import annotations

import asyncio
import os
import sys
import tempfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT / "modules" / "tool-memory"))


class FakeContext:
    def __init__(self, messages: list[dict]) -> None:
        self.messages = messages

    async def get_messages(self) -> list[dict]:
        return list(self.messages)


class FakeCoordinator:
    def __init__(self, messages=None, parent_id=None, session_id="receipts-demo") -> None:
        self.session_id = session_id
        self.parent_id = parent_id
        self.mount_points: dict = {"tools": {}}
        if messages is not None:
            self.mount_points["context"] = FakeContext(messages)

    async def mount(self, mount_point, module, name=None):  # pragma: no cover - unused here
        self.mount_points.setdefault(mount_point, {})[name] = module


def user(text: str) -> dict:
    return {"role": "user", "content": text}


def heading(title: str) -> None:
    print(f"\n--- {title} " + "-" * max(0, 68 - len(title)))


async def main() -> int:
    import amplifier_module_tool_memory as mod

    import amplifier_memory

    with tempfile.TemporaryDirectory() as raw:
        tmp = Path(raw)
        home = tmp / "store"
        os.environ["AMPLIFIER_MEMORY_HOME"] = str(home)
        os.environ["AMPLIFIER_PROJECTS_HOME"] = str(tmp / "projects")
        os.environ["AMPLIFIER_MEMORY_ERROR_LOG"] = str(tmp / "memory-errors.log")
        amplifier_memory.init(home)

        said = "For future reference: never use tabs in YAML files you write for me."
        approval = "Great, remember these for me"
        tool = mod.MemoryTool(FakeCoordinator([user(said), user(approval)]), {})

        heading("save, writer=human (/remember)")
        # `/remember <text>` saves exactly what was typed: the quote IS the text.
        result = await tool.execute({"operation": "save", "text": said, "writer": "human"})
        print(result.output)

        heading("save, writer=assistant — a batch of three drafted lines")
        # §3: `batch_of` is the model's own count of the lines it drafted. The
        # first two results are their own three-line receipt; the LAST one
        # carries the set.
        for text in (
            "Lead with the next action.",
            "Number multi-step work.",
            "Cap lists at five items.",
        ):
            result = await tool.execute(
                {
                    "operation": "save",
                    "text": text,
                    "quote": approval,
                    "writer": "assistant",
                    "batch_of": 3,
                }
            )
            print(result.output)
            print()

        heading("edit — the id survives, the receipt shows what it was")
        print(
            (
                await tool.execute(
                    {
                        "operation": "edit",
                        "id": "m-002",
                        "text": "Number multi-step work, one bounded action per step.",
                        "quote": approval,
                        "writer": "assistant",
                    }
                )
            ).output
        )

        heading("cite — no receipt at all; the citation was made in the prose")
        cited = await tool.execute({"operation": "cite", "id": "m-002"})
        print(f"success={cited.success} output={cited.output!r}")
        print("usage.jsonl:")
        print((home / "usage.jsonl").read_text(encoding="utf-8"), end="")

        heading("list — /memory list")
        print((await tool.execute({"operation": "list"})).output)

        heading("overview — the bare /memory, with an empty inbox")
        print((await tool.execute({"operation": "overview"})).output)

        heading("overview — the bare /memory, with 34 suggestions waiting")
        (home / "inbox.md").write_text(
            "".join(
                f"- [s-{n:03d}] preference number {n}\n"
                f'  quote: "say it {n}"  session: bc214bdf  2026-09-05\n'
                for n in range(1, 35)
            ),
            encoding="utf-8",
        )
        print((await tool.execute({"operation": "overview"})).output)
        (home / "inbox.md").write_text("", encoding="utf-8")

        heading("review \u2014 page 1 of 17 waiting (\u00a76 as amended 2026-09-07)")
        # A real inbox, appended through the library's own `append`: this is the page
        # a human reads, rendered by the library and relayed bare (never fenced).
        amplifier_memory.inbox.append(
            home,
            [
                amplifier_memory.inbox.Candidate(
                    text=f"Preference {n:02d}: one standing line the daily pass proposed.",
                    quote=(
                        f"for future reference, preference {n:02d}: always do it this way, "
                        "in every session on this device, not just in this one"
                    ),
                    session="d9c3bf04",
                    date="2026-09-07",
                )
                for n in range(1, 18)
            ],
        )
        print((await tool.execute({"operation": "review"})).output)
        print()
        heading("review \u2014 the last page, which offers no `next`")
        print((await tool.execute({"operation": "review", "page": 3})).output)
        print()
        heading("review \u2014 a page past the last one, and a bare number")
        print((await tool.execute({"operation": "review", "page": 4})).output)
        print((await tool.execute({"operation": "review", "action": "accept", "id": "2"})).output)
        (home / "inbox.md").write_text("", encoding="utf-8")

        heading("forget")
        print((await tool.execute({"operation": "forget", "id": "m-003"})).output)

        heading("list, after the forget")
        print((await tool.execute({"operation": "list"})).output)

        heading("save into a topic file, then the one pointer line")
        for text in ("Use two-space indent.", "Never a tab character."):
            result = await tool.execute(
                {
                    "operation": "save",
                    "text": text,
                    "quote": said,
                    "topic": "yaml-style",
                    "topic_purpose": "How to write YAML for me.",
                }
            )
            print(result.output)
            print()
        print(
            (
                await tool.execute(
                    {
                        "operation": "save",
                        "text": "YAML style conventions → topics/yaml-style.md",
                        "quote": said,
                    }
                )
            ).output
        )
        print()
        print("MEMORY.md:")
        print((home / "MEMORY.md").read_text(encoding="utf-8"), end="")
        print("topics/yaml-style.md:")
        print((home / "topics" / "yaml-style.md").read_text(encoding="utf-8"), end="")

        heading("refusal — duplicate")
        print(
            (
                await tool.execute(
                    {
                        "operation": "save",
                        "text": "Cap lists at five items.",
                        "quote": approval,
                    }
                )
            ).output
        )

        heading("refusal — unknown id (forgotten)")
        print((await tool.execute({"operation": "forget", "id": "m-003"})).output)

        heading("refusal — edit of an unknown id")
        print(
            (
                await tool.execute(
                    {
                        "operation": "edit",
                        "id": "m-003",
                        "text": "Something else.",
                        "quote": approval,
                    }
                )
            ).output
        )

        heading("refusal — cite of an unknown id")
        print((await tool.execute({"operation": "cite", "id": "m-404"})).output)

        heading("refusal — unknown id (never issued)")
        print((await tool.execute({"operation": "forget", "id": "m-404"})).output)

        heading("refusal — no human words")
        poison = mod.MemoryTool(FakeCoordinator([user("do step 1")]), {})
        print(
            (
                await poison.execute(
                    {
                        "operation": "save",
                        "text": "Never run the tests twice.",
                        "quote": "never run the tests twice",
                    }
                )
            ).output
        )

        heading("refusal — the cap")
        lines = [f"- [m-{n:03d}] filler {n}" for n in range(1, 201)]
        (home / "MEMORY.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
        print(
            (await tool.execute({"operation": "save", "text": "One more.", "quote": said})).output
        )

        heading("refusal — any other failure (and the line it logs)")
        real_save = amplifier_memory.save

        def explode(*args, **kwargs):
            raise amplifier_memory.GitFailed("commit failed: could not lock ref")

        amplifier_memory.save = explode
        try:
            print((await tool.execute({"operation": "save", "text": "x", "quote": said})).output)
        finally:
            amplifier_memory.save = real_save
        print(
            "error log:",
            Path(os.environ["AMPLIFIER_MEMORY_ERROR_LOG"]).read_text(encoding="utf-8").strip(),
        )

    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
