"""tool-memory — the `memory` tool: save · edit · forget · list · overview · cite · review.

Serves `contracts/suggestions.v2.md`:

- §6  Review is one keystroke per item — `review` lists what the daily job
      proposed and takes one of three answers per id: **accept** writes the
      line through the same writer as session.v4 §5 and says so in that
      receipt's shape; **decline** never proposes it again; **skip** leaves it
      waiting. The library owns all three; this module renders their receipts.

Serves `contracts/session.v4.md` (FROZEN 2026-09-07):

- §3  Save on correction, in the same turn — the tool description tells the
      model when to call `save`; the *calling* is model behaviour. The receipt
      is three lines and is rendered here, once, never restated by the model.
- §4  Do not save — the same description tells the model when not to.
- §5  The model proposes; the writer commits — this module proposes; the
      writer is `amplifier_memory.save`, which owns the human-turn check,
      the duplicate check, the id, the caps, the write and the commit. Each
      refusal is relayed as the one line §5 fixes.
- §6  Two commands — `/remember <text>` and `/memory <first word>` are the
      skills that call this tool; `save`, `edit`, `forget`, `list`, `overview`
      and `review` are the operations behind them. The bare `/memory` overview
      is rendered by the library from the same report `amplifier-memory status`
      renders (`StatusReport.render_overview`), so a session and a shell can
      never disagree about a figure.
- §8  Cite at use — `cite` records the citation the assistant made in its own
      prose, through `amplifier_memory.record_citation`; the result is empty.
- §11 What reaches every model request is bounded — the description below
      teaches only what the model needs on every turn, and the skills teach the
      rest on demand. `conformance/session/budget/run.py` measures it.
- §12 Which instance a session uses is configuration — the mount plan's
      `config: home: <path>` names the instance every operation reads and
      writes; absent, the store contract's resolution order decides, so a
      session with no `home:` behaves exactly as it did before the key
      existed. When that instance's `config.yaml` says `enabled: false` the
      tool refuses every operation with §12's one line and writes nothing,
      and its description shrinks to that same line so an inert instance
      advertises nothing to the model either.
- §13 Which sessions have a human in them — a session whose
      `$AMPLIFIER_SESSION_ORIGIN` is not `human` may not `save`, `edit` or
      `forget`, refused exactly the way R2 refuses a sub-agent, naming the
      origin. Reading is untouched: the memories still apply.
- R2  Sub-agent sessions never write — refused here, before any library call,
      because only this process knows whether it is a root session.

AGENTS.md rule 11: this file carries no behaviour. It resolves the session's
human turns (which only a session can see), enforces R2 and §13 (which only a
session can know), renders the receipts and relays refusals in one line.
Everything else is a call into `amplifier_memory`. It never shells out to
`amplifier-memory` (cli.v3 §9).
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

#: `amplifier_memory.PageOutOfRange` (§6's paging rule) when this build carries it,
#: and an empty tuple when it does not: `isinstance(x, ())` is simply False, so an
#: older library takes the generic branch instead of failing at import time and
#: taking every operation down with it. The same seam `inbox_module()` keeps.
PAGE_OUT_OF_RANGE: Any = getattr(amplifier_memory, "PageOutOfRange", ())

#: Two writers reach this tool. `suggestion` is store.v2's third writer and
#: belongs to the suggestions contract — refused here by name so a caller
#: learns what happened instead of getting a library ValueError.
ALLOWED_WRITERS = ("assistant", "human")

#: session.v4 §12 — the mount-plan key naming this session's instance (store.v3 §1).
#: Read at mount, from the plan the app supplies, so this works under any app.
HOME_KEY = "home"

#: session.v4 §12, verbatim — what an inert instance answers, to every operation.
#: `<path>` is the instance itself, so a human reading the line knows which
#: `config.yaml` to change. The same sentence the library raises
#: (`store.InstanceDisabled`) and the CLI prints: one sentence, not three
#: paraphrases of one.
DISABLED = "memory is disabled for this instance ({path}: enabled: false)."

#: session.v4 §13, verbatim — the origin a session declares by exporting nothing.
HUMAN_ORIGIN = "human"

#: §13's refusals: "exactly the way it refuses a sub-agent today (R2's one-line
#: refusal, naming the origin)". One shape, one verb per operation, so the two
#: reasons a session may not write read as one rule with two causes rather than
#: as two unrelated rejections.
REFUSAL_SUB_AGENT = (
    "refused: session.v4 R2 — a sub-agent session never {verb}; "
    "only a root session with a human interlocutor may {may}."
)
REFUSAL_ORIGIN = (
    "refused: session.v4 §13 — a {origin} session never {verb}; "
    "only a session with a human interlocutor may {may}."
)

#: session.v4 §3 and §6, verbatim — the receipt lines this module may never
#: reword. The conformance kit re-extracts them from the locked contract and
#: compares, so the two cannot drift apart silently. Lines under the first are
#: indented two spaces, exactly as the contract prints them; the indent is part
#: of the receipt, not decoration.
ANNOUNCE_SAVE = "saved {id} — /memory forget {id} to undo."
ANNOUNCE_FORGET = "forgot {id} — still in git: amplifier-memory why {id}"
ANNOUNCE_EDIT = 'edited {id} — was: "{was}"'

#: Line 2 of a save receipt: the memory itself, unquoted, so a wrong line is
#: legible at a glance. Line 2 of an edit receipt: the new text, same rule.
SAVED_TEXT = "  {text}"
EDITED_TEXT = "  now: {text}"

#: Line 3 of a save receipt. The steward's transcript of 2026-09-06 showed the
#: assistant's own rewrite inside quotation marks, indistinguishable from the
#: human's words; provenance now travels with every receipt.
PROVENANCE_HUMAN = "  your words, verbatim"
PROVENANCE_ASSISTANT = '  my wording, your go-ahead: "{quote}"'

#: The batch form (§3). Several lines the assistant drafted and the human
#: approved with one phrase are ONE act; the last result of the run carries the
#: whole set, so the batch is announced once instead of N times. The run's
#: length comes from the model (`batch_of`), which is the only party that knows
#: how many lines it drafted; without it the tool stays silent rather than
#: reprinting a growing summary after every save.
BATCH_SUMMARY = (
    'saved {n} memories — my wording, your go-ahead: "{quote}". '
    "Reword any line and I'll replace it; /memory forget <id> drops one."
)

#: Line 2 of a forget receipt. Forgetting is the one irreversible-looking
#: operation, and it echoed nothing back: the human could not tell what left.
FORGOTTEN_TEXT = "  {text}"

#: suggestions.v2 §6 — the three answers, and what each one leaves behind. The
#: accept receipt is session.v4 §3's three lines with its own third line: the
#: line came from a session the human has already had, and their accept is what
#: made it a memory. A decline is reversible only by hand (§7), so the receipt
#: says where by name rather than implying a command that does not exist.
PROVENANCE_SUGGESTION = "  suggested from session {session}, accepted by you"
ANNOUNCE_CORRECTED_ACCEPT = "corrected {source} → saved as {id}"
PROVENANCE_CORRECTED_ACCEPT = '  my wording, your correction: "{quote}"'
ANNOUNCE_DECLINE = "declined {id} — won't be proposed again. Reverse by hand: edit declined.md"
ANNOUNCE_SKIP = "skipped {id} — still waiting."

#: §6 as amended 2026-09-07: a `review` page and a `list` page are **markdown,
#: rendered by the library** (`inbox.render_review_page`, `status.render_list_page`)
#: and relayed bare, so they wrap and read. Nothing here renders either one: this
#: module chooses the page, resolves the id, and renders the receipts.

#: An empty inbox has no count to print (session.v4 §6 bans a zero-valued
#: count), and a build with no inbox in it has no answer at all — the second
#: says which command puts one there instead of failing silently. The first is
#: the library's own sentence for an empty page, pinned to it by
#: `test_the_empty_inbox_line_is_the_librarys_own`.
REVIEW_EMPTY = "no suggestions waiting."
REVIEW_UNAVAILABLE = "review is not available in this build; run amplifier-memory update"
REVIEW_UNKNOWN = "no suggestion {id}. Waiting: {ids}."

#: §6: "Ids are the only names." A page numbers its items for the eye, so a model
#: that read `2.` may say `accept 2` — and by the time it lands the inbox may have
#: moved, which would accept a line the human never looked at. Refused in one line
#: that names what this page actually holds, and nothing is written.
REVIEW_POSITION = "{id} is a position, not an id \u2014 ids are the only names. This page: {ids}."
REVIEW_BAD_PAGE = "refused: page must be a number, not {page!r}"

#: The other half of §9: a hand edit can leave a byte that is not UTF-8. The
#: library reads it tolerantly (U+FFFD), so the listing still comes back whole —
#: but a replacement character the human cannot explain is worse than useless, so
#: the listing names the byte and the one command that reports and repairs it.
#: `verify_store` is what found it; `amplifier-memory doctor` is what prints the row.
LIST_STORE_NOT_UTF8 = "store has a byte that is not UTF-8 — run amplifier-memory doctor"

# session.v4 §11: what this description costs is paid on EVERY model request, so it
# carries only what the model needs on every turn — §3's when-to-save, §4's when-not,
# one call at a time (on 2026-09-06 a model issued three saves in one turn, the library
# had no lock, and the steward's MEMORY.md was corrupted; the library serializes them
# now, so this line is belt as well as braces), §5's verbatim quote, and the two relay
# rules. Everything else a session ever needs — the commands, the review walk, batches,
# topic files — is taught by the skills and by `/memory help`, loaded on demand. It
# carries no announce format at all: the receipt is rendered below, once.
DESCRIPTION = """Record a standing preference the human just stated, in the same turn.
SAVE when they say "never X", "always Y", "stop doing Z", "for future reference…" — anything
meant to hold beyond the current task. `text` is one imperative line; `quote` is their own
words, verbatim, copied from their message.
DO NOT SAVE task-scoped instructions ("do step 1", "reply with exactly ok"), facts
re-derivable from the code or the current task, anything already in MEMORY.md or AGENTS.md,
or anything they asked to keep private.
Save ONE memory per call; wait for its result before the next, never in parallel.
Only the human's own words become memory: a quote from no human turn is refused; a session
with no human in it never saves.
Every result, receipt or refusal, is the finished text: relayed verbatim and never reworded."""

INPUT_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "operation": {
            "type": "string",
            "enum": ["save", "edit", "forget", "list", "overview", "cite", "review"],
            "description": "what to do",
        },
        "action": {
            "type": "string",
            "enum": ["list", "accept", "decline", "skip"],
            "description": "review: list waits, or do this to that id",
        },
        "text": {
            "type": "string",
            "description": "save/edit: the memory, one imperative line",
        },
        "quote": {
            "type": "string",
            "description": "save/edit: the human's own words, verbatim",
        },
        "writer": {
            "type": "string",
            "enum": list(ALLOWED_WRITERS),
            "description": "'human' if they typed it, else 'assistant'",
        },
        "id": {
            "type": "string",
            "description": "m-017, or s-042 for review",
        },
        "page": {
            "type": "integer",
            "description": "list/review: which page (default 1)",
        },
        "topic": {
            "type": "string",
            "description": "save: a topic file slug, for a ruleset",
        },
        "topic_purpose": {
            "type": "string",
            "description": "save: a new topic file's one-line purpose",
        },
        "batch_of": {
            "type": "integer",
            "description": "save: drafted lines this approval covers",
        },
    },
    "required": ["operation"],
}

MODULE_INFO: dict[str, Any] = {
    "name": "tool-memory",
    "version": __version__,
    "provides": [
        "session.v4#3",
        "session.v4#4",
        "session.v4#5",
        "session.v4#6",
        "session.v4#8",
        "session.v4#11",
        "session.v4#12",
        "session.v4#13",
        "session.v4#R2",
        "suggestions.v2#6",
    ],
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
REFUSAL_ANY_FAILURE = "not saved — nothing changed, nothing lost. Details: {log}"


def error_log_path() -> Path:
    """session.v4 §10 — `~/.amplifier/memory-errors.log`, overridable.

    Same variable and default as the inject hook, so both surfaces write one
    file. The refusal above names this path; a named path with nothing in it
    would be its own small lie, which is why the tool appends before refusing.
    """
    raw = os.environ.get("AMPLIFIER_MEMORY_ERROR_LOG", "").strip()
    if raw:
        return Path(raw).expanduser()
    return Path.home() / ".amplifier" / "memory-errors.log"


def display_path(path: Path) -> str:
    """`~/…` for the default store, the real path when the env var is set.

    The library's own spelling (`amplifier_memory.display_path`) when this build has
    one, so the path in a listing and the path in a refusal are written the same way.
    """
    spell = getattr(amplifier_memory, "display_path", None)
    if spell is not None:
        return spell(path)
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
    """store.v2 §4/§5 caps, in the human's words rather than the writer's."""
    target = getattr(exc, "target", "MEMORY.md")
    current = getattr(exc, "current", "?")
    cap = getattr(exc, "cap", "?")
    if str(target).endswith("/"):
        return (
            f"not saved — the store already holds {current} of {cap} topic files. "
            "/memory forget one you no longer need, or consolidate two."
        )
    return (
        f"not saved — {target} is full ({current} of {cap} lines). "
        "/memory forget one you no longer need, or ask me to move a group into a topic file."
    )


def duplicate_refusal(text: str, home: Path | None = None) -> str:
    """Name the id that already holds this line; the human's next move needs it."""
    try:
        for memory in amplifier_memory.list_memories(home, include_topics=True):
            if memory["text"] == text:
                return REFUSAL_DUPLICATE.format(id=memory["id"])
    except Exception as exc:  # noqa: BLE001 — a lookup failure must not hide the refusal
        logger.debug("duplicate lookup failed: %s", exc)
    return REFUSAL_DUPLICATE_UNIDENTIFIED


def memory_text(memory_id: str, home: Path | None = None) -> str:
    """What `memory_id` currently reads, or `""` when it is not there.

    Read before an edit, because a receipt that cannot say what a memory *was*
    cannot show the human what they just changed (§6).
    """
    try:
        for memory in amplifier_memory.list_memories(home, include_topics=True):
            if str(memory["id"]) == memory_id:
                return str(memory["text"])
    except Exception as exc:  # noqa: BLE001 — the library refuses for itself
        logger.debug("could not read %s before an edit: %s", memory_id, exc)
    return ""


def memory_ids(home: Path | None = None) -> set[str] | None:
    """Every id in the store, or None when the store could not be listed.

    None is not an empty set: a citation is never refused because the *listing*
    failed, only because the id genuinely is not there.
    """
    try:
        return {str(m["id"]) for m in amplifier_memory.list_memories(home, include_topics=True)}
    except Exception as exc:  # noqa: BLE001 — see docstring
        logger.debug("id listing failed: %s", exc)
        return None


def unknown_id_refusal(memory_id: str, home: Path | None = None) -> str:
    """Say when it went and what exists now — never guess a near-miss id.

    The date comes from the store's own history (`why`), which is where a
    forget lands (store.v2 §6); nothing is remembered in the tool to produce it.
    """
    try:
        # Sorted, because this list is read to pick one out: file order puts
        # MEMORY.md before topics/ and would show m-006 ahead of m-004.
        current = ", ".join(
            sorted(str(m["id"]) for m in amplifier_memory.list_memories(home, include_topics=True))
        )
    except Exception as exc:  # noqa: BLE001 — see above
        logger.debug("id listing failed: %s", exc)
        current = ""
    current = current or "none"
    when = ""
    try:
        for record in amplifier_memory.why(memory_id, home):
            if record.get("action") == "forget":
                when = str(record.get("date") or "")[:10]
                break
    except Exception as exc:  # noqa: BLE001 — no history is a normal answer here
        logger.debug("why(%s) found nothing: %s", memory_id, exc)
    fate = f"forgotten {when}" if when else "never issued"
    return f"no memory {memory_id} — {fate}. Current: {current}. Say the id."


def inbox_module() -> Any | None:
    """`amplifier_memory.inbox`, or None when this build has no inbox at all.

    The attribute IS the seam between this adapter and the library that owns
    the inbox. Read by name on every call, so a build without one answers
    `REVIEW_UNAVAILABLE` in a sentence instead of raising `AttributeError` at
    import time and taking the four commands down with it.
    """
    return getattr(amplifier_memory, "inbox", None)


def short_session(session: Any) -> str:
    """The 8 characters a human uses to recognise a session (suggestions.v2 §4).

    The library's own spelling when this build has one — a review page and the accept
    receipt name the same session, and they must shorten it the same way.
    """
    shorten = getattr(inbox_module(), "short_session", None)
    return shorten(session) if shorten else str(session or "")[:8]


def wanted_page(input: dict[str, Any]) -> int:
    """§6's `<page>`: the page a `list` or `review` call asked for. Default 1.

    `next` in conversation is this call again with `page + 1` (§6) — the model does
    the adding, which is why nothing here remembers a page.
    """
    raw = input.get("page")
    if raw in (None, ""):
        return 1
    try:
        return int(raw)
    except (TypeError, ValueError) as exc:
        raise ValueError(REVIEW_BAD_PAGE.format(page=raw)) from exc


def position_refusal(said: str, page_ids: list[str]) -> str:
    """§6: a bare number is a position, and positions are never names."""
    return REVIEW_POSITION.format(id=said, ids=", ".join(page_ids) or "nothing")


def unknown_suggestion_refusal(suggestion_id: str, waiting: list[Any]) -> str:
    """One line: this id is not waiting, and these are. Never a near-miss guess."""
    if not waiting:
        return REVIEW_EMPTY
    return REVIEW_UNKNOWN.format(id=suggestion_id, ids=", ".join(str(item.id) for item in waiting))


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
            # Bytes, then a replacing decode — never a strict UTF-8 read, which
            # raises `UnicodeDecodeError` (a `ValueError`, so the clause below would
            # not catch it) on one byte that is not UTF-8. A transcript is the
            # session's own file, not the store, so `amplifier_memory.read_memory_text`
            # does not apply; the tolerance rule it follows does.
            lines = path.read_bytes().decode("utf-8", errors="replace").splitlines()
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
        # §12: the instance comes from the mount plan the app supplies, read
        # here, at mount, so this works under any app. `None` means "the store
        # contract's resolution order decides", which is the pre-§12 behaviour.
        raw_home = self.config.get(HOME_KEY)
        self.configured_home: str | None = str(raw_home).strip() or None if raw_home else None
        # The run of assistant saves sharing one approval phrase, if any. The
        # tool instance lives as long as the session, which is exactly the span
        # a batch can cover.
        self._batch: dict[str, Any] | None = None

    @property
    def name(self) -> str:
        return TOOL_NAME

    @property
    def description(self) -> str:
        """§11's description — or, on an inert instance, §12's one line instead.

        An instance that is switched off has nothing to teach the model about
        saving, and §11 is measured on what every request pays: a disabled
        instance should cost the sentence that says so, not the full lesson.
        """
        if not self._enabled():
            return self._disabled_line()
        return DESCRIPTION

    @property
    def input_schema(self) -> dict[str, Any]:
        return INPUT_SCHEMA

    # -- §12: which instance, and whether it is live ----------------------

    def home(self) -> Path:
        """The instance this session reads and writes — session.v4 §12, store.v3 §1.

        Resolved on every call rather than cached, so a test (or a human) can
        move the store without remounting the module, exactly as the inject
        hook does.
        """
        return amplifier_memory.store_home(self.configured_home)

    def _enabled(self) -> bool:
        """store.v3 §11 / session.v4 §12 — is this instance live, or inert?

        Never raises: an instance the library cannot judge is treated as live,
        which is `instance_enabled`'s own rule (a parse error must never
        silently switch memory off).
        """
        try:
            return amplifier_memory.instance_enabled(self.home())
        except Exception as exc:  # noqa: BLE001 — see docstring
            logger.debug("could not read the instance's config: %s", exc)
            return True

    def _disabled_line(self) -> str:
        """§12's sentence, naming this instance."""
        try:
            return DISABLED.format(path=self.home())
        except Exception as exc:  # noqa: BLE001 — a refusal must never fail to be a refusal
            logger.debug("could not name the instance: %s", exc)
            return DISABLED.format(path="this instance")

    # -- session facts the library cannot see -----------------------------

    def _session_id(self) -> str:
        try:
            return str(self.coordinator.session_id or "")
        except Exception:  # noqa: BLE001 — a missing id must not break a save
            return ""

    def _is_sub_agent(self) -> bool:
        """session.v4 R2. `parent_id` is None for a root session (PINS.md)."""
        try:
            return self.coordinator.parent_id is not None
        except Exception:  # noqa: BLE001 — unknown lineage is treated as root
            return False

    def origin(self) -> str:
        """session.v4 §13 — what this session declares itself to be.

        `$AMPLIFIER_SESSION_ORIGIN`, read through the library so the hook, the
        tool and the suggest job read one definition of the convention; unset
        means `human`, so a launcher that exports nothing writes exactly as it
        did before the variable existed.
        """
        try:
            return amplifier_memory.origin_from_env()
        except Exception as exc:  # noqa: BLE001 — an unreadable environment is not a failure
            logger.debug("could not read the session origin: %s", exc)
            return HUMAN_ORIGIN

    def _refuse_write(self, verb: str, may: str) -> str | None:
        """The one line that says this session may not write, or None when it may.

        Two causes, one shape (§13: "exactly the way it refuses a sub-agent
        today … naming the origin"). R2 is asked first because it is the
        narrower fact: a sub-agent of a human session is still not a writer,
        whatever the launcher exported.
        """
        if self._is_sub_agent():
            return REFUSAL_SUB_AGENT.format(verb=verb, may=may)
        origin = self.origin()
        if origin != HUMAN_ORIGIN:
            return REFUSAL_ORIGIN.format(origin=origin, verb=verb, may=may)
        return None

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
        # §12: an inert instance refuses EVERY operation — reads included — in
        # one line, and writes nothing. Asked before the operation is dispatched
        # so there is one gate rather than seven, and before any library call so
        # nothing is read from an instance the human switched off.
        if not await asyncio.to_thread(self._enabled):
            return _refuse(self._disabled_line())
        try:
            if operation == "save":
                return await self._save(input or {})
            if operation == "edit":
                return await self._edit(input or {})
            if operation == "forget":
                return await self._forget(input or {})
            if operation == "list":
                return await self._list(input or {})
            if operation == "overview":
                return await self._overview()
            if operation == "cite":
                return await self._cite(input or {})
            if operation == "review":
                return await self._review(input or {})
        except amplifier_memory.MemoryError as exc:
            return _refuse(await self._refusal(operation, exc, input or {}))
        except ValueError as exc:
            # A caller error the model must fix (empty text, a bad slug, a
            # missing topic purpose). Its own words are the useful ones.
            return _refuse(one_line(str(exc)))
        return _refuse(
            f"refused: unknown operation {operation!r}; "
            "expected one of save, edit, forget, list, overview, cite, review"
        )

    async def _refusal(self, operation: str, exc: Exception, input: dict[str, Any]) -> str:
        """One library refusal → one sentence a person can act on."""
        if isinstance(exc, PAGE_OUT_OF_RANGE):
            # §6's paging rule refuses a page past the last one and names the last
            # page in the message. Relayed as it stands: it is already the sentence.
            return one_line(str(exc))
        if isinstance(exc, amplifier_memory.CapExceeded):
            return cap_refusal(exc)
        if isinstance(exc, amplifier_memory.DuplicateMemory):
            text = str(input.get("text") or "").strip()
            return await asyncio.to_thread(duplicate_refusal, text, self.home())
        if isinstance(exc, amplifier_memory.UnknownId):
            memory_id = str(input.get("id") or "").strip()
            return await asyncio.to_thread(unknown_id_refusal, memory_id, self.home())
        if isinstance(exc, amplifier_memory.QuoteNotHuman):
            return REFUSAL_NO_HUMAN_WORDS
        if isinstance(
            exc,
            (
                getattr(amplifier_memory, "CorrectedAcceptanceUnverified", ()),
                getattr(amplifier_memory, "CorrectedAcceptanceInspectionRequired", ()),
            ),
        ):
            return one_line(str(exc))
        if isinstance(exc, (amplifier_memory.StoreMissing, amplifier_memory.StoreMalformed)):
            # Not "any other failure": these two carry a remedy the human can
            # run (`amplifier-memory init` / `amplifier-memory doctor --repair`),
            # and burying it under the generic line would cost them that.
            # (item zp4: a bad byte in MEMORY.md used to send the human to a log.)
            return one_line(str(exc))
        # Everything else — git trouble, a lock timeout, a write that did not
        # land, a malformed store. The human learns nothing from the mechanism.
        await asyncio.to_thread(log_failure, operation, exc)
        return REFUSAL_ANY_FAILURE.format(log=display_path(error_log_path()))

    async def _save(self, input: dict[str, Any]) -> ToolResult:
        refusal = self._refuse_write("saves", "write")
        if refusal:
            return _refuse(refusal)
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
                "only the human's own words become memory (session.v4 §5)."
            )

        # store.v2 §5: a ruleset lives in a topic file, one line per call, with
        # a single pointer line left in MEMORY.md.
        topic = str(input.get("topic") or "").strip() or None
        topic_purpose = str(input.get("topic_purpose") or "").strip() or None

        # §3's batch: how many drafted lines this one approval covers. A value
        # that is not a number is not worth a refusal — the save is the point,
        # and the batch summary is an addition to it.
        try:
            batch_of = int(input.get("batch_of") or 0)
        except (TypeError, ValueError):
            batch_of = 0

        human_turns = await self._human_turns(quote)
        result = await asyncio.to_thread(
            amplifier_memory.save,
            text,
            quote,
            writer,
            self._session_id(),
            human_turns,
            home=self.home(),
            topic=topic,
            topic_purpose=topic_purpose,
        )
        # §3: three lines, always, in this order — what happened and how to undo
        # it; the memory itself, unquoted, so a wrong line is legible at a
        # glance; whose words it is.
        lines = [
            ANNOUNCE_SAVE.format(id=result.id),
            SAVED_TEXT.format(text=result.text),
            PROVENANCE_HUMAN if writer == "human" else PROVENANCE_ASSISTANT.format(quote=quote),
        ]
        if topic is not None:
            lines.append(
                f"  in {result.target} — MEMORY.md needs one pointer line: "
                f"- [m-NNN] <what it covers> → {result.target}"
            )
        batch = self._track_batch(writer, quote, batch_of, result)
        if batch is not None:
            lines.append(BATCH_SUMMARY.format(n=len(batch), quote=quote))
            lines += [f"- [{mid}] {saved}" for mid, saved in batch]
        return ToolResult(success=True, output="\n".join(lines))

    def _track_batch(
        self, writer: str, quote: str, batch_of: int, result: Any
    ) -> list[tuple[str, str]] | None:
        """The whole run, on the save that COMPLETES it; None every other time.

        A batch is what the human experiences as one act: several lines the
        assistant drafted, approved with a single phrase. Two facts make it one
        run — that phrase, and `batch_of`, the count the model states because it
        is the only party that knows how many lines it drafted. The set renders
        once, on the call that completes the run; every earlier result is its own
        three-line receipt and nothing more. A summary reprinted after every save
        is the defect §6's relay-verbatim rule exists to prevent, in code rather
        than in prose. Without `batch_of` the tool cannot know which save is the last,
        so it says nothing rather than guessing.
        """
        if writer != "assistant" or not quote or batch_of < 2:
            self._batch = None
            return None
        # The target belongs to a run's identity: two lines in a topic file and
        # the pointer line in MEMORY.md are not peers, and listing them together
        # would say they were.
        run = (quote, batch_of, str(getattr(result, "target", "")))
        if self._batch is None or self._batch["run"] != run:
            self._batch = {"run": run, "saves": []}
        self._batch["saves"].append((result.id, result.text))
        if len(self._batch["saves"]) < batch_of:
            return None
        saves = list(self._batch["saves"])
        self._batch = None
        return saves

    async def _edit(self, input: dict[str, Any]) -> ToolResult:
        """§6 `/edit <id> <text>` — the id survives; the text is replaced."""
        refusal = self._refuse_write("writes to the store", "edit a memory")
        if refusal:
            return _refuse(refusal)
        self._batch = None  # an edit is not part of a run of saves
        memory_id = str(input.get("id") or input.get("memory_id") or "").strip()
        if not memory_id:
            return _refuse("refused: edit needs the memory id, e.g. m-017")
        raw_text = str(input.get("text") or "")
        text = raw_text.strip()
        if not text:
            return _refuse("refused: the memory text is empty")
        writer = str(input.get("writer") or "assistant").strip().lower()
        if writer not in ALLOWED_WRITERS:
            return _refuse(
                f"refused: writer {writer!r} is not available; "
                f"expected one of {', '.join(ALLOWED_WRITERS)}."
            )
        # A literal `/memory edit <id> <text>` is typed by the human, so its
        # quote is the text itself. A natural correction instead has two honest
        # parts: the human's instruction in `quote`, and the assistant's
        # replacement in `text`. Some models label that latter shape `human`;
        # preserving that label would silently replace the supplied quote and
        # make the library reject a real correction. Normalize only that
        # contradictory shape. The library still checks the preserved quote
        # against actual human turns before it writes.
        supplied_quote = str(input.get("quote") or "")
        if writer == "human" and supplied_quote.strip() and supplied_quote != raw_text:
            writer = "assistant"
        quote = text if writer == "human" else supplied_quote
        if writer != "human" and not quote.strip():
            return _refuse(
                "refused: edit needs the human's verbatim words in `quote`; "
                "only the human's own words become memory (session.v4 §5)."
            )

        # The old text is read BEFORE the write: the receipt shows what it was,
        # and `SaveResult` carries only what it now is. An id that is not there
        # is left to the library, which raises UnknownId and gets §6's one line.
        was = await asyncio.to_thread(memory_text, memory_id, self.home())
        human_turns = await self._human_turns(quote)
        result = await asyncio.to_thread(
            amplifier_memory.edit,
            memory_id,
            text,
            quote,
            writer,
            self._session_id(),
            human_turns,
            home=self.home(),
        )
        return ToolResult(
            success=True,
            output="\n".join(
                [
                    ANNOUNCE_EDIT.format(id=result.id, was=was),
                    EDITED_TEXT.format(text=result.text),
                ]
            ),
        )

    async def _cite(self, input: dict[str, Any]) -> ToolResult:
        """§8 — record a citation the assistant already made in its own prose.

        The result is empty by design: the citation has already been made in the
        assistant's own sentence, and a receipt here would be a second rendering
        of one act. R2 does not apply — a usage event is not a memory, it
        makes no commit at all (store.v2 §1), and a sub-agent that acts on a memory is
        exactly as worth counting as a root session that does.
        """
        memory_id = str(input.get("id") or input.get("memory_id") or "").strip()
        if not memory_id:
            return _refuse("refused: cite needs the memory id, e.g. m-017")
        known = await asyncio.to_thread(memory_ids, self.home())
        if known is not None and memory_id not in known:
            return _refuse(await asyncio.to_thread(unknown_id_refusal, memory_id, self.home()))
        await asyncio.to_thread(
            amplifier_memory.record_citation, memory_id, self._session_id(), self.home()
        )
        return ToolResult(success=True, output="")

    async def _forget(self, input: dict[str, Any]) -> ToolResult:
        refusal = self._refuse_write("writes to the store", "forget a memory")
        if refusal:
            return _refuse(refusal)
        memory_id = str(input.get("id") or "").strip()
        if not memory_id:
            return _refuse("refused: forget needs the memory id, e.g. m-017")
        result = await asyncio.to_thread(
            amplifier_memory.forget,
            memory_id,
            self.home(),
            session_id=self._session_id(),
            writer="human",
        )
        self._batch = None  # a forget is not part of a run of saves
        # The text is echoed because forgetting is the one operation that leaves
        # nothing behind to look at: the line is gone from the file. Where it
        # still lives travels on the first line, so the undo is never a search.
        return ToolResult(
            success=True,
            output="\n".join(
                [
                    ANNOUNCE_FORGET.format(id=result.id),
                    FORGOTTEN_TEXT.format(text=result.text),
                ]
            ),
        )

    async def _review(self, input: dict[str, Any]) -> ToolResult:
        """suggestions.v2 §6 — list what was proposed; accept, decline or skip one.

        Nothing here decides anything: the library owns the inbox, the writer
        and `declined.md`. This method resolves the id against what is actually
        waiting (so an unknown id is a sentence, not a library traceback),
        renders the three receipts, and enforces the one thing only a session
        knows — session.v4 R2, that a sub-agent never writes.
        """
        inbox = inbox_module()
        if inbox is None:
            return _refuse(REVIEW_UNAVAILABLE)
        action = str(input.get("action") or "").strip().lower()
        if action and action not in ("list", "accept", "decline", "skip"):
            return _refuse(
                f"refused: review action {action!r} is not available; "
                "expected one of list, accept, decline, skip."
            )
        home = self.home()
        try:
            waiting = list(await asyncio.to_thread(inbox.pending, home))
        except amplifier_memory.MemoryError:
            raise  # execute() turns a library refusal into §5's one line
        except Exception as exc:  # noqa: BLE001 — §10: a broken inbox is one line, not a crash
            await asyncio.to_thread(log_failure, "review", exc)
            return _refuse(REFUSAL_ANY_FAILURE.format(log=display_path(error_log_path())))

        page = wanted_page(input)
        if action in ("", "list"):
            # A page is reading, so it is allowed in a sub-agent session too (R2
            # forbids writing, not reading) — and an empty inbox is a normal
            # answer, not a refusal. The library renders it (§6); a page past the
            # last one raises, and `execute` relays that one line.
            return ToolResult(
                success=True,
                output=await asyncio.to_thread(inbox.render_review_page, page, home),
            )

        suggestion_id = str(input.get("id") or "").strip()
        if not suggestion_id:
            return _refuse(f"refused: review {action} needs the suggestion id, e.g. s-042")
        if suggestion_id.isdigit():
            # §6: ids are the only names. The refusal names the ids on the page the
            # call was made against, so the answer is one word away — and writes
            # nothing, because a position resolved by guesswork is the wrong line.
            bounds = amplifier_memory.page_bounds(len(waiting), page)
            return _refuse(
                position_refusal(
                    suggestion_id,
                    [str(s.id) for s in waiting[bounds.start : bounds.stop]],
                )
            )
        item = next((s for s in waiting if str(s.id) == suggestion_id), None)
        if item is None:
            return _refuse(unknown_suggestion_refusal(suggestion_id, waiting))

        # R2 and §13 cover what writes: accept puts a line in MEMORY.md, decline
        # puts one in declined.md. Skip writes nothing at all, which is why it is
        # not here — a sub-agent leaving an item exactly where it found it is not
        # a write by any reading of R2.
        #
        # §13 names save, edit and forget; accept is a save under another name,
        # and a session with nobody in it accepting a suggestion on the human's
        # behalf is exactly what §13 exists to prevent — the same reason R2 has
        # covered accept and decline since suggestions shipped.
        corrected = action == "accept" and (
            input.get("text") is not None or input.get("quote") is not None
        )
        if corrected and (
            not str(input.get("text") or "").strip() or not str(input.get("quote") or "").strip()
        ):
            return _refuse(
                "refused: corrected review accept needs both corrected text and the human's verbatim correction quote"
            )
        if action in ("accept", "decline"):
            refusal = self._refuse_write("writes to the store", f"{action} a suggestion")
            if refusal:
                return _refuse(refusal)

        try:
            if action == "accept":
                if corrected:
                    quote = str(input["quote"])
                    result = await asyncio.to_thread(
                        inbox.accept_corrected,
                        suggestion_id,
                        str(input["text"]),
                        quote,
                        self._session_id(),
                        await self._human_turns(quote),
                        home=home,
                    )
                    return ToolResult(
                        success=True,
                        output="\n".join(
                            [
                                ANNOUNCE_CORRECTED_ACCEPT.format(source=suggestion_id, id=result.id),
                                SAVED_TEXT.format(text=result.text),
                                PROVENANCE_CORRECTED_ACCEPT.format(quote=quote),
                            ]
                        ),
                    )
                result = await asyncio.to_thread(
                    inbox.accept, suggestion_id, home, session_id=self._session_id()
                )
                # session.v4 §3's three lines, with §6's provenance for the
                # third: the words are the human's, said in an earlier session,
                # and this accept is what made them a memory.
                return ToolResult(
                    success=True,
                    output="\n".join(
                        [
                            ANNOUNCE_SAVE.format(id=result.id),
                            SAVED_TEXT.format(text=result.text),
                            PROVENANCE_SUGGESTION.format(session=short_session(item.session)),
                        ]
                    ),
                )
            if action == "decline":
                await asyncio.to_thread(inbox.decline, suggestion_id, home)
                return ToolResult(success=True, output=ANNOUNCE_DECLINE.format(id=suggestion_id))
            await asyncio.to_thread(inbox.skip, suggestion_id, home)
            return ToolResult(success=True, output=ANNOUNCE_SKIP.format(id=suggestion_id))
        except amplifier_memory.MemoryError:
            raise  # execute() relays §5's refusals unchanged
        except Exception as exc:  # noqa: BLE001 — see above
            await asyncio.to_thread(log_failure, f"review {action}", exc)
            return _refuse(REFUSAL_ANY_FAILURE.format(log=display_path(error_log_path())))

    async def _overview(self) -> ToolResult:
        """§6's bare `/memory` — the library renders it; nothing is decided here.

        `status()` is the one computation (cli.v2 §2); `render_overview()` is its
        second rendering. Reading, so R2 does not apply. A missing or malformed
        store raises a `MemoryError` the way every other operation's does, and
        `execute` turns it into §5's one line with its remedy.
        """
        report = await asyncio.to_thread(amplifier_memory.status, self.home())
        return ToolResult(success=True, output=report.render_overview())

    async def _list(self, input: dict[str, Any]) -> ToolResult:
        """§6's `/memory list`, and §7's recall: reading, never searching.

        One page of markdown, rendered by the library (`status.render_list_page`) —
        the counts, the bullets and the hand-edit line are §6's, spelled once, there.
        What is added here is the one thing only a tool result can carry: a note that
        the store holds a byte that is not UTF-8, which is a fact about the store
        rather than about the listing.
        """
        page = wanted_page(input)
        lines = [await asyncio.to_thread(amplifier_memory.render_list_page, page, self.home())]
        if await asyncio.to_thread(_store_has_a_byte_that_is_not_utf8, self.home()):
            lines.append(LIST_STORE_NOT_UTF8)
        return ToolResult(success=True, output="\n".join(lines))


def _store_has_a_byte_that_is_not_utf8(home: Path | None = None) -> bool:
    """Ask the library, never the file — `verify_store` is what knows (store.v2 §9).

    Never raises: the note is an addition to a listing that already succeeded, so a
    store `verify_store` itself cannot inspect costs the note, not the listing.
    """
    try:
        return amplifier_memory.verify_store(home).decode_error_offset is not None
    except Exception as exc:  # noqa: BLE001 — a missing note is never worth a failed list
        logger.debug("verify_store unavailable: %s", exc)
        return False


def _refuse(message: str) -> ToolResult:
    """One line, both channels. The model relays it; nothing raises."""
    return ToolResult(success=False, output=message, error={"message": message})


async def mount(coordinator: Any, config: dict[str, Any] | None = None) -> dict[str, Any]:
    """Mount the one tool this module has.

    IRON LAW: the tool is registered via `coordinator.mount("tools", …)`.
    Returning without mounting fails `protocol_compliance` for every agent
    that composes this behavior.

    That law is why §12's inert instance is served by the *second* half of its
    own sentence — "or, where a plan requires it to be, refuses every operation
    with one line" — rather than the first. A plan that names this module
    requires the tool to be there; a mount that silently skipped it would fail
    protocol compliance for every agent composing this behavior, and the
    session would learn nothing about why. So the tool is always mounted, and
    on an inert instance it answers every operation with §12's line and carries
    that same line as its description, which is what makes it advertise nothing
    (`MemoryTool.description`).
    """
    tool = MemoryTool(coordinator, config or {})
    await coordinator.mount("tools", tool, name=tool.name)
    if not tool._enabled():
        logger.info("Mounted tool-memory — inert: %s", tool._disabled_line())
    else:
        logger.info("Mounted tool-memory")
    return MODULE_INFO
