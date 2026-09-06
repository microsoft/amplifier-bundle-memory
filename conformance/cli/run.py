#!/usr/bin/env python3
"""cli.v1 conformance kit — one line per Core clause, against a fresh temp store.

Run it:  ``uv run python conformance/cli/run.py``

Each probe builds its own throwaway store, drives the real click group, and returns
one of the ledger's plain words: **Kept · Not yet · Broken · Can't check**. A probe
that cannot fail is not a probe: every Kept below rests on an assertion a regression
would trip. Exit code is 0 unless a clause reads Broken.

Two clauses honestly read **Not yet**, and say why in their own evidence: Core 6
(`service`) — Phase 1 renders no units, so the install/rollback half of the clause is
unbuilt — and Core 7 (`update`) — this build prints the plan and runs only `doctor`;
the upgrade path itself is the install lane's work.

No probe here touches the network: the update check's two shas are injected.
"""

from __future__ import annotations

import os
import sys
import tempfile
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from datetime import UTC, datetime, timedelta
from pathlib import Path

if __package__ in (None, ""):  # allow `python conformance/cli/run.py`
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from click.testing import CliRunner

import amplifier_memory
from amplifier_memory import _git
from amplifier_memory.cli import main

Verdict = tuple[str, str]

CONTRACT_VERBS = ["init", "status", "why", "review", "doctor", "service", "update", "suggest"]
HUMAN_IDENTITY = ("Test Human", "human@example.invalid")
SHA_A, SHA_B = "a" * 40, "b" * 40


@contextmanager
def fresh_store(*, init: bool = True) -> Iterator[Path]:
    """A brand-new store in a temp dir, with git's global/system config isolated."""
    with tempfile.TemporaryDirectory(prefix="cli-v1-conformance-") as tmp:
        root = Path(tmp)
        gitconfig = root / "gitconfig"
        gitconfig.write_text(
            f"[user]\n\tname = {HUMAN_IDENTITY[0]}\n\temail = {HUMAN_IDENTITY[1]}\n",
            encoding="utf-8",
        )
        os.environ["GIT_CONFIG_GLOBAL"] = str(gitconfig)
        os.environ["GIT_CONFIG_NOSYSTEM"] = "1"
        home = root / "memory"
        os.environ["AMPLIFIER_MEMORY_HOME"] = str(home)
        if init:
            amplifier_memory.init(home)
        yield home


@contextmanager
def at(days_ago: float) -> Iterator[None]:
    """Commits made inside the block carry a backdated git date."""
    when = (datetime.now(UTC) - timedelta(days=days_ago)).isoformat()
    saved = {k: os.environ.get(k) for k in ("GIT_AUTHOR_DATE", "GIT_COMMITTER_DATE")}
    os.environ["GIT_AUTHOR_DATE"] = os.environ["GIT_COMMITTER_DATE"] = when
    try:
        yield
    finally:
        for key, value in saved.items():
            os.environ.pop(key, None) if value is None else os.environ.__setitem__(key, value)


def run(*args: str):
    return CliRunner().invoke(main, list(args), catch_exceptions=False)


def _save(text: str, home: Path, **kw: object):
    return amplifier_memory.save(text, text, "human", "sess-kit", [text], home=home, **kw)


def _fingerprint(home: Path) -> dict[str, str]:
    import hashlib

    return {
        str(p.relative_to(home)): hashlib.sha256(p.read_bytes()).hexdigest()
        for p in sorted(home.rglob("*"))
        if p.is_file()
    }


# --------------------------------------------------------------------------- probes


def probe_core_1() -> Verdict:
    """Verbs: exactly the eight; unknown verb is a one-line error, exit 2; upgrade aliases update."""
    with fresh_store():
        listed = [
            line.split()[0]
            for line in run("--help").output.split("Commands:", 1)[1].splitlines()
            if line.startswith("  ")
        ]
        assert sorted(listed) == sorted(CONTRACT_VERBS), listed
        bogus = run("bogus")
        lines = [line for line in bogus.output.strip().splitlines() if line.strip()]
        assert bogus.exit_code == 2, f"unknown verb exited {bogus.exit_code}, wanted 2"
        assert len(lines) == 1, f"unknown verb printed {len(lines)} lines: {lines}"
        assert run("upgrade").output == run("update").output, "upgrade is not an alias of update"
        assert "upgrade" not in run("--help").output, "the alias is listed among the verbs"
    return "Kept", (
        f"--help lists exactly {sorted(listed)}; `bogus` -> one line, exit 2; "
        "`upgrade` is a hidden alias of `update`"
    )


def probe_core_2() -> Verdict:
    """status: the VISION principle 9 numbers, from git and usage.jsonl, matching a built history."""
    with fresh_store() as home:
        with at(40):
            _save("forty days old", home)
        with at(8):
            _save("eight days old", home)
        with at(2):
            _save("two days old", home)
        with at(3):
            amplifier_memory.forget("m-001", home, session_id="sess-kit")
        report = amplifier_memory.status(home)
        assert (report.memories, report.written_7, report.written_30) == (2, 1, 2), report
        assert (report.forgotten_7, report.forgotten_30) == (1, 1), report
        assert report.kept == 1, f"kept={report.kept}: m-002 (8d, present) alone qualifies"
        result = run("status")
        assert result.exit_code == 0 and result.output.rstrip() == report.render()
    return "Kept", (
        f"against a built history: memories={report.memories} written={report.written_7}/7d "
        f"{report.written_30}/30d forgotten={report.forgotten_7}/7d kept={report.kept}; "
        "the CLI prints exactly StatusReport.render()"
    )


def probe_core_3() -> Verdict:
    """why <id>: text, verbatim quote, session, writer, date — creation and forget."""
    with fresh_store() as home:
        quote = "never use tabs in YAML files; always two-space indentation"
        amplifier_memory.save(
            "never use tabs in YAML files", quote, "assistant", "sess-abc", [quote], home=home
        )
        amplifier_memory.forget("m-001", home, session_id="sess-abc")
        out = run("why", "m-001").output
        for needle in ("never use tabs in YAML files", quote, "sess-abc", "assistant", "save", "forget"):
            assert needle in out, f"why does not print {needle!r}"
        assert out.count("commit:") == 2, "why does not show both the save and the forget"
        unknown = run("why", "m-999")
        lines = [line for line in unknown.output.strip().splitlines() if line.strip()]
        assert unknown.exit_code != 0 and len(lines) == 1, (unknown.exit_code, lines)
    return "Kept", (
        "why m-001 prints text/quote/session/writer/date for both the save and the forget "
        f"commit; an unknown id is one line, exit {unknown.exit_code}"
    )


def probe_core_4() -> Verdict:
    """review: an empty inbox says so and exits 0."""
    with fresh_store():
        result = run("review")
        assert result.exit_code == 0, result.exit_code
        assert "empty" in result.output.lower(), result.output
    return "Kept", f"empty inbox -> {result.output.splitlines()[0]!r}, exit 0"


def probe_core_5() -> Verdict:
    """doctor: every row the clause names, never mutates, update trio, exit nonzero only on FAIL."""
    with fresh_store() as home:
        _save("never use tabs", home)
        _save("two spaces", home, topic="yaml-style", topic_purpose="YAML style.")
        before = _fingerprint(home)
        report = amplifier_memory.doctor(home, installed_sha=SHA_A, remote_sha=SHA_A)
        after = _fingerprint(home)
        assert before == after, (
            f"doctor mutated {[k for k in before if before.get(k) != after.get(k)]}"
        )
        names = [row.name for row in report.rows]
        assert names == [
            "store", "caps", "stale topics", "inbox", "suggest timer", "substrate", "update"
        ], names
        assert report.exit_code == 0
        trio = [
            amplifier_memory.update_check(SHA_A, SHA_B).level,
            amplifier_memory.update_check(SHA_A, SHA_A).level,
            amplifier_memory.update_check(SHA_A, None).level,
        ]
        assert trio == ["WARN", "OK", "INFO"], trio
        assert "amplifier-memory update" in amplifier_memory.update_check(SHA_A, SHA_B).detail
    with fresh_store(init=False) as empty:
        missing = amplifier_memory.doctor(empty, installed_sha=SHA_A, remote_sha=SHA_A)
        assert missing.exit_code == 1, "a missing store did not fail the check"
        behind = amplifier_memory.doctor(empty, installed_sha=SHA_A, remote_sha=SHA_B)
        assert behind.exit_code == 1 and behind.rows[0].level == "FAIL"
    return "Kept", (
        f"{len(before)} files byte-identical before/after; rows {names}; update trio "
        f"{trio} (behind names the remedy); exit 1 only when the store check fails"
    )


def probe_core_6() -> Verdict:
    """service: Phase 1 has no service, and the verb says so."""
    with fresh_store():
        result = run("service", "install")
        assert result.exit_code == 0
        assert "Phase 1 has no service" in result.output, result.output
        for verb in amplifier_memory.SERVICE_VERBS:
            assert run("service", verb).exit_code == 0
    return "Not yet", (
        "the clause's Phase 1 sentence is met — every one of "
        f"{list(amplifier_memory.SERVICE_VERBS)} reports plainly that Phase 1 has no service and "
        "exits 0 — but the clause's substance (render units, daemon-reload -> enable --now, roll "
        "back written units on a failed step) is unbuilt: it manages the Phase 2 suggest timer, "
        "and suggestions.v1 is still DRAFT"
    )


def probe_core_7() -> Verdict:
    """update: the real upgrade path is not built here."""
    with fresh_store() as home:
        before = _git.log_records(home)
        result = run("update")
        after = _git.log_records(home)
        assert result.exit_code == 0
        assert "uv tool upgrade amplifier-memory" in result.output
        assert "keep the old module code until they restart" in result.output
        assert "amplifier-memory doctor" in result.output, "update did not end by running doctor"
        assert len(before) == len(after), "update mutated the store"
    return "Not yet", (
        "`update` prints the four steps it will take (uv tool upgrade, app-bundle refresh, "
        "timer restart, doctor) and the stale-in-memory note, then runs step 4 only. Steps 1-3 "
        "are unbuilt — the upgrade path is the install lane's work (AMM-026, item 16w)"
    )


def probe_core_8() -> Verdict:
    """init: creates the store; a second run reports it exists and changes nothing."""
    with fresh_store(init=False) as home:
        first = run("init")
        log_one = _git.git(["log", "--oneline"], cwd=home).stdout.strip()
        second = run("init")
        log_two = _git.git(["log", "--oneline"], cwd=home).stdout.strip()
        assert first.exit_code == second.exit_code == 0
        assert "created" in first.output and "already exists" in second.output
        assert log_one == log_two, f"the second init changed the history: {log_one} -> {log_two}"
        assert len(log_two.splitlines()) == 1, log_two
        on_disk = sorted(p.name for p in home.iterdir() if p.name != ".git")
        assert on_disk == ["MEMORY.md", "declined.md", "inbox.md", "topics", "usage.jsonl"], on_disk
    return "Kept", (
        f"first init created {on_disk} in one commit ({log_one}); the second changed nothing "
        "and said so"
    )


def probe_core_9() -> Verdict:
    """Thin wrapper: cli.py imports only click and amplifier_memory; every verb is a library call."""
    import subprocess

    source = (Path(__file__).resolve().parents[2] / "src" / "amplifier_memory" / "cli.py").read_text(
        encoding="utf-8"
    )
    imports = [line for line in source.splitlines() if line.startswith(("import ", "from "))]
    assert imports == ["import click", "import amplifier_memory"], imports

    with fresh_store(init=False) as home:
        code = (
            "import sys, amplifier_memory as m;"
            f" m.init({str(home)!r}); m.status({str(home)!r}); m.review({str(home)!r});"
            f" m.doctor({str(home)!r}, installed_sha=None, remote_sha=None);"
            " m.service_status('install'); m.suggest_status(); m.update_plan();"
            " m.update_check('a'*40,'b'*40);"
            " print([x for x in sys.modules if x.startswith('click')])"
        )
        proc = subprocess.run(
            [sys.executable, "-c", code], capture_output=True, text=True, check=True, cwd=home.parent
        )
        assert proc.stdout.strip() == "[]", f"click leaked into the library path: {proc.stdout}"
    return "Kept", (
        f"cli.py imports exactly {imports}; every verb's behaviour ran in a subprocess with "
        "click absent from sys.modules"
    )


PROBES: list[tuple[int, Callable[[], Verdict]]] = [
    (1, probe_core_1),
    (2, probe_core_2),
    (3, probe_core_3),
    (4, probe_core_4),
    (5, probe_core_5),
    (6, probe_core_6),
    (7, probe_core_7),
    (8, probe_core_8),
    (9, probe_core_9),
]


def main_() -> int:
    broken = 0
    for clause, probe in PROBES:
        try:
            verdict, evidence = probe()
        except Exception as exc:  # noqa: BLE001 - a probe that raises is Broken, never a silent pass
            verdict, evidence = "Broken", f"{type(exc).__name__}: {exc}".replace("\n", " ")[:300]
        if verdict == "Broken":
            broken += 1
        print(f"Core {clause} \u2014 {verdict} \u2014 {evidence}")
    return 1 if broken else 0


if __name__ == "__main__":
    raise SystemExit(main_())
