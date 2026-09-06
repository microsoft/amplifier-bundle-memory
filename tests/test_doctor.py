"""cli.v1 Core 5 — `doctor` never mutates, and the update check has three states.

The no-mutation claim is proved the only way it can be: sha256 of every file in the
store (including everything under `.git/`) before and after a full doctor run, plus
the commit count and `git status --porcelain`. A doctor that committed, staged, or
truncated anything would move one of those.

The update check is exercised in all three states with the shas injected, so no test
here touches the network. `remote_commit()` itself — the one real network call in the
bundle — is exercised only by the argv-verification test below, which asks git for
its own help rather than reaching the internet.
"""

from __future__ import annotations

import hashlib
import os
import subprocess
from pathlib import Path

import pytest

import amplifier_memory
from amplifier_memory import store as store_mod

SHA_A = "a" * 40
SHA_B = "b" * 40


def _fingerprint(home: Path) -> dict[str, str]:
    """sha256 of every file under the store, `.git` included."""
    out: dict[str, str] = {}
    for path in sorted(home.rglob("*")):
        if path.is_file():
            out[str(path.relative_to(home))] = hashlib.sha256(path.read_bytes()).hexdigest()
    return out


def _seed(home: Path) -> None:
    amplifier_memory.save("never use tabs", "never use tabs", "human", "s-1", ["never use tabs"])
    amplifier_memory.save(
        "two-space indentation",
        "two-space indentation",
        "human",
        "s-1",
        ["two-space indentation"],
        topic="yaml-style",
        topic_purpose="YAML style.",
    )
    amplifier_memory.log_usage("loaded", "MEMORY.md", "s-1")


# --------------------------------------------------------------- Core 5: never mutates


def test_doctor_does_not_mutate_a_single_byte_of_the_store(store: Path) -> None:
    _seed(store)
    before = _fingerprint(store)
    report = amplifier_memory.doctor(installed_sha=SHA_A, remote_sha=SHA_A)
    after = _fingerprint(store)

    print(report.render())
    print(f"\nfiles hashed: {len(before)} before, {len(after)} after")
    changed = [name for name in before if before.get(name) != after.get(name)]
    print("files whose sha256 changed:", changed or "none")
    print("files added:", sorted(set(after) - set(before)) or "none")
    print("files removed:", sorted(set(before) - set(after)) or "none")

    assert before == after, f"doctor mutated the store: {changed}"
    porcelain = subprocess.run(
        ["git", "status", "--porcelain"], cwd=store, capture_output=True, text=True, check=True
    ).stdout.strip()
    print("git status --porcelain:", porcelain or "(clean)")
    assert porcelain == ""


def test_doctor_rows_cover_every_row_the_clause_names(store: Path) -> None:
    _seed(store)
    report = amplifier_memory.doctor(installed_sha=SHA_A, remote_sha=SHA_A)
    names = [row.name for row in report.rows]
    print(report.render())
    assert names == [
        "store",
        "caps",
        "stale topics",
        "inbox",
        "suggest timer",
        "substrate",
        "update",
    ], names
    caps = next(row for row in report.rows if row.name == "caps")
    assert "MEMORY.md 1/200" in caps.detail and "topics 1/50" in caps.detail, caps.detail
    assert report.exit_code == 0


def test_doctor_exit_code_is_nonzero_only_on_a_failed_check(memory_home: Path) -> None:
    """No store is a failed check; a WARN update is not."""
    missing = amplifier_memory.doctor(installed_sha=SHA_A, remote_sha=SHA_B)
    print(missing.render())
    print("exit code with no store:", missing.exit_code)
    assert missing.rows[0].name == "store" and missing.rows[0].level == "FAIL"
    assert "amplifier-memory init" in missing.rows[0].detail, "the remedy is not named"
    assert missing.exit_code == 1

    amplifier_memory.init()
    behind = amplifier_memory.doctor(installed_sha=SHA_A, remote_sha=SHA_B)
    print(behind.render())
    print("exit code with a store and a WARN update row:", behind.exit_code)
    assert [row.level for row in behind.rows if row.name == "update"] == ["WARN"]
    assert behind.exit_code == 0, "a WARN is not a failed check (cli.v1 Core 5)"


def test_doctor_reports_stale_topics_without_deleting_them(store: Path) -> None:
    _seed(store)
    row = next(r for r in amplifier_memory.doctor(installed_sha=None, remote_sha=None).rows
               if r.name == "stale topics")
    print(row.render())
    assert row.level == "INFO", "staleness is reported, never a failure (VISION: a human decides)"
    assert "yaml-style" in row.detail
    assert (store / "topics" / "yaml-style.md").is_file(), "doctor deleted a stale topic"


# --------------------------------------------------------------- Core 5: the update trio


@pytest.mark.parametrize(
    ("installed", "remote", "level", "needle"),
    [
        (SHA_A, SHA_B, "WARN", "amplifier-memory update"),
        (SHA_A, SHA_A, "OK", "current"),
        (SHA_A, None, "INFO", "not checkable"),
        (None, SHA_A, "INFO", "not checkable"),
    ],
)
def test_update_check_trio(installed: str | None, remote: str | None, level: str, needle: str) -> None:
    row = amplifier_memory.update_check(installed, remote)
    print(f"{installed and installed[:8]!s:>10} vs {remote and remote[:8]!s:>10} -> {row.render()}")
    assert row.level == level
    assert needle in row.detail
    assert row.level != "FAIL", "the update check is never RED (cli.v1 Core 5)"


def test_update_check_reaches_doctor_when_the_shas_are_injected(store: Path) -> None:
    report = amplifier_memory.doctor(installed_sha=SHA_A, remote_sha=SHA_B)
    update = next(row for row in report.rows if row.name == "update")
    print(update.render())
    assert update.level == "WARN" and "behind" in update.detail


def test_installed_commit_is_none_or_a_sha_never_a_guess() -> None:
    """A working-tree install has no recorded commit; that is reported, not invented."""
    value = amplifier_memory.installed_commit()
    print("installed_commit():", value)
    assert value is None or (len(value) == 40 and all(c in "0123456789abcdef" for c in value))


# --------------------------------------------------------------- Core 6, 7, 1: the honest verbs


def test_service_reports_that_phase_1_has_no_service() -> None:
    for verb in amplifier_memory.SERVICE_VERBS:
        message = amplifier_memory.service_status(verb)
        assert message.startswith("Phase 1 has no service; the suggest timer arrives with Phase 2.")
    print(amplifier_memory.service_status("install"))
    with pytest.raises(ValueError, match="unknown service verb"):
        amplifier_memory.service_status("frobnicate")


def test_suggest_says_phase_2_is_not_installed() -> None:
    message = amplifier_memory.suggest_status()
    print(message)
    assert message.startswith("Phase 2 not installed.")


def test_update_plan_names_all_four_steps_and_the_stale_in_memory_note() -> None:
    plan = amplifier_memory.update_plan()
    print(plan)
    assert "uv tool upgrade amplifier-memory" in plan
    assert "amplifier bundle add" in plan and "--app" in plan
    assert "doctor" in plan
    assert "keep the old module code until they restart" in plan
    assert "amplifier bundle remove" in plan, (
        "the plan must show the refresh as it is really performed: `amplifier bundle update` "
        "cannot reach an app bundle registered by URI, so step 2 is a remove-then-add"
    )


# --------------------------------------------------------------- AGENTS.md rule 5


ARGV_UNDER_TEST = {
    ("git", None): ["-c <name>=<value>"],
    ("git", "ls-remote"): ["<repository>"],
    # Not shelled by this lane — printed by `update_plan()` as the remedy. Advice that
    # does not exist is exactly the failure AGENTS.md rule 5 was written for
    # (`amplifier run --once` shipped without existing), so it is checked the same way.
    ("uv", "tool upgrade"): ["<NAME>"],
}


@pytest.mark.parametrize(("tool", "subcommand"), sorted(ARGV_UNDER_TEST, key=str))
def test_shelled_argv_added_by_this_lane_is_verified_against_help(
    tool: str, subcommand: str | None
) -> None:
    """AGENTS.md rule 5: ask the CLI's own help, do not assume.

    `git -c user.name=…` is how the writer names itself per commit (store.v1 Core 9);
    `git ls-remote <repository>` is the update check's read; `uv tool upgrade <NAME>` is
    the remedy `update_plan()` prints.
    """
    argv = [tool, *subcommand.split(), "--help"] if subcommand else [tool, "--help"]
    proc = subprocess.run(
        argv,
        capture_output=True,
        text=True,
        check=True,
        env={**os.environ, "MANPAGER": "cat", "GIT_PAGER": "cat"},
    )
    for flag in ARGV_UNDER_TEST[(tool, subcommand)]:
        assert flag in proc.stdout, f"{' '.join(argv)} does not document {flag}"
    print(f"{' '.join(argv)} documents {ARGV_UNDER_TEST[(tool, subcommand)]}")


def test_the_store_repo_holds_no_identity_and_the_writer_names_itself(
    store: Path, human_identity: tuple[str, str]
) -> None:
    """store.v1 Core 9: `git log` attributes a hand commit to the human.

    Carried from wave 1: `init` used to write user.name/user.email into the store's own
    config, so a human editing MEMORY.md with an editor and committing it by hand would
    have been recorded as `amplifier-memory`. The writer names itself per commit instead.
    """
    local = subprocess.run(
        ["git", "config", "--local", "--get", "user.name"],
        cwd=store,
        capture_output=True,
        text=True,
        check=False,
    )
    print(f"git config --local --get user.name -> exit {local.returncode} {local.stdout.strip()!r}")
    assert local.returncode != 0, "init wrote a repo-local identity into the store"

    # With no global config either, `git config --get user.name` is simply unset.
    bare = subprocess.run(
        ["git", "config", "--get", "user.name"],
        cwd=store,
        capture_output=True,
        text=True,
        check=False,
        env={**os.environ, "GIT_CONFIG_GLOBAL": "/dev/null", "GIT_CONFIG_NOSYSTEM": "1"},
    )
    print(f"git config --get user.name (no global) -> exit {bare.returncode}")
    assert bare.returncode != 0

    amplifier_memory.save("never use tabs", "never use tabs", "human", "s-1", ["never use tabs"])
    (store / "MEMORY.md").write_text(
        (store / "MEMORY.md").read_text(encoding="utf-8") + "- [m-002] typed by hand\n",
        encoding="utf-8",
    )
    subprocess.run(["git", "add", "MEMORY.md"], cwd=store, check=True, capture_output=True)
    subprocess.run(
        ["git", "commit", "-m", "hand edit: a human with an editor"],
        cwd=store,
        check=True,
        capture_output=True,
    )
    authors = subprocess.run(
        ["git", "log", "--format=%an <%ae>", "-2"],
        cwd=store,
        capture_output=True,
        text=True,
        check=True,
    ).stdout.splitlines()
    print("git log --format='%an <%ae>' -2:")
    for line in authors:
        print("   ", line)
    name, email = store_mod.STORE_IDENTITY
    assert authors[0] == f"{human_identity[0]} <{human_identity[1]}>", (
        "the hand commit is not attributed to the human"
    )
    assert authors[1] == f"{name} <{email}>", "the writer commit is not attributed to the tool"
