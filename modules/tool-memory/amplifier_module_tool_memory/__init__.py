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
from datetime import UTC, datetime
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

#: session.v1 §3 and §6, verbatim — the two literals this module may never
#: reword. The conformance kit re-extracts them from the locked contract and
#: compares, so the two cannot drift apart silently. Everything else in a
#: receipt is a line ADDED under them.
ANNOUNCE_SAVE = 'Saved memory {id}: "{text}" — /forget {id} to undo.'
ANNOUNCE_FORGET = "Forgot {id}."

#: Line 2 of a save receipt. The steward's transcript of 2026-09-06 showed the
#: assistant's own rewrite inside quotation marks, indistinguishable from the
#: human's words; provenance now travels with every receipt.
PROVENANCE_HUMAN = "your words, verbatim"
PROVENANCE_ASSISTANT = 'my wording, your go-ahead: "{quote}"'

#: The batch form. Consecutive assistant saves sharing one approval phrase are
#: one act to the human; the last result of the run carries the whole set, so
#: the human reads the batch once instead of N times.
BATCH_SUMMARY = (
    'Saved {n} memories — my wording, your go-ahead: "{quote}". '
    "Reword any line and I'll replace it; /forget <id> drops one."
)

#: Line 3 of a forget receipt. Forgetting is the one irreversible-looking
#: operation, and it echoed nothing back: the human could not tell what left.
FORGET_PROVENANCE = "still in git: amplifier-memory why {id}"

#: store.v1 §9 — hand edits are legitimate and need no ceremony. The listing
#: says so, every time, because nothing else does.
LIST_EDIT_BY_HAND = "edit by hand: $EDITOR {path}"

# §3 (when to save) and §4 (when not to) both stated, the §3 announce format quoted so
# the model has nothing to invent, and one line of calling discipline: on 2026-09-06 a
# model issued three saves in one turn, the library had no lock, and the steward's
# MEMORY.md was corrupted. The library now serializes them (store.v1 Core 1), so that
# line is belt as well as braces — a serialized call still costs a wait.
DESCRIPTION = """Record a standing preference the human just stated, in the same turn.
SAVE when the human says "never X", "always Y", "stop doing Z", "for future reference…" —
anything meant to hold beyond the current task. `text` is one imperative line; `quote` is
the human's own words, verbatim, copied from their message.
DO NOT SAVE task-scoped instructions ("do step 1", "reply with exactly ok"), facts
re-derivable from the code or the current task, anything already in MEMORY.md or
AGENTS.md, or anything the human asked to keep private.
Then announce it in one line, exactly: Saved memory m-017: "<text>" — /forget m-017 to undo. Save ONE memory per call and wait for its result before the next; never issue memory calls in parallel.
operation=save {text, quote, writer, topic, topic_purpose} · operation=forget {id} · operation=list
You can save wording you drafted. When the human approves lines you proposed ("remember
these"), save them one per call with writer=assistant and quote set to their approval
phrase; the last result carries the whole batch, and you add nothing to it.
A ruleset — anything that will not fit on one line — goes in a topic file: pass topic=<slug>
(plus topic_purpose=<one line> the first time), one call per line, then ONE pointer line in
MEMORY.md: save `<what it covers> → topics/<slug>.md` with no topic=.
Ids are the only names. A bare number N means m-00N, never a position in a list. Never guess an id: if it cannot be resolved, list the current ids and ask.
Never restate a memory receipt or listing in your own words; the tool result is what the human reads.
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
        "topic": {
            "type": "string",
            "description": (
                "save: put this line in topics/<slug>.md instead of MEMORY.md "
                "(store.v1 §5) — for a ruleset, one call per line"
            ),
        },
        "topic_purpose": {
            "type": "string",
            "description": "save: the topic file's one-line purpose; required when it is new",
        },
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


# ------------------------------------------------------------------- refusals
#
# One line each, and each one says what happened, what did not change, and what
# the human can do next. The library's own messages are engineer-facing; these
# are the sentences a person reads on screen.

REFUSAL_DUPLICATE = "already remembered as {id} — nothing changed."
REFUSAL_DUPLICATE_UNIDENTIFIED = "already remembered — nothing changed."
REFUSAL_NO_HUMAN_WORDS = (
    "can't save that one — you haven't said it in your own words yet. "
    "Type it and I'll record it verbatim."
)
REFUSAL_ANY_FAILURE = (
    "not saved — nothing changed, nothing lost. Details: {log}"
)


def error_log_path() -> Path:
    """session.v1 §10 — `~/.amplifier/memory-errors.log`, overridable.

    Same variable and default as the inject hook, so both surfaces write one
    file. The refusal above names this path; a named path with nothing in it
    would be its own small lie, which is why the tool appends before refusing.
    """
    raw = os.environ.get("AMPLIFIER_MEMORY_ERROR_LOG", "").strip()
    if raw:
        return Path(raw).expanduser()
    return Path.home() / ".amplifier" / "memory-errors.log"


def display_path(path: Path) -> str:
    """`~/…` for the default store, the real path when the env var is set."""
    if os.environ.get("AMPLIFIER_MEMORY_HOME", "").strip():
        return str(path)
    try:
        return "~/" + str(path.relative_to(Path.home()))
    except ValueError:
        return str(path)


def log_failure(operation: str, exc: BaseException) -> None:
    """One line to the error log. Never raises: §10 is fail-open."""
    try:
        path = error_log_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now(UTC).isoformat(timespec="seconds")
        with path.open("a", encoding="utf-8") as handle:
            handle.write(f"{stamp} tool-memory {operation}: {one_line(str(exc))}\n")
    except Exception as log_exc:  # noqa: BLE001 — a log failure is not a session failure
        logger.debug("could not append to the memory error log: %s", log_exc)


def cap_refusal(exc: Any) -> str:
    """store.v1 §4/§5 caps, in the human's words rather than the writer's."""
    target = getattr(exc, "target", "MEMORY.md")
    current = getattr(exc, "current", "?")
    cap = getattr(exc, "cap", "?")
    if str(target).endswith("/"):
        return (
            f"not saved — the store already holds {current} of {cap} topic files. "
            "/forget one you no longer need, or consolidate two."
        )
    return (
        f"not saved — {target} is full ({current} of {cap} lines). "
        "/forget one you no longer need, or ask me to move a group into a topic file."
    )


def duplicate_refusal(text: str) -> str:
    """Name the id that already holds this line; the human's next move needs it."""
    try:
        for memory in amplifier_memory.list_memories(include_topics=True):
            if memory["text"] == text:
                return REFUSAL_DUPLICATE.format(id=memory["id"])
    except Exception as exc:  # noqa: BLE001 — a lookup failure must not hide the refusal
        logger.debug("duplicate lookup failed: %s", exc)
    return REFUSAL_DUPLICATE_UNIDENTIFIED


def unknown_id_refusal(memory_id: str) -> str:
    """Say when it went and what exists now — never guess a near-miss id.

    The date comes from the store's own history (`why`), which is where a
    forget lands (store.v1 §6); nothing is remembered in the tool to produce it.
    """
    try:
        # Sorted, because this list is read to pick one out: file order puts
        # MEMORY.md before topics/ and would show m-006 ahead of m-004.
        current = ", ".join(
            sorted(str(m["id"]) for m in amplifier_memory.list_memories(include_topics=True))
        )
    except Exception as exc:  # noqa: BLE001 — see above
        logger.debug("id listing failed: %s", exc)
        current = ""
    current = current or "none"
    when = ""
    try:
        for record in amplifier_memory.why(memory_id):
            if record.get("action") == "forget":
                when = str(record.get("date") or "")[:10]
                break
    except Exception as exc:  # noqa: BLE001 — no history is a normal answer here
        logger.debug("why(%s) found nothing: %s", memory_id, exc)
    fate = f"forgotten {when}" if when else "never issued"
    return f"no memory {memory_id} — {fate}. Current: {current}. Say the id."


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
        # The run of assistant saves sharing one approval phrase, if any. The
        # tool instance lives as long as the session, which is exactly the span
        # a batch can cover.
        self._batch: dict[str, Any] | None = None

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
            return _refuse(await self._refusal(operation, exc, input or {}))
        except ValueError as exc:
            # A caller error the model must fix (empty text, a bad slug, a
            # missing topic purpose). Its own words are the useful ones.
            return _refuse(one_line(str(exc)))
        return _refuse(
            f"refused: unknown operation {operation!r}; expected one of save, forget, list"
        )

    async def _refusal(self, operation: str, exc: Exception, input: dict[str, Any]) -> str:
        """One library refusal → one sentence a person can act on."""
        if isinstance(exc, amplifier_memory.CapExceeded):
            return cap_refusal(exc)
        if isinstance(exc, amplifier_memory.DuplicateMemory):
            text = str(input.get("text") or "").strip()
            return await asyncio.to_thread(duplicate_refusal, text)
        if isinstance(exc, amplifier_memory.UnknownId):
            memory_id = str(input.get("id") or "").strip()
            return await asyncio.to_thread(unknown_id_refusal, memory_id)
        if isinstance(exc, amplifier_memory.QuoteNotHuman):
            return REFUSAL_NO_HUMAN_WORDS
        if isinstance(exc, amplifier_memory.StoreMissing):
            # Not "any other failure": this one has a remedy the human can run,
            # and burying it under the generic line would cost them that.
            return one_line(str(exc))
        # Everything else — git trouble, a lock timeout, a write that did not
        # land, a malformed store. The human learns nothing from the mechanism.
        await asyncio.to_thread(log_failure, operation, exc)
        return REFUSAL_ANY_FAILURE.format(log=display_path(error_log_path()))

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
                f"refused: writer {writer!r} is not available; "
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

        # store.v1 §5: a ruleset lives in a topic file, one line per call, with
        # a single pointer line left in MEMORY.md.
        topic = str(input.get("topic") or "").strip() or None
        topic_purpose = str(input.get("topic_purpose") or "").strip() or None

        human_turns = await self._human_turns(quote)
        result = await asyncio.to_thread(
            amplifier_memory.save,
            text,
            quote,
            writer,
            self._session_id(),
            human_turns,
            topic=topic,
            topic_purpose=topic_purpose,
        )
        lines = [ANNOUNCE_SAVE.format(id=result.id, text=result.text)]
        batch = self._track_batch(writer, quote, result)
        if batch is not None:
            lines.append(BATCH_SUMMARY.format(n=len(batch), quote=quote))
            lines += [f"- [{mid}] {saved}" for mid, saved in batch]
        elif writer == "human":
            lines.append(PROVENANCE_HUMAN)
        else:
            lines.append(PROVENANCE_ASSISTANT.format(quote=quote))
        if topic is not None:
            lines.append(
                f"in {result.target} — MEMORY.md needs one pointer line: "
                f"- [m-NNN] <what it covers> → {result.target}"
            )
        return ToolResult(success=True, output="\n".join(lines))

    def _track_batch(self, writer: str, quote: str, result: Any) -> list[tuple[str, str]] | None:
        """The run so far when this save continues one, else None.

        A batch is what the human experiences as one act: several lines the
        assistant drafted, approved with a single phrase. The signal is that
        phrase — consecutive assistant saves carrying the same `quote` into the
        same file. The
        first save of a run reads as an ordinary save; from the second on, the
        receipt carries the whole set, so the last result of the run is the one
        the human needs to read.
        """
        if writer != "assistant" or not quote:
            self._batch = None
            return None
        # The target is part of the key: two lines in a topic file and the
        # pointer line in MEMORY.md are not peers, and listing them together
        # would say they were.
        key = (quote, result.target)
        if self._batch is None or self._batch["key"] != key:
            self._batch = {"key": key, "saves": [(result.id, result.text)]}
            return None
        self._batch["saves"].append((result.id, result.text))
        return list(self._batch["saves"])

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
        # The text is echoed because forgetting is the one operation whose
        # result the human cannot see: the line is gone from the file.
        return ToolResult(
            success=True,
            output="\n".join(
                [
                    ANNOUNCE_FORGET.format(id=result.id),
                    result.text,
                    FORGET_PROVENANCE.format(id=result.id),
                ]
            ),
        )

    async def _list(self) -> ToolResult:
        """§6's `/memory`, and §7's recall: reading, never searching."""
        memories = await asyncio.to_thread(amplifier_memory.list_memories)
        home = amplifier_memory.store_home()
        topics = sorted((home / "topics").glob("*.md")) if (home / "topics").is_dir() else []
        header = f"{len(memories)} memories" if len(memories) != 1 else "1 memory"
        if topics:
            header += f", {len(topics)} topics" if len(topics) != 1 else ", 1 topic"
        body = [f"- [{m['id']}] {m['text']}" for m in memories] or [
            "No memories yet — /remember <text> to add one."
        ]
        edit = LIST_EDIT_BY_HAND.format(path=display_path(home / "MEMORY.md"))
        return ToolResult(success=True, output="\n".join([header, *body, edit]))


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
