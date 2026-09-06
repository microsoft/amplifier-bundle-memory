"""The memory store writer — the reference implementation of store.v2.

Every behaviour the CLI, the memory tool, the inject hook and the Phase 2 job
expose lives here (AGENTS.md rule 11, cli.v2 §9). This module imports only
the standard library: no `click`, no `amplifier_*`.

store.v2 clause map
-------------------
§1  location; one commit per change, none for a usage append `store_home`, `log_usage`
§2  fixed layout ................................. `init`, `LAYOUT_FILES`
§3  MEMORY.md flat list, 200-line cap ............ `save`, `MEMORY_LINE_CAP`
§4  the cap is enforced by the writer ............ `CapExceeded`
§5  topic files, 150 lines / 50 files ............ `save(topic=...)`
§6  provenance lives in git: `action`, `was:`,
    and a `forgot` subject ....................... `_commit_message`, `edit`, `why`
§7  declined.md .................................. created by `init` (Phase 2 writes it)
§8  usage.jsonl: loaded/read/cited, 90 days,
    never committed .............................. `log_usage`, `record_citation`
§9  two writers, one path ........................ hand edits read back by `list_memories`;
        the writer names itself per commit (`STORE_IDENTITY`); the store repo carries no
        identity of its own, so a hand commit is attributed to the human
§10 bounded by construction ...................... the caps above, plus §1's exception:
        git history grows only with changes a human made or approved

Reading leaves no commit behind (§1, §8, §10)
---------------------------------------------
A session that only *loads* memory used to leave one commit per load — four
`usage: loaded` commits landed in one afternoon on the steward's store, for sessions
that changed nothing. store.v2 §1 makes the usage append the one exception to "every
mutation is one commit": `log_usage` writes the file and stops. `usage.jsonl` is
therefore untracked inside the store (`init` writes the store's `.gitignore`), and a
store created before v2 is migrated by `_untrack_usage` in one visible commit, once.

One writer at a time (Core 1, Core 9)
-------------------------------------
Every mutating path here runs inside `_exclusive()`: an `fcntl.flock` on a lock file,
plus a process-level `threading.Lock` because `flock` is per open file description and
two threads of one process would otherwise share nothing. Concurrent `save`/`forget`/
`log_usage` calls — threads of one session, or several sessions at once — serialize on
it, so each leaves exactly one well-formed commit.

The lock file is **plumbing, not memory**: store.v2 Core 2 says a file not listed there
is not memory, so it is never placed among the store's files at all. It lives inside the
store's own `.git/` directory (`_lock_path`), which git already owns and no listing of
the store treats as content. That also means no `.gitignore` has to be invented, and a
store created before this writer existed needs no migration.

After the commit, the writer re-reads **both trees** — the committed tree
(`git show HEAD:<file>`) and the working tree file — and asserts its own line is present
(`save`) or absent (`forget`) in each. A write that did not land raises `WriteNotLanded`;
success is never reported on the strength of one tree alone. Two trees, because they are
read by different consumers: `why` and `status` read git, while the inject hook reads the
**working** file on every `provider:request`. A save that was refused but left corruption
in the working tree is published to the model on the next request, indefinitely.

Nothing half-written survives a refusal (store.v2 Core 1: every mutation is one commit)
-------------------------------------------------------------------------------------
Every file this writer touches is written by `_atomic_write` — a temp file in the same
directory, `fsync`, then `os.replace`, which is atomic on POSIX — so no reader ever sees a
partial line. And every write is wrapped in `_reverting`: if anything after it raises, the
file is restored from `HEAD` and unstaged, leaving `git status --porcelain` empty. Without
that, a save whose commit failed left the new text staged, and the *next* save's `git add`
swept it into an unrelated commit.
"""

from __future__ import annotations

import difflib
import fcntl
import json
import os
import re
import subprocess
import tempfile
import threading
import time
import unicodedata
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from pathlib import Path

from . import _git

# --- store.v2 Core 3 / Core 5: the caps, enforced by this writer, not by advice.
MEMORY_LINE_CAP = 200
TOPIC_LINE_CAP = 150
TOPIC_FILE_CAP = 50
# --- store.v2 Core 8
USAGE_RETENTION_DAYS = 90

# --- store.v2 §2: the fixed layout. Nothing else is memory.
LAYOUT_FILES = ("MEMORY.md", "declined.md", "inbox.md", "usage.jsonl")
LAYOUT_DIRS = ("topics",)
# `topics/` must survive a clone; git does not track empty directories.
TOPICS_KEEP = "topics/.gitkeep"

#: store.v2 §1/§8: `usage.jsonl` is memory, but it is never committed — so it is the one
#: layout file git does not track. Everything else `init` creates is committed.
UNTRACKED_LAYOUT_FILES = ("usage.jsonl",)
TRACKED_LAYOUT_FILES = tuple(f for f in LAYOUT_FILES if f not in UNTRACKED_LAYOUT_FILES)

#: store.v2 §2: "`.lock` and `.gitignore` inside the store are plumbing, not memory."
STORE_GITIGNORE = ".gitignore"
GITIGNORE_BODY = (
    "# Plumbing, not memory (store.v2 \u00a72).\n"
    "#\n"
    "# store.v2 \u00a71: appends to usage.jsonl are written without a commit, so a session\n"
    "# that only reads memory leaves no commit behind. usage.jsonl is still memory\n"
    "# (\u00a72 lists it) and still on disk \u2014 it is simply not tracked.\n"
    "usage.jsonl\n"
)

#: The subject of the one-time migration commit on a store created before store.v2.
UNTRACK_USAGE_SUBJECT = "store: stop tracking usage.jsonl (store.v2 \u00a71)"
UNTRACK_USAGE_MESSAGE = f"""{UNTRACK_USAGE_SUBJECT}

One-time migration, made under the write lock on the first usage append after this
version was installed (on the steward's device, by `amplifier-memory update`). Before
store.v2 every `loaded` event was committed: four `usage: loaded` commits landed in one
afternoon on the steward's store for sessions that changed nothing. store.v2 \u00a71 makes
reading commit-free, so usage.jsonl is untracked from here on and the store's .gitignore
says so.

Nothing is deleted: `git rm --cached` leaves the working-tree file and every line of its
history exactly as they are. This commit is made once; every later append writes the file
and stops.

action: untrack
target: usage.jsonl"""

WRITERS = ("human", "assistant", "suggestion")
# store.v2 §8: `cited` joins loaded/read so `status` can derive a citation rate.
USAGE_EVENTS = ("loaded", "read", "cited")
#: A `cited` event's target is a memory id, not a file (store.v2 §8).
_CITED_TARGET_RE = re.compile(r"^m-\d{3,6}$")

#: store.v2 §6: "A forget's first line reads `forgot [m-017] …` so a removal is never
#: mistaken for a creation in `git log --oneline`."
FORGOT_PREFIX = "forgot "

# The identity this library's own commits carry, applied per commit with
# `git -c user.name=… -c user.email=…` (store.v2 Core 1: every mutation is one
# commit; Core 9: `git log` attributes each writer). It is deliberately NOT written
# into the store repository's config: a human's own `git commit` in the store must
# be attributed to the human, not to this tool.
STORE_USER_NAME = "amplifier-memory"
STORE_USER_EMAIL = "amplifier-memory@localhost"
STORE_IDENTITY = (STORE_USER_NAME, STORE_USER_EMAIL)

# store.v2 Core 3: `m-NNN`, assigned by code. Bounded on purpose — `m-\d+` accepts a
# digit run of any length, so a hand-edited or pasted line could hand `int()` an
# arbitrarily long number and `_next_id` an arbitrarily large one. Three to six digits
# spans m-001 .. m-999999, which is 5,000x the 200-line cap.
_ID_RE = re.compile(r"\[(m-\d{3,6})\]")
_LINE_RE = re.compile(r"^\s*-\s*\[(m-\d{3,6})\]\s*(.*)$")
_SLUG_RE = re.compile(r"^[a-z0-9][a-z0-9._-]*$")

# --- store.v2 Core 3: one memory is one line, and Python's idea of "one line" is wider
# than "\n". `str.splitlines()` splits on all of these, so a text carrying one becomes two
# lines on disk while the writer believes it wrote one — the exact shape of the U+2028
# corruption the engineering council reproduced on 2026-09-06.
LINE_SEPARATORS = (
    "\n",
    "\r",
    "\v",
    "\f",
    "\x1c",
    "\x1d",
    "\x1e",
    "\x85",
    "\u2028",
    "\u2029",
)

#: A safety bound on one memory line, in bytes of UTF-8. store.v2 R2 leaves per-line
#: length open in v1, and this is **not** a style rule: it is the bound that keeps a
#: pasted log out of a commit message and out of `MEMORY.md`. 2,000 bytes is ~10x the
#: ~200 characters R2 names as the point to revisit, so no ordinary memory meets it.
MEMORY_BYTE_CAP = 2000

#: session.v2 Core 5's quote floor, for a quote that is a *fragment* of a longer human
#: turn. A quote that is an entire human turn identifies that turn exactly and is exempt.
#: Reproduced by the engineering council: `quote='e'` against the turn "Great remember
#: these for me" authorised a memory the human never stated.
QUOTE_MIN_CHARS = 15
QUOTE_MIN_WORDS = 3

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
    """A write would exceed a store.v2 cap. Carries the cap and the remedy."""

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
    """`MEMORY.md` carries lines that are not store.v2 Core 3 lines.

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
    """One line of `MEMORY.md` that is not a store.v2 Core 3 line."""

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
    #: Byte offset of the first byte of the file that is not UTF-8, or None when it
    #: decodes clean. A file that does not decode is malformed in a way no line number
    #: can name, so the offset is reported instead — and never as a traceback.
    decode_error_offset: int | None = None

    @property
    def ok(self) -> bool:
        return not self.malformed and self.decode_error_offset is None

    def render(self) -> str:
        if self.ok:
            return (
                f"{self.target} is well-formed ({self.line_count} line(s) parse as store.v2 Core 3)"
            )
        if self.decode_error_offset is not None:
            where = (
                f"last commit whose {self.target} parsed clean: {self.last_clean_commit[:12]}"
                if self.last_clean_commit
                else f"no commit in this store's history has a well-formed {self.target}"
            )
            return (
                f"{self.target} well-formed \u2014 byte offset {self.decode_error_offset} is not "
                f"UTF-8; {where}; remedy: `amplifier-memory doctor --repair`"
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
    #: Every line the restore threw away, in file order, each truncated to
    #: `DISCARD_PREVIEW_CHARS`. A repair that deletes a memory must say which memory it
    #: deleted: the council reproduced `repair_store` restoring `MEMORY.md` to `''` —
    #: correct behaviour, undisclosed consequence.
    discarded: list[str] = field(default_factory=list)

    def render(self) -> str:
        if not self.repaired:
            return f"nothing to repair: {self.target} is already well-formed"
        head = (
            f"restoring {self.target} from commit {self.restored_from[:12]} "
            f"(malformed lines: {len(self.malformed)})"
        )
        found = "\n".join(f"  {item.render()}" for item in self.malformed)
        discarded = "\n".join(
            [f"  discarding {len(self.discarded)} line(s) not in that commit:"]
            + [f"    {line}" for line in self.discarded]
        ) if self.discarded else "  discarding nothing: every current line is in that commit"
        return "\n".join(
            [
                head,
                found,
                discarded,
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
    """store.v2 Core 1: ``${AMPLIFIER_MEMORY_HOME:-~/.amplifier/memory}``."""
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

    store.v2 Core 2: a file not listed there is not memory. The lock is plumbing, so it
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


# --------------------------------------------------------------------------- writing to disk


def _atomic_write(path: Path, text: str) -> None:
    """Write `text` to `path` in one indivisible step, or not at all.

    A temp file in the **same directory** (so `os.replace` stays within one filesystem),
    flushed and `fsync`ed, then `os.replace` — atomic on POSIX. A reader of `MEMORY.md`
    therefore sees either every line of the old file or every line of the new one, never
    a half-written file. The inject hook reads that file on every model request, so a
    torn read is a corrupt memory delivered to the model.

    The temp file is not memory (store.v2 Core 2 lists what is): it lives for the length
    of this call, is named `.<file>.<random>.tmp`, and is removed on any failure.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=str(path.parent), prefix=f".{path.name}.", suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as handle:
            handle.write(text)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(tmp, path)
    except BaseException:
        Path(tmp).unlink(missing_ok=True)
        raise


def _restore_from_head(home: Path, targets: list[str]) -> None:
    """Put `targets` back exactly as HEAD has them, in the working tree and the index.

    Both halves matter. The working tree is what the inject hook reads on every model
    request; the index is what the *next* commit would sweep up.
    """
    for target in targets:
        committed = _git.show(home, f"HEAD:{target}")
        path = home / target
        if committed is None:
            path.unlink(missing_ok=True)
        else:
            _atomic_write(path, committed)
    _git.unstage(home, targets)


@contextmanager
def _reverting(home: Path, targets: list[str]) -> Iterator[None]:
    """Undo any write to `targets` if the block raises. The refusal is then the truth.

    Before this existed, a save that raised after writing left the new text in the
    working tree (published to the model by the inject hook on the next request) and in
    the index (committed by the next unrelated write). A refusal that leaves the change
    behind is not a refusal.
    """
    try:
        yield
    except BaseException as failure:
        try:
            _restore_from_head(home, targets)
        except Exception as rollback:  # noqa: BLE001 - the original refusal is still the answer
            # Never swallowed: the original failure is what the caller asked about, but a
            # failed rollback means the store really is left dirty, and saying so is the
            # difference between a refusal and a lie.
            failure.add_note(
                f"the rollback of {targets} also failed ({type(rollback).__name__}: "
                f"{rollback}); the store at {home} may be left dirty \u2014 run "
                "`amplifier-memory doctor`"
            )
        raise


# --------------------------------------------------------------------------- reading, tolerantly


def _decode(raw: bytes) -> tuple[str, int | None]:
    """`raw` as text, plus the byte offset of the first byte that is not UTF-8.

    store.v2 Core 9 invites hand edits, so one accented byte typed in an editor with the
    wrong encoding is a thing that happens. Before this, that byte raised
    `UnicodeDecodeError` out of six functions including `doctor`, the designated remedy.
    """
    try:
        return raw.decode("utf-8"), None
    except UnicodeDecodeError as exc:
        return raw.decode("utf-8", errors="replace"), exc.start


def _read_text(path: Path) -> str:
    """Every read of a store file goes through here: explicit UTF-8, never raising."""
    if not path.exists():
        return ""
    return _decode(path.read_bytes())[0]


def read_memory_text(
    home: str | os.PathLike[str] | None = None, *, target: str = "MEMORY.md"
) -> str:
    """The text of a store file, read the one tolerant way — for wrappers.

    AGENTS.md rule 11: no wrapper carries logic, and reading the store is logic.
    Both wrappers used to call `Path.read_text(encoding="utf-8")` themselves, which
    raises `UnicodeDecodeError` on one accented byte a human left with the wrong
    editor encoding — and store.v2 Core 9 explicitly invites those hand edits. In
    the inject hook that read runs on *every* provider request. This returns what
    every other reader in this module sees: the undecodable byte as U+FFFD
    (`errors="replace"`), never an exception. The byte itself is not swallowed —
    `verify_store` reports its offset, and the `doctor` row names the remedy.

    A store that is not there is still an error (`StoreMissing`): "no memories" and
    "no store" are different facts, and session.v2 §10's fail-open path is where the
    second one belongs.
    """
    return _read_text(_require_store(home) / target)


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
    """cli.v2 Core 8 / store.v2 Core 2: create the layout and the initial commit.

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
        gitignore = path / STORE_GITIGNORE
        if not gitignore.exists():
            gitignore.write_text(GITIGNORE_BODY, encoding="utf-8")
            created.append(STORE_GITIGNORE)

        # store.v2 §1: `usage.jsonl` exists on disk but is never committed, so it is
        # created above and left out of the commit — `git add` on an ignored path errors.
        paths = [*TRACKED_LAYOUT_FILES, TOPICS_KEEP, STORE_GITIGNORE]
        # AGENTS.md rule 10: assert the post-state before the commit; gate on the assert.
        missing = [
            p for p in (*LAYOUT_FILES, TOPICS_KEEP, STORE_GITIGNORE) if not (path / p).is_file()
        ]
        if missing:
            raise StoreMissing(f"init failed to create {missing} under {path}")
        sha, _ = _commit_or_already_applied(
            path, "init: memory store (store.v2 \u00a72 layout)", paths, operation="commit"
        )
    return InitResult(home=path, existed=False, created=sorted(created), commit=sha)


# --------------------------------------------------------------------------- reading


def _read_lines(path: Path) -> list[str]:
    text = _read_text(path)
    if text == "":
        return []
    return text.splitlines()


def _count_lines(path: Path) -> int:
    """store.v2 Core 3: headings and blank lines count toward the cap."""
    return len(_read_lines(path))


def _parse(line: str) -> tuple[str, str] | None:
    match = _LINE_RE.match(line)
    if match is None:
        return None
    return match.group(1), match.group(2).strip()


def list_memories(
    home: str | os.PathLike[str] | None = None, *, include_topics: bool = False
) -> list[dict[str, object]]:
    """Every memory line in ``MEMORY.md`` (store.v2 Core 3), in file order."""
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
    """store.v2 Core 3: a memory line, a `## heading`, a comment, or a blank line.

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
    """Report every line of `MEMORY.md` that is not a store.v2 Core 3 line.

    Reads only — no write, no stage, no commit — so `doctor` can call it (cli.v2 Core 5).
    Also finds the newest commit whose `MEMORY.md` parses clean, which is what
    `repair_store` restores and what the `doctor` row names.
    """
    path = _require_store(home)
    raw = (path / target).read_bytes() if (path / target).exists() else b""
    text, offset = _decode(raw)
    check = StoreCheck(
        home=path,
        target=target,
        line_count=len(text.splitlines()),
        malformed=_malformed(text) if offset is None else [],
        decode_error_offset=offset,
    )
    if not check.ok:
        check.last_clean_commit = _last_clean_commit(path, target)
    return check


def _last_clean_commit(home: Path, target: str) -> str | None:
    """The newest commit whose `target` exists, decodes as UTF-8, and parses clean.

    Read as bytes and decoded strictly: a commit carrying a byte that is not UTF-8 is not
    a commit worth restoring from, and a tolerant decode would hide exactly that.
    """
    for record in _git.log_records(home):
        raw = _git.show_bytes(home, f"{record['sha']}:{target}")
        if raw is None:
            continue
        committed, offset = _decode(raw)
        if offset is not None:
            continue
        if not _malformed(committed):
            return record["sha"]
    return None


#: How much of a discarded line `repair_store` shows. Long enough to recognise a memory,
#: short enough that a pasted blob cannot bury the rest of the report.
DISCARD_PREVIEW_CHARS = 120


def _preview(line: str) -> str:
    return line if len(line) <= DISCARD_PREVIEW_CHARS else line[: DISCARD_PREVIEW_CHARS - 1] + "\u2026"


def repair_store(
    home: str | os.PathLike[str] | None = None,
    *,
    target: str = "MEMORY.md",
    announce: Callable[[str], None] | None = None,
) -> RepairResult:
    """Restore `MEMORY.md` from the last commit whose lines parse, in one visible commit.

    The one sanctioned repair. The steward repaired their store by hand once, with bash,
    because nothing else could (VISION principle 4 says the model never edits the store
    directly). This is that path, in code: it names the malformed lines, **says which
    lines it is about to throw away**, shows the diff, restores, commits, and re-reads the
    committed tree to prove it.

    `announce` receives each line of that report *before* the write and the commit, so a
    human watching a terminal sees what is being discarded while it can still be copied
    out. It defaults to `print`; pass a collector to capture it instead.
    """
    say = print if announce is None else announce
    path = _require_store(home)
    with _exclusive(path):
        check = verify_store(path, target=target)
        if check.ok:
            return RepairResult(home=path, target=target, repaired=False)
        if check.last_clean_commit is None:
            raise StoreMalformed(
                f"cannot repair {target}: {check.render()} and no commit in this store's "
                f"history has a well-formed {target}; the fix is an edit by hand",
                check=check,
            )
        current = _read_text(path / target)
        with _git_step("show", path):
            restored = _git.show(path, f"{check.last_clean_commit}:{target}")
        if restored is None:  # pragma: no cover - _last_clean_commit only returns readable shas
            raise StoreMalformed(
                f"cannot repair {target}: commit {check.last_clean_commit[:12]} no longer "
                f"carries {target}",
                check=check,
            )
        keeping = set(restored.splitlines())
        discarded = [_preview(line) for line in current.splitlines() if line not in keeping]
        diff = "".join(
            difflib.unified_diff(
                current.splitlines(keepends=True),
                restored.splitlines(keepends=True),
                fromfile=f"a/{target} (now, malformed)",
                tofile=f"b/{target} (commit {check.last_clean_commit[:12]})",
            )
        )

        # Said before anything is written or committed: this is the human's only chance
        # to see a memory that is about to stop existing.
        say(
            f"repair: restoring {target} from commit {check.last_clean_commit[:12]} "
            f"({check.render()})"
        )
        if discarded:
            say(f"repair: discarding {len(discarded)} line(s) not in that commit:")
            for line in discarded:
                say(f"repair:   {line}")
        else:
            say("repair: discarding nothing: every current line is in that commit")

        with _reverting(path, [target]):
            _atomic_write(path / target, restored)
            sha, _ = _commit_or_already_applied(
                path,
                f"repair: restore {target} from {check.last_clean_commit[:12]} "
                f"(malformed lines: {len(check.malformed)}, discarded lines: {len(discarded)})",
                [target],
                operation="commit",
            )
            after = _committed(path, target)
            if after is None or _malformed(after):
                raise WriteNotLanded(
                    f"repair of {target} did not land: the committed tree at {sha[:12]} still "
                    f"does not parse as store.v2 Core 3"
                )
        return RepairResult(
            home=path,
            target=target,
            repaired=True,
            malformed=check.malformed,
            restored_from=check.last_clean_commit,
            commit=sha,
            diff=diff,
            discarded=discarded,
        )


# --------------------------------------------------------------------------- verify after commit


def _committed(home: Path, target: str) -> str | None:
    """`target` as the committed tree has it — the only state worth asserting on.

    The working tree can legitimately be mid-hand-edit (store.v2 Core 9), so a writer
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
    """store.v2 Core 5: the topic files, as ``topics/<slug>.md`` paths."""
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
    *,
    mid: str,
    text: str,
    quote: str,
    session_id: str,
    writer: str,
    action: str,
    target: str,
    was: str | None = None,
    suggestion_session: str | None = None,
) -> str:
    """store.v2 §6: id, text, verbatim quote, session, writer, action — in every message.

    Two shapes the subject carries on purpose:

    * a **forget** reads ``forgot [m-017] …``, so `git log --oneline` never shows a
      removal and a creation as the same line (the Dana persona run read a forget as a
      save because they were identical);
    * an **edit** also carries ``was: "<previous text>"``, so `why` can show the
      refinement rather than only its result.

    A **suggestion** (suggestions.v1 Core 6) carries a third: ``suggestion-session:
    <id>``, the session the quote was taken *from*, which is not the session that
    accepted it. `session:` stays the reviewing session, so `why` answers both "who
    accepted this" and "where did the human actually say it".
    """
    subject = f"{FORGOT_PREFIX}[{mid}] {text}" if action == "forget" else f"[{mid}] {text}"
    lines = [
        subject,
        "",
        f"quote: {json.dumps(quote, ensure_ascii=False)}",
    ]
    if was is not None:
        lines.append(f"was: {json.dumps(was, ensure_ascii=False)}")
    lines += [
        f"session: {session_id}",
        f"writer: {writer}",
        f"action: {action}",
        f"target: {target}",
    ]
    if suggestion_session is not None:
        lines.append(f"suggestion-session: {suggestion_session}")
    return "\n".join(lines)


def _field(body: str, name: str) -> str | None:
    for line in body.splitlines():
        if line.startswith(f"{name}: "):
            return line[len(name) + 2 :]
    return None


def _json_field(body: str, name: str) -> str | None:
    """A field this writer stored as JSON (`quote`, `was`), decoded — or as written."""
    raw = _field(body, name)
    if raw is None:
        return None
    try:
        decoded = json.loads(raw)
    except json.JSONDecodeError:
        return raw
    return decoded if isinstance(decoded, str) else raw


def commit_subject_memory(body: str) -> tuple[str, str]:
    """The (id, text) a commit subject names, tolerating store.v2 §6's `forgot` marker.

    Public because `status` needs it too: a forget's subject is ``forgot [m-002] …``,
    which the ordinary memory-line regex does not match, and a caller that stripped the
    marker itself would be carrying logic the library owns (AGENTS.md rule 11).
    """
    subject = body.splitlines()[0] if body else ""
    bare = subject.removeprefix(FORGOT_PREFIX)
    parsed = _parse(f"- {bare}")
    return parsed if parsed is not None else ("", bare)


def why(memory_id: str, home: str | os.PathLike[str] | None = None) -> list[dict[str, object]]:
    """store.v2 §6 / cli.v2 §3: ``git log --grep '\\[m-017\\]'``, parsed.

    `was` is None except on an edit, where it is the text the memory carried before.
    """
    path = _require_store(home)
    records = _git.log_records(path, grep=rf"\[{memory_id}\]")
    if not records:
        raise UnknownId(f"unknown memory id {memory_id!r}: no commit mentions [{memory_id}]")
    out: list[dict[str, object]] = []
    for record in records:
        found, text = commit_subject_memory(record["body"])
        out.append(
            {
                "commit": record["sha"],
                "date": record["date"],
                "id": found or memory_id,
                "text": text,
                "was": _json_field(record["body"], "was"),
                "quote": _json_field(record["body"], "quote"),
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
    """session.v2 Core 5: the quote must appear verbatim in a human turn — and identify it.

    Two bars, because "appears in" alone was not one. The engineering council saved
    `bkrabach prefers dark mode and lives in Seattle` with `quote='e'` against the real
    turn *"Great remember these for me"*: a single letter satisfied verbatim containment
    while identifying nothing, and `why` would show that quote to a human as the
    justification. So:

    * a quote that **is** an entire human turn identifies it exactly — no floor applies
      (this is `/remember`'s ordinary shape: the human typed the whole line);
    * a quote that is a **fragment** of a longer turn must be at least
      `QUOTE_MIN_CHARS` characters and `QUOTE_MIN_WORDS` words, which is the difference
      between quoting the human and picking a letter out of their sentence.
    """
    turns = list(human_turns or [])
    if not quote.strip():
        raise QuoteNotHuman("refused: the quote is empty; only the human's own words become memory")
    fragment_of = None
    for turn in turns:
        if quote == turn.strip() or quote == turn:
            return
        if quote in turn:
            fragment_of = turn
    if fragment_of is None:
        raise QuoteNotHuman(
            "refused: the quote does not appear verbatim in any human turn of this session "
            f"({len(turns)} turn(s) supplied); tool output and external content can never "
            "become memory"
        )
    if len(quote.strip()) < QUOTE_MIN_CHARS or len(quote.split()) < QUOTE_MIN_WORDS:
        raise QuoteNotHuman(
            f"refused: the quote {quote!r} appears in a human turn only as a fragment "
            "(too short to identify a human turn): a fragment must be at least "
            f"{QUOTE_MIN_CHARS} characters and {QUOTE_MIN_WORDS} words, or be the whole "
            "turn; only the human's own words become memory"
        )


def _require_one_line(text: str) -> None:
    """store.v2 Core 3: one memory is one line, in plain UTF-8, within a safety bound.

    Checked **before** anything is opened, locked, or written, so a hostile text never
    reaches the disk at all — the file is byte-identical after the refusal. Three bars:

    1. **No line separator.** `str.splitlines()` splits on ten characters, not one. A
       text carrying U+2028 was written as two lines while the writer believed it wrote
       one; the writer then raised "did not land" and left the corruption in the working
       tree, which is the file the inject hook feeds the model on every request.
    2. **No control character, and nothing invisible.** A control character (category
       `Cc`, which includes DEL) cannot be read back in a terminal or an editor. An
       invisible formatting character (category `Cf`, which includes the BOM U+FEFF)
       is worse than unreadable: it makes two memories that *look* identical compare
       unequal, so the duplicate check passes and the human sees the same line twice.
    3. **A byte cap.** store.v2 R2 leaves per-line length open, so this is a safety
       bound and not a style rule (see `MEMORY_BYTE_CAP`): a 131 KB text used to be
       refused only when the kernel rejected git's argv, *after* `git add` had staged it.
    """
    for index, char in enumerate(text):
        if char in LINE_SEPARATORS:
            raise ValueError(
                f"refused: memory text contains a line separator (U+{ord(char):04X}) at "
                f"character {index}; one memory is one line"
            )
        category = unicodedata.category(char)
        if category == "Cc":
            raise ValueError(
                f"refused: memory text contains a control character (U+{ord(char):04X}) at "
                f"character {index}; a memory is plain text a human can read back"
            )
        if category in ("Cf", "Cs"):
            raise ValueError(
                f"refused: memory text contains an invisible character (U+{ord(char):04X}) at "
                f"character {index}; two memories that look identical must not differ by a "
                "character no one can see"
            )
    size = len(text.encode("utf-8"))
    if size > MEMORY_BYTE_CAP:
        raise ValueError(
            f"refused: the memory text is {size:,} bytes and the cap is "
            f"{MEMORY_BYTE_CAP:,} bytes; a memory is one line, not a pasted document. "
            "Remedy: save the one sentence that is the standing preference."
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
    suggestion_session: str | None = None,
) -> SaveResult:
    """session.v2 Core 5: the deterministic writer. Verify, refuse, or write one commit.

    `human_turns` are the human messages of the current session; the caller
    supplies them, this library owns the check.

    `suggestion_session` is the one exemption, and it is narrow (suggestions.v1 Core 4
    and Core 6). An accepted inbox item's quote was said in **another** session, days
    ago; the session accepting it has no such turn, so `human_turns` cannot carry it.
    The verification still happened — `suggest.run_suggest` checked that quote verbatim
    against a human turn of the named session in code *before* the item was ever
    proposed (AGENTS.md rule 7 holds either way) — and this argument is where the
    accepting caller names the session it happened in. So: writer `suggestion`
    **requires** `suggestion_session`, and no other writer may pass it. A quote with no
    source session named is refused, which keeps the exemption auditable in `git log`
    rather than making it a hole.
    """
    path = _require_store(home)
    text = text.strip()
    if not text:
        raise ValueError("refused: the memory text is empty")
    _require_one_line(text)
    if writer not in WRITERS:
        raise ValueError(f"unknown writer {writer!r}: expected one of {WRITERS}")
    if writer == "human" and quote != text:
        raise ValueError(
            "refused: for writer='human' the quote is the text itself "
            f"(text={text!r}, quote={quote!r})"
        )
    if writer == "suggestion":
        if not (suggestion_session or "").strip():
            raise ValueError(
                "refused: writer='suggestion' must name the session its quote was taken "
                "from (suggestion_session=); an accepted suggestion's quote is verified "
                "against that session's human turns when it is proposed, and the commit "
                "records which one"
            )
        if not quote.strip():
            raise QuoteNotHuman(
                "refused: the quote is empty; only the human's own words become memory"
            )
    else:
        if suggestion_session is not None:
            raise ValueError(
                f"refused: suggestion_session is only for writer='suggestion' (got {writer!r})"
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
                        "(store.v2 Core 5); pass topic_purpose="
                    )
                new_lines.append(topic_purpose.strip().splitlines()[0])
            if len(existing) + len(new_lines) + 1 > TOPIC_LINE_CAP:
                raise _topic_line_cap_error(target, len(existing))

        mid = _next_id(path)
        line = f"- [{mid}] {text}"
        body = existing + new_lines + [line]

        # Everything from the write to the assert is reverted as one unit: a refusal
        # after this point restores the file from HEAD and unstages it, so a save that
        # says "did not land" has not landed in the working tree the hook reads either.
        with _reverting(path, [target]):
            _atomic_write(target_path, "\n".join(body) + "\n")

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
                    suggestion_session=suggestion_session,
                ),
                [target],
                operation="commit",
            )
            _assert_saved(path, target, line, sha)
    return SaveResult(id=mid, text=text, target=target, commit=sha, line=line, note=note)


def _assert_saved(home: Path, target: str, line: str, sha: str) -> None:
    """Both trees carry this exact line, and both still parse. Neither one alone.

    session.v2 Core 5 says the writer commits and a refusal is returned with the reason.
    Reporting a save whose line is not in the committed tree is neither — it is a lie the
    human only discovers when the memory is gone. So this is asserted, and a failure
    raises rather than returning a `SaveResult`.

    The **working** tree is asserted too, and it is not a duplicate check: `why` and
    `status` read git, but `hooks-memory-inject` reads the working file on every
    `provider:request`. Wave 4 asserted only the committed tree, so a file that was
    corrupt on disk and clean in git passed — and the corrupt one is the published one.
    """
    for where, content in (
        ("committed", _committed(home, target)),
        ("working-tree", _read_text(home / target)),
    ):
        if content is None or line not in content.splitlines():
            raise WriteNotLanded(
                f"the memory was not saved: commit {sha[:12]} was made, but the {where} "
                f"{target} does not carry {line!r}; nothing was reported as saved"
            )
        if target != "MEMORY.md":
            continue
        broken = _malformed(content)
        if broken:
            raise WriteNotLanded(
                f"the memory was not saved cleanly: commit {sha[:12]} left "
                f"{len(broken)} malformed line(s) in the {where} {target} "
                f"({'; '.join(item.render() for item in broken)}); "
                "remedy: `amplifier-memory doctor --repair`"
            )


def edit(
    memory_id: str,
    new_text: str,
    quote: str,
    writer: str,
    session_id: str,
    human_turns: list[str] | tuple[str, ...] | None = None,
    *,
    home: str | os.PathLike[str] | None = None,
) -> SaveResult:
    """store.v2 §6 / cli.v2 §3: refine a memory in place. Same id, new text, one commit.

    An edit is a **refinement, not a new memory**: the id survives (store.v2 §3), the
    commit carries ``action: edit`` and ``was: "<previous text>"`` (§6), and `status`
    counts the memory from its first write, not from this one
    (`docs/workflow/GATE-DEFINITION-2026-09-06.md`).

    Every refusal `save` makes, this makes too, and for the same reasons: one line, the
    byte cap, no duplicate of a line already present, and a quote that identifies a real
    human turn. An unknown id raises `UnknownId`.
    """
    path = _require_store(home)
    new_text = new_text.strip()
    if not new_text:
        raise ValueError("refused: the memory text is empty")
    _require_one_line(new_text)
    if writer not in WRITERS:
        raise ValueError(f"unknown writer {writer!r}: expected one of {WRITERS}")
    if writer == "human" and quote != new_text:
        raise ValueError(
            "refused: for writer='human' the quote is the text itself "
            f"(text={new_text!r}, quote={quote!r})"
        )
    _check_quote(quote, human_turns)

    # One writer at a time, exactly as `save`: this is a read-modify-write plus a commit.
    with _exclusive(path):
        _require_wellformed(path)
        for source in ["MEMORY.md", *topic_files(path)]:
            source_path = path / source
            lines = _read_lines(source_path)
            for index, line in enumerate(lines):
                parsed = _parse(line)
                if parsed is None or parsed[0] != memory_id:
                    continue
                was = parsed[1]
                if was == new_text:
                    raise DuplicateMemory(
                        f"refused: [{memory_id}] already reads exactly this: {new_text}"
                    )
                for other_index, other in enumerate(lines):
                    if other_index == index:
                        continue
                    other_parsed = _parse(other)
                    if (other_parsed is not None and other_parsed[1] == new_text) or (
                        other.strip() == new_text
                    ):
                        raise DuplicateMemory(
                            f"refused: {source} already carries this memory "
                            f"({other_parsed[0] if other_parsed else 'hand-written line'}): "
                            f"{new_text}"
                        )

                new_line = f"- [{memory_id}] {new_text}"
                body = lines[:index] + [new_line] + lines[index + 1 :]
                with _reverting(path, [source]):
                    _atomic_write(source_path, "\n".join(body) + "\n")

                    # AGENTS.md rule 10: assert the post-state, then gate the commit.
                    written = _read_lines(source_path)
                    if written[index] != new_line:
                        raise WriteNotLanded(
                            f"edit of {memory_id} in {source} did not land; refusing to commit"
                        )
                    sha, note = _commit_or_already_applied(
                        path,
                        _commit_message(
                            mid=memory_id,
                            text=new_text,
                            quote=quote,
                            session_id=session_id,
                            writer=writer,
                            action="edit",
                            target=source,
                            was=was,
                        ),
                        [source],
                        operation="commit",
                    )
                    _assert_saved(path, source, new_line, sha)
                return SaveResult(
                    id=memory_id,
                    text=new_text,
                    target=source,
                    commit=sha,
                    line=new_line,
                    note=note,
                )

    raise UnknownId(f"unknown memory id {memory_id!r}: no such line in MEMORY.md or topics/")


def forget(
    memory_id: str,
    home: str | os.PathLike[str] | None = None,
    *,
    session_id: str = "",
    writer: str = "human",
) -> ForgetResult:
    """session.v2 Core 6 / store.v2 §6: remove the line and commit `forgot [m-NNN] …`.

    The id is never reassigned, and the commit subject carries the `forgot` marker so
    `git log --oneline` cannot show a removal as if it were a creation.
    """
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
                with _reverting(path, [source]):
                    _atomic_write(
                        source_path, ("\n".join(remaining) + "\n") if remaining else ""
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


def _untrack_usage(home: Path) -> str | None:
    """store.v2 §1's one-time migration: stop tracking `usage.jsonl`, visibly, once.

    Called under the caller's lock on every usage append, and does something exactly
    once: the first time it meets a store that still tracks the file. After that
    `git ls-files` no longer matches it and this is a single cheap read.

    A store created before store.v2 committed every load. On the steward's device that
    is ~10 `usage: loaded` commits for sessions that changed nothing; the file itself is
    memory (§2) and none of it is deleted — `git rm --cached` unstages the path and
    leaves the working-tree file untouched.
    """
    if not _git.is_tracked(home, "usage.jsonl"):
        return None

    gitignore = home / STORE_GITIGNORE
    current = _read_text(gitignore)
    if "usage.jsonl" not in current.splitlines():
        prefix = current if (current == "" or current.endswith("\n")) else current + "\n"
        _atomic_write(gitignore, prefix + GITIGNORE_BODY)

    with _git_step("rm --cached", home):
        _git.rm_cached(home, ["usage.jsonl"])
    with _git_step("add", home):
        _git.add(home, [STORE_GITIGNORE])
    with _git_step("commit", home):
        sha = _git.commit_index(home, UNTRACK_USAGE_MESSAGE, identity=STORE_IDENTITY)
    # AGENTS.md rule 10: the migration is asserted, not assumed. If the file is still
    # tracked, the next append would commit again and the loop would never end.
    if _git.is_tracked(home, "usage.jsonl"):
        raise WriteNotLanded(
            f"commit {sha[:12]} was made but git still tracks usage.jsonl in {home}; "
            "reading memory would keep leaving commits behind (store.v2 \u00a71)"
        )
    return sha


def log_usage(
    event: str,
    target: str,
    session_id: str,
    home: str | os.PathLike[str] | None = None,
) -> dict[str, str]:
    """store.v2 §1/§8: append one entry, **without a commit**; truncate to 90 days.

    This is the one write in the library that makes no commit, and that is the clause,
    not an optimisation: a session that only reads memory must leave no commit behind
    (§1, §10). There is no `commit=` switch — a caller that could ask for a commit could
    reintroduce the four-commits-in-an-afternoon defect §1 was written to end.
    """
    path = _require_store(home)
    if event not in USAGE_EVENTS:
        raise ValueError(f"unknown usage event {event!r}: expected one of {USAGE_EVENTS}")
    if event == "cited":
        if not _CITED_TARGET_RE.match(target):
            raise ValueError(
                f"unknown usage target {target!r} for a 'cited' event: expected a memory id "
                "like m-017 (store.v2 \u00a78)"
            )
    elif target != "MEMORY.md" and not target.startswith("topics/"):
        raise ValueError(f"unknown usage target {target!r}: expected MEMORY.md or topics/<slug>.md")

    entry = {
        "ts": _now().isoformat(),
        "event": event,
        "target": target,
        "session_id": session_id,
    }
    usage = path / "usage.jsonl"
    cutoff = _now() - timedelta(days=USAGE_RETENTION_DAYS)
    # The same lock as `save`: this is still a read-modify-write, and two interleaved
    # appends would still lose an entry. There is no `_reverting` here on purpose — the
    # file is untracked, so restoring it "from HEAD" would delete the usage log outright.
    with _exclusive(path):
        _untrack_usage(path)
        kept: list[str] = []
        for line in _read_lines(usage):
            if not line.strip():
                continue
            try:
                when = datetime.fromisoformat(json.loads(line)["ts"])
            except (json.JSONDecodeError, KeyError, TypeError, ValueError):
                continue  # undateable: not a store.v2 §8 entry
            if when.tzinfo is None:
                when = when.replace(tzinfo=UTC)
            if when >= cutoff:
                kept.append(line)
        kept.append(json.dumps(entry, ensure_ascii=False))
        _atomic_write(usage, "\n".join(kept) + "\n")
    return entry


def record_citation(
    memory_id: str,
    session_id: str,
    home: str | os.PathLike[str] | None = None,
) -> dict[str, str]:
    """store.v2 §8: record that the assistant named `memory_id` at use. No commit.

    session.v2 §8 asks the assistant to cite a memory when it acts on one; this is where
    that lands, and it is what `status`'s citation rate (cli.v2 §2) is computed from.
    """
    if not _CITED_TARGET_RE.match(memory_id):
        raise ValueError(f"not a memory id: {memory_id!r} (expected m-017)")
    return log_usage("cited", memory_id, session_id, home)


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
