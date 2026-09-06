"""suggestions.v1 Core 4, 6, 7 — the inbox file, and the three things a keystroke does.

Every test here prints what it asserted on: the two lines of `inbox.md` before and
after, the commit message the writer produced, and the entry `declined.md` gained.
A test that says "accepted" without showing the commit is the kind of evidence this
project has already been burned by (AGENTS.md rule 10).

Nothing here touches the real store (`tests/conftest.py` points
`AMPLIFIER_MEMORY_HOME` at a temp dir and asserts it), and nothing here calls a model:
the inbox never does.
"""

from __future__ import annotations

import subprocess
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

import amplifier_memory
from amplifier_memory import inbox

CONTRACT = Path(__file__).resolve().parents[1] / "contracts" / "suggestions.v1.md"


def show(home: Path, label: str) -> str:
    body = (home / "inbox.md").read_text(encoding="utf-8")
    print(f"--- {label}: inbox.md ---\n{body or '(empty)'}")
    return body


def last_commit(home: Path) -> str:
    body = subprocess.run(
        ["git", "log", "-1", "--format=%B"], cwd=home, capture_output=True, text=True, check=True
    ).stdout
    print(f"--- git log -1 --format=%B ---\n{body}")
    return body


def one(text: str = "never use tabs in YAML; two-space indentation") -> inbox.Candidate:
    return inbox.Candidate(
        text=text,
        quote="never use tabs in YAML files I ask you to write",
        session="bc214bdf",
        date="2026-09-05",
    )


# ---------------------------------------------------------------- Core 4: the file shape


def test_the_contract_example_renders_byte_for_byte(store: Path) -> None:
    """The §4 example, rendered from a `Suggestion`, is the contract's own two lines.

    Lifted from `contracts/suggestions.v1.md` rather than retyped here, so the day the
    clause changes this fails instead of quietly rendering yesterday's shape.
    """
    lines = CONTRACT.read_text(encoding="utf-8").splitlines()
    start = next(i for i, line in enumerate(lines) if line.strip().startswith("- [s-042]"))
    expected = "\n".join(line.strip("\n")[3:] for line in lines[start : start + 2])
    item = inbox.Suggestion(
        id="s-042",
        text="never use tabs in YAML; two-space indentation",
        quote="never use tabs in YAML files I ask you to write\u2026",
        session="bc214bdf",
        date="2026-09-05",
    )
    print(f"--- contract §4 ---\n{expected}\n--- rendered ---\n{item.render()}")
    assert item.render() == expected
    assert inbox.parse(item.render().splitlines()) == [item], "what it renders, it parses"


def test_append_assigns_monotonic_ids_and_one_commit_for_the_run(store: Path) -> None:
    show(store, "before")
    landed = inbox.append(store, [one(), one("always run `make check` before pushing")])
    body = show(store, "after")
    message = last_commit(store)

    assert [item.id for item in landed] == ["s-001", "s-002"]
    assert body.count("- [s-") == 2
    assert message.startswith("inbox: propose 2 suggestion(s)")
    assert "action: propose" in message and "target: inbox.md" in message
    commits = subprocess.run(
        ["git", "log", "--oneline"], cwd=store, capture_output=True, text=True, check=True
    ).stdout.splitlines()
    print("commits:", commits)
    assert len(commits) == 2, "one commit for the run (init + this one)"


def test_ids_are_never_reused_after_an_item_leaves_the_inbox(store: Path) -> None:
    """PINS.md: neither `m-NNN` nor `s-NNN` is ever reused.

    The discriminating case: accept the only item, so `inbox.md` is empty again, then
    append. Scanning the file alone would hand the next proposal `s-001` a second time
    and `why` would show two different memories behind one id.
    """
    first = inbox.append(store, [one()])[0]
    inbox.accept(first.id, store, session_id="reviewer-1")
    assert inbox.pending(store) == []
    second = inbox.append(store, [one("always run `make check` before pushing")])[0]
    print(f"first={first.id} accepted; next issued={second.id}")
    assert second.id == "s-002", "an id was reused after the inbox emptied"


def test_append_skips_what_is_already_known_and_merges_duplicates(store: Path) -> None:
    """Core 4: not a MEMORY.md line, not a decline, and duplicates within the run merge."""
    amplifier_memory.save(
        "point time estimates at whoever runs the steps",
        "point time estimates at whoever runs the steps",
        "human",
        "session-1",
        ["point time estimates at whoever runs the steps"],
        home=store,
    )
    (store / "declined.md").write_text("- 2026-09-01 never use emoji in commit messages\n", "utf-8")

    landed = inbox.append(
        store,
        [
            one("point time estimates at whoever runs the steps"),  # already a memory
            one("never use emoji in commit messages"),  # already declined
            one("prefer ripgrep over grep"),
            one("prefer ripgrep over grep"),  # duplicate within the run
            one("   prefer   ripgrep over grep  "),  # the same line, differently spaced
        ],
    )
    show(store, "after")
    print("landed:", [(item.id, item.text) for item in landed])
    assert [item.text for item in landed] == ["prefer ripgrep over grep"]


def test_a_run_that_proposes_nothing_writes_nothing(store: Path) -> None:
    """Core 9: "0 proposed" is a normal outcome — and it must not leave a commit."""
    before = subprocess.run(
        ["git", "log", "--oneline"], cwd=store, capture_output=True, text=True, check=True
    ).stdout
    assert inbox.append(store, []) == []
    after = subprocess.run(
        ["git", "log", "--oneline"], cwd=store, capture_output=True, text=True, check=True
    ).stdout
    print("git log before == after:", before == after)
    assert before == after and not (store / "inbox.md").read_text(encoding="utf-8")


# ---------------------------------------------------------------- Core 6: accept


def test_accept_writes_through_the_shared_writer_and_removes_the_item(store: Path) -> None:
    """Core 6: the commit carries writer `suggestion`, the quote, and the source session."""
    item = inbox.append(store, [one()])[0]
    show(store, "before accept")
    result = inbox.accept(item.id, store, session_id="reviewing-session-9")
    body = show(store, "after accept")
    memory = (store / "MEMORY.md").read_text(encoding="utf-8")
    print(f"--- MEMORY.md ---\n{memory}")
    message = last_commit(store)
    save_message = subprocess.run(
        ["git", "log", "--format=%B", "-n", "1", "--skip", "1"],
        cwd=store,
        capture_output=True,
        text=True,
        check=True,
    ).stdout
    print(f"--- the save commit ---\n{save_message}")

    assert f"- [{result.id}] {item.text}" in memory.splitlines()
    assert "writer: suggestion" in save_message
    assert 'quote: "never use tabs in YAML files I ask you to write"' in save_message
    assert "suggestion-session: bc214bdf" in save_message
    assert "session: reviewing-session-9" in save_message, "the reviewing session, separately"
    assert item.id not in body and inbox.pending(store) == []
    assert message.startswith(f"inbox: accept [{item.id}] -> [{result.id}]")


def test_a_refused_save_leaves_the_item_in_the_inbox(store: Path) -> None:
    """A keystroke that did not become a memory has not reviewed the proposal away."""
    amplifier_memory.save(
        "never use tabs in YAML; two-space indentation",
        "never use tabs in YAML; two-space indentation",
        "human",
        "session-1",
        ["never use tabs in YAML; two-space indentation"],
        home=store,
    )
    # The text is a memory already, so `append` would skip it: write the item by hand,
    # exactly as a store that gained the memory after the proposal would look.
    (store / "inbox.md").write_text(
        inbox.Suggestion("s-007", one().text, one().quote, "bc214bdf", "2026-09-05").render() + "\n",
        encoding="utf-8",
    )
    with pytest.raises(amplifier_memory.DuplicateMemory):
        inbox.accept("s-007", store, session_id="reviewer")
    body = show(store, "after the refusal")
    assert "s-007" in body, "the refused item was reviewed away anyway"


def test_writer_suggestion_refuses_without_the_session_the_quote_came_from(store: Path) -> None:
    """The exemption from `human_turns` is narrow: it must name where the quote was said."""
    with pytest.raises(ValueError, match="must name the session its quote was taken from"):
        amplifier_memory.save("some text", "some quote", "suggestion", "reviewer", None, home=store)
    with pytest.raises(ValueError, match="only for writer='suggestion'"):
        amplifier_memory.save(
            "some text",
            "some quote",
            "assistant",
            "reviewer",
            ["some quote is in here"],
            home=store,
            suggestion_session="bc214bdf",
        )
    print("writer `suggestion` without a source session, and the field on another writer: refused")


# ---------------------------------------------------------------- Core 6/7: decline, skip


def test_decline_appends_the_dated_line_and_is_never_re_proposed(store: Path) -> None:
    item = inbox.append(store, [one()])[0]
    inbox.decline(item.id, store)
    declined = (store / "declined.md").read_text(encoding="utf-8")
    print(f"--- declined.md ---\n{declined}")
    show(store, "after decline")
    last_commit(store)

    today = datetime.now(UTC).date().isoformat()
    assert declined.strip() == f"- {today} {item.text}"
    assert inbox.is_declined(item.text, store) and inbox.pending(store) == []
    assert inbox.append(store, [one()]) == [], "a declined text was proposed again"


def test_decline_and_the_inbox_removal_are_one_commit(store: Path) -> None:
    item = inbox.append(store, [one()])[0]
    before = len(
        subprocess.run(
            ["git", "log", "--oneline"], cwd=store, capture_output=True, text=True, check=True
        ).stdout.splitlines()
    )
    inbox.decline(item.id, store)
    log = subprocess.run(
        ["git", "log", "--oneline"], cwd=store, capture_output=True, text=True, check=True
    ).stdout
    print(log)
    assert len(log.splitlines()) == before + 1, "declining should be exactly one commit"
    assert (
        subprocess.run(
            ["git", "status", "--porcelain"], cwd=store, capture_output=True, text=True, check=True
        ).stdout
        == ""
    )


def test_skip_leaves_it(store: Path) -> None:
    item = inbox.append(store, [one()])[0]
    before = show(store, "before skip")
    log_before = subprocess.run(
        ["git", "log", "--oneline"], cwd=store, capture_output=True, text=True, check=True
    ).stdout
    assert inbox.skip(item.id, store).id == item.id
    assert show(store, "after skip") == before
    assert (
        subprocess.run(
            ["git", "log", "--oneline"], cwd=store, capture_output=True, text=True, check=True
        ).stdout
        == log_before
    ), "skip committed something"


def test_an_unknown_id_is_a_named_refusal(store: Path) -> None:
    for call in (
        lambda: inbox.accept("s-404", store, session_id="reviewer"),
        lambda: inbox.decline("s-404", store),
        lambda: inbox.skip("s-404", store),
    ):
        with pytest.raises(amplifier_memory.UnknownSuggestion, match="s-404"):
            call()
    print("accept/decline/skip on an unknown id: UnknownSuggestion naming the id")


# ---------------------------------------------------------------- Core 6: the 30-day drop


def test_expire_drops_only_what_is_older_than_thirty_days(store: Path) -> None:
    now = datetime.now(UTC)
    fresh = (now - timedelta(days=29)).date().isoformat()
    stale = (now - timedelta(days=31)).date().isoformat()
    inbox.append(
        store,
        [
            inbox.Candidate("a stale one", "quote a", "aaaaaaaa", stale),
            inbox.Candidate("a fresh one", "quote b", "bbbbbbbb", fresh),
        ],
    )
    show(store, "before expire")
    dropped = inbox.expire(store, now=now)
    show(store, "after expire")
    last_commit(store)
    print("dropped:", [(item.id, item.date) for item in dropped])
    assert [item.text for item in dropped] == ["a stale one"]
    assert [item.text for item in inbox.pending(store)] == ["a fresh one"]
    assert inbox.expire(store, now=now) == [], "a second run drops nothing and commits nothing"


def test_a_hand_edited_date_is_never_a_reason_to_delete(store: Path) -> None:
    """store.v2 Core 9 invites hand edits; an unreadable date must not lose a proposal."""
    inbox.append(store, [one()])
    text = (store / "inbox.md").read_text(encoding="utf-8").replace("2026-09-05", "yesterday")
    (store / "inbox.md").write_text(text, encoding="utf-8")
    print(f"--- hand-edited inbox.md ---\n{text}")
    assert inbox.expire(store, days=0) == []
    assert inbox.parse(text.splitlines()) == [], "an unparseable item is simply not pending"


# ---------------------------------------------------------------- the review surface


def test_review_one_maps_a_keystroke_onto_the_three_library_calls(store: Path) -> None:
    """Core 6: `/memory review` and the shell verb reach the same three calls."""
    items = inbox.append(
        store,
        [
            one("accept me"),
            one("decline me"),
            one("skip me"),
        ],
    )
    for item, key in zip(items, ("a", "d", "s"), strict=True):
        print(inbox.review_one(item.id, key, store, session_id="reviewer"))
    remaining = [item.text for item in inbox.pending(store)]
    print("remaining:", remaining)
    assert remaining == ["skip me"]
    assert "accept me" in (store / "MEMORY.md").read_text(encoding="utf-8")
    assert inbox.is_declined("decline me", store)
    with pytest.raises(ValueError, match="unknown review key"):
        inbox.review_one(items[2].id, "z", store)


def test_render_pending_says_so_when_the_inbox_is_empty(store: Path) -> None:
    empty = inbox.render_pending(store)
    print(empty)
    assert "inbox is empty" in empty
    inbox.append(store, [one()])
    listing = inbox.render_pending(store)
    print(listing)
    assert "[s-001]" in listing and "quote:" in listing and "session: bc214bdf" in listing
