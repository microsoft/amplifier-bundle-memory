"""Ratified decline-reason storage: provenance is validated before any state changes."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

from amplifier_memory import QuoteNotHuman, inbox


def _item(store: Path):
    return inbox.append(
        store,
        [inbox.Candidate("keep replies short", "I decline this because it is too broad", "source")],
    )[0]


def _state(store: Path) -> tuple[bytes, bytes, str, str]:
    return (
        (store / "inbox.md").read_bytes(),
        (store / "declined.md").read_bytes(),
        subprocess.run(["git", "rev-parse", "HEAD"], cwd=store, text=True, capture_output=True, check=True).stdout,
        subprocess.run(
            ["git", "ls-files", "--stage"], cwd=store, text=True, capture_output=True, check=True
        ).stdout,
    )


def test_reason_round_trips_exactly_and_audits_source_and_writer(store: Path) -> None:
    item = _item(store)
    reason = 'I decline this because "short" is too broad.\\Keep scope local.\nKeep scope local.'
    turns = ["I decline this because it is too broad", reason]
    before = _state(store)
    inbox.decline(item.id, store, reason=reason, human_turns=turns, session_id="current-session")
    after = _state(store)
    line = (store / "declined.md").read_text(encoding="utf-8").strip()
    message = subprocess.run(
        ["git", "log", "-1", "--format=%B"], cwd=store, text=True, capture_output=True, check=True
    ).stdout
    print("declined:", line)
    print("commit:", message)
    print("HEAD moved:", before[2] != after[2], "| index:", after[3])

    assert json.loads(line.rsplit("  reason: ", 1)[1]) == reason
    assert inbox.declined_records(store) == [
        inbox.DeclinedEntry(item.text, item.quote, reason, "valid")
    ]
    for field in (
        f"source-suggestion-id: {item.id}",
        "session: current-session",
        "reason-writer: human",
        f"reason: {json.dumps(reason)}",
    ):
        assert field in message
    assert item.id not in after[0].decode()
    assert before[2] != after[2]


@pytest.mark.parametrize(
    "reason,turns",
    [
        ("invented reason with enough words", []),
        ("x" * 2001, ["x" * 2001]),
        ("because this came from an assistant", ["other human words"]),
    ],
)
def test_invalid_reason_refuses_before_inbox_or_declined_mutation(
    store: Path, reason: str, turns: list[str]
) -> None:
    item = _item(store)
    before = _state(store)
    with pytest.raises((ValueError, QuoteNotHuman), match="refused"):
        inbox.decline(item.id, store, reason=reason, human_turns=turns, session_id="current")
    print("refused reason bytes:", len(reason.encode()), "| state unchanged:", _state(store) == before)
    assert _state(store) == before


def test_declined_reader_preserves_legacy_dedupe_and_hides_invalid_reason(store: Path) -> None:
    (store / "declined.md").write_text(
        '- 2026-09-01 legacy text\n'
        '- 2026-09-02 text with  reason: "literal"  quote: "source  reason: inside"\n'
        '- 2026-09-03 retained text  quote: "retained quote"  reason: {"bad"\n',
        encoding="utf-8",
    )
    records = inbox.declined_records(store)
    print(records)
    assert records == [
        inbox.DeclinedEntry("legacy text", "", None, "absent"),
        inbox.DeclinedEntry('text with  reason: "literal"', "source  reason: inside", None, "absent"),
        inbox.DeclinedEntry("retained text", "retained quote", None, "invalid"),
    ]
    assert inbox.is_declined("anything", store, quote="retained quote")
    assert inbox.append(store, [inbox.Candidate("rewritten", "retained quote", "s")]) == []


def test_reason_bearing_empty_quote_round_trips_and_keeps_legacy_text_bytes() -> None:
    line = inbox.declined_line("avoid global rules", "", "2026-09-13", reason="too broad")
    parsed = inbox._declined_record(line)
    print(line, "->", parsed)

    assert line == '- 2026-09-13 avoid global rules  quote: ""  reason: "too broad"'
    assert parsed == inbox.DeclinedEntry("avoid global rules", "", "too broad", "valid")
    assert inbox.declined_line("avoid global rules", "", "2026-09-13") == "- 2026-09-13 avoid global rules"


@pytest.mark.parametrize("target", ["committed-inbox", "working-inbox", "committed-declined", "working-declined"])
def test_post_commit_read_failures_are_unverified_and_preserve_the_landed_transition(
    store: Path, monkeypatch: pytest.MonkeyPatch, target: str
) -> None:
    item = _item(store)
    before = _state(store)
    original_committed, original_read_text = inbox._committed, inbox._read_text

    def broken_committed(home: Path, name: str) -> str | None:
        if target == f"committed-{name.removesuffix('.md')}":
            raise OSError(f"{target} unavailable")
        return original_committed(home, name)

    def broken_read_text(path: Path) -> str:
        if target == f"working-{path.name.removesuffix('.md')}":
            raise OSError(f"{target} unavailable")
        return original_read_text(path)

    monkeypatch.setattr(inbox, "_committed", broken_committed)
    monkeypatch.setattr(inbox, "_read_text", broken_read_text)
    with pytest.raises(inbox.DeclineUnverified, match="^commit succeeded but decline readback is unverified$"):
        inbox.decline(item.id, store)

    after = _state(store)
    committed_inbox = original_committed(store, "inbox.md") or ""
    committed_declined = original_committed(store, "declined.md") or ""
    print(target, "head moved:", before[2] != after[2], "index changed:", before[3] != after[3])
    assert before[2] != after[2] and before[3] != after[3]
    assert item.id not in committed_inbox and item.id not in (store / "inbox.md").read_text()
    assert item.text in committed_declined and item.text in (store / "declined.md").read_text()