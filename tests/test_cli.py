"""cli.v2 Core 1-9 — the `amplifier-memory` command itself.

Two kinds of test live here. Most drive the click group in-process with `CliRunner`,
which is fast and exact about exit codes. A few shell out to the installed console
script, because "the entry point in pyproject.toml actually resolves" is a claim only
a subprocess can make (AGENTS.md rule 5's lesson: `amplifier run --once` shipped
without existing).

Core 9 — the thin-wrapper clause — is checked two ways that a wrapper carrying logic
would fail: `cli.py` is grepped for its imports, and every verb's behaviour is reached
in a subprocess with `click` absent from `sys.modules`.
"""

from __future__ import annotations

import os
import re
import subprocess
import sys
from collections.abc import Callable
from contextlib import AbstractContextManager
from pathlib import Path

import pytest
from click.testing import CliRunner

import amplifier_memory
from amplifier_memory.cli import main

REPO_ROOT = Path(__file__).resolve().parents[1]
CLI_SOURCE = REPO_ROOT / "src" / "amplifier_memory" / "cli.py"

# cli.v2 Core 1: these verbs and nothing else.
CONTRACT_VERBS = ["init", "status", "why", "review", "doctor", "service", "update", "suggest"]

Backdate = Callable[[float], AbstractContextManager[None]]


@pytest.fixture
def run() -> Callable[..., object]:
    runner = CliRunner()

    def invoke(*args: str):
        result = runner.invoke(main, list(args), catch_exceptions=False)
        print(f"$ amplifier-memory {' '.join(args)}   -> exit {result.exit_code}")
        print(result.output.rstrip() or "(no output)")
        return result

    return invoke


# --------------------------------------------------------------- Core 1: the verb surface


def test_help_lists_exactly_the_contract_verbs(run) -> None:
    result = run("--help")
    section = result.output.split("Commands:", 1)[1]
    listed = [line.split()[0] for line in section.splitlines() if line.startswith("  ")]
    print("verbs listed by --help:", listed)
    assert sorted(listed) == sorted(CONTRACT_VERBS), listed
    assert result.exit_code == 0


def test_an_unknown_verb_is_one_line_and_exit_2(run) -> None:
    result = run("bogus")
    lines = [line for line in result.output.strip().splitlines() if line.strip()]
    print("lines of output:", len(lines))
    assert result.exit_code == 2
    assert len(lines) == 1, lines
    assert lines[0] == "error: unknown verb 'bogus'; try `amplifier-memory --help`"


def test_upgrade_is_an_alias_of_update_and_is_not_listed(
    run, store: Path, no_shelling_out
) -> None:
    listed = run("--help").output
    assert "upgrade" not in listed, "the alias is listed; --help must show exactly the 8 verbs"
    alias = run("upgrade")
    update = run("update")
    assert alias.output == update.output, "upgrade is not the same command as update"
    assert alias.exit_code == update.exit_code == 0


# --------------------------------------------------------------- Core 8: init


def test_init_creates_the_store_then_says_it_exists(run, memory_home: Path) -> None:
    first = run("init")
    log_after_first = subprocess.run(
        ["git", "log", "--oneline"], cwd=memory_home, capture_output=True, text=True, check=True
    ).stdout.strip()
    second = run("init")
    log_after_second = subprocess.run(
        ["git", "log", "--oneline"], cwd=memory_home, capture_output=True, text=True, check=True
    ).stdout.strip()

    print("git log --oneline after first init: ", log_after_first)
    print("git log --oneline after second init:", log_after_second)

    assert first.exit_code == second.exit_code == 0
    assert "created" in first.output
    assert "already exists" in second.output and "nothing changed" in second.output
    assert log_after_first == log_after_second
    assert len(log_after_second.splitlines()) == 1


# --------------------------------------------------------------- Core 2: status


def test_status_prints_the_screen(run, store: Path, backdate: Backdate) -> None:
    from tests.test_status import build_fixture

    build_fixture(store, backdate)
    result = run("status")
    assert result.exit_code == 0
    assert result.output.rstrip() == amplifier_memory.status().render()


# --------------------------------------------------------------- Core 3: why


def test_why_prints_the_commit_fields_and_an_unknown_id_is_one_line(run, store: Path) -> None:
    amplifier_memory.save(
        "never use tabs in YAML files",
        "never use tabs in YAML files; always two-space indentation, please",
        "assistant",
        "sess-abc",
        ["never use tabs in YAML files; always two-space indentation, please"],
    )
    known = run("why", "m-001")
    assert known.exit_code == 0
    for needle in ("never use tabs in YAML files", "sess-abc", "assistant", "quote:", "save"):
        assert needle in known.output, f"why does not print {needle!r}"
    assert re.search(r"\d{4}-\d{2}-\d{2}", known.output), "why does not print a date"

    amplifier_memory.forget("m-001", store, session_id="sess-abc")
    after_forget = run("why", "m-001")
    assert after_forget.output.count("commit:") == 2, "the forget commit is missing"

    unknown = run("why", "m-999")
    lines = [line for line in unknown.output.strip().splitlines() if line.strip()]
    assert unknown.exit_code == 1
    assert len(lines) == 1 and lines[0].startswith("error: unknown memory id 'm-999'")


# --------------------------------------------------------------- Core 4, 6, 7, 1: the rest


def test_review_with_an_empty_inbox_says_so_and_exits_0(run, store: Path) -> None:
    result = run("review")
    assert result.exit_code == 0
    assert "empty" in result.output.lower()


def test_service_and_suggest_are_honest_and_exit_0(
    run, store: Path, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """cli.v2 Core 6 / suggestions.v1 Core 10: both verbs report and exit 0.

    Two injections, both by environment because the verbs take no arguments (they are
    thin wrappers): the unit directory and the session substrate are pointed at empty
    temp directories. Without them this test installed a real timer on this device and
    would have spent real model calls on the steward's own recorded sessions.
    """
    monkeypatch.setenv("AMPLIFIER_MEMORY_UNIT_DIR", str(tmp_path / "units"))
    monkeypatch.setenv("AMPLIFIER_CONTEXT_INTELLIGENCE_BASE_PATH", str(tmp_path / "no-substrate"))
    service = run("service", "status")
    suggest = run("suggest")
    print(service.output)
    print(suggest.output)
    assert service.exit_code == suggest.exit_code == 0
    assert "installed:    not installed" in service.output
    assert "status=degraded:substrate missing" in suggest.output, (
        "a missing substrate is Core 10's fail-open path: report it and exit 0"
    )
    assert not (store / "inbox.md").read_text(encoding="utf-8"), "a degraded run wrote to the inbox"
    bad = run("service", "frobnicate")
    print("unknown service verb exit:", bad.exit_code)
    assert bad.exit_code == 2, "an unknown service verb is a usage error"


def test_update_runs_its_steps_and_ends_in_doctor(run, store: Path, no_shelling_out) -> None:
    """cli.v2 Core 7. The steps are real argv; `no_shelling_out` records instead of running."""
    before = subprocess.run(
        ["git", "log", "--oneline"], cwd=store, capture_output=True, text=True, check=True
    ).stdout
    result = run("update")
    after = subprocess.run(
        ["git", "log", "--oneline"], cwd=store, capture_output=True, text=True, check=True
    ).stdout
    assert result.exit_code == 0
    assert "uv tool upgrade amplifier-memory" in result.output
    assert "keep the old module code until they restart" in result.output
    assert "amplifier-memory doctor" in result.output, "doctor did not run"
    assert before == after, "update mutated the store"
    assert no_shelling_out[0] == amplifier_memory.UPGRADE_CLI_ARGV, no_shelling_out
    # The verb takes no injection (it is a thin wrapper), so WHICH argv follow the
    # upgrade depend on what this device has installed: a cache clone -> git
    # fetch/reset; no clone -> the `bundle remove`/`add` install path; an amplifier
    # venv -> uv pip install. Each branch is pinned exactly, against a fake device, in
    # `tests/test_update.py` and `conformance/cli/run.py`.
    recorded = [" ".join(argv) for argv in no_shelling_out]
    print("\n".join(recorded))
    assert any("fetch origin" in line for line in recorded) or (
        amplifier_memory.BUNDLE_ADD_ARGV in no_shelling_out
    ), recorded
    assert any("uv pip install" in line for line in recorded) or (
        "no amplifier environment found" in result.output
    ), recorded

    # cli.v2 Core 7, "one run is enough": the hand-off's own flag. It is hidden (a
    # steward never types it), and it makes the verb skip the uv-tool step, because the
    # process that re-executed this one already ran it.
    help_text = run("update", "--help").output
    assert "--after-upgrade" not in help_text, help_text
    mark = len(no_shelling_out)
    handed = run("update", "--after-upgrade")
    assert handed.exit_code == 0
    assert "skipped \u2014 already upgraded by the previous process" in handed.output
    after = [" ".join(argv) for argv in no_shelling_out[mark:]]
    print("\n".join(after))
    assert amplifier_memory.UPGRADE_CLI_ARGV not in no_shelling_out[mark:], after


def test_doctor_exits_nonzero_when_the_store_is_missing(run, memory_home: Path) -> None:
    result = run("doctor")
    assert result.exit_code == 1
    assert "FAIL" in result.output and "amplifier-memory init" in result.output


# --------------------------------------------------------------- Core 9: the thin wrapper


def test_cli_imports_only_click_and_the_library() -> None:
    """The grep the acceptance criteria names, run as an assertion."""
    imports = [
        line
        for line in CLI_SOURCE.read_text(encoding="utf-8").splitlines()
        if line.startswith(("import ", "from "))
    ]
    print("imports in cli.py:")
    for line in imports:
        print("   ", line)
    assert imports == ["import click", "import amplifier_memory"], imports


def test_every_command_body_is_short(run) -> None:
    """cli.v2 Core 9: parse -> one library call -> print. A long body is carrying logic."""
    source = CLI_SOURCE.read_text(encoding="utf-8").splitlines()
    bodies: dict[str, int] = {}
    current: str | None = None
    for line in source:
        match = re.match(r"^def (\w+)\(", line)
        if match:
            current = match.group(1)
            bodies[current] = 0
        elif current and line.startswith(("    ", "\t")):
            if line.strip() and not line.strip().startswith(("#", '"""')):
                bodies[current] += 1
        elif line.strip() and not line.startswith(" "):
            current = None
    print("statement lines per command body:", bodies)
    for name, length in bodies.items():
        assert length <= 10, f"{name} carries {length} lines; a wrapper that carries logic is a defect"


def test_every_verbs_behaviour_is_reachable_without_click(tmp_path: Path) -> None:
    """cli.v2 Conformance: reachable by importing `amplifier_memory` alone."""
    home = tmp_path / "store"
    code = (
        "import sys, amplifier_memory as m;"
        f" m.init({str(home)!r});"
        f" m.status({str(home)!r});"
        f" m.review({str(home)!r});"
        f" m.doctor({str(home)!r}, installed_sha=None, remote_sha=None);"
        " m.service_status('status', runner=lambda argv: (0, ''),"
        f" config_dir={str(tmp_path / 'units')!r}, home={str(home)!r});"
        f" m.suggest_status({str(home)!r}); m.update_plan();"
        " m.update_check('a'*40, 'b'*40);"
        " print('click' in sys.modules, [x for x in sys.modules if x.startswith('click')])"
    )
    gitconfig = tmp_path / "gitconfig"
    gitconfig.write_text("[user]\n\tname = T\n\temail = t@example.invalid\n", encoding="utf-8")
    proc = subprocess.run(
        [sys.executable, "-c", code],
        capture_output=True,
        text=True,
        check=True,
        cwd=tmp_path,
        env={
            **os.environ,
            "GIT_CONFIG_GLOBAL": str(gitconfig),
            "GIT_CONFIG_NOSYSTEM": "1",
            # Both Phase 2 verbs reach the device: `service` writes unit files and
            # `suggest` would read this machine's real recorded sessions. Point them at
            # temp directories, and inject the runner rather than shelling out.
            "AMPLIFIER_MEMORY_UNIT_DIR": str(tmp_path / "units"),
            "AMPLIFIER_CONTEXT_INTELLIGENCE_BASE_PATH": str(tmp_path / "no-substrate"),
        },
    )
    print("every verb's library call ran; click in sys.modules ->", proc.stdout.strip())
    assert proc.stdout.strip().startswith("False")


# --------------------------------------------------------------- the console script is real


def test_the_console_script_resolves_and_runs(tmp_path: Path) -> None:
    """AGENTS.md rule 5: the entry point is asserted by running it, not by reading pyproject."""
    home = tmp_path / "store"
    gitconfig = tmp_path / "gitconfig"
    gitconfig.write_text("[user]\n\tname = T\n\temail = t@example.invalid\n", encoding="utf-8")
    env = {
        **os.environ,
        "AMPLIFIER_MEMORY_HOME": str(home),
        "GIT_CONFIG_GLOBAL": str(gitconfig),
        "GIT_CONFIG_NOSYSTEM": "1",
    }
    for args, expected in [(["--help"], 0), (["init"], 0), (["status"], 0), (["bogus"], 2)]:
        proc = subprocess.run(
            ["uv", "run", "amplifier-memory", *args],
            capture_output=True,
            text=True,
            check=False,
            cwd=REPO_ROOT,
            env=env,
        )
        print(f"$ amplifier-memory {' '.join(args)} -> exit {proc.returncode}")
        print((proc.stdout + proc.stderr).rstrip())
        assert proc.returncode == expected, proc.stderr


# --------------------------------------------------------------- the cli conformance kit and its ledger rows


def test_cli_conformance_kit_runs_green_and_covers_every_core_clause() -> None:
    proc = subprocess.run(
        [sys.executable, str(REPO_ROOT / "conformance" / "cli" / "run.py")],
        capture_output=True,
        text=True,
        check=False,
        cwd=REPO_ROOT,
    )
    print(proc.stdout)
    assert proc.returncode == 0, proc.stderr
    lines = [line for line in proc.stdout.splitlines() if line.startswith("Core ")]
    assert len(lines) == 9
    for index, line in enumerate(lines, start=1):
        assert line.startswith(f"Core {index} \u2014 ")
        assert line.split(" \u2014 ")[1] in {"Kept", "Not yet", "Broken", "Can't check"}


def test_cli_ledger_rows_marked_conforms_name_a_cli_probe_that_passes() -> None:
    """A row is CONFORMS only where the probe it names says Kept — checked per kit.

    `tests/test_store.py`'s equivalent matches probes by bare function name, which cannot
    tell `conformance/store/run.py::probe_core_1` from `conformance/cli/run.py::probe_core_1`.
    This one keys on the full ref, so a cli row can never be validated by a store probe.
    """
    from conformance.cli import run as kit

    rows_text = (REPO_ROOT / "ledger" / "rows.yaml").read_text(encoding="utf-8")
    conforming: list[tuple[str, str]] = []
    current_id = disposition = ""
    for line in rows_text.splitlines():
        if line.startswith("- id: "):
            current_id, disposition = line.split("- id: ")[1].strip(), ""
        elif line.strip().startswith("disposition:"):
            disposition = line.split("disposition:")[1].strip()
        elif line.strip().startswith("ref:") and disposition == "CONFORMS":
            conforming.append((current_id, line.split("ref:")[1].strip()))

    cli_rows = [(row, ref) for row, ref in conforming if ref.startswith("conformance/cli/run.py::")]
    assert cli_rows, "no cli.v2 row is CONFORMS; this test would pass vacuously"
    results = {fn.__name__: fn() for _, fn in kit.PROBES}
    for row_id, ref in cli_rows:
        probe = ref.rsplit("::", 1)[-1]
        assert probe in results, f"{row_id} names {probe}, which the cli kit does not define"
        assert results[probe][0] == "Kept", f"{row_id} claims CONFORMS but {probe} says {results[probe][0]}"
    print("cli.v2 CONFORMS rows checked against their own kit:", [row for row, _ in cli_rows])


# ------------------------------------------- Core 5: `doctor --repair`, the one write


def test_doctor_repair_prints_the_diff_then_what_it_did(run, store: Path) -> None:
    """The only sanctioned repair. Without the flag `doctor` still writes nothing.

    Deviation on record: cli.v2 Core 5 says "`doctor` never mutates". The verb still
    does not — `amplifier-memory doctor` writes nothing at all — but `--repair` is an
    explicit, printed, opt-in write, and the clause's sentence does not carve it out.
    Evidence for the change: the steward's store had to be repaired by hand with bash
    on 2026-09-06 because no command could do it (VISION principle 4).
    """
    amplifier_memory.save("keep me", "keep me", "human", "s-1", ["keep me"])
    path = store / "MEMORY.md"
    fragment = " and this fragment has no id, which is how the store was found"
    path.write_text(path.read_text(encoding="utf-8") + fragment + "\n", encoding="utf-8")
    subprocess.run(["git", "add", "MEMORY.md"], cwd=store, check=True)
    subprocess.run(["git", "commit", "-m", "hand edit: clobbered"], cwd=store, check=True,
                   capture_output=True)

    before = run("doctor")
    assert before.exit_code == 1, "a malformed MEMORY.md did not fail the check"
    assert "not well-formed" in before.output and "doctor --repair" in before.output

    repaired = run("doctor", "--repair")
    assert repaired.exit_code == 0, repaired.output
    assert "restoring MEMORY.md from" in repaired.output
    assert f"-{fragment}" in repaired.output, "the diff was not printed before the summary"
    assert repaired.output.index("restoring") < repaired.output.index("committed")

    after = run("doctor")
    assert after.exit_code == 0, after.output
    assert fragment not in path.read_text(encoding="utf-8")


def test_doctor_repair_on_a_healthy_store_is_a_no_op_that_says_so(run, store: Path) -> None:
    amplifier_memory.save("keep me", "keep me", "human", "s-1", ["keep me"])
    head = subprocess.run(["git", "rev-parse", "HEAD"], cwd=store, capture_output=True,
                          text=True, check=True).stdout.strip()
    result = run("doctor", "--repair")
    after = subprocess.run(["git", "rev-parse", "HEAD"], cwd=store, capture_output=True,
                           text=True, check=True).stdout.strip()
    assert result.exit_code == 0
    assert "nothing to repair" in result.output
    assert after == head, "a no-op repair made a commit"


# --------------------------------------------------- cli.v2 §3: `why` shows a memory's life


def test_why_shows_the_creation_each_edit_as_was_now_and_a_forget_marked_forgot(
    run, store: Path
) -> None:
    """cli.v2 §3: three moments, three shapes — and a removal is never read as a creation."""
    quote = "never use tabs in YAML files; always two-space indentation, please"
    amplifier_memory.save("never use tabs in YAML files", quote, "assistant", "sess-abc", [quote])
    amplifier_memory.edit("m-001", "never use tabs in YAML", quote, "assistant", "sess-abc", [quote])
    amplifier_memory.forget("m-001", store, session_id="sess-abc")

    result = run("why", "m-001")
    print(result.output)
    lines = result.output.splitlines()
    headings = [line.split()[0] for line in lines if line and not line.startswith(" ")]

    assert result.exit_code == 0
    assert headings == ["save", "edit", "forgot"], headings
    was_now = next(line for line in lines if line.strip().startswith("was:"))
    assert '"never use tabs in YAML files"' in was_now, was_now
    assert "now: never use tabs in YAML" in was_now, was_now
    assert result.output.count("commit:") == 3, "why does not show all three commits"
    for needle in ("sess-abc", "assistant", "quote:"):
        assert needle in result.output, f"why does not print {needle!r}"
    assert re.search(r"\d{4}-\d{2}-\d{2}", result.output), "why does not print a date"


def test_doctor_prints_its_own_wellformed_row(run, store: Path) -> None:
    """cli.v2 §5: the row is its own line, and it is the one that FAILs on damage."""
    amplifier_memory.save("never use tabs", "never use tabs", "human", "s-1", ["never use tabs"])
    healthy = run("doctor")
    print(healthy.output)
    row = next(line for line in healthy.output.splitlines() if "MEMORY.md well-formed" in line)
    assert row.strip().startswith("[OK"), row

    path = store / "MEMORY.md"
    path.write_bytes(path.read_bytes() + b"two-space indentation\n")
    damaged = run("doctor")
    print(damaged.output)
    broken_row = next(line for line in damaged.output.splitlines() if "MEMORY.md well-formed" in line)
    store_row = next(line for line in damaged.output.splitlines() if "] store " in line)

    assert broken_row.strip().startswith("[FAIL"), broken_row
    assert "line 2" in broken_row and "doctor --repair" in broken_row, broken_row
    assert store_row.strip().startswith("[OK"), store_row
    assert damaged.exit_code == 1
