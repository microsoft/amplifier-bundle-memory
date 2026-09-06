#!/usr/bin/env python3
"""store.v1 conformance kit — one line per Core clause, against a fresh temp store.

Run it:  ``uv run python conformance/store/run.py``

Each probe builds its own throwaway store, exercises the clause, and returns one
of the ledger's plain words: **Kept · Not yet · Broken · Can't check**. A probe
that cannot fail is not a probe: every Kept below rests on an assertion that a
regression would trip. Exit code is 0 unless a clause reads Broken.
"""

from __future__ import annotations

import json
import os
import sys
import tempfile
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from datetime import UTC, datetime, timedelta
from pathlib import Path

if __package__ in (None, ""):  # allow `python conformance/store/run.py`
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import amplifier_memory
from amplifier_memory import _git
from amplifier_memory import store as store_mod

Verdict = tuple[str, str]

TURNS = ["never use tabs in YAML files; always two-space indentation, please"]

# The stand-in for "this device's human". store.v1 Core 9 says a hand edit is
# attributed by `git log`, so the isolated global config must carry a human identity:
# the store repository holds none of its own, exactly as on a real device.
HUMAN_IDENTITY = ("Test Human", "human@example.invalid")


@contextmanager
def fresh_store() -> Iterator[Path]:
    """A brand-new store in a temp dir, with git's global/system config out of the way."""
    with tempfile.TemporaryDirectory(prefix="store-v1-conformance-") as tmp:
        root = Path(tmp)
        gitconfig = root / "gitconfig"
        gitconfig.write_text(
            f"[user]\n\tname = {HUMAN_IDENTITY[0]}\n\temail = {HUMAN_IDENTITY[1]}\n",
            encoding="utf-8",
        )
        os.environ["GIT_CONFIG_GLOBAL"] = str(gitconfig)
        os.environ["GIT_CONFIG_NOSYSTEM"] = "1"
        home = root / "memory"
        amplifier_memory.init(home)
        yield home


def _fill(home: Path, lines: int) -> None:
    """A hand edit that seeds `lines` lines: one heading, one blank, the rest memories."""
    body = ["## conventions", ""] + [
        f"- [m-{i:03d}] hand-written memory number {i}" for i in range(1, lines - 1)
    ]
    assert len(body) == lines, f"seed produced {len(body)} lines, wanted {lines}"
    (home / "MEMORY.md").write_text("\n".join(body) + "\n", encoding="utf-8")
    _git.commit(home, "hand edit: seed conventions", ["MEMORY.md"])


# --------------------------------------------------------------------------- probes


def probe_core_1() -> Verdict:
    """Location under AMPLIFIER_MEMORY_HOME, a git repo, one commit per mutation."""
    with fresh_store() as home:
        os.environ["AMPLIFIER_MEMORY_HOME"] = str(home)
        assert amplifier_memory.store_home() == home, "store_home ignored AMPLIFIER_MEMORY_HOME"
        assert _git.is_repo(home), "the store is not a git repository"
        after_init = _git.commit_count(home)
        amplifier_memory.save("never use tabs", "never use tabs", "human", "s-1", ["never use tabs"])
        after_save = _git.commit_count(home)
        amplifier_memory.forget("m-001", home, session_id="s-1")
        after_forget = _git.commit_count(home)
        assert (after_init, after_save, after_forget) == (1, 2, 3), (
            f"commit counts {after_init}/{after_save}/{after_forget}: a mutation was not one commit"
        )
        assert _git.git(["status", "--porcelain"], cwd=home).stdout.strip() == "", "store left dirty"
    return "Kept", f"git repo at $AMPLIFIER_MEMORY_HOME; init/save/forget = {after_forget} commits, tree clean"


def probe_core_2() -> Verdict:
    """The fixed layout, and nothing else counted as memory."""
    with fresh_store() as home:
        present = sorted(p.name for p in home.iterdir() if p.name != ".git")
        assert present == ["MEMORY.md", "declined.md", "inbox.md", "topics", "usage.jsonl"], present
        assert (home / "topics").is_dir(), "topics/ is not a directory"
        (home / "notes.txt").write_text("- [m-900] not memory\n", encoding="utf-8")
        amplifier_memory.save("never use tabs", "never use tabs", "human", "s-1", ["never use tabs"], home=home)
        ids = [m["id"] for m in amplifier_memory.list_memories(home)]
        assert ids == ["m-001"], f"a file outside the layout was treated as memory: {ids}"
    return "Kept", f"exactly {present} on disk; a stray notes.txt is not memory"


def probe_core_3() -> Verdict:
    """MEMORY.md is a flat list, one memory per line, capped at 200 with headings counted."""
    with fresh_store() as home:
        _fill(home, 199)
        saved = amplifier_memory.save(
            "never use tabs in YAML files", "never use tabs in YAML", "assistant", "s-1", TURNS, home=home
        )
        lines = (home / "MEMORY.md").read_text(encoding="utf-8").splitlines()
        assert len(lines) == 200, f"MEMORY.md has {len(lines)} lines, wanted 200"
        assert lines[-1] == f"- [{saved.id}] never use tabs in YAML files", lines[-1]
        parsed = amplifier_memory.list_memories(home)
        assert len(parsed) == 198, f"{len(parsed)} memories among 200 lines: heading/blank miscounted"
    return "Kept", "200 lines incl. a heading and a blank line; line form `- [m-NNN] text`; 198 memories parsed"


def probe_core_4() -> Verdict:
    """The 201st line is refused by the writer, with the cap and both remedies named."""
    with fresh_store() as home:
        _fill(home, 200)
        try:
            amplifier_memory.save("one more", "one more", "human", "s-1", ["one more"], home=home)
        except amplifier_memory.CapExceeded as exc:
            message = str(exc)
        else:
            return "Broken", "the 201st MEMORY.md line was accepted"
        for needle in ("200", "topic file", "/forget"):
            assert needle in message, f"the refusal does not name {needle!r}: {message}"
        assert len((home / "MEMORY.md").read_text().splitlines()) == 200, "the refused line was written"
    return "Kept", "201st refused, file still 200 lines; message names 200 / topic file / /forget"


def probe_core_5() -> Verdict:
    """Topic files: at most 150 lines each, at most 50 files, each begins with a purpose."""
    with fresh_store() as home:
        created = amplifier_memory.save(
            "always two-space indentation", "always two-space indentation", "human", "s-1",
            ["always two-space indentation"], home=home,
            topic="yaml-style", topic_purpose="YAML and JSON style conventions.",
        )
        first_line = (home / "topics" / "yaml-style.md").read_text().splitlines()[0]
        assert first_line == "YAML and JSON style conventions.", first_line
        assert created.target == "topics/yaml-style.md", created.target

        body = ["YAML and JSON style conventions."] + [f"- [m-{i:03d}] line {i}" for i in range(1, 150)]
        (home / "topics" / "yaml-style.md").write_text("\n".join(body) + "\n", encoding="utf-8")
        _git.commit(home, "hand edit: fill the topic", ["topics/yaml-style.md"])
        try:
            amplifier_memory.save("one more", "one more", "human", "s-1", ["one more"], home=home, topic="yaml-style")
        except amplifier_memory.CapExceeded as exc:
            line_cap = str(exc)
        else:
            return "Broken", "the 151st topic line was accepted"

        for i in range(1, 50):
            (home / "topics" / f"t{i:02d}.md").write_text(f"Topic {i}.\n", encoding="utf-8")
        assert len(store_mod.topic_files(home)) == 50, store_mod.topic_files(home)
        try:
            amplifier_memory.save(
                "spill", "spill", "human", "s-1", ["spill"], home=home,
                topic="overflow", topic_purpose="Spill.",
            )
        except amplifier_memory.CapExceeded:
            pass
        else:
            return "Broken", "the 51st topic file was created"
        assert not (home / "topics" / "overflow.md").exists(), "the refused topic file was created"
    return "Kept", f"purpose line required; 151st line refused ({line_cap.split(';')[0]}); 51st file refused"


def probe_core_6() -> Verdict:
    """Provenance lives in git: id, text, verbatim quote, session, writer — and `why` reads it back."""
    with fresh_store() as home:
        quote = "never use tabs in YAML files; always two-space indentation"
        amplifier_memory.save("never use tabs in YAML files", quote, "assistant", "sess-abc", TURNS, home=home)
        message = _git.git(["log", "-1", "--format=%B"], cwd=home).stdout.strip()
        for needle in ("[m-001]", "never use tabs in YAML files", f'quote: "{quote}"',
                       "session: sess-abc", "writer: assistant"):
            assert needle in message, f"the commit message is missing {needle!r}:\n{message}"
        record = amplifier_memory.why("m-001", home)[0]
        assert record["quote"] == quote, record["quote"]
        assert record["session"] == "sess-abc" and record["writer"] == "assistant", record
        assert "provenance.json" not in [p.name for p in home.iterdir()], "a separate provenance store exists"
    return "Kept", "commit carries id/text/quote/session/writer; why('m-001') parses all five back from git log"


def probe_core_7() -> Verdict:
    """declined.md — the file exists; the exact-match block is Phase 2 (suggestions.v1, DRAFT)."""
    with fresh_store() as home:
        assert (home / "declined.md").is_file(), "declined.md was not created by init"
        assert (home / "declined.md").read_text(encoding="utf-8") == "", "declined.md is not empty"
    evidence = (
        "declined.md is created and empty, but Phase 1 has no decline path: the append and the "
        "exact-match re-proposal block belong to suggestions.v1, which is (DRAFT) and unimplemented"
    )
    return "Can't check", evidence


def probe_core_8() -> Verdict:
    """usage.jsonl records the four fields and is truncated to 90 days on each write."""
    with fresh_store() as home:
        usage = home / "usage.jsonl"
        old = {"ts": (datetime.now(UTC) - timedelta(days=91)).isoformat(),
               "event": "loaded", "target": "MEMORY.md", "session_id": "s-old"}
        recent = {"ts": (datetime.now(UTC) - timedelta(days=1)).isoformat(),
                  "event": "read", "target": "topics/yaml-style.md", "session_id": "s-recent"}
        usage.write_text(json.dumps(old) + "\n" + json.dumps(recent) + "\n", encoding="utf-8")
        before = len(usage.read_text().splitlines())
        entry = amplifier_memory.log_usage("loaded", "MEMORY.md", "s-new", home)
        after = [json.loads(line) for line in usage.read_text().splitlines()]
        assert set(entry) == {"ts", "event", "target", "session_id"}, entry
        assert [e["session_id"] for e in after] == ["s-recent", "s-new"], after
        assert (home / "MEMORY.md").read_text() == "", "logging a read mutated MEMORY.md"
    return "Kept", f"{before} entries in, {len(after)} out: the 91-day-old entry dropped, nothing else deleted"


def probe_core_9() -> Verdict:
    """Two writers, one path: a hand edit is legitimate and the writer never clobbers it."""
    with fresh_store() as home:
        (home / "MEMORY.md").write_text("- [m-007] hand-written by the human\n", encoding="utf-8")
        _git.commit(home, "hand edit: add a memory with an editor", ["MEMORY.md"])
        seen = [m["id"] for m in amplifier_memory.list_memories(home)]
        assert seen == ["m-007"], seen
        nxt = amplifier_memory.save("never use tabs", "never use tabs", "human", "s-1", ["never use tabs"], home=home)
        assert nxt.id == "m-008", f"the writer reused an id a human had used: {nxt.id}"
        text = (home / "MEMORY.md").read_text()
        assert "- [m-007] hand-written by the human" in text, "the writer clobbered the hand edit"
        assert len(_git.log_records(home)) == 3, "a hand commit and a writer commit are both ordinary commits"
        # "git log attributes them": the hand commit must be the human's, the writer's its own.
        authors = _git.git(["log", "--format=%an", "-3"], cwd=home).stdout.split("\n")
        assert authors[0] == store_mod.STORE_USER_NAME, f"the writer commit is not attributed: {authors}"
        assert authors[1] == HUMAN_IDENTITY[0], f"the hand commit is not the human's: {authors}"
        assert _git.get_config(home, "user.name") == HUMAN_IDENTITY[0], (
            "the store repository carries an identity of its own; a hand commit would be misattributed"
        )
    return "Kept", (
        f"hand edit read back as m-007 and preserved; the writer then issued m-008; both are git "
        f"commits, attributed {authors[1]!r} (hand) and {authors[0]!r} (writer)"
    )


def probe_core_10() -> Verdict:
    """Bounded by construction: every Phase 1 growth surface refuses or truncates."""
    bounded = []
    with fresh_store() as home:
        _fill(home, 200)
        try:
            amplifier_memory.save("x", "x", "human", "s", ["x"], home=home)
        except amplifier_memory.CapExceeded:
            bounded.append("MEMORY.md 200")
        else:
            return "Broken", "MEMORY.md grew past 200 lines"
    with fresh_store() as home:
        body = ["Purpose."] + [f"- [m-{i:03d}] line {i}" for i in range(1, 150)]
        (home / "topics" / "t.md").write_text("\n".join(body) + "\n", encoding="utf-8")
        try:
            amplifier_memory.save("x", "x", "human", "s", ["x"], home=home, topic="t")
        except amplifier_memory.CapExceeded:
            bounded.append("topic 150")
        else:
            return "Broken", "a topic file grew past 150 lines"
        for i in range(1, 50):
            (home / "topics" / f"t{i:02d}.md").write_text("Purpose.\n", encoding="utf-8")
        try:
            amplifier_memory.save("x", "x", "human", "s", ["x"], home=home, topic="new", topic_purpose="P.")
        except amplifier_memory.CapExceeded:
            bounded.append("topics 50")
        else:
            return "Broken", "a 51st topic file was created"
        stale = {"ts": (datetime.now(UTC) - timedelta(days=91)).isoformat(),
                 "event": "loaded", "target": "MEMORY.md", "session_id": "s-old"}
        (home / "usage.jsonl").write_text(json.dumps(stale) + "\n", encoding="utf-8")
        amplifier_memory.log_usage("loaded", "MEMORY.md", "s-new", home)
        assert len((home / "usage.jsonl").read_text().splitlines()) == 1, "usage.jsonl is unbounded"
        bounded.append("usage 90d")
    return "Kept", (
        f"all Phase 1 growth surfaces bounded ({', '.join(bounded)}); the inbox 30-day expiry is "
        "suggestions.v1 (DRAFT), outside Phase 1"
    )


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


def main() -> int:
    broken = 0
    for clause, probe in PROBES:
        try:
            verdict, evidence = probe()
        except Exception as exc:  # noqa: BLE001 - a probe that raises is Broken, never a silent pass
            verdict, evidence = "Broken", f"{type(exc).__name__}: {exc}".replace("\n", " ")[:300]
        if verdict == "Broken":
            broken += 1
        print(f"Core {clause} — {verdict} — {evidence}")
    return 1 if broken else 0


if __name__ == "__main__":
    raise SystemExit(main())
