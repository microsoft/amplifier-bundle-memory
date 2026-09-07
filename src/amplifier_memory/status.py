"""The read-only reports: `status`, `review`, and the formatting of `why`.

cli.v2 Core 9 says every behaviour a verb exposes is a public library function
first, so `amplifier-memory status` is `click.echo(amplifier_memory.status().render())`
and nothing else. This module imports only the standard library: no `click`.

Every number `status` prints comes from exactly two places (cli.v2 Core 2): the
store's **git history** and **usage.jsonl**. There is no counter file, no cache,
and no third source — VISION principle 9 is the project's success metric, and a
metric computed from anything but the record it claims to measure is a lie.

The overview a session shows for a bare `/memory` (session.v3 §6) is the same
`StatusReport`, rendered differently: `StatusReport.render_overview()`. Two
renderings, one computation, so the four lines a human reads in a session and
the screen `amplifier-memory status` prints can never disagree about a figure.

cli.v2 clause map
-----------------
Core 2  `status` ....... `status`, `StatusReport.render`
Core 3  `why <id>` ..... `format_why` (the git read itself is `store.why`)
Core 4  `review` ....... `review`

session.v3 clause map
---------------------
§6      bare `/memory` .. `StatusReport.render_overview`
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from pathlib import Path

from . import _git, inbox
from .store import (
    _ID_RE,
    USAGE_RETENTION_DAYS,
    _field,
    _json_field,
    _read_lines,
    _require_store,
    commit_subject_memory,
    list_memories,
    read_usage,
    topic_files,
)

# store.v2 §8 / cli.v2 §5: a topic not read in this many days is reported stale.
STALE_TOPIC_DAYS = USAGE_RETENTION_DAYS
# cli.v2 Reserved R1: "kept" is present this many days after the write.
KEPT_AFTER_DAYS = 7
# docs/VISION.md, Sequencing: Phase 1's success gate.
KEPT_GATE = 5
# session.v3 §6: the overview's third line reports this window.
OVERVIEW_DAYS = 7

#: session.v3 §6, the bare `/memory` overview — at most four lines, each present
#: only under its own condition, suggestions first because reviewing them is the
#: act the steward asked to encourage. Every figure comes from the `StatusReport`
#: the CLI's `status` renders; nothing here counts anything itself.
OVERVIEW_SUGGESTIONS = "{n} suggestions waiting. /memory review to walk them."
OVERVIEW_SUGGESTIONS_ONE = "1 suggestion waiting. /memory review to walk it."
OVERVIEW_MEMORIES = "{counts}. /memory list to see them."
OVERVIEW_WINDOW = "last {days} days: {terms}."
OVERVIEW_COMMANDS = "/memory {commands}"

#: §6 bans a zero-valued count, so a store with nothing in it is told what to do
#: next instead of counting to zero. One home for the sentence: the tool's
#: listing shows the same line, imported from here.
EMPTY_STORE_LINE = "no memories yet \u2014 /remember <text> to add one."


@dataclass
class StatusReport:
    """The VISION principle 9 numbers, one screen (cli.v2 Core 2)."""

    home: Path
    memories: int
    topics: int
    stale_topics: list[str] = field(default_factory=list)
    written_7: int = 0
    written_30: int = 0
    forgotten_7: int = 0
    forgotten_30: int = 0
    kept: int = 0
    loaded_7: int = 0
    loaded_30: int = 0
    cited_7: int = 0
    cited_30: int = 0
    pending_suggestions: int = 0
    last_suggest_run: str | None = None

    def render(self) -> str:
        """One screen. The CLI adds nothing to this."""
        gate = "met" if self.kept >= KEPT_GATE else f"not met (gate is {KEPT_GATE})"
        stale = f"{len(self.stale_topics)} stale, unread {STALE_TOPIC_DAYS} days"
        kept_note = f"(written \u2265{KEPT_AFTER_DAYS} days ago, still present) \u2014 {gate}"
        last_run = (
            self.last_suggest_run or "never (run amplifier-memory suggest, or install the timer)"
        )
        lines = [
            f"memory store: {self.home}",
            "",
            f"  memories      {self.memories:>4} in MEMORY.md",
            f"  topics        {self.topics:>4} files ({stale})",
            f"  written       {self.written_7:>4} (7d)  {self.written_30:>4} (30d)",
            f"  forgotten     {self.forgotten_7:>4} (7d)  {self.forgotten_30:>4} (30d)",
            f"  loaded        {self.loaded_7:>4} (7d)  {self.loaded_30:>4} (30d)",
            # cli.v2 §2: a floor, not a percentage — a memory the assistant honoured
            # without naming it is invisible here, so this can only understate.
            f"  citation rate {self.cited_30:>4} cited / {self.loaded_30} loaded (30d)",
            f"  kept          {self.kept:>4}  {kept_note}",
            "",
            f"  suggestions   {self.pending_suggestions:>4} pending    last run: {last_run}",
        ]
        for name in self.stale_topics:
            lines.append(f"    stale: {name} \u2014 unused {STALE_TOPIC_DAYS} days; keep?")
        return "\n".join(lines)

    def render_overview(self) -> str:
        """session.v3 §6: the bare `/memory` — at most four lines, suggestions first.

        The second rendering of this dataclass. `render` above is one screen for a
        human at a shell; this is the four lines a session shows. Neither computes
        anything: both read the same fields of the same report, so a figure cannot
        differ between them.

        A line is present only under its own condition — the inbox line when
        something waits, the window line when anything happened inside it,
        `review` in the command line only while there is something to review. §6
        forbids a zero-valued count anywhere, which is why every term here is
        dropped rather than printed as 0.
        """
        lines: list[str] = []

        if self.pending_suggestions == 1:
            lines.append(OVERVIEW_SUGGESTIONS_ONE)
        elif self.pending_suggestions > 1:
            lines.append(OVERVIEW_SUGGESTIONS.format(n=self.pending_suggestions))

        counts: list[str] = []
        if self.memories:
            counts.append(f"{self.memories} memories" if self.memories != 1 else "1 memory")
        if self.topics:
            counts.append(f"{self.topics} topics" if self.topics != 1 else "1 topic")
        lines.append(
            OVERVIEW_MEMORIES.format(counts=", ".join(counts)) if counts else EMPTY_STORE_LINE
        )

        terms = [
            f"{count} {word}"
            for count, word in (
                (self.written_7, "written"),
                (self.forgotten_7, "forgotten"),
                (self.cited_7, "cited"),
            )
            if count
        ]
        if terms:
            lines.append(OVERVIEW_WINDOW.format(days=OVERVIEW_DAYS, terms=", ".join(terms)))

        commands = ["list", "forget <id>", "edit <id> <text>", "help"]
        if self.pending_suggestions:
            commands.insert(1, "review")
        lines.append(OVERVIEW_COMMANDS.format(commands=" \u00b7 ".join(commands)))
        return "\n".join(lines)


@dataclass(frozen=True)
class _CommitFact:
    """One commit, reduced to what `status` needs: when, what, which ids, which texts."""

    when: datetime
    action: str | None
    ids: tuple[str, ...]
    #: The memory text the subject names ("" when the subject is not a memory line).
    text: str
    #: The text the memory carried before, on an `edit` commit only (store.v2 §6).
    was: str | None


def _commit_facts(home: Path) -> list[_CommitFact]:
    """Every commit as a `_CommitFact`. The one git read `status` performs."""
    out: list[_CommitFact] = []
    for record in _git.log_records(home):
        try:
            when = datetime.fromisoformat(record["date"])
        except ValueError:
            continue
        if when.tzinfo is None:
            when = when.replace(tzinfo=UTC)
        _, text = commit_subject_memory(record["body"])
        out.append(
            _CommitFact(
                when=when,
                action=_field(record["body"], "action"),
                ids=tuple(_ID_RE.findall(record["body"])),
                text=text,
                was=_json_field(record["body"], "was"),
            )
        )
    return out


def _kept(facts: list[_CommitFact], present: set[str], kept_before: datetime) -> int:
    """cli.v2 §2 and R1, as pre-registered in `docs/workflow/GATE-DEFINITION-2026-09-06.md`.

    > **kept** = a memory written ≥ 7 days before the reading and still present; an
    > `edit` keeps the original write date (a refinement is continuity, not a new
    > memory); a forget + re-save of the same intent counts once, from the first write.

    Two rules, one mechanism. Each id's write date is the date of its **save** commit —
    an `edit` commit is not a write, so editing a memory never resets its clock. And ids
    that have ever held the same text are one *lineage*: a memory forgotten and written
    again under a new id is the same memory, counted once, from the earliest save in the
    lineage. A line added by hand has no save commit and so has no write date: it is not
    counted, because nothing says when it was written.
    """
    first_save: dict[str, datetime] = {}
    held: dict[str, set[str]] = {}
    for fact in facts:
        for mid in fact.ids:
            texts = held.setdefault(mid, set())
            if fact.text:
                texts.add(fact.text)
            if fact.was:
                texts.add(fact.was)
            if fact.action == "save":
                earlier = first_save.get(mid)
                if earlier is None or fact.when < earlier:
                    first_save[mid] = fact.when

    parent: dict[str, str] = {mid: mid for mid in held}

    def find(mid: str) -> str:
        root = mid
        while parent[root] != root:
            root = parent[root]
        while parent[mid] != root:  # path compression
            parent[mid], mid = root, parent[mid]
        return root

    def union(left: str, right: str) -> None:
        left_root, right_root = find(left), find(right)
        if left_root != right_root:
            parent[right_root] = left_root

    by_text: dict[str, str] = {}
    for mid, texts in held.items():
        for text in texts:
            union(mid, by_text.setdefault(text, mid))

    lineage_first: dict[str, datetime] = {}
    for mid, when in first_save.items():
        root = find(mid)
        if root not in lineage_first or when < lineage_first[root]:
            lineage_first[root] = when

    kept_roots: set[str] = set()
    for mid in present:
        if mid not in parent:
            continue  # present but never committed: a hand-added line, undateable
        written = lineage_first.get(find(mid))
        if written is not None and written <= kept_before:
            kept_roots.add(find(mid))
    return len(kept_roots)


def _usage_facts(home: Path) -> list[tuple[datetime, str, str]]:
    """Every retained usage entry as (ts, event, target) — store.v2 Core 8."""
    out: list[tuple[datetime, str, str]] = []
    for entry in read_usage(home):
        raw = entry.get("ts")
        if not isinstance(raw, str):
            continue
        try:
            when = datetime.fromisoformat(raw)
        except ValueError:
            continue
        if when.tzinfo is None:
            when = when.replace(tzinfo=UTC)
        out.append((when, str(entry.get("event", "")), str(entry.get("target", ""))))
    return out


def _pending_suggestions(home: Path) -> int:
    """Items waiting in `inbox.md` — the inbox's own parse, never a line count.

    suggestions.v1 §4 gives an item TWO lines (the text, then the quote), so
    counting non-empty lines reported double, and an item whose second line a
    hand edit or an embedded newline broke reported one that `review` cannot
    show at all (measured on the steward's device 2026-09-07: 17 written, 16
    readable). `inbox.parse` is what `review` and `doctor` already read, so the
    overview's `N suggestions waiting. /memory review to walk them.` counts
    exactly what walking them will produce.
    """
    return len(inbox.parse(_read_lines(home / inbox.INBOX)))


def status(home: str | os.PathLike[str] | None = None) -> StatusReport:
    """cli.v2 Core 2: the VISION principle 9 numbers, from git and usage.jsonl only."""
    path = _require_store(home)
    now = datetime.now(UTC)
    day7, day30 = now - timedelta(days=7), now - timedelta(days=30)
    kept_before = now - timedelta(days=KEPT_AFTER_DAYS)

    present = {str(memory["id"]) for memory in list_memories(path, include_topics=True)}
    commits = _commit_facts(path)

    written_7 = written_30 = forgotten_7 = forgotten_30 = 0
    for fact in commits:
        # An `edit` is a refinement, not a write: it is counted in neither window, and
        # `_kept` dates the memory from its save (GATE-DEFINITION-2026-09-06).
        if fact.action == "save":
            written_30 += int(fact.when >= day30)
            written_7 += int(fact.when >= day7)
        elif fact.action == "forget":
            forgotten_30 += int(fact.when >= day30)
            forgotten_7 += int(fact.when >= day7)

    usage = _usage_facts(path)
    loaded_7 = sum(1 for when, event, _ in usage if event == "loaded" and when >= day7)
    loaded_30 = sum(1 for when, event, _ in usage if event == "loaded" and when >= day30)
    cited_7 = sum(1 for when, event, _ in usage if event == "cited" and when >= day7)
    cited_30 = sum(1 for when, event, _ in usage if event == "cited" and when >= day30)
    read_recently = {
        target
        for when, event, target in usage
        if event == "read" and when >= now - timedelta(days=STALE_TOPIC_DAYS)
    }
    topics = topic_files(path)

    return StatusReport(
        home=path,
        memories=len([m for m in list_memories(path) if m["source"] == "MEMORY.md"]),
        topics=len(topics),
        stale_topics=[name for name in topics if name not in read_recently],
        written_7=written_7,
        written_30=written_30,
        forgotten_7=forgotten_7,
        forgotten_30=forgotten_30,
        kept=_kept(commits, present, kept_before),
        loaded_7=loaded_7,
        loaded_30=loaded_30,
        cited_7=cited_7,
        cited_30=cited_30,
        pending_suggestions=_pending_suggestions(path),
        # The suggest job records its own last run in suggest.log (doctor reads it);
        # status keeps None here so the two never disagree.
        last_suggest_run=None,
    )


def review(home: str | os.PathLike[str] | None = None) -> str:
    """cli.v2 Core 4: the shell form of `/memory review`. Empty inbox says so."""
    path = _require_store(home)
    pending = [line for line in _read_lines(path / "inbox.md") if line.strip()]
    if not pending:
        return (
            "inbox is empty: nothing to review.\n"
            "The daily suggest job fills it (amplifier-memory suggest; doctor shows the timer); "
            "corrections are still saved on the spot."
        )
    body = "\n".join(f"  {line}" for line in pending)
    return f"{len(pending)} pending suggestion(s) in {path / 'inbox.md'}:\n{body}"


def format_why(records: list[dict[str, object]]) -> str:
    """cli.v2 §3: `git log --grep '\\[m-017\\]'`, formatted. Oldest first.

    Three shapes, because a memory's life has three kinds of moment (store.v2 §6):

    * the creation, and any other commit — text, quote, session, writer, date;
    * an **edit** — the same, plus `was: "<old>" → now: <new>`, so a refinement reads as
      a refinement rather than as a second memory;
    * a **forget** — headed `forgot`, so a removal is never mistaken for a creation.
    """
    blocks: list[str] = []
    for record in reversed(records):
        quote = record.get("quote")
        when = str(record.get("date") or "")[:19]
        shown = json.dumps(quote, ensure_ascii=False) if quote else "(none)"
        action = str(record.get("action") or "commit")
        heading = "forgot" if action == "forget" else action
        lines = [f"{heading}  {record.get('id')}  {when}"]
        was = record.get("was")
        if action == "edit" and isinstance(was, str):
            lines.append(
                f"  was:     {json.dumps(was, ensure_ascii=False)} \u2192 now: {record.get('text')}"
            )
        else:
            lines.append(f"  text:    {record.get('text')}")
        lines += [
            f"  quote:   {shown}",
            f"  session: {record.get('session') or '(none)'}",
            f"  writer:  {record.get('writer') or '(none)'}",
            f"  target:  {record.get('target') or '(none)'}",
            f"  commit:  {record.get('commit')}",
        ]
        blocks.append("\n".join(lines))
    return "\n\n".join(blocks)


__all__ = [
    "EMPTY_STORE_LINE",
    "KEPT_AFTER_DAYS",
    "KEPT_GATE",
    "OVERVIEW_DAYS",
    "STALE_TOPIC_DAYS",
    "StatusReport",
    "format_why",
    "review",
    "status",
]
