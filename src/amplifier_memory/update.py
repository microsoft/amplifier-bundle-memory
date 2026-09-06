"""`update` — cli.v2 Core 7, performed rather than described.

The clause: "upgrades the uv tool and refreshes the registered app bundle, restarts
the timer if installed, ends by running `doctor`, and prints the stale-in-memory
note: sessions started before the refresh keep the old module code until restarted."

A device runs **three** copies of this bundle, and until 2026-09-06 this verb refreshed
one of them. The steps, in order, each a real argv this module shells out to:

1. ``uv tool upgrade amplifier-memory`` — the shell verb.
2. ``git -C <cache clone> fetch origin`` then ``git -C <cache clone> reset --hard
   origin/<ref>``, for every cache clone — **what sessions load the modules and skills
   from**. Falls back to ``amplifier bundle remove/add <APP_BUNDLE_URI> --app`` when
   there is no clone to move (nothing installed yet, or a cache that is not a git
   checkout), and says which happened.
3. ``uv pip install --python <the amplifier venv's python> --refresh
   --reinstall-package amplifier-memory "amplifier-memory @ git+<repo>@<ref>"`` — **the
   library those modules import**. One warning line and no failure when no amplifier
   venv can be found.
4. the suggest timer — skipped while `service_status` says Phase 1 has none.
5. ``amplifier-memory doctor``, in-process (`doctor()`), never as a subprocess:
   a wrapper must not call a wrapper (cli.v2 Core 9).

Every argv above is verified against that CLI's own ``--help`` by
`tests/test_update.py`, which prints the help it relied on (AGENTS.md rule 5).

Why steps 2 and 3 exist at all
------------------------------
Measured on the steward's device 2026-09-06 21:55–22:05Z, after four waves of merged
work: `update` reported ``[ok] refresh the app bundle`` and `doctor` reported ``[OK]
update current (0f7e0fc == main)``, and a real session still printed **v1's** ``Loaded 2
memories (0 topics available).`` The cache clone sat at ``0afc6a8`` (through both
``bundle remove``+``add`` *and* ``amplifier bundle update``) and the library inside the
amplifier venv sat at a pre-K1 commit with ``edit``/``record_citation`` absent — which is
also what raised ``AttributeError: … read_memory_text`` in a lane's real session. The two
commands in steps 2 and 3 are the ones that actually repaired the device by hand; they
are encoded here, not redesigned. `docs/workflow/CHECK-RECORD.md`, addendum 22:05Z.

Why the fallback is a remove-then-add and not ``amplifier bundle update``
-------------------------------------------------------------------------
Measured 2026-09-06 against the installed CLI:

- ``amplifier bundle update <name>`` resolves *registry* names. The app bundle is
  registered by URI in ``bundle.app``, not by name, so it answers
  ``Error: Failed to load bundle: No handler for URI: memory-session``.
- ``amplifier bundle update --check --source <uri>`` answers ``No active bundle.``
- ``amplifier bundle update --all --check`` enumerates discovered bundles only; the
  app-bundle URIs are not among them.

``amplifier bundle add`` refetches the source ("Fetching bundle from …") and registers
the URI, so it remains the *install* path — but it does not move an existing clone off
its commit, which is why it is no longer the refresh. The remove is tolerated when it
fails: an app entry that is already absent is not an error.

Why the URI carries ``#subdirectory=behaviors/memory-session.yaml``
------------------------------------------------------------------
The root-bundle URI composes nothing. The root bundle includes this same behavior,
so an ``--app`` install of the root is a self-include the loader skips ("Circular
Include Skipped"), and the session gets no hook and no memory tool. Measured in
`tests/smoke/evidence/` and fixed in README step 1.

This module imports only the standard library and this package: no `click`.
"""

from __future__ import annotations

import subprocess
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from pathlib import Path

from .doctor import (
    PINNED_REF,
    REPO_URL,
    SHORT,
    STALE_NOTE,
    DoctorReport,
    amplifier_env_python,
    bundle_cache_dirs,
    commit_of_cache,
    commit_of_env_library,
    doctor,
    service_status,
    update_plan,
)

#: The app-bundle URI, spelled the one way that composes (see the module docstring).
APP_BUNDLE_URI = f"git+{REPO_URL}@{PINNED_REF}#subdirectory=behaviors/memory-session.yaml"

#: The requirement `uv pip install` is given for the library inside the amplifier venv.
#: AGENTS.md rule 4: a self-referential git URL, never a bare name.
LIBRARY_REQUIREMENT = f"amplifier-memory @ git+{REPO_URL}@{PINNED_REF}"

UPGRADE_CLI_ARGV: tuple[str, ...] = ("uv", "tool", "upgrade", "amplifier-memory")
BUNDLE_REMOVE_ARGV: tuple[str, ...] = ("amplifier", "bundle", "remove", APP_BUNDLE_URI, "--app")
BUNDLE_ADD_ARGV: tuple[str, ...] = ("amplifier", "bundle", "add", APP_BUNDLE_URI, "--app")

#: "the caller said nothing", as distinct from "the caller said None" (= no venv found).
_UNSET = object()


def cache_fetch_argv(cache_dir: Path) -> tuple[str, ...]:
    """`git -C <clone> fetch origin` — the first half of a cache refresh."""
    return ("git", "-C", str(cache_dir), "fetch", "origin")


def cache_reset_argv(cache_dir: Path, ref: str = PINNED_REF) -> tuple[str, ...]:
    """`git -C <clone> reset --hard origin/<ref>` — the half that moves the clone."""
    return ("git", "-C", str(cache_dir), "reset", "--hard", f"origin/{ref}")


def env_install_argv(python: Path) -> tuple[str, ...]:
    """The uv command that reinstalls this library into the amplifier CLI's own venv.

    `--refresh` defeats uv's cache (the commit behind `@main` moved; the URL did not),
    and `--reinstall-package` forces the rebuild of this one distribution rather than
    re-resolving the whole environment.
    """
    return (
        "uv",
        "pip",
        "install",
        "--python",
        str(python),
        "--refresh",
        "--reinstall-package",
        "amplifier-memory",
        LIBRARY_REQUIREMENT,
    )


def _short(sha: str | None) -> str:
    """A sha as the steps print it, or an honest word when there is none."""
    return sha[:SHORT] if sha else "unknown"

#: What a step runner returns: an exit code and whatever the command said.
Runner = Callable[[Sequence[str]], "tuple[int, str]"]


@dataclass
class StepResult:
    """One update step: what was run, what happened, and whether it mattered."""

    name: str
    argv: tuple[str, ...] | None
    returncode: int | None = None
    output: str = ""
    skipped: bool = False
    reason: str = ""
    #: A step whose failure must not fail the update (the tolerated remove).
    optional: bool = False

    @property
    def failed(self) -> bool:
        return not self.skipped and not self.optional and (self.returncode or 0) != 0

    def render(self) -> str:
        shown = " ".join(self.argv) if self.argv else (self.reason or "(no command)")
        if self.skipped:
            head = f"  [skip] {self.name}: {self.reason}"
            return head
        mark = "ok  " if (self.returncode or 0) == 0 else ("warn" if self.optional else "FAIL")
        lines = [f"  [{mark}] {self.name}: {shown}"]
        body = (self.output or "").strip()
        if body:
            lines.extend(f"         {line}" for line in body.splitlines())
        return "\n".join(lines)


@dataclass
class UpdateReport:
    """cli.v2 Core 7's whole output: the steps, the stale note, then doctor."""

    steps: list[StepResult] = field(default_factory=list)
    report: DoctorReport | None = None

    @property
    def exit_code(self) -> int:
        """Nonzero when a required step failed, or when doctor itself failed."""
        if any(step.failed for step in self.steps):
            return 1
        return self.report.exit_code if self.report is not None else 1

    def render(self) -> str:
        """The plan (which carries the stale-in-memory note), the steps, then doctor."""
        parts = [update_plan(), "", *(step.render() for step in self.steps), ""]
        if self.report is not None:
            parts.append(self.report.render())
        return "\n".join(parts)


def _default_runner(argv: Sequence[str]) -> tuple[int, str]:
    """Run a command, return (exit code, combined output). Never raises on exit code.

    A missing executable is reported as an exit code and a message, not a traceback:
    `update` is a maintenance verb and must say what is wrong rather than crash.
    """
    try:
        proc = subprocess.run(list(argv), capture_output=True, text=True, check=False)
    except (OSError, ValueError) as exc:
        return 127, f"{type(exc).__name__}: {exc}"
    return proc.returncode, (proc.stdout + proc.stderr).strip()


def _register_app_bundle(run: Runner, why: str) -> list[StepResult]:
    """The fallback: re-register the app-bundle URI so `amplifier` fetches it fresh.

    This is the *install* path, and it is reached only when there is no git clone to
    move — because on this device it demonstrably left an existing clone on its old
    commit (see the module docstring). `why` says which case it was, in the step's own
    line, so the reader is never left guessing which path ran.
    """
    code, out = run(BUNDLE_REMOVE_ARGV)
    steps = [
        StepResult(
            "drop the old app-bundle entry",
            BUNDLE_REMOVE_ARGV,
            code,
            out,
            optional=True,
            reason="an absent entry is not an error",
        )
    ]
    code, out = run(BUNDLE_ADD_ARGV)
    steps.append(StepResult(f"register the app bundle ({why})", BUNDLE_ADD_ARGV, code, out))
    return steps


def _refresh_bundle_cache(
    run: Runner, app_bundle_uri: str, amplifier_home: str | None
) -> list[StepResult]:
    """Move every cache clone to the pinned ref — one step line per clone, old -> new.

    The cache is what a session actually loads modules and skills from, so this is the
    step whose absence made four merged waves invisible on the steward's device.
    """
    directories = bundle_cache_dirs(app_bundle_uri, amplifier_home)
    clones = [path for path in directories if commit_of_cache(path) is not None]
    steps: list[StepResult] = []

    for clone in clones:
        before = commit_of_cache(clone)
        fetch, reset = cache_fetch_argv(clone), cache_reset_argv(clone)
        code, out = run(fetch)
        if code != 0:
            steps.append(
                StepResult(f"refresh the bundle cache: {clone} ({_short(before)}, unmoved)",
                           fetch, code, out)
            )
            continue
        reset_code, reset_out = run(reset)
        after = commit_of_cache(clone)
        steps.append(
            StepResult(
                f"refresh the bundle cache: {clone} {_short(before)} \u2192 {_short(after)}",
                reset,
                reset_code,
                "\n".join(part for part in (out, reset_out) if part.strip()),
            )
        )

    if not directories:
        steps.extend(_register_app_bundle(run, "no cache clone found: this installs it"))
    elif not clones:
        steps.extend(
            _register_app_bundle(
                run, f"{len(directories)} cache dir(s) found, none a git clone"
            )
        )
    return steps


def _refresh_env_library(run: Runner, python: Path | None) -> StepResult:
    """Reinstall this library inside the amplifier CLI's venv — what the modules import.

    A missing venv is a warning, never a failure: a device can run the CLI verb without
    ever having installed `amplifier`, and the other steps still have work to do.
    """
    name = "refresh the library in the amplifier environment"
    if python is None:
        return StepResult(
            name,
            None,
            returncode=1,
            output=(
                "no amplifier environment found: `shutil.which(\"amplifier\")` found nothing, "
                "so the library the modules import was not refreshed"
            ),
            optional=True,
            reason="no amplifier venv on this device",
        )
    before = commit_of_env_library(python)
    argv = env_install_argv(python)
    code, out = run(argv)
    after = commit_of_env_library(python)
    return StepResult(f"{name}: {_short(before)} \u2192 {_short(after)}", argv, code, out)


def run_update(
    *,
    runner: Runner | None = None,
    doctor_fn: Callable[[], DoctorReport] | None = None,
    timer_installed: bool = False,
    app_bundle_uri: str = APP_BUNDLE_URI,
    amplifier_home: str | None = None,
    env_python: Path | None | object = _UNSET,
) -> UpdateReport:
    """cli.v2 Core 7, executed. Returns what happened; prints nothing.

    `runner`, `doctor_fn`, `amplifier_home` and `env_python` are injectable so the
    conformance kit and the tests can exercise every step with no network and no
    mutation of this device. `env_python=None` is the "no amplifier venv" branch;
    leaving it unset resolves the real one.
    `timer_installed` stays False for the whole of Phase 1 — `service_status` is the
    library's own statement that there is no timer, and it is quoted in the skip
    reason rather than paraphrased.
    """
    run = runner or _default_runner
    steps: list[StepResult] = []

    code, out = run(UPGRADE_CLI_ARGV)
    steps.append(StepResult("upgrade the CLI", UPGRADE_CLI_ARGV, code, out))

    steps.extend(_refresh_bundle_cache(run, app_bundle_uri, amplifier_home))

    python = amplifier_env_python() if env_python is _UNSET else env_python
    steps.append(_refresh_env_library(run, python if python is None else Path(str(python))))

    if timer_installed:
        argv = ("amplifier-memory", "service", "restart")
        steps.append(StepResult("restart the suggest timer", argv, *run(argv)))
    else:
        steps.append(
            StepResult(
                "restart the suggest timer",
                None,
                skipped=True,
                reason=service_status("restart").splitlines()[0],
            )
        )

    report = (doctor_fn or doctor)()
    return UpdateReport(steps=steps, report=report)


__all__ = [
    "APP_BUNDLE_URI",
    "BUNDLE_ADD_ARGV",
    "BUNDLE_REMOVE_ARGV",
    "LIBRARY_REQUIREMENT",
    "STALE_NOTE",
    "UPGRADE_CLI_ARGV",
    "StepResult",
    "UpdateReport",
    "cache_fetch_argv",
    "cache_reset_argv",
    "env_install_argv",
    "run_update",
]
