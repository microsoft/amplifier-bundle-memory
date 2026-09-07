"""`init` — building one instance, end to end (cli.v3 §8).

`store.init` is the *primitive*: it makes the layout, writes `config.yaml`, and makes
the initial commit for a path. This module is the **verb** the clause describes, which
is that primitive plus the three things around it:

1. **the move offer** — when the default instance does not exist and the older
   `~/.amplifier/memory` does, offer to move it and print what was done. Never a silent
   move: a store is the human's memory, and moving it without a word is the kind of
   thing that makes someone stop trusting the tool;
2. **the one seeding question** — `What kinds of things should I remember for you?`,
   with the default answer offered verbatim, saved as `m-001` `writer=human`. The answer
   *is* the quote, because only the human's own words become memory (AGENTS.md rule 7);
   with no TTY it takes the default **and says so**, rather than pretending it asked;
3. **this instance's timer** — `service.install(home=…)`, whose unit name carries the
   instance (cli.v3 §6), so `init` works for any instance rather than only the device
   store, and a kit's temp instance gets its own unit instead of touching the device's.

It lives in the library, not in `cli.py`: cli.v3 §9 says every behaviour a verb exposes
is a public importable function first, and a wrapper that carries logic is a defect. The
two prompts are injectable (`ask=`, `confirm=`) for exactly the same reason — the default
implementations are `input()` behind `is_interactive()`, so no surface needs `click` to
reach this.

This module imports only the standard library and this package: no `click`.
"""

from __future__ import annotations

import os
import shutil
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from pathlib import Path

from . import llm_config, service, store
from .inbox import is_interactive
from .service import ServiceResult

#: cli.v3 §8's one question, and the default answer it offers **verbatim**.
SEED_QUESTION = "What kinds of things should I remember for you?"
SEED_DEFAULT = (
    "Standing preferences and corrections meant to hold beyond one task \u2014 not task "
    "steps, not facts about the code"
)
#: The session id `why m-001` will show. `init` is not a session, and saying so beats
#: minting an id that looks like one.
SEED_SESSION = "amplifier-memory-init"

#: What the move offer asks. The paths are filled in at the call site.
MOVE_QUESTION = "Move it there now?"

#: cli.v3 Core 1's flag. Declared here, with the instance resolution it selects.
HOME_FLAG = "--home"


def split_home(args: Sequence[str]) -> tuple[list[str], str | None]:
    """cli.v3 Core 1: pull `--home X` (or `--home=X`) out of an argument list, anywhere in it.

    The clause declares `--home` once, on the group, so `--help` shows it once — and the
    clause's own examples type it *after* the verb (`service uninstall --home
    <instance>`). Both are the same command, and this is where that is true: the surface
    lifts the flag out of wherever a human put it and hands the rest on unchanged.

    In the library rather than in `cli.py` for the reason Core 9 gives: a behaviour the
    surface exposes is an importable function first, testable with no `click` at all.
    Raises `ValueError` when `--home` carries no value, which the surface renders as its
    own usage error.
    """
    rest: list[str] = []
    home: str | None = None
    want = False
    for arg in args:
        if want:
            home, want = arg, False
        elif arg == HOME_FLAG:
            want = True
        elif arg.startswith(f"{HOME_FLAG}="):
            home = arg.split("=", 1)[1]
        else:
            rest.append(arg)
    if want:
        raise ValueError(f"{HOME_FLAG} needs an instance path")
    return rest, home


#: (question, default answer) -> what the human typed, or the default.
Ask = Callable[[str, str], str]
#: (question) -> yes/no.
Confirm = Callable[[str], bool]


def default_instance() -> Path:
    """store.v3 §1's default *location* — `~/.amplifier-memory`, whether or not it exists.

    Not `store.default_home()`, which answers a different question: that one falls back
    to the older path while the default is absent (which is the migration this module
    offers to end), so it cannot be used to ask "does the default exist yet?".
    """
    return Path.home() / store.DEFAULT_HOME_NAME


def _ask(question: str, default: str) -> str:
    """Ask, offering the default verbatim. No TTY -> the default, and the caller says so."""
    if not is_interactive():
        return default
    print(f"\n{question}")
    print(f"  Enter for: {default}")
    try:
        typed = input("> ").strip()
    except EOFError:  # a pipe that closed mid-prompt is a no-answer, not a crash
        return default
    return typed or default


def _confirm(question: str) -> bool:
    """Offer. No TTY -> no. An unattended run must never move a human's store."""
    if not is_interactive():
        return False
    try:
        return input(f"{question} [y/N] ").strip().lower() in ("y", "yes")
    except EOFError:
        return False


@dataclass
class InstanceReport:
    """What `init` did, in the order cli.v3 §8 says it out loud."""

    home: Path
    existed: bool
    created: list[str] = field(default_factory=list)
    commit: str | None = None

    #: The move offer (§8). `moved_from` is set only when a store actually moved.
    move_offered: bool = False
    moved_from: Path | None = None
    move_note: str = ""

    #: The seeding question (§8). `seed_asked` is False when there was no TTY.
    seed_id: str | None = None
    seed_text: str = ""
    seed_asked: bool = False
    seed_note: str = ""

    #: This instance's timer (§6). `timer` is None when the install plane was not touched.
    timer: ServiceResult | None = None
    timer_installed: bool = False
    timer_note: str = ""
    timer_plane: str = ""
    timer_when: str = ""
    timer_unit: str = ""

    #: suggestions.v2 §8: where the cost of the daily job is steered, for this instance.
    config_path: Path | None = None

    @property
    def uninstall_command(self) -> str:
        """§8's opt-out, naming the instance — `service uninstall` on the wrong one is a trap."""
        return f"amplifier-memory service uninstall --home {self.home}"

    @property
    def untouched(self) -> bool:
        """A plain second run: the store was already there and nothing moved (§8)."""
        return self.existed and self.moved_from is None

    def render(self) -> str:
        lines = list(self._move_lines())
        if self.existed:
            state = "timer installed" if self.timer_installed else "no timer installed"
            lines.append(
                f"store exists \u00b7 {state} \u2014 nothing changed ({self.home})"
                if self.untouched
                else f"store ready \u00b7 {state} ({self.home})"
            )
        else:
            created = ", ".join(self.created)
            lines.append(f"created {self.home}: {created} (commit {(self.commit or '')[:12]})")
        if self.untouched:
            # "asks nothing, and changes nothing" — one line is the whole report.
            return "\n".join(lines)
        lines += self._seed_lines() + self._timer_lines()
        return "\n".join(lines)

    def _move_lines(self) -> list[str]:
        if self.moved_from:
            return [f"moved {self.moved_from} to {self.home} \u2014 the same store, at the default"]
        return [self.move_note] if self.move_note else []

    def _seed_lines(self) -> list[str]:
        if self.seed_note:
            return [self.seed_note]
        if not self.seed_id:
            return []
        how = (
            "your answer"
            if self.seed_asked
            else "the default answer (no TTY to ask, so nothing was minted \u2014 change it any time)"
        )
        return [f"saved {self.seed_id} from {how}: {self.seed_text}"]

    def _timer_lines(self) -> list[str]:
        """The two closing lines §8 names — or one line saying why there are none."""
        if not self.timer_installed:
            return [f"no suggest timer installed: {self.timer_note}"] if self.timer_note else []
        unit = f", unit {self.timer_unit}" if self.timer_unit else ""
        installed = (
            f"installed the daily suggest timer for this instance ({self.timer_plane}, next "
            f"run {self.timer_when}{unit}). Off: {self.uninstall_command}."
        )
        cost = f"which model it uses, and what it costs, is yours to set: {self.config_path}"
        return [installed, cost]


def _offer_move(
    home: str | os.PathLike[str] | None, confirm: Confirm, report: InstanceReport
) -> Path:
    """§8's move offer. Returns the instance path to build at — moved, or left alone."""
    default = default_instance()
    chose_an_instance = home is not None or os.environ.get(store.HOME_ENV, "").strip()
    if chose_an_instance or default.exists() or not store.legacy_store_present():
        return store.store_home(home)

    legacy = store.legacy_home()
    report.move_offered = True
    print(f"\nThere is a memory store at {legacy}. The default is now {default}.")
    if not confirm(MOVE_QUESTION):
        report.move_note = (
            f"left {legacy} where it is (not moved); this instance is {legacy}. "
            f"Move it yourself any time: mv {legacy} {default}"
        )
        return legacy
    try:
        shutil.move(str(legacy), str(default))
    except OSError as exc:
        report.move_note = (
            f"could not move {legacy} to {default} ({type(exc).__name__}: {exc}); "
            f"this instance is {legacy}"
        )
        return legacy
    report.moved_from = legacy
    return default


def _seed(report: InstanceReport, home: Path, ask: Ask) -> None:
    """§8's one question, saved as `m-001` writer=human — the human's own words, or the default."""
    asked = is_interactive()
    answer = ask(SEED_QUESTION, SEED_DEFAULT).strip() or SEED_DEFAULT
    try:
        saved = store.save(
            answer,
            answer,
            "human",
            SEED_SESSION,
            [answer],
            home=home,
        )
    except (store.MemoryError, ValueError) as exc:
        report.seed_note = f"nothing was saved for `{SEED_QUESTION}`: {exc}"
        return
    report.seed_id, report.seed_text, report.seed_asked = saved.id, saved.text, asked


def _install_timer(
    report: InstanceReport,
    home: Path,
    *,
    timer: bool,
    runner: service.Runner | None,
    config_dir: str | os.PathLike[str] | None,
    executable: str | os.PathLike[str] | None,
    platform: str | None,
) -> None:
    """§8: install the daily timer for **this** instance, exactly as `service install` does."""
    report.config_path = llm_config.config_path(home)
    report.timer_unit = service.timer_unit(home)
    if not timer:
        report.timer_note = "--no-timer was given"
        return
    if service.timer_present(config_dir=config_dir, platform=platform, home=home):
        report.timer_installed = True
        report.timer_plane = service.PLANE_NOTE[service.which_platform(platform)]
        report.timer_when = service.RUN_TIME[service.which_platform(platform)]
        return

    outcome = service.install(
        runner=runner,
        config_dir=config_dir,
        executable=executable,
        platform=platform,
        home=home,
    )
    report.timer = outcome
    report.timer_installed = outcome.ok
    report.timer_plane = service.PLANE_NOTE[outcome.platform]
    report.timer_when = service.RUN_TIME[outcome.platform]
    if not outcome.ok:
        report.timer_note = _first_failure(outcome)


def _first_failure(outcome: ServiceResult) -> str:
    """`service install`'s own words for why it refused — never a paraphrase of them."""
    for step in outcome.steps:
        if step.failed:
            return " ".join((step.output or step.name).split())
    return "install reported no failing step"


def build_instance(
    home: str | os.PathLike[str] | None = None,
    *,
    timer: bool = True,
    ask: Ask | None = None,
    confirm: Confirm | None = None,
    runner: service.Runner | None = None,
    config_dir: str | os.PathLike[str] | None = None,
    executable: str | os.PathLike[str] | None = None,
    platform: str | None = None,
) -> InstanceReport:
    """cli.v3 §8: build the instance at the resolved home. This is `amplifier-memory init`.

    Idempotent: a second run reports the store exists and whether this instance's timer
    is installed, asks **nothing**, and changes nothing — no question, no move, no unit.

    `runner`, `config_dir`, `executable` and `platform` are `service.install`'s own
    injection points, passed straight through so a test or a conformance kit exercises
    the install plane without touching this device. `ask` and `confirm` are the two
    prompts, injectable for the same reason.
    """
    report = InstanceReport(home=Path(), existed=False)
    target = _offer_move(home, confirm or _confirm, report)

    outcome = store.init(target, timer=False)
    report.home = outcome.home
    report.existed = outcome.existed
    report.created = outcome.created
    report.commit = outcome.commit

    # A store that has just MOVED is not "a second run": it is a fresh instance path,
    # with no timer of its own yet. A plain second run reaches neither branch below.
    if not outcome.existed:
        _seed(report, outcome.home, ask or _ask)
    if not outcome.existed or report.moved_from:
        _install_timer(
            report,
            outcome.home,
            timer=timer,
            runner=runner,
            config_dir=config_dir,
            executable=executable,
            platform=platform,
        )
    else:
        report.config_path = llm_config.config_path(outcome.home)
        report.timer_unit = service.timer_unit(outcome.home)
        report.timer_installed = service.timer_present(
            config_dir=config_dir, platform=platform, home=outcome.home
        )
    return report


__all__ = [
    "HOME_FLAG",
    "MOVE_QUESTION",
    "SEED_DEFAULT",
    "SEED_QUESTION",
    "SEED_SESSION",
    "Ask",
    "Confirm",
    "InstanceReport",
    "build_instance",
    "default_instance",
    "split_home",
]
