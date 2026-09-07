"""suggestions.v1 Core 1 / cli.v2 Core 6 — the timer: rendered, enabled, rolled back.

**Nothing here runs a real command or writes a real unit file.** Every test passes a
recorder as `runner=` and a temp directory as `config_dir=`, and
`service._default_runner` refuses outright when `PYTEST_CURRENT_TEST` is set. Both
guards were written on 2026-09-06, the day the cli.v2 Core 6 probe invoked
`service install` with no injection and enabled a real daily timer on this device.
"""

from __future__ import annotations

import subprocess
from collections.abc import Sequence
from pathlib import Path

import pytest

import amplifier_memory
from amplifier_memory import service

EXE = "/usr/bin/amplifier-memory"


class Recorder:
    """A runner that records argv and answers with whatever it was told to."""

    def __init__(self, fail_on: str | None = None, message: str = "boom") -> None:
        self.calls: list[tuple[str, ...]] = []
        self.fail_on = fail_on
        self.message = message

    def __call__(self, argv: Sequence[str]) -> tuple[int, str]:
        self.calls.append(tuple(argv))
        if self.fail_on and self.fail_on in argv:
            return 1, self.message
        return 0, ""


@pytest.fixture
def units(tmp_path: Path) -> Path:
    return tmp_path / "systemd-user"


# ---------------------------------------------------------------- Core 1: what is written


def test_install_writes_a_oneshot_service_and_a_daily_timer(units: Path) -> None:
    runner = Recorder()
    result = amplifier_memory.service_install(
        runner=runner, config_dir=units, executable=EXE, platform=service.SYSTEMD
    )
    print(result.render())
    body = (units / service.SERVICE_UNIT).read_text(encoding="utf-8")
    timer = (units / service.TIMER_UNIT).read_text(encoding="utf-8")
    print(f"--- {service.SERVICE_UNIT} ---\n{body}--- {service.TIMER_UNIT} ---\n{timer}")

    assert result.ok and result.exit_code == 0
    assert "Type=oneshot" in body, "Core 1: nothing is resident"
    assert f"ExecStart={EXE} suggest" in body
    assert "[Install]" not in body, "only the timer is enabled; nothing else starts the job"
    assert "OnCalendar=daily" in timer and "Persistent=true" in timer
    assert "WantedBy=timers.target" in timer


def test_install_runs_daemon_reload_then_enable_now_in_that_order(units: Path) -> None:
    runner = Recorder()
    amplifier_memory.service_install(
        runner=runner, config_dir=units, executable=EXE, platform=service.SYSTEMD
    )
    print("argv:", runner.calls)
    assert runner.calls == [
        ("systemctl", "--user", "daemon-reload"),
        ("systemctl", "--user", "enable", "--now", service.TIMER_UNIT),
    ]


def test_the_systemctl_argv_matches_systemctl_help() -> None:
    """AGENTS.md rule 5: every shelled argv is verified against that CLI's own --help."""
    proc = subprocess.run(["systemctl", "--help"], capture_output=True, text=True, check=False)
    if proc.returncode != 0:
        pytest.skip("no systemctl on this device")
    help_text = proc.stdout
    wanted = [
        "daemon-reload",
        "enable ",
        "disable ",
        "is-enabled ",
        "start ",
        "restart ",
        "--now",
        "--user",
    ]
    for token in wanted:
        line = next(
            (row.strip() for row in help_text.splitlines() if row.strip().startswith(token)), None
        )
        print(f"{token!r:18} -> {line}")
        assert line is not None, f"systemctl --help does not document {token!r}"


# ---------------------------------------------------------------- Core 6: the rollback


def test_a_failed_enable_step_removes_every_unit_this_call_wrote(units: Path) -> None:
    runner = Recorder(fail_on="enable", message="Failed to enable unit: Unit file is masked.")
    result = amplifier_memory.service_install(
        runner=runner, config_dir=units, executable=EXE, platform=service.SYSTEMD
    )
    print(result.render())
    left = sorted(path.name for path in units.iterdir()) if units.exists() else []
    print("left behind:", left)
    assert not result.ok and result.rolled_back and left == []


def test_a_runner_that_raises_is_a_failed_step_and_still_rolls_back(units: Path) -> None:
    """An exception is not an escape hatch: it once left both unit files on disk."""

    def explode(argv: Sequence[str]) -> tuple[int, str]:
        raise OSError("systemctl: command not found")

    result = amplifier_memory.service_install(
        runner=explode, config_dir=units, executable=EXE, platform=service.SYSTEMD
    )
    print(result.render())
    left = sorted(path.name for path in units.iterdir()) if units.exists() else []
    assert not result.ok and result.rolled_back and left == [], left


def test_the_rollback_never_removes_a_unit_it_did_not_write(units: Path) -> None:
    """Reverting someone else's install is not a rollback."""
    units.mkdir(parents=True)
    (units / service.SERVICE_UNIT).write_text("# someone else's unit\n", encoding="utf-8")
    runner = Recorder(fail_on="enable")
    result = amplifier_memory.service_install(
        runner=runner, config_dir=units, executable=EXE, platform=service.SYSTEMD
    )
    left = sorted(path.name for path in units.iterdir())
    print(result.render())
    print("left behind:", left)
    assert left == [service.SERVICE_UNIT], "the pre-existing unit was swept away"


def test_install_refuses_when_there_is_no_absolute_executable(units: Path) -> None:
    runner = Recorder()
    result = amplifier_memory.service_install(
        runner=runner, config_dir=units, executable="amplifier-memory", platform=service.SYSTEMD
    )
    print(result.render())
    assert not result.ok and runner.calls == []
    assert not units.exists() or list(units.iterdir()) == []


def test_uninstall_leaves_nothing_behind(units: Path) -> None:
    runner = Recorder()
    amplifier_memory.service_install(
        runner=runner, config_dir=units, executable=EXE, platform=service.SYSTEMD
    )
    result = amplifier_memory.service_uninstall(
        runner=runner, config_dir=units, platform=service.SYSTEMD
    )
    print(result.render())
    print("argv:", runner.calls)
    assert list(units.iterdir()) == []
    assert ("systemctl", "--user", "disable", "--now", service.TIMER_UNIT) in runner.calls


# ---------------------------------------------------------------- Core 8: what status says


def test_status_reports_installed_enabled_last_run_and_last_outcome(
    units: Path, store: Path
) -> None:
    runner = Recorder()
    absent = amplifier_memory.service_state(
        runner=runner, config_dir=units, platform=service.SYSTEMD, home=store
    )
    print(absent.render())
    assert not absent.installed and runner.calls == [], "a missing timer is not asked about"

    amplifier_memory.service_install(
        runner=runner, config_dir=units, executable=EXE, platform=service.SYSTEMD
    )
    amplifier_memory.run_suggest(
        store, base_path=store / "no-substrate", model_call=lambda prompt: "[]"
    )

    class Enabled(Recorder):
        def __call__(self, argv):
            self.calls.append(tuple(argv))
            return 0, "enabled"

    enabled = Enabled()
    state = amplifier_memory.service_state(
        runner=enabled, config_dir=units, platform=service.SYSTEMD, home=store
    )
    print(state.render())
    assert state.installed and state.enabled
    assert enabled.calls == [("systemctl", "--user", "is-enabled", service.TIMER_UNIT)]
    assert state.last_status == "degraded:substrate missing"
    assert state.last_run is not None


def test_the_doctor_timer_row_goes_warn_not_fail(units: Path, store: Path) -> None:
    """cli.v2 Core 5: a machine with no timer is not a failed check."""
    runner = Recorder()
    missing = amplifier_memory.timer_row(home=store, runner=runner, config_dir=units)
    print(missing.render())
    assert missing.level == "INFO" and "not installed" in missing.detail

    amplifier_memory.service_install(
        runner=runner, config_dir=units, executable=EXE, platform=service.SYSTEMD
    )

    class Disabled(Recorder):
        def __call__(self, argv):
            self.calls.append(tuple(argv))
            return 1, "disabled"

    row = amplifier_memory.timer_row(home=store, runner=Disabled(), config_dir=units)
    print(row.render())
    assert row.level == "WARN" and "NOT enabled" in row.detail

    report = amplifier_memory.doctor(
        store,
        installed_sha=None,
        remote_sha=None,
        base_path=store / "no-substrate",
        service_runner=Recorder(),
        config_dir=units,
    )
    print(report.render())
    assert report.exit_code == 0, "no Phase 2 row may fail the check"


# ---------------------------------------------------------------- the macOS branch


def test_the_launchd_branch_renders_and_says_it_is_unverified(units: Path) -> None:
    """Rendered here; its `launchctl` argv cannot be checked against --help on Linux."""
    runner = Recorder()
    result = amplifier_memory.service_install(
        runner=runner, config_dir=units, executable=EXE, platform=service.LAUNCHD
    )
    plist = (units / service.PLIST_NAME).read_text(encoding="utf-8")
    print(result.render())
    print(f"--- {service.PLIST_NAME} ---\n{plist}")
    assert result.ok and service.PLIST_LABEL in plist and f"<string>{EXE}</string>" in plist
    assert "StartCalendarInterval" in plist and "<key>RunAtLoad</key>" in plist
    assert "not verified here" in result.note
    assert runner.calls[-1] == ("launchctl", "load", "-w", str(units / service.PLIST_NAME))


# ---------------------------------------------------------------- the guards


def test_the_default_runner_refuses_to_touch_this_device_from_a_test() -> None:
    with pytest.raises(RuntimeError, match="refusing to run"):
        # conftest swaps `_default_runner` for a recorder suite-wide; the guard under test
        # is the real function, kept under this name by the same fixture.
        service._unpatched_default_runner(["systemctl", "--user", "daemon-reload"])
    print("service._default_runner under pytest: refused, loudly")


def test_the_unit_dir_can_be_overridden_by_environment(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """The override the CLI needs: its verbs take no arguments, so a check needs a door."""
    monkeypatch.setenv(service.UNIT_DIR_ENV, str(tmp_path / "elsewhere"))
    print("unit_dir ->", service.unit_dir())
    assert service.unit_dir() == tmp_path / "elsewhere"
    monkeypatch.delenv(service.UNIT_DIR_ENV)
    assert service.unit_dir() != tmp_path / "elsewhere"


def test_a_plain_verb_runs_nothing_when_no_timer_is_installed(units: Path, store: Path) -> None:
    """`update` asks for `service restart` on every run (cli.v2 Core 7 step 4)."""
    runner = Recorder()
    for verb in ("start", "stop", "restart", "logs"):
        message = amplifier_memory.service_status(
            verb, runner=runner, config_dir=units, home=store, platform=service.SYSTEMD
        )
        print(f"{verb}: {message.splitlines()[0]}")
        assert "no suggest timer is installed" in message
    assert runner.calls == [], f"a verb shelled out with no timer installed: {runner.calls}"
