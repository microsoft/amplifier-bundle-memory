"""tool-memory — the `memory` tool: save · forget · list.

Serves `contracts/session.v1.md` (FROZEN 2026-09-06):

- §3  Save on correction, in the same turn — the tool description tells the
      model when to call `save`; the *calling* is model behaviour.
- §4  Do not save — the same description tells the model when not to.
- §5  The model proposes; the writer commits — this module proposes; the
      writer is `amplifier_memory.save`, which owns the human-turn check,
      the duplicate check, the id, the caps, the write and the commit.
- §6  The three commands — `/remember`, `/forget`, `/memory` are skills that
      call this tool; `save`, `forget` and `list` are the operations behind them.
- R2  Sub-agent sessions never save — refused here, before any library call,
      because only this process knows whether it is a root session.

AGENTS.md rule 11: this file carries no behaviour. It resolves the session's
human turns (which only a session can see), enforces R2 (which only a session
can know), and relays refusals in one line. Everything else is a call into
`amplifier_memory`. It never shells out to `amplifier-memory` (cli.v1 §9).
"""

from __future__ import annotations

import asyncio
import inspect
import json
import logging
import os
from pathlib import Path
from typing import Any

import amplifier_memory
from amplifier_core import ToolResult

logger = logging.getLogger(__name__)

# Amplifier module metadata
__amplifier_module_type__ = "tool"

__version__ = "0.1.0"

TOOL_NAME = "memory"

#: Phase 1 accepts two writers. `suggestion` is store.v1's third writer and
#: belongs to the (DRAFT) suggestions.v1 contract — refused here by name so a
#: caller learns what happened instead of getting a library ValueError.
ALLOWED_WRITERS = ("assistant", "human")

#: session.v1 §3, verbatim. The conformance kit re-extracts this from the
#: locked contract and compares it, so the two cannot drift apart silently.
ANNOUNCE_SAVE = 'Saved memory {id}: "{text}" — /forget {id} to undo.'
ANNOUNCE_FORGET = "Forgot {id}."

# 12 lines. §3 (when to save) and §4 (when not to) both stated, and the §3
# announce format quoted so the model has nothing to invent.
DESCRIPTION = """Record a standing preference the human just stated, in the same turn.
SAVE when the human says "never X", "always Y", "stop doing Z", "for future reference…" —
anything meant to hold beyond the current task. `text` is one imperative line; `quote` is
the human's own words, verbatim, copied from their message.
DO NOT SAVE task-scoped instructions ("do step 1", "reply with exactly ok"), facts
re-derivable from the code or the current task, anything already in MEMORY.md or
AGENTS.md, or anything the human asked to keep private.
Then announce it in one line, exactly: Saved memory m-017: "<text>" — /forget m-017 to undo.
operation=save {text, quote} · operation=forget {id} · operation=list
Only the human's own words become memory: a quote that appears in no human turn of this
session is refused, and a sub-agent session may not save at all. A refusal comes back as
one line — relay it to the human as it stands, and carry on."""

INPUT_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "operation": {
            "type": "string",
            "enum": ["save", "forget", "list"],
            "description": "save a memory · forget one by id · list MEMORY.md",
        },
        "text": {
            "type": "string",
            "description": "save: the memory, one imperative line",
        },
        "quote": {
            "type": "string",
            "description": "save: the human's verbatim words from their own message",
        },
        "writer": {
            "type": "string",
            "enum": list(ALLOWED_WRITERS),
            "description": "save: 'assistant' (default) or 'human' (a /remember command)",
        },
        "id": {"type": "string", "description": "forget: the memory id, e.g. m-017"},
    },
    "required": ["operation"],
}

MODULE_INFO: dict[str, Any] = {
    "name": "tool-memory",
    "version": __version__,
    "provides": ["session.v1#3", "session.v1#4", "session.v1#5", "session.v1#6", "session.v1#R2"],
}


# --------------------------------------------------------------------- helpers


def one_line(message: str) -> str:
    """Collapse a refusal to a single line. A traceback is never a tool result."""
    return " ".join(str(message).split())


def flatten_content(content: Any) -> str:
    """A message's text, whether `content` is a string or a list of blocks.

    Providers differ: `content` is a plain string in some, a list of typed
    blocks in others. Only text blocks can carry a human's words.
    """
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts: list[str] = []
        for block in content:
            if isinstance(block, str):
                parts.append(block)
            elif isinstance(block, dict):
                text = block.get("text")
                if isinstance(text, str):
                    parts.append(text)
            else:
                text = getattr(block, "text", None)
                if isinstance(text, str):
                    parts.append(text)
        return "\n".join(parts)
    return ""


def project_slug(cwd: Path | None = None) -> str:
    """The CLI's session-directory slug rule, re-implemented, not guessed.

    Verified against the installed CLI:
    `amplifier_app_cli/project_utils.py:22-30` (`get_project_slug`) — absolute
    cwd, `/` `\\` → `-`, `:` dropped, leading `-` guaranteed. Re-implemented
    rather than imported: a session module must not depend on the app package.
    """
    path = (cwd or Path.cwd()).resolve()
    slug = str(path).replace("/", "-").replace("\\", "-").replace(":", "")
    return slug if slug.startswith("-") else "-" + slug


def transcript_candidates(session_id: str) -> list[Path]:
    """Where this session's `transcript.jsonl` may be, best guess first.

    `amplifier_app_cli/session_store.py:96-99` writes
    `~/.amplifier/projects/<slug>/sessions/<id>/`, with `<slug>` derived from
    the cwd at session start. A session whose cwd moved is still found by the
    glob below, which is why there are two candidates and not one.
    """
    # `Path("")` is `Path(".")` and is truthy, so the empty case is tested by
    # hand rather than with `or` — an unset variable must not mean the cwd.
    raw = os.environ.get("AMPLIFIER_PROJECTS_HOME", "").strip()
    root = Path(raw).expanduser() if raw else Path.home() / ".amplifier" / "projects"
    first = root / project_slug() / "sessions" / session_id / "transcript.jsonl"
    found = [first] if first.is_file() else []
    found += [
        path
        for path in sorted(root.glob(f"*/sessions/{session_id}/transcript.jsonl"))
        if path != first
    ]
    return found


def read_transcript_human_turns(session_id: str) -> list[str]:
    """The `role: user` message texts on disk. Never raises — a missing or
    half-written transcript simply yields no turns, and the caller refuses."""
    turns: list[str] = []
    for path in transcript_candidates(session_id):
        try:
            lines = path.read_text(encoding="utf-8").splitlines()
        except OSError as exc:  # unreadable: not a reason to crash a session
            logger.debug("transcript unreadable at %s: %s", path, exc)
            continue
        for line in lines:
            if not line.strip():
                continue
            try:
                message = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(message, dict) and message.get("role") == "user":
                turns.append(flatten_content(message.get("content")))
        if turns:
            break
    return turns


async def context_human_turns(coordinator: Any) -> list[str]:
    """The `role: user` messages the live context module holds.

    `get_messages()` is a coroutine on the shipped context module and a plain
    call on some fakes; both are accepted. Any failure returns no turns, which
    sends the caller to the disk fallback rather than breaking the save.
    """
    try:
        context = coordinator.mount_points["context"]
    except Exception as exc:  # noqa: BLE001 — absent context is a normal path
        logger.debug("no context mount point: %s", exc)
        return []
    if context is None:
        return []
    try:
        messages = context.get_messages()
        if inspect.isawaitable(messages):
            messages = await messages
    except Exception as exc:  # noqa: BLE001 — see docstring
        logger.debug("get_messages() failed: %s", exc)
        return []
    turns: list[str] = []
    for message in messages or []:
        role = message.get("role") if isinstance(message, dict) else getattr(message, "role", None)
        if role != "user":
            continue
        content = (
            message.get("content") if isinstance(message, dict) else getattr(message, "content", "")
        )
        turns.append(flatten_content(content))
    return turns


# ------------------------------------------------------------------- the tool


class MemoryTool:
    """One tool, three operations. Every refusal is one line."""

    def __init__(self, coordinator: Any, config: dict[str, Any] | None = None) -> None:
        self.coordinator = coordinator
        self.config = config or {}

    @property
    def name(self) -> str:
        return TOOL_NAME

    @property
    def description(self) -> str:
        return DESCRIPTION

    @property
    def input_schema(self) -> dict[str, Any]:
        return INPUT_SCHEMA

    # -- session facts the library cannot see -----------------------------

    def _session_id(self) -> str:
        try:
            return str(self.coordinator.session_id or "")
        except Exception:  # noqa: BLE001 — a missing id must not break a save
            return ""

    def _is_sub_agent(self) -> bool:
        """session.v1 R2. `parent_id` is None for a root session (PINS.md)."""
        try:
            return self.coordinator.parent_id is not None
        except Exception:  # noqa: BLE001 — unknown lineage is treated as root
            return False

    async def _human_turns(self, quote: str) -> list[str]:
        """§5's evidence: every human turn of this session.

        The live context is asked first. The transcript on disk is added when
        the context module is absent, or when it holds no turn containing the
        quote — a `/remember` reaches the tool through a synthetic prompt, and
        a resumed session's earlier turns may only exist on disk.
        """
        turns = await context_human_turns(self.coordinator)
        if turns and any(quote in turn for turn in turns):
            return turns
        session_id = self._session_id()
        if session_id:
            turns = turns + await asyncio.to_thread(read_transcript_human_turns, session_id)
        return turns

    # -- operations --------------------------------------------------------

    # The parameter is named `input` because the Tool protocol names it that
    # (amplifier_core/interfaces.py:153); shadowing the builtin here is the
    # contract, not a slip.
    async def execute(self, input: dict[str, Any]) -> ToolResult:
        operation = str((input or {}).get("operation", "")).strip().lower()
        try:
            if operation == "save":
                return await self._save(input or {})
            if operation == "forget":
                return await self._forget(input or {})
            if operation == "list":
                return await self._list()
        except amplifier_memory.MemoryError as exc:
            # CapExceeded · DuplicateMemory · UnknownId · StoreMissing ·
            # QuoteNotHuman — every one already carries its own remedy.
            return _refuse(one_line(str(exc)))
        except ValueError as exc:
            return _refuse(one_line(str(exc)))
        return _refuse(
            f"refused: unknown operation {operation!r}; expected one of save, forget, list"
        )

    async def _save(self, input: dict[str, Any]) -> ToolResult:
        if self._is_sub_agent():
            return _refuse(
                "refused: session.v1 R2 — a sub-agent session never saves; "
                "only a root session with a human interlocutor may write."
            )
        text = str(input.get("text") or "").strip()
        writer = str(input.get("writer") or "assistant").strip().lower()
        if writer not in ALLOWED_WRITERS:
            return _refuse(
                f"refused: writer {writer!r} is not available in Phase 1; "
                f"expected one of {', '.join(ALLOWED_WRITERS)}."
            )
        # §6: `/remember <text>` writes exactly what the human typed, so the
        # quote IS the text. store.py enforces quote == text for this writer.
        quote = text if writer == "human" else str(input.get("quote") or "")
        if not text:
            return _refuse("refused: the memory text is empty")
        if writer != "human" and not quote.strip():
            return _refuse(
                "refused: save needs the human's verbatim words in `quote`; "
                "only the human's own words become memory (session.v1 §5)."
            )

        human_turns = await self._human_turns(quote)
        result = await asyncio.to_thread(
            amplifier_memory.save,
            text,
            quote,
            writer,
            self._session_id(),
            human_turns,
        )
        announce = ANNOUNCE_SAVE.format(id=result.id, text=result.text)
        return ToolResult(
            success=True,
            output=f"{announce}\n(committed {result.commit[:7]} to {result.target})",
        )

    async def _forget(self, input: dict[str, Any]) -> ToolResult:
        if self._is_sub_agent():
            return _refuse(
                "refused: session.v1 R2 — a sub-agent session never writes to the store; "
                "only a root session with a human interlocutor may forget a memory."
            )
        memory_id = str(input.get("id") or "").strip()
        if not memory_id:
            return _refuse("refused: forget needs the memory id, e.g. m-017")
        result = await asyncio.to_thread(
            amplifier_memory.forget,
            memory_id,
            None,
            session_id=self._session_id(),
            writer="human",
        )
        announce = ANNOUNCE_FORGET.format(id=result.id)
        return ToolResult(
            success=True,
            output=f"{announce}\n(committed {result.commit[:7]} to {result.target}: {result.text})",
        )

    async def _list(self) -> ToolResult:
        """§6's `/memory`, and §7's recall: reading, never searching."""
        memories = await asyncio.to_thread(amplifier_memory.list_memories)
        home = amplifier_memory.store_home()
        topics = sorted((home / "topics").glob("*.md")) if (home / "topics").is_dir() else []
        header = (
            f"{len(memories)} memories, {len(topics)} topic files, "
            "0 pending suggestions (Phase 1 records none)."
        )
        if not memories:
            return ToolResult(
                success=True,
                output=f"{header}\nNo memories yet — /remember <text> to add one.",
            )
        body = "\n".join(f"- [{m['id']}] {m['text']}" for m in memories)
        return ToolResult(success=True, output=f"{header}\n{body}")


def _refuse(message: str) -> ToolResult:
    """One line, both channels. The model relays it; nothing raises."""
    return ToolResult(success=False, output=message, error={"message": message})


async def mount(coordinator: Any, config: dict[str, Any] | None = None) -> dict[str, Any]:
    """Mount the one tool this module has.

    IRON LAW: the tool is registered via `coordinator.mount("tools", …)`.
    Returning without mounting fails `protocol_compliance` for every agent
    that composes this behavior.
    """
    tool = MemoryTool(coordinator, config or {})
    await coordinator.mount("tools", tool, name=tool.name)
    logger.info("Mounted tool-memory")
    return MODULE_INFO
