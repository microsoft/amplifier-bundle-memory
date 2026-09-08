"""`update` — cli.v2 Core 7. Every step's argv verified, every step's run injected.

Three kinds of test here, and they are deliberately different:

- **AGENTS.md rule 5** — the argv `update` shells out to is asked of that CLI's own
  `--help`, and the help is printed. `amplifier run --once` shipped without existing;
  this is the check that would have caught it. These tests need the CLI on PATH and
  skip (never silently pass) when it is absent.
- **Behaviour** — `run_update` is exercised with an injected runner, so no network
  call, no upgrade, and no change to this device happens in the suite.
- **The fake device** — a temp `~/.amplifier` whose cache clones point at a temp
  "remote" on local disk, plus a temp venv carrying a `direct_url.json`. The git half
  of the refresh really runs there (a local origin needs no network), so these tests
  prove the clone *moved*, not merely that an argv was composed. Nothing under
  `tests/` ever touches this device's real cache, venv or store.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
from collections.abc import Sequence
from pathlib import Path

import pytest

import amplifier_memory
from amplifier_memory.doctor import (
    DoctorReport,
    DoctorRow,
    amplifier_env_python,
    bundle_cache_dirs,
    cache_dir_name,
    commit_of_cache,
    commit_of_env_library,
    installed_commits,
)

# Bound at import time, before conftest's autouse `no_shelling_out` fixture replaces the
# module attribute — this is the one test that must exercise the REAL runner.
from amplifier_memory.update import _default_runner as _real_default_runner
from amplifier_memory.update import (
    cache_fetch_argv,
    cache_reset_argv,
    env_install_argv,
)

# --------------------------------------------------------------- AGENTS.md rule 5


def _help(argv: Sequence[str]) -> str:
    proc = subprocess.run(
        list(argv),
        capture_output=True,
        text=True,
        check=True,
        env={**os.environ, "MANPAGER": "cat", "GIT_PAGER": "cat", "NO_COLOR": "1"},
    )
    out = proc.stdout + proc.stderr
    print(f"$ {' '.join(argv)}\n{out}")
    return out


def _usage(argv: Sequence[str]) -> str:
    """Like `_help`, but for the `-h` forms that print usage and exit nonzero."""
    proc = subprocess.run(
        list(argv),
        capture_output=True,
        text=True,
        check=False,
        env={**os.environ, "MANPAGER": "cat", "GIT_PAGER": "cat", "NO_COLOR": "1"},
    )
    out = proc.stdout + proc.stderr
    print(f"$ {' '.join(argv)}   (exit {proc.returncode})\n{out}")
    return out


@pytest.mark.skipif(shutil.which("uv") is None, reason="uv is not on PATH")
def test_uv_tool_upgrade_argv_exists() -> None:
    """`uv tool upgrade amplifier-memory` — the tool name is a positional <NAME>."""
    out = _help(["uv", "tool", "upgrade", "--help"])
    assert "uv tool upgrade" in out
    assert "<NAME>" in out, "uv tool upgrade does not take a positional tool name"
    assert amplifier_memory.UPGRADE_CLI_ARGV[:3] == ("uv", "tool", "upgrade")
    assert amplifier_memory.UPGRADE_CLI_ARGV[3] == "amplifier-memory"


@pytest.mark.skipif(shutil.which("amplifier") is None, reason="amplifier is not on PATH")
def test_amplifier_bundle_add_and_remove_argv_exist() -> None:
    """`amplifier bundle add|remove <uri> --app` — the app-bundle refresh path.

    `amplifier bundle update` is NOT used: measured on this device it cannot reach an
    app bundle registered by URI (`No handler for URI: memory-session` by name,
    `No active bundle.` with `--source`, and `--all` enumerates registry bundles only).
    """
    add = _help(["amplifier", "bundle", "add", "--help"])
    remove = _help(["amplifier", "bundle", "remove", "--help"])
    assert "--app" in add and "URI" in add
    assert "--app" in remove
    assert amplifier_memory.BUNDLE_ADD_ARGV[:3] == ("amplifier", "bundle", "add")
    assert amplifier_memory.BUNDLE_REMOVE_ARGV[:3] == ("amplifier", "bundle", "remove")
    assert amplifier_memory.BUNDLE_ADD_ARGV[-1] == "--app"


@pytest.mark.skipif(shutil.which("uv") is None, reason="uv is not on PATH")
def test_uv_pip_install_argv_exists() -> None:
    """`uv pip install --python <p> --refresh --reinstall-package <name> <requirement>`.

    This is the command that repaired the steward's device by hand on 2026-09-06; every
    flag in it is asked of `uv pip install --help` here rather than assumed.
    """
    out = _help(["uv", "pip", "install", "--help"])
    for flag in ("--python", "--refresh", "--reinstall-package"):
        assert flag in out, f"uv pip install has no {flag}"
    argv = env_install_argv(Path("/tmp/venv/bin/python"))
    print(" ".join(argv))
    assert argv[:3] == ("uv", "pip", "install")
    assert argv[3:5] == ("--python", "/tmp/venv/bin/python")
    assert "--refresh" in argv and "--reinstall-package" in argv
    assert argv[-1] == amplifier_memory.update.LIBRARY_REQUIREMENT
    assert argv[-1].startswith("amplifier-memory @ git+https://github.com/")


def test_git_cache_refresh_argv_exists() -> None:
    """`git -C <dir> fetch origin` and `git -C <dir> reset --hard origin/<ref>`.

    `git <subcommand> -h` prints its usage and exits nonzero, so the usage forms are
    read with `_usage` rather than `_help` — the text is the point, not the exit code.
    """
    top = _help(["git", "--help"])
    assert "-C <path>" in top, "git has no -C"
    fetch = _usage(["git", "fetch", "-h"])
    assert "<repository>" in fetch, "git fetch takes no positional repository"
    reset = _usage(["git", "reset", "-h"])
    assert "--hard" in reset, "git reset has no --hard"
    clone = Path("/tmp/cache/bundle-abc")
    assert cache_fetch_argv(clone) == ("git", "-C", str(clone), "fetch", "origin")
    assert cache_reset_argv(clone) == (
        "git",
        "-C",
        str(clone),
        "reset",
        "--hard",
        "origin/main",
    )
    print(" ".join(cache_fetch_argv(clone)), "|", " ".join(cache_reset_argv(clone)))


def test_app_bundle_uri_points_at_the_behavior_not_the_root_bundle() -> None:
    """The root-bundle URI composes nothing (a self-include the loader skips).

    Evidence: tests/smoke/evidence/ — with the root URI installed, a real session
    answered `NONE` where the announce belongs; with this URI, `Loaded 1 memories`.
    """
    uri = amplifier_memory.APP_BUNDLE_URI
    print(uri)
    assert uri.endswith("#subdirectory=behaviors/memory-session.yaml")
    assert uri.startswith("git+https://github.com/microsoft/amplifier-bundle-memory@")


# --------------------------------------------------------------- behaviour


def _fake_doctor() -> DoctorReport:
    from pathlib import Path

    return DoctorReport(home=Path("/tmp/store"), rows=[DoctorRow("store", "OK", "present")])


class _Recorder:
    """A runner that records argv and answers with canned exit codes."""

    def __init__(self, codes: dict[str, int] | None = None) -> None:
        self.calls: list[tuple[str, ...]] = []
        self.codes = codes or {}

    def __call__(self, argv: Sequence[str]) -> tuple[int, str]:
        argv = tuple(argv)
        self.calls.append(argv)
        for needle, code in self.codes.items():
            if needle in " ".join(argv):
                return code, f"simulated failure of {needle}"
        return 0, f"ok: {' '.join(argv)}"


# --------------------------------------------------------------- the fake device


def _git(args: list[str], cwd: Path) -> str:
    proc = subprocess.run(["git", *args], cwd=cwd, capture_output=True, text=True, check=True)
    return proc.stdout.strip()


class FakeDevice:
    """A temp stand-in for the three installed things, with a local-disk "remote".

    `origin` is a real repository with two commits; the cache clones and the venv's
    `direct_url.json` are parked on the older one, exactly as the steward's device was
    found on 2026-09-06. Nothing here needs the network, so the git half of `update`
    can really run.
    """

    def __init__(self, root: Path, *, clones: int = 2, venv: bool = True) -> None:
        self.root = root
        self.origin = root / "origin"
        self.origin.mkdir(parents=True)
        _git(["init", "-b", "main"], self.origin)
        (self.origin / "bundle.md").write_text("v1\n", encoding="utf-8")
        _git(["add", "."], self.origin)
        _git(["commit", "-m", "the commit the device is stuck on"], self.origin)
        self.old = _git(["rev-parse", "HEAD"], self.origin)
        (self.origin / "bundle.md").write_text("v2\n", encoding="utf-8")
        _git(["add", "."], self.origin)
        _git(["commit", "-m", "the commit main is at"], self.origin)
        self.new = _git(["rev-parse", "HEAD"], self.origin)

        self.uri = f"git+file://{self.origin}@main#subdirectory=behaviors/memory-session.yaml"
        self.home = root / "amplifier"
        parents = [self.home / "cache", self.home / "cache" / "skills"][:clones]
        for parent in parents:
            parent.mkdir(parents=True)
            clone = parent / cache_dir_name(self.uri)
            _git(["clone", str(self.origin), str(clone)], self.root)
            _git(["reset", "--hard", self.old], clone)

        self.python: Path | None = None
        if venv:
            self.python = root / "venv" / "bin" / "python"
            self.python.parent.mkdir(parents=True)
            self.python.write_text("#!/bin/sh\n", encoding="utf-8")
            self.python.chmod(0o755)
            self.dist = (
                root
                / "venv"
                / "lib"
                / "python3.13"
                / "site-packages"
                / "amplifier_memory-0.1.0.dist-info"
            )
            self.dist.mkdir(parents=True)
            self._write_env_commit(self.old)

    def _write_env_commit(self, commit: str) -> None:
        (self.dist / "direct_url.json").write_text(
            json.dumps(
                {
                    "url": str(self.origin),
                    "vcs_info": {
                        "vcs": "git",
                        "commit_id": commit,
                        "requested_revision": "main",
                    },
                }
            ),
            encoding="utf-8",
        )

    def runner(self, calls: list[tuple[str, ...]]):
        """git runs for real (local origin); uv/amplifier are stood in for."""

        def run(argv: Sequence[str]) -> tuple[int, str]:
            argv = tuple(argv)
            calls.append(argv)
            if argv[0] == "git":
                return _real_default_runner(argv)
            if argv[:3] == ("uv", "pip", "install"):
                # What the real `uv pip install` would leave behind: a new commit id.
                self._write_env_commit(self.new)
                return (
                    0,
                    f"- amplifier-memory ({self.old[:7]})\n+ amplifier-memory ({self.new[:7]})",
                )
            return 0, f"stood in for: {' '.join(argv)}"

        return run

    def clones(self) -> list[Path]:
        return bundle_cache_dirs(self.uri, self.home)

    def update(self, runner, **kw):
        return amplifier_memory.run_update(
            runner=runner,
            doctor_fn=_fake_doctor,
            app_bundle_uri=self.uri,
            amplifier_home=str(self.home),
            env_python=self.python,
            **kw,
        )


# --------------------------------------------------------------- finding the three


def test_cache_dir_name_is_amplifiers_own_derivation() -> None:
    """`<repo>-<sha256(url@ref)[:16]>` — the rule, and the name it yields on this device.

    Both halves matter: the formula is amplifier's
    (`amplifier_foundation/sources/git.py::_get_cache_path`), and the name it produces
    for this bundle's own URI is the directory `~/.amplifier/cache/` really holds.
    """
    import hashlib

    url = "https://github.com/microsoft/amplifier-bundle-memory"
    expected = "amplifier-bundle-memory-" + hashlib.sha256(f"{url}@main".encode()).hexdigest()[:16]
    got = cache_dir_name(amplifier_memory.APP_BUNDLE_URI)
    print(got)
    assert got == expected
    assert got == "amplifier-bundle-memory-aa8dcd869aff907a", (
        "microsoft URL, measured 2026-09-07 (was 450b259c7cb6895f under bkrabach)"
    )


def test_bundle_cache_dirs_finds_both_the_module_cache_and_the_skills_twin(
    tmp_path: Path,
) -> None:
    device = FakeDevice(tmp_path)
    found = device.clones()
    for path in found:
        print(path, commit_of_cache(path)[:7])
    assert [path.parent.name for path in found] == ["cache", "skills"]
    assert all(commit_of_cache(path) == device.old for path in found)


def test_bundle_cache_dirs_falls_back_to_an_origin_match(tmp_path: Path) -> None:
    """A URI spelled with another ref must not silently refresh nothing."""
    device = FakeDevice(tmp_path)
    other = f"git+file://{device.origin}@some-other-ref"
    assert cache_dir_name(other) != cache_dir_name(device.uri), "the derived names differ"
    found = bundle_cache_dirs(other, device.home)
    print(other, "->", [str(path) for path in found])
    assert [path.parent.name for path in found] == ["cache", "skills"]


def test_bundle_cache_dirs_is_empty_when_nothing_is_installed(tmp_path: Path) -> None:
    device = FakeDevice(tmp_path, clones=0)
    assert device.clones() == []


def test_commit_of_env_library_reads_uvs_own_record(tmp_path: Path) -> None:
    """uv records the resolved commit in the dist-info's `direct_url.json` (PEP 610)."""
    device = FakeDevice(tmp_path)
    record = device.dist / "direct_url.json"
    print(record, "->", record.read_text(encoding="utf-8"))
    assert commit_of_env_library(device.python) == device.old
    assert commit_of_env_library(None) is None, "no venv is not knowable, never guessed"
    empty = tmp_path / "bare" / "bin" / "python"
    empty.parent.mkdir(parents=True)
    assert commit_of_env_library(empty) is None, "a venv without the dist is not a guess"


def test_amplifier_env_python_is_a_venv_python_or_none() -> None:
    """Whatever this device answers, it is a `bin/python` next to the `amplifier` it found."""
    found = amplifier_env_python()
    print("amplifier_env_python():", found)
    if shutil.which("amplifier") is None:
        assert found is None
    else:
        assert found is None or found.name.startswith("python")


def test_installed_commits_names_three_legs(tmp_path: Path) -> None:
    device = FakeDevice(tmp_path)
    legs = installed_commits(
        app_bundle_uri=device.uri, amplifier_home=device.home, env_python=device.python
    )
    print(legs)
    assert list(legs) == ["uv tool", "bundle cache", "env library"]
    assert legs["bundle cache"] == device.old and legs["env library"] == device.old


def test_installed_commits_splits_the_cache_leg_when_the_clones_disagree(tmp_path: Path) -> None:
    """A `cache/` and a `cache/skills/` at different commits is named, never averaged."""
    device = FakeDevice(tmp_path)
    _git(["reset", "--hard", device.new], device.clones()[1])
    legs = installed_commits(
        app_bundle_uri=device.uri, amplifier_home=device.home, env_python=device.python
    )
    print(legs)
    assert "bundle cache (cache/)" in legs and "bundle cache (skills/)" in legs
    assert legs["bundle cache (cache/)"] == device.old
    assert legs["bundle cache (skills/)"] == device.new


# --------------------------------------------------------------- what `update` does


def test_update_refreshes_all_three_installed_things(tmp_path: Path) -> None:
    """The lane's whole point: after `update`, all three are at the new commit.

    The uv-tool leg is stood in for (upgrading the machine running the suite is not a
    test), but the cache clones really move — `git log -1` below is read off disk after
    the run, not from the step's own claim.
    """
    device = FakeDevice(tmp_path)
    calls: list[tuple[str, ...]] = []
    result = device.update(device.runner(calls))
    print(result.render())
    print("\nargv the runner saw:")
    for argv in calls:
        print("   ", " ".join(argv))

    names = [step.name for step in result.steps]
    assert names[0] == "upgrade the CLI"
    assert sum("refresh the bundle cache" in name for name in names) == 2, names
    assert any(
        name.startswith("refresh the library in the amplifier environment") for name in names
    )
    for name in names:
        if "refresh the" in name:
            assert f"{device.old[:7]} \u2192 {device.new[:7]}" in name, name

    print("\ngit log -1 in each clone AFTER the run:")
    for clone in device.clones():
        print("   ", clone, "->", _git(["log", "-1", "--oneline"], clone))
        assert commit_of_cache(clone) == device.new, "the clone did not move"
    assert commit_of_env_library(device.python) == device.new
    assert result.exit_code == 0
    assert calls[0] == amplifier_memory.UPGRADE_CLI_ARGV
    assert amplifier_memory.BUNDLE_ADD_ARGV not in calls, "a live clone needs no re-register"


def test_doctor_reads_all_three_as_current_after_the_update(tmp_path: Path) -> None:
    """cli.v2 Core 5's update row, over the same fake device, before and after."""
    device = FakeDevice(tmp_path)
    legs = lambda: {
        "uv tool": device.new,
        **{
            k: v
            for k, v in installed_commits(
                app_bundle_uri=device.uri,
                amplifier_home=device.home,
                env_python=device.python,
            ).items()
            if k != "uv tool"
        },
    }
    before = amplifier_memory.update_check(legs(), device.new)
    print(before.render())
    assert before.level == "WARN"
    assert f"bundle cache {device.old[:7]} behind main {device.new[:7]}" in before.detail
    assert f"env library {device.old[:7]} behind main" in before.detail
    assert "amplifier-memory update" in before.detail

    device.update(device.runner([]))
    after = amplifier_memory.update_check(legs(), device.new)
    print(after.render())
    assert after.level == "OK"
    for leg in ("uv tool", "bundle cache", "env library"):
        assert f"{leg} {device.new[:7]}" in after.detail, after.detail
    assert "== main" in after.detail


def test_no_amplifier_venv_warns_and_the_other_steps_still_run(tmp_path: Path) -> None:
    device = FakeDevice(tmp_path, venv=False)
    calls: list[tuple[str, ...]] = []
    result = device.update(device.runner(calls))
    library = next(step for step in result.steps if "amplifier environment" in step.name)
    print(result.render())
    assert "[warn]" in library.render(), library.render()
    assert "no amplifier environment found" in library.output
    assert not library.failed, "a device without `amplifier` is not a failed update"
    assert result.exit_code == 0
    assert all(commit_of_cache(clone) == device.new for clone in device.clones()), (
        "the cache refresh stopped because the venv was missing"
    )
    assert not any(argv[:3] == ("uv", "pip", "install") for argv in calls)


def test_a_cache_that_is_not_a_git_clone_falls_back_to_remove_then_add(tmp_path: Path) -> None:
    device = FakeDevice(tmp_path, clones=0)
    plain = device.home / "cache" / cache_dir_name(device.uri)
    plain.mkdir(parents=True)
    (plain / "bundle.md").write_text("unpacked, not cloned\n", encoding="utf-8")
    calls: list[tuple[str, ...]] = []
    result = device.update(device.runner(calls))
    print(result.render())
    fallback = next(
        step for step in result.steps if step.name.startswith("register the app bundle")
    )
    assert "none a git clone" in fallback.name, fallback.name
    assert amplifier_memory.BUNDLE_ADD_ARGV in calls
    assert result.exit_code == 0


def test_nothing_installed_yet_registers_the_app_bundle(tmp_path: Path) -> None:
    """The install path is still reachable: `bundle add` is what creates the clone."""
    device = FakeDevice(tmp_path, clones=0)
    calls: list[tuple[str, ...]] = []
    result = device.update(device.runner(calls))
    print(result.render())
    fallback = next(
        step for step in result.steps if step.name.startswith("register the app bundle")
    )
    assert "no cache clone found" in fallback.name
    assert calls[1] == amplifier_memory.BUNDLE_REMOVE_ARGV
    assert calls[2] == amplifier_memory.BUNDLE_ADD_ARGV


def test_run_update_prints_the_plan_the_stale_note_and_doctor() -> None:
    """cli.v2 Core 7's output requirements, checked on the rendered text."""
    out = amplifier_memory.run_update(
        runner=_Recorder(),
        doctor_fn=_fake_doctor,
        amplifier_home="/nonexistent-home",
        env_python=None,
    ).render()
    print(out)
    assert "uv tool upgrade amplifier-memory" in out
    assert "amplifier bundle add" in out and "--app" in out
    assert "git fetch origin" in out and "reset --hard origin/main" in out, "the plan's step 2"
    assert "uv pip install" in out, "the plan's step 3"
    assert "keep the old module code until they restart" in out, "the stale-in-memory note"
    assert "amplifier-memory doctor — store:" in out, "update did not end by running doctor"


def test_phase_1_skips_the_timer_and_says_why_in_the_librarys_own_words() -> None:
    result = amplifier_memory.run_update(
        runner=_Recorder(),
        doctor_fn=_fake_doctor,
        amplifier_home="/nonexistent-home",
        env_python=None,
    )
    timer = next(step for step in result.steps if "timer" in step.name)
    print(timer.render())
    assert timer.skipped
    assert timer.reason == amplifier_memory.service_status("restart").splitlines()[0]
    assert not timer.failed


def test_a_missing_app_entry_does_not_fail_the_update(tmp_path: Path) -> None:
    """The remove is tolerated: an entry that is already absent is not an error."""
    device = FakeDevice(tmp_path, clones=0)
    runner = _Recorder(codes={"bundle remove": 1})
    result = device.update(runner)
    removal = next(step for step in result.steps if "drop" in step.name)
    print(result.render())
    assert removal.returncode == 1
    assert not removal.failed
    assert result.exit_code == 0


def test_a_failed_upgrade_is_reported_and_exits_nonzero() -> None:
    runner = _Recorder(codes={"tool upgrade": 2})
    result = amplifier_memory.run_update(
        runner=runner, doctor_fn=_fake_doctor, amplifier_home="/nonexistent-home", env_python=None
    )
    print(result.render())
    assert result.exit_code == 1
    assert "FAIL" in result.render()
    assert "simulated failure" in result.render()


def test_a_failed_cache_fetch_is_reported_and_the_clone_is_named_unmoved(tmp_path: Path) -> None:
    device = FakeDevice(tmp_path, clones=1)
    runner = _Recorder(codes={"fetch origin": 128})
    result = device.update(runner)
    print(result.render())
    step = next(s for s in result.steps if "refresh the bundle cache" in s.name)
    assert "unmoved" in step.name and step.failed
    assert result.exit_code == 1
    assert commit_of_cache(device.clones()[0]) == device.old


# --------------------------------------------------------------- one run is enough
#
# The process running `update` IS the pre-upgrade CLI (measured 2026-09-06 22:25Z: the
# first run after an upgrade printed the old binary's steps and the old doctor row; only
# the second run refreshed the cache and the venv). These tests drive both sides of the
# hand-off with a scripted commit reader and a monkeypatched `os.execv`, so no test ever
# upgrades or re-executes the machine running the suite.


class _Commits:
    """A stand-in for `doctor.installed_commit()` that answers a scripted sequence.

    The last value is repeated, so `(old,)` means "nothing moved" and `(old, new)` means
    "step 1 upgraded this install" without the test having to count the readings.
    """

    def __init__(self, *values: str | None) -> None:
        self.values = list(values)
        self.calls = 0

    def __call__(self) -> str | None:
        value = self.values[min(self.calls, len(self.values) - 1)]
        self.calls += 1
        return value


def _forbidden_execv(path, argv):  # a trap: never called
    raise AssertionError(f"re-executed when it must not: {path} {list(argv)}")


def test_an_upgrade_hands_the_rest_of_the_run_to_the_new_binary(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """Upgraded -> `os.execv(<amplifier-memory>, [..., "update", "--after-upgrade"])`.

    And nothing after step 1 runs here: the clones are still on the old commit and the
    runner saw exactly one argv, because the refresh belongs to the new code.
    """
    device = FakeDevice(tmp_path)
    calls: list[tuple[str, ...]] = []
    execs: list[tuple[str, list[str]]] = []
    binary = "/fake/bin/amplifier-memory"
    monkeypatch.setattr(os, "execv", lambda path, argv: execs.append((path, list(argv))))
    monkeypatch.setattr(
        shutil, "which", lambda name: binary if name == "amplifier-memory" else None
    )

    result = device.update(
        device.runner(calls), installed_commit_fn=_Commits(device.old, device.new)
    )
    printed = capsys.readouterr().out
    print(printed, end="")
    print("os.execv calls:", execs)
    print("argv the runner saw:", [" ".join(argv) for argv in calls])
    print("steps recorded by the OLD process:", [step.name for step in result.steps])

    assert execs == [(binary, [binary, "update", "--after-upgrade"])], execs
    assert [step.name for step in result.steps] == ["upgrade the CLI"], "a step ran after step 1"
    assert calls == [amplifier_memory.UPGRADE_CLI_ARGV], calls
    assert result.report is None, "doctor ran in the process that was about to be replaced"
    for clone in device.clones():
        assert commit_of_cache(clone) == device.old, "the old process refreshed the cache"
    assert commit_of_env_library(device.python) == device.old
    assert "upgrade the CLI" in printed, "the steward loses step 1 unless it is printed first"
    assert f"with {device.new[:7]}, not {device.old[:7]}" in printed


def test_after_upgrade_skips_step_1_and_runs_the_rest_with_the_new_code(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The other half of the hand-off: the re-executed process refreshes and runs doctor."""
    device = FakeDevice(tmp_path)
    calls: list[tuple[str, ...]] = []
    monkeypatch.setattr(os, "execv", _forbidden_execv)

    result = device.update(device.runner(calls), after_upgrade=True)
    print(result.render())

    step_one = result.steps[0]
    assert step_one.name == "upgrade the CLI" and step_one.skipped
    assert step_one.reason == "skipped \u2014 already upgraded by the previous process"
    assert amplifier_memory.UPGRADE_CLI_ARGV not in calls, calls
    names = [step.name for step in result.steps]
    assert sum("refresh the bundle cache" in name for name in names) == 2, names
    assert any("amplifier environment" in name for name in names), names
    assert all(commit_of_cache(clone) == device.new for clone in device.clones())
    assert commit_of_env_library(device.python) == device.new
    assert result.report is not None, "the re-executed process must end in doctor"
    assert result.exit_code == 0


def test_no_upgrade_means_no_hand_off_and_every_step_runs_here(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Commits equal -> exactly the run lane M left: step 1, both caches, the venv, doctor."""
    device = FakeDevice(tmp_path)
    calls: list[tuple[str, ...]] = []
    monkeypatch.setattr(os, "execv", _forbidden_execv)

    result = device.update(device.runner(calls), installed_commit_fn=_Commits(device.old))
    rendered = result.render()
    print(rendered)

    assert result.steps[0].argv == amplifier_memory.UPGRADE_CLI_ARGV
    assert not result.steps[0].skipped
    assert not any(step.info for step in result.steps), "an INFO line with nothing to warn about"
    assert amplifier_memory.update.IN_PLACE_NOTE not in rendered
    assert all(commit_of_cache(clone) == device.new for clone in device.clones())
    assert commit_of_env_library(device.python) == device.new
    assert result.report is not None and result.exit_code == 0


def test_no_binary_to_re_exec_prints_one_info_line_and_carries_on(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Hand-off impossible: the steps still run, and one line says they ran with old code."""
    device = FakeDevice(tmp_path)
    monkeypatch.setattr(os, "execv", _forbidden_execv)
    monkeypatch.setattr(shutil, "which", lambda name: None)

    result = device.update(device.runner([]), installed_commit_fn=_Commits(device.old, device.new))
    rendered = result.render()
    print(rendered)

    infos = [step for step in result.steps if step.info]
    assert len(infos) == 1, [step.name for step in result.steps]
    assert amplifier_memory.update.IN_PLACE_NOTE in infos[0].reason
    assert "is not on PATH" in infos[0].reason
    assert rendered.count(amplifier_memory.update.IN_PLACE_NOTE) == 1, "said twice"
    assert infos[0].render().startswith("  [info] "), infos[0].render()
    assert not infos[0].failed, "an unusable hand-off is not a failed update"
    assert all(commit_of_cache(clone) == device.new for clone in device.clones())
    assert result.report is not None and result.exit_code == 0


def test_the_hand_off_never_loops(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """`--after-upgrade` with a moved commit re-executes nothing: it says so instead."""
    device = FakeDevice(tmp_path)
    monkeypatch.setattr(os, "execv", _forbidden_execv)

    result = device.update(
        device.runner([]), after_upgrade=True, installed_commit_fn=_Commits(device.old, device.new)
    )
    print(result.render())

    infos = [step for step in result.steps if step.info]
    assert len(infos) == 1
    assert amplifier_memory.update.IN_PLACE_NOTE in infos[0].reason
    assert "already the re-exec" in infos[0].reason
    assert result.exit_code == 0


def test_an_execv_that_refuses_is_reported_not_raised(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """`update` is a maintenance verb: a hand-off that cannot happen is a line, not a crash."""
    device = FakeDevice(tmp_path)

    def refusing(path, argv):
        raise OSError(13, "Permission denied")

    monkeypatch.setattr(os, "execv", refusing)
    monkeypatch.setattr(shutil, "which", lambda name: "/fake/bin/amplifier-memory")

    result = device.update(device.runner([]), installed_commit_fn=_Commits(device.old, device.new))
    capsys.readouterr()
    print(result.render())

    info = next(step for step in result.steps if step.info)
    assert amplifier_memory.update.IN_PLACE_NOTE in info.reason
    assert "Permission denied" in info.reason
    assert all(commit_of_cache(clone) == device.new for clone in device.clones())
    assert result.exit_code == 0


def test_doctors_own_failure_makes_update_exit_nonzero() -> None:
    from pathlib import Path

    def failing_doctor() -> DoctorReport:
        return DoctorReport(home=Path("/tmp/x"), rows=[DoctorRow("store", "FAIL", "missing")])

    result = amplifier_memory.run_update(runner=_Recorder(), doctor_fn=failing_doctor)
    assert result.exit_code == 1


def test_the_default_runner_never_raises_on_a_missing_executable() -> None:
    """`update` is a maintenance verb: it reports what is wrong, it does not crash."""
    code, out = _real_default_runner(["definitely-not-a-real-command-xyz"])
    print(code, out)
    assert code == 127
    assert "Error" in out or "error" in out.lower()
