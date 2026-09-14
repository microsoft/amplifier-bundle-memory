"""Same-session assistant context and bounded complete feedback packets."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from amplifier_memory import inbox, suggest


def test_context_is_nearest_visible_assistant_only_and_keeps_eligible_indices(tmp_path: Path) -> None:
    session = tmp_path / "projects" / "p" / "sessions" / "12345678-1111-2222-3333-444444444444"
    session.mkdir(parents=True)
    now = datetime.now(UTC)
    (session / "metadata.json").write_text('{"created": "' + now.isoformat() + '"}', encoding="utf-8")
    entries = [
        ('{"role":"system","content":"system poison"}'),
        ('{"role":"user","content":"first human turn"}'),
        ('{"role":"assistant","content":[{"type":"thinking","text":"reasoning poison"},{"type":"text","text":"before context"}]}'),
        ('{"role":"tool","content":"tool poison"}'),
        ('{"role":"user","content":"second human turn"}'),
        ('{"role":"assistant","content":"after context"}'),
    ]
    (session / "transcript.jsonl").write_text("\n".join(entries) + "\n", encoding="utf-8")
    recorded = suggest.read_session(session)
    assert recorded is not None
    turns, context = suggest._recent_human_context(
        recorded, cutoff=now - timedelta(hours=24), now=now + timedelta(seconds=1)
    )
    request = suggest.compose_request(suggest.build_prompt([], []), turns, assistant_context=context)
    print(request)
    assert turns == ("first human turn", "second human turn")
    assert context == (
        suggest.AssistantContext(1, None, "before context"),
        suggest.AssistantContext(2, "before context", "after context"),
    )
    assert "reasoning poison" not in request and "tool poison" not in request and "system poison" not in request
    assert "assistant-context for eligible human 2" in request


def test_composer_keeps_complete_feedback_and_context_under_pressure() -> None:
    reason = "reason " * 100
    declined = [
        inbox.DeclinedEntry(f"old {n}", f"quote {n}", None, "absent") for n in range(10)
    ] + [inbox.DeclinedEntry("new", "new quote", reason, "valid")]
    humans = ["human turn " + str(n) + " x" * 1400 for n in range(20)]
    context = [suggest.AssistantContext(20, "before", "after")]
    request = suggest.compose_request(
        suggest.build_prompt([], []), humans, assistant_context=context, declined=declined
    )
    print(request[:300], "\n...\n", request[-300:])
    assert len(request) <= suggest.REQUEST_CHARS
    assert f"verified-human-reason: {suggest._safe_data(reason)}" in request
    assert "assistant-context for eligible human 20" in request
    assert request.rstrip().endswith(suggest.FENCE_CLOSE)


def test_composer_reserves_omission_labels_and_counts_context_lost_with_its_human() -> None:
    humans = [f"human {index} " + "x" * suggest.TURN_CHARS for index in range(1, 30)]
    context = [suggest.AssistantContext(index, f"before {index}", f"after {index}") for index in range(1, 30)]
    declined = [inbox.DeclinedEntry(f"text {index}", f"quote {index}", None, "absent") for index in range(30)]
    request = suggest.compose_request(suggest.build_prompt([], []), humans, assistant_context=context, declined=declined)
    print(request[:200], "\n…\n", request[-400:])

    assert len(request) <= suggest.REQUEST_CHARS
    assert "(eligible human turn(s) omitted for length)" not in request
    assert "eligible human turn(s) omitted for length" in request
    assert "assistant-context unit(s) omitted for length" in request
    retained = {
        int(line.removesuffix(":").rsplit(" ", 1)[1])
        for line in request.splitlines()
        if line.startswith("assistant-context for eligible human ")
    }
    human_body = request.split(suggest.FENCE_OPEN, 1)[1].split(suggest.FENCE_CLOSE, 1)[0]
    for index in retained:
        assert f"\n{index}. " in f"\n{human_body}"


def test_composer_handles_empty_input_and_only_fails_when_mandatory_framing_overflows(monkeypatch) -> None:
    request = suggest.compose_request(suggest.build_prompt([], []), [])
    assert len(request) <= suggest.REQUEST_CHARS
    assert request.rstrip().endswith(suggest.FENCE_CLOSE)

    monkeypatch.setattr(suggest, "REQUEST_CHARS", 20)
    with pytest.raises(ValueError, match="fixed request header exceeds"):
        suggest.compose_request(suggest.build_prompt([], []), ["human"])