"""The only place this library shells out.

Every argv here is verified against `git --help` output by
``tests/test_store.py::test_shelled_argv_is_verified_against_git_help`` and
``tests/test_cli.py::test_shelled_argv_added_by_the_cli_lane_is_verified`` (AGENTS.md
rule 5): the flags below are asserted to exist in the installed git's own help,
by running it, not by assuming.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

# Record/unit separators for machine-readable `git log` output. Chosen because
# neither can appear in a commit message written by this library.
RECORD = "\x1e"
UNIT = "\x1f"


def git(
    args: list[str],
    cwd: Path,
    check: bool = True,
    timeout: float | None = None,
    stdin_text: str | None = None,
) -> subprocess.CompletedProcess[str]:
    """Run one git command in `cwd`. Fails loud: non-zero raises CalledProcessError.

    `stdin_text` is fed to the command on stdin. That is how a commit message reaches
    `git commit -F -` without ever being an argv element: past ~131,000 bytes the kernel
    refuses the exec with `OSError: [Errno 7] Argument list too long`, which is neither
    `MemoryError` nor `ValueError` and so escaped every refusal path this library has.

    Output is decoded with `errors="replace"`: store.v1 Core 9 invites hand edits, a hand
    edit can leave a byte that is not UTF-8, and a *read* of the store must never raise.
    """
    return subprocess.run(
        ["git", *args],
        cwd=str(cwd),
        check=check,
        capture_output=True,
        text=True,
        errors="replace",
        timeout=timeout,
        input=stdin_text,
    )


def init_repo(home: Path) -> None:
    git(["init", "-b", "main"], cwd=home)


def get_config(home: Path, key: str) -> str | None:
    proc = git(["config", "--get", key], cwd=home, check=False)
    return proc.stdout.strip() if proc.returncode == 0 else None


def is_repo(home: Path) -> bool:
    proc = git(["rev-parse", "--is-inside-work-tree"], cwd=home, check=False)
    return proc.returncode == 0 and proc.stdout.strip() == "true"


def add(home: Path, paths: list[str]) -> None:
    git(["add", "--", *paths], cwd=home)


def commit(
    home: Path, message: str, paths: list[str], *, identity: tuple[str, str] | None = None
) -> str:
    """Stage exactly `paths` and make one commit. Returns the new commit sha.

    `identity` is `(name, email)` applied to this commit alone, as
    ``git -c user.name=… -c user.email=… commit`` (store.v1 Core 9): the store
    repository carries no identity of its own, so a human's own `git commit` in
    the store is attributed to the human, not to this tool. `identity=None`
    means "use whatever git already resolves for this caller" — the hand-edit path.
    """
    add(home, paths)
    prefix: list[str] = []
    if identity is not None:
        prefix = ["-c", f"user.name={identity[0]}", "-c", f"user.email={identity[1]}"]
    # `-F -` reads the message from stdin. Never `-m <message>`: a memory text is
    # human-supplied and unbounded from this library's point of view, and an argv past
    # the kernel's limit raises OSError *after* `git add` has already staged the file —
    # which is how a loudly-refused 131 KB save was committed by the next innocent write.
    git([*prefix, "commit", "-F", "-"], cwd=home, stdin_text=message)
    return git(["rev-parse", "HEAD"], cwd=home).stdout.strip()


def unstage(home: Path, paths: list[str]) -> None:
    """Return `paths` in the index to their state at HEAD. Never raises.

    The index half of a rollback: `git add` may already have run when a commit failed,
    and a staged file left behind is swept into the *next* write's commit.
    """
    git(["reset", "-q", "HEAD", "--", *paths], cwd=home, check=False)


def head(home: Path) -> str:
    """The current HEAD sha."""
    return git(["rev-parse", "HEAD"], cwd=home).stdout.strip()


def show_bytes(home: Path, spec: str) -> bytes | None:
    """`git show <sha>:<path>` as raw bytes, or None when that commit lacks the path.

    Bytes, not text, because whether a committed blob decodes as UTF-8 is itself a
    question this library answers (`doctor`, and choosing a commit to repair from).
    A decoded-with-replacement string cannot be told apart from one that really
    contained U+FFFD.
    """
    proc = subprocess.run(
        ["git", "show", spec],
        cwd=str(home),
        check=False,
        capture_output=True,
    )
    if proc.returncode != 0:
        return None
    return proc.stdout


def show(home: Path, spec: str) -> str | None:
    """`git show <sha>:<path>` — a file as the **committed tree** has it, or None.

    None means that commit does not carry that path (never an empty file, which is a
    real and different answer). The committed tree is what a writer must assert on: the
    working tree can legitimately be mid-hand-edit (store.v1 Core 9).

    Decoded tolerantly — see `git()`. Use `show_bytes` when the answer depends on
    whether the blob was valid UTF-8 in the first place.
    """
    raw = show_bytes(home, spec)
    if raw is None:
        return None
    return raw.decode("utf-8", errors="replace")


#: git's own words when a commit had nothing staged. Matched, not guessed: verified
#: against the installed git by `tests/test_store.py::test_nothing_to_commit_is_reported_honestly`.
NOTHING_TO_COMMIT = (
    "nothing to commit",
    "no changes added to commit",
    "nothing added to commit",
)


def is_nothing_to_commit(exc: subprocess.CalledProcessError) -> bool:
    """True when git refused a commit because nothing was staged.

    Under the store's write lock that is not a failure: it means the change is already
    in the committed tree because a concurrent writer swept it in.
    """
    blob = f"{exc.stdout or ''}\n{exc.stderr or ''}".lower()
    return any(marker in blob for marker in NOTHING_TO_COMMIT)


def first_error_line(exc: subprocess.CalledProcessError) -> str:
    """git's own first line of explanation — never the argv.

    An argv dump is what the steward saw when a concurrent `forget` failed
    (`Command '['git', '-c', 'user.name=amplifier-memory', …]'`): it names the tool's
    plumbing and not one thing the human can act on.
    """
    for stream in (exc.stderr, exc.stdout):
        for line in (stream or "").splitlines():
            if line.strip():
                return line.strip()
    return f"git exited {exc.returncode} with no output"


def commit_count(home: Path) -> int:
    proc = git(["rev-list", "--count", "HEAD"], cwd=home, check=False)
    if proc.returncode != 0:
        return 0
    return int(proc.stdout.strip() or 0)


def ls_remote(url: str, ref: str, cwd: Path, timeout: float = 10.0) -> str | None:
    """The sha `ref` points at in the remote `url`, or None when it is not checkable.

    Offline, unreachable, or slow is never an error here: cli.v1 Core 5 says the
    update check reports "not checkable" and is never RED.
    """
    try:
        proc = git(["ls-remote", url, ref], cwd=cwd, check=False, timeout=timeout)
    except (subprocess.TimeoutExpired, OSError):
        return None
    if proc.returncode != 0 or not proc.stdout.strip():
        return None
    return proc.stdout.split()[0]


def log_records(home: Path, grep: str | None = None) -> list[dict[str, str]]:
    """Commits as {sha, date, body}, newest first. `grep` is a git BRE pattern."""
    args = ["log", f"--format={RECORD}%H{UNIT}%aI{UNIT}%B"]
    if grep is not None:
        args.append(f"--grep={grep}")
    proc = git(args, cwd=home, check=False)
    if proc.returncode != 0:
        return []
    records = []
    for chunk in proc.stdout.split(RECORD):
        if not chunk.strip():
            continue
        sha, date, body = chunk.split(UNIT, 2)
        records.append({"sha": sha, "date": date, "body": body.strip("\n")})
    return records
