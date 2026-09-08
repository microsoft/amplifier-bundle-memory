#!/usr/bin/env python3
"""store.v3 conformance kit — one line per Core clause, against a fresh temp store.

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
from concurrent.futures import ThreadPoolExecutor
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

# The stand-in for "this device's human". store.v2 Core 9 says a hand edit is
# attributed by `git log`, so the isolated global config must carry a human identity:
# the store repository holds none of its own, exactly as on a real device.
HUMAN_IDENTITY = ("Test Human", "human@example.invalid")


@contextmanager
def fresh_store() -> Iterator[Path]:
    """A brand-new store in a temp dir, with git's global/system config out of the way."""
    with tempfile.TemporaryDirectory(prefix="store-v2-conformance-") as tmp:
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


def _committed_lines(home: Path, target: str = "MEMORY.md") -> list[str]:
    """`target` as the committed tree has it \u2014 the state a writer must be judged on."""
    text = _git.show(home, f"HEAD:{target}")
    assert text is not None, f"HEAD does not carry {target}"
    return [line for line in text.splitlines() if line.strip()]


def probe_concurrency(workers: int = 8) -> Verdict:
    """store.v2 Core 1 under concurrency: N saves at once, N well-formed lines, N commits.

    The clause says every mutation is one commit. Before this probe existed, three saves
    issued in one model turn interleaved on an unlocked read-modify-write and left the
    steward's MEMORY.md with two lines, a headless fragment, and one call that reported
    success for a line that was never committed
    (`.converge/feedback/2026-09-06-kicked-the-tires-transcript.md`).

    It discriminates: with the lock removed, the same eight calls leave one line.
    """
    with fresh_store() as home:
        texts = [f"concurrent memory number {i}" for i in range(1, workers + 1)]
        with ThreadPoolExecutor(max_workers=workers) as pool:
            results = list(
                pool.map(
                    lambda text: amplifier_memory.save(
                        text, text, "human", "s-cc", [text], home=home
                    ),
                    texts,
                )
            )
        committed = _committed_lines(home)
        ids = sorted(r.id for r in results)
        saves = [r for r in _git.log_records(home) if "action: save" in r["body"]]

        assert len(committed) == workers, f"{len(committed)} lines committed, wanted {workers}"
        assert ids == [f"m-{i:03d}" for i in range(1, workers + 1)], (
            f"ids have a gap or a duplicate: {ids}"
        )
        assert len(saves) == workers, f"{len(saves)} save commits for {workers} saves"
        for line in committed:
            assert store_mod.wellformed(line), f"a concurrent write left a malformed line: {line!r}"
        for result in results:
            assert result.line in committed, (
                f"{result.id} was reported saved but is not in the committed tree"
            )
        assert _git.git(["status", "--porcelain"], cwd=home).stdout.strip() == "", (
            "store left dirty"
        )
    return "Kept", (
        f"{workers} concurrent saves \u2192 {len(committed)} well-formed lines, ids m-001..m-{workers:03d} "
        f"with no gap or duplicate, {len(saves)} save commits, every returned id present in "
        "`git show HEAD:MEMORY.md`, tree clean"
    )


# --------------------------------------------------------------------------- probes


def probe_reading_leaves_no_commit() -> Verdict:
    """store.v2 §1's exception: a session that only READS memory leaves no commit behind.

    The clause exists because four `usage: loaded` commits landed in one afternoon on the
    steward's store for sessions that changed nothing. It discriminates: restore the
    commit inside `log_usage` and `after` is three commits higher than `before`.

    The second half is the migration a pre-v2 store needs — including the steward's, which
    still tracks `usage.jsonl` with ~10 `usage: loaded` commits. The first append untracks
    it in exactly one visible commit, and never again.
    """
    with fresh_store() as home:
        before = _git.commit_count(home)
        for _ in range(3):
            amplifier_memory.log_usage("loaded", "MEMORY.md", "s-read", home)
        after = _git.commit_count(home)
        events = [json.loads(line) for line in (home / "usage.jsonl").read_text().splitlines()]
        assert after == before, f"three loads left {after - before} commit(s) behind"
        assert len(events) == 3, f"{len(events)} events written for three loads"
        assert not _git.is_tracked(home, "usage.jsonl"), "a fresh v2 store still tracks usage.jsonl"
        assert _git.git(["status", "--porcelain"], cwd=home).stdout.strip() == "", (
            "store left dirty"
        )

    # A store created before store.v2: usage.jsonl is tracked and committed.
    with fresh_store() as home:
        (home / ".gitignore").unlink()
        (home / "usage.jsonl").write_text("", encoding="utf-8")
        _git.commit(home, "pre-v2 store: usage.jsonl tracked", ["usage.jsonl", ".gitignore"])
        assert _git.is_tracked(home, "usage.jsonl"), "the pre-v2 fixture does not track usage.jsonl"
        pre = _git.commit_count(home)
        amplifier_memory.log_usage("loaded", "MEMORY.md", "s-1", home)
        migrated = _git.commit_count(home)
        subject = _git.git(["log", "-1", "--format=%s"], cwd=home).stdout.strip()
        amplifier_memory.log_usage("loaded", "MEMORY.md", "s-2", home)
        settled = _git.commit_count(home)
        assert migrated == pre + 1, f"the migration made {migrated - pre} commits, wanted 1"
        assert subject == store_mod.UNTRACK_USAGE_SUBJECT, subject
        assert settled == migrated, "the migration ran twice"
        assert not _git.is_tracked(home, "usage.jsonl"), "usage.jsonl is still tracked"
        assert len((home / "usage.jsonl").read_text().splitlines()) == 2, "an event was lost"
    return "Kept", (
        f"three loads on a v2 store -> {after - before} commits and {len(events)} events; a "
        f"pre-v2 store that tracks usage.jsonl migrates in exactly one commit ({subject!r}) "
        "and never again, losing no event"
    )


def probe_instance_resolution() -> Verdict:
    """store.v3 §1's four cases, on a fake home directory: caller > env > default > older path."""
    with tempfile.TemporaryDirectory(prefix="store-v3-home-") as tmp:
        house = Path(tmp)
        saved = {k: os.environ.get(k) for k in ("HOME", "AMPLIFIER_MEMORY_HOME")}
        try:
            os.environ["HOME"] = str(house)
            os.environ.pop("AMPLIFIER_MEMORY_HOME", None)
            assert Path.home() == house, Path.home()

            neither = store_mod.store_home()
            assert neither == house / ".amplifier-memory", neither

            legacy = house / ".amplifier" / "memory"
            legacy.mkdir(parents=True)
            migrating = store_mod.store_home()
            assert migrating == legacy, migrating
            assert store_mod.legacy_store_present() is True

            os.environ["AMPLIFIER_MEMORY_HOME"] = str(house / "from-the-env")
            from_env = store_mod.store_home()
            assert from_env == house / "from-the-env", from_env

            explicit = store_mod.store_home(house / "named")
            assert explicit == house / "named", explicit
        finally:
            for key, value in saved.items():
                if value is None:
                    os.environ.pop(key, None)
                else:
                    os.environ[key] = value
    return "Kept", (
        f"resolution order proved on a fake home: explicit {explicit.name!r} > "
        f"$AMPLIFIER_MEMORY_HOME {from_env.name!r} > the default {neither.name!r}; and with "
        "neither the default directory nor the env set, an existing ~/.amplifier/memory is "
        "the default (the \u00a71 migration), so a device that has never seen v3 keeps its store"
    )


def probe_core_1() -> Verdict:
    """An instance: resolved per §1, a git repo, one commit per change — none for a read."""
    verdict, resolution = probe_instance_resolution()
    if verdict != "Kept":
        return verdict, resolution
    with fresh_store() as home:
        os.environ["AMPLIFIER_MEMORY_HOME"] = str(home)
        assert amplifier_memory.store_home() == home, "store_home ignored AMPLIFIER_MEMORY_HOME"
        assert _git.is_repo(home), "the store is not a git repository"
        after_init = _git.commit_count(home)
        amplifier_memory.save(
            "never use tabs", "never use tabs", "human", "s-1", ["never use tabs"]
        )
        after_save = _git.commit_count(home)
        amplifier_memory.edit(
            "m-001",
            "never use tabs in YAML",
            "never use tabs in YAML",
            "human",
            "s-1",
            ["never use tabs in YAML"],
        )
        after_edit = _git.commit_count(home)
        amplifier_memory.forget("m-001", home, session_id="s-1")
        after_forget = _git.commit_count(home)
        assert (after_init, after_save, after_edit, after_forget) == (1, 2, 3, 4), (
            f"commit counts {after_init}/{after_save}/{after_edit}/{after_forget}: a change was "
            "not exactly one commit"
        )
        assert _git.git(["status", "--porcelain"], cwd=home).stdout.strip() == "", (
            "store left dirty"
        )
    # The clause's "every mutation is one commit" has to hold when mutations overlap,
    # which is where it actually broke on the steward's device.
    verdict, concurrency = probe_concurrency()
    if verdict != "Kept":
        return verdict, concurrency
    # …and its one exception: a usage append is written without a commit.
    verdict, reading = probe_reading_leaves_no_commit()
    if verdict != "Kept":
        return verdict, reading
    return "Kept", (
        f"{resolution}; git repo at $AMPLIFIER_MEMORY_HOME; init/save/edit/forget = "
        f"{after_forget} commits, tree clean; under concurrency: {concurrency}; the §1 "
        f"exception: {reading}"
    )


def probe_core_2() -> Verdict:
    """The fixed layout, and nothing else counted as memory — including the plumbing."""
    with fresh_store() as home:
        plumbing = {".git", store_mod.STORE_GITIGNORE}
        present = sorted(p.name for p in home.iterdir() if p.name not in plumbing)
        assert present == [
            "MEMORY.md",
            "config.yaml",
            "declined.md",
            "inbox.md",
            "sessions.jsonl",
            "topics",
            "usage.jsonl",
        ], present
        assert (home / store_mod.STORE_GITIGNORE).is_file(), ".gitignore (plumbing) was not created"
        assert (home / "topics").is_dir(), "topics/ is not a directory"
        (home / "notes.txt").write_text("- [m-900] not memory\n", encoding="utf-8")
        amplifier_memory.save(
            "never use tabs", "never use tabs", "human", "s-1", ["never use tabs"], home=home
        )
        ids = [m["id"] for m in amplifier_memory.list_memories(home)]
        assert ids == ["m-001"], f"a file outside the layout was treated as memory: {ids}"

        # \u00a72: config.yaml and sessions.jsonl are plumbing, not memory. The proof that
        # they are not memory is that neither reaches a reader of memory, and that a
        # session record leaves no commit (they are also never injected/suggested/cited,
        # which the session and suggestions kits check on their own surfaces).
        amplifier_memory.record_session(home, "s-conformance", "worker")
        before = _git.commit_count(home)
        amplifier_memory.record_session(home, "s-two", "recipe")
        origins = amplifier_memory.session_origins(home)
        config = amplifier_memory.instance_enabled(home)
        assert _git.commit_count(home) == before, "a session record made a commit"
        assert origins == {"s-conformance": "worker", "s-two": "recipe"}, origins
        assert [m["id"] for m in amplifier_memory.list_memories(home)] == ["m-001"], (
            "config.yaml or sessions.jsonl was read back as memory"
        )
        # (`notes.txt` above is deliberately untracked, so the tree is not clean here —
        # what matters is that the two plumbing files are not what git is reporting.)
        porcelain = _git.git(["status", "--porcelain"], cwd=home).stdout
        assert "sessions.jsonl" not in porcelain and "config.yaml" not in porcelain, porcelain
        tracked = sorted(_git.git(["ls-files"], cwd=home).stdout.split())
        assert "config.yaml" in tracked and "sessions.jsonl" not in tracked, tracked
    return "Kept", (
        f"exactly {present} on disk; a stray notes.txt is not memory; `.lock` and `.gitignore` "
        f"are plumbing and counted as neither. config.yaml is tracked (written once by init, "
        f"read back enabled={config}) and sessions.jsonl is not: two session records "
        f"({origins}) added no commit and never appear in `git status`, so a session start "
        "never costs a commit, and neither file is ever read back as memory"
    )


def probe_hostile_corpus() -> Verdict:
    """store.v2 Core 3 against the engineering council's hostile corpus (2026-09-06).

    "One memory is one line" is a claim about what reaches the disk, so every input here
    is one that used to reach it. Each was reproduced by execution against the installed
    library before the fix: a U+2028 text was written as two lines and then reported as
    "did not land"; a 131 KB text was refused *after* `git add` had staged it; one
    accented byte in `MEMORY.md` killed `doctor`; `quote='e'` authorised a memory the
    human never stated.

    It discriminates: remove any one refusal and the matching assertion below fails.
    """
    findings: list[str] = []
    with fresh_store() as home:
        amplifier_memory.save(
            "never use tabs in YAML files",
            "never use tabs in YAML files",
            "human",
            "s-1",
            ["never use tabs in YAML files"],
            home=home,
        )
        memory = home / "MEMORY.md"
        before = memory.read_bytes()

        hostile = {
            "U+2028": "never use tabs\u2028always two-space",
            "U+2029": "never use tabs\u2029always two-space",
            "U+0085": "never use tabs\x85always two-space",
            "lone CR": "never use tabs\ralways two-space",
            "BOM": "\ufeffnever use tabs in YAML files",
            "NUL": "never use tabs\x00always two-space",
            "131 KB": "x" * 131_072,
        }
        for label, text in hostile.items():
            try:
                amplifier_memory.save(text, text, "human", "s-1", [text], home=home)
            except ValueError as exc:
                assert str(exc).startswith("refused: "), (
                    f"{label}: refusal is not one sentence: {exc}"
                )
            else:
                return "Broken", f"a {label} memory text was accepted"
            assert memory.read_bytes() == before, f"{label} reached the disk before the refusal"
            assert _git.git(["status", "--porcelain"], cwd=home).stdout.strip() == "", (
                f"{label} left something staged"
            )
        findings.append(
            f"{len(hostile)} hostile texts refused before any write, file byte-identical"
        )

        try:
            amplifier_memory.save(
                "bkrabach prefers dark mode",
                "e",
                "assistant",
                "s-1",
                ["Great remember these for me"],
                home=home,
            )
        except amplifier_memory.QuoteNotHuman as exc:
            assert "too short to identify a human turn" in str(exc), str(exc)
        else:
            return "Broken", "a one-character quote authorised a memory"
        findings.append("quote='e' refused as too short to identify a human turn")

        # One raw byte that is not UTF-8, as a hand edit leaves it (Core 9 invites them).
        memory.write_bytes(memory.read_bytes() + b"- [m-002] Jos\xe9 prefers short reviews\n")
        offset = memory.read_bytes().index(b"\xe9")
        check = amplifier_memory.verify_store(home)
        report = amplifier_memory.doctor(home, installed_sha=None, remote_sha=None)
        assert check.decode_error_offset == offset, (
            f"verify_store missed the bad byte at {offset}: {check.render()}"
        )
        assert report.exit_code == 1, "doctor passed a store it cannot decode"
        assert f"byte offset {offset} is not UTF-8" in report.render(), report.render()
        assert len(amplifier_memory.list_memories(home)) == 2, (
            "a reader dropped a line it could show"
        )
        findings.append(
            f"one non-UTF-8 byte -> a doctor FAIL row naming offset {offset}, exit 1, no traceback"
        )

        said: list[str] = []
        repaired = amplifier_memory.repair_store(home, announce=said.append)
        assert repaired.discarded, "repair discarded a line without saying which"
        assert any("Jos" in line for line in said), said
        assert amplifier_memory.verify_store(home).ok, "the repair did not produce a clean file"
        findings.append(
            f"repair named {len(repaired.discarded)} discarded line(s) before committing"
        )
    return "Kept", "; ".join(findings)


def probe_core_3() -> Verdict:
    """MEMORY.md is a flat list, one memory per line, capped at 200 with headings counted."""
    with fresh_store() as home:
        _fill(home, 199)
        saved = amplifier_memory.save(
            "never use tabs in YAML files",
            "never use tabs in YAML",
            "assistant",
            "s-1",
            TURNS,
            home=home,
        )
        lines = (home / "MEMORY.md").read_text(encoding="utf-8").splitlines()
        assert len(lines) == 200, f"MEMORY.md has {len(lines)} lines, wanted 200"
        assert lines[-1] == f"- [{saved.id}] never use tabs in YAML files", lines[-1]
        parsed = amplifier_memory.list_memories(home)
        assert len(parsed) == 198, (
            f"{len(parsed)} memories among 200 lines: heading/blank miscounted"
        )
    # "One memory per line" is only true if a text that would become two lines cannot be
    # written at all, so the hostile corpus is part of this clause, not a separate one.
    verdict, hostile = probe_hostile_corpus()
    if verdict != "Kept":
        return verdict, hostile
    return "Kept", (
        "200 lines incl. a heading and a blank line; line form `- [m-NNN] text`; 198 memories "
        f"parsed; hostile corpus: {hostile}"
    )


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
        for needle in ("200", "topic file", "/memory forget"):
            assert needle in message, f"the refusal does not name {needle!r}: {message}"
        assert len((home / "MEMORY.md").read_text().splitlines()) == 200, (
            "the refused line was written"
        )
    return (
        "Kept",
        "201st refused, file still 200 lines; message names 200 / topic file / /memory forget",
    )


def probe_core_5() -> Verdict:
    """Topic files: at most 150 lines each, at most 50 files, each begins with a purpose."""
    with fresh_store() as home:
        created = amplifier_memory.save(
            "always two-space indentation",
            "always two-space indentation",
            "human",
            "s-1",
            ["always two-space indentation"],
            home=home,
            topic="yaml-style",
            topic_purpose="YAML and JSON style conventions.",
        )
        first_line = (home / "topics" / "yaml-style.md").read_text().splitlines()[0]
        assert first_line == "YAML and JSON style conventions.", first_line
        assert created.target == "topics/yaml-style.md", created.target

        body = ["YAML and JSON style conventions."] + [
            f"- [m-{i:03d}] line {i}" for i in range(1, 150)
        ]
        (home / "topics" / "yaml-style.md").write_text("\n".join(body) + "\n", encoding="utf-8")
        _git.commit(home, "hand edit: fill the topic", ["topics/yaml-style.md"])
        try:
            amplifier_memory.save(
                "one more", "one more", "human", "s-1", ["one more"], home=home, topic="yaml-style"
            )
        except amplifier_memory.CapExceeded as exc:
            line_cap = str(exc)
        else:
            return "Broken", "the 151st topic line was accepted"

        for i in range(1, 50):
            (home / "topics" / f"t{i:02d}.md").write_text(f"Topic {i}.\n", encoding="utf-8")
        assert len(store_mod.topic_files(home)) == 50, store_mod.topic_files(home)
        try:
            amplifier_memory.save(
                "spill",
                "spill",
                "human",
                "s-1",
                ["spill"],
                home=home,
                topic="overflow",
                topic_purpose="Spill.",
            )
        except amplifier_memory.CapExceeded:
            pass
        else:
            return "Broken", "the 51st topic file was created"
        assert not (home / "topics" / "overflow.md").exists(), "the refused topic file was created"
    return (
        "Kept",
        f"purpose line required; 151st line refused ({line_cap.split(';')[0]}); 51st file refused",
    )


def probe_core_6() -> Verdict:
    """Provenance in git: id/text/quote/session/writer/action, `was:` on an edit, `forgot` on a removal.

    The two v2 additions each answer a defect that shipped. `git log --oneline` showed a
    save and its forget as identical lines (Dana persona run), so a forget's subject now
    begins `forgot`. And an edit that recorded only its result could not be told from a
    second memory, so it carries `was:` and keeps the id.
    """
    with fresh_store() as home:
        quote = "never use tabs in YAML files; always two-space indentation"
        amplifier_memory.save(
            "never use tabs in YAML files", quote, "assistant", "sess-abc", TURNS, home=home
        )
        message = _git.git(["log", "-1", "--format=%B"], cwd=home).stdout.strip()
        for needle in (
            "[m-001]",
            "never use tabs in YAML files",
            f'quote: "{quote}"',
            "session: sess-abc",
            "writer: assistant",
            "action: save",
        ):
            assert needle in message, f"the commit message is missing {needle!r}:\n{message}"
        record = amplifier_memory.why("m-001", home)[0]
        assert record["quote"] == quote, record["quote"]
        assert record["session"] == "sess-abc" and record["writer"] == "assistant", record
        assert "provenance.json" not in [p.name for p in home.iterdir()], (
            "a separate provenance store exists"
        )

        # An edit: same id, new text, `was:` naming what it replaced.
        edited = amplifier_memory.edit(
            "m-001", "never use tabs in YAML", quote, "assistant", "sess-abc", TURNS, home=home
        )
        edit_message = _git.git(["log", "-1", "--format=%B"], cwd=home).stdout.strip()
        assert edited.id == "m-001", f"the edit reassigned the id: {edited.id}"
        assert edit_message.splitlines()[0] == "[m-001] never use tabs in YAML", edit_message
        assert 'was: "never use tabs in YAML files"' in edit_message, edit_message
        assert "action: edit" in edit_message, edit_message
        assert [m["text"] for m in amplifier_memory.list_memories(home)] == [
            "never use tabs in YAML"
        ]

        # A forget: the subject says so, in `git log --oneline`, before anything is parsed.
        amplifier_memory.forget("m-001", home, session_id="sess-abc")
        oneline = _git.git(["log", "--oneline", "-1"], cwd=home).stdout.strip()
        assert "forgot [m-001]" in oneline, oneline
        actions = [(r["action"], r["was"]) for r in amplifier_memory.why("m-001", home)]
        assert actions == [
            ("forget", None),
            ("edit", "never use tabs in YAML files"),
            ("save", None),
        ], actions
    return "Kept", (
        "commit carries id/text/quote/session/writer/action; an edit keeps m-001 and carries "
        f'was: "never use tabs in YAML files"; a forget reads {oneline.split(" ", 1)[1]!r} in '
        "git log --oneline; why('m-001') parses all three back from git log"
    )


def probe_core_7() -> Verdict:
    """declined.md — append-only, and a declined text is never proposed again (Phase 2 path)."""
    from amplifier_memory import inbox

    with fresh_store() as home:
        assert (home / "declined.md").is_file(), "declined.md was not created by init"
        assert (home / "declined.md").read_text(encoding="utf-8") == "", "declined.md is not empty"
        cand = inbox.Candidate(
            text="never use tabs in YAML files", quote="never use tabs", session="deadbeef"
        )
        landed = inbox.append(home, [cand])
        assert [s.text for s in landed] == [cand.text], landed
        inbox.decline(landed[0].id, home)
        declined = (home / "declined.md").read_text(encoding="utf-8")
        assert declined.strip().endswith(f'{cand.text}  quote: "{cand.quote}"'), declined
        assert inbox.pending(home) == [], "declined item still pending"
        again = inbox.append(home, [cand])
        assert again == [], f"a declined text was proposed again: {again}"
        assert inbox.is_declined(cand.text, home)

        # \u00a77: "matched exactly by code on text OR quote" \u2014 the field a model does not
        # rewrite. Measured over 210 calls and 7 models, a re-proposal paraphrases the
        # text and copies the quote verbatim, so text alone let a decline come back.
        reworded = inbox.Candidate(
            text="tabs are banned in YAML - use two spaces", quote=cand.quote, session="deadbeef"
        )
        paraphrase = inbox.append(home, [reworded])
        assert paraphrase == [], f"a declined suggestion came back reworded: {paraphrase}"
        assert inbox.declined_quotes(home) == [cand.quote]

        # A line written before v3 has two fields, stays readable, and still blocks.
        (home / "declined.md").write_text("- 2026-09-01 always rebase\n", encoding="utf-8")
        assert inbox.declined_entries(home) == [("always rebase", "")]
        assert inbox.is_declined("always rebase", home)

        (home / "declined.md").write_text(declined, encoding="utf-8")
        declined_after = (home / "declined.md").read_text(encoding="utf-8")
        assert declined_after == declined, "declined.md was rewritten, not appended"
    return "Kept", (
        f"decline appended {declined.strip()!r} to declined.md \u2014 the verbatim quote on the "
        "line, as \u00a77 fixes it; the same text offered again was not proposed, and neither "
        "was the same quote wearing a paraphrased text (append returned [] both times); a "
        "pre-v3 two-field line still parses and still blocks; declined.md is appended, "
        "never rewritten"
    )


def probe_core_8() -> Verdict:
    """usage.jsonl: loaded/read/cited with four fields, truncated to 90 days, never committed."""
    with fresh_store() as home:
        usage = home / "usage.jsonl"
        old = {
            "ts": (datetime.now(UTC) - timedelta(days=91)).isoformat(),
            "event": "loaded",
            "target": "MEMORY.md",
            "session_id": "s-old",
        }
        recent = {
            "ts": (datetime.now(UTC) - timedelta(days=1)).isoformat(),
            "event": "read",
            "target": "topics/yaml-style.md",
            "session_id": "s-recent",
        }
        usage.write_text(json.dumps(old) + "\n" + json.dumps(recent) + "\n", encoding="utf-8")
        before = len(usage.read_text().splitlines())
        entry = amplifier_memory.log_usage("loaded", "MEMORY.md", "s-new", home)
        after = [json.loads(line) for line in usage.read_text().splitlines()]
        assert set(entry) == {"ts", "event", "target", "session_id"}, entry
        assert [e["session_id"] for e in after] == ["s-recent", "s-new"], after
        assert (home / "MEMORY.md").read_text() == "", "logging a read mutated MEMORY.md"

        # store.v2 §8: `cited` records each time the assistant names a memory at use, so
        # `status` can derive a citation rate. Its target is a memory id, not a file.
        cited = amplifier_memory.record_citation("m-017", "s-new", home)
        assert cited["event"] == "cited" and cited["target"] == "m-017", cited
        assert set(cited) == {"ts", "event", "target", "session_id"}, cited
        for bad in (
            lambda: amplifier_memory.record_citation("MEMORY.md", "s", home),
            lambda: amplifier_memory.log_usage("cited", "topics/x.md", "s", home),
        ):
            try:
                bad()
            except ValueError:
                continue
            return "Broken", "a `cited` event accepted a target that is not a memory id"
    return "Kept", (
        f"{before} entries in, {len(after) + 1} out: the 91-day-old entry dropped, nothing else "
        "deleted; a `cited` event carries the memory id and refuses a file target; nothing "
        "committed (see Core 1's §1-exception evidence)"
    )


def probe_core_9() -> Verdict:
    """Two writers, one path: a hand edit is legitimate and the writer never clobbers it."""
    with fresh_store() as home:
        (home / "MEMORY.md").write_text("- [m-007] hand-written by the human\n", encoding="utf-8")
        _git.commit(home, "hand edit: add a memory with an editor", ["MEMORY.md"])
        seen = [m["id"] for m in amplifier_memory.list_memories(home)]
        assert seen == ["m-007"], seen
        nxt = amplifier_memory.save(
            "never use tabs", "never use tabs", "human", "s-1", ["never use tabs"], home=home
        )
        assert nxt.id == "m-008", f"the writer reused an id a human had used: {nxt.id}"
        text = (home / "MEMORY.md").read_text()
        assert "- [m-007] hand-written by the human" in text, "the writer clobbered the hand edit"
        assert len(_git.log_records(home)) == 3, (
            "a hand commit and a writer commit are both ordinary commits"
        )
        # "git log attributes them": the hand commit must be the human's, the writer's its own.
        authors = _git.git(["log", "--format=%an", "-3"], cwd=home).stdout.split("\n")
        assert authors[0] == store_mod.STORE_USER_NAME, (
            f"the writer commit is not attributed: {authors}"
        )
        assert authors[1] == HUMAN_IDENTITY[0], f"the hand commit is not the human's: {authors}"
        assert _git.get_config(home, "user.name") == HUMAN_IDENTITY[0], (
            "the store repository carries an identity of its own; a hand commit would be misattributed"
        )

        # Two writers, *interleaved*: a hand edit committed between concurrent writer
        # saves. Both must land \u2014 the hand line survives, the writer's ids skip it, and
        # every writer line that was reported saved is in the committed tree.
        def hand_edit() -> None:
            with store_mod._exclusive(home):
                path = home / "MEMORY.md"
                path.write_text(
                    path.read_text(encoding="utf-8") + "- [m-500] written by hand mid-flight\n",
                    encoding="utf-8",
                )
                _git.commit(home, "hand edit: while the writer was working", ["MEMORY.md"])

        with ThreadPoolExecutor(max_workers=5) as pool:
            futures = [
                pool.submit(
                    amplifier_memory.save,
                    f"writer line {i}",
                    f"writer line {i}",
                    "human",
                    "s-9",
                    [f"writer line {i}"],
                    home=home,
                )
                for i in range(1, 5)
            ]
            futures.append(pool.submit(hand_edit))
            written = [f.result() for f in futures[:4]]
            futures[4].result()

        interleaved = _committed_lines(home)
        assert "- [m-500] written by hand mid-flight" in interleaved, (
            "a writer clobbered a hand edit made while it was working"
        )
        for result in written:
            assert result.line in interleaved, f"{result.id} reported saved but is not committed"
        assert all(store_mod.wellformed(line) for line in interleaved), interleaved
        assert _git.git(["status", "--porcelain"], cwd=home).stdout.strip() == "", (
            "store left dirty"
        )
        next_id = amplifier_memory.save(
            "after the hand edit",
            "after the hand edit",
            "human",
            "s-9",
            ["after the hand edit"],
            home=home,
        )
        # The clause is "the id is never reused", not "the next id is exactly 501": the
        # hand commit may land before or after any of the four concurrent saves compute
        # theirs, so a writer that saw m-500 legitimately issues m-501 and this one m-502.
        # Asserting the exact number asserted a thread schedule, and passed by luck.
        issued = [r.id for r in written] + [next_id.id]
        assert len(set(issued)) == len(issued), f"an id was issued twice: {issued}"
        assert "m-500" not in issued, f"the writer reused the hand-written id: {issued}"
        assert int(next_id.id.split("-")[1]) > 500, (
            f"the writer issued an id below the hand-written one: {next_id.id}"
        )
    return "Kept", (
        f"hand edit read back as m-007 and preserved; the writer then issued m-008; both are git "
        f"commits, attributed {authors[1]!r} (hand) and {authors[0]!r} (writer); interleaved: a "
        f"hand commit taken under the store lock during 4 concurrent saves left "
        f"{len(interleaved)} well-formed lines, every writer line present, next id {next_id.id}. "
        "Caveat: the lock protects writers from each other and any hand edit made through this "
        "library or the CLI; a human editing MEMORY.md in vi takes no lock, so an editor save "
        "landing inside a writer's read-modify-write is still last-writer-wins (store.v2 Core 9 "
        "asks for no more, and `doctor` now names the damage if it happens)"
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
            amplifier_memory.save(
                "x", "x", "human", "s", ["x"], home=home, topic="new", topic_purpose="P."
            )
        except amplifier_memory.CapExceeded:
            bounded.append("topics 50")
        else:
            return "Broken", "a 51st topic file was created"
        stale = {
            "ts": (datetime.now(UTC) - timedelta(days=91)).isoformat(),
            "event": "loaded",
            "target": "MEMORY.md",
            "session_id": "s-old",
        }
        (home / "usage.jsonl").write_text(json.dumps(stale) + "\n", encoding="utf-8")
        amplifier_memory.log_usage("loaded", "MEMORY.md", "s-new", home)
        assert len((home / "usage.jsonl").read_text().splitlines()) == 1, "usage.jsonl is unbounded"
        bounded.append("usage 90d")
    # store.v2 §10: "git history grows only with changes a human made or approved." The
    # discriminating pair is a read against a write, on one store.
    with fresh_store() as home:
        start = _git.commit_count(home)
        for i in range(5):
            amplifier_memory.log_usage("loaded", "MEMORY.md", f"s-{i}", home)
            amplifier_memory.record_citation("m-001", f"s-{i}", home)
        reads_only = _git.commit_count(home)
        amplifier_memory.save(
            "a change a human approved",
            "a change a human approved",
            "human",
            "s",
            ["a change a human approved"],
            home=home,
        )
        after_write = _git.commit_count(home)
        assert reads_only == start, f"ten reads grew the history by {reads_only - start} commits"
        assert after_write == start + 1, f"one save made {after_write - start} commits"
        bounded.append("history: reads 0, one save 1")
    return "Kept", (
        f"all Phase 1 growth surfaces bounded ({', '.join(bounded)}); the inbox 30-day expiry is "
        "suggestions.v1 Core 9, checked by conformance/suggestions/run.py"
    )


def probe_core_11() -> Verdict:
    """store.v3 §11: `enabled: false` makes the instance inert — including the daily pass."""
    from amplifier_memory import inbox, llm_config, suggest

    with fresh_store() as home:
        amplifier_memory.save(
            "a live memory", "a live memory", "human", "s", ["a live memory"], home=home
        )
        inbox.append(home, [inbox.Candidate("a pending one", "a pending one please", "deadbeef")])
        assert amplifier_memory.instance_enabled(home) is True, "a fresh instance is live"

        # The daily-pass discriminating pair: this recorded session spends one injected
        # call while enabled and none after the same instance is switched off.
        base = home.parent / "projects"
        session = base / "project" / "sessions" / "11111111-2222-3333-4444-555555555555"
        session.mkdir(parents=True)
        now = datetime.now(UTC)
        (session / "metadata.json").write_text(
            json.dumps({"created": now.isoformat(), "bundle": "fixture"}), encoding="utf-8"
        )
        (session / "transcript.jsonl").write_text(
            "\n".join(
                json.dumps(
                    {
                        "role": "user",
                        "content": turn,
                        "metadata": {"timestamp": now.isoformat()},
                    }
                )
                for turn in ("remember that I prefer two spaces", "please keep it that way")
            )
            + "\n",
            encoding="utf-8",
        )
        enabled_calls: list[str] = []

        def enabled_model(request: str) -> str:
            enabled_calls.append(request)
            return "[]"

        enabled_pass = amplifier_memory.run_suggest(
            home, base_path=base, model_call=enabled_model, help_text=""
        )
        assert enabled_calls and enabled_pass.calls == len(enabled_calls) == 1, (
            enabled_pass.log_line
        )

        (home / llm_config.CONFIG_NAME).write_text(
            llm_config.default_body(enabled=False), encoding="utf-8"
        )
        _git.commit(home, "hand edit: turn this instance off", [llm_config.CONFIG_NAME])
        assert amplifier_memory.instance_enabled(home) is False, "enabled: false was not read"

        before = (home / "MEMORY.md").read_bytes()
        commits = _git.commit_count(home)
        refusals: dict[str, str] = {}
        writes = {
            "save": lambda: amplifier_memory.save(
                "x", "x is a thing", "human", "s", ["x is a thing"], home=home
            ),
            "edit": lambda: amplifier_memory.edit(
                "m-001", "x", "x is a thing", "human", "s", ["x is a thing"], home=home
            ),
            "forget": lambda: amplifier_memory.forget("m-001", home, session_id="s"),
            "record_session": lambda: amplifier_memory.record_session(home, "s-1", "human"),
            "inbox.append": lambda: inbox.append(
                home, [inbox.Candidate("t", "q is a quote", "deadbeef")]
            ),
            "inbox.accept": lambda: inbox.accept("s-001", home, session_id="s"),
            "inbox.decline": lambda: inbox.decline("s-001", home),
        }
        for name, call in writes.items():
            try:
                call()
            except amplifier_memory.InstanceDisabled as exc:
                refusals[name] = str(exc)
            else:
                return "Broken", f"{name} wrote to an instance carrying enabled: false"
        assert (home / "MEMORY.md").read_bytes() == before, "a refusal still changed MEMORY.md"
        assert _git.commit_count(home) == commits, "a refusal still made a commit"
        assert _git.git(["status", "--porcelain"], cwd=home).stdout.strip() == "", "store dirty"
        assert len(set(refusals.values())) == 1, refusals
        one_line = next(iter(refusals.values()))
        assert one_line == f"memory is disabled for this instance ({home}: enabled: false).", (
            one_line
        )

        disabled_calls: list[str] = []

        def disabled_model(request: str) -> str:
            disabled_calls.append(request)
            return "[]"

        before_disabled_log = suggest.log_path(home).read_text(encoding="utf-8").splitlines()
        disabled_pass = amplifier_memory.run_suggest(
            home, base_path=base, model_call=disabled_model, help_text=""
        )
        disabled_log = suggest.log_path(home).read_text(encoding="utf-8").splitlines()
        assert disabled_calls == [] and disabled_pass.calls == 0, disabled_pass.log_line
        assert disabled_pass.status == f"disabled:instance={home} (enabled: false)", (
            disabled_pass.log_line
        )
        assert not disabled_pass.degraded
        assert disabled_log == [*before_disabled_log, disabled_pass.log_line], disabled_log

        # ...and it is a switch, not a door that locks: reading still works, and turning
        # it back on restores every writer.
        assert [m["text"] for m in amplifier_memory.list_memories(home)] == ["a live memory"]
        (home / llm_config.CONFIG_NAME).write_text(llm_config.default_body(), encoding="utf-8")
        _git.commit(home, "hand edit: turn it back on", [llm_config.CONFIG_NAME])
        back = amplifier_memory.save(
            "live again", "live again", "human", "s", ["live again"], home=home
        )
    return "Kept", (
        f"with `enabled: false` in the instance's config.yaml, all {len(refusals)} writers "
        f"({', '.join(refusals)}) refused with one line \u2014 {one_line!r} \u2014 MEMORY.md byte-identical, "
        f"no commit made, tree clean; the daily-pass pair measured enabled calls={len(enabled_calls)} "
        f"and disabled calls={len(disabled_calls)}, with the disabled pass recording "
        f"{disabled_pass.log_line!r} without `degraded:`; reading the instance still works (\u00a711 silences the session "
        f"plane, it does not hide the memories); setting it back to true restored the writer ({back.id}). "
        "The rest of \u00a711 \u2014 nothing injected, no tool offered, no skills advertised, no timer \u2014 is "
        "the session plane's and the CLI's, checked in their own kits (session.v4 \u00a712, cli.v3 \u00a78)"
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
    (11, probe_core_11),
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
