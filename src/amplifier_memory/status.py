"""The read-only reports: `status`, `review`, and the formatting of `why`.

cli.v1 Core 9 says every behaviour a verb exposes is a public library function
first, so `amplifier-memory status` is `click.echo(amplifier_memory.status().render())`
and nothing else. This module imports only the standard library: no `click`.

Every number `status` prints comes from exactly two places (cli.v1 Core 2): the
store's **git history** and **usage.jsonl**. There is no counter file, no cache,
and no third source — VISION principle 9 is the project's success metric, and a
metric computed from anything but the record it claims to measure is a lie.

cli.v1 clause map
-----------------
Core 2  `status` ....... `status`, `StatusReport.render`
Core 3  `why <id>` ..... `format_why` (the git read itself is `store.why`)
Core 4  `review` ....... `review`
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from pathlib import Path

from . import _git
from .store import (
    _ID_RE,
    USAGE_RETENTION_DAYS,
    _field,
    _read_lines,
    _require_store,
    list_memories,
    read_usage,
    topic_files,
)

# store.v1 Core 8 / cli.v1 Core 5: a topic not read in this many days is reported stale.
STALE_TOPIC_DAYS = USAGE_RETENTION_DAYS
# cli.v1 Reserved R1: "kept" is present this many days after the write.
KEPT_AFTER_DAYS = 7
# docs/VISION.md, Sequencing: Phase 1's success gate.
KEPT_GATE = 5


@dataclass
class StatusReport:
    """The VISION principle 9 numbers, one screen (cli.v1 Core 2)."""

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
    pending_suggestions: int = 0
    last_suggest_run: str | None = None

    def render(self) -> str:
        """One screen. The CLI adds nothing to this."""
        gate = "met" if self.kept >= KEPT_GATE else f"not met (gate is {KEPT_GATE})"
        stale = f"{len(self.stale_topics)} stale, unread {STALE_TOPIC_DAYS} days"
        kept_note = f"(written \u2265{KEPT_AFTER_DAYS} days ago, still present) \u2014 {gate}"
        last_run = self.last_suggest_run or "never (Phase 2 not installed)"
        lines = [
            f"memory store: {self.home}",
            "",
            f"  memories      {self.memories:>4} in MEMORY.md",
            f"  topics        {self.topics:>4} files ({stale})",
            f"  written       {self.written_7:>4} (7d)  {self.written_30:>4} (30d)",
            f"  forgotten     {self.forgotten_7:>4} (7d)  {self.forgotten_30:>4} (30d)",
            f"  loaded        {self.loaded_7:>4} (7d)  {self.loaded_30:>4} (30d)",
            f"  kept          {self.kept:>4}  {kept_note}",
            "",
            f"  suggestions   {self.pending_suggestions:>4} pending    last run: {last_run}",
        ]
        for name in self.stale_topics:
            lines.append(f"    stale: {name} \u2014 unused {STALE_TOPIC_DAYS} days; keep?")
        return "\n".join(lines)


def _commit_facts(home: Path) -> list[tuple[datetime, str | None, list[str]]]:
    """Every commit as (date, action, ids). The one git read `status` performs."""
    out: list[tuple[datetime, str | None, list[str]]] = []
    for record in _git.log_records(home):
        try:
            when = datetime.fromisoformat(record["date"])
        except ValueError:
            continue
        if when.tzinfo is None:
            when = when.replace(tzinfo=UTC)
        out.append((when, _field(record["body"], "action"), _ID_RE.findall(record["body"])))
    return out


def _usage_facts(home: Path) -> list[tuple[datetime, str, str]]:
    """Every retained usage entry as (ts, event, target) — store.v1 Core 8."""
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
    """Non-empty lines in inbox.md. Phase 1 never writes it, so this is 0."""
    return len([line for line in _read_lines(home / "inbox.md") if line.strip()])


def status(home: str | os.PathLike[str] | None = None) -> StatusReport:
    """cli.v1 Core 2: the VISION principle 9 numbers, from git and usage.jsonl only."""
    path = _require_store(home)
    now = datetime.now(UTC)
    day7, day30 = now - timedelta(days=7), now - timedelta(days=30)
    kept_before = now - timedelta(days=KEPT_AFTER_DAYS)

    present = {str(memory["id"]) for memory in list_memories(path, include_topics=True)}
    commits = _commit_facts(path)

    written_7 = written_30 = forgotten_7 = forgotten_30 = 0
    kept_ids: set[str] = set()
    for when, action, ids in commits:
        if action == "save":
            written_30 += int(when >= day30)
            written_7 += int(when >= day7)
            if when <= kept_before:
                kept_ids |= {mid for mid in ids if mid in present}
        elif action == "forget":
            forgotten_30 += int(when >= day30)
            forgotten_7 += int(when >= day7)

    usage = _usage_facts(path)
    loaded_7 = sum(1 for when, event, _ in usage if event == "loaded" and when >= day7)
    loaded_30 = sum(1 for when, event, _ in usage if event == "loaded" and when >= day30)
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
        kept=len(kept_ids),
        loaded_7=loaded_7,
        loaded_30=loaded_30,
        pending_suggestions=_pending_suggestions(path),
        # Phase 1 has no suggest job, so there is no run to report. When the Phase 2
        # timer lands it records its own last run; until then "never" is the truth.
        last_suggest_run=None,
    )


def review(home: str | os.PathLike[str] | None = None) -> str:
    """cli.v1 Core 4: the shell form of `/memory review`. Empty inbox says so."""
    path = _require_store(home)
    pending = [line for line in _read_lines(path / "inbox.md") if line.strip()]
    if not pending:
        return (
            "inbox is empty: nothing to review.\n"
            "The daily suggestion inbox arrives with Phase 2 (suggestions.v1, still DRAFT); "
            "Phase 1 writes memories on the correction instead."
        )
    body = "\n".join(f"  {line}" for line in pending)
    return f"{len(pending)} pending suggestion(s) in {path / 'inbox.md'}:\n{body}"


def format_why(records: list[dict[str, object]]) -> str:
    """cli.v1 Core 3: `git log --grep '\\[m-017\\]'`, formatted. Oldest first."""
    blocks: list[str] = []
    for record in reversed(records):
        quote = record.get("quote")
        when = str(record.get("date") or "")[:19]
        shown = json.dumps(quote, ensure_ascii=False) if quote else "(none)"
        blocks.append(
            "\n".join(
                [
                    f"{record.get('action') or 'commit'}  {record.get('id')}  {when}",
                    f"  text:    {record.get('text')}",
                    f"  quote:   {shown}",
                    f"  session: {record.get('session') or '(none)'}",
                    f"  writer:  {record.get('writer') or '(none)'}",
                    f"  target:  {record.get('target') or '(none)'}",
                    f"  commit:  {record.get('commit')}",
                ]
            )
        )
    return "\n\n".join(blocks)


__all__ = [
    "KEPT_AFTER_DAYS",
    "KEPT_GATE",
    "STALE_TOPIC_DAYS",
    "StatusReport",
    "format_why",
    "review",
    "status",
]
