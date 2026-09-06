"""The install-plane reports: `doctor`, the update check, `service`, `suggest`, `update`.

cli.v1 Core 9: every behaviour a verb exposes is a public library function first,
so `amplifier-memory doctor` is `click.echo(amplifier_memory.doctor().render())` and
an exit code. This module imports only the standard library: no `click`.

**`doctor` never mutates** (cli.v1 Core 5). Nothing here writes, commits, stages, or
creates a file; the only shell-out is a read-only `git ls-remote` for the update
check, and that is injectable so a test never touches the network.
`tests/test_doctor.py` proves the no-mutation claim by hashing every file in the
store before and after.

cli.v1 clause map
-----------------
Core 5  `doctor` ........ `doctor`, `DoctorReport`, `update_check`
Core 6  `service` ....... `service_status`
Core 7  `update` ........ `update_plan` (the upgrade itself is not built here)
Core 1  `suggest` ....... `suggest_status`
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from pathlib import Path

from . import _git
from .status import STALE_TOPIC_DAYS, status
from .store import (
    MEMORY_LINE_CAP,
    TOPIC_FILE_CAP,
    _read_lines,
    store_home,
    topic_files,
)

# AGENTS.md rule 4: the self-referential git URL, never a bare name or a relative path.
REPO_URL = "https://github.com/bkrabach/amplifier-bundle-memory"
PINNED_REF = "main"

OK, WARN, FAIL, INFO = "OK", "WARN", "FAIL", "INFO"
# cli.v1 Core 5: "Exit code is nonzero only on failed checks." WARN and INFO are not failures.
FAILING_LEVELS = (FAIL,)


@dataclass
class DoctorRow:
    """One doctor line: a name, a level, and what was actually observed."""

    name: str
    level: str
    detail: str

    def render(self) -> str:
        return f"  [{self.level:<4}] {self.name:<14} {self.detail}"


@dataclass
class DoctorReport:
    home: Path
    rows: list[DoctorRow] = field(default_factory=list)

    @property
    def exit_code(self) -> int:
        """cli.v1 Core 5: nonzero only on a failed check."""
        return 1 if any(row.level in FAILING_LEVELS for row in self.rows) else 0

    def render(self) -> str:
        head = f"amplifier-memory doctor \u2014 store: {self.home}"
        return "\n".join([head, "", *(row.render() for row in self.rows)])


# --------------------------------------------------------------------------- update check


def installed_commit() -> str | None:
    """The commit this install was built from, or None when it is not knowable.

    A `uv tool install git+https://…` records the resolved commit in the
    distribution's `direct_url.json` (PEP 610). A working-tree/editable install has
    no such record, and that is reported honestly as "not checkable", never guessed.
    """
    try:
        from importlib.metadata import PackageNotFoundError, distribution

        raw = distribution("amplifier-memory").read_text("direct_url.json")
    except (ImportError, PackageNotFoundError, OSError):
        return None
    if raw is None:
        return None
    try:
        return json.loads(raw).get("vcs_info", {}).get("commit_id") or None
    except (json.JSONDecodeError, AttributeError):
        return None


def remote_commit(url: str = REPO_URL, ref: str = PINNED_REF) -> str | None:
    """`git ls-remote <url> <ref>`, or None offline. The only network call in this bundle."""
    return _git.ls_remote(url, ref, cwd=Path.cwd())


def update_check(installed_sha: str | None, remote_sha: str | None) -> DoctorRow:
    """cli.v1 Core 5's update check, as a pure function of the two shas.

    Behind -> WARN naming the remedy. Current -> OK. Either side unknown (offline, or
    an install with no recorded commit) -> INFO "not checkable". Never RED: an update
    check that cannot run is not a broken store.
    """
    if installed_sha is None or remote_sha is None:
        unknown = "the installed commit" if installed_sha is None else f"{REPO_URL}@{PINNED_REF}"
        return DoctorRow(
            "update",
            INFO,
            f"not checkable \u2014 {unknown} could not be read (offline, or not a git install)",
        )
    if installed_sha == remote_sha:
        return DoctorRow("update", OK, f"current ({installed_sha[:12]} == {PINNED_REF})")
    return DoctorRow(
        "update",
        WARN,
        f"behind \u2014 installed {installed_sha[:12]}, {PINNED_REF} is {remote_sha[:12]}; "
        f"remedy: `amplifier-memory update`",
    )


# --------------------------------------------------------------------------- doctor


_UNSET = object()


def _store_rows(home: Path) -> list[DoctorRow]:
    """The store-side rows of cli.v1 Core 5, in the order the clause lists them."""
    report = status(home)
    memory_lines = len(_read_lines(home / "MEMORY.md"))
    topics = topic_files(home)
    caps = f"MEMORY.md {memory_lines}/{MEMORY_LINE_CAP}, topics {len(topics)}/{TOPIC_FILE_CAP}"
    cap_level = WARN if (memory_lines >= MEMORY_LINE_CAP or len(topics) >= TOPIC_FILE_CAP) else OK
    rows = [DoctorRow("caps", cap_level, caps)]

    if report.stale_topics:
        names = ", ".join(report.stale_topics)
        rows.append(
            DoctorRow(
                "stale topics",
                INFO,
                f"{len(report.stale_topics)} unread {STALE_TOPIC_DAYS} days ({names}) \u2014 "
                "keep? nothing is deleted automatically",
            )
        )
    else:
        rows.append(DoctorRow("stale topics", OK, f"0 unread {STALE_TOPIC_DAYS} days"))

    pending = [line for line in _read_lines(home / "inbox.md") if line.strip()]
    rows.append(DoctorRow("inbox", OK, f"{len(pending)} pending, oldest {_oldest(pending)}"))
    return rows


def _oldest(pending: list[str]) -> str:
    """The oldest inbox entry's date, or an honest 'n/a'.

    suggestions.v1 is still DRAFT, so there is no entry format to date. Guessing one
    would be a number with nothing behind it.
    """
    if not pending:
        return "n/a (inbox empty)"
    return "n/a (suggestions.v1 is DRAFT: no dated entry format yet)"


def doctor(
    home: str | os.PathLike[str] | None = None,
    *,
    installed_sha: str | None | object = _UNSET,
    remote_sha: str | None | object = _UNSET,
) -> DoctorReport:
    """cli.v1 Core 5. Reads only; never writes, stages, or commits.

    `installed_sha` and `remote_sha` are injectable so the update check can be
    exercised in all three states with no network. Left unset, they are resolved
    from the installed distribution and `git ls-remote`.
    """
    path = store_home(home)
    rows: list[DoctorRow] = []

    has_memory = (path / "MEMORY.md").is_file()
    is_repo = path.is_dir() and _git.is_repo(path)
    if has_memory and is_repo:
        rows.append(DoctorRow("store", OK, f"present and a git repo at {path}"))
        rows.extend(_store_rows(path))
    else:
        missing = "no MEMORY.md" if not has_memory else "not a git repository"
        rows.append(
            DoctorRow("store", FAIL, f"{missing} at {path}; remedy: `amplifier-memory init`")
        )
        rows.append(DoctorRow("caps", INFO, "skipped: no store to measure"))
        rows.append(DoctorRow("stale topics", INFO, "skipped: no store to measure"))
        rows.append(DoctorRow("inbox", INFO, "skipped: no store to measure"))

    rows.append(
        DoctorRow(
            "suggest timer",
            INFO,
            "Phase 2 not installed \u2014 no timer to check (installed/enabled/last run/last "
            "outcome arrive with suggestions.v1)",
        )
    )
    rows.append(
        DoctorRow(
            "substrate",
            INFO,
            "checked only when Phase 2 is installed (cli.v1 Core 5)",
        )
    )
    installed = installed_commit() if installed_sha is _UNSET else installed_sha
    remote = remote_commit() if remote_sha is _UNSET else remote_sha
    rows.append(
        update_check(
            installed if isinstance(installed, str) or installed is None else None,
            remote if isinstance(remote, str) or remote is None else None,
        )
    )
    return DoctorReport(home=path, rows=rows)


# --------------------------------------------------------------------------- service / suggest / update

SERVICE_VERBS = ("install", "uninstall", "start", "stop", "restart", "status", "logs")

# The steps `update` performs, in order. Named here, in the library, so the CLI prints
# the plan rather than inventing one; `update.py` executes exactly these and no others.
# Each argv is verified against its own `--help` by tests/test_update.py, which prints
# the help it relied on (AGENTS.md rule 5).
#
# Step 2 is a remove-then-add, and its URI carries the behavior path, because measured
# on this device (2026-09-06) `amplifier bundle update` cannot reach an app bundle
# registered by URI, and the root-bundle URI composes nothing (a self-include the
# loader skips). Both findings are evidenced in tests/smoke/ and explained in
# `update.py`'s docstring.
_APP_URI = f"git+{REPO_URL}@{PINNED_REF}#subdirectory=behaviors/memory-session.yaml"

#: cli.v1 Core 7's last requirement, in one place. `update` prints it every run.
STALE_NOTE = (
    "Note: sessions started before the refresh keep the old module code until they "
    "restart. Nothing is hot-reloaded."
)

UPDATE_STEPS = (
    f"uv tool upgrade amplifier-memory   (the CLI, from {REPO_URL}@{PINNED_REF})",
    (
        f"amplifier bundle remove {_APP_URI} --app   then   amplifier bundle add {_APP_URI} "
        "--app   (refresh the app bundle; the remove is tolerated when the entry is absent)"
    ),
    "restart the suggest timer, if one is installed (Phase 2 only)",
    "run `amplifier-memory doctor`",
)


def service_status(verb: str) -> str:
    """cli.v1 Core 6. Phase 1 has no service; the verb reports that plainly."""
    if verb not in SERVICE_VERBS:
        raise ValueError(f"unknown service verb {verb!r}: expected one of {SERVICE_VERBS}")
    return (
        "Phase 1 has no service; the suggest timer arrives with Phase 2.\n"
        f"`service {verb}` did nothing: no unit was rendered, enabled, started, or removed."
    )


def suggest_status() -> str:
    """cli.v1 Core 1: in Phase 1 `suggest` says so and exits 0."""
    return (
        "Phase 2 not installed.\n"
        "The daily suggestion pass (suggestions.v1, still DRAFT) begins only after Phase 1's "
        "gate is met: five kept memories after a week of real use (`amplifier-memory status`)."
    )


def update_plan() -> str:
    """cli.v1 Core 7, as text: the four steps `update` runs, in order.

    `amplifier_memory.run_update` performs exactly these steps and prints this plan
    above its results, so the plan and the run can never describe different things.
    """
    steps = "\n".join(f"  {i}. {step}" for i, step in enumerate(UPDATE_STEPS, start=1))
    return f"`amplifier-memory update` runs, in order:\n{steps}\n\n{STALE_NOTE}"


__all__ = [
    "PINNED_REF",
    "REPO_URL",
    "SERVICE_VERBS",
    "STALE_NOTE",
    "UPDATE_STEPS",
    "DoctorReport",
    "DoctorRow",
    "doctor",
    "installed_commit",
    "remote_commit",
    "service_status",
    "suggest_status",
    "update_check",
    "update_plan",
]
