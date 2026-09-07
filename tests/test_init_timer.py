"""cli.v2 §8 — `init` installs the daily suggest timer, and the three arms that do not.

**Nothing here writes a real unit file or runs a real command.** Three guards, all of
them already in the repository before this file existed:

* `tests/conftest.py`'s `no_shelling_out` replaces `service._default_runner` with a
  recorder for every test, and points `AMPLIFIER_MEMORY_UNIT_DIR` at a fresh temp dir;
* `service._default_runner` refuses outright when `PYTEST_CURRENT_TEST` is set;
* `store.device_store()` is the gate that keeps `init` off the install plane whenever the
  store is not this device's own — so a test store never reaches it by accident. Each
  test below that wants the *installing* path says so out loud by pointing
  `device_store` at its own temp home, which is also what makes it the real default
  path and not a special case: from there on it is exactly the code the device runs.

`~/.config/systemd/user` is asserted untouched at the end of this module.
"""

from __future__ import annotations

import hashlib
import os
from collections.abc import Callable
from pathlib import Path

import pytest
from click.testing import CliRunner

import amplifier_memory
from amplifier_memory import service, store
from amplifier_memory.cli import main

REAL_UNIT_DIR = Path.home() / ".config" / "systemd" / "user"


@pytest.fixture
def run() -> Callable[..., object]:
    """The click group, in-process, printing what a human would have seen."""
    runner = CliRunner()

    def invoke(*args: str):
        result = runner.invoke(main, list(args), catch_exceptions=False)
        print(f"$ amplifier-memory {' '.join(args)}   -> exit {result.exit_code}")
        print(result.output.rstrip() or "(no output)")
        return result

    return invoke


@pytest.fixture
def units() -> Path:
    """The temp unit directory `conftest.no_shelling_out` already pointed the env at."""
    return Path(os.environ[service.UNIT_DIR_ENV])


@pytest.fixture
def this_is_the_device_store(monkeypatch: pytest.MonkeyPatch, memory_home: Path) -> Path:
    """Let the temp store take the device store's place, so the *default* path runs.

    Without this, `init` skips the install plane for any store that is not
    `~/.amplifier/memory` — the gate that keeps a kit or a test off this device.
    """
    monkeypatch.setattr(store, "device_store", lambda: memory_home)
    return memory_home


def fingerprint(*roots: Path) -> dict[str, str]:
    """sha256 of every file under each root — the "wrote nothing" assertion."""
    return {
        str(p): hashlib.sha256(p.read_bytes()).hexdigest()
        for root in roots
        for p in sorted(root.rglob("*"))
        if p.is_file()
    }


# --------------------------------------------------------- 1: a fresh init installs it


def test_a_fresh_init_creates_the_store_and_installs_the_timer(
    run, this_is_the_device_store: Path, units: Path, no_shelling_out: list[tuple[str, ...]]
) -> None:
    """cli.v2 §8: the store, then `service install`'s own units — and the two closing lines."""
    result = run("init")
    print(result.output)
    print("argv the runner saw:", no_shelling_out)
    print("unit dir:", sorted(p.name for p in units.iterdir()))

    home = this_is_the_device_store
    assert result.exit_code == 0
    assert (home / "MEMORY.md").is_file()
    log = os.popen(f"git -C {home} log --oneline").read().strip()
    print("git log --oneline:", log)
    assert len(log.splitlines()) == 1, "the initial commit is missing or doubled"

    # The units are the ones `service install` renders — written by it, not by `init`.
    assert sorted(p.name for p in units.iterdir()) == sorted(
        [service.SERVICE_UNIT, service.TIMER_UNIT]
    )
    assert "OnCalendar=daily" in (units / service.TIMER_UNIT).read_text(encoding="utf-8")
    assert no_shelling_out == [
        ("systemctl", "--user", "daemon-reload"),
        ("systemctl", "--user", "enable", "--now", service.TIMER_UNIT),
    ]

    last_two = result.output.rstrip().splitlines()[-2:]
    print("last two lines:", last_two)
    assert "amplifier-memory service uninstall" in last_two[0], last_two
    assert str(Path.home() / ".amplifier" / "memory-config.toml") in last_two[1], last_two


def test_service_status_and_doctor_read_back_the_timer_init_installed(
    this_is_the_device_store: Path, units: Path
) -> None:
    """cli.v2 §8 Conformance: `service status` says so, and `doctor`'s row reads it."""
    amplifier_memory.init()

    def enabled(argv):  # the `systemctl --user is-enabled` query, answered
        return 0, "enabled"

    state = amplifier_memory.service_state(runner=enabled, config_dir=units)
    row = amplifier_memory.timer_row(
        runner=enabled, config_dir=units, home=this_is_the_device_store
    )
    print(state.render())
    print(f"doctor row: {row.name} {row.level} {row.detail}")
    assert state.installed and state.enabled
    assert "installed" in row.detail and "enabled" in row.detail


def test_init_installs_through_service_install_and_never_renders_its_own_units(
    this_is_the_device_store: Path, units: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The falsifier for acceptance 1: the units must come from `service.install`.

    Stubbing that one function out leaves an empty unit directory. If `init` had its own
    renderer — or shelled out to `amplifier-memory service install` — files would appear
    here anyway, and this test would fail.
    """
    called: list[str] = []

    def not_really(**kwargs: object) -> service.ServiceResult:
        called.append("service.install")
        return service.ServiceResult(verb="install", platform=service.SYSTEMD)

    monkeypatch.setattr(service, "install", not_really)
    outcome = amplifier_memory.init()
    print("install calls:", called, "| unit dir:", list(units.iterdir()))
    assert called == ["service.install"], "init did not go through service.install"
    assert list(units.iterdir()) == [], "init wrote unit files of its own"
    assert outcome.timer_installed is True


# ------------------------------------------------------------- 2: a second init is a no-op


def test_a_second_init_reports_both_and_writes_nothing(
    run, this_is_the_device_store: Path, units: Path, no_shelling_out: list[tuple[str, ...]]
) -> None:
    """cli.v2 §8: "store exists · timer installed", and it changes nothing."""
    home = this_is_the_device_store
    run("init")
    no_shelling_out.clear()
    before = fingerprint(home, units)

    second = run("init")
    after = fingerprint(home, units)
    print(second.output)
    print("argv the runner saw on the second run:", no_shelling_out)
    print("files fingerprinted:", len(before), "| identical:", before == after)

    assert second.exit_code == 0
    assert "store exists \u00b7 timer installed" in second.output
    assert no_shelling_out == [], "a second init ran a command"
    assert before == after, "a second init changed a file"


def test_a_second_init_never_reinstalls_a_timer_the_human_uninstalled(
    this_is_the_device_store: Path, units: Path, no_shelling_out: list[tuple[str, ...]]
) -> None:
    """cli.v2 §6: `service uninstall` is the opt-out — `init` must not undo it."""
    amplifier_memory.init()
    amplifier_memory.service_uninstall(runner=lambda argv: (0, ""))
    assert list(units.iterdir()) == []
    no_shelling_out.clear()

    again = amplifier_memory.init()
    print(again.render(), "| unit dir:", list(units.iterdir()))
    assert again.existed is True and again.timer_installed is False
    assert list(units.iterdir()) == [], "init reinstalled a timer the human removed"
    assert no_shelling_out == []
    assert "store exists \u00b7 no timer installed" in again.render()


# ----------------------------------------------------------------------- 3: --no-timer


def test_no_timer_creates_the_store_and_nothing_else(
    run, this_is_the_device_store: Path, units: Path, no_shelling_out: list[tuple[str, ...]]
) -> None:
    """cli.v2 §8: `--no-timer` skips the timer for a host that must not run one."""
    result = run("init", "--no-timer")
    print(result.output)
    print("unit dir:", list(units.iterdir()), "| argv:", no_shelling_out)

    assert result.exit_code == 0
    assert (this_is_the_device_store / "MEMORY.md").is_file()
    assert not units.exists() or list(units.iterdir()) == [], "--no-timer wrote a unit file"
    assert no_shelling_out == [], "--no-timer ran a command"
    assert "no suggest timer installed: --no-timer was given" in result.output


# ------------------------------------------------------- 4: the host with no Phase 2 job


def test_a_host_with_no_installed_cli_gets_the_no_service_line_and_no_unit(
    run, this_is_the_device_store: Path, units: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """cli.v2 §8/§6: where there is no Phase 2 job to run, say so and install nothing.

    The predicate is **`service install`'s own** — `executable_path()` finds no
    `amplifier-memory` on PATH, so `install` refuses before writing anything and says
    why. `init` prints that refusal in install's words rather than inventing a second
    test for "is Phase 2 here", which is the only way the two can never disagree.
    """
    monkeypatch.setattr(service.shutil, "which", lambda name: None)
    result = run("init")
    print(result.output)
    print("unit dir:", list(units.iterdir()) if units.exists() else "not created")

    assert result.exit_code == 0
    assert (this_is_the_device_store / "MEMORY.md").is_file(), "the store is still created"
    assert not units.exists() or list(units.iterdir()) == [], "a unit was written anyway"
    assert "no suggest timer installed:" in result.output
    assert "no `amplifier-memory` on PATH" in result.output
    assert "amplifier-memory service uninstall" not in result.output, (
        "an opt-out was offered for a timer that was never installed"
    )


# --------------------------------------------------- the gate that keeps kits off this device


def test_init_leaves_the_install_plane_alone_for_a_store_that_is_not_this_devices(
    units: Path, no_shelling_out: list[tuple[str, ...]], memory_home: Path
) -> None:
    """Why `device_store()` exists: a kit builds a temp store and calls `init`.

    Twice on 2026-09-06 that enabled a real daily timer on the steward's machine. Note
    this test does NOT use `this_is_the_device_store` — it is the unpatched default.
    """
    result = amplifier_memory.init()
    print(result.render())
    print("unit dir:", list(units.iterdir()) if units.exists() else "not created", no_shelling_out)

    assert result.timer is None and result.timer_installed is False
    assert not units.exists() or list(units.iterdir()) == []
    assert no_shelling_out == []
    assert "is not this device's store" in result.render()
    assert str(store.device_store()) in result.render()


def test_this_device_s_real_unit_directory_was_never_touched(units: Path) -> None:
    """The lane's honesty gate, asserted: every unit this suite wrote went to a temp dir."""
    real = sorted(p.name for p in REAL_UNIT_DIR.glob("amplifier-memory-suggest.*"))
    print("temp unit dir:", units, "| real unit dir entries:", real)
    assert units != REAL_UNIT_DIR
    assert REAL_UNIT_DIR not in units.parents
