"""`update` — cli.v2 Core 7, performed rather than described.

The clause: "upgrades the uv tool and refreshes the registered app bundle, restarts
the timer if installed, ends by running `doctor`, and prints the stale-in-memory
note: sessions started before the refresh keep the old module code until restarted."

Four steps, in that order, each one a real argv this module shells out to:

1. ``uv tool upgrade amplifier-memory``
2. ``amplifier bundle remove <APP_BUNDLE_URI> --app`` then
   ``amplifier bundle add <APP_BUNDLE_URI> --app``
3. the suggest timer — skipped while `service_status` says Phase 1 has none
4. ``amplifier-memory doctor``, in-process (`doctor()`), never as a subprocess:
   a wrapper must not call a wrapper (cli.v2 Core 9).

Every argv above is verified against that CLI's own ``--help`` by
`tests/test_update.py`, which prints the help it relied on (AGENTS.md rule 5).

Why step 2 is a remove-then-add and not ``amplifier bundle update``
------------------------------------------------------------------
Measured 2026-09-06 against the installed CLI:

- ``amplifier bundle update <name>`` resolves *registry* names. The app bundle is
  registered by URI in ``bundle.app``, not by name, so it answers
  ``Error: Failed to load bundle: No handler for URI: memory-session``.
- ``amplifier bundle update --check --source <uri>`` answers ``No active bundle.``
- ``amplifier bundle update --all --check`` enumerates discovered bundles only; the
  app-bundle URIs are not among them.

``amplifier bundle add`` refetches the source ("Fetching bundle from …"), so
remove-then-add is the refresh path this CLI actually offers. The remove is
tolerated when it fails: an app entry that is already absent is not an error, and
the add that follows is what matters.

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

from .doctor import (
    PINNED_REF,
    REPO_URL,
    STALE_NOTE,
    DoctorReport,
    doctor,
    service_status,
    update_plan,
)

#: The app-bundle URI, spelled the one way that composes (see the module docstring).
APP_BUNDLE_URI = f"git+{REPO_URL}@{PINNED_REF}#subdirectory=behaviors/memory-session.yaml"

UPGRADE_CLI_ARGV: tuple[str, ...] = ("uv", "tool", "upgrade", "amplifier-memory")
BUNDLE_REMOVE_ARGV: tuple[str, ...] = ("amplifier", "bundle", "remove", APP_BUNDLE_URI, "--app")
BUNDLE_ADD_ARGV: tuple[str, ...] = ("amplifier", "bundle", "add", APP_BUNDLE_URI, "--app")

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
        shown = " ".join(self.argv) if self.argv else "(no command)"
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


def run_update(
    *,
    runner: Runner | None = None,
    doctor_fn: Callable[[], DoctorReport] | None = None,
    timer_installed: bool = False,
) -> UpdateReport:
    """cli.v2 Core 7, executed. Returns what happened; prints nothing.

    `runner` and `doctor_fn` are injectable so the conformance kit and the tests can
    exercise every step with no network and no mutation of this device.
    `timer_installed` stays False for the whole of Phase 1 — `service_status` is the
    library's own statement that there is no timer, and it is quoted in the skip
    reason rather than paraphrased.
    """
    run = runner or _default_runner
    steps: list[StepResult] = []

    code, out = run(UPGRADE_CLI_ARGV)
    steps.append(StepResult("upgrade the CLI", UPGRADE_CLI_ARGV, code, out))

    code, out = run(BUNDLE_REMOVE_ARGV)
    steps.append(
        StepResult(
            "drop the old app-bundle entry",
            BUNDLE_REMOVE_ARGV,
            code,
            out,
            optional=True,
            reason="an absent entry is not an error",
        )
    )
    code, out = run(BUNDLE_ADD_ARGV)
    steps.append(StepResult("refresh the app bundle", BUNDLE_ADD_ARGV, code, out))

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
    "STALE_NOTE",
    "UPGRADE_CLI_ARGV",
    "StepResult",
    "UpdateReport",
    "run_update",
]
