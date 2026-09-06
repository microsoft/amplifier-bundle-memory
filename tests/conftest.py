"""Test isolation: nothing under `tests/` may touch the real store (PINS.md).

The autouse fixture points `AMPLIFIER_MEMORY_HOME` at a temp dir, isolates git's
global/system config so a commit never depends on this device's identity, and
asserts the resolved home is neither the real store nor inside it.

The isolated global config carries a stand-in *human* identity (`HUMAN_IDENTITY`),
because store.v2 Core 9 says a hand commit in the store is the human's: the store
repository holds no identity of its own, so a hand edit resolves the caller's own
git config exactly as it would on a real device. The library's own commits override
it per commit (`store.STORE_IDENTITY`), and a test asserting the two differ is what
proves the attribution.
"""

from __future__ import annotations

import os
from collections.abc import Callable, Iterator
from contextlib import AbstractContextManager, contextmanager
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

import amplifier_memory
import amplifier_memory.update

REAL_STORE = (Path.home() / ".amplifier" / "memory").resolve()

# The stand-in for "this device's human", written into the isolated global git config.
HUMAN_IDENTITY = ("Test Human", "human@example.invalid")


@pytest.fixture(autouse=True)
def memory_home(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    home = tmp_path / "memory"
    gitconfig = tmp_path / "gitconfig"
    gitconfig.write_text(
        f"[user]\n\tname = {HUMAN_IDENTITY[0]}\n\temail = {HUMAN_IDENTITY[1]}\n", encoding="utf-8"
    )
    monkeypatch.setenv("AMPLIFIER_MEMORY_HOME", str(home))
    monkeypatch.setenv("GIT_CONFIG_GLOBAL", str(gitconfig))
    monkeypatch.setenv("GIT_CONFIG_NOSYSTEM", "1")

    resolved = amplifier_memory.store_home()
    assert resolved == home, f"store_home() ignored AMPLIFIER_MEMORY_HOME: {resolved}"
    guarded = resolved.resolve() if resolved.exists() else resolved
    assert guarded != REAL_STORE, "refusing to run tests against the real store"
    assert REAL_STORE not in guarded.parents, "refusing to run tests inside the real store"
    return home


@pytest.fixture(autouse=True)
def no_shelling_out(monkeypatch: pytest.MonkeyPatch) -> list[tuple[str, ...]]:
    """Nothing under `tests/` may change this device — the same rule PINS.md sets for the store.

    `update` (cli.v2 Core 7) really runs `uv tool upgrade` and `amplifier bundle
    remove/add --app`. A test that invokes the verb would upgrade the machine running
    the suite, so the default runner is replaced by a recorder for every test. Ask for
    this fixture by name to assert on the argv that *would* have run; the real argv is
    verified against each CLI's own `--help` in `tests/test_update.py` instead.
    """
    calls: list[tuple[str, ...]] = []

    def recorder(argv):
        calls.append(tuple(argv))
        return 0, f"recorded (not run): {' '.join(argv)}"

    monkeypatch.setattr(amplifier_memory.update, "_default_runner", recorder)
    return calls


@pytest.fixture
def store(memory_home: Path) -> Path:
    """An initialized store at the temp home."""
    amplifier_memory.init()
    return memory_home


@contextmanager
def _at(when: str) -> Iterator[None]:
    """Run the block with git's author and committer clock set to `when` (ISO-8601)."""
    saved = {k: os.environ.get(k) for k in ("GIT_AUTHOR_DATE", "GIT_COMMITTER_DATE")}
    os.environ["GIT_AUTHOR_DATE"] = when
    os.environ["GIT_COMMITTER_DATE"] = when
    try:
        yield
    finally:
        for key, value in saved.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value


@pytest.fixture
def backdate() -> Callable[[float], AbstractContextManager[None]]:
    """`with backdate(days_ago): …` — commits made inside carry a backdated git date.

    `status` reads every number it prints out of git and `usage.jsonl` (cli.v2 Core 2),
    so a fixture that cannot move the clock cannot test it.
    """

    def factory(days_ago: float) -> AbstractContextManager[None]:
        return _at((datetime.now(UTC) - timedelta(days=days_ago)).isoformat())

    return factory


@pytest.fixture
def human_identity() -> tuple[str, str]:
    """The stand-in human this device's isolated git config names."""
    return HUMAN_IDENTITY
