"""Which model each of the job's LLM calls uses — one small table, outside the store.

The job makes exactly one kind of LLM call today: the suggestions.v1 §3 judge, one call
per session in the daily pass. Until now it ran `amplifier run --output-format json` with
no `-p/-m/-B`, so it inherited whatever the amplifier CLI's starred provider happened to
be. On the steward's device that was the most expensive variant measured
(`evaluations/model-class/RESULTS-2026-09-06-pilot.md`: opus, $0.276/call) while a
measured-clean alternative cost $0.02. suggestions.v1 Core 8 asks for cost that is
*bounded and visible*; a knob the user can see is how that becomes true rather than
accidental.

The file
--------
``${AMPLIFIER_MEMORY_CONFIG:-~/.amplifier/memory-config.toml}``::

    [llm.judge]
    provider = "luna"   # an amplifier provider id -> `amplifier run -p`
    model = ""          # optional                -> `-m`
    bundle = ""         # optional                -> `-B`
    role = "fast"       # recorded and logged; resolved only once the host can

**Beside the store, never inside it.** store.v2 §2 fixes the store's layout and says a
file not listed there is not memory; a config file under `~/.amplifier/memory` would
break a locked contract. So it sits one directory up, and `AMPLIFIER_MEMORY_CONFIG`
points at it the way `AMPLIFIER_MEMORY_HOME` points at the store.

`role` is recorded and logged but not resolved: `amplifier run` has no `--model-role`
today (`docs/upstream/amplifier-run-model-role.md` is the ask, with the evidence). When
it grows one, this key is already here and no schema changes.

Whole-file semantics
--------------------
The file is usable in whole or not at all. Any problem — unreadable, not TOML, a value
of the wrong type, a call type or key this version does not know — returns **one honest
reason** and the built-in defaults, and never raises into the job (suggestions.v1 Core
10, fail open). A typo is reported rather than silently ignored, because a user who
writes `[llm.judg]` believes they changed the model and nothing would have.

Standard library only: `tomllib` (Python ≥ 3.11, which `pyproject.toml` already
requires). No `click`, no third-party TOML parser.
"""

from __future__ import annotations

import os
import tomllib
from collections.abc import Mapping
from dataclasses import dataclass, field, replace
from pathlib import Path

#: The environment variable that moves the file, mirroring `AMPLIFIER_MEMORY_HOME`.
CONFIG_ENV = "AMPLIFIER_MEMORY_CONFIG"
#: Its default name, beside the store rather than in it (store.v2 §2).
CONFIG_NAME = "memory-config.toml"

#: The one top-level table. One sub-table per LLM call type.
TABLE = "llm"
#: suggestions.v1 §3's judge — the only LLM call this job makes today.
JUDGE = "judge"
CALL_TYPES: tuple[str, ...] = (JUDGE,)
#: The keys a call table may carry, in the order `flags()` emits them.
KEYS: tuple[str, ...] = ("provider", "model", "bundle", "role")
#: The role recorded when the user names none. Semantic, host-resolved one day.
DEFAULT_ROLE = "fast"


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
    """The whole file, read: where it is, whether it was usable, and each call's choice."""

    path: Path
    #: The file exists (whether or not it turned out to be usable).
    present: bool = False
    #: One sentence when the file is present but unusable; None when all is well.
    reason: str | None = None
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


def config_path(path: str | os.PathLike[str] | None = None) -> Path:
    """`${AMPLIFIER_MEMORY_CONFIG:-~/.amplifier/memory-config.toml}`, or what was passed."""
    if path is not None:
        return Path(path).expanduser()
    env = os.environ.get(CONFIG_ENV, "").strip()
    if env:
        return Path(env).expanduser()
    return Path.home() / ".amplifier" / CONFIG_NAME


def _named_explicitly(path: str | os.PathLike[str] | None) -> bool:
    return path is not None or bool(os.environ.get(CONFIG_ENV, "").strip())


def load(path: str | os.PathLike[str] | None = None) -> LlmConfig:
    """Read the file. Never raises: a problem comes back as `reason`, with defaults.

    It refuses to read *this device's own* config from a test — the same guard, for the
    same reason, as `suggest.default_model_call` and `service._default_runner`: a suite
    whose assertions depend on the steward's real file is not a suite. A test that wants
    a config names one, by argument or by `AMPLIFIER_MEMORY_CONFIG`; with neither, a test
    sees exactly what a device with no file sees, which is the inherit-the-default path.
    """
    resolved = config_path(path)
    absent = LlmConfig(path=resolved)
    if not _named_explicitly(path) and os.environ.get("PYTEST_CURRENT_TEST"):
        return absent

    try:
        raw = resolved.read_bytes()
    except FileNotFoundError:
        return absent
    except OSError as exc:
        return replace(absent, present=True, reason=f"{type(exc).__name__}: {exc}")

    try:
        payload = tomllib.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, tomllib.TOMLDecodeError) as exc:
        return replace(absent, present=True, reason=f"not valid TOML ({exc})")

    calls, reason = _read_calls(payload)
    return LlmConfig(path=resolved, present=True, reason=reason, calls=calls)


def _read_calls(payload: Mapping[str, object]) -> tuple[dict[str, CallConfig], str | None]:
    """`[llm.<call type>]` tables into `CallConfig`s — all of them, or none of them."""
    table = payload.get(TABLE)
    if table is None:
        return _defaults(), None
    if not isinstance(table, dict):
        return _defaults(), f"[{TABLE}] is {type(table).__name__}, expected a table"

    unknown = sorted(name for name in table if name not in CALL_TYPES)
    if unknown:
        return _defaults(), (
            f"unknown call type(s) {', '.join(unknown)} under [{TABLE}]; "
            f"this version has {', '.join(CALL_TYPES)}"
        )

    calls = _defaults()
    for name in CALL_TYPES:
        entry = table.get(name)
        if entry is None:
            continue
        if not isinstance(entry, dict):
            return _defaults(), f"[{TABLE}.{name}] is {type(entry).__name__}, expected a table"
        stray = sorted(key for key in entry if key not in KEYS)
        if stray:
            return _defaults(), (
                f"unknown key(s) {', '.join(stray)} in [{TABLE}.{name}]; expected {', '.join(KEYS)}"
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


#: What the file looks like when a human writes one — printed by docs and by `doctor`'s
#: remedy, so the example and the parser can never drift apart.
EXAMPLE = f"""[{TABLE}.{JUDGE}]
provider = "luna"   # an amplifier provider id -> `amplifier run -p`
model = ""          # optional -> `-m`
bundle = ""         # optional -> `-B`
role = "{DEFAULT_ROLE}"       # recorded and logged; resolved when the host can
"""


__all__ = [
    "CALL_TYPES",
    "CONFIG_ENV",
    "CONFIG_NAME",
    "DEFAULT_ROLE",
    "EXAMPLE",
    "JUDGE",
    "KEYS",
    "TABLE",
    "CallConfig",
    "LlmConfig",
    "config_path",
    "load",
]
