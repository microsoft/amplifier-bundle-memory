#!/usr/bin/env python3
"""suggestions.v1 conformance kit — one line per Core clause, against a fixture substrate.

Run it:  ``uv run python conformance/suggestions/run.py``

Each probe builds its own throwaway store and its own fake session capture, and returns
one of the ledger's plain words: **Kept · Not yet · Broken · Can't check**. A probe that
cannot fail is not a probe: every Kept below rests on an assertion a regression would
trip. Exit code is 0 unless a clause reads Broken.

Two clauses are answered honestly rather than asserted:

* **Core 5** (the pending line beside the session's load line) is rendered by the
  session hook, not by this library — `conformance/session/inject/run.py` is where it is
  checked.
* **Core 1's second half** ("nothing is resident") is asserted on the *unit* — the
  service is `Type=oneshot` and carries no `[Install]`, so only the timer starts it —
  never on a running systemd, because this kit must not install one.

**No probe here touches this device, the network, or a model.** The substrate is a temp
directory, `model_call` is a fake, unit files land in a temp directory, and both
`service._default_runner` and `suggest.default_model_call` refuse under pytest. Those
two guards exist because on 2026-09-06 the cli.v2 Core 6 probe called `service install`
with no injection and enabled a real daily timer on the steward's machine.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
from collections.abc import Callable, Iterator, Sequence
from contextlib import contextmanager
from datetime import UTC, datetime, timedelta
from pathlib import Path

if __package__ in (None, ""):  # allow `python conformance/suggestions/run.py`
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import amplifier_memory
from amplifier_memory import inbox, service, suggest

Verdict = tuple[str, str]

HUMAN_IDENTITY = ("Test Human", "human@example.invalid")

#: The fixture transcript's two human turns: a standing correction, and a task
#: instruction in the same session. suggestions.v1's Conformance section calls this the
#: discriminating pair.
CORRECTION = "stop reformatting my YAML - never use tabs in YAML files I ask you to write"
TASK = "now add a --verbose flag to the parser and run the tests"

GOOD = {
    "text": "never use tabs in YAML files",
    "quote": "never use tabs in YAML files I ask you to write",
}
TASKY = {"text": "add a --verbose flag to the parser", "quote": TASK}
#: The re-proposal arm: the same human sentence, word for word, under a rewritten text.
#: This is what every model in the pilots actually returned when it missed §3's
#: "skip anything already in this list" - see `probe_core_4_quote`.
PARAPHRASE = {"text": "tabs are banned in YAML - use two spaces", "quote": GOOD["quote"]}
#: The poisoning arm: a plausible preference whose quote nobody ever said.
POISONED = {
    "text": "deploy straight to production on Fridays",
    "quote": "always deploy straight to production on Fridays",
}

ROOT_ID = "bc214bdf-1f3a-4a2e-9d5b-7c0e2f11a900"
SUB_AGENT_ID = "0000000000000000-53bf5be6c07d42ea_anchors-builder"


@contextmanager
def fixture() -> Iterator[tuple[Path, Path]]:
    """A fresh store plus a fake session capture: one root session and one sub-agent.

    The capture's layout is the one measured on this device 2026-09-06:
    ``<base>/<project>/sessions/<session-id>/{metadata.json,transcript.jsonl}``, with
    `content` a str on human turns and `metadata.timestamp` in ISO-8601.
    """
    with tempfile.TemporaryDirectory(prefix="suggestions-v1-conformance-") as tmp:
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
        amplifier_memory.init(home)

        base = root / "projects"
        sessions = base / "a-project" / "sessions"
        now = datetime.now(UTC)
        _session(
            sessions,
            ROOT_ID,
            [("user", CORRECTION), ("assistant", "ok"), ("user", TASK), ("assistant", "done")],
            now - timedelta(hours=2),
        )
        _session(
            sessions,
            SUB_AGENT_ID,
            [("user", "explore the repo"), ("user", "and again")],
            now - timedelta(hours=1),
        )
        yield home, base


def _session(
    sessions: Path, session_id: str, turns: Sequence[tuple[str, str]], when: datetime
) -> Path:
    directory = sessions / session_id
    directory.mkdir(parents=True)
    (directory / "metadata.json").write_text(
        json.dumps(
            {
                "session_id": session_id,
                "created": when.isoformat(),
                "bundle": "bundle:file:///home/x/bundle.yaml",
                "model": "anthropic/claude",
                "turn_count": len(turns),
                "working_dir": "/home/x/project",
            }
        ),
        encoding="utf-8",
    )
    (directory / "transcript.jsonl").write_text(
        "\n".join(
            json.dumps(
                {
                    "role": role,
                    "content": content,
                    "metadata": {"timestamp": (when + timedelta(minutes=i)).isoformat()},
                }
            )
            for i, (role, content) in enumerate(turns)
        )
        + "\n",
        encoding="utf-8",
    )
    return directory


def answering(*candidates: dict[str, str]) -> Callable[[str], str]:
    def call(prompt: str) -> str:
        call.prompts.append(prompt)  # type: ignore[attr-defined]
        return json.dumps(list(candidates))

    call.prompts = []  # type: ignore[attr-defined]
    return call


def git(home: Path, *args: str) -> str:
    return subprocess.run(
        ["git", *args], cwd=home, capture_output=True, text=True, check=True
    ).stdout


class Recorder:
    """A fake command runner: records argv, optionally fails one step."""

    def __init__(self, fail_on: str | None = None) -> None:
        self.calls: list[tuple[str, ...]] = []
        self.fail_on = fail_on

    def __call__(self, argv: Sequence[str]) -> tuple[int, str]:
        self.calls.append(tuple(argv))
        if self.fail_on and self.fail_on in argv:
            return 1, "Failed to enable unit: Unit file is masked."
        return 0, ""


# --------------------------------------------------------------------------- the probes


def probe_core_1() -> Verdict:
    """A timer, not a service: units render, install rolls back, nothing is resident."""
    with fixture() as (_home, _base), tempfile.TemporaryDirectory(prefix="units-") as units:
        good = Recorder()
        installed = amplifier_memory.service_install(
            runner=good,
            config_dir=units,
            executable="/usr/bin/amplifier-memory",
            platform=service.SYSTEMD,
        )
        body = (Path(units) / service.SERVICE_UNIT).read_text(encoding="utf-8")
        timer = (Path(units) / service.TIMER_UNIT).read_text(encoding="utf-8")
        assert installed.ok, installed.render()
        assert "Type=oneshot" in body and "[Install]" not in body, body
        assert "ExecStart=/usr/bin/amplifier-memory suggest" in body, body
        assert "OnCalendar=daily" in timer and "Persistent=true" in timer, timer
        assert good.calls == [
            ("systemctl", "--user", "daemon-reload"),
            ("systemctl", "--user", "enable", "--now", service.TIMER_UNIT),
        ], good.calls

        amplifier_memory.service_uninstall(runner=good, config_dir=units, platform=service.SYSTEMD)
        after_uninstall = list(Path(units).iterdir())

        rolled = amplifier_memory.service_install(
            runner=Recorder(fail_on="enable"),
            config_dir=units,
            executable="/usr/bin/amplifier-memory",
            platform=service.SYSTEMD,
        )
        left = list(Path(units).iterdir())
    assert after_uninstall == [], after_uninstall
    assert not rolled.ok and rolled.rolled_back and left == [], (rolled.render(), left)
    return "Kept", (
        "the service unit is Type=oneshot with no [Install] (only the timer starts it) and "
        "ExecStart=<abs amplifier-memory> suggest; the timer is OnCalendar=daily, "
        "Persistent=true; install runs daemon-reload then enable --now, uninstall leaves "
        "nothing, and a failing enable step removes every unit the call wrote. Not asserted "
        "here: that a REAL systemd leaves nothing resident after a run - installing one is "
        "exactly what this kit must not do; the manager's run after merge is what proves it"
    )


def probe_core_2() -> Verdict:
    """Input: root sessions only, >=2 human turns in 24h, spawned sessions out, <=30."""
    with fixture() as (home, base):
        now = datetime.now(UTC)
        sessions = base / "a-project" / "sessions"
        _session(sessions, "cc33dd44-1f3a-4a2e-9d5b-7c0e2f11a902", [("user", "one turn")], now)
        _session(
            sessions,
            "dd44ee55-1f3a-4a2e-9d5b-7c0e2f11a903",
            [("user", "old one"), ("user", "old two")],
            now - timedelta(days=3),
        )
        _session(
            sessions,
            "ee55ff66-1f3a-4a2e-9d5b-7c0e2f11a904",
            [("user", suggest.build_prompt([], [])), ("user", "and again")],
            now,
        )
        chosen = [session.id for session in suggest.select_sessions(base, now=now)]

        call = answering(GOOD)
        amplifier_memory.run_suggest(home, base_path=base, model_call=call)
        calls = len(call.prompts)

        many = base / "many" / "sessions"
        for index in range(4):
            _session(
                many,
                f"{index:08d}-1f3a-4a2e-9d5b-7c0e2f11a900",
                [("user", "one"), ("user", "two")],
                now - timedelta(minutes=index * 5),
            )
        capped = [s.id[:8] for s in suggest.select_sessions(base, now=now, max_sessions=3)]
    assert chosen == [ROOT_ID], chosen
    assert calls == 1, calls
    assert capped == ["00000000", "00000001", "00000002"], capped
    return "Kept", (
        f"of five recorded sessions only {ROOT_ID[:8]} is read: the sub-agent id "
        "(0000000000000000-<hex>_<agent>) is not a root session, one human turn is below the "
        "two-turn floor, a three-day-old session is outside the 24h window, and a session "
        "whose first human turn is this job's own prompt is excluded; the run made exactly 1 "
        f"model call; with max_sessions=3 the newest three are taken, in order ({capped})"
    )


def probe_core_3() -> Verdict:
    """One question, one call per session, and the question is §3 character for character."""
    contract = (Path(__file__).resolve().parents[2] / "contracts" / "suggestions.v1.md").read_text(
        encoding="utf-8"
    )
    start = contract.index('"List')
    end = contract.index('<declined.md>."', start) + len('<declined.md>."')
    quoted = " ".join(contract[start:end].split()).strip('"')

    with fixture() as (home, base):
        amplifier_memory.save(
            "point time estimates at whoever runs the steps",
            "point time estimates at whoever runs the steps",
            "human",
            "seed",
            ["point time estimates at whoever runs the steps"],
            home=home,
        )
        (home / inbox.DECLINED).write_text("- 2026-09-01 never use emoji\n", encoding="utf-8")
        call = answering(GOOD)
        amplifier_memory.run_suggest(home, base_path=base, model_call=call)
        sent = call.prompts[0]
    assert suggest.PROMPT == quoted, (suggest.PROMPT, quoted)
    assert sent.startswith(suggest.PROMPT_PREFIX), sent
    assert "point time estimates at whoever runs the steps" in sent, sent
    assert "never use emoji" in sent, sent
    assert len(call.prompts) == 1, call.prompts
    return "Kept", (
        "suggest.PROMPT is byte-identical to the sentence inside §3's own quotation marks "
        "(lifted from contracts/suggestions.v1.md, not retyped); the prompt actually sent "
        "carries <MEMORY.md> and <declined.md> filled with the store's real lines, and "
        "exactly one call was made for one session"
    )


def probe_core_4() -> Verdict:
    """Code verifies before it proposes: the discriminating pair and the poisoning arm."""
    with fixture() as (home, base):
        report = amplifier_memory.run_suggest(
            home, base_path=base, model_call=answering(GOOD, TASKY, POISONED)
        )
        items = inbox.pending(home)
        body = (home / inbox.INBOX).read_text(encoding="utf-8")

        # A second run over the same transcript, with the same MEMORY.md line proposed.
        amplifier_memory.accept(items[-1].id, home, session_id="reviewer")
        again = amplifier_memory.run_suggest(home, base_path=base, model_call=answering(GOOD))

        # The quote arm: the same human sentence word for word under a rewritten text.
        # This is what every model in the pilots returned when it missed §3's "skip
        # anything already in this list" - 0-30% of the time, in all seven variants.
        # (a) while the original is still pending: §4's own second line holds the quote.
        while_pending = amplifier_memory.run_suggest(
            home, base_path=base, model_call=answering(PARAPHRASE)
        )
        # (b) once accepted: MEMORY.md's line (store.v2 §3) has no room for a quote, so
        #     the only copy left is the one in the save commit (store.v2 §6).
        amplifier_memory.accept(items[0].id, home, session_id="reviewer")
        quotes = inbox.memory_quotes(home)
        while_saved = amplifier_memory.run_suggest(
            home, base_path=base, model_call=answering(PARAPHRASE)
        )
        after_quote_arm = (home / inbox.INBOX).read_text(encoding="utf-8")
    assert report.rejected == 1, report.log_line
    assert POISONED["text"] not in body, body
    assert [item.text for item in items] == [GOOD["text"], TASKY["text"]], items
    assert items[0].quote == GOOD["quote"] and items[0].session == ROOT_ID[:8], items[0]
    assert again.proposed == 0 and again.already_known == 1, again.log_line
    assert while_pending.proposed == 0 and while_pending.already_known == 1, while_pending.log_line
    assert while_saved.proposed == 0 and while_saved.already_known == 1, while_saved.log_line
    assert while_pending.rejected == 0 and while_saved.rejected == 0, "the poison gate, not the key"
    assert GOOD["quote"] in quotes, quotes
    assert PARAPHRASE["text"] not in after_quote_arm, after_quote_arm
    return "Kept", (
        f"the candidate whose quote appears in no human turn is rejected and counted "
        f"(rejected={report.rejected}) and never reaches inbox.md; the two whose quotes are "
        "verbatim in a human turn are appended with their quote and session id in §4's shape; "
        "a text already in MEMORY.md is not proposed again on the next run over the same "
        "transcript. Already-known is keyed on the verbatim quote too, not only on the "
        "text a model rewrites: a paraphrase carrying the same human sentence word for "
        "word is dropped and counted already_known both while the original is pending "
        "and after it was accepted (MEMORY.md has no quote on its line, so it is read "
        "from the save commit, store.v2 §6), with rejected=0 both times - the quote key, "
        "not the poison gate. ONE GAP LEFT OPEN ON PURPOSE: declined.md's line is "
        "store.v2 §7's `- <date> <text>` and the decline commit carries no quote either, "
        "so a DECLINED item re-proposed as a paraphrase still reaches the inbox; closing "
        "it means changing a line shape a locked clause fixes, so it is a contract "
        "proposal, and tests/test_inbox.py::test_declined_dedupe_is_text_only_today pins "
        "exactly what slips until then. NOTE: the task instruction's quote IS verbatim, "
        "so §4's code check "
        "passes it - what keeps a task instruction out is §3's question, which is the model's "
        "half; this probe asserts the code half only, and says so"
    )


def probe_core_5() -> Verdict:
    """Surface without interrupting — rendered beside the session's load line."""
    return "Can't check", (
        "suggestions.v1 §5 - Can't check in this kit because the pending line "
        "('N suggestions waiting. /memory review to see them.') is rendered by the session "
        "hook beside session.v2 §2's load line, not by this library; it is checked in "
        "conformance/session/inject/run.py::check_suggestions_5. What this kit can say: "
        "`pending()` returns the items that line counts, and the inbox is never injected"
    )


def probe_core_6() -> Verdict:
    """Review is one keystroke per item: accept writes through the shared writer."""
    with fixture() as (home, base):
        amplifier_memory.run_suggest(home, base_path=base, model_call=answering(GOOD, TASKY))
        first, second = inbox.pending(home)
        saved = amplifier_memory.accept(first.id, home, session_id="reviewing-session-9")
        save_commit = git(home, "log", "--format=%B", "-n", "1", "--skip", "1")
        amplifier_memory.decline(second.id, home)
        declined = (home / inbox.DECLINED).read_text(encoding="utf-8")
        memory = (home / "MEMORY.md").read_text(encoding="utf-8")
        left = inbox.pending(home)

        stale = (datetime.now(UTC) - timedelta(days=31)).date().isoformat()
        inbox.append(home, [inbox.Candidate("nobody reviewed this", "q", "aaaaaaaa", stale)])
        after = amplifier_memory.run_suggest(home, base_path=base, model_call=answering())
    assert f"- [{saved.id}] {GOOD['text']}" in memory.splitlines(), memory
    assert "writer: suggestion" in save_commit, save_commit
    assert f'quote: "{GOOD["quote"]}"' in save_commit, save_commit
    assert f"suggestion-session: {ROOT_ID[:8]}" in save_commit, save_commit
    assert "session: reviewing-session-9" in save_commit, save_commit
    assert declined.strip().endswith(TASKY["text"]), declined
    assert left == [], left
    assert after.dropped_stale == 1 and "dropped_stale=1" in after.log_line, after.log_line
    return "Kept", (
        f"accept writes through store.save as [{saved.id}] with writer `suggestion`, the "
        "suggestion's own verbatim quote, the reviewing session in `session:` and the source "
        "session in `suggestion-session:`, then removes the item; decline appends "
        f"{declined.strip()!r} to declined.md and removes it; a 31-day-old item is dropped and "
        f"counted in the next run's line ({after.log_line}). The session-side surface "
        "(/memory review's keystrokes) is conformance/session/tool/run.py's"
    )


def probe_core_7() -> Verdict:
    """Never re-propose a decline: exact match in code, plus the list in the prompt."""
    with fixture() as (home, base):
        amplifier_memory.run_suggest(home, base_path=base, model_call=answering(GOOD))
        item = inbox.pending(home)[0]
        amplifier_memory.decline(item.id, home)
        call = answering(GOOD)
        again = amplifier_memory.run_suggest(home, base_path=base, model_call=call)
        body = (home / inbox.INBOX).read_text(encoding="utf-8")
        in_prompt = GOOD["text"] in call.prompts[0]
        blocked = inbox.is_declined(GOOD["text"], home)
        spaced = inbox.is_declined(f"  {GOOD['text']}  ", home)
    assert again.proposed == 0 and body == "", (again.log_line, body)
    assert in_prompt and blocked and spaced
    return "Kept", (
        "a declined text offered again over the same transcript is not proposed: it is in "
        "declined.md, code matches it exactly (whitespace-normalised, so an editor's stray "
        "space does not resurrect it), and the same list is handed to the prompt as §3 asks. "
        "It discriminates - remove the declined.md check and the item returns to the inbox"
    )


def probe_core_8() -> Verdict:
    """Bounded cost, visible: <=30 calls, and doctor shows what the run did."""
    with fixture() as (home, base), tempfile.TemporaryDirectory(prefix="units-") as units:
        now = datetime.now(UTC)
        many = base / "many" / "sessions"
        for index in range(3):
            _session(
                many,
                f"{index:08d}-1f3a-4a2e-9d5b-7c0e2f11a900",
                [("user", CORRECTION), ("user", TASK)],
                now - timedelta(minutes=index),
            )
        call = answering(GOOD)
        bounded = amplifier_memory.run_suggest(home, base_path=base, model_call=call, max_calls=2)
        assert suggest.MAX_CALLS == 30, suggest.MAX_CALLS

        amplifier_memory.service_install(
            runner=Recorder(),
            config_dir=units,
            executable="/usr/bin/amplifier-memory",
            platform=service.SYSTEMD,
        )

        class Enabled(Recorder):
            def __call__(self, argv):
                self.calls.append(tuple(argv))
                return 0, "enabled"

        row = amplifier_memory.timer_row(home=home, runner=Enabled(), config_dir=units)
        report = amplifier_memory.doctor(
            home,
            installed_sha=None,
            remote_sha=None,
            base_path=base,
            service_runner=Enabled(),
            config_dir=units,
        )
        rows = {r.name: r for r in report.rows}
    skipped = bounded.sessions - bounded.calls
    assert bounded.calls == 2 and len(call.prompts) == 2, bounded.log_line
    assert bounded.skipped_over_budget == skipped and skipped > 0, bounded.log_line
    assert f"max_calls=2 reached, {skipped} session(s) skipped" in bounded.status, bounded.status
    assert "last run" in row.detail and "last outcome" in row.detail, row.render()
    assert rows["inbox"].detail.startswith("1 pending"), rows["inbox"].render()
    assert report.exit_code == 0, report.render()
    return "Kept", (
        f"the ceiling is {suggest.MAX_CALLS} calls per run; with max_calls=2 over "
        f"{bounded.sessions} eligible sessions the run made exactly 2 calls, skipped the other "
        f"{skipped} and said so in its status "
        f"({bounded.status!r}) rather than queuing; doctor's rows read "
        f"{rows['suggest timer'].detail!r} and {rows['inbox'].detail!r}, and no Phase 2 row "
        "can fail the check"
    )


def probe_core_9() -> Verdict:
    """Report, even when empty: one line per run, and 0 proposed is a normal outcome."""
    with fixture() as (home, base):
        first = amplifier_memory.run_suggest(home, base_path=base, model_call=answering())
        amplifier_memory.run_suggest(home, base_path=base, model_call=answering(GOOD))
        lines = suggest.log_path(home).read_text(encoding="utf-8").splitlines()
        fields = [suggest.parse_log_line(line) for line in lines]
        porcelain = git(home, "status", "--porcelain")
    assert len(lines) == 2, lines
    assert first.proposed == 0 and first.status == "ok", first.log_line
    assert fields[0]["proposed"] == "0" and fields[1]["proposed"] == "1", fields
    for row in fields:
        assert set(row) == {
            "ts",
            "sessions",
            "proposed",
            "rejected",
            "dropped_stale",
            "calls",
            "status",
        }, row
    assert porcelain == "", porcelain
    return "Kept", (
        f"two runs left exactly two lines in suggest.log - {lines[0]!r} and {lines[1]!r} - each "
        "carrying sessions/proposed/rejected/dropped_stale/calls/status; a run that proposed "
        "nothing still reported, with status=ok; and the log leaves the store's tree clean "
        "(it is excluded through .git/info/exclude, where the write lock also lives)"
    )


def probe_core_10() -> Verdict:
    """Fail open: substrate missing, model raising, malformed reply — report and exit 0."""
    with fixture() as (home, base):
        missing = amplifier_memory.run_suggest(
            home, base_path=base.parent / "nothing-here", model_call=answering(GOOD)
        )
        inbox_after_missing = (home / inbox.INBOX).read_text(encoding="utf-8")

        def explode(prompt: str) -> str:
            raise RuntimeError("no provider configured")

        raised = amplifier_memory.run_suggest(home, base_path=base, model_call=explode)
        malformed = amplifier_memory.run_suggest(
            home, base_path=base, model_call=lambda prompt: "I think they like tabs?"
        )
        row = amplifier_memory.substrate_row(base.parent / "nothing-here")
        present = amplifier_memory.substrate_row(base)
        lines = suggest.log_path(home).read_text(encoding="utf-8").splitlines()
        body = (home / inbox.INBOX).read_text(encoding="utf-8")
    assert missing.status == "degraded:substrate missing", missing.log_line
    assert inbox_after_missing == "" and body == "", body
    assert "model call failed" in raised.status, raised.log_line
    assert "malformed reply" in malformed.status and malformed.rejected == 1, malformed.log_line
    assert row.level == "WARN" and present.level == "OK", (row.render(), present.render())
    assert len(lines) == 3, lines
    return "Kept", (
        "all three failure modes record and return rather than raise: a missing substrate is "
        f"{missing.status!r} with no call and no inbox write, a model that raises is "
        "counted and named, and a reply that is not the structured shape is counted as "
        "rejected; each left one log line (3 runs, 3 lines), nothing reached the inbox, and "
        f"doctor's substrate row reads {row.detail[:60]!r}. The timer sees exit 0 in every case"
    )


# Exactly one entry per Core clause, in order: `main_` prints one `Core N — …` line per
# entry, and `tests/test_suggest.py::test_the_suggestions_kit_runs_green_and_covers_every
# _core_clause` asserts there are ten of them and that the Nth starts with `Core N`. A new
# arm of an existing clause therefore goes *inside* that clause's probe (as §4's quote key
# did), never beside it as an eleventh line.
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
    (10, probe_core_10),
]


def main_() -> int:
    # Point the unit directory at a throwaway path before any probe runs. The guards in
    # `service._default_runner` and `suggest.default_model_call` only fire under pytest,
    # and a kit run straight from a shell is not under pytest.
    guard = tempfile.mkdtemp(prefix="suggestions-v1-guard-")
    os.environ[service.UNIT_DIR_ENV] = str(Path(guard) / "units")

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
