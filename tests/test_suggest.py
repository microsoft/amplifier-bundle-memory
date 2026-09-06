"""suggestions.v1 Core 2, 3, 4, 8, 9, 10 — the daily pass, against a fixture substrate.

Nothing here calls a model: every test injects `model_call`, and
`suggest.default_model_call` refuses outright under pytest (a guard written after the
cli.v2 Core 6 probe enabled a real timer on this device on 2026-09-06). Nothing here
reads this machine's real sessions either: `base_path` is a temp tree built by
`substrate` below, whose layout is the one measured on this device the same day.

The discriminating pair the contract asks for lives in `substrate`: one transcript
carries **an explicit standing correction** and **a task instruction**, and the fake
model returns both, plus a poisoned candidate whose quote nobody ever said.
"""

from __future__ import annotations

import json
import subprocess
import sys
from collections.abc import Callable, Sequence
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

import amplifier_memory
from amplifier_memory import inbox, suggest

CONTRACT = Path(__file__).resolve().parents[1] / "contracts" / "suggestions.v1.md"

#: The human's two turns. The first is a standing preference; the second is a task
#: instruction, which Core 3 tells the model to skip and Core 4 never sees.
CORRECTION = "stop reformatting my YAML - never use tabs in YAML files I ask you to write"
TASK = "now add a --verbose flag to the parser and run the tests"
#: A candidate the model invented: nothing like this appears in any human turn.
POISON_QUOTE = "always deploy straight to production on Fridays"


def write_session(
    sessions: Path,
    session_id: str,
    turns: Sequence[tuple[str, str]],
    *,
    when: datetime,
    bundle: str = "bundle:file:///home/x/bundle.yaml",
) -> Path:
    """One recorded session, in the layout measured on this device 2026-09-06."""
    directory = sessions / session_id
    directory.mkdir(parents=True)
    (directory / "metadata.json").write_text(
        json.dumps(
            {
                "session_id": session_id,
                "created": when.isoformat(),
                "bundle": bundle,
                "model": "anthropic/claude",
                "turn_count": len(turns),
                "working_dir": "/home/x/project",
            }
        ),
        encoding="utf-8",
    )
    lines = [
        json.dumps(
            {
                "role": role,
                "content": content,
                "metadata": {"timestamp": (when + timedelta(minutes=index)).isoformat()},
            }
        )
        for index, (role, content) in enumerate(turns)
    ]
    (directory / "transcript.jsonl").write_text("\n".join(lines) + "\n", encoding="utf-8")
    return directory


ROOT_ID = "bc214bdf-1f3a-4a2e-9d5b-7c0e2f11a900"
OTHER_ROOT = "aa11bb22-1f3a-4a2e-9d5b-7c0e2f11a901"
SUB_AGENT_ID = "0000000000000000-53bf5be6c07d42ea_anchors-builder"


@pytest.fixture
def substrate(tmp_path: Path) -> Path:
    """A fake `~/.amplifier/projects`: one root session, one sub-agent, both recent."""
    base = tmp_path / "projects"
    sessions = base / "a-project" / "sessions"
    now = datetime.now(UTC)
    write_session(
        sessions,
        ROOT_ID,
        [
            ("user", CORRECTION),
            ("assistant", "understood"),
            ("user", TASK),
            ("assistant", "done"),
        ],
        when=now - timedelta(hours=2),
    )
    write_session(
        sessions,
        SUB_AGENT_ID,
        [("user", "explore the repo and report"), ("user", "again please")],
        when=now - timedelta(hours=1),
    )
    return base


def model_returning(*candidates: dict[str, str]) -> Callable[[str], str]:
    """A fake model: records the prompt it was given, answers with a fixed JSON list."""

    def call(prompt: str) -> str:
        call.prompts.append(prompt)  # type: ignore[attr-defined]
        return json.dumps(list(candidates))

    call.prompts = []  # type: ignore[attr-defined]
    return call


GOOD = {"text": "never use tabs in YAML files", "quote": "never use tabs in YAML files I ask you to write"}
TASKY = {"text": "add a --verbose flag to the parser", "quote": TASK}
POISONED = {"text": "deploy to production on Fridays", "quote": POISON_QUOTE}


# ---------------------------------------------------------------- Core 3: the question


def test_the_prompt_is_section_3_verbatim() -> None:
    """The sentence is lifted from the contract file, not retyped, so drift fails here."""
    body = CONTRACT.read_text(encoding="utf-8")
    start = body.index('"List')
    end = body.index('<declined.md>."', start) + len('<declined.md>."')
    quoted = " ".join(body[start:end].split()).strip('"')
    print(f"--- contract §3 ---\n{quoted}\n--- PROMPT ---\n{suggest.PROMPT}")
    assert suggest.PROMPT == quoted
    assert suggest.PROMPT.startswith(suggest.PROMPT_PREFIX)

    filled = suggest.build_prompt(["a memory"], ["a decline"])
    print(f"--- filled ---\n{filled}")
    assert filled.startswith(suggest.PROMPT_PREFIX)
    assert "<MEMORY.md: a memory>" in filled and "<declined.md: a decline>" in filled


def test_the_default_argv_matches_amplifier_run_help() -> None:
    """AGENTS.md rule 5: the argv is checked against that CLI's own --help, output shown.

    The lesson this rule exists for: `amplifier run --once` did not exist and shipped
    anyway. The flag here is `--output-format`, not `--output`.
    """
    proc = subprocess.run(
        ["amplifier", "run", "--help"], capture_output=True, text=True, check=False
    )
    if proc.returncode != 0:
        pytest.skip(f"no `amplifier` on this PATH: {proc.stderr.strip()[:120]}")
    print(proc.stdout)
    assert suggest.RUN_ARGV == ("amplifier", "run", "--output-format", "json")
    assert "--output-format" in proc.stdout
    assert "[text|json|json-trace]" in proc.stdout


def test_the_default_model_call_refuses_to_run_from_a_test() -> None:
    with pytest.raises(RuntimeError, match="refusing to call the model from a test"):
        suggest.default_model_call("anything")
    print("default_model_call under pytest: refused, loudly")


# ---------------------------------------------------------------- Core 2: what is read


def test_only_root_sessions_with_two_recent_human_turns_are_read(substrate: Path) -> None:
    now = datetime.now(UTC)
    sessions = substrate / "a-project" / "sessions"
    write_session(  # one human turn only
        sessions, "cc33dd44-1f3a-4a2e-9d5b-7c0e2f11a902", [("user", "hi")], when=now
    )
    write_session(  # two turns, but three days ago
        sessions,
        "dd44ee55-1f3a-4a2e-9d5b-7c0e2f11a903",
        [("user", "old one"), ("user", "old two")],
        when=now - timedelta(days=3),
    )
    write_session(  # spawned by this job: its first human turn is the §3 prompt
        sessions,
        "ee55ff66-1f3a-4a2e-9d5b-7c0e2f11a904",
        [("user", suggest.build_prompt([], [])), ("user", "again")],
        when=now,
    )
    chosen = [session.id for session in suggest.select_sessions(substrate, now=now)]
    print("selected:", chosen)
    assert chosen == [ROOT_ID], "only the root session with two recent human turns"
    assert not suggest.is_root_session_id(SUB_AGENT_ID)


def test_at_most_max_sessions_most_recent_first(tmp_path: Path) -> None:
    base = tmp_path / "projects"
    sessions = base / "p" / "sessions"
    now = datetime.now(UTC)
    for index in range(5):
        write_session(
            sessions,
            f"{index:08d}-1f3a-4a2e-9d5b-7c0e2f11a900",
            [("user", "one"), ("user", "two")],
            when=now - timedelta(minutes=index * 10),
        )
    chosen = [s.id[:8] for s in suggest.select_sessions(base, now=now, max_sessions=3)]
    print("selected (newest first, capped at 3):", chosen)
    assert chosen == ["00000000", "00000001", "00000002"]


# ---------------------------------------------------------------- Core 4: verification


def test_the_discriminating_pair_and_the_poisoning_arm(store: Path, substrate: Path) -> None:
    """A standing correction lands with its verbatim quote; a task instruction does not.

    The task instruction's quote IS verbatim, so §4's code check passes it — what keeps
    it out is the model's own answer to §3's question. The poisoned candidate is the one
    code refuses: its quote appears in no human turn, so it is rejected and counted, and
    a model that invents a preference cannot reach the inbox.
    """
    call = model_returning(GOOD, POISONED)
    report = amplifier_memory.run_suggest(store, base_path=substrate, model_call=call)
    body = (store / "inbox.md").read_text(encoding="utf-8")
    print(f"--- prompt sent ---\n{call.prompts[0]}")
    print(f"--- inbox.md ---\n{body}")
    print("--- log line ---\n" + report.log_line)

    items = inbox.pending(store)
    assert len(items) == 1 and items[0].id == "s-001"
    assert items[0].text == GOOD["text"]
    assert items[0].quote == GOOD["quote"]
    assert items[0].session == ROOT_ID[:8]
    assert TASK not in body and POISON_QUOTE not in body
    assert (report.sessions, report.proposed, report.rejected, report.calls) == (1, 1, 1, 1)
    assert report.status == "ok"
    assert len(call.prompts) == 1, "Core 3: one call per session"


def test_the_sub_agent_session_is_never_read(store: Path, substrate: Path) -> None:
    call = model_returning(GOOD)
    amplifier_memory.run_suggest(store, base_path=substrate, model_call=call)
    print(f"{len(call.prompts)} call(s) for a substrate holding 1 root + 1 sub-agent session")
    assert len(call.prompts) == 1


def test_a_declined_text_is_not_proposed_on_a_second_run(store: Path, substrate: Path) -> None:
    """Core 7, end to end: propose, decline, run again over the same transcript."""
    first = amplifier_memory.run_suggest(
        store, base_path=substrate, model_call=model_returning(GOOD)
    )
    item = inbox.pending(store)[0]
    inbox.decline(item.id, store)
    print("--- declined.md ---\n" + (store / "declined.md").read_text(encoding="utf-8"))

    second = amplifier_memory.run_suggest(
        store, base_path=substrate, model_call=model_returning(GOOD)
    )
    body = (store / "inbox.md").read_text(encoding="utf-8")
    print(f"--- inbox.md after the second run ---\n{body or '(empty)'}")
    print(first.log_line)
    print(second.log_line)
    assert second.proposed == 0 and inbox.pending(store) == []
    assert second.already_known == 1, "the survivor was dropped as already declined"


def test_a_malformed_reply_is_counted_and_the_run_goes_degraded(store: Path, substrate: Path) -> None:
    report = amplifier_memory.run_suggest(
        store, base_path=substrate, model_call=lambda prompt: "I think they like tabs?"
    )
    print(report.log_line)
    assert report.rejected == 1 and report.proposed == 0
    assert report.status.startswith("degraded:") and "malformed reply" in report.status
    assert not (store / "inbox.md").read_text(encoding="utf-8")


def test_a_model_that_raises_is_counted_and_the_run_still_ends(store: Path, substrate: Path) -> None:
    def explode(prompt: str) -> str:
        raise RuntimeError("no provider configured")

    report = amplifier_memory.run_suggest(store, base_path=substrate, model_call=explode)
    print(report.log_line)
    assert report.status.startswith("degraded:") and "model call failed" in report.status
    assert report.proposed == 0 and suggest.last_log_line(store) == report.log_line


# ---------------------------------------------------------------- Core 8: the bounds


def test_exceeding_max_calls_skips_the_rest_and_reports(tmp_path: Path, store: Path) -> None:
    base = tmp_path / "projects"
    sessions = base / "p" / "sessions"
    now = datetime.now(UTC)
    for index in range(3):
        write_session(
            sessions,
            f"{index:08d}-1f3a-4a2e-9d5b-7c0e2f11a900",
            [("user", CORRECTION), ("user", TASK)],
            when=now - timedelta(minutes=index),
        )
    call = model_returning(GOOD)
    report = amplifier_memory.run_suggest(store, base_path=base, model_call=call, max_calls=2)
    print(report.log_line)
    assert report.sessions == 3 and report.calls == 2 and len(call.prompts) == 2
    assert report.skipped_over_budget == 1
    assert "max_calls=2 reached, 1 session(s) skipped" in report.status


# ---------------------------------------------------------------- Core 9/10: the report


def test_every_run_writes_exactly_one_log_line_even_when_empty(store: Path, substrate: Path) -> None:
    amplifier_memory.run_suggest(store, base_path=substrate, model_call=model_returning())
    amplifier_memory.run_suggest(store, base_path=substrate, model_call=model_returning())
    lines = suggest.log_path(store).read_text(encoding="utf-8").splitlines()
    print("--- suggest.log ---\n" + "\n".join(lines))
    assert len(lines) == 2
    for line in lines:
        fields = suggest.parse_log_line(line)
        assert set(fields) == {"ts", "sessions", "proposed", "rejected", "dropped_stale", "calls", "status"}
        assert fields["proposed"] == "0" and fields["status"] == "ok"


def test_the_log_never_dirties_the_store(store: Path, substrate: Path) -> None:
    """suggest.log is a run log, not memory (store.v2 §2) — and never a dirty tree."""
    amplifier_memory.run_suggest(store, base_path=substrate, model_call=model_returning(GOOD))
    porcelain = subprocess.run(
        ["git", "status", "--porcelain"], cwd=store, capture_output=True, text=True, check=True
    ).stdout
    exclude = (store / ".git" / "info" / "exclude").read_text(encoding="utf-8")
    print(f"git status --porcelain: {porcelain!r}")
    print(f"--- .git/info/exclude ---\n{exclude}")
    assert porcelain == ""
    assert "suggest.log" in exclude.splitlines()


def test_substrate_missing_is_degraded_exit_0_and_no_inbox_write(store: Path, tmp_path: Path) -> None:
    """Core 10's named case: the report says so, nothing is proposed, doctor shows it."""
    report = amplifier_memory.run_suggest(
        store, base_path=tmp_path / "nothing-here", model_call=model_returning(GOOD)
    )
    print(report.log_line)
    assert report.status == "degraded:substrate missing"
    assert report.proposed == 0 and report.calls == 0
    assert not (store / "inbox.md").read_text(encoding="utf-8")

    row = amplifier_memory.substrate_row(tmp_path / "nothing-here")
    print(row.render())
    assert row.level == "WARN" and "missing at" in row.detail


def test_a_stale_item_is_dropped_and_counted_in_the_next_runs_line(store: Path, substrate: Path) -> None:
    """Core 6's 30-day drop, reported by Core 9's line — the two clauses meet here."""
    old = (datetime.now(UTC) - timedelta(days=31)).date().isoformat()
    inbox.append(store, [inbox.Candidate("something nobody reviewed", "q", "aaaaaaaa", old)])
    print("--- inbox.md before ---\n" + (store / "inbox.md").read_text(encoding="utf-8"))
    report = amplifier_memory.run_suggest(
        store, base_path=substrate, model_call=model_returning(GOOD)
    )
    print("--- inbox.md after ---\n" + (store / "inbox.md").read_text(encoding="utf-8"))
    print(report.log_line)
    assert report.dropped_stale == 1
    assert "dropped_stale=1" in report.log_line
    assert [item.text for item in inbox.pending(store)] == [GOOD["text"]]


# ---------------------------------------------------------------- the conformance kit


def test_the_suggestions_kit_runs_green_and_covers_every_core_clause() -> None:
    """Every clause gets a line, and only Broken fails the run."""
    repo = Path(__file__).resolve().parents[1]
    proc = subprocess.run(
        [sys.executable, str(repo / "conformance" / "suggestions" / "run.py")],
        capture_output=True,
        text=True,
        check=False,
        cwd=repo,
    )
    print(proc.stdout)
    assert proc.returncode == 0, proc.stderr
    lines = [line for line in proc.stdout.splitlines() if line.startswith("Core ")]
    assert len(lines) == 10
    for index, line in enumerate(lines, start=1):
        assert line.startswith(f"Core {index} \u2014 ")
        assert line.split(" \u2014 ")[1] in {"Kept", "Not yet", "Broken", "Can't check"}
    kept = [line.split(" \u2014 ")[0] for line in lines if " \u2014 Kept \u2014 " in line]
    print("Kept:", kept)
    assert {f"Core {n}" for n in (1, 2, 3, 4, 7, 8, 9, 10)} <= set(kept)
