"""The suggest timer — suggestions.v1 Core 1, cli.v3 Core 6.

"A timer, not a service." `amplifier-memory suggest` runs once a day, does its work,
and exits. Nothing is resident: the systemd unit is `Type=oneshot` and carries no
`[Install]` section of its own — only the **timer** is enabled, so nothing starts the
job except the clock (and `Persistent=true`, which catches up one missed run after the
machine was off).

**One timer per instance (cli.v3 §6).** A store is an instance (store.v3 §1), and every
verb here acts on the instance `home` names. The unit name is derived from that
instance's path (`instance_tag`) and its `ExecStart` carries `suggest --home
<instance>`, so two instances never collide and neither can silently uninstall or
re-point the other's timer. `status` lists **every** installed instance timer it can
find in the unit directory, not only the resolved one.

`home=None` is the one exception, and it is a compatibility shim, not a default: it
renders the un-instanced device-wide name this module shipped before v3
(`amplifier-memory-suggest.service`/`.timer`), which is the unit already installed on
any device that ran cli.v2's `service install`. Every v3 surface — the CLI, `doctor`,
`init`, `update` — resolves the instance first and passes it, so the name always
carries the instance.

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

import hashlib
import os
import platform as _platform
import re
import shutil
import subprocess
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from pathlib import Path

from .suggest import last_log_line, parse_log_line

#: What a step runner returns: an exit code and whatever the command said.
Runner = Callable[[Sequence[str]], "tuple[int, str]"]

UNIT_BASE = "amplifier-memory-suggest"
#: The un-instanced names — the unit a pre-v3 `service install` wrote on this device.
#: `service_unit(None)` / `timer_unit(None)` still render these, so an already-installed
#: device timer stays addressable (and visible in `status`) rather than orphaned.
SERVICE_UNIT = f"{UNIT_BASE}.service"
TIMER_UNIT = f"{UNIT_BASE}.timer"
PLIST_LABEL = "com.amplifier-memory.suggest"
PLIST_NAME = f"{PLIST_LABEL}.plist"

#: Every timer this module can have written, instanced or not — what `status` scans for.
UNIT_GLOB = f"{UNIT_BASE}*.timer"
PLIST_GLOB = f"{PLIST_LABEL}*.plist"

_SLUG = re.compile(r"[^a-z0-9]+")
#: How much of the instance's own directory name survives into the unit name. The digest
#: below is what makes the name unique; this part is only so a human reading
#: `systemctl --user list-timers` can tell which store a timer belongs to.
TAG_SLUG_CHARS = 24
TAG_DIGEST_CHARS = 8

SYSTEMD = "systemd"
LAUNCHD = "launchd"

#: cli.v2 Core 1's `service` verbs. `install`/`uninstall`/`status` are the clause's
#: substance; the other four are one `systemctl` call each on the same timer.
VERBS = ("install", "uninstall", "start", "stop", "restart", "status", "logs")

#: suggestions.v1 Core 1: once a day, catching up one missed run after the machine was off.
ON_CALENDAR = "daily"

#: What the two planes are called, and when each one fires, in the words `init` prints
#: back to a human (cli.v2 Core 8's "what it installed"). `OnCalendar=daily` is midnight;
#: the launchd agent's `StartCalendarInterval` above says 09:00. Read from here rather
#: than retyped at the call site, so a schedule change moves the sentence with it.
PLANE_NOTE = {SYSTEMD: "systemd --user", LAUNCHD: "launchd agent"}
RUN_TIME = {SYSTEMD: "00:00", LAUNCHD: "09:00"}


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


def instance_path(home: str | os.PathLike[str] | None = None) -> Path:
    """The absolute instance path a unit name is derived from (store.v3 §1's resolution).

    Absolute but **not** `resolve()`d: an instance that does not exist yet has no real
    path to resolve, and `init` names its unit before creating the store. Two names for
    one instance would be worse than a long one.
    """
    from .store import store_home  # deferred: `store` reaches this module the same way

    return Path(os.path.abspath(str(store_home(home))))


def instance_tag(home: str | os.PathLike[str] | None = None) -> str:
    """cli.v3 §6: the instance's own part of a unit name — readable, and unique.

    `~/.amplifier-memory` -> `amplifier-memory-<8 hex>`. The slug is for the human
    reading `systemctl --user list-timers`; the digest of the absolute path is what
    guarantees two instances never collide (two stores may share a directory *name*).
    """
    path = instance_path(home)
    slug = _SLUG.sub("-", path.name.lower()).strip("-")[:TAG_SLUG_CHARS] or "instance"
    digest = hashlib.sha256(str(path).encode("utf-8")).hexdigest()[:TAG_DIGEST_CHARS]
    return f"{slug}-{digest}"


def unit_stem(home: str | os.PathLike[str] | None = None) -> str:
    """`amplifier-memory-suggest-<instance tag>`, or the bare base when `home` is None."""
    return UNIT_BASE if home is None else f"{UNIT_BASE}-{instance_tag(home)}"


def service_unit(home: str | os.PathLike[str] | None = None) -> str:
    return f"{unit_stem(home)}.service"


def timer_unit(home: str | os.PathLike[str] | None = None) -> str:
    return f"{unit_stem(home)}.timer"


def plist_label(home: str | os.PathLike[str] | None = None) -> str:
    return PLIST_LABEL if home is None else f"{PLIST_LABEL}.{instance_tag(home)}"


def plist_name(home: str | os.PathLike[str] | None = None) -> str:
    return f"{plist_label(home)}.plist"


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


def _suggest_argv(home: str | os.PathLike[str] | None) -> list[str]:
    """What the unit runs: `suggest`, and — cli.v3 §6 — the instance it runs it for.

    Without `--home`, two instances' timers would run the same command and both would
    act on whatever `$AMPLIFIER_MEMORY_HOME` resolved to inside systemd's own minimal
    environment (which carries neither the steward's exports nor their shell profile).
    """
    return ["suggest"] if home is None else ["suggest", "--home", str(instance_path(home))]


def render_service(executable: str, home: str | os.PathLike[str] | None = None) -> str:
    """The oneshot unit. No `[Install]`: only the timer is enabled (Core 1)."""
    argv = " ".join(_suggest_argv(home))
    named = "" if home is None else f" for {instance_path(home)}"
    return (
        "[Unit]\n"
        f"Description=amplifier-memory daily suggestion pass (suggestions.v1){named}\n"
        "Documentation=https://github.com/microsoft/amplifier-bundle-memory\n"
        "\n"
        "[Service]\n"
        "Type=oneshot\n"
        f"ExecStart={executable} {argv}\n"
    )


def render_timer(home: str | os.PathLike[str] | None = None) -> str:
    """The timer. `Persistent=true` catches up one missed run after the machine was off."""
    named = "" if home is None else f" for {instance_path(home)}"
    return (
        "[Unit]\n"
        f"Description=Run the amplifier-memory suggestion pass once a day{named}\n"
        "\n"
        "[Timer]\n"
        f"OnCalendar={ON_CALENDAR}\n"
        "Persistent=true\n"
        "\n"
        "[Install]\n"
        "WantedBy=timers.target\n"
    )


def render_plist(executable: str, home: str | os.PathLike[str] | None = None) -> str:
    """The launchd agent (macOS). Rendered here; its `launchctl` argv is unverified on Linux."""
    args = "".join(f"    <string>{arg}</string>\n" for arg in _suggest_argv(home))
    return (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" '
        '"http://www.apple.com/DTDs/PropertyList-1.0.dtd">\n'
        '<plist version="1.0">\n'
        "<dict>\n"
        "  <key>Label</key>\n"
        f"  <string>{plist_label(home)}</string>\n"
        "  <key>ProgramArguments</key>\n"
        f"  <array>\n    <string>{executable}</string>\n{args}  </array>\n"
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
    #: cli.v3 §6: which instance this acted on, printed so two instances are never
    #: confused in a transcript. Empty for the un-instanced (pre-v3) unit.
    instance: str = ""

    @property
    def ok(self) -> bool:
        return not any(step.failed for step in self.steps)

    @property
    def exit_code(self) -> int:
        return 0 if self.ok else 1

    def render(self) -> str:
        head = f"amplifier-memory service {self.verb} ({self.platform})"
        lines = [head, *([f"  instance: {self.instance}"] if self.instance else []), ""]
        lines += [step.render() for step in self.steps]
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
    #: cli.v3 §6: the resolved instance these numbers are about.
    instance: str = ""
    #: cli.v3 §6: "status lists every installed instance timer, not only the resolved
    #: one" — so a second instance's timer is never invisible to the person reading this.
    others: list[InstalledTimer] = field(default_factory=list)

    @property
    def unit_name(self) -> str:
        """The unit answering for this instance, read off `units` — never a rendered guess.

        `units` holds only files that exist, so anything printed from here is on disk at
        the moment it is printed. `doctor`'s row names the unit from this.
        """
        return self.units[-1].name if self.units else ""

    def render(self) -> str:
        state = "installed" if self.installed else "not installed"
        enabled = "unknown" if self.enabled is None else ("enabled" if self.enabled else "disabled")
        run = self.last_run or "never"
        outcome = self.last_status or "n/a"
        lines = [
            f"amplifier-memory suggest timer ({self.platform})",
            "",
            *([f"  instance:     {self.instance}"] if self.instance else []),
            f"  installed:    {state}"
            + (f" ({', '.join(str(p) for p in self.units)})" if self.units else ""),
            f"  enabled:      {enabled}",
            f"  last run:     {run}",
            f"  last outcome: {outcome}",
        ]
        if self.detail:
            lines.append(f"  note:         {self.detail}")
        lines.append(f"  all timers:   {len(self.others)} installed on this device")
        lines += [f"    {timer.render()}" for timer in self.others]
        return "\n".join(lines)


def redirect_reason() -> str | None:
    """Why a real `systemctl`/`launchctl` call is refused right now, or None.

    Two signals, one rule: **the install plane is redirected, so a real command would
    act on this device rather than on what was just written.**

    * `PYTEST_CURRENT_TEST` — a test. `tests/conftest.py` replaces this module's runner
      for the whole suite; this is the backstop for anything that slips past it.
    * `$AMPLIFIER_MEMORY_UNIT_DIR` — units are being written somewhere systemd does not
      read, so `systemctl --user enable --now <unit>` cannot enable *that* unit. It
      resolves the name against `~/.config/systemd/user` instead, which is how a
      conformance probe re-enabled the steward's own daily timer on 2026-09-06 while
      believing every unit it touched was in `/tmp` (work item `…-azy`). Refusing is
      not caution: an enable that can only hit the wrong unit has no correct outcome.

    Public so a check can assert the guard is armed without patching anything —
    `conformance/cli/run.py` does exactly that.
    """
    if os.environ.get("PYTEST_CURRENT_TEST"):
        return "a test is running (PYTEST_CURRENT_TEST is set)"
    override = os.environ.get(UNIT_DIR_ENV, "").strip()
    if override:
        return f"${UNIT_DIR_ENV} redirects unit files to {override}"
    return None


def _default_runner(argv: Sequence[str]) -> tuple[int, str]:
    """Run a command, return (exit code, combined output). Never raises on exit code.

    One thing it does raise on: being reached while the install plane is redirected
    (`redirect_reason`). On 2026-09-06 the cli.v2 Core 6 probe invoked `service install`
    through the CLI with no injection, and this function enabled a real daily timer on
    the steward's device (`systemctl --user enable --now`) — the store escaped unharmed
    only because the *installed* CLI was still Phase 1's stub. It happened a second way
    on 2026-09-07 (`…-azy`): the unit directory was redirected but the runner was not,
    so `enable --now` resolved the unit *name* against the real one. This refusal fails
    loud rather than silently changing the machine running the checks.
    """
    redirected = redirect_reason()
    if redirected:
        raise RuntimeError(
            f"refusing to run {' '.join(argv)}: {redirected}, so this command would act "
            "on this device's own units, not on the ones just written. Pass an explicit "
            "`runner=` (with `config_dir=`) to exercise the install plane."
        )
    try:
        proc = subprocess.run(list(argv), capture_output=True, text=True, check=False)
    except (OSError, ValueError) as exc:
        return 127, f"{type(exc).__name__}: {exc}"
    return proc.returncode, (proc.stdout + proc.stderr).strip()


# --------------------------------------------------------------------------- verbs


def _named(home: str | os.PathLike[str] | None) -> str:
    """The instance path a result prints, or `""` for the un-instanced (pre-v3) unit."""
    return "" if home is None else str(instance_path(home))


def _targets(
    platform: str,
    config_dir: str | os.PathLike[str] | None,
    home: str | os.PathLike[str] | None = None,
) -> list[Path]:
    if platform == LAUNCHD:
        return [agent_dir(config_dir) / plist_name(home)]
    directory = unit_dir(config_dir)
    return [directory / service_unit(home), directory / timer_unit(home)]


def _bodies(platform: str, executable: str, home: str | os.PathLike[str] | None) -> list[str]:
    if platform == LAUNCHD:
        return [render_plist(executable, home)]
    return [render_service(executable, home), render_timer(home)]


@dataclass(frozen=True)
class InstalledTimer:
    """One timer found on disk: which instance it serves, and the unit that serves it."""

    unit: Path
    #: The instance from the paired unit's `ExecStart … --home <instance>`; None for a
    #: unit that names none (the pre-v3 device-wide timer, or one written by hand).
    instance: Path | None
    resolved: bool = False

    def render(self) -> str:
        where = str(self.instance) if self.instance else "pre-v3, serves the default only"
        mark = " <- this one" if self.resolved else ""
        return f"{self.unit.name}  {where}{mark}"


def _instance_of(timer: Path) -> Path | None:
    """Read `--home <instance>` back out of the timer's paired unit. Never raises."""
    paired = timer.with_suffix(".service") if timer.suffix == ".timer" else timer
    try:
        body = paired.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return None
    for line in body.splitlines():
        if line.startswith("ExecStart=") and " --home " in line:
            return Path(line.split(" --home ", 1)[1].strip())
    return None


def installed_timers(
    *,
    config_dir: str | os.PathLike[str] | None = None,
    platform: str | None = None,
    home: str | os.PathLike[str] | None = None,
) -> list[InstalledTimer]:
    """cli.v3 §6: every installed instance timer, not only the resolved one.

    Filesystem only — a listing must not depend on `systemctl` answering. `home` marks
    which of them is the resolved instance's, so `status` can say "this one" rather than
    leaving a human to match hashes by eye.
    """
    kind = which_platform(platform)
    directory = agent_dir(config_dir) if kind == LAUNCHD else unit_dir(config_dir)
    mine = _targets(kind, config_dir, home)[-1]
    try:
        found = sorted(directory.glob(PLIST_GLOB if kind == LAUNCHD else UNIT_GLOB))
    except OSError:  # pragma: no cover - an unreadable unit dir is reported as "none"
        return []
    return [
        InstalledTimer(unit=path, instance=_instance_of(path), resolved=path == mine)
        for path in found
    ]


def serves_default(home: str | os.PathLike[str] | None) -> bool:
    """Would the un-instanced (pre-v3) unit serve this instance?

    That unit's `ExecStart` is a bare `amplifier-memory suggest`, so at fire time it acts
    on whatever store.v3 §1 resolves to — which is this instance exactly when `home` *is*
    the resolved one. On any other instance it is somebody else's timer, and saying
    "installed" for it would be a lie with a bill attached.

    Public because it is also the predicate for the migration below: the pre-v3 pair is
    replaced only for the instance it actually serves, and left strictly alone otherwise.
    """
    return home is not None and instance_path(home) == instance_path(None)


def effective_targets(
    kind: str,
    config_dir: str | os.PathLike[str] | None,
    home: str | os.PathLike[str] | None,
) -> tuple[list[Path], str | os.PathLike[str] | None, bool]:
    """The units that actually serve this instance: its own, or the pre-v3 device one.

    Returns `(targets, unit_home, is_legacy)`. A device that ran cli.v2's `service
    install` has `amplifier-memory-suggest.timer` and no instanced unit; that timer does
    run this instance's pass while this instance is the resolved one, so reporting "not
    installed" — and inviting a second, duplicate timer — would be worse than saying
    plainly which unit was found.
    """
    own = _targets(kind, config_dir, home)
    if all(path.exists() for path in own) or not serves_default(home):
        return own, home, False
    legacy = _targets(kind, config_dir, None)
    if all(path.exists() for path in legacy):
        return legacy, None, True
    return own, home, False


def timer_present(
    *,
    config_dir: str | os.PathLike[str] | None = None,
    platform: str | None = None,
    home: str | os.PathLike[str] | None = None,
) -> bool:
    """Is a timer that serves this instance on disk right now? Filesystem only.

    `status()` answers the same question and more, but it asks `systemctl is-enabled` to
    do it. `init` (cli.v3 §8) has to be able to say "timer installed" on a second run
    while changing nothing and *running* nothing, so the cheap half is its own function.
    """
    targets, _, _ = effective_targets(which_platform(platform), config_dir, home)
    return all(path.exists() for path in targets)


def serving_unit(
    *,
    config_dir: str | os.PathLike[str] | None = None,
    platform: str | None = None,
    home: str | os.PathLike[str] | None = None,
) -> str:
    """The name of the unit that serves this instance **right now**, read off disk.

    `""` when none does. This is the only sanctioned source for a unit name a surface
    prints: on 2026-09-07 `init` composed its success line from `timer_unit(home)` while
    `timer_present()` had answered "installed" about the *pre-v3* pair, and named a unit
    `systemctl --user status` could not find. A name that came off the filesystem cannot
    tell that lie.
    """
    targets, _, _ = effective_targets(which_platform(platform), config_dir, home)
    return targets[-1].name if all(path.exists() for path in targets) else ""


#: What any surface says when the pre-v3 device-wide pair is what serves this instance.
#: Composed once, here, so `status`, `doctor` and a second `init` cannot describe the same
#: device three different ways (AGENTS.md rule 9). The remedy is `service install`, not
#: `init`: cli.v3 §8 says a second `init` changes nothing, so it reports and stops.
LEGACY_SERVING = (
    "{unit} is the pre-v3 device-wide unit and has no --home; it serves this instance "
    "only while it is the resolved one. Remedy: `amplifier-memory service install "
    "--home {home}` replaces it with this instance's own"
)


def legacy_serving(
    *,
    config_dir: str | os.PathLike[str] | None = None,
    platform: str | None = None,
    home: str | os.PathLike[str] | None = None,
) -> bool:
    """Is the pre-v3 device-wide pair what serves this instance right now?"""
    _, _, legacy = effective_targets(which_platform(platform), config_dir, home)
    return legacy


def own_timer_present(
    *,
    config_dir: str | os.PathLike[str] | None = None,
    platform: str | None = None,
    home: str | os.PathLike[str] | None = None,
) -> bool:
    """Are **this instance's own** units on disk? The pre-v3 pair does not count.

    `timer_present` deliberately does count it (a device-wide timer really does run this
    instance's pass while this instance is the resolved default), which is the right
    answer for "is anything serving me" and the wrong one for "may I skip installing":
    skipping is what left the device with one pre-v3 timer and a printed name for a unit
    that was never written. `install` is what closes that gap, by migrating.
    """
    return all(path.exists() for path in _targets(which_platform(platform), config_dir, home))


def install(
    *,
    runner: Runner | None = None,
    config_dir: str | os.PathLike[str] | None = None,
    executable: str | os.PathLike[str] | None = None,
    platform: str | None = None,
    home: str | os.PathLike[str] | None = None,
) -> ServiceResult:
    """cli.v3 §6: render this instance's units, reload, enable --now — roll back on failure."""
    run = runner or _default_runner
    kind = which_platform(platform)
    exe = executable_path(executable)
    result = ServiceResult(verb="install", platform=kind, instance=_named(home))

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

    targets = _targets(kind, config_dir, home)
    bodies = _bodies(kind, exe, home)
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

    for argv in _enable_argv(kind, targets, home):
        # A step that RAISES is a failed step, not an escape hatch (`_step`). Before
        # this, an exception out of the runner (the pytest guard below is one) skipped
        # the rollback entirely and left both unit files on disk — a half-install that
        # reported nothing, which is precisely what Core 6 forbids.
        code, output = _step(run, argv)
        result.steps.append(Step(argv[0], tuple(argv), code, output))
        if code != 0:
            _rollback(result, fresh)
            return result

    _migrate_device_wide(result, kind, config_dir, home, run)

    if kind == LAUNCHD:
        _add_note(
            result,
            "the launchd branch is rendered on this device but its `launchctl` argv is "
            "not verified here (this bundle's checks run on Linux)",
        )
    return result


#: cli.v3 §6, said out loud. The pre-v3 pair carries no `--home`, so beside a new
#: instanced timer it would fire the *same* pass a second time every day — which is why
#: `install` ends it rather than reporting "already installed" and writing nothing.
MIGRATED = "replaced the device-wide timer with this instance's: {unit}"
#: The other instance: the pre-v3 unit is somebody else's, and removing it would silently
#: stop the daily pass for whatever instance IS the resolved default.
LEFT_ALONE = (
    "{unit} is the pre-v3 device-wide timer and names no instance; it does not serve "
    "this instance ({home}), so it was left alone"
)
#: A disable that genuinely failed leaves TWO timers on one instance. Said loudly, with
#: the one command that ends it — a silent double timer is the failure being prevented.
MIGRATION_FAILED = (
    "could not disable {unit} ({said}); it and {mine} now BOTH serve {home}. "
    "Remedy: `systemctl --user disable --now {unit}`"
)


def _add_note(result: ServiceResult, note: str) -> None:
    """Append a note without dropping one already there."""
    result.note = " \u00b7 ".join(part for part in (result.note, note) if part)


def _step(run: Runner, argv: Sequence[str]) -> tuple[int, str]:
    """Run one step; a runner that RAISES is a failed step, never an escape hatch."""
    try:
        return run(argv)
    except Exception as exc:  # noqa: BLE001 - reported as the step's own failure
        return 1, f"{type(exc).__name__}: {exc}"


def _migrate_device_wide(
    result: ServiceResult,
    kind: str,
    config_dir: str | os.PathLike[str] | None,
    home: str | os.PathLike[str] | None,
    run: Runner,
) -> None:
    """cli.v3 §6: end the pre-v3 device-wide timer for the instance it actually served.

    Runs after this instance's own units are written and enabled, so the migration can
    only ever *reduce* the number of timers serving the instance — never leave it with
    none. Everything goes through the injected runner, so a kit or a test exercises this
    path without touching the device.
    """
    legacy = _targets(kind, config_dir, None)
    if not any(path.exists() for path in legacy):
        return
    old = legacy[-1].name
    if not serves_default(home):
        _add_note(result, LEFT_ALONE.format(unit=old, home=_named(home)))
        return

    argv = _disable_argv(kind, legacy, None)[0]
    code, output = _step(run, argv)
    # A unit that was never enabled is not a failure to disable it (as `uninstall` reads it).
    result.steps.append(Step(argv[0], tuple(argv), 0 if code in (0, 1) else code, output))
    if code not in (0, 1):
        mine = _targets(kind, config_dir, home)[-1].name
        _add_note(
            result,
            MIGRATION_FAILED.format(
                unit=old,
                said=" ".join(output.split()) or f"exit {code}",
                mine=mine,
                home=_named(home),
            ),
        )
        return

    for path in legacy:
        try:
            if path.exists():
                path.unlink()
                result.removed.append(path)
        except OSError as exc:  # pragma: no cover - a unit dir we could read but not unlink
            result.steps.append(Step(f"remove {path}", None, 1, f"{type(exc).__name__}: {exc}"))
            return
    if kind == SYSTEMD:
        reload_argv = ("systemctl", "--user", "daemon-reload")
        code, output = _step(run, reload_argv)
        result.steps.append(Step("systemctl", reload_argv, code, output))
    _add_note(result, MIGRATED.format(unit=_targets(kind, config_dir, home)[-1].name))


def _enable_argv(
    kind: str, targets: Sequence[Path], home: str | os.PathLike[str] | None = None
) -> list[list[str]]:
    if kind == LAUNCHD:
        plist = str(targets[0])
        return [["launchctl", "unload", "-w", plist], ["launchctl", "load", "-w", plist]]
    return [
        ["systemctl", "--user", "daemon-reload"],
        ["systemctl", "--user", "enable", "--now", timer_unit(home)],
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
    home: str | os.PathLike[str] | None = None,
) -> ServiceResult:
    """cli.v3 §6: disable **this instance's** timer and remove its units, nothing else.

    The unit names carry the instance, so an `uninstall` for one instance cannot reach
    another's timer even by accident — the clause's "neither can silently uninstall the
    other's timer", enforced by the naming rather than by a check that could be skipped.
    """
    run = runner or _default_runner
    kind = which_platform(platform)
    result = ServiceResult(verb="uninstall", platform=kind, instance=_named(home))
    targets = _targets(kind, config_dir, home)

    for argv in _disable_argv(kind, targets, home):
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


def _disable_argv(
    kind: str, targets: Sequence[Path], home: str | os.PathLike[str] | None = None
) -> list[list[str]]:
    if kind == LAUNCHD:
        return [["launchctl", "unload", "-w", str(targets[0])]]
    return [["systemctl", "--user", "disable", "--now", timer_unit(home)]]


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
    targets, unit_home, legacy = effective_targets(kind, config_dir, home)
    present = [path for path in targets if path.exists()]
    installed = len(present) == len(targets)

    enabled: bool | None = None
    detail = LEGACY_SERVING.format(unit=targets[-1].name, home=_named(home)) if legacy else ""
    query = (
        ["systemctl", "--user", "is-enabled", timer_unit(unit_home)]
        if kind == SYSTEMD
        else ["launchctl", "list", plist_label(unit_home)]
    )
    if installed:
        try:
            code, output = run(query)
        except Exception as exc:  # noqa: BLE001 - `doctor` must report, never raise
            # `enabled` stays None, which renders as "unknown" — an honest third state.
            # `doctor` calls this on every run and must not turn a query it could not
            # make into a crashed health check.
            enabled, said = None, f"could not ask {query[0]}: {type(exc).__name__}: {exc}"
        else:
            enabled = code == 0 and (kind == LAUNCHD or output.strip().startswith("enabled"))
            said = (
                output.strip()
                if kind == SYSTEMD
                else "launchd branch: `launchctl` argv unverified on this device"
            )
        detail = " \u00b7 ".join(part for part in (said, detail) if part)

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
        instance=_named(home),
        others=installed_timers(config_dir=config_dir, platform=platform, home=home),
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
    """cli.v3 §6, as one string — what `amplifier-memory service <verb> --home X` prints."""
    if verb not in VERBS:
        raise ValueError(f"unknown service verb {verb!r}: expected one of {VERBS}")
    if verb == "install":
        return install(
            runner=runner,
            config_dir=config_dir,
            executable=executable,
            platform=platform,
            home=home,
        ).render()
    if verb == "uninstall":
        return uninstall(
            runner=runner, config_dir=config_dir, platform=platform, home=home
        ).render()
    if verb == "status":
        return status(runner=runner, config_dir=config_dir, platform=platform, home=home).render()

    kind = which_platform(platform)
    # start / stop / restart / logs act on a unit. When there is none, nothing is run at
    # all: `update` calls `service_status("restart")` on every run (cli.v2 Core 7 step 4),
    # and a verb that shells out on a machine with no timer would make a maintenance
    # command touch units it never installed.
    state = status(runner=runner, config_dir=config_dir, platform=platform, home=home)
    if not state.installed:
        where = f" --home {_named(home)}" if home is not None else ""
        return (
            f"no suggest timer is installed for {_named(home) or 'this device'}; "
            f"`service {verb}` did nothing.\n"
            f"Remedy: `amplifier-memory service install{where}` installs the daily timer "
            "(suggestions.v1 Core 1)."
        )
    if kind != SYSTEMD:
        return (
            f"`service {verb}` is a systemd verb; on {kind} the timer is a launchd agent \u2014 "
            f"use `launchctl` against {agent_dir(config_dir) / plist_name(home)}."
        )
    argv = (
        ["journalctl", "--user", "-u", service_unit(home), "-n", "50", "--no-pager"]
        if verb == "logs"
        else ["systemctl", "--user", verb, timer_unit(home)]
    )
    code, output = (runner or _default_runner)(argv)
    return Step(argv[0], tuple(argv), code, output).render()


__all__ = [
    "LAUNCHD",
    "LEFT_ALONE",
    "LEGACY_SERVING",
    "MIGRATED",
    "MIGRATION_FAILED",
    "ON_CALENDAR",
    "PLANE_NOTE",
    "PLIST_LABEL",
    "PLIST_NAME",
    "RUN_TIME",
    "SERVICE_UNIT",
    "SYSTEMD",
    "TIMER_UNIT",
    "UNIT_BASE",
    "VERBS",
    "InstalledTimer",
    "Runner",
    "ServiceResult",
    "ServiceStatus",
    "Step",
    "agent_dir",
    "effective_targets",
    "executable_path",
    "install",
    "installed_timers",
    "instance_path",
    "instance_tag",
    "legacy_serving",
    "own_timer_present",
    "plist_label",
    "plist_name",
    "redirect_reason",
    "render_plist",
    "render_service",
    "render_timer",
    "run_verb",
    "serves_default",
    "service_unit",
    "serving_unit",
    "status",
    "timer_present",
    "timer_unit",
    "uninstall",
    "unit_dir",
    "unit_stem",
    "which_platform",
]
