"""cli.v2 Core 5 — `doctor` never mutates, and the update check has three states.

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
import re
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
        # cli.v2 §5 gives well-formedness its own row: "the store is a git repo" and
        # "its contents parse" are different questions with different remedies.
        "MEMORY.md well-formed",
        "stale topics",
        "inbox",
        "suggest timer",
        "substrate",
        # suggestions.v1 Core 8 made visible: which model the daily pass is billed to.
        # cli.v2 §5 enumerates its rows but, unlike Core 1's verb list, does not close
        # the set.
        "llm judge",
        "update",
    ], names
    caps = next(row for row in report.rows if row.name == "caps")
    assert "MEMORY.md 1/200" in caps.detail and "topics 1/50" in caps.detail, caps.detail
    wellformed = next(row for row in report.rows if row.name == "MEMORY.md well-formed")
    assert wellformed.level == "OK" and "well-formed" in wellformed.detail, wellformed.detail
    store_row = next(row for row in report.rows if row.name == "store")
    assert "well-formed" not in store_row.detail, "the store row still carries the parse check"
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
    assert behind.exit_code == 0, "a WARN is not a failed check (cli.v2 Core 5)"


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
    assert row.level != "FAIL", "the update check is never RED (cli.v2 Core 5)"


def test_update_check_reaches_doctor_when_the_shas_are_injected(store: Path) -> None:
    report = amplifier_memory.doctor(installed_sha=SHA_A, remote_sha=SHA_B)
    update = next(row for row in report.rows if row.name == "update")
    print(update.render())
    assert update.level == "WARN" and "behind" in update.detail


# ----------------------------------------------- Core 5: the update row reads all three


def _legs(uv: str | None, cache: str | None, library: str | None) -> dict[str, str | None]:
    return {"uv tool": uv, "bundle cache": cache, "env library": library}


def test_update_check_is_ok_only_when_all_three_agree() -> None:
    row = amplifier_memory.update_check(_legs(SHA_A, SHA_A, SHA_A), SHA_A)
    print(row.render())
    assert row.level == "OK"
    for leg in ("uv tool", "bundle cache", "env library"):
        assert f"{leg} {SHA_A[:7]}" in row.detail, row.detail
    assert "== main" in row.detail


@pytest.mark.parametrize("behind_leg", ["uv tool", "bundle cache", "env library"])
def test_update_check_names_which_of_the_three_is_behind(behind_leg: str) -> None:
    """The row must name the stale one. "current" over a stale cache is the whole defect."""
    legs = _legs(SHA_A, SHA_A, SHA_A) | {behind_leg: SHA_B}
    row = amplifier_memory.update_check(legs, SHA_A)
    print(row.render())
    assert row.level == "WARN"
    assert f"{behind_leg} {SHA_B[:7]} behind main {SHA_A[:7]}" in row.detail
    assert "amplifier-memory update" in row.detail
    for current in [leg for leg in legs if leg != behind_leg]:
        assert f"{current} {SHA_B[:7]}" not in row.detail, "a current leg is named as behind"


def test_a_leg_that_cannot_be_found_is_info_never_red() -> None:
    """No amplifier venv, or no cache, is not a broken install (cli.v2 Core 5)."""
    row = amplifier_memory.update_check(_legs(SHA_A, SHA_A, None), SHA_A)
    print(row.render())
    assert row.level == "INFO"
    assert "env library not found" in row.detail
    assert "uv tool" in row.detail and "bundle cache" in row.detail

    behind_and_missing = amplifier_memory.update_check(_legs(SHA_A, SHA_B, None), SHA_A)
    print(behind_and_missing.render())
    assert behind_and_missing.level == "WARN", "something behind outranks something absent"
    assert "bundle cache" in behind_and_missing.detail
    assert "env library not found" in behind_and_missing.detail


def test_the_update_row_this_device_produces_is_one_of_the_honest_shapes(store: Path) -> None:
    """The default path reads all three off this device — read-only, and never RED."""
    row = next(r for r in amplifier_memory.doctor().rows if r.name == "update")
    print(row.render())
    assert row.level in ("OK", "WARN", "INFO")
    assert row.level != "FAIL", "the update check is never RED (cli.v2 Core 5)"


def test_installed_commit_is_none_or_a_sha_never_a_guess() -> None:
    """A working-tree install has no recorded commit; that is reported, not invented."""
    value = amplifier_memory.installed_commit()
    print("installed_commit():", value)
    assert value is None or (len(value) == 40 and all(c in "0123456789abcdef" for c in value))


# --------------------------------------------------------------- Core 6, 7, 1: the honest verbs


def test_service_reports_the_timer_when_there_is_none(tmp_path: Path, store: Path) -> None:
    """cli.v2 Core 6: with no timer installed, every verb says so and runs no command.

    `config_dir` is a temp directory and the runner is a recorder, because this test once
    installed and enabled a real daily timer on this device (see
    `service._default_runner`'s guard).
    """
    calls: list[tuple[str, ...]] = []

    def recorder(argv):
        calls.append(tuple(argv))
        return 0, ""

    for verb in amplifier_memory.SERVICE_VERBS:
        if verb in ("install", "uninstall"):
            continue
        message = amplifier_memory.service_status(
            verb, runner=recorder, config_dir=tmp_path / "units", home=store
        )
        assert "no suggest timer is installed" in message or "not installed" in message, message
    print(amplifier_memory.service_status("status", runner=recorder, config_dir=tmp_path / "units", home=store))
    assert calls == [], f"a verb shelled out with no timer installed: {calls}"
    with pytest.raises(ValueError, match="unknown service verb"):
        amplifier_memory.service_status("frobnicate")


def test_suggest_status_reads_the_last_run_back_out_of_the_log(store: Path) -> None:
    """suggestions.v1 Core 9: the run log is the record, and 'never run' is an answer."""
    never = amplifier_memory.suggest_status(store)
    print(never)
    assert "has not run on this device yet" in never

    report = amplifier_memory.run_suggest(
        store, base_path=store / "no-substrate-here", model_call=lambda prompt: "[]"
    )
    print(report.log_line)
    after = amplifier_memory.suggest_status(store)
    print(after)
    assert "status degraded:substrate missing" in after
    assert report.log_line in after


def test_update_plan_names_all_five_steps_and_the_stale_in_memory_note() -> None:
    """The plan names the three installed things, because `update` refreshes all three.

    Measured 2026-09-06: a plan that named only the uv tool and the app-bundle entry
    described an update that left a device running four-waves-old module code and said
    `[ok]` while doing it (`docs/workflow/CHECK-RECORD.md`, addendum 22:05Z).
    """
    plan = amplifier_memory.update_plan()
    print(plan)
    assert "uv tool upgrade amplifier-memory" in plan
    assert "git fetch origin" in plan and "reset --hard origin/main" in plan, (
        "step 2 must name the cache-clone refresh: `amplifier bundle add` re-registers the "
        "URI without moving an existing clone off its old commit"
    )
    assert "cache/skills/" in plan, "the skills twin is a second clone, and it is loaded from"
    assert "uv pip install" in plan and "--reinstall-package amplifier-memory" in plan, (
        "step 3 must name the library inside the amplifier venv: that is what the modules "
        "import, and it is resolved once at install time"
    )
    assert "doctor" in plan
    assert "keep the old module code until they restart" in plan
    assert "amplifier bundle remove" in plan and "--app" in plan, (
        "the remove-then-add stays in the plan as the fallback: `amplifier bundle update` "
        "cannot reach an app bundle registered by URI at all"
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

    `git -c user.name=…` is how the writer names itself per commit (store.v2 Core 9);
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
    """store.v2 Core 9: `git log` attributes a hand commit to the human.

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


# ------------------------------- cli.v2 Core 5 + store.v2 Core 3: a malformed MEMORY.md


#: The exact wreckage from the steward's store on 2026-09-06: a clobbered concurrent
#: write left the tail of a memory with no `- [m-NNN]` head. `cat MEMORY.md` showed it;
#: nothing in the tool did. The assistant repaired it by hand with bash.
HEADLESS_FRAGMENT = (
    " work, concrete time estimates, lists capped at 5 and ranked, no preamble or closing "
    "pleasantries."
)


def _corrupt(home: Path) -> None:
    """Seed the transcript's damage: one good line, one headless fragment."""
    amplifier_memory.save(
        "Point time estimates at whoever actually runs the steps.",
        "Point time estimates at whoever actually runs the steps.",
        "human",
        "s-1",
        ["Point time estimates at whoever actually runs the steps."],
    )
    path = home / "MEMORY.md"
    path.write_text(path.read_text(encoding="utf-8") + HEADLESS_FRAGMENT + "\n", encoding="utf-8")
    store_mod._git.commit(home, "hand edit: the clobbered write, as it was found", ["MEMORY.md"])


def test_doctor_names_a_malformed_memory_file_the_line_and_the_remedy(store: Path) -> None:
    """cli.v2 §5: the FAIL lands on the `MEMORY.md well-formed` row, not on `store`."""
    _corrupt(store)
    report = amplifier_memory.doctor(installed_sha=SHA_A, remote_sha=SHA_A)
    print("=== doctor, before repair ===")
    print(report.render())

    row = next(r for r in report.rows if r.name == "MEMORY.md well-formed")
    assert row.level == "FAIL", report.render()
    assert "MEMORY.md is not well-formed" in row.detail
    assert "line 2" in row.detail, row.detail
    assert "doctor --repair" in row.detail, "the remedy is not named"
    assert re.search(r"parsed clean: [0-9a-f]{12}", row.detail), row.detail
    assert report.exit_code == 1, "a malformed store is not a failed check"

    # The discriminating half: the store itself is present and a git repo, and says so.
    # Before the split, one FAIL answered both questions and a healthy store that had
    # been hand-corrupted read as "the store is broken" with no way to tell them apart.
    store_row = next(r for r in report.rows if r.name == "store")
    print("store row while MEMORY.md is malformed:", store_row.render())
    assert store_row.level == "OK", store_row.render()


def test_doctor_itself_still_never_mutates_a_malformed_store(store: Path) -> None:
    """cli.v2 Core 5 holds for the verb: detection is read-only, repair is opt-in."""
    _corrupt(store)
    before = _fingerprint(store)
    amplifier_memory.doctor(installed_sha=SHA_A, remote_sha=SHA_A)
    after = _fingerprint(store)
    print("files whose sha256 changed:", [k for k in before if before.get(k) != after.get(k)] or "none")
    assert before == after


def test_repair_restores_the_last_clean_commit_in_one_visible_commit(store: Path) -> None:
    _corrupt(store)
    before_text = (store / "MEMORY.md").read_text(encoding="utf-8")
    commits_before = store_mod._git.commit_count(store)

    result = amplifier_memory.repair_store()
    print("=== doctor --repair ===")
    print(result.render())

    after_text = (store / "MEMORY.md").read_text(encoding="utf-8")
    print("=== MEMORY.md before ===")
    print(before_text)
    print("=== MEMORY.md after ===")
    print(after_text)
    print("=== doctor, after repair ===")
    print(amplifier_memory.doctor(installed_sha=SHA_A, remote_sha=SHA_A).render())

    assert HEADLESS_FRAGMENT in before_text and HEADLESS_FRAGMENT not in after_text
    assert "- [m-001] Point time estimates at whoever actually runs the steps." in after_text
    assert result.repaired and result.commit and result.restored_from
    assert HEADLESS_FRAGMENT in result.diff, "the diff does not show what was removed"
    assert store_mod._git.commit_count(store) == commits_before + 1, "repair was not one commit"
    message = store_mod._git.log_records(store)[0]["body"]
    print("repair commit message:", message)
    assert message.startswith(f"repair: restore MEMORY.md from {result.restored_from[:12]}")
    assert amplifier_memory.verify_store().ok
    assert amplifier_memory.doctor(installed_sha=SHA_A, remote_sha=SHA_A).exit_code == 0


def test_repair_on_a_healthy_store_changes_nothing_and_says_so(store: Path) -> None:
    _seed(store)
    before = _fingerprint(store)
    result = amplifier_memory.repair_store()
    print(result.render())
    assert not result.repaired and result.commit is None
    assert _fingerprint(store) == before


def test_repair_falls_back_to_the_empty_file_init_committed(store: Path) -> None:
    """There is always a clean commit for a store `init` made: its first one is empty.

    So the "nothing to restore from" branch is unreachable for a real store, and the
    worst case is losing hand-written damage back to the last state that parsed — never
    an invented file. Recorded here rather than claimed: this is what actually happens.
    """
    (store / "MEMORY.md").write_text("not a memory line at all\n", encoding="utf-8")
    store_mod._git.commit(store, "hand edit: corrupt", ["MEMORY.md"])

    result = amplifier_memory.repair_store()
    print(result.render())
    print("MEMORY.md after:", repr((store / "MEMORY.md").read_text(encoding="utf-8")))
    assert result.repaired
    assert (store / "MEMORY.md").read_text(encoding="utf-8") == ""
    assert amplifier_memory.verify_store().ok


# ------------------------- suggestions.v1 Core 8 made visible: which model, and what it cost


def _llm(tmp_path: Path, body: str):
    from amplifier_memory import llm_config

    path = tmp_path / llm_config.CONFIG_NAME
    path.write_text(body, encoding="utf-8")
    return llm_config.load(path)


def test_the_llm_row_names_the_resolved_judge_or_the_inheritance(
    store: Path, tmp_path: Path
) -> None:
    from amplifier_memory import llm_config
    from amplifier_memory.doctor import llm_row

    inherited = llm_row(llm_config.load(tmp_path / llm_config.CONFIG_NAME), home=store)
    print(inherited.render())
    assert inherited.level == "OK"
    assert "inherits the CLI default" in inherited.detail
    assert llm_config.CONFIG_NAME in inherited.detail, "the file's name and place are named"
    assert "role fast" in inherited.detail and "--model-role" in inherited.detail

    configured = llm_row(
        _llm(tmp_path, '[llm.judge]\nprovider = "luna"\nmodel = "gpt-5.6-luna"\n'), home=store
    )
    print(configured.render())
    assert configured.level == "OK"
    assert "provider luna" in configured.detail and "model gpt-5.6-luna" in configured.detail
    assert llm_config.CONFIG_NAME in configured.detail


def test_the_llm_row_warns_when_the_file_is_there_but_unusable(store: Path, tmp_path: Path) -> None:
    """Nothing is broken - the pass still runs - but the user's choice did not take."""
    from amplifier_memory.doctor import llm_row

    row = llm_row(_llm(tmp_path, "[llm.judge\nprovider = 'luna'\n"), home=store)
    print(row.render())
    assert row.level == "WARN", "a bad config file is not a broken store"
    assert "not valid TOML" in row.detail, "the reason is named, not merely 'unusable'"
    assert "inherits the CLI default" in row.detail and "remedy" in row.detail

    report = amplifier_memory.doctor(
        installed_sha=SHA_A, remote_sha=SHA_A, llm=_llm(tmp_path, "[llm.judge\n")
    )
    print(report.render())
    assert report.exit_code == 0, "cli.v2 Core 5: nonzero only on a FAILed check"


def test_the_llm_row_reports_which_provider_the_last_run_actually_used(
    store: Path, tmp_path: Path
) -> None:
    """Config says X, last run used Y - that is a stale timer, and it should be visible."""
    from datetime import UTC, datetime

    from amplifier_memory import suggest
    from amplifier_memory.doctor import llm_row

    suggest.append_log(
        suggest.SuggestReport(when=datetime.now(UTC), sessions=2, calls=2, provider="opus"), store
    )
    row = llm_row(_llm(tmp_path, '[llm.judge]\nprovider = "luna"\n'), home=store)
    print(row.render())
    assert "provider luna" in row.detail and "last run used provider=opus" in row.detail


def test_the_llm_row_never_mutates_the_store(store: Path, tmp_path: Path) -> None:
    """cli.v2 Core 5: doctor reads. Reading a config file outside the store is still reading."""
    _seed(store)
    before = _fingerprint(store)
    report = amplifier_memory.doctor(
        installed_sha=SHA_A,
        remote_sha=SHA_A,
        llm=_llm(tmp_path, '[llm.judge]\nprovider = "luna"\n'),
    )
    after = _fingerprint(store)
    row = next(r for r in report.rows if r.name == "llm judge")
    print(row.render())
    print("files whose sha256 changed:", [k for k in before if before.get(k) != after.get(k)])
    assert before == after
    assert set(after) == set(before)
