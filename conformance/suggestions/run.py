#!/usr/bin/env python3
"""suggestions.v2 conformance kit — one line per Core clause, against a fixture substrate.

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

Core 3's host probe is injected the same way and for the same reason: every
`run_suggest` / `resolve_judge` call below passes `help_text=`, so no probe ever shells
out to `amplifier run --help` (this kit runs from a shell, where the pytest guard that
makes `host_help` inert does not fire). `NO_ROLES` is a host that documents no
`--model-role`; `WITH_ROLES` is one that does.
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
from amplifier_memory import inbox, llm_config, service, store, suggest

Verdict = tuple[str, str]

HUMAN_IDENTITY = ("Test Human", "human@example.invalid")

#: The fixture transcript's two human turns: a standing correction, and a task
#: instruction in the same session. suggestions.v2's Conformance section calls this the
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
WORKER_ID = "6bafabaf-1f3a-4a2e-9d5b-7c0e2f11a905"
BRIEFED_ID = "ff77aa88-1f3a-4a2e-9d5b-7c0e2f11a906"

#: Core 3's host probe, injected: what `amplifier run --help` documents. Measured on the
#: steward's device 2026-09-07: `-B/-p/-m` and no `--model-role`, so `NO_ROLES` is this
#: host and `WITH_ROLES` is the one the clause is already written for.
NO_ROLES = "  -p, --provider TEXT   LLM provider to use\n"
WITH_ROLES = NO_ROLES + f"  {suggest.MODEL_ROLE_FLAG} TEXT    Route this run by model role\n"

#: Core 2's first measured non-typed shape: the manager's lane brief that opened worker
#: session 6bafabaf, from which six of the first timer night's seventeen proposals came.
LANE_BRIEF = (
    "Claim drumbeat-d4h from the drumbeat work-tracker project, read its description "
    "and acceptance IN FULL (they are the spec), and work it to a resolution.\n\n"
    "Worker session, alone, in your own worktree. Never merge to main.\n\n"
    + ("Read first: PINS.md, AGENTS.md, and the contract this item names. " * 40)
    + "\n\nFinal act: DONE.json (valid JSON) in the worktree root.\n"
)

#: Core 2's second: a `/goal` continuation turn that is only the harness's own reminders.
REMINDER_ONLY = (
    "<system-reminders>\n"
    '<system-reminder source="hooks-status-context">\n'
    "Today's date: 2026-09-07\n"
    "</system-reminder>\n"
    "</system-reminders>"
)


@contextmanager
def fixture() -> Iterator[tuple[Path, Path]]:
    """A fresh store plus a fake session capture: one root session and one sub-agent.

    The capture's layout is the one measured on this device 2026-09-06:
    ``<base>/<project>/sessions/<session-id>/{metadata.json,transcript.jsonl}``, with
    `content` a str on human turns and `metadata.timestamp` in ISO-8601.
    """
    with tempfile.TemporaryDirectory(prefix="suggestions-v2-conformance-") as tmp:
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
        # The LLM-call knob lives INSIDE the instance (store.v3 §2): `init` writes
        # `<instance>/config.yaml` with the shipped defaults, and every probe below reads
        # that temp file - never this device's own instance, and never a real provider id.

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
    sessions: Path,
    session_id: str,
    turns: Sequence[tuple[str, str]],
    when: datetime,
    turn_times: Sequence[datetime | None] | None = None,
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
    stamps = turn_times or [when - timedelta(minutes=len(turns) - i - 1) for i in range(len(turns))]
    assert len(stamps) == len(turns)
    (directory / "transcript.jsonl").write_text(
        "\n".join(
            json.dumps(
                {
                    "role": role,
                    "content": content,
                    "metadata": {"timestamp": stamp.isoformat()} if stamp is not None else {},
                }
            )
            for (role, content), stamp in zip(turns, stamps, strict=True)
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
    """Input: human origin, >=2 TYPED-TEXT turns in 24h, root only, spawned out, <=30."""
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
        # (a) recorded origin `worker` - the shape that produced 6 of 17 proposals.
        _session(sessions, WORKER_ID, [("user", CORRECTION), ("user", TASK)], now)
        store.record_session(home, WORKER_ID, origin="worker")
        # ... and a session recorded `human`, to prove the record is read, not ignored.
        store.record_session(home, ROOT_ID, origin="human")
        # (b) typed text: a lane brief plus reminder-only turns is zero typed turns.
        _session(
            sessions,
            BRIEFED_ID,
            [("user", LANE_BRIEF), ("assistant", "on it"), ("user", REMINDER_ONLY)],
            now,
        )

        origins = store.session_origins(home)
        selected = suggest.select_sessions(base, now=now, origins=origins)
        chosen, refused = selected.ids, selected.origin_excluded
        unrecorded = suggest.select_sessions(base, now=now).ids

        call = answering(GOOD)
        report = amplifier_memory.run_suggest(
            home, base_path=base, model_call=call, help_text=NO_ROLES
        )
        calls = len(call.prompts)
        sent = call.prompts[0]

        many = base / "many" / "sessions"
        for index in range(4):
            _session(
                many,
                f"{index:08d}-1f3a-4a2e-9d5b-7c0e2f11a900",
                [("user", "one"), ("user", "two")],
                now - timedelta(minutes=index * 5),
            )
        capped = [
            s.id[:8]
            for s in suggest.select_sessions(base, now=now, max_sessions=3, origins=origins)
        ]

        # The window is a boundary on the turns supplied to the judge and verifier, not
        # merely a session-level eligibility count. This deliberately returns an old
        # quote that remains in the session record: it must be rejected because the
        # quote is outside the same window the judge saw.
        window_base = home.parent / "window-projects"
        window_id = "12345678-2222-3333-4444-555555555555"
        old = "old correction"
        recent_one = "recent preference one"
        recent_two = "recent preference two"
        future = "future correction"
        _session(
            window_base / "p" / "sessions",
            window_id,
            [("user", old), ("user", recent_one), ("user", recent_two), ("user", future)],
            now,
            [
                now - timedelta(days=2),
                now - timedelta(hours=1),
                now,
                now + timedelta(seconds=1),
            ],
        )
        window_call = answering(
            {"text": "old result", "quote": old},
            {"text": "future result", "quote": future},
        )
        windowed = amplifier_memory.run_suggest(
            home, base_path=window_base, now=now, model_call=window_call, help_text=NO_ROLES
        )
        window_request = window_call.prompts[0]
    assert chosen == [ROOT_ID], chosen
    assert refused == 1, refused
    assert WORKER_ID not in chosen and BRIEFED_ID not in chosen, chosen
    # No record counts as `human`: with no origins map at all the worker session is read.
    assert WORKER_ID in unrecorded and BRIEFED_ID not in unrecorded, unrecorded
    assert calls == 1, calls
    assert report.origin_excluded == 1 and report.sessions == 1, report.log_line
    assert "Claim drumbeat-d4h" not in sent and "system-reminder" not in sent, sent[:200]
    assert suggest.is_typed_text(CORRECTION) and not suggest.is_typed_text(LANE_BRIEF)
    assert not suggest.is_typed_text(REMINDER_ONLY)
    assert capped == ["00000000", "00000001", "00000002"], capped
    assert (windowed.sessions, windowed.calls, windowed.proposed, windowed.rejected) == (1, 1, 0, 2)
    assert recent_one in window_request and recent_two in window_request, window_request
    assert old not in window_request and future not in window_request, window_request
    return "Kept", (
        f"of seven recorded sessions only {ROOT_ID[:8]} is read. Refused: {WORKER_ID[:8]}, "
        "whose sessions.jsonl origin is `worker` (counted, origin_excluded=1 in the run's "
        f"line); {BRIEFED_ID[:8]}, whose turns are a lane brief (opens 'Claim <id> from the "
        "<project> work-tracker project', >1500 chars) and a system-reminder-only "
        "continuation, so it has zero typed-text turns; the sub-agent id "
        "(0000000000000000-<hex>_<agent>); one human turn (below the two-turn floor); a "
        "three-day-old session (outside 24h); and a session whose first human turn is this "
        "job's own prompt. It discriminates in both directions: with NO origins map the "
        "worker session IS read, because `no record counts as human`, while the briefed one "
        "is still refused. The run made exactly 1 model call, and neither the brief nor the "
        f"reminders appear in the request the judge saw; with max_sessions=3 the newest "
        f"three are taken, in order ({capped}). The window probe has exactly two typed "
        "turns inside its closed interval, plus one old and one future turn: the judge "
        "saw only the two recent turns, and fake old and future quotes were rejected (not proposed)"
    )


def probe_core_3() -> Verdict:
    """One question, one call per session, and the question is §3 character for character."""
    contract = (Path(__file__).resolve().parents[2] / "contracts" / "suggestions.v2.md").read_text(
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
        amplifier_memory.run_suggest(home, base_path=base, model_call=call, help_text=NO_ROLES)
        sent = call.prompts[0]

        # "Which model answers it" is the rest of §3, in its own order.
        shipped = llm_config.load(home)
        inherited = suggest.resolve_judge(shipped, help_text=NO_ROLES)
        by_role = suggest.resolve_judge(shipped, help_text=WITH_ROLES)
        (home / llm_config.CONFIG_NAME).write_text(
            'llm:\n  judge:\n    provider: "luna"\n    model: "gpt-5.6-luna"\n', encoding="utf-8"
        )
        configured = suggest.resolve_judge(llm_config.load(home), help_text=WITH_ROLES)
    assert suggest.PROMPT == quoted, (suggest.PROMPT, quoted)
    assert sent.startswith(suggest.PROMPT_PREFIX), sent
    assert "point time estimates at whoever runs the steps" in sent, sent
    assert "never use emoji" in sent, sent
    assert len(call.prompts) == 1, call.prompts
    # 1. provider/model/bundle when set.
    assert configured.source == "config" and configured.name == "luna", configured
    assert configured.flags() == ["-p", "luna", "-m", "gpt-5.6-luna"], configured.flags()
    # 2. else the role, when the host can resolve one. Shipped: `fast`, never a provider id.
    assert by_role.source == "role" and by_role.name == "role:fast", by_role
    assert by_role.flags() == [suggest.MODEL_ROLE_FLAG, "fast"], by_role.flags()
    assert shipped.call(llm_config.JUDGE).provider == "", shipped
    # 3. else the app's own default, inherited - adding no flag at all.
    assert inherited.source == suggest.INHERITED and inherited.flags() == [], inherited
    assert suggest.build_argv("r", inherited) == [*suggest.RUN_ARGV, "r"]
    return "Kept", (
        "suggest.PROMPT is byte-identical to the sentence inside §3's own quotation marks "
        "(lifted from contracts/suggestions.v2.md, not retyped); the prompt actually sent "
        "carries <MEMORY.md> and <declined.md> filled with the store's real lines, and "
        "exactly one call was made for one session. Which model answers it follows §3's "
        "order over the INSTANCE's config.yaml (store.v3 §2): provider/model set -> "
        "`-p luna -m gpt-5.6-luna`; unset on a host whose `amplifier run --help` documents "
        f"{suggest.MODEL_ROLE_FLAG} -> `{suggest.MODEL_ROLE_FLAG} fast`, the shipped ROLE; "
        "unset on a host without it -> inherited, adding no flag, so the argv is byte for "
        "byte what it always was. The shipped default carries no provider id, because a "
        "provider id names one machine's account"
    )


def probe_core_4() -> Verdict:
    """Code verifies before it proposes: the discriminating pair and the poisoning arm."""
    with fixture() as (home, base):
        report = amplifier_memory.run_suggest(
            home, base_path=base, model_call=answering(GOOD, TASKY, POISONED), help_text=NO_ROLES
        )
        items = inbox.pending(home)
        body = (home / inbox.INBOX).read_text(encoding="utf-8")

        # A second run over the same transcript, with the same MEMORY.md line proposed.
        amplifier_memory.accept(items[-1].id, home, session_id="reviewer")
        again = amplifier_memory.run_suggest(
            home, base_path=base, model_call=answering(GOOD), help_text=NO_ROLES
        )

        # The quote arm: the same human sentence word for word under a rewritten text.
        # This is what every model in the pilots returned when it missed §3's "skip
        # anything already in this list" - 0-30% of the time, in all seven variants.
        # (a) while the original is still pending: §4's own second line holds the quote.
        while_pending = amplifier_memory.run_suggest(
            home, base_path=base, model_call=answering(PARAPHRASE), help_text=NO_ROLES
        )
        # (b) once accepted: MEMORY.md's line (store.v2 §3) has no room for a quote, so
        #     the only copy left is the one in the save commit (store.v2 §6).
        amplifier_memory.accept(items[0].id, home, session_id="reviewer")
        quotes = inbox.memory_quotes(home)
        while_saved = amplifier_memory.run_suggest(
            home, base_path=base, model_call=answering(PARAPHRASE), help_text=NO_ROLES
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
        "not the poison gate. A DECLINED item is keyed on both fields too since store.v3 "
        "§7 put the verbatim quote on declined.md's line (`- <date> <text>  quote: "
        '"<quote>"`, matched on text OR quote), so a decline re-proposed as a paraphrase '
        "no longer reaches the inbox either - conformance/store/run.py::probe_core_7 and "
        "tests/test_inbox.py::test_a_declined_quote_blocks_the_same_quote_reworded prove "
        "that arm. NOTE: the task instruction's quote IS verbatim, "
        "so §4's code check "
        "passes it - what keeps a task instruction out is §3's question, which is the model's "
        "half; this probe asserts the code half only, and says so"
    )


def probe_core_5() -> Verdict:
    """Surface without interrupting — rendered beside the session's load line."""
    return "Can't check", (
        "suggestions.v2 §5 - Can't check in this kit because the pending line "
        "('N suggestions waiting. /memory review to see them.') is rendered by the session "
        "hook beside session.v4 §2's load line, not by this library; it is checked in "
        "conformance/session/inject/run.py::check_suggestions_5. What this kit can say: "
        "`pending()` returns the items that line counts, and the inbox is never injected"
    )


def probe_core_6() -> Verdict:
    """Review is one keystroke per item: accept writes through the shared writer."""
    with fixture() as (home, base):
        amplifier_memory.run_suggest(
            home, base_path=base, model_call=answering(GOOD, TASKY), help_text=NO_ROLES
        )
        first, second = inbox.pending(home)
        saved = amplifier_memory.accept(first.id, home, session_id="reviewing-session-9")
        save_commit = git(home, "log", "--format=%B", "-n", "1", "--skip", "1")
        amplifier_memory.decline(second.id, home)
        declined = (home / inbox.DECLINED).read_text(encoding="utf-8")
        memory = (home / "MEMORY.md").read_text(encoding="utf-8")
        left = inbox.pending(home)

        stale = (datetime.now(UTC) - timedelta(days=31)).date().isoformat()
        inbox.append(home, [inbox.Candidate("nobody reviewed this", "q", "aaaaaaaa", stale)])
        after = amplifier_memory.run_suggest(
            home, base_path=base, model_call=answering(), help_text=NO_ROLES
        )
    assert f"- [{saved.id}] {GOOD['text']}" in memory.splitlines(), memory
    assert "writer: suggestion" in save_commit, save_commit
    assert f'quote: "{GOOD["quote"]}"' in save_commit, save_commit
    assert f"suggestion-session: {ROOT_ID[:8]}" in save_commit, save_commit
    assert "session: reviewing-session-9" in save_commit, save_commit
    # store.v3 §7: the line carries the verbatim quote after the text.
    assert declined.strip().endswith(f'{TASKY["text"]}  quote: "{TASKY["quote"]}"'), declined
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
        amplifier_memory.run_suggest(
            home, base_path=base, model_call=answering(GOOD), help_text=NO_ROLES
        )
        item = inbox.pending(home)[0]
        amplifier_memory.decline(item.id, home)
        call = answering(GOOD)
        again = amplifier_memory.run_suggest(
            home, base_path=base, model_call=call, help_text=NO_ROLES
        )
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
        bounded = amplifier_memory.run_suggest(
            home, base_path=base, model_call=call, max_calls=2, help_text=NO_ROLES
        )
        assert suggest.MAX_CALLS == 30, suggest.MAX_CALLS

        # "and names the judge" - the library owns the sentence; doctor's row is a thin
        # adapter over it (AGENTS.md rule 11), so the CLI and the log cannot disagree.
        shipped = llm_config.load(home)
        named_inherited = suggest.judge_detail(shipped, help_text=NO_ROLES)
        named_role = suggest.judge_detail(shipped, help_text=WITH_ROLES)
        (home / llm_config.CONFIG_NAME).write_text(
            'llm:\n  judge:\n    provider: "luna"\n', encoding="utf-8"
        )
        named_provider = suggest.judge_detail(llm_config.load(home), help_text=NO_ROLES)

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

        # store.v3 §11's discriminating pair belongs here too: the enabled pass above
        # makes calls, then the same instance is switched off and must not even discover
        # the fixture capture. The fake model and the patched discovery door make either
        # regression visible without touching a real session or model.
        before_disabled = suggest.log_path(home).read_text(encoding="utf-8").splitlines()
        (home / llm_config.CONFIG_NAME).write_text(
            llm_config.default_body(enabled=False), encoding="utf-8"
        )
        disabled_call = answering(GOOD)

        def capture_was_touched(*_args: object, **_kwargs: object) -> Path:
            raise AssertionError("disabled pass discovered the session capture")

        original_substrate_root = suggest.substrate_root
        suggest.substrate_root = capture_was_touched
        try:
            disabled = amplifier_memory.run_suggest(
                home, base_path=base, model_call=disabled_call, help_text=NO_ROLES
            )
        finally:
            suggest.substrate_root = original_substrate_root
        disabled_lines = suggest.log_path(home).read_text(encoding="utf-8").splitlines()
    skipped = bounded.sessions - bounded.calls
    assert bounded.calls == 2 and len(call.prompts) == 2, bounded.log_line
    assert bounded.skipped_over_budget == skipped and skipped > 0, bounded.log_line
    assert f"max_calls=2 reached, {skipped} session(s) skipped" in bounded.status, bounded.status
    assert "last run" in row.detail and "last outcome" in row.detail, row.render()
    assert rows["inbox"].detail.startswith("1 pending"), rows["inbox"].render()
    assert report.exit_code == 0, report.render()
    # The judge, named, in all three states - including what an inherited night costs.
    assert suggest.INHERITED in named_inherited, named_inherited
    assert f"${suggest.INHERITED_COST_USD:.3f}/call" in named_inherited, named_inherited
    assert suggest.INHERITED_COST_SOURCE in named_inherited, named_inherited
    assert f"${suggest.INHERITED_COST_USD * suggest.MAX_CALLS:.2f}" in named_inherited
    assert suggest.MODEL_ROLE_FLAG in named_role and "role fast" in named_role, named_role
    assert "provider luna" in named_provider, named_provider
    assert disabled_call.prompts == [], "a disabled instance spent a model call"
    assert disabled.status == f"disabled:instance={home} (enabled: false)", disabled.log_line
    assert not disabled.degraded and disabled_lines == [*before_disabled, disabled.log_line], (
        disabled_lines
    )
    return "Kept", (
        f"the ceiling is {suggest.MAX_CALLS} calls per run; with max_calls=2 over "
        f"{bounded.sessions} eligible sessions the run made exactly 2 calls, skipped the other "
        f"{skipped} and said so in its status "
        f"({bounded.status!r}) rather than queuing; doctor's rows read "
        f"{rows['suggest timer'].detail!r} and {rows['inbox'].detail!r}, and no Phase 2 row "
        "can fail the check. The judge is NAMED in all three states by one library "
        "function, `suggest.judge_detail`, which doctor's `llm judge` row is a thin adapter "
        f"over: a configured provider ({named_provider!r}); the role this host resolved "
        f"({named_role!r}); or inherited, with the app's default AND its measured per-call "
        f"cost - ${suggest.INHERITED_COST_USD:.3f}/call from "
        f"{suggest.INHERITED_COST_SOURCE}, up to "
        f"${suggest.INHERITED_COST_USD * suggest.MAX_CALLS:.2f} for a full night - so an "
        "unattended night's bill is read before the night, never after it. store.v3 §11's "
        f"discriminating pair measured enabled calls={len(call.prompts)} versus disabled "
        f"calls={len(disabled_call.prompts)}; the disabled pass did not discover the capture and "
        f"added one deliberate outcome line ({disabled.log_line!r}), never `degraded:`"
    )


def probe_core_9() -> Verdict:
    """Report, even when empty: one line per run, `origin_excluded=` beside `sessions=`."""
    with fixture() as (home, base):
        # A refused session, so the count in the line is a real number and not a zero
        # that any implementation would print.
        _session(
            base / "a-project" / "sessions",
            WORKER_ID,
            [("user", CORRECTION), ("user", TASK)],
            datetime.now(UTC),
        )
        store.record_session(home, WORKER_ID, origin="worker")
        first = amplifier_memory.run_suggest(
            home, base_path=base, model_call=answering(), help_text=NO_ROLES
        )
        amplifier_memory.run_suggest(
            home, base_path=base, model_call=answering(GOOD), help_text=NO_ROLES
        )
        lines = suggest.log_path(home).read_text(encoding="utf-8").splitlines()
        fields = [suggest.parse_log_line(line) for line in lines]
        porcelain = git(home, "status", "--porcelain")
        old = suggest.parse_log_line(
            "2026-09-06T09:00:04+00:00 sessions=3 proposed=1 rejected=2 "
            "dropped_stale=0 calls=3 status=ok"
        )
    assert len(lines) == 2, lines
    assert first.proposed == 0 and first.status == "ok", first.log_line
    assert fields[0]["proposed"] == "0" and fields[1]["proposed"] == "1", fields
    for row in fields:
        # `origin_excluded` sits beside `sessions`, where Core 9 puts it; `provider` names
        # which model the run's calls were billed to (Core 8, visible cost); `model=` joins
        # the line only when the config named one, and none of them displaces a field that
        # was there before - `status` is still last.
        assert set(row) == {
            "ts",
            "sessions",
            "origin_excluded",
            "proposed",
            "rejected",
            "dropped_stale",
            "calls",
            "provider",
            "status",
        }, row
        assert row["origin_excluded"] == "1", row
        assert row["provider"] == suggest.INHERITED, row
        assert " sessions=1 origin_excluded=1 " in lines[fields.index(row)], lines
    assert porcelain == "", porcelain
    assert "origin_excluded" not in old and old["status"] == "ok", old
    return "Kept", (
        f"two runs left exactly two lines in suggest.log - {lines[0]!r} and {lines[1]!r} - "
        "each carrying sessions/origin_excluded/proposed/rejected/dropped_stale/calls/"
        "provider/status, with `origin_excluded=1` beside `sessions=1` for the one session "
        "refused by origin, and `provider=inherited` naming which model was billed; a run "
        "that proposed nothing still reported, with status=ok; a line written before either "
        "field existed still parses (it simply lacks the keys), and `status` is still last "
        "so a degraded run's own sentence cannot swallow a field; and the log leaves the "
        "store's tree clean (excluded through .git/info/exclude, where the write lock lives)"
    )


def probe_core_10() -> Verdict:
    """Fail open: substrate missing, model raising, malformed reply — report and exit 0."""
    with fixture() as (home, base):
        missing = amplifier_memory.run_suggest(
            home,
            base_path=base.parent / "nothing-here",
            model_call=answering(GOOD),
            help_text=NO_ROLES,
        )
        inbox_after_missing = (home / inbox.INBOX).read_text(encoding="utf-8")

        def explode(prompt: str) -> str:
            raise RuntimeError("no provider configured")

        raised = amplifier_memory.run_suggest(
            home, base_path=base, model_call=explode, help_text=NO_ROLES
        )
        malformed = amplifier_memory.run_suggest(
            home,
            base_path=base,
            model_call=lambda prompt: "I think they like tabs?",
            help_text=NO_ROLES,
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
    guard = tempfile.mkdtemp(prefix="suggestions-v2-guard-")
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
