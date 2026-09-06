"""Test isolation: nothing under `tests/` may touch the real store (PINS.md).

The autouse fixture points `AMPLIFIER_MEMORY_HOME` at a temp dir, isolates git's
global/system config so a commit never depends on this device's identity, and
asserts the resolved home is neither the real store nor inside it.
"""

from __future__ import annotations

from pathlib import Path

import pytest

import amplifier_memory

REAL_STORE = (Path.home() / ".amplifier" / "memory").resolve()


@pytest.fixture(autouse=True)
def memory_home(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    home = tmp_path / "memory"
    monkeypatch.setenv("AMPLIFIER_MEMORY_HOME", str(home))
    monkeypatch.setenv("GIT_CONFIG_GLOBAL", str(tmp_path / "gitconfig"))
    monkeypatch.setenv("GIT_CONFIG_NOSYSTEM", "1")

    resolved = amplifier_memory.store_home()
    assert resolved == home, f"store_home() ignored AMPLIFIER_MEMORY_HOME: {resolved}"
    guarded = resolved.resolve() if resolved.exists() else resolved
    assert guarded != REAL_STORE, "refusing to run tests against the real store"
    assert REAL_STORE not in guarded.parents, "refusing to run tests inside the real store"
    return home


@pytest.fixture
def store(memory_home: Path) -> Path:
    """An initialized store at the temp home."""
    amplifier_memory.init()
    return memory_home
