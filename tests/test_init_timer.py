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
    # cli.v3 §8: the layout, then the seeding answer as m-001. Two commits, no more.
    assert len(log.splitlines()) == 2, "the initial commits are missing or doubled"
    assert "[m-001]" in log.splitlines()[0], log

    # The units are the ones `service install` renders — written by it, not by `init` —
    # and cli.v3 §6 puts THIS instance in their names and `--home` in the ExecStart.
    unit, timer = service.service_unit(home), service.timer_unit(home)
    assert sorted(p.name for p in units.iterdir()) == sorted([unit, timer])
    assert service.instance_tag(home) in timer, timer
    assert "OnCalendar=daily" in (units / timer).read_text(encoding="utf-8")
    assert f"suggest --home {home}" in (units / unit).read_text(encoding="utf-8")
    assert no_shelling_out == [
        ("systemctl", "--user", "daemon-reload"),
        ("systemctl", "--user", "enable", "--now", timer),
    ]

    last_two = result.output.rstrip().splitlines()[-2:]
    print("last two lines:", last_two)
    assert f"amplifier-memory service uninstall --home {home}" in last_two[0], last_two
    # store.v3 §2: the cost knob is `config.yaml` INSIDE the instance init just made.
    assert str(home / "config.yaml") in last_two[1], last_two


def test_service_status_and_doctor_read_back_the_timer_init_installed(
    this_is_the_device_store: Path, units: Path
) -> None:
    """cli.v2 §8 Conformance: `service status` says so, and `doctor`'s row reads it."""
    amplifier_memory.init()

    def enabled(argv):  # the `systemctl --user is-enabled` query, answered
        return 0, "enabled"

    state = amplifier_memory.service_state(
        runner=enabled, config_dir=units, home=this_is_the_device_store
    )
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


# ------------------------------------------- cli.v3 §8: the move offer and the one question


def test_the_seeding_question_saves_the_humans_own_answer_as_m_001(
    this_is_the_device_store: Path,
) -> None:
    """cli.v3 §8: one question, the answer saved as `m-001` writer=human, quote == text.

    Only the human's own words become memory (AGENTS.md rule 7), so nothing here is
    minted: what `save` records as the quote is the very text the human typed.
    """
    typed = "corrections I have already made once, and how I like commits written"
    asked: list[tuple[str, str]] = []

    def ask(question: str, default: str) -> str:
        asked.append((question, default))
        return typed

    report = amplifier_memory.build_instance(this_is_the_device_store, timer=False, ask=ask)
    print(report.render())
    assert asked == [(amplifier_memory.SEED_QUESTION, amplifier_memory.SEED_DEFAULT)], asked

    # The line says whose answer it was — "your answer", not "the default".
    assert report.seed_asked is True and "no TTY" not in report.render(), report.render()

    record = amplifier_memory.why("m-001", this_is_the_device_store)[0]
    print("why m-001:", record)
    assert report.seed_id == "m-001"
    assert record["text"] == record["quote"] == typed
    assert record["writer"] == "human"


def test_no_tty_takes_the_default_and_says_so(this_is_the_device_store: Path) -> None:
    """cli.v3 §8: "with no TTY it takes the default and says so" — never a silent default."""
    report = amplifier_memory.build_instance(this_is_the_device_store, timer=False)
    printed = report.render()
    print(printed)
    assert report.seed_asked is False
    assert report.seed_text == amplifier_memory.SEED_DEFAULT
    assert "no TTY to ask" in printed, printed
    assert amplifier_memory.SEED_DEFAULT in printed, printed


@pytest.fixture
def legacy_device(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> tuple[Path, Path]:
    """A device whose only store is the pre-v3 `~/.amplifier/memory`, with $HOME redirected."""
    fake_home = tmp_path / "home"
    legacy = fake_home / ".amplifier" / "memory"
    amplifier_memory.init(legacy, timer=False)
    monkeypatch.delenv("AMPLIFIER_MEMORY_HOME", raising=False)
    monkeypatch.setattr(Path, "home", staticmethod(lambda: fake_home))
    return legacy, fake_home / store.DEFAULT_HOME_NAME


def test_init_offers_to_move_the_older_store_and_prints_what_it_did(
    legacy_device: tuple[Path, Path],
) -> None:
    """cli.v3 §8: the older store moves only on a yes, and the move is always printed."""
    legacy, default = legacy_device
    report = amplifier_memory.build_instance(timer=False, confirm=lambda _q: True)
    printed = report.render()
    print(printed)
    assert report.move_offered and report.moved_from == legacy
    assert report.home == default and default.is_dir() and not legacy.exists()
    assert f"moved {legacy} to {default}" in printed, printed
    # The memories moved with it: the same git history, at the new path.
    assert (default / "MEMORY.md").is_file()


def test_a_declined_move_leaves_the_older_store_exactly_where_it_is(
    legacy_device: tuple[Path, Path],
) -> None:
    """cli.v3 §8: "never a silent move" cuts both ways — a no moves nothing, and says so."""
    legacy, default = legacy_device
    before = fingerprint(legacy)
    report = amplifier_memory.build_instance(timer=False, confirm=lambda _q: False)
    printed = report.render()
    print(printed)
    assert report.move_offered and report.moved_from is None
    assert report.home == legacy and not default.exists()
    assert fingerprint(legacy) == before, "a declined offer changed the store"
    assert f"left {legacy} where it is" in printed, printed


def test_no_tty_never_moves_a_store(legacy_device: tuple[Path, Path]) -> None:
    """An unattended run must never move a human's memories: no TTY is a no."""
    legacy, default = legacy_device
    report = amplifier_memory.build_instance(timer=False)
    print(report.render())
    assert report.moved_from is None and legacy.is_dir() and not default.exists()


def test_the_offer_is_not_made_when_an_instance_was_named(
    legacy_device: tuple[Path, Path], tmp_path: Path
) -> None:
    """§8's offer is about the DEFAULT instance; naming one is already an answer."""
    legacy, _ = legacy_device
    chosen = tmp_path / "chosen"
    report = amplifier_memory.build_instance(chosen, timer=False, confirm=_never_asked)
    print(report.render())
    assert report.move_offered is False and report.home == chosen and legacy.is_dir()


def _never_asked(question: str) -> bool:
    raise AssertionError(f"init asked about the move when no offer was due: {question!r}")
