"""`inbox.md` and `declined.md` — the suggestion inbox (suggestions.v1 Core 4, 6, 7).

The inbox is the one place a *proposal* lives. It is not memory: nothing here is ever
injected into a session (suggestions.v1 Core 5), and only an accepted item reaches
`MEMORY.md`, through the same writer every other save uses (Core 6).

The file shape is the contract's own (Core 4), two lines per item::

    - [s-042] never use tabs in YAML; two-space indentation
      quote: "never use tabs in YAML files I ask you to write…"  session: bc214bdf  2026-09-05

`tests/test_inbox.py::test_the_contract_example_renders_byte_for_byte` renders exactly
those two lines from a `Suggestion` and compares them with the literal text lifted from
`contracts/suggestions.v1.md`, so the shape cannot drift from the clause quietly.

suggestions.v1 clause map
-------------------------
Core 4  survivors are appended in the §4 shape ....... `append`, `Suggestion.render`, `parse`
Core 4  already known: by text **and** by quote ...... `append`, `memory_texts`, `memory_quotes`
Core 6  accept / decline / skip; 30-day expiry ....... `accept`, `decline`, `skip`, `expire`
Core 7  never re-propose a decline ................... `is_declined`, `decline`

Which of the store's files can be keyed on which field is not a choice this module makes
— it is what the locked contracts fix, and it is worth stating once:

===========  ===================================  ==========================================
file         line shape                            carries the quote?
===========  ===================================  ==========================================
inbox.md     §4's two lines                        yes, on the second line
MEMORY.md    store.v2 §3 ``- [m-017] <text>``      not on the line; yes in git (store.v2 §6)
declined.md  store.v2 §7 ``- <date> <text>``       no — and the decline commit has none either
===========  ===================================  ==========================================

So a re-proposal is caught by quote against a pending item and against a live memory,
and by text alone against a decline. That last gap is deliberate and pinned by a test,
not papered over: closing it would mean changing a line shape a locked clause fixes.

Every mutation here is one commit, made under the store's own exclusive lock and
verified by re-reading **both** trees afterwards — the same discipline `store.save`
uses, for the same reason: a mutation that reports success and did not land is the
failure this project has already paid for once (store.py's module docstring).

`accept` is deliberately **two** commits: the memory save (`store.save`, which takes the
lock itself) and then the inbox removal. Each is one mutation of one file, which is what
store.v2 Core 1 asks for; folding them together would mean this module reaching inside
the writer's commit. `decline` is one commit over two files, because appending the
decline and dropping the item are one decision — a crash between them would either lose
the decline (it returns tomorrow) or lose the item.

This module imports only the standard library and this package: no `click`.
"""

from __future__ import annotations

import os
import re
import sys
from collections.abc import Iterable, Sequence
from dataclasses import dataclass, field
from datetime import UTC, date, datetime
from pathlib import Path

from . import _git
from .store import (
    MemoryError as _MemoryError,
)
from .store import (
    SaveResult,
    WriteNotLanded,
    _atomic_write,
    _commit_or_already_applied,
    _committed,
    _exclusive,
    _json_field,
    _parse,
    _read_lines,
    _read_text,
    _require_store,
    _reverting,
    commit_subject_memory,
)
from .store import (
    save as _save,
)

#: store.v2 §2's two Phase 2 files. Nothing else in this module writes to the store.
INBOX = "inbox.md"
DECLINED = "declined.md"

#: suggestions.v1 Core 6: "Items unreviewed for 30 days are dropped and counted in the
#: next run's report."
EXPIRY_DAYS = 30

#: PINS.md: "Memory ids are `m-NNN`; suggestion ids are `s-NNN`. Neither is ever reused."
#: Bounded exactly as the memory id is, and for the same reason (`store._ID_RE`).
_SID_RE = re.compile(r"\[(s-\d{3,6})\]")
_ITEM_RE = re.compile(r"^\s*-\s*\[(s-\d{3,6})\]\s*(.*)$")
#: The §4 continuation line. Rendered with exactly two spaces between fields; parsed
#: tolerantly, because store.v2 Core 9 invites a human to edit this file by hand.
_QUOTE_RE = re.compile(
    r'^\s*quote:\s*"(?P<quote>.*)"\s+session:\s*(?P<session>\S+)\s+(?P<date>\d{4}-\d{2}-\d{2})\s*$'
)
#: `declined.md` (store.v2 §7): append-only, `- <YYYY-MM-DD> <text>`.
_DECLINED_RE = re.compile(r"^\s*-\s*(?P<date>\d{4}-\d{2}-\d{2})\s+(?P<text>.*)$")


class UnknownSuggestion(_MemoryError):
    """No inbox item carries this id."""


def _today(now: datetime | None = None) -> date:
    return (now or datetime.now(UTC)).date()


@dataclass(frozen=True)
class Suggestion:
    """One pending proposal, exactly as `inbox.md` carries it (suggestions.v1 §4)."""

    id: str
    text: str
    quote: str
    session: str
    date: str

    def render(self) -> str:
        """The two lines this item occupies in `inbox.md` — §4's shape, byte for byte."""
        return (
            f"- [{self.id}] {self.text}\n"
            f'  quote: "{self.quote}"  session: {self.session}  {self.date}'
        )

    def render_review(self) -> str:
        """What `review` shows a human before they press one key (Core 6)."""
        return (
            f"[{self.id}] {self.text}\n"
            f'      quote: "{self.quote}"\n'
            f"      session: {self.session}  proposed {self.date}"
        )


@dataclass(frozen=True)
class Candidate:
    """A verified survivor on its way into the inbox — an item without an id yet.

    `suggest.run_suggest` builds these; `append` assigns the ids, because an id is the
    inbox's to give: it must never be reused, and only the inbox knows the high-water
    mark.
    """

    text: str
    quote: str
    session: str
    date: str = field(default_factory=lambda: _today().isoformat())


def _norm(text: str) -> str:
    """The one spelling used for every exact-match comparison in this module.

    Exact, per Core 4 and Core 7 ("matched exactly by code"), but not brittle about the
    whitespace an editor leaves behind: leading/trailing space and a run of internal
    spaces are the same line to a reader, and treating them as different is how a
    declined suggestion comes back.

    Quotes are normalised through here too, and this is character-for-character
    `suggest._flatten` — the normalisation `suggest.verify` already applied when it
    checked that quote against the human's turn. It is written out again rather than
    imported because `suggest` imports *this* module, and a quote key that drifted from
    the verification key would silently stop matching.
    `tests/test_inbox.py::test_the_quote_key_is_the_same_normalisation_verify_used`
    asserts the two agree.
    """
    return " ".join(text.split())


def _ordinal(when: str) -> int | None:
    """`YYYY-MM-DD` as a day number, or None when the date does not parse (hand edit)."""
    try:
        return date.fromisoformat(when).toordinal()
    except ValueError:
        return None


# --------------------------------------------------------------------------- reading


def _inbox_path(home: Path) -> Path:
    return home / INBOX


def parse(lines: Sequence[str]) -> list[Suggestion]:
    """Every well-formed item in `lines`. A line that does not parse is skipped, not raised.

    store.v2 Core 9 invites hand edits of the store's files; a half-typed item must not
    make `review`, `doctor` or the next `suggest` run explode. What is unreadable is
    simply not pending.
    """
    out: list[Suggestion] = []
    index = 0
    while index < len(lines):
        head = _ITEM_RE.match(lines[index])
        tail = _QUOTE_RE.match(lines[index + 1]) if head and index + 1 < len(lines) else None
        if head is None or tail is None:
            index += 1
            continue
        out.append(
            Suggestion(
                id=head.group(1),
                text=head.group(2).strip(),
                quote=tail.group("quote"),
                session=tail.group("session"),
                date=tail.group("date"),
            )
        )
        index += 2
    return out


def pending(home: str | os.PathLike[str] | None = None) -> list[Suggestion]:
    """suggestions.v1 Core 6: the items waiting for one keystroke each, oldest first."""
    path = _require_store(home)
    return parse(_read_lines(_inbox_path(path)))


#: suggestions.v1 Core 6: "Review is one keystroke per item." The keys and the line that
#: offers them live here, not in `cli.py`, so the session command and the shell verb
#: offer the same four and a change lands in one place.
REVIEW_KEYS = ("a", "d", "s", "q")
REVIEW_PROMPT = "  [a]ccept / [d]ecline / [s]kip / [q]uit"


def is_interactive() -> bool:
    """Whether a human is at the other end of stdin — the walk runs only then.

    In the library because `cli.py` imports exactly `click` and `amplifier_memory`
    (cli.v2 Core 9), and because `click.get_text_stream` is deprecated in Click 9.
    """
    return sys.stdin.isatty()


def review_one(
    sid: str,
    choice: str,
    home: str | os.PathLike[str] | None = None,
    *,
    session_id: str | None = None,
) -> str:
    """suggestions.v1 Core 6: one keystroke, one outcome, one line saying what happened.

    `a` accepts (through the shared writer), `d` declines (to `declined.md`), `s` skips.
    The three library calls are the whole of Core 6; this is the one place that maps a
    key onto them, so `/memory review` in a session and `amplifier-memory review` at a
    shell can never drift apart.
    """
    key = (choice or "").strip().lower()[:1]
    if key == "a":
        saved = accept(sid, home, session_id=session_id or reviewing_session_id())
        return f"accepted [{sid}] \u2192 saved as [{saved.id}] (commit {saved.commit[:12]})"
    if key == "d":
        item = decline(sid, home)
        return f"declined [{sid}]: {item.text} \u2014 it will not be proposed again ({DECLINED})"
    if key == "s":
        return f"skipped [{sid}]: {skip(sid, home).text} \u2014 it stays in the inbox"
    raise ValueError(f"unknown review key {choice!r}: expected one of {REVIEW_KEYS}")


def review_action(
    *,
    accept_id: str | None = None,
    decline_id: str | None = None,
    skip_id: str | None = None,
    home: str | os.PathLike[str] | None = None,
    session_id: str | None = None,
) -> str | None:
    """The non-interactive form of Core 6: at most one of the three, or None for neither.

    None means "no flag was given", which is the caller's cue to list or to walk — a
    distinction the CLI would otherwise have to make by carrying logic.
    """
    for key, sid in (("a", accept_id), ("d", decline_id), ("s", skip_id)):
        if sid:
            return review_one(sid, key, home, session_id=session_id)
    return None


def reviewing_session_id() -> str:
    """The session id a shell review records: `cli-<pid>` (store.v2 §6's `session:`).

    In the library rather than in `cli.py`, because `cli.py` imports exactly `click` and
    `amplifier_memory` (cli.v2 Core 9) — and because a review that happens at a shell is
    still a session, and `why` should say which one.
    """
    return f"cli-{os.getpid()}"


def render_pending(home: str | os.PathLike[str] | None = None) -> str:
    """cli.v2 Core 4 / suggestions.v1 Core 6: the inbox as a human reads it.

    Lives here, not in `cli.py`, because `/memory review` shows the same list inside a
    session and no wrapper may carry logic (AGENTS.md rule 11). An empty inbox says so
    and is a normal, complete answer.
    """
    items = pending(home)
    if not items:
        return (
            "inbox is empty: nothing to review.\n"
            "The daily pass proposes what it finds; `amplifier-memory service install` "
            "installs the timer that runs it."
        )
    body = "\n".join(f"  {item.render_review()}" for item in items)
    head = f"{len(items)} pending suggestion(s) in {_require_store(home) / INBOX}:"
    return f"{head}\n{body}\n\nAccept, decline or skip each: `amplifier-memory review`."


def declined_texts(home: str | os.PathLike[str] | None = None) -> list[str]:
    """Every text in `declined.md` (store.v2 §7), in the order it was declined."""
    path = _require_store(home)
    out: list[str] = []
    for line in _read_lines(path / DECLINED):
        match = _DECLINED_RE.match(line)
        if match is not None:
            out.append(match.group("text").strip())
        elif line.strip():
            out.append(line.strip().removeprefix("-").strip())
    return out


def is_declined(text: str, home: str | os.PathLike[str] | None = None) -> bool:
    """suggestions.v1 Core 7: exact match against `declined.md`, in code.

    The prompt is given the list too (Core 3), but the prompt is advice and this is the
    gate: a model that ignores the list still cannot get a declined text past here.
    """
    wanted = _norm(text)
    return any(_norm(existing) == wanted for existing in declined_texts(home))


def memory_texts(home: str | os.PathLike[str] | None = None) -> list[str]:
    """Every line of `MEMORY.md` as a comparable text — parsed memories and hand lines.

    Core 4 says a candidate must not "exactly match a `MEMORY.md` line", and a
    hand-written line with no id is still a line (store.v2 Core 9).
    """
    path = _require_store(home)
    out: list[str] = []
    for line in _read_lines(path / "MEMORY.md"):
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        parsed = _parse(line)
        out.append(parsed[1] if parsed is not None else line.strip())
    return out


def memory_quotes(home: str | os.PathLike[str] | None = None) -> list[str]:
    """The verbatim quote behind every memory `MEMORY.md` still carries (store.v2 §6).

    `MEMORY.md`'s line (store.v2 §3) is `- [m-017] <text>`: there is no room on it for a
    quote, and that line shape is fixed by a locked clause. But store.v2 §6 puts the
    verbatim quote in the commit that wrote the line, and says "no separate provenance
    store exists" — so the quote *is* kept, in git, and this is where to read it.

    Only ids `MEMORY.md` **currently** carries are read. A forgotten memory's save commit
    still carries its quote forever, and treating that as "already known" would mean a
    line the human deliberately removed could never be proposed again — a `/forget` is
    not a decline (store.v2 §7).
    """
    path = _require_store(home)
    live = {
        parsed[0]
        for line in _read_lines(path / "MEMORY.md")
        if (parsed := _parse(line)) is not None
    }
    if not live:
        return []
    out: list[str] = []
    for record in _git.log_records(path):
        mid, _ = commit_subject_memory(record["body"])
        if mid in live:
            quote = _json_field(record["body"], "quote")
            if quote:
                out.append(quote)
    return out


# --------------------------------------------------------------------------- ids


def _known_sids(home: Path) -> set[int]:
    """Every suggestion id ever issued: the git history, plus the working tree.

    The same high-water mark `store._known_ids` keeps for `m-NNN`, and for the same
    reason (PINS.md: neither id is ever reused). Scanning `inbox.md` alone would reissue
    an id the moment its item was accepted or declined — that file is exactly where an
    issued id stops being.
    """
    seen: set[int] = set()
    for record in _git.log_records(home):
        for found in _SID_RE.findall(record["body"]):
            seen.add(int(found.split("-", 1)[1]))
    for line in _read_lines(_inbox_path(home)):
        for found in _SID_RE.findall(line):
            seen.add(int(found.split("-", 1)[1]))
    return seen


def _next_sid(home: Path, offset: int = 0) -> str:
    known = _known_sids(home)
    return f"s-{((max(known) + 1) if known else 1) + offset:03d}"


# --------------------------------------------------------------------------- writing


def _rendered(items: Sequence[Suggestion]) -> str:
    body = "\n".join(item.render() for item in items)
    return f"{body}\n" if body else ""


def _assert_inbox(home: Path, sha: str, *, present: Sequence[str], absent: Sequence[str]) -> None:
    """Both trees agree about which ids the inbox carries. Neither one alone.

    `store._assert_saved`'s discipline, applied to this file: `review` and `doctor` read
    the working tree while the history reads git, and a removal that landed in one and
    not the other is a suggestion that comes back from the dead.
    """
    for where, content in (
        ("committed", _committed(home, INBOX)),
        ("working-tree", _read_text(home / INBOX)),
    ):
        text = content or ""
        for sid in present:
            if f"[{sid}]" not in text:
                raise WriteNotLanded(
                    f"the inbox write did not land: commit {sha[:12]} was made, but the "
                    f"{where} {INBOX} does not carry [{sid}]"
                )
        for sid in absent:
            if f"[{sid}]" in text:
                raise WriteNotLanded(
                    f"the inbox write did not land: commit {sha[:12]} was made, but the "
                    f"{where} {INBOX} still carries [{sid}]"
                )


def append(
    home: str | os.PathLike[str] | None,
    candidates: Iterable[Candidate],
) -> list[Suggestion]:
    """suggestions.v1 Core 4: append the survivors in one commit, and say which landed.

    Dropped before anything is written, each for a clause and not a taste:

    * a text that exactly matches a `MEMORY.md` line (Core 4: already known);
    * a text in `declined.md` (Core 7: never re-propose a decline);
    * a text already pending in the inbox, and a text repeated inside this batch
      (Core 4: "duplicates within the run are merged");
    * **the same verbatim quote** as a pending item, as a memory `MEMORY.md` still
      carries, or as another candidate in this batch.

    The quote is a key because the text is the field a model rewrites. Measured over
    three pilots, 210 real calls, 7 models (`evaluations/model-class/`): every model
    re-proposed a line it had been told was already known at least once — 0–30% of the
    time — and each time it paraphrased the `text` while copying the `quote` verbatim,
    because §3's question asks it to quote a human turn word for word. Keying only on
    the text meant every one of those reached the inbox and cost the steward a decline.

    The cost of the quote key, paid knowingly: two genuinely different preferences said
    in one sentence carry one quote, so the second is merged away. That is the same
    trade §4 already makes with "duplicates within the run are merged", and the human
    sees the whole sentence in the inbox either way — but it is a real loss, and
    `tests/test_inbox.py::test_two_preferences_in_one_sentence_merge_and_that_is_a_cost`
    pins it rather than leaving it to be discovered.

    A declined suggestion is the one source with no quote to key on: `declined.md`'s
    line (store.v2 §7) is `- <YYYY-MM-DD> <text>` and the decline commit carries no
    quote either, so a decline is still matched by text alone — see
    `test_declined_dedupe_is_text_only_today`.

    Returns the items that were actually appended. An empty list means nothing was
    written and no commit was made, which is a normal outcome (Core 9).
    """
    path = _require_store(home)
    with _exclusive(path):
        existing = parse(_read_lines(_inbox_path(path)))
        known = {_norm(text) for text in memory_texts(path)}
        known |= {_norm(text) for text in declined_texts(path)}
        known |= {_norm(item.text) for item in existing}
        # Every source that actually keeps a quote: the pending items carry it on their
        # own second line (§4), and a saved memory keeps it in its commit (store.v2 §6).
        known_quotes = {_norm(item.quote) for item in existing if item.quote.strip()}
        known_quotes |= {_norm(quote) for quote in memory_quotes(path) if quote.strip()}

        fresh: list[Suggestion] = []
        for candidate in candidates:
            text = " ".join(candidate.text.split())
            # §4's item is exactly two lines. A verbatim quote lifted from a multi-line
            # human turn carries its newlines, and a newline inside the `quote: "…"` line
            # breaks the shape: the item is written but `pending()` cannot read it back,
            # so it is invisible to `review` and never expires. Measured on the steward's
            # device on 2026-09-07 (the timer's first run: 17 written, 16 readable).
            # `verify` and `_norm` already compare whitespace-insensitively, so flattening
            # the quote to one line changes nothing the contract checks.
            quote = " ".join(candidate.quote.split())
            if not text or _norm(text) in known:
                continue
            # An empty quote is not a key: it would make every unquoted candidate the
            # same candidate. `suggest.verify` rejects those long before here anyway.
            if quote.strip() and _norm(quote) in known_quotes:
                continue
            known.add(_norm(text))
            if quote.strip():
                known_quotes.add(_norm(quote))
            fresh.append(
                Suggestion(
                    id=_next_sid(path, offset=len(fresh)),
                    text=text,
                    quote=quote,
                    session=candidate.session,
                    date=candidate.date,
                )
            )
        if not fresh:
            return []

        message = "\n".join(
            [
                f"inbox: propose {len(fresh)} suggestion(s) (suggestions.v1 \u00a74)",
                "",
                *(f"[{item.id}] {item.text}" for item in fresh),
                "",
                "action: propose",
                f"target: {INBOX}",
            ]
        )
        with _reverting(path, [INBOX]):
            _atomic_write(_inbox_path(path), _rendered([*existing, *fresh]))
            sha, _ = _commit_or_already_applied(path, message, [INBOX], operation="commit")
            _assert_inbox(path, sha, present=[item.id for item in fresh], absent=[])
    return fresh


def _find(items: Sequence[Suggestion], sid: str) -> Suggestion:
    for item in items:
        if item.id == sid:
            return item
    raise UnknownSuggestion(
        f"unknown suggestion id {sid!r}: {INBOX} carries "
        f"{[item.id for item in items] or 'no pending items'}"
    )


def accept(
    sid: str,
    home: str | os.PathLike[str] | None = None,
    *,
    session_id: str,
) -> SaveResult:
    """suggestions.v1 Core 6: write the line through the shared writer, then drop the item.

    Two commits, in this order and never the other: `store.save` first, the removal
    second. If the save is refused — the 200-line cap, a duplicate, a corrupt store —
    the item is still in the inbox afterwards, which is the honest state: the keystroke
    did not become a memory, so the proposal has not been reviewed away.

    `session_id` is the session doing the accepting. The session the quote came from
    travels separately, into the commit's `suggestion-session:` field, because they are
    different facts (store.v2 §6).
    """
    path = _require_store(home)
    item = _find(parse(_read_lines(_inbox_path(path))), sid)
    result = _save(
        item.text,
        item.quote,
        "suggestion",
        session_id,
        None,
        home=path,
        suggestion_session=item.session,
    )
    message = "\n".join(
        [
            f"inbox: accept [{sid}] -> [{result.id}] (suggestions.v1 \u00a76)",
            "",
            f"text: {item.text}",
            f"session: {session_id}",
            f"suggestion-session: {item.session}",
            "action: accept",
            f"target: {INBOX}",
        ]
    )
    with _exclusive(path):
        items = parse(_read_lines(_inbox_path(path)))
        with _reverting(path, [INBOX]):
            _atomic_write(_inbox_path(path), _rendered([i for i in items if i.id != sid]))
            sha, _ = _commit_or_already_applied(path, message, [INBOX], operation="commit")
            _assert_inbox(path, sha, present=[], absent=[sid])
    return result


def decline(sid: str, home: str | os.PathLike[str] | None = None) -> Suggestion:
    """suggestions.v1 Core 6/7: append the text to `declined.md` with the date, drop the item.

    One commit over both files. store.v2 §7 keeps `declined.md` append-only — reversal is
    by hand, by deleting the line — so nothing here ever rewrites an earlier entry.
    """
    path = _require_store(home)
    with _exclusive(path):
        items = parse(_read_lines(_inbox_path(path)))
        item = _find(items, sid)
        line = f"- {_today().isoformat()} {item.text}"
        existing = _read_lines(path / DECLINED)
        message = "\n".join(
            [
                f"inbox: decline [{sid}] (suggestions.v1 \u00a77)",
                "",
                f"text: {item.text}",
                f"declined: {line}",
                "action: decline",
                f"target: {INBOX}, {DECLINED}",
            ]
        )
        with _reverting(path, [INBOX, DECLINED]):
            _atomic_write(path / DECLINED, "\n".join([*existing, line]) + "\n")
            _atomic_write(_inbox_path(path), _rendered([i for i in items if i.id != sid]))
            sha, _ = _commit_or_already_applied(
                path, message, [INBOX, DECLINED], operation="commit"
            )
            _assert_inbox(path, sha, present=[], absent=[sid])
            declined = _committed(path, DECLINED) or ""
            if line not in declined.splitlines():
                raise WriteNotLanded(
                    f"the decline did not land: commit {sha[:12]} was made, but the "
                    f"committed {DECLINED} does not carry {line!r}"
                )
    return item


def skip(sid: str, home: str | os.PathLike[str] | None = None) -> Suggestion:
    """suggestions.v1 Core 6: **skip** leaves it. Nothing is written, nothing is committed."""
    return _find(pending(home), sid)


def expire(
    home: str | os.PathLike[str] | None = None,
    days: int = EXPIRY_DAYS,
    *,
    now: datetime | None = None,
) -> list[Suggestion]:
    """suggestions.v1 Core 6: drop items unreviewed for `days`, and return them to be counted.

    Returns the dropped items so the caller can put the number in the run's one log line
    (Core 9). Nothing dropped means nothing written and no commit. An item whose date
    does not parse is never dropped: a hand edit is not a reason to delete a proposal.
    """
    path = _require_store(home)
    cutoff = _today(now).toordinal() - days
    with _exclusive(path):
        items = parse(_read_lines(_inbox_path(path)))
        stale = [
            item
            for item in items
            if (ordinal := _ordinal(item.date)) is not None and ordinal <= cutoff
        ]
        if not stale:
            return []
        stale_ids = {item.id for item in stale}
        keep = [item for item in items if item.id not in stale_ids]
        message = "\n".join(
            [
                (
                    f"inbox: drop {len(stale)} item(s) unreviewed for {days} days "
                    "(suggestions.v1 \u00a76)"
                ),
                "",
                *(f"[{item.id}] {item.text}" for item in stale),
                "",
                "action: expire",
                f"target: {INBOX}",
            ]
        )
        with _reverting(path, [INBOX]):
            _atomic_write(_inbox_path(path), _rendered(keep))
            sha, _ = _commit_or_already_applied(path, message, [INBOX], operation="commit")
            _assert_inbox(path, sha, present=[i.id for i in keep], absent=sorted(stale_ids))
    return stale


__all__ = [
    "DECLINED",
    "EXPIRY_DAYS",
    "INBOX",
    "REVIEW_KEYS",
    "REVIEW_PROMPT",
    "Candidate",
    "Suggestion",
    "UnknownSuggestion",
    "accept",
    "append",
    "decline",
    "declined_texts",
    "expire",
    "is_declined",
    "is_interactive",
    "memory_quotes",
    "memory_texts",
    "parse",
    "pending",
    "render_pending",
    "review_action",
    "review_one",
    "reviewing_session_id",
    "skip",
]
