"""cli.v1 Core 1-9 — the `amplifier-memory` command itself.

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

# cli.v1 Core 1: these verbs and nothing else.
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


def test_upgrade_is_an_alias_of_update_and_is_not_listed(run, store: Path) -> None:
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


def test_service_and_suggest_are_honest_and_exit_0(run, store: Path) -> None:
    service = run("service", "install")
    suggest = run("suggest")
    assert service.exit_code == suggest.exit_code == 0
    assert "Phase 1 has no service; the suggest timer arrives with Phase 2." in service.output
    assert "Phase 2 not installed" in suggest.output
    bad = run("service", "frobnicate")
    print("unknown service verb exit:", bad.exit_code)
    assert bad.exit_code == 2, "an unknown service verb is a usage error"


def test_update_prints_the_plan_and_runs_only_doctor(run, store: Path) -> None:
    before = subprocess.run(
        ["git", "log", "--oneline"], cwd=store, capture_output=True, text=True, check=True
    ).stdout
    result = run("update")
    after = subprocess.run(
        ["git", "log", "--oneline"], cwd=store, capture_output=True, text=True, check=True
    ).stdout
    assert result.exit_code == 0
    assert "uv tool upgrade amplifier-memory" in result.output
    assert "runs step 4 only" in result.output
    assert "amplifier-memory doctor" in result.output, "doctor did not run"
    assert before == after, "update mutated the store"


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
    """cli.v1 Core 9: parse -> one library call -> print. A long body is carrying logic."""
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
    """cli.v1 Conformance: reachable by importing `amplifier_memory` alone."""
    home = tmp_path / "store"
    code = (
        "import sys, amplifier_memory as m;"
        f" m.init({str(home)!r});"
        f" m.status({str(home)!r});"
        f" m.review({str(home)!r});"
        f" m.doctor({str(home)!r}, installed_sha=None, remote_sha=None);"
        " m.service_status('install'); m.suggest_status(); m.update_plan();"
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
        env={**os.environ, "GIT_CONFIG_GLOBAL": str(gitconfig), "GIT_CONFIG_NOSYSTEM": "1"},
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
    assert cli_rows, "no cli.v1 row is CONFORMS; this test would pass vacuously"
    results = {fn.__name__: fn() for _, fn in kit.PROBES}
    for row_id, ref in cli_rows:
        probe = ref.rsplit("::", 1)[-1]
        assert probe in results, f"{row_id} names {probe}, which the cli kit does not define"
        assert results[probe][0] == "Kept", f"{row_id} claims CONFORMS but {probe} says {results[probe][0]}"
    print("cli.v1 CONFORMS rows checked against their own kit:", [row for row, _ in cli_rows])
