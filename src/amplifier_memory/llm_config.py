"""`config.yaml` — one instance's configuration, inside the instance (store.v3 §2, §11).

Two things live in this file, and both belong to the instance rather than to the
device:

* ``enabled`` (§11) — ``false`` makes the instance **inert**: nothing injects, no
  memory tool is offered, no skills are advertised, no timer runs against it, and
  every writer in this library refuses with one line.
* ``llm:`` (suggestions.v1 §8) — which model each of the job's LLM calls uses. The
  job makes exactly one kind of call today: the suggestions.v1 §3 judge, one call per
  session in the daily pass. Until this knob existed it ran ``amplifier run
  --output-format json`` with no ``-p/-m/-B`` and inherited whatever the amplifier
  CLI's starred provider happened to be — on the steward's device the most expensive
  variant measured (`evaluations/model-class/RESULTS-2026-09-06-pilot.md`: opus,
  $0.276/call) while a measured-clean alternative cost $0.02.

The file
--------
``<instance>/config.yaml``::

    enabled: true       # store.v3 §11 - false makes this instance inert
    llm:
      judge:
        role: fast      # recorded and logged; resolved only once the host can
        provider: ""    # an amplifier provider id -> `amplifier run -p`
        model: ""       # optional                -> `-m`
        bundle: ""      # optional                -> `-B`

**Inside the instance, because the instance is the unit.** store.v3 §1 makes a store
an *instance* — there may be more than one, each its own git repository — and §2 gives
the layout a place for this file. So configuration travels with the instance it
configures: moving the instance moves its config, and two instances on one device
disagree about the judge, or about `enabled`, without either knowing about the other.
There is nothing left for a device-wide config file to configure, and none exists.

`role` is recorded and logged but not resolved: `amplifier run` has no `--model-role`
today (the ask to app-cli is tracked in the upstream workspace, not in this repo). When
it grows one, this key is already here and no schema changes.

Whole-file semantics
--------------------
The file is usable in whole or not at all. Any problem — unreadable, not YAML, a value
of the wrong type, a call type or key this version does not know — returns **one honest
reason** and the built-in defaults, and never raises into the job (suggestions.v1 Core
10, fail open). A typo is reported rather than silently ignored, because a user who
writes ``judg:`` believes they changed the model and nothing would have.

``enabled`` follows the same rule and lands on the safe side of it: an unusable file
leaves the instance **enabled**, because a parse error must never silently switch
memory off. Only a file that says ``enabled: false`` in so many words disables it.
"""

from __future__ import annotations

import os
from collections.abc import Mapping
from dataclasses import dataclass, field, replace
from pathlib import Path

import yaml

#: store.v3 §2's name for this file, inside the instance.
CONFIG_NAME = "config.yaml"

#: store.v3 §11's key, and the value a file that does not mention it is read as.
ENABLED_KEY = "enabled"
DEFAULT_ENABLED = True

#: The one LLM top-level key. One sub-key per LLM call type.
TABLE = "llm"
#: suggestions.v1 §3's judge — the only LLM call this job makes today.
JUDGE = "judge"
CALL_TYPES: tuple[str, ...] = (JUDGE,)
#: The keys a call table may carry, in the order `flags()` emits them.
KEYS: tuple[str, ...] = ("provider", "model", "bundle", "role")
#: The role recorded when the user names none. Semantic, host-resolved one day.
DEFAULT_ROLE = "fast"

#: The keys a `config.yaml` may carry at the top level.
TOP_KEYS: tuple[str, ...] = (ENABLED_KEY, TABLE)


@dataclass(frozen=True)
class CallConfig:
    """One LLM call type's choice: an amplifier provider id, and optionally a model/bundle.

    Empty strings mean "say nothing and inherit the CLI default" — the behaviour the job
    had before this file existed, and still its behaviour with no file present.
    """

    provider: str = ""
    model: str = ""
    bundle: str = ""
    role: str = DEFAULT_ROLE

    @property
    def inherits(self) -> bool:
        """True when this call adds no flag at all, so `amplifier run`'s own default wins."""
        return not (self.provider or self.model or self.bundle)

    def flags(self) -> list[str]:
        """The `amplifier run` flags this choice adds — only the ones actually set.

        `-p/-m/-B` are the CLI's own short forms, verified against `amplifier run --help`
        by `tests/test_suggest.py::test_the_default_argv_matches_amplifier_run_help`,
        which prints the help it relied on (AGENTS.md rule 5).
        """
        out: list[str] = []
        if self.provider:
            out += ["-p", self.provider]
        if self.model:
            out += ["-m", self.model]
        if self.bundle:
            out += ["-B", self.bundle]
        return out

    def render(self) -> str:
        """What `doctor` prints for this choice — the resolved flags, or the inheritance."""
        if self.inherits:
            return "inherits the CLI default"
        named = (
            ("provider", self.provider),
            ("model", self.model),
            ("bundle", self.bundle),
        )
        return " \u00b7 ".join(f"{key} {value}" for key, value in named if value)


def _defaults() -> dict[str, CallConfig]:
    return {name: CallConfig() for name in CALL_TYPES}


@dataclass(frozen=True)
class LlmConfig:
    """The whole file, read: where it is, whether it was usable, and what it says."""

    path: Path
    #: The file exists (whether or not it turned out to be usable).
    present: bool = False
    #: One sentence when the file is present but unusable; None when all is well.
    reason: str | None = None
    #: store.v3 §11. An unusable file leaves the instance enabled — see the module docstring.
    enabled: bool = DEFAULT_ENABLED
    calls: Mapping[str, CallConfig] = field(default_factory=_defaults)

    @property
    def usable(self) -> bool:
        return self.reason is None

    def call(self, name: str = JUDGE) -> CallConfig:
        """One call type's choice; an unconfigured type inherits the CLI default."""
        return self.calls.get(name, CallConfig())

    def source(self) -> str:
        """Where the answer came from, for a human reading `doctor`."""
        if not self.present:
            return f"no {self.path.name} at {self.path}"
        if self.reason:
            return f"{self.path.name} unusable: {self.reason}"
        return f"{self.path.name}"


def config_path(home: str | os.PathLike[str] | None = None) -> Path:
    """The instance's `config.yaml` — `<instance>/config.yaml` (store.v3 §2).

    `home` is the instance: an explicit path, else the store contract's own resolution
    order (`store.store_home`). Passing the file itself is accepted too, so a caller
    holding a path to one config file does not have to strip the name off it first.
    """
    if home is not None:
        path = Path(home).expanduser()
        return path if path.name == CONFIG_NAME else path / CONFIG_NAME
    from .store import store_home  # deferred: `store` reaches this module the same way

    return store_home() / CONFIG_NAME


def default_body(*, enabled: bool = DEFAULT_ENABLED) -> str:
    """What `init` writes into a fresh instance — the shipped defaults, commented.

    The example in the docs and the file `init` writes are this one function, so they
    cannot drift apart; `tests/test_llm_config.py` reads this body back through `load`.
    """
    return (
        f"# This instance's configuration (store.v3 \u00a72). Not memory: never injected,\n"
        f"# never suggested, never cited.\n"
        f"{ENABLED_KEY}: {'true' if enabled else 'false'}"
        f"        # store.v3 \u00a711 - false makes this instance inert\n"
        f"{TABLE}:\n"
        f"  {JUDGE}:                # suggestions.v1 \u00a73's judge, one call per session\n"
        f'    role: "{DEFAULT_ROLE}"        # recorded and logged; resolved when the host can\n'
        f'    provider: ""      # an amplifier provider id -> `amplifier run -p`\n'
        f'    model: ""         # optional -> `-m`\n'
        f'    bundle: ""        # optional -> `-B`\n'
    )


#: What the file looks like when a human writes one — printed by docs and by `doctor`'s
#: remedy, so the example and the parser can never drift apart.
EXAMPLE = default_body()


def _under_pytest_without_an_instance(home: str | os.PathLike[str] | None) -> bool:
    """A test that named no instance must never read this device's own config.

    The same guard, for the same reason, as `suggest.default_model_call` and
    `service._default_runner`: a suite whose assertions depend on the steward's real
    file is not a suite. A test that wants a config names one, by argument or by
    `AMPLIFIER_MEMORY_HOME`; with neither, it sees exactly what a fresh device sees.
    """
    if home is not None or not os.environ.get("PYTEST_CURRENT_TEST"):
        return False
    return not os.environ.get("AMPLIFIER_MEMORY_HOME", "").strip()


def load(home: str | os.PathLike[str] | None = None) -> LlmConfig:
    """Read the instance's `config.yaml`. Never raises: a problem is a `reason` + defaults."""
    resolved = config_path(home)
    absent = LlmConfig(path=resolved)
    if _under_pytest_without_an_instance(home):
        return absent

    try:
        raw = resolved.read_bytes()
    except FileNotFoundError:
        return absent
    except OSError as exc:
        return replace(absent, present=True, reason=f"{type(exc).__name__}: {exc}")

    try:
        payload = yaml.safe_load(raw.decode("utf-8"))
    except (UnicodeDecodeError, yaml.YAMLError) as exc:
        return replace(absent, present=True, reason=f"not valid YAML ({_one_line(exc)})")

    if payload is None:  # an empty file is a file that changes nothing
        return replace(absent, present=True)
    if not isinstance(payload, dict):
        return replace(
            absent,
            present=True,
            reason=f"{CONFIG_NAME} is {type(payload).__name__}, expected a map",
        )

    stray = sorted(key for key in payload if key not in TOP_KEYS)
    if stray:
        return replace(
            absent,
            present=True,
            reason=(
                f"unknown top-level key(s) {', '.join(map(str, stray))}; "
                f"this version has {', '.join(TOP_KEYS)}"
            ),
        )

    enabled = payload.get(ENABLED_KEY, DEFAULT_ENABLED)
    if not isinstance(enabled, bool):
        return replace(
            absent,
            present=True,
            reason=f"{ENABLED_KEY} is {type(enabled).__name__}, expected true or false",
        )

    calls, reason = _read_calls(payload)
    if reason is not None:
        # Whole-file semantics: an unusable file gives up its `enabled` too, and §11's
        # safe side is enabled — a parse error must never silently switch memory off.
        return replace(absent, present=True, reason=reason)
    return LlmConfig(path=resolved, present=True, reason=None, enabled=enabled, calls=calls)


def _one_line(exc: object) -> str:
    """A YAML error is several lines with a caret; a `reason` is one sentence."""
    return " ".join(str(exc).split())


def _read_calls(payload: Mapping[str, object]) -> tuple[dict[str, CallConfig], str | None]:
    """`llm: <call type>:` maps into `CallConfig`s — all of them, or none of them."""
    table = payload.get(TABLE)
    if table is None:
        return _defaults(), None
    if not isinstance(table, dict):
        return _defaults(), f"{TABLE}: is {type(table).__name__}, expected a map"

    unknown = sorted(str(name) for name in table if name not in CALL_TYPES)
    if unknown:
        return _defaults(), (
            f"unknown call type(s) {', '.join(unknown)} under {TABLE}:; "
            f"this version has {', '.join(CALL_TYPES)}"
        )

    calls = _defaults()
    for name in CALL_TYPES:
        entry = table.get(name)
        if entry is None:
            continue
        if not isinstance(entry, dict):
            return _defaults(), f"{TABLE}.{name} is {type(entry).__name__}, expected a map"
        stray = sorted(str(key) for key in entry if key not in KEYS)
        if stray:
            return _defaults(), (
                f"unknown key(s) {', '.join(stray)} in {TABLE}.{name}; expected {', '.join(KEYS)}"
            )
        values: dict[str, str] = {}
        for key in KEYS:
            value = entry.get(key)
            if value is None:
                continue
            if not isinstance(value, str):
                return _defaults(), (
                    f"{TABLE}.{name}.{key} is {type(value).__name__}, expected a string"
                )
            values[key] = value.strip()
        role = values.pop("role", "") or DEFAULT_ROLE
        calls[name] = CallConfig(role=role, **values)
    return calls, None


__all__ = [
    "CALL_TYPES",
    "CONFIG_NAME",
    "DEFAULT_ENABLED",
    "DEFAULT_ROLE",
    "ENABLED_KEY",
    "EXAMPLE",
    "JUDGE",
    "KEYS",
    "TABLE",
    "TOP_KEYS",
    "CallConfig",
    "LlmConfig",
    "config_path",
    "default_body",
    "load",
]
