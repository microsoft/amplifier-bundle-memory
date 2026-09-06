"""The only place this library shells out.

Every argv here is verified against `git --help` output by
``tests/test_store.py::test_shelled_argv_is_verified_against_git_help`` (AGENTS.md
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


def git(args: list[str], cwd: Path, check: bool = True) -> subprocess.CompletedProcess[str]:
    """Run one git command in `cwd`. Fails loud: non-zero raises CalledProcessError."""
    return subprocess.run(
        ["git", *args],
        cwd=str(cwd),
        check=check,
        capture_output=True,
        text=True,
    )


def init_repo(home: Path) -> None:
    git(["init", "-b", "main"], cwd=home)


def set_identity(home: Path, name: str, email: str) -> None:
    git(["config", "user.name", name], cwd=home)
    git(["config", "user.email", email], cwd=home)


def get_config(home: Path, key: str) -> str | None:
    proc = git(["config", "--get", key], cwd=home, check=False)
    return proc.stdout.strip() if proc.returncode == 0 else None


def is_repo(home: Path) -> bool:
    proc = git(["rev-parse", "--is-inside-work-tree"], cwd=home, check=False)
    return proc.returncode == 0 and proc.stdout.strip() == "true"


def add(home: Path, paths: list[str]) -> None:
    git(["add", "--", *paths], cwd=home)


def commit(home: Path, message: str, paths: list[str]) -> str:
    """Stage exactly `paths` and make one commit. Returns the new commit sha."""
    add(home, paths)
    git(["commit", "-m", message], cwd=home)
    return git(["rev-parse", "HEAD"], cwd=home).stdout.strip()


def commit_count(home: Path) -> int:
    proc = git(["rev-list", "--count", "HEAD"], cwd=home, check=False)
    if proc.returncode != 0:
        return 0
    return int(proc.stdout.strip() or 0)


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
