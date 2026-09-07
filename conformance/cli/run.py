#!/usr/bin/env python3
"""cli.v2 conformance kit — one line per Core clause, against a fresh temp store.

Run it:  ``uv run python conformance/cli/run.py``

Each probe builds its own throwaway store, drives the real click group, and returns
one of the ledger's plain words: **Kept · Not yet · Broken · Can't check**. A probe
that cannot fail is not a probe: every Kept below rests on an assertion a regression
would trip. Exit code is 0 unless a clause reads Broken.

Every clause reads **Kept**. Core 6 (`service`) reached Kept with Phase 2: the units are
rendered, enabled and rolled back against a temp unit directory with a fake runner.

No probe here touches the network or this machine: the update check's shas are injected,
and Core 7 runs `update`'s real steps against a **fake device** — a temp `~/.amplifier`
whose cache clones point at a temp "remote" on local disk, and a temp venv carrying a
`direct_url.json`. The git half really runs there (a local origin needs no network); the
`uv` and `amplifier` halves are stood in for, because invoking them for real would
upgrade the machine running the kit.
"""

from __future__ import annotations

import io
import os
import re
import shutil
import sys
import tempfile
from collections.abc import Callable, Iterator
from contextlib import contextmanager, redirect_stdout
from datetime import UTC, datetime, timedelta
from pathlib import Path

if __package__ in (None, ""):  # allow `python conformance/cli/run.py`
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from click.testing import CliRunner

import amplifier_memory
from amplifier_memory import _git
from amplifier_memory.cli import main
from amplifier_memory.doctor import (
    bundle_cache_dirs,
    cache_dir_name,
    commit_of_cache,
    commit_of_env_library,
)

Verdict = tuple[str, str]

#: Every unit name a surface can print. cli.v3 §6/§8: a name a surface prints as the
#: timer that serves an instance must be a file in the unit directory at that moment —
#: `init` printed `amplifier-memory-suggest-amplifier-memory-c0195169.timer` on the
#: steward's device on 2026-09-07 while only the pre-v3 pair existed (item `…-5wc`).
UNIT_NAME = re.compile(r"amplifier-memory-suggest[A-Za-z0-9._-]*\.(?:timer|service)")

CONTRACT_VERBS = ["init", "status", "why", "review", "doctor", "service", "update", "suggest"]
HUMAN_IDENTITY = ("Test Human", "human@example.invalid")
SHA_A, SHA_B = "a" * 40, "b" * 40


@contextmanager
def fresh_store(*, init: bool = True) -> Iterator[Path]:
    """A brand-new store in a temp dir, with git's global/system config isolated."""
    with tempfile.TemporaryDirectory(prefix="cli-v2-conformance-") as tmp:
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
            # timer=False, explicitly: a fixture must never reach the install plane at
            # all. The probes that DO install inject `runner=`/`config_dir=` themselves.
            amplifier_memory.init(home, timer=False)
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


class FakeDevice:
    """The three installed things, in temp dirs, with a local-disk "remote".

    `origin` carries two commits; the cache clones (`cache/` and `cache/skills/`) and the
    venv's `direct_url.json` are parked on the older one — the shape the steward's device
    was found in on 2026-09-06, after four merged waves were reported installed.
    """

    def __init__(self, root: Path, *, clones: int = 2, venv: bool = True) -> None:
        self.root = root
        self.origin = root / "origin"
        self.origin.mkdir(parents=True)
        _sh(["git", "init", "-b", "main"], self.origin)
        (self.origin / "bundle.md").write_text("v1\n", encoding="utf-8")
        _sh(["git", "add", "."], self.origin)
        _commit("the commit the device is stuck on", self.origin)
        self.old = _sh(["git", "rev-parse", "HEAD"], self.origin)
        (self.origin / "bundle.md").write_text("v2\n", encoding="utf-8")
        _sh(["git", "add", "."], self.origin)
        _commit("the commit main is at", self.origin)
        self.new = _sh(["git", "rev-parse", "HEAD"], self.origin)

        self.uri = f"git+file://{self.origin}@main#subdirectory=behaviors/memory-session.yaml"
        self.home = root / "amplifier"
        for parent in [self.home / "cache", self.home / "cache" / "skills"][:clones]:
            parent.mkdir(parents=True)
            clone = parent / cache_dir_name(self.uri)
            _sh(["git", "clone", str(self.origin), str(clone)], self.root)
            _sh(["git", "reset", "--hard", self.old], clone)

        self.python: Path | None = None
        if venv:
            self.python = root / "venv" / "bin" / "python"
            self.python.parent.mkdir(parents=True)
            self.python.write_text("#!/bin/sh\n", encoding="utf-8")
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
        import json

        (self.dist / "direct_url.json").write_text(
            json.dumps({"url": str(self.origin), "vcs_info": {"vcs": "git", "commit_id": commit}}),
            encoding="utf-8",
        )

    def runner(self, calls: list[tuple[str, ...]]):
        """git runs for real against the local origin; uv and amplifier are stood in for.

        git is run here with `subprocess` rather than through the library's own default
        runner, because a suite that imports this kit may have replaced that runner with
        a recorder - and a probe that silently records the refresh instead of performing
        it would assert nothing at all.
        """
        import subprocess

        def run(argv) -> tuple[int, str]:
            argv = tuple(argv)
            calls.append(argv)
            if argv[0] == "git":
                proc = subprocess.run(list(argv), capture_output=True, text=True, check=False)
                return proc.returncode, (proc.stdout + proc.stderr).strip()
            if argv[:3] == ("uv", "pip", "install"):
                self._write_env_commit(self.new)
                return (
                    0,
                    f"- amplifier-memory ({self.old[:7]})\n+ amplifier-memory ({self.new[:7]})",
                )
            return 0, f"stood in for: {' '.join(argv)}"

        return run

    def clones(self) -> list[Path]:
        return bundle_cache_dirs(self.uri, self.home)


def _scripted(*values: str | None) -> Callable[[], str | None]:
    """A stand-in for `doctor.installed_commit()` answering a fixed sequence.

    The last value repeats, so `(old, new)` is "step 1 upgraded this install" and a
    single value is "nothing moved" — no counting of readings in the probe.
    """
    remaining = iter(values)

    def read() -> str | None:
        return next(remaining, values[-1])

    return read


def _never_execv(path, argv):  # a trap: never called
    raise AssertionError(f"re-executed when it must not: {path} {list(argv)}")


def _sh(argv: list[str], cwd: Path) -> str:
    import subprocess

    return subprocess.run(argv, cwd=cwd, capture_output=True, text=True, check=True).stdout.strip()


def _commit(message: str, cwd: Path) -> str:
    """A commit that does not depend on this device's git identity (there may be none)."""
    return _sh(
        [
            "git",
            "-c",
            f"user.name={HUMAN_IDENTITY[0]}",
            "-c",
            f"user.email={HUMAN_IDENTITY[1]}",
            "commit",
            "-m",
            message,
        ],
        cwd,
    )


def _fingerprint(home: Path) -> dict[str, str]:
    import hashlib

    return {
        str(p.relative_to(home)): hashlib.sha256(p.read_bytes()).hexdigest()
        for p in sorted(home.rglob("*"))
        if p.is_file()
    }


# --------------------------------------------------------------------------- probes


def probe_core_1() -> Verdict:
    """Verbs: exactly the eight; `--home` once, on the group, and honoured in any position.

    cli.v3 Core 1 adds `--home <instance>` to every verb while keeping the verb count at
    eight - "a flag is not a verb" - and says `--help` shows it once, on the group. Both
    halves are asserted here, and so is the thing that makes the flag usable: the clause's
    own examples type it AFTER the verb (`service uninstall --home <instance>`).
    """
    with fresh_store(init=False) as home:
        group_help = run("--help").output
        listed = [
            line.split()[0]
            for line in group_help.split("Commands:", 1)[1].splitlines()
            if line.startswith("  ")
        ]
        assert sorted(listed) == sorted(CONTRACT_VERBS), listed
        assert group_help.count("--home") == 1, group_help
        for verb in CONTRACT_VERBS:
            assert "--home" not in run(verb, "--help").output, f"{verb} --help repeats --home"

        # Either position, same instance - and an instance that is NOT the resolved one,
        # so a `--home` that was silently dropped could not accidentally pass.
        other = home.parent / "other-instance"
        amplifier_memory.init(other, timer=False)
        before = run("--home", str(other), "status").output
        after = run("status", "--home", str(other)).output
        equals = run(f"--home={other}", "status").output
        assert before == after == equals, (before, after, equals)
        assert str(other) in before, before
        empty = run("status", "--home")
        assert empty.exit_code != 0, empty.output

        bogus = run("bogus")
        lines = [line for line in bogus.output.strip().splitlines() if line.strip()]
        assert bogus.exit_code == 2, f"unknown verb exited {bogus.exit_code}, wanted 2"
        assert len(lines) == 1, f"unknown verb printed {len(lines)} lines: {lines}"
        assert run("upgrade").output == run("update").output, "upgrade is not an alias of update"
        assert "upgrade" not in group_help, "the alias is listed among the verbs"
    return "Kept", (
        f"--help lists exactly {sorted(listed)} and `--home` exactly once, on the group "
        "(no verb repeats it); `--home X status`, `status --home X` and `--home=X status` "
        f"print byte-identical output for a non-resolved instance, and a bare `--home` "
        f"exits {empty.exit_code}; `bogus` -> one line, exit 2; `upgrade` is a hidden alias"
    )


def probe_core_2() -> Verdict:
    """status: the VISION principle 9 numbers — including the citation rate and v2's `kept`.

    `kept` is the pre-registered definition in
    `docs/workflow/GATE-DEFINITION-2026-09-06.md`, and this probe holds it to both halves:
    an edit keeps the original write date, and a forget + re-save of the same text counts
    once, from the first write. Both discriminate — date an edit from the edit commit and
    `kept` drops by one; count the re-save as new and it drops by one.
    """
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

        # An edit today must not reset m-002's clock (a refinement is continuity).
        amplifier_memory.edit(
            "m-002",
            "eight days old, refined",
            "eight days old, refined",
            "human",
            "sess-kit",
            ["eight days old, refined"],
            home=home,
        )
        after_edit = amplifier_memory.status(home)
        assert after_edit.kept == 1, f"an edit reset the write date: kept={after_edit.kept}"
        assert after_edit.written_7 == 1, f"an edit counted as a write: {after_edit.written_7}"

        # A forget + re-save of the same text is one memory, dated from the first write.
        with at(30):
            _save("said once, forgotten, said again", home)
        with at(20):
            amplifier_memory.forget("m-004", home, session_id="sess-kit")
        with at(1):
            again = _save("said once, forgotten, said again", home)
        lineage = amplifier_memory.status(home)
        assert again.id == "m-005", again.id
        assert lineage.kept == 2, (
            f"kept={lineage.kept}: m-002 plus the m-004/m-005 lineage, counted once from its "
            "30-day-old first write"
        )

        amplifier_memory.log_usage("loaded", "MEMORY.md", "sess-kit", home)
        amplifier_memory.record_citation("m-002", "sess-kit", home)
        amplifier_memory.record_citation("m-006", "sess-kit", home)
        rate = amplifier_memory.status(home)
        line = "  citation rate    2 cited / 1 loaded (30d)"
        assert line in rate.render().splitlines(), rate.render()
        result = run("status")
        assert result.exit_code == 0 and result.output.rstrip() == rate.render()
    return "Kept", (
        f"against a built history: memories={rate.memories} written={rate.written_7}/7d "
        f"{rate.written_30}/30d forgotten={rate.forgotten_7}/7d kept={rate.kept} (an edit keeps "
        "the first write date; a forget + re-save counts once); status prints "
        f"{line.strip()!r}; the CLI prints exactly StatusReport.render()"
    )


def probe_core_3() -> Verdict:
    """why <id>: the creation, each edit as `was:` → `now:`, and a forget marked `forgot`.

    The `forgot` marker discriminates against the defect it was written for: in the Dana
    persona run `git log --oneline` showed a save and its forget as identical lines, and
    `why` headed both the same way.
    """
    with fresh_store() as home:
        quote = "never use tabs in YAML files; always two-space indentation"
        amplifier_memory.save(
            "never use tabs in YAML files", quote, "assistant", "sess-abc", [quote], home=home
        )
        amplifier_memory.edit(
            "m-001", "never use tabs in YAML", quote, "assistant", "sess-abc", [quote], home=home
        )
        amplifier_memory.forget("m-001", home, session_id="sess-abc")
        out = run("why", "m-001").output
        lines = out.splitlines()
        for needle in ("never use tabs in YAML files", quote, "sess-abc", "assistant"):
            assert needle in out, f"why does not print {needle!r}"
        assert out.count("commit:") == 3, "why does not show the save, the edit and the forget"
        headings = [line.split()[0] for line in lines if line and not line.startswith(" ")]
        assert headings == ["save", "edit", "forgot"], headings
        was_now = next(line for line in lines if line.strip().startswith("was:"))
        assert (
            '"never use tabs in YAML files"' in was_now and "now: never use tabs in YAML" in was_now
        ), was_now
        unknown = run("why", "m-999")
        error_lines = [line for line in unknown.output.strip().splitlines() if line.strip()]
        assert unknown.exit_code != 0 and len(error_lines) == 1, (unknown.exit_code, error_lines)
    return "Kept", (
        f"why m-001 prints three blocks headed {headings} (oldest first), the edit as "
        f"{was_now.strip()!r}, and quote/session/writer/date on each; an unknown id is one "
        f"line, exit {unknown.exit_code}"
    )


def probe_core_4() -> Verdict:
    """review: an empty inbox says so and exits 0."""
    with fresh_store():
        result = run("review")
        assert result.exit_code == 0, result.exit_code
        assert "empty" in result.output.lower(), result.output
    return "Kept", f"empty inbox -> {result.output.splitlines()[0]!r}, exit 0"


def _judge_rows(home: Path) -> dict[str, str]:
    """§5's judge row, in the clause's own WORDS, in each state the clause names.

    Until this existed the kit asserted only that the row was PRESENT in §5's row set;
    its wording was asserted only by `tests/test_doctor.py -k llm_row`, so the kit alone
    did not carry the clause (AMM-024's named limit, CHECK-RECORD 15b). These are those
    assertions, moved.

    `help_text=` is injected in every state, so no probe shells out to `amplifier run
    --help` and the wording does not depend on what this host happens to document.
    """
    from amplifier_memory import llm_config
    from amplifier_memory.doctor import APP_DEFAULT, INHERITED, llm_row

    config = home / llm_config.CONFIG_NAME
    shipped = config.read_text(encoding="utf-8")
    rows: dict[str, str] = {}

    # 1. INHERITED - the shipped config names a role and no provider, and this host
    #    documents no `--model-role`, so the pass runs on the app's own default.
    inherited = llm_row(llm_config.load(home), home=home, help_text="")
    assert inherited.level == "OK", inherited.render()
    assert INHERITED in inherited.detail, inherited.detail
    assert APP_DEFAULT in inherited.detail, "the inherited default is not named"
    assert llm_config.CONFIG_NAME in inherited.detail, "the file is not named"
    assert "role fast" in inherited.detail, "the recorded role is not named"
    assert "no run yet, so no measured cost" in inherited.detail, "the measured cost is missing"
    rows["inherited"] = inherited.detail

    # 2. CONFIGURED - a provider and model written in, printed, and no inheritance claimed.
    config.write_text(
        'llm:\n  judge:\n    provider: "luna"\n    model: "gpt-5.6-luna"\n', encoding="utf-8"
    )
    configured = llm_row(llm_config.load(home), home=home, help_text="")
    assert configured.level == "OK", configured.render()
    assert "provider luna" in configured.detail and "model gpt-5.6-luna" in configured.detail
    assert llm_config.CONFIG_NAME in configured.detail, configured.detail
    assert INHERITED not in configured.detail, "a named judge inherits nothing"
    rows["configured"] = configured.detail

    # 3. UNUSABLE - WARN, never FAIL: the run still happens and still inherits, but the
    #    human believes they chose a model and did not, so the reason and remedy are said.
    config.write_text("llm:\n  judge:\n   provider: 'luna'\n  \tbad\n", encoding="utf-8")
    unusable = llm_row(llm_config.load(home), home=home, help_text="")
    assert unusable.level == "WARN", "a bad config file is not a broken store"
    assert "not valid YAML" in unusable.detail, "the reason is not named"
    assert INHERITED in unusable.detail and "remedy" in unusable.detail
    rows["unusable"] = unusable.detail

    # 4. The row and the daily job are ONE sentence, not two renderings of one fact
    #    (AGENTS.md rule 11; the residual this closes). Same config, same words.
    config.write_text(shipped, encoding="utf-8")
    from amplifier_memory import suggest

    library = suggest.judge_detail(llm_config.load(home), home=home, help_text="")
    assert library in inherited.detail, (library, inherited.detail)
    rows["one sentence"] = "doctor's row is `suggest.judge_detail` plus the measured cost"
    return rows


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
        # cli.v2 §5 enumerates the rows doctor must carry; unlike Core 1's verb list it
        # does not close the set with "Nothing else". `llm judge` is the added one - it
        # answers suggestions.v1 Core 8 (bounded cost, *visible*) by naming which model
        # the daily pass is billed to. The exact list is still asserted, so a row that
        # silently appeared or vanished would trip here.
        assert names == [
            "store",
            "caps",
            "MEMORY.md well-formed",
            "stale topics",
            "inbox",
            "suggest timer",
            "substrate",
            "llm judge",
            "update",
        ], names
        assert report.exit_code == 0
        wellformed = next(row for row in report.rows if row.name == "MEMORY.md well-formed")
        assert wellformed.level == "OK", wellformed.render()
        judge = _judge_rows(home)

    # cli.v2 §5: the row FAILs on a headless fragment and on a non-UTF-8 byte, naming the
    # line or the offset and the last clean commit — and it is its own row, so the `store`
    # row stays OK and the two questions stay distinguishable.
    damage = {}
    for label, corrupt in (
        ("headless fragment", lambda p: p.write_bytes(p.read_bytes() + b"two-space indentation\n")),
        ("non-UTF-8 byte", lambda p: p.write_bytes(p.read_bytes() + b"- [m-002] caf\xe9\n")),
    ):
        with fresh_store() as home:
            _save("never use tabs", home)
            corrupt(home / "MEMORY.md")
            broken = amplifier_memory.doctor(home, installed_sha=SHA_A, remote_sha=SHA_A)
            row = next(r for r in broken.rows if r.name == "MEMORY.md well-formed")
            store_row = next(r for r in broken.rows if r.name == "store")
            assert row.level == "FAIL", row.render()
            assert store_row.level == "OK", store_row.render()
            assert "doctor --repair" in row.detail, row.detail
            assert "parsed clean:" in row.detail, row.detail
            assert broken.exit_code == 1, broken.exit_code
            damage[label] = row.detail
    assert "line 2" in damage["headless fragment"], damage["headless fragment"]
    assert "byte offset" in damage["non-UTF-8 byte"], damage["non-UTF-8 byte"]

    with fresh_store():
        trio = [
            amplifier_memory.update_check(SHA_A, SHA_B).level,
            amplifier_memory.update_check(SHA_A, SHA_A).level,
            amplifier_memory.update_check(SHA_A, None).level,
        ]
        assert trio == ["WARN", "OK", "INFO"], trio
        assert "amplifier-memory update" in amplifier_memory.update_check(SHA_A, SHA_B).detail

        # The row reads all THREE installed things, and names which one is behind. A
        # device whose uv tool is current while its bundle cache and venv library are
        # four waves old read `[OK] update current` for four waves (CHECK-RECORD,
        # 2026-09-06 22:05Z); each leg below discriminates that exact silence.
        legs = {"uv tool": SHA_A, "bundle cache": SHA_A, "env library": SHA_A}
        current = amplifier_memory.update_check(legs, SHA_A)
        assert current.level == "OK", current.render()
        for leg in legs:
            assert f"{leg} {SHA_A[:7]}" in current.detail, current.detail
        named = {}
        for leg in legs:
            row = amplifier_memory.update_check({**legs, leg: SHA_B}, SHA_A)
            assert row.level == "WARN", row.render()
            assert f"{leg} {SHA_B[:7]} behind main {SHA_A[:7]}" in row.detail, row.detail
            assert "amplifier-memory update" in row.detail
            named[leg] = row.detail
        absent = amplifier_memory.update_check({**legs, "env library": None}, SHA_A)
        assert absent.level == "INFO" and "env library not found" in absent.detail, absent.render()
    with fresh_store(init=False) as empty:
        missing = amplifier_memory.doctor(empty, installed_sha=SHA_A, remote_sha=SHA_A)
        assert missing.exit_code == 1, "a missing store did not fail the check"
        behind = amplifier_memory.doctor(empty, installed_sha=SHA_A, remote_sha=SHA_B)
        assert behind.exit_code == 1 and behind.rows[0].level == "FAIL"
    return "Kept", (
        f"{len(before)} files byte-identical before/after; rows {names}; the well-formed row "
        "FAILs on a headless fragment (names line 2) and on a non-UTF-8 byte (names the offset), "
        "both naming the last clean commit and `doctor --repair`, while the `store` row stays "
        f"OK; update trio {trio} (behind names the remedy); the row reads all three installed "
        f"things - OK says {current.detail!r}, and a stale one is named: {named['bundle cache']!r}; "
        "a leg that cannot be found is INFO, never RED; exit 1 only on a failed check. The "
        "judge row is asserted in §5's own WORDS, in every state, with the host probe "
        f"injected: inherited -> {judge['inherited']!r}; configured -> "
        f"{judge['configured']!r}; an unusable config.yaml is WARN naming the reason and the "
        f"remedy -> {judge['unusable']!r}; and {judge['one sentence']}"
    )


def probe_core_6() -> Verdict:
    """service: render units, daemon-reload -> enable --now, and roll back on a failed step.

    Every command here is a **fake runner** and every unit file lands in a temp directory.
    This probe once invoked `service install` with no injection at all and enabled a real
    daily timer on the steward's device (2026-09-06); `service.UNIT_DIR_ENV` is the
    override that makes the CLI surface reachable without touching
    `~/.config/systemd/user`, and `service._default_runner` now refuses outright under
    pytest.
    """
    from amplifier_memory import service

    with fresh_store() as home, tempfile.TemporaryDirectory(prefix="cli-v2-units-") as units:
        os.environ[service.UNIT_DIR_ENV] = units
        try:
            calls: list[tuple[str, ...]] = []

            def ok(argv):
                calls.append(tuple(argv))
                return 0, ""

            def enable_fails(argv):
                calls.append(tuple(argv))
                if "enable" in argv:
                    return 1, "Failed to enable unit: Unit file is masked."
                return 0, ""

            unit = amplifier_memory.service_unit(home)
            timer_name = amplifier_memory.timer_unit(home)
            good = amplifier_memory.service_install(
                runner=ok, config_dir=units, executable="/usr/bin/amplifier-memory", home=home
            )
            written = sorted(path.name for path in Path(units).iterdir())
            body = (Path(units) / unit).read_text(encoding="utf-8")
            timer = (Path(units) / timer_name).read_text(encoding="utf-8")
            assert good.ok and written == sorted([unit, timer_name]), (good.render(), written)
            assert "Type=oneshot" in body, body
            # cli.v3 §6: the unit name carries the instance, and ExecStart carries --home,
            # so two instances never collide and neither runs the other's pass.
            assert amplifier_memory.instance_tag(home) in timer_name, timer_name
            assert f"ExecStart=/usr/bin/amplifier-memory suggest --home {home}" in body, body
            assert "OnCalendar=daily" in timer and "Persistent=true" in timer, timer
            assert calls == [
                ("systemctl", "--user", "daemon-reload"),
                ("systemctl", "--user", "enable", "--now", timer_name),
            ], calls

            # A SECOND instance gets its own units, and neither uninstall reaches the other.
            second = home.parent / "second-instance"
            amplifier_memory.init(second, timer=False)
            amplifier_memory.service_install(
                runner=ok, config_dir=units, executable="/usr/bin/amplifier-memory", home=second
            )
            both = sorted(path.name for path in Path(units).iterdir())
            assert len(both) == 4, both
            # §6: `status` lists EVERY installed instance timer, not only the resolved one.
            listed = amplifier_memory.installed_timers(config_dir=units, home=home)
            instances = sorted(str(t.instance) for t in listed)
            assert instances == sorted([str(home), str(second)]), instances
            assert sum(t.resolved for t in listed) == 1, instances

            amplifier_memory.service_uninstall(runner=ok, config_dir=units, home=second)
            after_one = sorted(path.name for path in Path(units).iterdir())
            assert after_one == sorted([unit, timer_name]), after_one

            # The CLI verb reaches the same library call, read-only, against the temp dir.
            shown = run("service", "status", "--home", str(home))
            assert shown.exit_code == 0 and "installed" in shown.output, shown.output

            amplifier_memory.service_uninstall(runner=ok, config_dir=units, home=home)
            assert list(Path(units).iterdir()) == [], "uninstall left units behind"

            rolled = amplifier_memory.service_install(
                runner=enable_fails,
                config_dir=units,
                executable="/usr/bin/amplifier-memory",
                home=home,
            )
            left = list(Path(units).iterdir())
        finally:
            os.environ.pop(service.UNIT_DIR_ENV, None)
    assert not rolled.ok and rolled.rolled_back and left == [], (rolled.render(), left)
    migration = _migration_arm()
    return "Kept", (
        f"install writes {written} into the unit dir - the unit name carries the instance "
        f"({amplifier_memory.instance_tag(home)}) and ExecStart is `<abs> suggest --home "
        "<instance>` (Type=oneshot; OnCalendar=daily, Persistent=true) - and runs exactly "
        f"`systemctl --user daemon-reload` then `enable --now {timer_name}`; a second "
        f"instance adds its own two units ({both}), `installed_timers` lists both instances "
        f"({instances}) marking one resolved, and uninstalling the second leaves the first "
        f"({after_one}); `service status --home` through the CLI reads it back and exits 0; "
        f"uninstall leaves nothing; a failing enable rolls back every file written (left "
        f"{left}) - all against a temp unit dir with a fake runner, never this device. "
        f"Pre-v3 migration: {migration}"
    )


def _migration_arm() -> str:
    """cli.v3 §6: the pre-v3 device-wide pair, ended for the instance it actually served.

    The un-instanced pair (`amplifier-memory-suggest.service`/`.timer`) carries no
    `--home`, so it runs whichever instance store.v3 §1 resolves to. Left beside a new
    instanced timer it fires the same pass a second time every day; so `install` replaces
    it for the resolved default, and leaves it strictly alone for any other instance —
    removing it there would silently stop the daily pass for whoever IS the default.

    Both arms run against a temp unit dir with a fake runner, and every unit name a
    result CLAIMS is serving an instance is checked back against the directory listing.
    """
    from amplifier_memory import service

    calls: list[tuple[str, ...]] = []

    def ok(argv):
        calls.append(tuple(argv))
        return 0, ""

    with fresh_store() as home, tempfile.TemporaryDirectory(prefix="cli-v3-migrate-") as units:
        unit_dir = Path(units)
        exe = "/usr/bin/amplifier-memory"

        def lay_pre_v3() -> None:
            (unit_dir / service.SERVICE_UNIT).write_text(
                service.render_service(exe, None), encoding="utf-8"
            )
            (unit_dir / service.TIMER_UNIT).write_text(service.render_timer(None), encoding="utf-8")

        # Arm one: the instance IS the resolved default, so the pre-v3 pair is replaced.
        lay_pre_v3()
        before = sorted(p.name for p in unit_dir.iterdir())
        migrated = amplifier_memory.service_install(
            runner=ok, config_dir=unit_dir, executable=exe, platform=service.SYSTEMD, home=home
        )
        after = sorted(p.name for p in unit_dir.iterdir())
        mine = service.timer_unit(home)
        assert migrated.ok, migrated.render()
        assert after == sorted([service.service_unit(home), mine]), after
        assert [n for n in after if n.endswith(".timer")] == [mine], after
        assert ("systemctl", "--user", "disable", "--now", service.TIMER_UNIT) in calls, calls
        assert service.MIGRATED.format(unit=mine) in migrated.note, migrated.note
        assert all(path.exists() for path in migrated.written), migrated.render()
        assert not any(path.exists() for path in migrated.removed), migrated.render()

        # Arm two: a DIFFERENT instance. The pre-v3 pair is somebody else's, and is said
        # to be, by name — never removed.
        second = home.parent / "second-instance"
        amplifier_memory.init(second, timer=False)
        lay_pre_v3()
        calls.clear()
        kept = amplifier_memory.service_install(
            runner=ok, config_dir=unit_dir, executable=exe, platform=service.SYSTEMD, home=second
        )
        survived = sorted(p.name for p in unit_dir.iterdir())
        assert kept.ok and (unit_dir / service.TIMER_UNIT).is_file(), (kept.render(), survived)
        assert service.LEFT_ALONE.format(unit=service.TIMER_UNIT, home=second) in kept.note, (
            kept.note
        )
        assert ("systemctl", "--user", "disable", "--now", service.TIMER_UNIT) not in calls, calls

        # §6: `status` lists every timer on the device by unit and instance, and names
        # the surviving pre-v3 one for exactly what it is.
        listed = {
            timer.unit.name: timer.render()
            for timer in amplifier_memory.installed_timers(
                config_dir=unit_dir, platform=service.SYSTEMD, home=second
            )
        }
        assert set(listed) == {service.TIMER_UNIT, mine, service.timer_unit(second)}, listed
        assert "pre-v3, serves the default only" in listed[service.TIMER_UNIT], listed
        assert str(second) in listed[service.timer_unit(second)], listed
        for name in listed:
            assert (unit_dir / name).is_file(), f"{name} is listed but not on disk"

    return (
        f"the pre-v3 pair {before} on disk, `service install --home <default>` leaves "
        f"exactly {after} - one timer, {mine} - having run `systemctl --user disable --now "
        f"{service.TIMER_UNIT}` through the injected runner and said {migrated.note!r}; "
        f"for a NON-default instance the same pair survives ({survived}) and install says "
        f"{kept.note!r}; `installed_timers` names all three by unit and instance "
        f"({sorted(listed.values())}), every one of them a file in the temp unit dir"
    )


def probe_core_7() -> Verdict:
    """update: upgrade the tool, refresh **all three** installed things, end in doctor.

    The clause's "refreshes the registered app bundle" is read as what a session actually
    loads: the cache clone the modules and skills come from, and the `amplifier_memory`
    inside the amplifier CLI's own venv that those modules import. Against a fake device
    the git half really runs, so this probe proves the clones MOVED — `git rev-parse` off
    disk afterwards, never the step's own claim about itself.

    And "a steward runs it once": the process running `update` is the pre-upgrade CLI, so
    when step 1 moves the installed commit the rest of the run is handed to the freshly
    installed binary. All three sides are exercised here — the hand-off (os.execv argv
    recorded, nothing after step 1 run in the old process), the re-executed process
    (`--after-upgrade` skips step 1, the refreshes really happen, doctor runs), and a
    hand-off that cannot happen (one [info] line naming the remedy, every step still run).
    """
    with tempfile.TemporaryDirectory(prefix="cli-v2-fake-device-") as tmp:
        device = FakeDevice(Path(tmp))
        assert [commit_of_cache(c) for c in device.clones()] == [device.old, device.old]
        assert commit_of_env_library(device.python) == device.old

        from amplifier_memory import service

        calls: list[tuple[str, ...]] = []
        # Step 4 reads the unit dir to decide whether a timer is installed (cli.v2 Core 7
        # "restarts the timer if installed"); this arm is the no-timer device, so point the
        # unit dir at an empty directory of its own rather than whatever an earlier probe left.
        os.environ[service.UNIT_DIR_ENV] = str(Path(tmp) / "no-units")
        with fresh_store() as home:
            before = _git.log_records(home)
            result = amplifier_memory.run_update(
                runner=device.runner(calls),
                app_bundle_uri=device.uri,
                amplifier_home=str(device.home),
                env_python=device.python,
            )
            rendered = result.render()
            after = _git.log_records(home)

        assert calls[0] == amplifier_memory.UPGRADE_CLI_ARGV, calls
        moved = [commit_of_cache(clone) for clone in device.clones()]
        assert moved == [device.new, device.new], f"the cache clones did not move: {moved}"
        assert commit_of_env_library(device.python) == device.new, "the venv library did not move"
        cache_lines = [
            step.name for step in result.steps if "refresh the bundle cache" in step.name
        ]
        library_line = next(
            step.name for step in result.steps if "amplifier environment" in step.name
        )
        assert len(cache_lines) == 2, cache_lines
        for line in [*cache_lines, library_line]:
            assert f"{device.old[:7]} \u2192 {device.new[:7]}" in line, line
        assert any(argv[:2] == ("uv", "pip") for argv in calls), calls
        assert amplifier_memory.BUNDLE_ADD_ARGV not in calls, "a live clone needs no re-register"
        assert not any("service" in " ".join(argv) for argv in calls), "the timer was touched"

        # The other half of step 4 (item ohg, 2026-09-07): with a timer INSTALLED the restart
        # runs through the injected runner under an [ok] label - never under [skip], and
        # never against the real systemctl.
        with_units = Path(tmp) / "with-units"
        with_units.mkdir()
        for name in (amplifier_memory.SERVICE_UNIT, amplifier_memory.TIMER_UNIT):
            (with_units / name).write_text("[Unit]\n", encoding="utf-8")
        os.environ[service.UNIT_DIR_ENV] = str(with_units)
        restart_calls: list[tuple[str, ...]] = []
        with fresh_store() as restart_home:
            restarted = amplifier_memory.run_update(
                runner=device.runner(restart_calls),
                app_bundle_uri=device.uri,
                amplifier_home=str(device.home),
                env_python=device.python,
            )
        step4 = next(s for s in restarted.steps if s.name == "restart the suggest timer")
        # cli.v3 Core 1: the restart names the instance, so `update --home X` can never
        # restart Y's timer. The unit dir above carries X's own units, not the base ones.
        wanted = ("amplifier-memory", "service", "restart", "--home", str(restart_home))
        assert not step4.skipped and step4.argv == wanted, step4
        assert wanted in restart_calls, restart_calls
        os.environ[service.UNIT_DIR_ENV] = str(Path(tmp) / "no-units")
        assert amplifier_memory.APP_BUNDLE_URI.endswith("behaviors/memory-session.yaml")
        assert result.report is not None, "update did not end by running doctor"
        assert "keep the old module code until they restart" in rendered
        assert "amplifier-memory doctor — store:" in rendered
        assert result.exit_code == 0, rendered
        assert len(before) == len(after), "update mutated the store"

    # No amplifier venv: one warning line, and every other step still runs.
    with tempfile.TemporaryDirectory(prefix="cli-v2-fake-device-") as tmp:
        bare = FakeDevice(Path(tmp), venv=False)
        with fresh_store():
            no_venv = amplifier_memory.run_update(
                runner=bare.runner([]),
                app_bundle_uri=bare.uri,
                amplifier_home=str(bare.home),
                env_python=None,
            )
        warned = next(s for s in no_venv.steps if "amplifier environment" in s.name)
        assert "[warn]" in warned.render() and not warned.failed, warned.render()
        assert no_venv.exit_code == 0
        assert [commit_of_cache(c) for c in bare.clones()] == [bare.new, bare.new]

    # Nothing installed yet: the remove-then-add install path is still reachable.
    with tempfile.TemporaryDirectory(prefix="cli-v2-fake-device-") as tmp:
        empty = FakeDevice(Path(tmp), clones=0, venv=False)
        install_calls: list[tuple[str, ...]] = []
        with fresh_store():
            amplifier_memory.run_update(
                runner=empty.runner(install_calls),
                app_bundle_uri=empty.uri,
                amplifier_home=str(empty.home),
                env_python=None,
            )
        assert amplifier_memory.BUNDLE_ADD_ARGV in install_calls, install_calls

    # One run is enough: when step 1 moved the installed commit, the rest of the run is
    # handed to the freshly installed binary, and NOTHING after step 1 happens here. The
    # commit reader is scripted and `os.execv` is stood in for, so the kit never
    # re-executes the machine running it.
    with tempfile.TemporaryDirectory(prefix="cli-v2-fake-device-") as tmp:
        upgraded = FakeDevice(Path(tmp))
        binary = "/fake/bin/amplifier-memory"
        handed_calls: list[tuple[str, ...]] = []
        execs: list[tuple[str, list[str]]] = []
        real_execv, real_which = os.execv, shutil.which
        os.execv = lambda path, argv: execs.append((path, list(argv)))
        shutil.which = lambda name: binary if name == "amplifier-memory" else real_which(name)
        said = io.StringIO()
        try:
            with fresh_store(), redirect_stdout(said):
                handed = amplifier_memory.run_update(
                    runner=upgraded.runner(handed_calls),
                    app_bundle_uri=upgraded.uri,
                    amplifier_home=str(upgraded.home),
                    env_python=upgraded.python,
                    installed_commit_fn=_scripted(upgraded.old, upgraded.new),
                )
        finally:
            os.execv, shutil.which = real_execv, real_which

        assert execs == [(binary, [binary, "update", "--after-upgrade"])], execs
        assert [s.name for s in handed.steps] == ["upgrade the CLI"], [s.name for s in handed.steps]
        assert handed_calls == [amplifier_memory.UPGRADE_CLI_ARGV], handed_calls
        assert handed.report is None, "doctor ran in the process that was about to be replaced"
        assert [commit_of_cache(c) for c in upgraded.clones()] == [upgraded.old, upgraded.old]
        assert commit_of_env_library(upgraded.python) == upgraded.old
        assert "upgrade the CLI" in said.getvalue(), said.getvalue()

        # The other half: the re-executed process skips step 1 and refreshes for real.
        rest_calls: list[tuple[str, ...]] = []
        with fresh_store():
            rest = amplifier_memory.run_update(
                runner=upgraded.runner(rest_calls),
                app_bundle_uri=upgraded.uri,
                amplifier_home=str(upgraded.home),
                env_python=upgraded.python,
                after_upgrade=True,
            )
        assert rest.steps[0].skipped, rest.steps[0].render()
        assert "already upgraded by the previous process" in rest.steps[0].reason
        assert amplifier_memory.UPGRADE_CLI_ARGV not in rest_calls, rest_calls
        assert [commit_of_cache(c) for c in upgraded.clones()] == [upgraded.new, upgraded.new]
        assert commit_of_env_library(upgraded.python) == upgraded.new
        assert rest.report is not None and rest.exit_code == 0, rest.render()

        # Hand-off impossible: one INFO line, the remedy named, every step still run.
        stuck = FakeDevice(Path(tmp) / "stuck")
        os.execv, shutil.which = _never_execv, lambda name: None
        try:
            with fresh_store():
                in_place = amplifier_memory.run_update(
                    runner=stuck.runner([]),
                    app_bundle_uri=stuck.uri,
                    amplifier_home=str(stuck.home),
                    env_python=stuck.python,
                    installed_commit_fn=_scripted(stuck.old, stuck.new),
                )
        finally:
            os.execv, shutil.which = real_execv, real_which
        infos = [s for s in in_place.steps if s.info]
        assert len(infos) == 1 and amplifier_memory.update.IN_PLACE_NOTE in infos[0].reason, infos
        assert in_place.render().count(amplifier_memory.update.IN_PLACE_NOTE) == 1
        assert [commit_of_cache(c) for c in stuck.clones()] == [stuck.new, stuck.new]
        assert in_place.exit_code == 0

    # The CLI verb is one call into this same function and carries no logic of its
    # own (cli.v2 Core 9). Read, never invoked: invoking `update` through the CLI
    # would use the real runner and actually upgrade the machine running the kit.
    cli_src = (Path(__file__).resolve().parents[2] / "src/amplifier_memory/cli.py").read_text()
    body = cli_src.split("def update(")[1].split("@main.command()")[0]
    assert "run_update(after_upgrade=after_upgrade, home=home)" in body, body
    assert "subprocess" not in body and "uv tool" not in body, body

    return "Kept", (
        "one run is enough: with the installed commit moving across step 1, the old process "
        f"ran step 1 and NOTHING else (steps: {[s.name for s in handed.steps]}, clones still "
        f"at {upgraded.old[:7]}) and re-executed `{binary} update --after-upgrade` (os.execv argv "
        "recorded); with --after-upgrade, step 1 is skipped ('already upgraded by the previous "
        "process') and the cache clones and venv library really move; hand-off impossible "
        "(nothing on PATH) is ONE [info] line naming the remedy, with every other step still "
        "run and exit 0. Also, against a fake device (temp cache clones off a local-disk "
        "origin, temp venv with a "
        "PEP 610 direct_url.json), `update` moved ALL THREE installed things off the old "
        f"commit: uv tool upgrade amplifier-memory; both cache clones {device.old[:7]} -> "
        f"{device.new[:7]} verified by git rev-parse on disk; the venv library "
        f"{device.old[:7]} -> {device.new[:7]} verified by re-reading direct_url.json; timer "
        "skipped (Phase 1 has none); doctor. `bundle add` is no longer the refresh (it left "
        "the clone on its old commit on the real device) but stays the install path, reached "
        "when there is no clone; no venv is one warn line and the other steps still run. "
        "The stale-in-memory note printed and the store's git history was unchanged. "
        "NOT checked here, and deliberately: that the REAL `uv tool upgrade` / `uv pip install` "
        "/ `amplifier bundle add` subprocesses do what their steps claim on a real device - "
        "running them would upgrade whatever machine runs this kit. Their argv is verified "
        "against each CLI's own --help by tests/test_update.py; the real run belongs to the "
        "manager session after merge"
    )


def probe_core_8() -> Verdict:
    """init: the store, the timer, and the three arms that install no timer.

    Five arms. Four are the clause as amended 2026-09-07: a fresh init installs the daily
    timer and prints the opt-out and the config path; a second init reports both and
    changes nothing; `--no-timer` leaves no unit; and a host where `service install` finds
    no `amplifier-memory` on PATH gets install's own refusal and no unit. The fifth is the
    device the steward actually had (item `…-5wc`): a pre-v3 device-wide pair and no
    instanced unit, where `init` must end with exactly ONE timer, say it replaced the old
    one, and name only units that are on disk.

    **Every unit here lands in a temp directory through a fake runner.** The installing
    arms call the library with `runner=`/`config_dir=` injected, and every unit name
    carries the instance (§6), so a temp instance's timer is a different file from this
    device's. Both together are what replaced the old "install only for the device store"
    gate, which existed because a probe enabled a real daily timer on the steward's
    device twice on 2026-09-06.
    """
    from amplifier_memory import instance as instance_mod
    from amplifier_memory import service

    # amplifier_bundle_memory-azy, half one: while the unit dir is redirected - which
    # `main_()` does for the whole run - the real runner REFUSES. So no probe here, and
    # nothing a future probe adds, can reach this device's systemctl by unit name.
    guard = service.redirect_reason()
    assert guard, "the install-plane guard is not armed; a probe could reach real systemctl"

    with fresh_store(init=False) as home:
        # The CLI arm asks for no timer, so this assertion reads the same standalone as
        # under pytest (where conftest swaps the runner in). The installing arms below
        # inject `runner=`/`config_dir=` explicitly - azy, half two.
        first = run("init", "--no-timer")
        log_one = _git.git(["log", "--oneline"], cwd=home).stdout.strip()
        second = run("init")
        log_two = _git.git(["log", "--oneline"], cwd=home).stdout.strip()
        assert first.exit_code == second.exit_code == 0
        assert "created" in first.output and "store exists" in second.output
        assert log_one == log_two, f"the second init changed the history: {log_one} -> {log_two}"
        # cli.v3 §8: the layout, then the ONE seeding question's answer as m-001.
        subjects = [line.split(" ", 1)[1] for line in log_two.splitlines()]
        assert len(subjects) == 2, subjects
        assert subjects[0].startswith("[m-001] "), subjects
        seeded = amplifier_memory.why("m-001", home)
        assert seeded[0]["writer"] == "human", seeded
        assert seeded[0]["quote"] == seeded[0]["text"] == instance_mod.SEED_DEFAULT, seeded
        assert instance_mod.SEED_QUESTION in first.output or "no TTY" in first.output
        assert "no TTY" in first.output, first.output
        # "asks nothing, and changes nothing": the second run is one line, no m-002.
        assert len(second.output.strip().splitlines()) == 1, second.output
        plumbing = {".git", ".gitignore"}
        on_disk = sorted(p.name for p in home.iterdir() if p.name not in plumbing)
        assert on_disk == [
            "MEMORY.md",
            "config.yaml",
            "declined.md",
            "inbox.md",
            "sessions.jsonl",
            "topics",
            "usage.jsonl",
        ], on_disk
        # store.v2 §1: usage.jsonl is created but never tracked, so reading leaves no commit.
        tracked = sorted(_git.git(["ls-files"], cwd=home).stdout.split())
        assert tracked == [
            ".gitignore",
            "MEMORY.md",
            "config.yaml",
            "declined.md",
            "inbox.md",
            "topics/.gitkeep",
        ], tracked

    arms: dict[str, str] = {}
    for arm in ("installs", "second", "no-timer", "no-cli", "device-wide"):
        with (
            fresh_store(init=False) as home,
            tempfile.TemporaryDirectory(prefix="cli-v3-init-units-") as units,
        ):
            calls: list[tuple[str, ...]] = []

            def record(argv, calls=calls):
                calls.append(tuple(argv))
                return 0, ""

            unit_dir = Path(units)
            exe = "amplifier-memory" if arm == "no-cli" else "/usr/bin/amplifier-memory"
            if arm == "device-wide":
                # The device the steward actually had on 2026-09-07: a pre-v3 pair from
                # cli.v2's `service install`, and no instanced unit at all.
                (unit_dir / service.SERVICE_UNIT).write_text(
                    service.render_service(exe, None), encoding="utf-8"
                )
                (unit_dir / service.TIMER_UNIT).write_text(
                    service.render_timer(None), encoding="utf-8"
                )
            result = amplifier_memory.build_instance(
                home,
                timer=arm != "no-timer",
                runner=record,
                config_dir=unit_dir,
                executable=exe,
                platform=service.SYSTEMD,
            )
            printed = result.render()
            written = sorted(p.name for p in unit_dir.iterdir())
            wanted = sorted([service.service_unit(home), service.timer_unit(home)])

            if arm == "installs":
                lines = printed.splitlines()
                assert result.timer_installed and written == wanted, (printed, written)
                assert calls == [
                    ("systemctl", "--user", "daemon-reload"),
                    ("systemctl", "--user", "enable", "--now", service.timer_unit(home)),
                ], calls
                # §8: the unit name carries the instance, so a kit's temp instance gets
                # its own unit instead of touching the device's.
                assert service.instance_tag(home) in written[0], written
                assert service.timer_unit(None) not in written, written
                # §8's two closing lines: the opt-out NAMES the instance, and the cost
                # knob is this instance's own config.yaml (store.v3 §2).
                assert f"service uninstall --home {home}" in lines[-2], lines
                assert str(home / "config.yaml") in lines[-1], lines
                # §8: config.yaml carries the shipped defaults - a ROLE, never a provider.
                config = (home / "config.yaml").read_text(encoding="utf-8")
                assert "enabled: true" in config and 'role: "fast"' in config, config
                assert 'provider: ""' in config, config
                arms[arm] = f"units {written}, argv {[c[2] for c in calls]}, closing lines ok"
            elif arm == "second":
                before = _fingerprint(home) | _fingerprint(unit_dir)
                calls.clear()
                again = amplifier_memory.build_instance(
                    home, config_dir=unit_dir, platform=service.SYSTEMD
                )
                after = _fingerprint(home) | _fingerprint(unit_dir)
                assert "store exists \u00b7 timer installed" in again.render(), again.render()
                assert calls == [] and before == after, (calls, len(before))
                arms[arm] = f"{again.render()!r}; {len(before)} files unchanged, no argv"
            elif arm == "no-timer":
                assert written == [] and calls == [], (written, calls)
                assert "--no-timer" in printed, printed
                arms[arm] = f"no unit written, no argv; said {printed.splitlines()[-1]!r}"
            elif arm == "no-cli":
                assert written == [] and result.timer_installed is False, (written, printed)
                assert "no `amplifier-memory` on PATH" in printed, printed
                assert "service uninstall" not in printed, printed
                arms[arm] = "install's own refusal, no unit"
            else:
                # cli.v3 §6/§8: exactly ONE timer serves the instance afterwards, the
                # replacement is said out loud, and every unit name `init` PRINTS is a
                # file in the unit dir at the moment it is printed (item `…-5wc`).
                named = sorted(set(UNIT_NAME.findall(printed)))
                missing = [name for name in named if not (unit_dir / name).is_file()]
                timers = [name for name in written if name.endswith(".timer")]
                assert result.timer_installed and written == wanted, (printed, written)
                assert timers == [service.timer_unit(home)], written
                assert missing == [], (named, written)
                assert service.MIGRATED.format(unit=service.timer_unit(home)) in printed, printed
                assert (
                    "systemctl",
                    "--user",
                    "disable",
                    "--now",
                    service.TIMER_UNIT,
                ) in calls, calls
                arms[arm] = (
                    f"pre-v3 pair replaced: units {written} (one timer, {timers[0]}), argv "
                    f"{[c[2] for c in calls]}, and the {len(named)} unit name(s) init printed "
                    f"({named}) are all files in the unit dir"
                )

    # §8's move offer, both answers. `store.legacy_home()` is under $HOME, so the offer is
    # driven through the injected `confirm=` rather than by moving anything real.
    moved = _move_arm()

    return "Kept", (
        f"first init created {on_disk} in two commits ({log_one}), tracking {tracked} \u2014 "
        "usage.jsonl on disk but untracked (store.v2 §1); m-001 carries the seeding answer "
        f"as writer=human with the answer as its own quote; the second changed nothing and "
        f"said so in one line. The install-plane guard is armed ({guard!r}), so a standalone "
        "kit run cannot reach real systemctl (azy). Timer arms, all against a temp unit dir "
        f"with a fake runner: installs -> {arms['installs']}; second init -> {arms['second']}; "
        f"--no-timer -> {arms['no-timer']}; no CLI on PATH -> {arms['no-cli']}; "
        f"pre-v3 device-wide pair present -> {arms['device-wide']}. Move offer -> {moved}"
    )


def _move_arm() -> str:
    """§8's move offer: declined leaves the older store alone, accepted moves it and says so.

    The offer only fires for the DEFAULT instance, so `Path.home()` is redirected at the
    two functions that read it rather than on this device: nothing here goes near a real
    `~/.amplifier/memory`.
    """
    from amplifier_memory import store

    said = {}
    for answer in (False, True):
        with tempfile.TemporaryDirectory(prefix="cli-v3-move-") as tmp:
            fake_home = Path(tmp)
            legacy = fake_home / ".amplifier" / "memory"
            default = fake_home / store.DEFAULT_HOME_NAME
            amplifier_memory.init(legacy, timer=False)
            saved = os.environ.pop("AMPLIFIER_MEMORY_HOME", None)
            real_home = Path.home
            try:
                Path.home = staticmethod(lambda root=fake_home: root)  # type: ignore[method-assign]
                report = amplifier_memory.build_instance(
                    timer=False, confirm=lambda _q, answer=answer: answer
                )
            finally:
                Path.home = real_home  # type: ignore[method-assign]
                if saved is not None:
                    os.environ["AMPLIFIER_MEMORY_HOME"] = saved
            printed = report.render()
            assert report.move_offered, printed
            if answer:
                assert report.moved_from == legacy and report.home == default, printed
                assert default.is_dir() and not legacy.exists(), printed
                assert "moved" in printed, printed
            else:
                assert report.moved_from is None and report.home == legacy, printed
                assert legacy.is_dir() and not default.exists(), "a declined offer moved it"
                assert "left" in printed, printed
            said["accepted" if answer else "declined"] = printed.splitlines()[0]
    return f"declined -> {said['declined']!r}; accepted -> {said['accepted']!r}"


def probe_core_9() -> Verdict:
    """Thin wrapper: cli.py imports only click and amplifier_memory; every verb is a library call."""
    import subprocess

    source = (
        Path(__file__).resolve().parents[2] / "src" / "amplifier_memory" / "cli.py"
    ).read_text(encoding="utf-8")
    imports = [line for line in source.splitlines() if line.startswith(("import ", "from "))]
    assert imports == ["import click", "import amplifier_memory"], imports

    with fresh_store(init=False) as home:
        code = (
            "import sys, amplifier_memory as m;"
            f" m.init({str(home)!r}); m.status({str(home)!r}); m.review({str(home)!r});"
            f" m.doctor({str(home)!r}, installed_sha=None, remote_sha=None);"
            " m.service_status('status', runner=lambda argv: (0, ''),"
            f" config_dir={str(home.parent / 'units')!r}, home={str(home)!r});"
            f" m.suggest_status({str(home)!r}); m.update_plan();"
            " m.update_check('a'*40,'b'*40);"
            " print([x for x in sys.modules if x.startswith('click')])"
        )
        proc = subprocess.run(
            [sys.executable, "-c", code],
            capture_output=True,
            text=True,
            check=True,
            cwd=home.parent,
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
    # Belt and braces for the whole run, not per probe: point the unit directory and the
    # session substrate at throwaway paths BEFORE any probe runs. `service._default_runner`
    # and `suggest.default_model_call` refuse under pytest, but a kit run straight from a
    # shell is not under pytest -- and that is exactly how probe_core_9's subprocess
    # enabled a real daily timer on the steward's device (twice, 2026-09-06).
    from amplifier_memory import service as _service

    guard = tempfile.mkdtemp(prefix="cli-v2-guard-")
    os.environ[_service.UNIT_DIR_ENV] = str(Path(guard) / "units")
    os.environ["AMPLIFIER_CONTEXT_INTELLIGENCE_BASE_PATH"] = str(Path(guard) / "no-substrate")

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
