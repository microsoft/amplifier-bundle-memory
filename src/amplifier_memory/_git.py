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
    args: list[str], cwd: Path, check: bool = True, timeout: float | None = None
) -> subprocess.CompletedProcess[str]:
    """Run one git command in `cwd`. Fails loud: non-zero raises CalledProcessError."""
    return subprocess.run(
        ["git", *args],
        cwd=str(cwd),
        check=check,
        capture_output=True,
        text=True,
        timeout=timeout,
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
    git([*prefix, "commit", "-m", message], cwd=home)
    return git(["rev-parse", "HEAD"], cwd=home).stdout.strip()


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
