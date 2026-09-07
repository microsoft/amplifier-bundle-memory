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


DEFAULT_TEXT = "never use tabs in YAML; two-space indentation"
DEFAULT_QUOTE = "never use tabs in YAML files I ask you to write"


def one(text: str = DEFAULT_TEXT, quote: str | None = None) -> inbox.Candidate:
    """One candidate, with the human sentence behind it.

    The quote defaults to the human turn behind the default text, and to a sentence of
    this text's own otherwise. That default matters: `append` keys the known-set on the
    quote as well as the text (suggestions.v1 §4), so two candidates standing for two
    *different* preferences must carry the two different sentences a real transcript
    would have. A fixture that gave both the same quote would be asserting that one
    human sentence stated two preferences — which is a real case, and has its own test
    (`test_two_preferences_in_one_sentence_merge_and_that_is_a_cost`), not the default.
    """
    if quote is None:
        quote = DEFAULT_QUOTE if text == DEFAULT_TEXT else f"please, {text}"
    return inbox.Candidate(text=text, quote=quote, session="bc214bdf", date="2026-09-05")


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


# -------------------------------------------- Core 4: already known, keyed on the quote
#
# The field a model rewrites is the `text`; the field it copies word for word is the
# `quote`, because §3's question tells it to. Measured over three pilots, 210 calls,
# 7 models (`evaluations/model-class/RESULTS-2026-09-06-pilot.md`): every model
# re-proposed a line it had been told was already known at least once (0-30%), each time
# as a paraphrase carrying the original verbatim quote. These tests are that failure.


def test_a_paraphrase_of_a_pending_item_is_dropped_by_its_quote(store: Path) -> None:
    """Different text, same verbatim quote as something already pending: not proposed.

    The store must be byte-identical afterwards and no commit may be made - a dropped
    candidate is not a write (Core 9).
    """
    inbox.append(store, [one()])
    before = show(store, "one pending item")
    log_before = subprocess.run(
        ["git", "log", "--oneline"], cwd=store, capture_output=True, text=True, check=True
    ).stdout

    paraphrase = inbox.Candidate(
        text="tabs are banned in YAML - use two spaces",  # a paraphrase, not the same text
        quote=DEFAULT_QUOTE,  # the same human sentence, word for word
        session="bc214bdf",
        date="2026-09-05",
    )
    landed = inbox.append(store, [paraphrase])
    after = show(store, "after the paraphrase")
    log_after = subprocess.run(
        ["git", "log", "--oneline"], cwd=store, capture_output=True, text=True, check=True
    ).stdout
    print(f"landed={landed}  text differs={paraphrase.text != DEFAULT_TEXT}")
    print(f"inbox byte-identical={after == before}  git log unchanged={log_after == log_before}")

    assert landed == [], "a paraphrase of a pending item reached the inbox"
    assert after == before and log_after == log_before, "a dropped candidate wrote something"


def test_two_preferences_in_one_sentence_merge_and_that_is_a_cost(store: Path) -> None:
    """Same-batch duplicates by quote collapse to one - and the cost is stated, not hidden.

    Two candidates sharing one verbatim quote are two readings of one human sentence, so
    §4's "duplicates within the run are merged" merges them. When the sentence really did
    carry two preferences, the second reading is lost. The mitigation is that the whole
    sentence is still in front of the human on the item that survived, so nothing about
    what they said is hidden from them.
    """
    sentence = "never use tabs in YAML and always run make check before pushing"
    landed = inbox.append(
        store,
        [
            one("never use tabs in YAML", quote=sentence),
            one("always run make check before pushing", quote=sentence),
        ],
    )
    show(store, "after one sentence carrying two preferences")
    print("landed:", [(item.id, item.text) for item in landed])

    assert len(landed) == 1, "two candidates on one quote should merge to one item"
    assert landed[0].text == "never use tabs in YAML", "the first reading is the one kept"
    assert landed[0].quote == sentence, "the human still sees the whole sentence they said"


def test_a_paraphrase_of_a_live_memory_is_dropped_by_its_quote(store: Path) -> None:
    """store.v2 §3 leaves no room for a quote on a MEMORY.md line; §6 keeps it in git.

    This is the case the pilots actually measured: the already-known line was planted in
    `memory_lines`, and the models paraphrased it back.
    """
    turn = "always run make check before pushing, every single time"
    amplifier_memory.save(
        "always run `make check` before pushing", turn, "assistant", "session-1", [turn], home=store
    )
    print("--- MEMORY.md ---")
    print((store / "MEMORY.md").read_text(encoding="utf-8"))
    print("memory_quotes:", inbox.memory_quotes(store))

    landed = inbox.append(store, [one("run make check first, always", quote=turn)])
    print("landed:", landed)
    assert inbox.memory_quotes(store) == [turn], "the quote behind a live memory is readable"
    assert landed == [], "a paraphrase of a saved memory reached the inbox"


def test_a_forgotten_memorys_quote_is_not_a_reason_to_drop(store: Path) -> None:
    """A `/forget` is not a decline (store.v2 §7): what was removed may be proposed again.

    The save commit keeps the quote forever, so reading git without checking which ids
    `MEMORY.md` still carries would silently make every forgotten memory unproposable.
    """
    turn = "always run make check before pushing, every single time"
    saved = amplifier_memory.save(
        "always run `make check` before pushing", turn, "assistant", "session-1", [turn], home=store
    )
    amplifier_memory.forget(saved.id, home=store, session_id="session-1", writer="human")
    print("MEMORY.md after forget:", (store / "MEMORY.md").read_text(encoding="utf-8") or "(empty)")
    print("memory_quotes after forget:", inbox.memory_quotes(store))

    landed = inbox.append(store, [one("run make check first, always", quote=turn)])
    print("landed:", [(item.id, item.text) for item in landed])
    assert inbox.memory_quotes(store) == [], "a forgotten memory's quote is still 'known'"
    assert [item.text for item in landed] == ["run make check first, always"]


def test_declined_dedupe_is_text_only_today(store: Path) -> None:
    """The one gap left open, on purpose: a decline keeps no quote to key on.

    `declined.md`'s line is store.v2 §7's `- <YYYY-MM-DD> <text>` and the decline commit
    carries `text:`/`declined:` and no quote, so after a decline the quote survives only
    inside historical `inbox.md` blobs. This code deliberately does not mine those: the
    same blobs hold the quotes of items that were *accepted* or that simply expired
    unreviewed, and an expired item was never decided, so re-proposing it is correct.

    Closing this properly means putting the quote on the `declined.md` line - a line
    shape a locked clause fixes - so it is a contract proposal, not a code change. Until
    then this test states exactly what still slips.
    """
    item = inbox.append(store, [one()])[0]
    inbox.decline(item.id, store)
    print("--- declined.md ---")
    print((store / "declined.md").read_text(encoding="utf-8"))
    print("--- the decline commit ---")
    decline_commit = last_commit(store)

    same_text = inbox.append(store, [one()])
    paraphrase = inbox.append(
        store, [one("tabs are banned in YAML - use two spaces", quote=DEFAULT_QUOTE)]
    )
    show(store, "after re-proposing the declined item both ways")
    print(f"same text -> {same_text}   paraphrase of it -> {[i.text for i in paraphrase]}")

    assert "quote" not in decline_commit, "the decline commit gained a quote; update this test"
    assert same_text == [], "Core 7 by text still holds"
    assert [i.text for i in paraphrase] == ["tabs are banned in YAML - use two spaces"], (
        "THE LIMIT: a declined suggestion re-proposed with a paraphrased text and the "
        "same verbatim quote still reaches the inbox, and costs the steward one decline"
    )


def test_the_quote_key_is_the_same_normalisation_verify_used(store: Path) -> None:
    """`inbox._norm` and `suggest._flatten` must agree, or the quote key stops matching.

    Importing `suggest` here is a read: it calls no model, and the inbox never does.
    `inbox` cannot import `suggest` (that is the cycle - `suggest` imports `inbox`), so
    the two spellings are pinned against each other from the outside instead.
    """
    from amplifier_memory import suggest

    turn = "  never   use tabs\tin YAML files I ask you to write  "
    for sample in (turn, DEFAULT_QUOTE, "", "one   two"):
        print(f"{sample!r} -> _norm={inbox._norm(sample)!r} _flatten={suggest._flatten(sample)!r}")
        assert inbox._norm(sample) == suggest._flatten(sample)

    inbox.append(store, [one()])
    landed = inbox.append(store, [one("a paraphrase", quote=turn)])
    print("re-flowed whitespace on the same sentence ->", landed)
    assert landed == [], "the same quote, re-wrapped, was treated as a different quote"


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
        inbox.Suggestion("s-007", one().text, one().quote, "bc214bdf", "2026-09-05").render()
        + "\n",
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


def test_append_flattens_a_multiline_quote_so_the_item_stays_readable(tmp_path):
    """Measured 2026-09-07 on the device: a quote with an embedded newline was written but
    `pending()` could not read the item back (17 written, 16 readable)."""
    from amplifier_memory import inbox, store

    home = tmp_path / "store"
    store.init(home)
    cand = inbox.Candidate(
        text="Keep\nit simple",
        quote="- **Wabi-sabi**: embrace simplicity.\n  Each line serves a purpose.",
        session="a7ec3363",
    )
    landed = inbox.append(home, [cand])
    assert len(landed) == 1
    assert "\n" not in landed[0].quote and "\n" not in landed[0].text
    pending = inbox.pending(home)
    assert [s.id for s in pending] == [landed[0].id]
    assert pending[0].quote == "- **Wabi-sabi**: embrace simplicity. Each line serves a purpose."
    lines = (home / "inbox.md").read_text(encoding="utf-8").strip("\n").split("\n")
    assert len(lines) == 2


# --------------------------------------------------------------------------
# session.v3 §6 as amended 2026-09-07 — `review` as one page of markdown
# --------------------------------------------------------------------------

#: The seeded inbox every page assertion below is rendered from. The same
#: spelling `modules/tool-memory/tests/test_tool_memory.py` and
#: `conformance/session/tool/run.py` use, so all three compare the same bytes.
SEED_SESSION = "d9c3bf04"
SEED_DATE = "2026-09-07"


def seeded(home: Path, n: int) -> list[inbox.Suggestion]:
    """`n` real items in a real `inbox.md`, appended through `inbox.append`.

    Never a hand-written page and never pre-rendered text: `render_review_page`
    parses `inbox.md` back off the disk, which is the only way a page test can
    prove the quote it prints is the quote the file carries.
    """
    return inbox.append(
        home,
        [
            inbox.Candidate(
                text=f"Preference {i:02d}: one standing line the daily pass proposed.",
                quote=(
                    f"for future reference, preference {i:02d}: always do it this way, "
                    "in every session on this device, not just in this one"
                ),
                session=SEED_SESSION,
                date=SEED_DATE,
            )
            for i in range(1, n + 1)
        ],
    )


def items_on(page: str) -> list[str]:
    return [line for line in page.splitlines() if line.startswith("**") and ". s-" in line]


def test_seventeen_waiting_come_back_six_at_a_time(memory_home: Path) -> None:
    """§6: 17 items are 6 · 6 · 5, and the header says which page this is."""
    amplifier_memory.init(memory_home)
    seeded(memory_home, 17)
    page = inbox.render_review_page(1, memory_home)
    print(page)

    assert page.splitlines()[0] == "**17 suggestions waiting** \u2014 page 1 of 3"
    assert len(items_on(page)) == 6
    assert (
        items_on(page)[0]
        == "**1. s-001** \u2014 Preference 01: one standing line the daily pass proposed."
    )
    assert len(items_on(inbox.render_review_page(2, memory_home))) == 6
    assert len(items_on(inbox.render_review_page(3, memory_home))) == 5


def test_a_page_carries_the_quote_whole_byte_for_byte(memory_home: Path) -> None:
    """The quote is the whole trust story of a suggestion: it is never truncated."""
    amplifier_memory.init(memory_home)
    written = seeded(memory_home, 17)
    raw = (memory_home / "inbox.md").read_text(encoding="utf-8")
    page = inbox.render_review_page(1, memory_home)
    quoted = [line[2:].strip('"') for line in page.splitlines() if line.startswith('> "')]
    print("first quote on the page:", quoted[0])
    print("first quote in inbox.md:", written[0].quote)

    assert len(quoted) == 6
    for suggestion, quote in zip(written[:6], quoted, strict=True):
        assert quote == suggestion.quote
        assert f'quote: "{quote}"' in raw


def test_eight_waiting_are_one_page_with_no_page_suffix(memory_home: Path) -> None:
    """§6: up to 8 is one page — a `— page 1 of 1` would be noise on every line."""
    amplifier_memory.init(memory_home)
    seeded(memory_home, 8)
    page = inbox.render_review_page(1, memory_home)
    print(page.splitlines()[0])
    print(page.splitlines()[-1])

    assert page.splitlines()[0] == "**8 suggestions waiting**"
    assert len(items_on(page)) == 8
    # Nothing to go on to, so nothing offers it.
    assert "`next`" not in page


def test_the_last_page_offers_no_next_and_the_first_does(memory_home: Path) -> None:
    amplifier_memory.init(memory_home)
    seeded(memory_home, 17)
    first, last = (inbox.render_review_page(n, memory_home) for n in (1, 3))
    print("page 1 closes:", first.splitlines()[-1])
    print("page 3 closes:", last.splitlines()[-1])

    assert "`next`" in first.splitlines()[-1]
    assert "`next`" not in last.splitlines()[-1]
    # Every command on the line names ids this page actually holds.
    for sid in ("s-001", "s-002", "s-003", "s-004"):
        assert sid in first.splitlines()[-1]


def test_a_page_past_the_last_is_refused_and_writes_nothing(memory_home: Path) -> None:
    amplifier_memory.init(memory_home)
    seeded(memory_home, 17)
    before = (memory_home / "inbox.md").read_bytes()
    with pytest.raises(amplifier_memory.PageOutOfRange) as refused:
        inbox.render_review_page(4, memory_home)
    print(refused.value)

    assert str(refused.value) == "no page 4 \u2014 the last page is 3."
    assert (memory_home / "inbox.md").read_bytes() == before


def test_an_empty_inbox_is_one_line(memory_home: Path) -> None:
    """§6 bans a zero-valued count: an empty inbox says what is true instead."""
    amplifier_memory.init(memory_home)
    page = inbox.render_review_page(1, memory_home)
    print(repr(page))
    assert page == "no suggestions waiting."
    assert "\n" not in page


def test_one_waiting_uses_the_singular_header(memory_home: Path) -> None:
    amplifier_memory.init(memory_home)
    seeded(memory_home, 1)
    page = inbox.render_review_page(1, memory_home)
    print(page)
    assert page.splitlines()[0] == "**1 suggestion waiting**"


def test_a_page_is_markdown_and_separates_its_items(memory_home: Path) -> None:
    """The whole point of the amendment: 17 items were one unbroken wall of text.

    A blank line between items is what makes markdown render each as its own
    paragraph; without it the page folds back into the wall it replaced.
    """
    amplifier_memory.init(memory_home)
    seeded(memory_home, 17)
    page = inbox.render_review_page(1, memory_home)
    blocks = page.split("\n\n")
    print("blocks:", len(blocks))

    # header + 6 items + the command line
    assert len(blocks) == 8
    assert all(block.count("\n") == 2 for block in blocks[1:7])
