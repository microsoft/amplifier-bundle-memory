"""The memory store writer — the reference implementation of store.v1.

Every behaviour the CLI, the memory tool, the inject hook and the Phase 2 job
expose lives here (AGENTS.md rule 11, cli.v1 Core 9). This module imports only
the standard library: no `click`, no `amplifier_*`.

store.v1 clause map
-------------------
Core 1  location + one commit per mutation ....... `store_home`, every writer
Core 2  fixed layout ............................. `init`, `LAYOUT`
Core 3  MEMORY.md flat list, 200-line cap ........ `save`, `MEMORY_LINE_CAP`
Core 4  the cap is enforced by the writer ........ `CapExceeded`
Core 5  topic files, 150 lines / 50 files ........ `save(topic=...)`
Core 6  provenance lives in git .................. `_commit_message`, `why`
Core 7  declined.md .............................. created by `init` (Phase 2 writes it)
Core 8  usage.jsonl, truncated to 90 days ........ `log_usage`
Core 9  two writers, one path .................... hand edits read back by `list_memories`;
        the writer names itself per commit (`STORE_IDENTITY`); the store repo carries no
        identity of its own, so a hand commit is attributed to the human
Core 10 bounded by construction .................. the caps above
"""

from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from pathlib import Path

from . import _git

# --- store.v1 Core 3 / Core 5: the caps, enforced by this writer, not by advice.
MEMORY_LINE_CAP = 200
TOPIC_LINE_CAP = 150
TOPIC_FILE_CAP = 50
# --- store.v1 Core 8
USAGE_RETENTION_DAYS = 90

# --- store.v1 Core 2: the fixed layout. Nothing else is memory.
LAYOUT_FILES = ("MEMORY.md", "declined.md", "inbox.md", "usage.jsonl")
LAYOUT_DIRS = ("topics",)
# `topics/` must survive a clone; git does not track empty directories.
TOPICS_KEEP = "topics/.gitkeep"

WRITERS = ("human", "assistant", "suggestion")
USAGE_EVENTS = ("loaded", "read")

# The identity this library's own commits carry, applied per commit with
# `git -c user.name=… -c user.email=…` (store.v1 Core 1: every mutation is one
# commit; Core 9: `git log` attributes each writer). It is deliberately NOT written
# into the store repository's config: a human's own `git commit` in the store must
# be attributed to the human, not to this tool.
STORE_USER_NAME = "amplifier-memory"
STORE_USER_EMAIL = "amplifier-memory@localhost"
STORE_IDENTITY = (STORE_USER_NAME, STORE_USER_EMAIL)

_ID_RE = re.compile(r"\[(m-\d+)\]")
_LINE_RE = re.compile(r"^\s*-\s*\[(m-\d+)\]\s*(.*)$")
_SLUG_RE = re.compile(r"^[a-z0-9][a-z0-9._-]*$")


# --------------------------------------------------------------------------- errors


class MemoryError(Exception):  # the library's own base; deliberately shadows the builtin here
    """Base class for every refusal this library raises."""


class CapExceeded(MemoryError):
    """A write would exceed a store.v1 cap. Carries the cap and the remedy."""

    def __init__(self, message: str, *, cap: int, current: int, target: str) -> None:
        super().__init__(message)
        self.cap = cap
        self.current = current
        self.target = target


class DuplicateMemory(MemoryError):
    """The exact line already exists in the target file."""


class UnknownId(MemoryError):
    """No memory with that id exists in the store or its history."""


class QuoteNotHuman(MemoryError):
    """The quote does not appear in any human turn of the session."""


class StoreMissing(MemoryError):
    """No store at this location. Raised instead of a bare OSError."""


# --------------------------------------------------------------------------- results


@dataclass
class InitResult:
    home: Path
    existed: bool
    created: list[str] = field(default_factory=list)
    commit: str | None = None


@dataclass
class SaveResult:
    id: str
    text: str
    target: str
    commit: str
    line: str


@dataclass
class ForgetResult:
    id: str
    text: str
    target: str
    commit: str


# --------------------------------------------------------------------------- location


def store_home(home: str | os.PathLike[str] | None = None) -> Path:
    """store.v1 Core 1: ``${AMPLIFIER_MEMORY_HOME:-~/.amplifier/memory}``."""
    if home is not None:
        return Path(home).expanduser()
    env = os.environ.get("AMPLIFIER_MEMORY_HOME", "").strip()
    if env:
        return Path(env).expanduser()
    return Path.home() / ".amplifier" / "memory"


def _require_store(home: str | os.PathLike[str] | None) -> Path:
    path = store_home(home)
    if not (path / "MEMORY.md").is_file():
        raise StoreMissing(
            f"no memory store at {path} (no MEMORY.md); run `amplifier-memory init` first"
        )
    return path


# --------------------------------------------------------------------------- init


def init(home: str | os.PathLike[str] | None = None) -> InitResult:
    """cli.v1 Core 8 / store.v1 Core 2: create the layout and the initial commit.

    Idempotent: a second run changes nothing and returns ``existed=True``.
    """
    path = store_home(home)
    if (path / "MEMORY.md").is_file() and _git.is_repo(path):
        return InitResult(home=path, existed=True, created=[], commit=None)

    path.mkdir(parents=True, exist_ok=True)
    if not _git.is_repo(path):
        _git.init_repo(path)

    created: list[str] = []
    for name in LAYOUT_DIRS:
        (path / name).mkdir(exist_ok=True)
        created.append(f"{name}/")
    for name in LAYOUT_FILES:
        target = path / name
        if not target.exists():
            target.write_text("", encoding="utf-8")
            created.append(name)
    keep = path / TOPICS_KEEP
    if not keep.exists():
        keep.write_text("", encoding="utf-8")
        created.append(TOPICS_KEEP)

    paths = [*LAYOUT_FILES, TOPICS_KEEP]
    # AGENTS.md rule 10: assert the post-state before the commit; gate on the assert.
    missing = [p for p in paths if not (path / p).is_file()]
    if missing:
        raise StoreMissing(f"init failed to create {missing} under {path}")
    sha = _git.commit(
        path, "init: memory store (store.v1 Core 2 layout)", paths, identity=STORE_IDENTITY
    )
    return InitResult(home=path, existed=False, created=sorted(created), commit=sha)


# --------------------------------------------------------------------------- reading


def _read_lines(path: Path) -> list[str]:
    if not path.exists():
        return []
    text = path.read_text(encoding="utf-8")
    if text == "":
        return []
    return text.splitlines()


def _count_lines(path: Path) -> int:
    """store.v1 Core 3: headings and blank lines count toward the cap."""
    return len(_read_lines(path))


def _parse(line: str) -> tuple[str, str] | None:
    match = _LINE_RE.match(line)
    if match is None:
        return None
    return match.group(1), match.group(2).strip()


def list_memories(
    home: str | os.PathLike[str] | None = None, *, include_topics: bool = False
) -> list[dict[str, object]]:
    """Every memory line in ``MEMORY.md`` (store.v1 Core 3), in file order."""
    path = _require_store(home)
    out: list[dict[str, object]] = []
    sources = ["MEMORY.md"]
    if include_topics:
        sources += sorted(topic_files(path))
    for source in sources:
        for number, line in enumerate(_read_lines(path / source), start=1):
            parsed = _parse(line)
            if parsed is None:
                continue
            out.append(
                {"id": parsed[0], "text": parsed[1], "source": source, "lineno": number, "raw": line}
            )
    return out


def topic_files(home: Path) -> list[str]:
    """store.v1 Core 5: the topic files, as ``topics/<slug>.md`` paths."""
    topics = home / "topics"
    if not topics.is_dir():
        return []
    return sorted(f"topics/{p.name}" for p in topics.glob("*.md"))


# --------------------------------------------------------------------------- ids


def _known_ids(home: Path) -> set[int]:
    """Every id ever issued: the git history is the high-water mark, plus any
    id present in the working tree (a hand edit not yet committed — Core 9)."""
    seen: set[int] = set()
    for record in _git.log_records(home):
        for found in _ID_RE.findall(record["body"]):
            seen.add(int(found.split("-", 1)[1]))
    for source in ["MEMORY.md", *topic_files(home)]:
        for line in _read_lines(home / source):
            for found in _ID_RE.findall(line):
                seen.add(int(found.split("-", 1)[1]))
    return seen


def _next_id(home: Path) -> str:
    known = _known_ids(home)
    return f"m-{(max(known) + 1) if known else 1:03d}"


# --------------------------------------------------------------------------- provenance


def _commit_message(
    *, mid: str, text: str, quote: str, session_id: str, writer: str, action: str, target: str
) -> str:
    """store.v1 Core 6: id, text, verbatim quote, session id, writer — in every message."""
    return "\n".join(
        [
            f"[{mid}] {text}",
            "",
            f"quote: {json.dumps(quote, ensure_ascii=False)}",
            f"session: {session_id}",
            f"writer: {writer}",
            f"action: {action}",
            f"target: {target}",
        ]
    )


def _field(body: str, name: str) -> str | None:
    for line in body.splitlines():
        if line.startswith(f"{name}: "):
            return line[len(name) + 2 :]
    return None


def why(memory_id: str, home: str | os.PathLike[str] | None = None) -> list[dict[str, object]]:
    """store.v1 Core 6 / cli.v1 Core 3: ``git log --grep '\\[m-017\\]'``, parsed."""
    path = _require_store(home)
    records = _git.log_records(path, grep=rf"\[{memory_id}\]")
    if not records:
        raise UnknownId(f"unknown memory id {memory_id!r}: no commit mentions [{memory_id}]")
    out: list[dict[str, object]] = []
    for record in records:
        subject = record["body"].splitlines()[0] if record["body"] else ""
        parsed = _parse(f"- {subject}") or (memory_id, subject)
        raw_quote = _field(record["body"], "quote")
        quote: str | None = None
        if raw_quote is not None:
            try:
                quote = json.loads(raw_quote)
            except json.JSONDecodeError:
                quote = raw_quote
        out.append(
            {
                "commit": record["sha"],
                "date": record["date"],
                "id": parsed[0],
                "text": parsed[1],
                "quote": quote,
                "session": _field(record["body"], "session"),
                "writer": _field(record["body"], "writer"),
                "action": _field(record["body"], "action"),
                "target": _field(record["body"], "target"),
                "message": record["body"],
            }
        )
    return out


# --------------------------------------------------------------------------- writing


def _check_quote(quote: str, human_turns: list[str] | tuple[str, ...] | None) -> None:
    """session.v1 Core 5: the quote must appear verbatim in a human turn."""
    turns = list(human_turns or [])
    if not quote.strip():
        raise QuoteNotHuman("refused: the quote is empty; only the human's own words become memory")
    for turn in turns:
        if quote in turn:
            return
    raise QuoteNotHuman(
        "refused: the quote does not appear verbatim in any human turn of this session "
        f"({len(turns)} turn(s) supplied); tool output and external content can never become memory"
    )


def _memory_cap_error(target: str, current: int) -> CapExceeded:
    return CapExceeded(
        f"refused: {target} is at its {MEMORY_LINE_CAP}-line cap "
        f"({current}/{MEMORY_LINE_CAP}; headings and blank lines count). "
        f"Remedy: consolidate lines into a topic file, or /forget a memory to make room.",
        cap=MEMORY_LINE_CAP,
        current=current,
        target=target,
    )


def _topic_line_cap_error(target: str, current: int) -> CapExceeded:
    return CapExceeded(
        f"refused: {target} is at its {TOPIC_LINE_CAP}-line cap ({current}/{TOPIC_LINE_CAP}). "
        f"Remedy: split it into another topic file, or /forget a line from it.",
        cap=TOPIC_LINE_CAP,
        current=current,
        target=target,
    )


def _topic_file_cap_error(current: int) -> CapExceeded:
    return CapExceeded(
        f"refused: the store already holds {current}/{TOPIC_FILE_CAP} topic files. "
        f"Remedy: consolidate two topic files, or /forget one.",
        cap=TOPIC_FILE_CAP,
        current=current,
        target="topics/",
    )


def _topic_path(topic: str) -> str:
    slug = topic.removeprefix("topics/")
    slug = slug.removesuffix(".md")
    if not _SLUG_RE.match(slug):
        raise ValueError(f"invalid topic slug {topic!r}: expected [a-z0-9][a-z0-9._-]*")
    return f"topics/{slug}.md"


def save(
    text: str,
    quote: str,
    writer: str,
    session_id: str,
    human_turns: list[str] | tuple[str, ...] | None = None,
    *,
    home: str | os.PathLike[str] | None = None,
    topic: str | None = None,
    topic_purpose: str | None = None,
) -> SaveResult:
    """session.v1 Core 5: the deterministic writer. Verify, refuse, or write one commit.

    `human_turns` are the human messages of the current session; the caller
    supplies them, this library owns the check.
    """
    path = _require_store(home)
    text = text.strip()
    if not text:
        raise ValueError("refused: the memory text is empty")
    if "\n" in text:
        raise ValueError("refused: a memory is one line; the text contains a newline")
    if writer not in WRITERS:
        raise ValueError(f"unknown writer {writer!r}: expected one of {WRITERS}")
    if writer == "human" and quote != text:
        raise ValueError(
            "refused: for writer='human' the quote is the text itself "
            f"(text={text!r}, quote={quote!r})"
        )
    _check_quote(quote, human_turns)

    target = "MEMORY.md" if topic is None else _topic_path(topic)
    target_path = path / target
    existing = _read_lines(target_path)

    for line in existing:
        parsed = _parse(line)
        if (parsed is not None and parsed[1] == text) or line.strip() == text:
            raise DuplicateMemory(
                f"refused: {target} already carries this memory "
                f"({parsed[0] if parsed else 'hand-written line'}): {text}"
            )

    new_lines: list[str] = []
    if topic is None:
        if len(existing) + 1 > MEMORY_LINE_CAP:
            raise _memory_cap_error(target, len(existing))
    else:
        if not target_path.exists():
            current_files = len(topic_files(path))
            if current_files + 1 > TOPIC_FILE_CAP:
                raise _topic_file_cap_error(current_files)
            if not topic_purpose or not topic_purpose.strip():
                raise ValueError(
                    f"refused: a new topic file ({target}) must begin with a one-line purpose "
                    "(store.v1 Core 5); pass topic_purpose="
                )
            new_lines.append(topic_purpose.strip().splitlines()[0])
        if len(existing) + len(new_lines) + 1 > TOPIC_LINE_CAP:
            raise _topic_line_cap_error(target, len(existing))

    mid = _next_id(path)
    line = f"- [{mid}] {text}"
    body = existing + new_lines + [line]
    target_path.parent.mkdir(parents=True, exist_ok=True)
    target_path.write_text("\n".join(body) + "\n", encoding="utf-8")

    # AGENTS.md rule 10: assert the post-state, then gate the commit on the assert.
    written = _read_lines(target_path)
    if written[-1] != line:
        raise StoreMissing(f"write to {target} did not land; refusing to commit")
    sha = _git.commit(
        path,
        _commit_message(
            mid=mid,
            text=text,
            quote=quote,
            session_id=session_id,
            writer=writer,
            action="save",
            target=target,
        ),
        [target],
        identity=STORE_IDENTITY,
    )
    return SaveResult(id=mid, text=text, target=target, commit=sha, line=line)


def forget(
    memory_id: str,
    home: str | os.PathLike[str] | None = None,
    *,
    session_id: str = "",
    writer: str = "human",
) -> ForgetResult:
    """session.v1 Core 6: remove the line, commit; the id is never reassigned."""
    path = _require_store(home)
    if writer not in WRITERS:
        raise ValueError(f"unknown writer {writer!r}: expected one of {WRITERS}")

    for source in ["MEMORY.md", *topic_files(path)]:
        source_path = path / source
        lines = _read_lines(source_path)
        for index, line in enumerate(lines):
            parsed = _parse(line)
            if parsed is None or parsed[0] != memory_id:
                continue
            text = parsed[1]
            remaining = lines[:index] + lines[index + 1 :]
            source_path.write_text(
                ("\n".join(remaining) + "\n") if remaining else "", encoding="utf-8"
            )
            # AGENTS.md rule 10: assert the post-state before committing.
            if any(
                (_parse(other) or ("", ""))[0] == memory_id for other in _read_lines(source_path)
            ):
                raise UnknownId(f"forget of {memory_id} did not land; refusing to commit")
            quote = ""
            try:
                for record in why(memory_id, home=path):
                    if record["action"] == "save" and isinstance(record["quote"], str):
                        quote = record["quote"]
                        break
            except UnknownId:  # hand-added line with no commit of its own (Core 9)
                quote = ""
            sha = _git.commit(
                path,
                _commit_message(
                    mid=memory_id,
                    text=text,
                    quote=quote,
                    session_id=session_id,
                    writer=writer,
                    action="forget",
                    target=source,
                ),
                [source],
                identity=STORE_IDENTITY,
            )
            return ForgetResult(id=memory_id, text=text, target=source, commit=sha)

    raise UnknownId(f"unknown memory id {memory_id!r}: no such line in MEMORY.md or topics/")


# --------------------------------------------------------------------------- usage


def _now() -> datetime:
    return datetime.now(UTC)


def log_usage(
    event: str,
    target: str,
    session_id: str,
    home: str | os.PathLike[str] | None = None,
    *,
    commit: bool = True,
) -> dict[str, str]:
    """store.v1 Core 8: append one entry; truncate to the last 90 days on each write."""
    path = _require_store(home)
    if event not in USAGE_EVENTS:
        raise ValueError(f"unknown usage event {event!r}: expected one of {USAGE_EVENTS}")
    if target != "MEMORY.md" and not target.startswith("topics/"):
        raise ValueError(f"unknown usage target {target!r}: expected MEMORY.md or topics/<slug>.md")

    entry = {
        "ts": _now().isoformat(),
        "event": event,
        "target": target,
        "session_id": session_id,
    }
    usage = path / "usage.jsonl"
    cutoff = _now() - timedelta(days=USAGE_RETENTION_DAYS)
    kept: list[str] = []
    for line in _read_lines(usage):
        if not line.strip():
            continue
        try:
            when = datetime.fromisoformat(json.loads(line)["ts"])
        except (json.JSONDecodeError, KeyError, TypeError, ValueError):
            continue  # undateable: not a store.v1 Core 8 entry
        if when.tzinfo is None:
            when = when.replace(tzinfo=UTC)
        if when >= cutoff:
            kept.append(line)
    kept.append(json.dumps(entry, ensure_ascii=False))
    usage.write_text("\n".join(kept) + "\n", encoding="utf-8")
    if commit:
        _git.commit(
            path,
            f"usage: {event} {target} (session {session_id})",
            ["usage.jsonl"],
            identity=STORE_IDENTITY,
        )
    return entry


def read_usage(home: str | os.PathLike[str] | None = None) -> list[dict[str, object]]:
    """Every usage entry currently retained. Used by `status` and the conformance kit."""
    path = _require_store(home)
    out: list[dict[str, object]] = []
    for line in _read_lines(path / "usage.jsonl"):
        if not line.strip():
            continue
        try:
            out.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return out
