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

One writer at a time (Core 1, Core 9)
-------------------------------------
Every mutating path here runs inside `_exclusive()`: an `fcntl.flock` on a lock file,
plus a process-level `threading.Lock` because `flock` is per open file description and
two threads of one process would otherwise share nothing. Concurrent `save`/`forget`/
`log_usage` calls — threads of one session, or several sessions at once — serialize on
it, so each leaves exactly one well-formed commit.

The lock file is **plumbing, not memory**: store.v1 Core 2 says a file not listed there
is not memory, so it is never placed among the store's files at all. It lives inside the
store's own `.git/` directory (`_lock_path`), which git already owns and no listing of
the store treats as content. That also means no `.gitignore` has to be invented, and a
store created before this writer existed needs no migration.

After the commit, the writer re-reads the **committed tree** (`git show HEAD:<file>`) and
asserts its own line is present (`save`) or absent (`forget`). A write that did not land
raises `WriteNotLanded`; success is never reported on the strength of the working tree
alone. That assert is what the steward's 2026-09-06 session did not have: three parallel
saves clobbered `MEMORY.md`, and one of them reported success without its line in the file.
"""

from __future__ import annotations

import difflib
import fcntl
import json
import os
import re
import subprocess
import threading
import time
from collections.abc import Iterator
from contextlib import contextmanager
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

# --- one writer at a time. See the module docstring for why the lock file lives in `.git/`.
LOCK_NAME = "amplifier-memory.lock"
#: Bounded wait. Long enough that a normal commit never trips it, short enough that a
#: stuck holder is a one-line error and not a hung session.
LOCK_TIMEOUT_S = 10.0
_LOCK_POLL_S = 0.02
#: `flock` is per open file description: two threads of one process each open the lock
#: file and would each get the lock. This closes that door before `flock` is reached.
_PROCESS_LOCK = threading.Lock()

#: What `_commit_or_already_applied` reports when git had nothing to commit because a
#: concurrent write already swept the same change into its own commit.
ALREADY_APPLIED = "already applied by a concurrent write"


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


class StoreBusy(MemoryError):
    """Another writer holds the store lock and did not release it in time."""


class WriteNotLanded(MemoryError):
    """The commit was made, but the committed tree does not carry the change.

    The one refusal that must never be swallowed: it means the store's committed
    state disagrees with what this call was about to report.
    """


class StoreMalformed(MemoryError):
    """`MEMORY.md` carries lines that are not store.v1 Core 3 lines.

    Carries the malformed lines (with line numbers) and the commit to restore from,
    so the message names the remedy instead of describing a mystery.
    """

    def __init__(self, message: str, *, check: StoreCheck | None = None) -> None:
        super().__init__(message)
        self.check = check


class GitFailed(MemoryError):
    """A git command failed. One sentence: the operation and git's own first line.

    Never the argv. The steward's session showed why: a failed `forget` surfaced
    `Command '['git', '-c', 'user.name=amplifier-memory', …]'` as the whole answer.
    """

    def __init__(self, message: str, *, nothing_to_commit: bool = False) -> None:
        super().__init__(message)
        self.nothing_to_commit = nothing_to_commit


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
    #: `ALREADY_APPLIED` when git had nothing to commit because a concurrent write
    #: had already swept the same change in. `None` on the ordinary path.
    note: str | None = None


@dataclass
class ForgetResult:
    id: str
    text: str
    target: str
    commit: str
    note: str | None = None


@dataclass
class MalformedLine:
    """One line of `MEMORY.md` that is not a store.v1 Core 3 line."""

    lineno: int
    line: str

    def render(self) -> str:
        shown = self.line if len(self.line) <= 60 else self.line[:57] + "…"
        return f"line {self.lineno}: {shown!r}"


@dataclass
class StoreCheck:
    """What `verify_store` found: the malformed lines, and where to restore from."""

    home: Path
    target: str
    line_count: int
    malformed: list[MalformedLine] = field(default_factory=list)
    #: The newest commit whose `MEMORY.md` parses clean, or None when no commit does.
    last_clean_commit: str | None = None

    @property
    def ok(self) -> bool:
        return not self.malformed

    def render(self) -> str:
        if self.ok:
            return (
                f"{self.target} is well-formed ({self.line_count} line(s) parse as store.v1 Core 3)"
            )
        found = "; ".join(item.render() for item in self.malformed)
        where = (
            f"last commit whose {self.target} parsed clean: {self.last_clean_commit[:12]}"
            if self.last_clean_commit
            else f"no commit in this store's history has a well-formed {self.target}"
        )
        return (
            f"{self.target} is not well-formed — {len(self.malformed)} malformed line(s): "
            f"{found}; {where}; remedy: `amplifier-memory doctor --repair`"
        )


@dataclass
class RepairResult:
    """What `repair_store` did — the diff first, then the commit it made."""

    home: Path
    target: str
    repaired: bool
    malformed: list[MalformedLine] = field(default_factory=list)
    restored_from: str | None = None
    commit: str | None = None
    diff: str = ""

    def render(self) -> str:
        if not self.repaired:
            return f"nothing to repair: {self.target} is already well-formed"
        head = (
            f"restoring {self.target} from commit {self.restored_from[:12]} "
            f"(malformed lines: {len(self.malformed)})"
        )
        found = "\n".join(f"  {item.render()}" for item in self.malformed)
        return "\n".join(
            [
                head,
                found,
                "",
                self.diff.rstrip("\n") or "  (no textual difference)",
                "",
                (
                    f"committed {self.commit[:12]}: {self.target} restored from "
                    f"{self.restored_from[:12]}"
                ),
            ]
        )


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


# --------------------------------------------------------------------------- the lock


def _lock_path(home: Path) -> Path:
    """Where the store's write lock lives — inside `.git/`, never among the store's files.

    store.v1 Core 2: a file not listed there is not memory. The lock is plumbing, so it
    is not placed beside `MEMORY.md` at all; `.git/` is git's own directory, already
    excluded from every listing of the store and from `git status`. The fallback path is
    for a store directory that is not yet a repository (only reachable inside `init`).
    """
    git_dir = home / ".git"
    if git_dir.is_dir():
        return git_dir / LOCK_NAME
    return home / f".{LOCK_NAME}"


@contextmanager
def _exclusive(home: Path, *, timeout: float | None = None) -> Iterator[Path]:
    """Hold the store's write lock, or raise `StoreBusy` after a bounded wait.

    Two layers, in this order every time (so the order can never deadlock): the
    process-level `threading.Lock` first, then `fcntl.flock` on a per-call open file
    description. The first serializes threads of this process — `flock` alone would not,
    because it is per open file description. The second serializes processes.
    """
    budget = LOCK_TIMEOUT_S if timeout is None else timeout
    deadline = time.monotonic() + budget
    if not _PROCESS_LOCK.acquire(timeout=budget):
        raise StoreBusy(
            f"the memory store at {home} is busy: another thread of this session held the "
            f"write lock for more than {budget:g}s; nothing was written"
        )
    try:
        path = _lock_path(home)
        path.parent.mkdir(parents=True, exist_ok=True)
        fd = os.open(path, os.O_RDWR | os.O_CREAT | os.O_CLOEXEC, 0o600)
        try:
            while True:
                try:
                    fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
                    break
                except OSError:
                    if time.monotonic() >= deadline:
                        raise StoreBusy(
                            f"the memory store at {home} is busy: another process held the "
                            f"write lock for more than {budget:g}s; nothing was written"
                        ) from None
                    time.sleep(_LOCK_POLL_S)
            try:
                yield path
            finally:
                fcntl.flock(fd, fcntl.LOCK_UN)
        finally:
            os.close(fd)
    finally:
        _PROCESS_LOCK.release()


# --------------------------------------------------------------------------- git, honestly


@contextmanager
def _git_step(operation: str, home: Path) -> Iterator[None]:
    """Turn a failed git command into one sentence naming the operation and git's reason.

    Never the argv: a tool result that is a `subprocess` repr tells the human nothing
    they can act on, and it is what the steward saw when a concurrent `forget` failed.
    """
    try:
        yield
    except subprocess.CalledProcessError as exc:
        reason = _git.first_error_line(exc)
        if _git.is_nothing_to_commit(exc):
            raise GitFailed(
                f"git had nothing to commit for {operation} in the memory store at {home}: "
                f"{reason}",
                nothing_to_commit=True,
            ) from exc
        raise GitFailed(
            f"git {operation} failed in the memory store at {home}: {reason}"
        ) from exc


def _commit_or_already_applied(
    home: Path, message: str, paths: list[str], *, operation: str
) -> tuple[str, str | None]:
    """One commit, or an honest note that a concurrent write already carried the change.

    `git commit` with nothing staged is not a failure here: under the lock it means the
    change this call was going to make is already in the committed tree. The caller still
    verifies the committed tree before reporting anything.
    """
    try:
        with _git_step(operation, home):
            return _git.commit(home, message, paths, identity=STORE_IDENTITY), None
    except GitFailed as exc:
        if not exc.nothing_to_commit:
            raise
        with _git_step("rev-parse", home):
            return _git.head(home), ALREADY_APPLIED


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
        with _git_step("init", path):
            _git.init_repo(path)

    with _exclusive(path):
        # Re-checked under the lock: a concurrent `init` may have finished while this
        # one waited, and two initial commits would not be "one commit per mutation".
        if (path / "MEMORY.md").is_file() and _git.commit_count(path) > 0:
            return InitResult(home=path, existed=True, created=[], commit=None)

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
        sha, _ = _commit_or_already_applied(
            path, "init: memory store (store.v1 Core 2 layout)", paths, operation="commit"
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


def wellformed(line: str) -> bool:
    """store.v1 Core 3: a memory line, a `## heading`, a comment, or a blank line.

    Anything else — the headless fragment a clobbered write leaves behind — is not.
    """
    stripped = line.strip()
    if stripped == "":
        return True
    if stripped.startswith("#"):
        return True
    return _LINE_RE.match(line) is not None


def _malformed(text: str) -> list[MalformedLine]:
    return [
        MalformedLine(lineno=number, line=line)
        for number, line in enumerate(text.splitlines(), start=1)
        if not wellformed(line)
    ]


def verify_store(
    home: str | os.PathLike[str] | None = None, *, target: str = "MEMORY.md"
) -> StoreCheck:
    """Report every line of `MEMORY.md` that is not a store.v1 Core 3 line.

    Reads only — no write, no stage, no commit — so `doctor` can call it (cli.v1 Core 5).
    Also finds the newest commit whose `MEMORY.md` parses clean, which is what
    `repair_store` restores and what the `doctor` row names.
    """
    path = _require_store(home)
    text = (path / target).read_text(encoding="utf-8")
    check = StoreCheck(
        home=path,
        target=target,
        line_count=len(text.splitlines()),
        malformed=_malformed(text),
    )
    if check.malformed:
        check.last_clean_commit = _last_clean_commit(path, target)
    return check


def _last_clean_commit(home: Path, target: str) -> str | None:
    """The newest commit whose `target` exists and parses clean, or None."""
    for record in _git.log_records(home):
        committed = _git.show(home, f"{record['sha']}:{target}")
        if committed is None:
            continue
        if not _malformed(committed):
            return record["sha"]
    return None


def repair_store(
    home: str | os.PathLike[str] | None = None, *, target: str = "MEMORY.md"
) -> RepairResult:
    """Restore `MEMORY.md` from the last commit whose lines parse, in one visible commit.

    The one sanctioned repair. The steward repaired their store by hand once, with bash,
    because nothing else could (VISION principle 4 says the model never edits the store
    directly). This is that path, in code: it names the malformed lines, shows the diff
    it is about to apply, restores, commits, and re-reads the committed tree to prove it.
    """
    path = _require_store(home)
    with _exclusive(path):
        check = verify_store(path, target=target)
        if check.ok:
            return RepairResult(home=path, target=target, repaired=False)
        if check.last_clean_commit is None:
            raise StoreMalformed(
                f"cannot repair {target}: {len(check.malformed)} malformed line(s) "
                f"({'; '.join(item.render() for item in check.malformed)}) and no commit in "
                f"this store's history has a well-formed {target}; the fix is an edit by hand",
                check=check,
            )
        current = (path / target).read_text(encoding="utf-8")
        with _git_step("show", path):
            restored = _git.show(path, f"{check.last_clean_commit}:{target}")
        if restored is None:  # pragma: no cover - _last_clean_commit only returns readable shas
            raise StoreMalformed(
                f"cannot repair {target}: commit {check.last_clean_commit[:12]} no longer "
                f"carries {target}",
                check=check,
            )
        diff = "".join(
            difflib.unified_diff(
                current.splitlines(keepends=True),
                restored.splitlines(keepends=True),
                fromfile=f"a/{target} (now, malformed)",
                tofile=f"b/{target} (commit {check.last_clean_commit[:12]})",
            )
        )
        (path / target).write_text(restored, encoding="utf-8")
        sha, _ = _commit_or_already_applied(
            path,
            f"repair: restore {target} from {check.last_clean_commit[:12]} "
            f"(malformed lines: {len(check.malformed)})",
            [target],
            operation="commit",
        )
        after = _committed(path, target)
        if after is None or _malformed(after):
            raise WriteNotLanded(
                f"repair of {target} did not land: the committed tree at {sha[:12]} still "
                f"does not parse as store.v1 Core 3"
            )
        return RepairResult(
            home=path,
            target=target,
            repaired=True,
            malformed=check.malformed,
            restored_from=check.last_clean_commit,
            commit=sha,
            diff=diff,
        )


# --------------------------------------------------------------------------- verify after commit


def _committed(home: Path, target: str) -> str | None:
    """`target` as the committed tree has it — the only state worth asserting on.

    The working tree can legitimately be mid-hand-edit (store.v1 Core 9), so a writer
    that checked the working tree would be checking the wrong thing.
    """
    with _git_step("show", home):
        return _git.show(home, f"HEAD:{target}")


def _require_wellformed(home: Path, target: str = "MEMORY.md") -> None:
    """Refuse to write into a store whose `MEMORY.md` is already corrupt.

    Checked before the write, not after, so a refusal never leaves a half-applied
    change and never blames this call for damage it did not do.
    """
    check = verify_store(home, target=target)
    if not check.ok:
        raise StoreMalformed(f"refused: {check.render()}", check=check)


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

    # One writer at a time: everything from here to the commit is a read-modify-write of
    # a file plus a git commit, and two of those interleaved is what corrupted the
    # steward's store on 2026-09-06.
    with _exclusive(path):
        # Refuse to write into a store that is already corrupt, before touching anything:
        # a refusal now names the remedy, where a write would bury the damage deeper.
        _require_wellformed(path)
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
            raise WriteNotLanded(f"write to {target} did not land; refusing to commit")
        sha, note = _commit_or_already_applied(
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
            operation="commit",
        )
        _assert_saved(path, target, line, sha)
    return SaveResult(id=mid, text=text, target=target, commit=sha, line=line, note=note)


def _assert_saved(home: Path, target: str, line: str, sha: str) -> None:
    """The committed tree carries this exact line, and `MEMORY.md` still parses.

    session.v1 Core 5 says the writer commits and a refusal is returned with the reason.
    Reporting a save whose line is not in the committed tree is neither — it is a lie the
    human only discovers when the memory is gone. So this is asserted, and a failure
    raises rather than returning a `SaveResult`.
    """
    committed = _committed(home, target)
    if committed is None or line not in committed.splitlines():
        raise WriteNotLanded(
            f"the memory was not saved: commit {sha[:12]} was made, but the committed "
            f"{target} does not carry {line!r}; nothing was reported as saved"
        )
    if target == "MEMORY.md":
        broken = _malformed(committed)
        if broken:
            raise WriteNotLanded(
                f"the memory was not saved cleanly: commit {sha[:12]} left "
                f"{len(broken)} malformed line(s) in {target} "
                f"({'; '.join(item.render() for item in broken)}); "
                "remedy: `amplifier-memory doctor --repair`"
            )


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

    # One writer at a time (see `save`): two concurrent forgets are exactly the pair that
    # produced a raw git error in the steward's session while both removals had landed.
    with _exclusive(path):
        _require_wellformed(path)
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
                    (_parse(other) or ("", ""))[0] == memory_id
                    for other in _read_lines(source_path)
                ):
                    raise WriteNotLanded(
                        f"forget of {memory_id} did not land; refusing to commit"
                    )
                quote = ""
                try:
                    for record in why(memory_id, home=path):
                        if record["action"] == "save" and isinstance(record["quote"], str):
                            quote = record["quote"]
                            break
                except UnknownId:  # hand-added line with no commit of its own (Core 9)
                    quote = ""
                sha, note = _commit_or_already_applied(
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
                    operation="commit",
                )
                _assert_forgotten(path, source, memory_id, sha)
                return ForgetResult(
                    id=memory_id, text=text, target=source, commit=sha, note=note
                )

    raise UnknownId(f"unknown memory id {memory_id!r}: no such line in MEMORY.md or topics/")


def _assert_forgotten(home: Path, target: str, memory_id: str, sha: str) -> None:
    """The committed tree no longer carries the id. The mirror of `_assert_saved`."""
    committed = _committed(home, target)
    still_there = [
        line
        for line in (committed or "").splitlines()
        if (_parse(line) or ("", ""))[0] == memory_id
    ]
    if still_there:
        raise WriteNotLanded(
            f"{memory_id} was not forgotten: commit {sha[:12]} was made, but the committed "
            f"{target} still carries {still_there[0]!r}; nothing was reported as forgotten"
        )


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
    # Read-modify-write plus a commit, exactly like `save`: the same lock, for the same
    # reason. A usage log that ate a save's commit would be the same defect wearing a hat.
    with _exclusive(path):
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
            _commit_or_already_applied(
                path,
                f"usage: {event} {target} (session {session_id})",
                ["usage.jsonl"],
                operation="commit",
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
