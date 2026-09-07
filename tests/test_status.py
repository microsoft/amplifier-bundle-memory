"""cli.v2 Core 2 — `status`, against a store whose git history is built to order.

Every number `status` prints comes from git and `usage.jsonl` and nowhere else, so
the fixture below constructs the history it expects to see: saves and forgets at
chosen dates (`backdate`, which sets GIT_AUTHOR_DATE/GIT_COMMITTER_DATE), usage
entries at chosen dates. The assertions are exact counts, not "at least".

A test that only asserted `status()` returns *something* could not fail. Each number
here is asserted against a history designed to make a wrong window, a wrong writer,
or a wrong presence check produce a different number.
"""

from __future__ import annotations

import json
from collections.abc import Callable
from contextlib import AbstractContextManager
from datetime import UTC, datetime, timedelta
from pathlib import Path

import amplifier_memory
from amplifier_memory.status import KEPT_AFTER_DAYS, KEPT_GATE, STALE_TOPIC_DAYS

Backdate = Callable[[float], AbstractContextManager[None]]


def _save(text: str, home: Path, **kw: object) -> object:
    return amplifier_memory.save(text, text, "human", "sess-fixture", [text], home=home, **kw)


def _usage(home: Path, days_ago: float, event: str, target: str) -> None:
    """Append one usage entry at a chosen date, without a commit (store.v2 Core 8 shape)."""
    entry = {
        "ts": (datetime.now(UTC) - timedelta(days=days_ago)).isoformat(),
        "event": event,
        "target": target,
        "session_id": "sess-fixture",
    }
    with (home / "usage.jsonl").open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(entry) + "\n")


def build_fixture(home: Path, backdate: Backdate) -> None:
    """A store with a history whose every `status` number is known in advance.

    saves:      m-001 at 40d, m-002 at 20d, m-003 at 8d, m-004 at 2d   (4 saves)
    forgets:    m-002 at 3d, m-001 at 40d-ish (kept out of both windows: 35d)
    topics:     yaml-style (read 2d ago), old-notes (never read -> stale)
    usage:      2 loads inside 7d, 1 more inside 30d, 1 outside 30d
    """
    with backdate(40):
        _save("m1 forty days old", home)
    with backdate(20):
        _save("m2 twenty days old", home)
    with backdate(8):
        _save("m3 eight days old", home)
    with backdate(2):
        _save("m4 two days old", home)
    with backdate(35):
        amplifier_memory.forget("m-001", home, session_id="sess-fixture")
    with backdate(3):
        amplifier_memory.forget("m-002", home, session_id="sess-fixture")
    with backdate(10):
        _save("t1 in a topic", home, topic="yaml-style", topic_purpose="YAML style.")
        _save("t2 in another topic", home, topic="old-notes", topic_purpose="Old notes.")

    _usage(home, 1, "loaded", "MEMORY.md")
    _usage(home, 5, "loaded", "MEMORY.md")
    _usage(home, 20, "loaded", "MEMORY.md")
    _usage(home, 100, "loaded", "MEMORY.md")  # outside every window and outside retention
    _usage(home, 2, "read", "topics/yaml-style.md")


def test_status_numbers_match_a_constructed_history(store: Path, backdate: Backdate) -> None:
    build_fixture(store, backdate)
    report = amplifier_memory.status()

    print(report.render())

    # MEMORY.md holds m-003 and m-004 (m-001 and m-002 were forgotten).
    assert report.memories == 2, [m["id"] for m in amplifier_memory.list_memories(store)]
    assert report.topics == 2
    # yaml-style was read 2 days ago; old-notes never was.
    assert report.stale_topics == ["topics/old-notes.md"]

    # 6 saves total: 4 in MEMORY.md + 2 topic lines (both at 10d).
    assert report.written_7 == 1, "only m-004 (2d) was written inside 7 days"
    assert report.written_30 == 5, "m-002(20d), m-003(8d), m-004(2d) and both topics(10d)"
    assert report.forgotten_7 == 1, "only the m-002 forget (3d) is inside 7 days"
    assert report.forgotten_30 == 1, "the m-001 forget is 35 days old"

    # kept = written >= 7 days ago AND still present. m-003 (8d) and the two topic
    # lines (10d) qualify; m-004 is too young; m-001/m-002 are gone.
    assert report.kept == 3, "m-003 plus the two topic memories"

    assert report.loaded_7 == 2
    assert report.loaded_30 == 3, "the 100-day-old load is outside the window"
    assert report.pending_suggestions == 0
    assert report.last_suggest_run is None


def test_kept_excludes_a_memory_that_was_forgotten(store: Path, backdate: Backdate) -> None:
    """The discriminating pair for `kept`: same write date, different presence."""
    with backdate(KEPT_AFTER_DAYS + 1):
        _save("stays put", store)
        _save("goes away", store)
    before = amplifier_memory.status().kept
    amplifier_memory.forget("m-002", store, session_id="s")
    after = amplifier_memory.status().kept
    print(f"kept before forget: {before}; after: {after}")
    assert (before, after) == (2, 1)


def test_kept_excludes_a_memory_written_today(store: Path, backdate: Backdate) -> None:
    """The other discriminating pair: same presence, different write date."""
    with backdate(KEPT_AFTER_DAYS + 1):
        _save("old enough", store)
    _save("written just now", store)
    report = amplifier_memory.status()
    print(f"memories={report.memories} kept={report.kept} written_7={report.written_7}")
    assert report.memories == 2
    assert report.kept == 1, "a memory written today is not yet kept"


def test_a_topic_read_inside_the_window_is_not_stale(store: Path) -> None:
    _save("a topic memory", store, topic="yaml-style", topic_purpose="YAML style.")
    stale_before = amplifier_memory.status().stale_topics
    _usage(store, STALE_TOPIC_DAYS - 1, "read", "topics/yaml-style.md")
    inside = amplifier_memory.status().stale_topics
    _usage(store, STALE_TOPIC_DAYS + 1, "read", "topics/old.md")
    print(f"stale with no read: {stale_before}; after a read inside the window: {inside}")
    assert stale_before == ["topics/yaml-style.md"]
    assert inside == []


def test_pending_suggestions_counts_inbox_items_not_lines(store: Path) -> None:
    """An item is TWO lines (suggestions.v1 §4), and a half-written one is none.

    session.v3 §6 puts this number in front of a human as `N suggestions waiting.
    /memory review to walk them.`, so it has to be the number walking them
    produces: `inbox.parse`, the same read `review` and `doctor` do. Counting
    lines reported double, and counted an item whose second line an embedded
    newline had broken — 17 written, 16 readable, measured on the steward's
    device on 2026-09-07.
    """
    assert amplifier_memory.status().pending_suggestions == 0
    (store / "inbox.md").write_text(
        "- [s-001] one\n"
        '  quote: "say one"  session: bc214bdf  2026-09-05\n'
        "\n"
        "- [s-002] two\n"
        '  quote: "say two"  session: bc214bdf  2026-09-05\n'
        "- [s-003] half-written, no quote line\n",
        encoding="utf-8",
    )
    report = amplifier_memory.status()
    print("pending after two whole items and one half-written:", report.pending_suggestions)
    assert report.pending_suggestions == 2, "blank lines and a broken item are not suggestions"


def test_the_overview_and_the_status_screen_never_disagree(store: Path) -> None:
    """session.v3 §6: two renderings of one report, so a figure cannot differ."""
    _save("lead with the next action", store)
    (store / "inbox.md").write_text(
        "- [s-001] one\n" '  quote: "say one"  session: bc214bdf  2026-09-05\n',
        encoding="utf-8",
    )
    report = amplifier_memory.status()
    overview = report.render_overview()
    print(overview)
    assert overview.splitlines() == [
        "1 suggestion waiting. /memory review to walk it.",
        "1 memory. /memory list to see them.",
        "last 7 days: 1 written.",
        "/memory list \u00b7 review \u00b7 forget <id> \u00b7 edit <id> <text> \u00b7 help",
    ]
    assert f"{report.pending_suggestions} pending" in report.render()


def test_render_is_one_screen_and_names_the_success_gate(store: Path, backdate: Backdate) -> None:
    build_fixture(store, backdate)
    screen = amplifier_memory.status().render()
    print(screen)
    lines = screen.splitlines()
    assert len(lines) <= 24, f"status is {len(lines)} lines; it is meant to be one screen"
    assert f"gate is {KEPT_GATE}" in screen, "the VISION success gate is not visible"
    for needle in ("memories", "written", "forgotten", "kept", "topics", "suggestions"):
        assert needle in screen, f"status does not print {needle}"


def test_status_refuses_when_there_is_no_store(memory_home: Path) -> None:
    """A read verb needs the store; it says so rather than inventing zeros."""
    try:
        amplifier_memory.status()
    except amplifier_memory.StoreMissing as exc:
        print("status with no store:", exc)
    else:
        raise AssertionError("status invented numbers for a store that does not exist")


def test_review_says_so_when_the_inbox_is_empty(store: Path) -> None:
    """cli.v2 Core 4."""
    message = amplifier_memory.review()
    print(message)
    assert "empty" in message.lower()

    (store / "inbox.md").write_text("- [s-001] a pending suggestion\n", encoding="utf-8")
    listed = amplifier_memory.review()
    print(listed)
    assert "s-001" in listed and "1 pending" in listed


# ------------------------------------------------- cli.v2 §2: the citation rate and `kept`


def test_status_prints_the_citation_rate_as_a_floor(store: Path) -> None:
    """cli.v2 §2: `cited` events over `loaded` events in the last 30 days.

    Printed as a floor and not a percentage on purpose: a memory the assistant honoured
    without naming it is invisible to this number, so it can only understate.
    """
    _save("never use tabs", store)
    amplifier_memory.log_usage("loaded", "MEMORY.md", "sess-fixture", store)
    amplifier_memory.record_citation("m-001", "sess-fixture", store)
    amplifier_memory.record_citation("m-001", "sess-fixture", store)
    _usage(store, 40, "cited", "m-001")  # outside the 30-day window

    report = amplifier_memory.status(store)
    screen = report.render()
    print(screen)
    line = "  citation rate    2 cited / 1 loaded (30d)"
    assert (report.cited_30, report.loaded_30) == (2, 1), report
    assert line in screen.splitlines(), f"status does not print {line!r}"


def test_kept_counts_an_edited_memory_from_its_first_write(store: Path, backdate: Backdate) -> None:
    """cli.v2 R1 / GATE-DEFINITION-2026-09-06: a refinement is continuity, not a new memory."""
    with backdate(KEPT_AFTER_DAYS + 1):
        _save("point time estimates at the reader", store)
    before = amplifier_memory.status(store)
    amplifier_memory.edit(
        "m-001",
        "point time estimates at whoever runs the steps",
        "point time estimates at whoever runs the steps",
        "human",
        "sess-fixture",
        ["point time estimates at whoever runs the steps"],
        home=store,
    )
    after = amplifier_memory.status(store)

    print("before the edit:", f"kept={before.kept} written_7={before.written_7}")
    print("after the edit: ", f"kept={after.kept} written_7={after.written_7}")
    print(f"MEMORY.md now: {(store / 'MEMORY.md').read_text()!r}")

    assert before.kept == 1
    assert after.kept == 1, "the edit reset the memory's write date"
    assert after.written_7 == 0, "an edit counted as a write"
    assert after.memories == 1, "the edit created a second memory"


def test_kept_counts_a_forget_and_re_save_once_from_the_first_write(
    store: Path, backdate: Backdate
) -> None:
    """The second half of the pre-registered rule: same intent, said twice, counted once."""
    with backdate(KEPT_AFTER_DAYS + 3):
        _save("said once, forgotten, said again", store)
    with backdate(KEPT_AFTER_DAYS + 2):
        amplifier_memory.forget("m-001", store, session_id="sess-fixture")
    again = _save("said once, forgotten, said again", store)  # today
    report = amplifier_memory.status(store)

    print(f"re-saved as {again.id} today; kept={report.kept} memories={report.memories}")
    assert again.id == "m-002", "the id was reused"
    assert report.kept == 1, (
        "the re-save was counted as a new memory: the lineage is dated from its first write"
    )

    # The discriminating half: a *different* text written today is not kept.
    _save("something else entirely", store)
    fresh = amplifier_memory.status(store)
    print(f"after an unrelated save today: kept={fresh.kept} memories={fresh.memories}")
    assert (fresh.kept, fresh.memories) == (1, 2), "m-001 was forgotten; m-002 and m-003 remain"
