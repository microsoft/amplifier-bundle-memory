"""suggestions.v1 Core 1 / cli.v2 Core 6 — the timer: rendered, enabled, rolled back.

**Nothing here runs a real command or writes a real unit file.** Every test passes a
recorder as `runner=` and a temp directory as `config_dir=`, and
`service._default_runner` refuses outright when `PYTEST_CURRENT_TEST` is set. Both
guards were written on 2026-09-06, the day the cli.v2 Core 6 probe invoked
`service install` with no injection and enabled a real daily timer on this device.
"""

from __future__ import annotations

import os
import socket
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


@pytest.fixture
def user_runtime(tmp_path: Path) -> tuple[Path, Path, Path, int, socket.socket]:
    """A private runtime directory with a real UNIX socket, never under `/run/user`."""
    uid = os.geteuid()
    root = tmp_path / "run" / "user"
    runtime = root / str(uid)
    runtime.mkdir(parents=True, mode=0o700)
    runtime.chmod(0o700)
    bus = runtime / "bus"
    listener = socket.socket(socket.AF_UNIX)
    listener.bind(str(bus))
    try:
        yield root, runtime, bus, uid, listener
    finally:
        listener.close()


def test_systemd_user_environment_adds_only_a_safe_runtime_dir(
    user_runtime: tuple[Path, Path, Path, int, socket.socket], monkeypatch: pytest.MonkeyPatch
) -> None:
    root, runtime, _, uid, _ = user_runtime
    monkeypatch.setenv("USER", "not-the-effective-user")
    before = dict(os.environ)
    supplied = {"XDG_RUNTIME_DIR": "", "DBUS_SESSION_BUS_ADDRESS": "", "EXTRA": "kept"}

    child = service.systemd_user_environment(supplied, root)

    assert child["XDG_RUNTIME_DIR"] == str(runtime)
    assert "DBUS_SESSION_BUS_ADDRESS" not in child or child["DBUS_SESSION_BUS_ADDRESS"] == ""
    assert child["EXTRA"] == "kept"
    assert supplied["XDG_RUNTIME_DIR"] == ""
    assert os.environ == before
    assert runtime.name == str(uid)


def test_systemd_user_environment_uses_an_injected_mapping_as_the_entire_child_environment(
    user_runtime: tuple[Path, Path, Path, int, socket.socket], monkeypatch: pytest.MonkeyPatch
) -> None:
    root, runtime, _, _, _ = user_runtime
    monkeypatch.setenv("XDG_RUNTIME_DIR", "/host/runtime")
    monkeypatch.setenv("HOST_ONLY", "must-not-leak")
    supplied: dict[str, str] = {}

    child = service.systemd_user_environment(supplied, root)

    assert child == {"XDG_RUNTIME_DIR": str(runtime)}
    assert supplied == {}
    assert os.environ["XDG_RUNTIME_DIR"] == "/host/runtime"
    assert os.environ["HOST_ONLY"] == "must-not-leak"


@pytest.mark.parametrize(
    "supplied",
    [
        {"XDG_RUNTIME_DIR": "/private/runtime", "DBUS_SESSION_BUS_ADDRESS": ""},
        {"XDG_RUNTIME_DIR": "", "DBUS_SESSION_BUS_ADDRESS": "unix:path=/private/bus"},
    ],
)
def test_systemd_user_environment_preserves_any_explicit_bus_setting(
    supplied: dict[str, str], tmp_path: Path
) -> None:
    child = service.systemd_user_environment(supplied, tmp_path / "not-present")
    assert {key: child[key] for key in supplied} == supplied


@pytest.mark.parametrize(
    ("breakage", "needle"),
    [
        ("runtime-mode", "mode 0700"),
        ("runtime-owner", "runtime directory"),
        ("runtime-file", "not a directory"),
        ("runtime-link", "is a symlink"),
        ("bus-missing", "cannot inspect"),
        ("bus-file", "not a UNIX socket"),
        ("bus-link", "is a symlink"),
        ("bus-owner", "user bus"),
    ],
)
def test_systemd_user_environment_rejects_unsafe_fallbacks(
    user_runtime: tuple[Path, Path, Path, int, socket.socket],
    monkeypatch: pytest.MonkeyPatch,
    breakage: str,
    needle: str,
) -> None:
    root, runtime, bus, uid, _ = user_runtime
    if breakage == "runtime-mode":
        runtime.chmod(0o750)
    elif breakage == "runtime-owner":
        other_uid = uid + 1
        other_runtime = root / str(other_uid)
        runtime.rename(other_runtime)
        monkeypatch.setattr(service.os, "geteuid", lambda: other_uid)
    elif breakage == "runtime-file":
        bus.unlink()
        runtime.rmdir()
        runtime.write_text("not a directory", encoding="utf-8")
    elif breakage == "runtime-link":
        bus.unlink()
        runtime.rmdir()
        runtime.symlink_to(root / "elsewhere")
    elif breakage == "bus-missing":
        bus.unlink()
    elif breakage == "bus-file":
        bus.unlink()
        bus.write_text("not a socket", encoding="utf-8")
    elif breakage == "bus-link":
        bus.unlink()
        bus.symlink_to(root / "elsewhere")
    else:
        real_lstat = os.lstat

        def wrong_bus_owner(path: str | os.PathLike[str]) -> os.stat_result:
            observed = real_lstat(path)
            if Path(path) == bus:
                values = list(observed)
                values[4] = uid + 1
                return os.stat_result(values)
            return observed

        monkeypatch.setattr(service.os, "lstat", wrong_bus_owner)

    with pytest.raises(service.UserBusUnavailable, match=needle):
        service.systemd_user_environment(
            {"XDG_RUNTIME_DIR": "", "DBUS_SESSION_BUS_ADDRESS": ""}, root
        )


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


def test_default_systemctl_paths_receive_one_recovered_child_environment(
    units: Path, store: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The default runner, not an injected Recorder, crosses the process boundary."""
    child_env = {"XDG_RUNTIME_DIR": "/safe/runtime", "UNCHANGED": "yes"}
    calls: list[tuple[tuple[str, ...], dict[str, object]]] = []

    def subprocess_spy(argv, **kwargs):
        calls.append((tuple(argv), kwargs))
        return subprocess.CompletedProcess(argv, 0, "enabled", "")

    monkeypatch.delenv("PYTEST_CURRENT_TEST", raising=False)
    monkeypatch.delenv(service.UNIT_DIR_ENV, raising=False)
    monkeypatch.setattr(service, "_default_runner", service._unpatched_default_runner)
    monkeypatch.setattr(service, "systemd_user_environment", lambda: dict(child_env))
    monkeypatch.setattr(service.subprocess, "run", subprocess_spy)

    assert service.install(
        config_dir=units, executable=EXE, platform=service.SYSTEMD, home=store
    ).ok
    assert service.status(config_dir=units, platform=service.SYSTEMD, home=store).enabled is True
    service.run_verb("restart", config_dir=units, platform=service.SYSTEMD, home=store)
    service.run_verb("stop", config_dir=units, platform=service.SYSTEMD, home=store)
    assert service.uninstall(config_dir=units, platform=service.SYSTEMD, home=store).ok

    expected = [
        ("systemctl", "--user", "daemon-reload"),
        ("systemctl", "--user", "enable", "--now", service.timer_unit(store)),
        ("systemctl", "--user", "is-enabled", service.timer_unit(store)),
        ("systemctl", "--user", "is-enabled", service.timer_unit(store)),
        ("systemctl", "--user", "restart", service.timer_unit(store)),
        ("systemctl", "--user", "is-enabled", service.timer_unit(store)),
        ("systemctl", "--user", "stop", service.timer_unit(store)),
        ("systemctl", "--user", "disable", "--now", service.timer_unit(store)),
        ("systemctl", "--user", "daemon-reload"),
    ]
    assert [argv for argv, _ in calls] == expected
    assert all(kwargs["env"] == child_env for _, kwargs in calls)


def test_default_runner_leaves_launchctl_and_journalctl_environments_unchanged(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[dict[str, object]] = []

    def subprocess_spy(argv, **kwargs):
        calls.append(kwargs)
        return subprocess.CompletedProcess(argv, 0, "", "")

    monkeypatch.delenv("PYTEST_CURRENT_TEST", raising=False)
    monkeypatch.delenv(service.UNIT_DIR_ENV, raising=False)
    monkeypatch.setattr(service.subprocess, "run", subprocess_spy)
    monkeypatch.setattr(
        service,
        "systemd_user_environment",
        lambda: (_ for _ in ()).throw(AssertionError("non-systemctl command asked for a bus")),
    )

    real_runner = service._unpatched_default_runner
    assert real_runner(["launchctl", "list"])[0] == 0
    assert real_runner(["journalctl", "--user", "-n", "1"])[0] == 0
    assert all("env" not in kwargs for kwargs in calls)


def test_default_runner_keeps_explicit_bus_failure_output_and_adds_one_hint(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    raw_error = "Failed to connect to bus: No such file or directory"

    def subprocess_spy(argv, **kwargs):
        return subprocess.CompletedProcess(argv, 1, "", raw_error)

    monkeypatch.delenv("PYTEST_CURRENT_TEST", raising=False)
    monkeypatch.delenv(service.UNIT_DIR_ENV, raising=False)
    monkeypatch.setenv("XDG_RUNTIME_DIR", "/explicit-but-bad")
    monkeypatch.delenv("DBUS_SESSION_BUS_ADDRESS", raising=False)
    monkeypatch.setattr(service.subprocess, "run", subprocess_spy)

    code, output = service._unpatched_default_runner(["systemctl", "--user", "daemon-reload"])
    assert code == 1
    assert output.startswith(raw_error)
    assert output.count("Hint:") == 1


def test_default_uninstall_preserves_units_when_the_runner_loses_the_bus_after_preflight(
    units: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    units.mkdir()
    targets = [units / service.SERVICE_UNIT, units / service.TIMER_UNIT]
    for target in targets:
        target.write_text("unit", encoding="utf-8")
    calls = iter([{"XDG_RUNTIME_DIR": "/safe/runtime"}, service.UserBusUnavailable("bus gone")])

    def environment() -> dict[str, str]:
        value = next(calls)
        if isinstance(value, Exception):
            raise value
        return value

    monkeypatch.delenv("PYTEST_CURRENT_TEST", raising=False)
    monkeypatch.delenv(service.UNIT_DIR_ENV, raising=False)
    monkeypatch.setattr(service, "_default_runner", service._unpatched_default_runner)
    monkeypatch.setattr(service, "systemd_user_environment", environment)

    result = service.uninstall(config_dir=units, platform=service.SYSTEMD)

    assert not result.ok
    assert result.steps[-1].returncode == service.USER_BUS_UNAVAILABLE
    assert all(target.exists() for target in targets)


def test_default_uninstall_preserves_units_on_a_real_bus_connection_error(
    units: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    units.mkdir()
    targets = [units / service.SERVICE_UNIT, units / service.TIMER_UNIT]
    for target in targets:
        target.write_text("unit", encoding="utf-8")
    calls: list[tuple[str, ...]] = []

    def subprocess_spy(argv, **kwargs):
        calls.append(tuple(argv))
        return subprocess.CompletedProcess(argv, 1, "", "Failed to connect to bus: unavailable")

    monkeypatch.delenv("PYTEST_CURRENT_TEST", raising=False)
    monkeypatch.delenv(service.UNIT_DIR_ENV, raising=False)
    monkeypatch.setattr(service, "_default_runner", service._unpatched_default_runner)
    monkeypatch.setattr(
        service, "systemd_user_environment", lambda: {"XDG_RUNTIME_DIR": "/safe/runtime"}
    )
    monkeypatch.setattr(service.subprocess, "run", subprocess_spy)

    result = service.uninstall(config_dir=units, platform=service.SYSTEMD)

    assert not result.ok
    assert calls == [("systemctl", "--user", "disable", "--now", service.TIMER_UNIT)]
    assert all(target.exists() for target in targets)


@pytest.mark.parametrize("code", [125, 126])
@pytest.mark.parametrize("output", ["user bus unavailable", ""])
def test_injected_uninstall_preserves_units_on_unavailable_bus_codes(
    units: Path, code: int, output: str
) -> None:
    units.mkdir()
    targets = [units / service.SERVICE_UNIT, units / service.TIMER_UNIT]
    for target in targets:
        target.write_text("unit", encoding="utf-8")

    calls = []

    def runner(argv):
        calls.append(tuple(argv))
        return code, output

    result = service.uninstall(
        runner=runner,
        config_dir=units,
        platform=service.SYSTEMD,
    )

    assert not result.ok
    assert all(target.exists() for target in targets)
    assert result.removed == []
    assert calls == [("systemctl", "--user", "disable", "--now", service.TIMER_UNIT)]


def test_status_reports_unknown_when_a_user_bus_query_fails(
    units: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    units.mkdir()
    for target in (units / service.SERVICE_UNIT, units / service.TIMER_UNIT):
        target.write_text("unit", encoding="utf-8")

    def subprocess_spy(argv, **kwargs):
        return subprocess.CompletedProcess(argv, 1, "", "Failed to connect to bus: unavailable")

    monkeypatch.delenv("PYTEST_CURRENT_TEST", raising=False)
    monkeypatch.delenv(service.UNIT_DIR_ENV, raising=False)
    monkeypatch.setattr(service, "_default_runner", service._unpatched_default_runner)
    monkeypatch.setattr(
        service, "systemd_user_environment", lambda: {"XDG_RUNTIME_DIR": "/safe/runtime"}
    )
    monkeypatch.setattr(service.subprocess, "run", subprocess_spy)

    default = service.status(config_dir=units, platform=service.SYSTEMD)
    injected = service.status(
        runner=lambda argv: (126, "user bus unavailable"),
        config_dir=units,
        platform=service.SYSTEMD,
    )

    assert default.enabled is None and "Failed to connect to bus" in default.detail
    assert injected.enabled is None and "user bus unavailable" in injected.detail


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


def test_default_install_and_uninstall_do_not_change_units_when_the_bus_is_unavailable(
    units: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    units.mkdir()
    existing = units / service.SERVICE_UNIT
    existing.write_text("do not overwrite", encoding="utf-8")

    def unavailable() -> dict[str, str]:
        raise service.UserBusUnavailable("user runtime directory is missing")

    monkeypatch.setattr(service, "systemd_user_environment", unavailable)
    install = service.install(config_dir=units, executable=EXE, platform=service.SYSTEMD)
    uninstall = service.uninstall(config_dir=units, platform=service.SYSTEMD)

    assert install.steps[0].returncode == service.USER_BUS_UNAVAILABLE
    assert uninstall.steps[0].returncode == service.USER_BUS_UNAVAILABLE
    assert existing.read_text(encoding="utf-8") == "do not overwrite"
    assert not (units / service.TIMER_UNIT).exists()


def test_injected_runner_does_not_require_a_host_user_bus(
    units: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    runner = Recorder()
    monkeypatch.setattr(
        service,
        "systemd_user_environment",
        lambda: (_ for _ in ()).throw(
            AssertionError("injected runner must remain host independent")
        ),
    )

    result = service.install(
        runner=runner, config_dir=units, executable=EXE, platform=service.SYSTEMD
    )

    assert result.ok
    assert runner.calls == [
        ("systemctl", "--user", "daemon-reload"),
        ("systemctl", "--user", "enable", "--now", service.TIMER_UNIT),
    ]


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


# ------------------------------------------------------ cli.v3 §6: one timer per instance


def test_a_unit_name_carries_the_instance_and_two_instances_never_collide(
    tmp_path: Path,
) -> None:
    """cli.v3 §6: "each unit name is derived from that instance's path"."""
    one, two = tmp_path / "alpha", tmp_path / "beta"
    same_name_elsewhere = tmp_path / "nested" / "alpha"
    names = {
        str(home): (service.service_unit(home), service.timer_unit(home))
        for home in (one, two, same_name_elsewhere)
    }
    for home, pair in names.items():
        print(f"{home} -> {pair[1]}")
    assert len({pair for pair in names.values()}) == 3, names
    # Readable: the instance's own directory name survives into the unit name.
    assert "alpha" in names[str(one)][1] and "beta" in names[str(two)][1]
    # Stable: the same instance always renders the same name.
    assert service.timer_unit(one) == service.timer_unit(str(one))
    # `home=None` is the pre-v3 device-wide name, unchanged.
    assert service.timer_unit(None) == service.TIMER_UNIT == "amplifier-memory-suggest.timer"


def test_installing_two_instances_leaves_two_timers_and_uninstall_touches_only_one(
    tmp_path: Path,
) -> None:
    """cli.v3 §6: "neither can silently uninstall the other's timer", and `status` lists both."""
    units = tmp_path / "units"
    one, two = tmp_path / "alpha", tmp_path / "beta"
    for home in (one, two):
        amplifier_memory.init(home, timer=False)
        amplifier_memory.service_install(
            runner=Recorder(),
            config_dir=units,
            executable="/usr/bin/amplifier-memory",
            platform=service.SYSTEMD,
            home=home,
        )
    on_disk = sorted(p.name for p in units.iterdir())
    print("units on disk:", on_disk)
    assert len(on_disk) == 4, on_disk

    listed = amplifier_memory.installed_timers(config_dir=units, home=one, platform=service.SYSTEMD)
    for found in listed:
        print("  ", found.render())
    assert sorted(str(t.instance) for t in listed) == sorted([str(one), str(two)])
    assert [t.resolved for t in listed].count(True) == 1, "the resolved instance is not marked"

    amplifier_memory.service_uninstall(
        runner=Recorder(), config_dir=units, platform=service.SYSTEMD, home=two
    )
    left = sorted(p.name for p in units.iterdir())
    print("after uninstalling beta:", left)
    assert left == sorted([service.service_unit(one), service.timer_unit(one)]), left


def test_the_unit_runs_the_pass_for_its_own_instance(tmp_path: Path) -> None:
    """cli.v3 §6: without `--home`, two instances' timers would run the same command."""
    home = tmp_path / "alpha"
    body = service.render_service("/usr/bin/amplifier-memory", home)
    print(body)
    assert f"ExecStart=/usr/bin/amplifier-memory suggest --home {home}" in body, body
    assert str(home) in service.render_timer(home), service.render_timer(home)


def test_the_real_runner_refuses_while_the_unit_dir_is_redirected(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """amplifier_bundle_memory-azy: `enable --now <name>` would resolve against the REAL units.

    The pytest half of the guard is why nothing under tests/ reaches systemctl; this is
    the other half, and it is what makes a standalone conformance kit run safe too. Both
    are asserted through `redirect_reason`, which is the predicate `_default_runner` uses.
    """
    monkeypatch.delenv(service.UNIT_DIR_ENV, raising=False)
    monkeypatch.setenv("PYTEST_CURRENT_TEST", "this test")
    assert "PYTEST_CURRENT_TEST" in (service.redirect_reason() or ""), service.redirect_reason()

    monkeypatch.delenv("PYTEST_CURRENT_TEST", raising=False)
    assert service.redirect_reason() is None, "nothing is redirected, so nothing is refused"
    monkeypatch.setenv(service.UNIT_DIR_ENV, "/tmp/somewhere-else")
    reason = service.redirect_reason()
    print("refusal reason:", reason)
    assert reason and "/tmp/somewhere-else" in reason
    # `conftest.no_shelling_out` has already replaced `_default_runner` with a recorder
    # for every test; it kept the real one under this name, and the real one is the
    # subject here.
    real_runner = service._unpatched_default_runner
    with pytest.raises(RuntimeError) as refused:
        real_runner(["systemctl", "--user", "enable", "--now", "whatever.timer"])
    print(refused.value)
    assert "would act on this device's own units" in str(refused.value)
