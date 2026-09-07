"""The suggest timer — suggestions.v1 Core 1, cli.v2 Core 6.

"A timer, not a service." `amplifier-memory suggest` runs once a day, does its work,
and exits. Nothing is resident: the systemd unit is `Type=oneshot` and carries no
`[Install]` section of its own — only the **timer** is enabled, so nothing starts the
job except the clock (and `Persistent=true`, which catches up one missed run after the
machine was off).

What `install` does, in this order:

1. render `amplifier-memory-suggest.service` and `.timer` into the user unit directory;
2. ``systemctl --user daemon-reload``;
3. ``systemctl --user enable --now amplifier-memory-suggest.timer``.

If any step fails, **every file this call wrote is removed** (cli.v2 Core 6: "rolls back
written units if any step fails") and the failure is reported with the step's own output.
A unit file that was already there is never touched by the rollback — reverting someone
else's install is not a rollback.

Verified argv (AGENTS.md rule 5), against this device's own `--help`, 2026-09-06:

    systemctl --user daemon-reload      "Reload systemd manager configuration"
    systemctl --user enable --now UNIT  "Enable one or more unit files" / "--now: Start
                                         or stop unit after enabling or disabling it"
    systemctl --user disable --now UNIT "Disable one or more unit files"
    systemctl --user is-enabled UNIT    "Check whether unit files are enabled"
    systemctl --user start|stop|restart UNIT
    journalctl --user -u UNIT           "-u --unit=UNIT: Show logs from the specified unit"

`tests/test_service.py::test_the_systemctl_argv_matches_systemctl_help` prints that help.

macOS is **rendered but unverified.** The launchd branch writes
`~/Library/LaunchAgents/com.amplifier-memory.suggest.plist` and runs
``launchctl unload -w <plist>`` / ``launchctl load -w <plist>``. This lane runs on Linux
and cannot verify `launchctl`'s argv against its own `--help` the way the systemd side is
verified, so it says so — here, in `conformance/suggestions/run.py`, and in the ledger
row. Rendering is exercised in tests; the enable step is a fake runner on this device.

The runner is injectable and **no test in this repository ever runs a real `systemctl`**:
`tests/conftest.py` replaces the process runner for the whole suite, and every test here
passes its own recorder.

This module imports only the standard library and this package: no `click`.
"""

from __future__ import annotations

import os
import platform as _platform
import shutil
import subprocess
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from pathlib import Path

from .suggest import last_log_line, parse_log_line

#: What a step runner returns: an exit code and whatever the command said.
Runner = Callable[[Sequence[str]], "tuple[int, str]"]

UNIT_BASE = "amplifier-memory-suggest"
SERVICE_UNIT = f"{UNIT_BASE}.service"
TIMER_UNIT = f"{UNIT_BASE}.timer"
PLIST_LABEL = "com.amplifier-memory.suggest"
PLIST_NAME = f"{PLIST_LABEL}.plist"

SYSTEMD = "systemd"
LAUNCHD = "launchd"

#: cli.v2 Core 1's `service` verbs. `install`/`uninstall`/`status` are the clause's
#: substance; the other four are one `systemctl` call each on the same timer.
VERBS = ("install", "uninstall", "start", "stop", "restart", "status", "logs")

#: suggestions.v1 Core 1: once a day, catching up one missed run after the machine was off.
ON_CALENDAR = "daily"


#: The one environment override for where units are written, so a check never has to
#: reach this device's real unit directory to exercise the install path. It exists
#: because a conformance probe did exactly that on 2026-09-06: `run("service",
#: "install")` through the CLI wrote both units into `~/.config/systemd/user/` and ran a
#: real `systemctl --user enable --now`, enabling a daily timer on the steward's machine
#: that nobody asked for. `AMPLIFIER_MEMORY_HOME` already plays this role for the store
#: (PINS.md); this is its twin for the install plane.
UNIT_DIR_ENV = "AMPLIFIER_MEMORY_UNIT_DIR"


def unit_dir(config_dir: str | os.PathLike[str] | None = None) -> Path:
    """`${XDG_CONFIG_HOME:-~/.config}/systemd/user` — where a `--user` unit lives."""
    if config_dir is not None:
        return Path(config_dir).expanduser()
    override = os.environ.get(UNIT_DIR_ENV, "").strip()
    if override:
        return Path(override).expanduser()
    xdg = os.environ.get("XDG_CONFIG_HOME", "").strip()
    root = Path(xdg).expanduser() if xdg else Path.home() / ".config"
    return root / "systemd" / "user"


def agent_dir(config_dir: str | os.PathLike[str] | None = None) -> Path:
    """`~/Library/LaunchAgents` — where a launchd user agent lives (macOS)."""
    if config_dir is not None:
        return Path(config_dir).expanduser()
    override = os.environ.get(UNIT_DIR_ENV, "").strip()
    if override:
        return Path(override).expanduser()
    return Path.home() / "Library" / "LaunchAgents"


def which_platform(platform: str | None = None) -> str:
    """`systemd` or `launchd`. Injectable so both branches are reachable from one device."""
    if platform is not None:
        return platform
    return LAUNCHD if _platform.system() == "Darwin" else SYSTEMD


def executable_path(executable: str | os.PathLike[str] | None = None) -> str:
    """The absolute `amplifier-memory` a unit's ExecStart names.

    Absolute on purpose: a timer runs with a minimal environment and no shell profile, so
    a bare name resolves against systemd's own PATH and not the steward's. When nothing
    is on PATH the plain name is returned and `install` refuses before writing anything —
    a unit pointing at a command that does not exist is a timer that fails silently every
    day.
    """
    if executable is not None:
        return str(Path(executable).expanduser())
    found = shutil.which("amplifier-memory")
    return found or "amplifier-memory"


def render_service(executable: str) -> str:
    """The oneshot unit. No `[Install]`: only the timer is enabled (Core 1)."""
    return (
        "[Unit]\n"
        "Description=amplifier-memory daily suggestion pass (suggestions.v1)\n"
        "Documentation=https://github.com/bkrabach/amplifier-bundle-memory\n"
        "\n"
        "[Service]\n"
        "Type=oneshot\n"
        f"ExecStart={executable} suggest\n"
    )


def render_timer() -> str:
    """The timer. `Persistent=true` catches up one missed run after the machine was off."""
    return (
        "[Unit]\n"
        "Description=Run the amplifier-memory suggestion pass once a day\n"
        "\n"
        "[Timer]\n"
        f"OnCalendar={ON_CALENDAR}\n"
        "Persistent=true\n"
        "\n"
        "[Install]\n"
        "WantedBy=timers.target\n"
    )


def render_plist(executable: str) -> str:
    """The launchd agent (macOS). Rendered here; its `launchctl` argv is unverified on Linux."""
    return (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" '
        '"http://www.apple.com/DTDs/PropertyList-1.0.dtd">\n'
        '<plist version="1.0">\n'
        "<dict>\n"
        "  <key>Label</key>\n"
        f"  <string>{PLIST_LABEL}</string>\n"
        "  <key>ProgramArguments</key>\n"
        f"  <array>\n    <string>{executable}</string>\n    <string>suggest</string>\n  </array>\n"
        "  <key>StartCalendarInterval</key>\n"
        "  <dict>\n    <key>Hour</key>\n    <integer>9</integer>\n"
        "    <key>Minute</key>\n    <integer>0</integer>\n  </dict>\n"
        "  <key>RunAtLoad</key>\n  <false/>\n"
        "</dict>\n"
        "</plist>\n"
    )


# --------------------------------------------------------------------------- results


@dataclass
class Step:
    """One installation step: what ran, what it said, and whether it failed."""

    name: str
    argv: tuple[str, ...] | None = None
    returncode: int | None = None
    output: str = ""

    @property
    def failed(self) -> bool:
        return (self.returncode or 0) != 0

    def render(self) -> str:
        shown = " ".join(self.argv) if self.argv else self.name
        mark = "FAIL" if self.failed else "ok  "
        line = f"  [{mark}] {shown}"
        body = (self.output or "").strip()
        return "\n".join([line, *(f"         {row}" for row in body.splitlines())])


@dataclass
class ServiceResult:
    """What `install` / `uninstall` / a plain verb did, and what is left on disk."""

    verb: str
    platform: str
    steps: list[Step] = field(default_factory=list)
    written: list[Path] = field(default_factory=list)
    removed: list[Path] = field(default_factory=list)
    rolled_back: bool = False
    note: str = ""

    @property
    def ok(self) -> bool:
        return not any(step.failed for step in self.steps)

    @property
    def exit_code(self) -> int:
        return 0 if self.ok else 1

    def render(self) -> str:
        head = f"amplifier-memory service {self.verb} ({self.platform})"
        lines = [head, "", *(step.render() for step in self.steps)]
        if self.written:
            lines.append(f"  wrote:    {', '.join(str(p) for p in self.written)}")
        if self.removed:
            lines.append(f"  removed:  {', '.join(str(p) for p in self.removed)}")
        if self.rolled_back:
            lines.append(
                "  rolled back: every unit file this run wrote was removed "
                "(cli.v2 Core 6); nothing is enabled"
            )
        if self.note:
            lines.append(f"  note:     {self.note}")
        return "\n".join(lines)


@dataclass
class ServiceStatus:
    """suggestions.v1 Core 8 / cli.v2 Core 5: installed · enabled · last run · last outcome."""

    platform: str
    installed: bool
    enabled: bool | None
    units: list[Path] = field(default_factory=list)
    last_run: str | None = None
    last_status: str | None = None
    detail: str = ""

    def render(self) -> str:
        state = "installed" if self.installed else "not installed"
        enabled = "unknown" if self.enabled is None else ("enabled" if self.enabled else "disabled")
        run = self.last_run or "never"
        outcome = self.last_status or "n/a"
        lines = [
            f"amplifier-memory suggest timer ({self.platform})",
            "",
            f"  installed:    {state}"
            + (f" ({', '.join(str(p) for p in self.units)})" if self.units else ""),
            f"  enabled:      {enabled}",
            f"  last run:     {run}",
            f"  last outcome: {outcome}",
        ]
        if self.detail:
            lines.append(f"  note:         {self.detail}")
        return "\n".join(lines)


def _default_runner(argv: Sequence[str]) -> tuple[int, str]:
    """Run a command, return (exit code, combined output). Never raises on exit code.

    One thing it does raise on: being reached from a test or a conformance probe. On
    2026-09-06 the cli.v2 Core 6 probe invoked `service install` through the CLI with no
    injection, and this function enabled a real daily timer on the steward's device
    (`systemctl --user enable --now`) — the store escaped unharmed only because the
    *installed* CLI was still Phase 1's stub. `tests/conftest.py` already replaces
    `update._default_runner` for the whole suite for exactly this reason; until it does
    the same here, this refusal is the guard, and it fails loud rather than silently
    changing the machine running the checks.
    """
    if os.environ.get("PYTEST_CURRENT_TEST"):
        raise RuntimeError(
            f"refusing to run {' '.join(argv)} from a test: pass an explicit `runner=` "
            f"(and `config_dir=`/${UNIT_DIR_ENV}) so nothing under tests/ changes this device"
        )
    try:
        proc = subprocess.run(list(argv), capture_output=True, text=True, check=False)
    except (OSError, ValueError) as exc:
        return 127, f"{type(exc).__name__}: {exc}"
    return proc.returncode, (proc.stdout + proc.stderr).strip()


# --------------------------------------------------------------------------- verbs


def _targets(platform: str, config_dir: str | os.PathLike[str] | None) -> list[Path]:
    if platform == LAUNCHD:
        return [agent_dir(config_dir) / PLIST_NAME]
    directory = unit_dir(config_dir)
    return [directory / SERVICE_UNIT, directory / TIMER_UNIT]


def _bodies(platform: str, executable: str) -> list[str]:
    if platform == LAUNCHD:
        return [render_plist(executable)]
    return [render_service(executable), render_timer()]


def install(
    *,
    runner: Runner | None = None,
    config_dir: str | os.PathLike[str] | None = None,
    executable: str | os.PathLike[str] | None = None,
    platform: str | None = None,
) -> ServiceResult:
    """cli.v2 Core 6: render the units, reload, enable --now — and roll back on any failure."""
    run = runner or _default_runner
    kind = which_platform(platform)
    exe = executable_path(executable)
    result = ServiceResult(verb="install", platform=kind)

    if not Path(exe).is_absolute():
        result.steps.append(
            Step(
                "locate amplifier-memory",
                None,
                127,
                f"no `amplifier-memory` on PATH (got {exe!r}); a timer runs with a minimal "
                "environment, so the unit needs an absolute path. Remedy: install the CLI "
                "(`uv tool install`) or pass the path explicitly.",
            )
        )
        return result

    targets = _targets(kind, config_dir)
    bodies = _bodies(kind, exe)
    #: Only files THIS call creates are rolled back; an existing unit is left alone.
    fresh = [path for path in targets if not path.exists()]

    try:
        for path, body in zip(targets, bodies, strict=True):
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(body, encoding="utf-8")
        result.written = list(targets)
        result.steps.append(Step(f"write {len(targets)} unit file(s)", None, 0, ""))
    except OSError as exc:
        result.steps.append(Step("write unit file(s)", None, 1, f"{type(exc).__name__}: {exc}"))
        _rollback(result, fresh)
        return result

    for argv in _enable_argv(kind, targets):
        # A step that RAISES is a failed step, not an escape hatch. Before this, an
        # exception out of the runner (the pytest guard below is one) skipped the
        # rollback entirely and left both unit files on disk — a half-install that
        # reported nothing, which is precisely what Core 6 forbids.
        try:
            code, output = run(argv)
        except Exception as exc:  # noqa: BLE001 - reported as the step's own failure
            code, output = 1, f"{type(exc).__name__}: {exc}"
        result.steps.append(Step(argv[0], tuple(argv), code, output))
        if code != 0:
            _rollback(result, fresh)
            return result

    if kind == LAUNCHD:
        result.note = (
            "the launchd branch is rendered on this device but its `launchctl` argv is "
            "not verified here (this bundle's checks run on Linux)"
        )
    return result


def _enable_argv(kind: str, targets: Sequence[Path]) -> list[list[str]]:
    if kind == LAUNCHD:
        plist = str(targets[0])
        return [["launchctl", "unload", "-w", plist], ["launchctl", "load", "-w", plist]]
    return [
        ["systemctl", "--user", "daemon-reload"],
        ["systemctl", "--user", "enable", "--now", TIMER_UNIT],
    ]


def _rollback(result: ServiceResult, fresh: Sequence[Path]) -> None:
    """cli.v2 Core 6: remove every unit file THIS call wrote. Nothing else."""
    for path in fresh:
        try:
            path.unlink(missing_ok=True)
        except OSError:  # pragma: no cover - a unit dir we could write but not unlink
            continue
    result.written = [path for path in result.written if path.exists()]
    result.removed = list(fresh)
    result.rolled_back = True


def uninstall(
    *,
    runner: Runner | None = None,
    config_dir: str | os.PathLike[str] | None = None,
    platform: str | None = None,
) -> ServiceResult:
    """cli.v2 Core 6: disable the timer and remove the units. Leaves nothing behind."""
    run = runner or _default_runner
    kind = which_platform(platform)
    result = ServiceResult(verb="uninstall", platform=kind)
    targets = _targets(kind, config_dir)

    for argv in _disable_argv(kind, targets):
        code, output = run(argv)
        # A unit that was never enabled is not a failure to disable it.
        result.steps.append(Step(argv[0], tuple(argv), 0 if code in (0, 1) else code, output))

    for path in targets:
        if path.exists():
            path.unlink()
            result.removed.append(path)
    result.steps.append(Step(f"remove {len(result.removed)} unit file(s)", None, 0, ""))

    if kind == SYSTEMD:
        code, output = run(["systemctl", "--user", "daemon-reload"])
        result.steps.append(
            Step("systemctl", ("systemctl", "--user", "daemon-reload"), code, output)
        )
    return result


def _disable_argv(kind: str, targets: Sequence[Path]) -> list[list[str]]:
    if kind == LAUNCHD:
        return [["launchctl", "unload", "-w", str(targets[0])]]
    return [["systemctl", "--user", "disable", "--now", TIMER_UNIT]]


def status(
    *,
    runner: Runner | None = None,
    config_dir: str | os.PathLike[str] | None = None,
    platform: str | None = None,
    home: str | os.PathLike[str] | None = None,
) -> ServiceStatus:
    """suggestions.v1 Core 8: installed · enabled · last run · last outcome.

    The last two come from `suggest.log` (Core 9), not from systemd: the log is what the
    job itself wrote, and a timer that fired while the job failed open would otherwise
    read as a healthy run.
    """
    run = runner or _default_runner
    kind = which_platform(platform)
    targets = _targets(kind, config_dir)
    present = [path for path in targets if path.exists()]
    installed = len(present) == len(targets)

    enabled: bool | None = None
    detail = ""
    query = (
        ["systemctl", "--user", "is-enabled", TIMER_UNIT]
        if kind == SYSTEMD
        else ["launchctl", "list", PLIST_LABEL]
    )
    if installed:
        try:
            code, output = run(query)
        except Exception as exc:  # noqa: BLE001 - `doctor` must report, never raise
            # `enabled` stays None, which renders as "unknown" — an honest third state.
            # `doctor` calls this on every run and must not turn a query it could not
            # make into a crashed health check.
            enabled, detail = None, f"could not ask {query[0]}: {type(exc).__name__}: {exc}"
        else:
            enabled = code == 0 and (kind == LAUNCHD or output.strip().startswith("enabled"))
            detail = (
                output.strip()
                if kind == SYSTEMD
                else "launchd branch: `launchctl` argv unverified on this device"
            )

    line = last_log_line(home)
    fields = parse_log_line(line) if line else {}
    return ServiceStatus(
        platform=kind,
        installed=installed,
        enabled=enabled,
        units=present,
        last_run=fields.get("ts"),
        last_status=fields.get("status"),
        detail=detail,
    )


def run_verb(
    verb: str,
    *,
    runner: Runner | None = None,
    config_dir: str | os.PathLike[str] | None = None,
    executable: str | os.PathLike[str] | None = None,
    platform: str | None = None,
    home: str | os.PathLike[str] | None = None,
) -> str:
    """cli.v2 Core 6, as one string — what `amplifier-memory service <verb>` prints."""
    if verb not in VERBS:
        raise ValueError(f"unknown service verb {verb!r}: expected one of {VERBS}")
    if verb == "install":
        return install(
            runner=runner, config_dir=config_dir, executable=executable, platform=platform
        ).render()
    if verb == "uninstall":
        return uninstall(runner=runner, config_dir=config_dir, platform=platform).render()
    if verb == "status":
        return status(runner=runner, config_dir=config_dir, platform=platform, home=home).render()

    kind = which_platform(platform)
    # start / stop / restart / logs act on a unit. When there is none, nothing is run at
    # all: `update` calls `service_status("restart")` on every run (cli.v2 Core 7 step 4),
    # and a verb that shells out on a machine with no timer would make a maintenance
    # command touch units it never installed.
    state = status(runner=runner, config_dir=config_dir, platform=platform, home=home)
    if not state.installed:
        return (
            f"no suggest timer is installed; `service {verb}` did nothing.\n"
            "Remedy: `amplifier-memory service install` installs the daily timer "
            "(suggestions.v1 Core 1)."
        )
    if kind != SYSTEMD:
        return (
            f"`service {verb}` is a systemd verb; on {kind} the timer is a launchd agent \u2014 "
            f"use `launchctl` against {agent_dir(config_dir) / PLIST_NAME}."
        )
    argv = (
        ["journalctl", "--user", "-u", SERVICE_UNIT, "-n", "50", "--no-pager"]
        if verb == "logs"
        else ["systemctl", "--user", verb, TIMER_UNIT]
    )
    code, output = (runner or _default_runner)(argv)
    return Step(argv[0], tuple(argv), code, output).render()


__all__ = [
    "LAUNCHD",
    "ON_CALENDAR",
    "PLIST_LABEL",
    "PLIST_NAME",
    "SERVICE_UNIT",
    "SYSTEMD",
    "TIMER_UNIT",
    "UNIT_BASE",
    "VERBS",
    "Runner",
    "ServiceResult",
    "ServiceStatus",
    "Step",
    "agent_dir",
    "executable_path",
    "install",
    "render_plist",
    "render_service",
    "render_timer",
    "run_verb",
    "status",
    "uninstall",
    "unit_dir",
    "which_platform",
]
