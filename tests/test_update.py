"""`update` — cli.v1 Core 7. Every step's argv verified, every step's run injected.

Two kinds of test here, and they are deliberately different:

- **AGENTS.md rule 5** — the argv `update` shells out to is asked of that CLI's own
  `--help`, and the help is printed. `amplifier run --once` shipped without existing;
  this is the check that would have caught it. These tests need the CLI on PATH and
  skip (never silently pass) when it is absent.
- **Behaviour** — `run_update` is exercised with an injected runner, so no network
  call, no upgrade, and no change to this device happens in the suite.
"""

from __future__ import annotations

import os
import shutil
import subprocess
from collections.abc import Sequence

import pytest

import amplifier_memory
from amplifier_memory.doctor import DoctorReport, DoctorRow

# Bound at import time, before conftest's autouse `no_shelling_out` fixture replaces the
# module attribute — this is the one test that must exercise the REAL runner.
from amplifier_memory.update import _default_runner as _real_default_runner

# --------------------------------------------------------------- AGENTS.md rule 5


def _help(argv: Sequence[str]) -> str:
    proc = subprocess.run(
        list(argv),
        capture_output=True,
        text=True,
        check=True,
        env={**os.environ, "MANPAGER": "cat", "GIT_PAGER": "cat", "NO_COLOR": "1"},
    )
    out = proc.stdout + proc.stderr
    print(f"$ {' '.join(argv)}\n{out}")
    return out


@pytest.mark.skipif(shutil.which("uv") is None, reason="uv is not on PATH")
def test_uv_tool_upgrade_argv_exists() -> None:
    """`uv tool upgrade amplifier-memory` — the tool name is a positional <NAME>."""
    out = _help(["uv", "tool", "upgrade", "--help"])
    assert "uv tool upgrade" in out
    assert "<NAME>" in out, "uv tool upgrade does not take a positional tool name"
    assert amplifier_memory.UPGRADE_CLI_ARGV[:3] == ("uv", "tool", "upgrade")
    assert amplifier_memory.UPGRADE_CLI_ARGV[3] == "amplifier-memory"


@pytest.mark.skipif(shutil.which("amplifier") is None, reason="amplifier is not on PATH")
def test_amplifier_bundle_add_and_remove_argv_exist() -> None:
    """`amplifier bundle add|remove <uri> --app` — the app-bundle refresh path.

    `amplifier bundle update` is NOT used: measured on this device it cannot reach an
    app bundle registered by URI (`No handler for URI: memory-session` by name,
    `No active bundle.` with `--source`, and `--all` enumerates registry bundles only).
    """
    add = _help(["amplifier", "bundle", "add", "--help"])
    remove = _help(["amplifier", "bundle", "remove", "--help"])
    assert "--app" in add and "URI" in add
    assert "--app" in remove
    assert amplifier_memory.BUNDLE_ADD_ARGV[:3] == ("amplifier", "bundle", "add")
    assert amplifier_memory.BUNDLE_REMOVE_ARGV[:3] == ("amplifier", "bundle", "remove")
    assert amplifier_memory.BUNDLE_ADD_ARGV[-1] == "--app"


def test_app_bundle_uri_points_at_the_behavior_not_the_root_bundle() -> None:
    """The root-bundle URI composes nothing (a self-include the loader skips).

    Evidence: tests/smoke/evidence/ — with the root URI installed, a real session
    answered `NONE` where the announce belongs; with this URI, `Loaded 1 memories`.
    """
    uri = amplifier_memory.APP_BUNDLE_URI
    print(uri)
    assert uri.endswith("#subdirectory=behaviors/memory-session.yaml")
    assert uri.startswith("git+https://github.com/bkrabach/amplifier-bundle-memory@")


# --------------------------------------------------------------- behaviour


def _fake_doctor() -> DoctorReport:
    from pathlib import Path

    return DoctorReport(home=Path("/tmp/store"), rows=[DoctorRow("store", "OK", "present")])


class _Recorder:
    """A runner that records argv and answers with canned exit codes."""

    def __init__(self, codes: dict[str, int] | None = None) -> None:
        self.calls: list[tuple[str, ...]] = []
        self.codes = codes or {}

    def __call__(self, argv: Sequence[str]) -> tuple[int, str]:
        argv = tuple(argv)
        self.calls.append(argv)
        for needle, code in self.codes.items():
            if needle in " ".join(argv):
                return code, f"simulated failure of {needle}"
        return 0, f"ok: {' '.join(argv)}"


def test_run_update_performs_the_four_steps_in_order() -> None:
    runner = _Recorder()
    result = amplifier_memory.run_update(runner=runner, doctor_fn=_fake_doctor)
    print(result.render())

    assert runner.calls[0] == amplifier_memory.UPGRADE_CLI_ARGV
    assert runner.calls[1] == amplifier_memory.BUNDLE_REMOVE_ARGV
    assert runner.calls[2] == amplifier_memory.BUNDLE_ADD_ARGV
    assert len(runner.calls) == 3, "the timer must not be touched in Phase 1"
    assert result.report is not None, "update did not end by running doctor"
    assert result.exit_code == 0


def test_run_update_prints_the_plan_the_stale_note_and_doctor() -> None:
    """cli.v1 Core 7's output requirements, checked on the rendered text."""
    out = amplifier_memory.run_update(runner=_Recorder(), doctor_fn=_fake_doctor).render()
    print(out)
    assert "uv tool upgrade amplifier-memory" in out
    assert "amplifier bundle add" in out and "--app" in out
    assert "keep the old module code until they restart" in out, "the stale-in-memory note"
    assert "amplifier-memory doctor — store:" in out, "update did not end by running doctor"


def test_phase_1_skips_the_timer_and_says_why_in_the_librarys_own_words() -> None:
    result = amplifier_memory.run_update(runner=_Recorder(), doctor_fn=_fake_doctor)
    timer = next(step for step in result.steps if "timer" in step.name)
    print(timer.render())
    assert timer.skipped
    assert timer.reason == amplifier_memory.service_status("restart").splitlines()[0]
    assert not timer.failed


def test_a_missing_app_entry_does_not_fail_the_update() -> None:
    """The remove is tolerated: an entry that is already absent is not an error."""
    runner = _Recorder(codes={"bundle remove": 1})
    result = amplifier_memory.run_update(runner=runner, doctor_fn=_fake_doctor)
    removal = next(step for step in result.steps if "drop" in step.name)
    print(result.render())
    assert removal.returncode == 1
    assert not removal.failed
    assert result.exit_code == 0


def test_a_failed_upgrade_is_reported_and_exits_nonzero() -> None:
    runner = _Recorder(codes={"tool upgrade": 2})
    result = amplifier_memory.run_update(runner=runner, doctor_fn=_fake_doctor)
    print(result.render())
    assert result.exit_code == 1
    assert "FAIL" in result.render()
    assert "simulated failure" in result.render()


def test_doctors_own_failure_makes_update_exit_nonzero() -> None:
    from pathlib import Path

    def failing_doctor() -> DoctorReport:
        return DoctorReport(home=Path("/tmp/x"), rows=[DoctorRow("store", "FAIL", "missing")])

    result = amplifier_memory.run_update(runner=_Recorder(), doctor_fn=failing_doctor)
    assert result.exit_code == 1


def test_the_default_runner_never_raises_on_a_missing_executable() -> None:
    """`update` is a maintenance verb: it reports what is wrong, it does not crash."""
    code, out = _real_default_runner(["definitely-not-a-real-command-xyz"])
    print(code, out)
    assert code == 127
    assert "Error" in out or "error" in out.lower()
