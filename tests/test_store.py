"""In-process conformance for store.v1 (FROZEN 2026-09-06) and cli.v1 Core 8-9.

Every test names the clause it serves. Output the acceptance criteria asks to see
is printed (pytest shows it under `-s`, and the conformance kit prints it always).
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

import amplifier_memory
from amplifier_memory import _git
from amplifier_memory import store as store_mod

REPO_ROOT = Path(__file__).resolve().parents[1]

EXPECTED_API = [
    "init",
    "save",
    "forget",
    "list_memories",
    # The one read path a wrapper uses (AGENTS.md rule 11). Added by this lane: the
    # inject hook and the memory tool each read `MEMORY.md` themselves, strictly, and
    # one hand-typed accented byte (store.v1 Core 9 invites hand edits) raised
    # `UnicodeDecodeError` inside a hook that runs on every provider request.
    "read_memory_text",
    "log_usage",
    "why",
    "store_home",
    # The writer-safety surface, added by this lane: the store's own well-formedness
    # check and its one repair path (store.v1 Core 1/Core 3; the steward's 2026-09-06
    # store had to be repaired by hand because neither existed).
    "verify_store",
    "repair_store",
    "StoreCheck",
    "RepairResult",
    "MalformedLine",
    # The report surface, added by the CLI lane (cli.v1 Core 9: every verb's behaviour is a
    # public library function first). cli.py calls exactly these and prints.
    "status",
    "StatusReport",
    "review",
    "format_why",
    "doctor",
    "DoctorReport",
    "DoctorRow",
    "update_check",
    "update_plan",
    # The install plane, added by the install lane: `update` performs cli.v1 Core 7
    # rather than describing it, and the argv it shells out to is public so the
    # conformance kit can inject a runner instead of touching this machine.
    "run_update",
    "UpdateReport",
    "StepResult",
    "APP_BUNDLE_URI",
    "UPGRADE_CLI_ARGV",
    "BUNDLE_REMOVE_ARGV",
    "BUNDLE_ADD_ARGV",
    "installed_commit",
    "remote_commit",
    "service_status",
    "SERVICE_VERBS",
    "suggest_status",
    "STALE_NOTE",
    "MemoryError",
    "CapExceeded",
    "DuplicateMemory",
    "UnknownId",
    "QuoteNotHuman",
    "StoreMissing",
    # The refusals this lane added. Each one is a state the old writer reported as
    # success (or as a raw git argv dump) in the steward's real session.
    "StoreBusy",
    "WriteNotLanded",
    "StoreMalformed",
    "GitFailed",
]

TURNS = ["never use tabs in YAML files; always two-space indentation, please"]


def _git_log_oneline(home: Path) -> str:
    return _git.git(["log", "--oneline"], cwd=home).stdout.strip()


# --------------------------------------------------------------- acceptance 1 and 2


def test_public_api_is_exactly_the_contracted_surface() -> None:
    assert amplifier_memory.__all__ == EXPECTED_API
    for name in EXPECTED_API:
        assert hasattr(amplifier_memory, name), f"{name} is exported but missing"
    print("__all__ =", amplifier_memory.__all__)


def test_import_pulls_in_neither_click_nor_amplifier(tmp_path: Path) -> None:
    """cli.v1 Core 9: every behaviour is reachable by importing the library alone."""
    code = (
        "import amplifier_memory, sys; "
        "print([m for m in sys.modules "
        "if m.startswith(('click','amplifier_core','amplifier_foundation'))])"
    )
    proc = subprocess.run(
        [sys.executable, "-c", code], capture_output=True, text=True, check=True, cwd=tmp_path
    )
    print("leaked modules:", proc.stdout.strip())
    assert proc.stdout.strip() == "[]"


# --------------------------------------------------------------- acceptance 3 (Core 2, cli.v1 Core 8)


def test_init_creates_the_layout_once_and_is_idempotent(memory_home: Path) -> None:
    first = amplifier_memory.init()
    assert first.existed is False
    assert sorted(first.created) == [
        "MEMORY.md",
        "declined.md",
        "inbox.md",
        "topics/",
        "topics/.gitkeep",
        "usage.jsonl",
    ]

    on_disk = sorted(p.name for p in memory_home.iterdir() if p.name != ".git")
    assert on_disk == ["MEMORY.md", "declined.md", "inbox.md", "topics", "usage.jsonl"]
    assert (memory_home / "topics").is_dir()

    # store.v1 Core 9: the store repository carries NO identity of its own, so a human's
    # own `git commit` in the store is attributed to the human. The writer names itself
    # per commit instead (see test_the_store_repo_holds_no_identity_and_the_writer_names_itself).
    assert _git.git(["config", "--local", "--get", "user.name"], cwd=memory_home, check=False).returncode != 0
    assert _git.git(["config", "--local", "--get", "user.email"], cwd=memory_home, check=False).returncode != 0

    after_first = _git_log_oneline(memory_home)
    second = amplifier_memory.init()
    after_second = _git_log_oneline(memory_home)

    print("git log --oneline after first init: ", after_first)
    print("git log --oneline after second init:", after_second)
    print("second init .existed =", second.existed)

    assert second.existed is True
    assert after_first == after_second
    assert _git.commit_count(memory_home) == 1
    assert len(after_second.splitlines()) == 1


# --------------------------------------------------------------- acceptance 4 (Core 3, Core 4)


def _fill_memory(home: Path, lines: int) -> None:
    """A legitimate hand edit (Core 9), committed once, to reach the cap quickly."""
    body = ["## conventions", ""]  # a heading and a blank line: both count (Core 3)
    body += [f"- [m-{i:03d}] hand-written memory number {i}" for i in range(1, lines - 1)]
    assert len(body) == lines
    (home / "MEMORY.md").write_text("\n".join(body) + "\n", encoding="utf-8")
    _git.commit(home, "hand edit: seed conventions", ["MEMORY.md"])


def test_memory_cap_discriminating_pair(store: Path) -> None:
    _fill_memory(store, 199)
    assert len((store / "MEMORY.md").read_text().splitlines()) == 199

    ok = amplifier_memory.save(
        "never use tabs in YAML files", "never use tabs in YAML", "assistant", "s-1", TURNS
    )
    line_count = len((store / "MEMORY.md").read_text().splitlines())
    print(f"200th line saved as {ok.id}; MEMORY.md now {line_count} lines")
    assert line_count == 200

    with pytest.raises(amplifier_memory.CapExceeded) as excinfo:
        amplifier_memory.save(
            "always two-space indentation", "always two-space indentation", "assistant", "s-1", TURNS
        )
    message = str(excinfo.value)
    print("201st refused:", message)
    assert "200" in message
    assert "topic file" in message
    assert "/forget" in message
    assert len((store / "MEMORY.md").read_text().splitlines()) == 200


def test_headings_and_blank_lines_count_toward_the_cap(store: Path) -> None:
    """Core 3: 'comments and blank lines count'."""
    _fill_memory(store, 200)  # 198 memories + one heading + one blank line
    memories = amplifier_memory.list_memories()
    print(f"MEMORY.md lines=200, parsed memories={len(memories)} (heading + blank line counted)")
    assert len(memories) == 198
    with pytest.raises(amplifier_memory.CapExceeded):
        amplifier_memory.save("one more", "one more", "assistant", "s-1", ["one more"])


# --------------------------------------------------------------- acceptance 5 (Core 5)


def test_topic_line_cap_and_file_cap(store: Path) -> None:
    topic = store / "topics" / "yaml-style.md"
    body = ["YAML and JSON style conventions."]
    body += [f"- [m-{i:03d}] topic line {i}" for i in range(1, 150)]
    assert len(body) == 150
    topic.write_text("\n".join(body) + "\n", encoding="utf-8")
    _git.commit(store, "hand edit: seed topic", ["topics/yaml-style.md"])

    with pytest.raises(amplifier_memory.CapExceeded) as line_exc:
        amplifier_memory.save(
            "prefer block scalars", "prefer block scalars", "human", "s-1",
            ["prefer block scalars"], topic="yaml-style",
        )
    print("151st topic line refused:", line_exc.value)
    assert line_exc.value.cap == 150

    for i in range(1, 50):
        (store / "topics" / f"t{i:02d}.md").write_text(f"Topic {i}.\n", encoding="utf-8")
    assert len(store_mod.topic_files(store)) == 50

    with pytest.raises(amplifier_memory.CapExceeded) as file_exc:
        amplifier_memory.save(
            "one more note", "one more note", "human", "s-1", ["one more note"],
            topic="overflow", topic_purpose="Notes that will not fit.",
        )
    print("51st topic file refused:", file_exc.value)
    assert file_exc.value.cap == 50
    assert not (store / "topics" / "overflow.md").exists()


def test_a_new_topic_file_begins_with_a_purpose(store: Path) -> None:
    result = amplifier_memory.save(
        "always two-space indentation", "always two-space indentation", "human", "s-1",
        ["always two-space indentation"], topic="yaml-style",
        topic_purpose="YAML and JSON style conventions.",
    )
    text = (store / "topics" / "yaml-style.md").read_text()
    print("new topic file:\n" + text.rstrip())
    assert text.splitlines()[0] == "YAML and JSON style conventions."
    assert result.target == "topics/yaml-style.md"


# --------------------------------------------------------------- acceptance 6 (Core 6)


def test_every_writer_commit_carries_the_five_provenance_fields(store: Path) -> None:
    result = amplifier_memory.save(
        "never use tabs in YAML files",
        "never use tabs in YAML files; always two-space indentation",
        "assistant",
        "sess-2026-09-06-abc",
        TURNS,
    )
    assert result.id == "m-001"
    message = _git.git(["log", "-1", "--format=%B"], cwd=store).stdout.strip()
    print("--- real commit message ---\n" + message + "\n---------------------------")

    assert "[m-001]" in message
    assert "never use tabs in YAML files" in message
    assert 'quote: "never use tabs in YAML files; always two-space indentation"' in message
    assert "session: sess-2026-09-06-abc" in message
    assert "writer: assistant" in message

    records = amplifier_memory.why("m-001")
    print("why(m-001) ->", json.dumps(records[0], indent=2, sort_keys=True))
    assert records[0]["id"] == "m-001"
    assert records[0]["text"] == "never use tabs in YAML files"
    assert records[0]["quote"] == "never use tabs in YAML files; always two-space indentation"
    assert records[0]["session"] == "sess-2026-09-06-abc"
    assert records[0]["writer"] == "assistant"

    grep = _git.git(["log", "--grep=\\[m-001\\]", "--format=%H"], cwd=store).stdout.split()
    assert records[0]["commit"] in grep


def test_why_of_an_unknown_id_raises(store: Path) -> None:
    with pytest.raises(amplifier_memory.UnknownId):
        amplifier_memory.why("m-999")


def test_every_mutation_is_exactly_one_commit(store: Path) -> None:
    """Core 1: every mutation is one commit."""
    before = _git.commit_count(store)
    amplifier_memory.save("never use tabs", "never use tabs", "human", "s-1", ["never use tabs"])
    after_save = _git.commit_count(store)
    amplifier_memory.forget("m-001", session_id="s-1")
    after_forget = _git.commit_count(store)
    print(f"commits: init={before} save={after_save} forget={after_forget}")
    assert after_save == before + 1
    assert after_forget == after_save + 1
    assert _git.git(["status", "--porcelain"], cwd=store).stdout.strip() == ""


# --------------------------------------------------------------- acceptance 7 (conformance 3-4)


def test_exact_duplicate_is_refused(store: Path) -> None:
    amplifier_memory.save("never use tabs", "never use tabs", "human", "s-1", ["never use tabs"])
    with pytest.raises(amplifier_memory.DuplicateMemory) as excinfo:
        amplifier_memory.save("never use tabs", "never use tabs", "human", "s-1", ["never use tabs"])
    print("duplicate refused:", excinfo.value)
    assert len(amplifier_memory.list_memories()) == 1


def test_forget_removes_the_line_and_the_id_is_never_reused(store: Path) -> None:
    first = amplifier_memory.save("never use tabs", "never use tabs", "human", "s-1", ["never use tabs"])
    second = amplifier_memory.save("always rebase", "always rebase", "human", "s-1", ["always rebase"])
    assert (first.id, second.id) == ("m-001", "m-002")

    gone = amplifier_memory.forget("m-002", session_id="s-1")
    remaining = [m["id"] for m in amplifier_memory.list_memories()]
    third = amplifier_memory.save("prefer uv", "prefer uv", "human", "s-1", ["prefer uv"])
    print(f"forgot {gone.id}; remaining={remaining}; next id issued={third.id}")

    assert remaining == ["m-001"]
    assert third.id == "m-003", "an id was reused after a forget"
    assert int(third.id.split("-")[1]) > int(second.id.split("-")[1])

    forget_record = amplifier_memory.why("m-002")[0]
    assert forget_record["action"] == "forget"


def test_forget_of_an_unknown_id_raises(store: Path) -> None:
    with pytest.raises(amplifier_memory.UnknownId):
        amplifier_memory.forget("m-404")


def test_the_high_water_mark_lives_in_git_not_in_a_counter_file(store: Path) -> None:
    """Core 2: a file not in the layout is not memory — so no counter file exists."""
    amplifier_memory.save("never use tabs", "never use tabs", "human", "s-1", ["never use tabs"])
    amplifier_memory.forget("m-001", session_id="s-1")
    assert (store / "MEMORY.md").read_text() == "", "forgetting the only memory left content behind"

    nxt = amplifier_memory.save("always rebase", "always rebase", "human", "s-1", ["always rebase"])
    listing = sorted(p.name for p in store.iterdir() if p.name != ".git")
    print(f"store contents={listing}; next id after an empty MEMORY.md={nxt.id}")
    assert nxt.id == "m-002"
    assert listing == ["MEMORY.md", "declined.md", "inbox.md", "topics", "usage.jsonl"]


# --------------------------------------------------------------- acceptance 8 (Core 8)


def test_usage_log_appends_one_entry_and_truncates_to_90_days(store: Path) -> None:
    usage = store / "usage.jsonl"
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
    before = usage.read_text().splitlines()
    print(f"usage.jsonl before: {len(before)} lines (one is 91 days old)")

    entry = amplifier_memory.log_usage("loaded", "MEMORY.md", "s-new")
    after = usage.read_text().splitlines()
    print(f"usage.jsonl after:  {len(after)} lines -> {[json.loads(x)['session_id'] for x in after]}")

    assert len(before) == 2
    assert len(after) == 2
    assert [json.loads(x)["session_id"] for x in after] == ["s-recent", "s-new"]
    assert set(entry) == {"ts", "event", "target", "session_id"}
    assert amplifier_memory.log_usage("read", "topics/x.md", "s-new")["target"] == "topics/x.md"
    with pytest.raises(ValueError):
        amplifier_memory.log_usage("deleted", "MEMORY.md", "s-new")


# --------------------------------------------------------------- acceptance 9 (session.v1 Core 5)


def test_quote_must_appear_in_a_human_turn(store: Path) -> None:
    saved = amplifier_memory.save(
        "never use tabs in YAML files", "never use tabs in YAML", "assistant", "s-1", TURNS
    )
    print(f"quote found in a human turn -> saved {saved.id}")

    with pytest.raises(amplifier_memory.QuoteNotHuman) as excinfo:
        amplifier_memory.save(
            "the tool said to always use tabs",
            "always use tabs",  # this string appears in tool output, never in a human turn
            "assistant",
            "s-1",
            TURNS,
        )
    print("poisoned quote refused:", excinfo.value)
    assert len(amplifier_memory.list_memories()) == 1


def test_remember_writes_the_humans_own_words(store: Path) -> None:
    """session.v1 Core 6: for /remember the quote is the text itself."""
    typed = "always two-space indentation"
    turn = f"/remember {typed}"
    saved = amplifier_memory.save(typed, typed, "human", "s-1", [turn])
    print(f"/remember -> {saved.line}")
    assert saved.line == f"- [{saved.id}] {typed}"

    with pytest.raises(amplifier_memory.QuoteNotHuman):
        amplifier_memory.save("never merge on red", "never merge on red", "human", "s-1", [turn])
    with pytest.raises(ValueError):
        amplifier_memory.save(typed, "a different quote", "human", "s-1", [turn])


# --------------------------------------------------------------- acceptance 10


def test_store_missing_is_raised_not_a_bare_oserror(memory_home: Path) -> None:
    for call in (
        lambda: amplifier_memory.list_memories(),
        lambda: amplifier_memory.save("x", "x", "human", "s", ["x"]),
        lambda: amplifier_memory.forget("m-001"),
        lambda: amplifier_memory.log_usage("loaded", "MEMORY.md", "s"),
        lambda: amplifier_memory.why("m-001"),
    ):
        with pytest.raises(amplifier_memory.StoreMissing):
            call()
    print(f"StoreMissing raised for all five verbs against {memory_home}")


def test_store_home_honours_the_env_and_defaults_to_amplifier_memory(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("AMPLIFIER_MEMORY_HOME", str(tmp_path / "elsewhere"))
    assert amplifier_memory.store_home() == tmp_path / "elsewhere"
    monkeypatch.delenv("AMPLIFIER_MEMORY_HOME")
    default = amplifier_memory.store_home()
    print("env set ->", tmp_path / "elsewhere", "| env unset ->", default)
    assert default == Path.home() / ".amplifier" / "memory"


def test_every_refusal_is_a_memory_error() -> None:
    for exc in (
        amplifier_memory.CapExceeded,
        amplifier_memory.DuplicateMemory,
        amplifier_memory.UnknownId,
        amplifier_memory.QuoteNotHuman,
        amplifier_memory.StoreMissing,
    ):
        assert issubclass(exc, amplifier_memory.MemoryError)


# --------------------------------------------------------------- Core 9: two writers, one path


def test_a_hand_edit_is_legitimate_and_the_writer_reads_it_back(store: Path) -> None:
    (store / "MEMORY.md").write_text("- [m-007] hand-written by the human\n", encoding="utf-8")
    _git.commit(store, "hand edit: add a memory with an editor", ["MEMORY.md"])

    seen = amplifier_memory.list_memories()
    nxt = amplifier_memory.save("never use tabs", "never use tabs", "human", "s-1", ["never use tabs"])
    print(f"hand edit read back as {seen[0]['id']}; writer then issued {nxt.id}")
    assert [m["id"] for m in seen] == ["m-007"]
    assert nxt.id == "m-008", "the writer reused an id a human had already used"


# --------------------------------------------------------------- AGENTS.md rule 5


GIT_ARGV_UNDER_TEST = {
    "init": ["-b <branch-name>"],
    "config": ["--get"],
    "add": ["<pathspec>"],
    # `-F <file>` with `-` for stdin: a commit message is never an argv element, because a
    # human-supplied text past the kernel's argv limit raised OSError *after* `git add`.
    "commit": ["-F <file>"],
    "log": ["--grep=<pattern>", "--format=<format>"],
    "rev-list": ["--count"],
    "rev-parse": ["--is-inside-work-tree"],
    "status": ["--porcelain"],
    # Added by this lane: the writer re-reads the committed tree after every commit.
    "show": ["<object>"],
    # Added by this lane: the index half of a rollback after a failed write.
    "reset": ["-q", "<pathspec>"],
}


@pytest.mark.parametrize("subcommand", sorted(GIT_ARGV_UNDER_TEST))
def test_shelled_argv_is_verified_against_git_help(subcommand: str) -> None:
    """AGENTS.md rule 5: every shelled argv is verified against that CLI's own help."""
    proc = subprocess.run(
        ["git", subcommand, "--help"],
        capture_output=True,
        text=True,
        check=True,
        env={**os.environ, "MANPAGER": "cat", "GIT_PAGER": "cat"},
    )
    help_text = proc.stdout
    for flag in GIT_ARGV_UNDER_TEST[subcommand]:
        assert flag in help_text, f"git {subcommand} help does not document {flag}"
    print(f"git {subcommand} --help documents {GIT_ARGV_UNDER_TEST[subcommand]}")


# --------------------------------------------------------------- the conformance kit and the ledger


def test_conformance_kit_runs_green_and_covers_every_core_clause() -> None:
    proc = subprocess.run(
        [sys.executable, str(REPO_ROOT / "conformance" / "store" / "run.py")],
        capture_output=True,
        text=True,
        check=False,
        cwd=REPO_ROOT,
    )
    print(proc.stdout)
    assert proc.returncode == 0, proc.stderr
    lines = [line for line in proc.stdout.splitlines() if line.startswith("Core ")]
    assert len(lines) == 10
    for index, line in enumerate(lines, start=1):
        assert line.startswith(f"Core {index} — ")
        verdict = line.split(" — ")[1]
        assert verdict in {"Kept", "Not yet", "Broken", "Can't check"}


def test_ledger_rows_marked_conforms_name_a_probe_that_passes() -> None:
    """Acceptance 12: a row is CONFORMS only where its named probe passes.

    A ref is `<kit path>::<probe>`, and BOTH halves matter: every kit numbers its probes
    `probe_core_N`, so matching on the function name alone runs a cli.v1 row against the
    store kit's probe of the same number. That is how AMM-026 could read CONFORMS while
    `conformance/cli/run.py::probe_core_7` had never been called.
    """
    from conformance.cli import run as cli_kit
    from conformance.store import run as store_kit

    kits = {
        "conformance/store/run.py": store_kit,
        "conformance/cli/run.py": cli_kit,
    }

    rows_text = (REPO_ROOT / "ledger" / "rows.yaml").read_text(encoding="utf-8")
    conforming: list[tuple[str, str]] = []
    current_id = ""
    disposition = ""
    for line in rows_text.splitlines():
        if line.startswith("- id: "):
            current_id, disposition = line.split("- id: ")[1].strip(), ""
        elif line.strip().startswith("disposition:"):
            disposition = line.split("disposition:")[1].strip()
        elif line.strip().startswith("ref:") and disposition == "CONFORMS":
            conforming.append((current_id, line.split("ref:")[1].strip()))

    results: dict[str, tuple[str, str]] = {}
    for path, kit in kits.items():
        for _, fn in kit.PROBES:
            results[f"{path}::{fn.__name__}"] = fn()
    for row_id, ref in conforming:
        if "::" not in ref or ref.split("::", 1)[0] not in kits:
            continue  # a pytest-side probe; checked by its own test
        assert ref in results, f"{row_id} names {ref}, which no kit defines"
        verdict = results[ref][0]
        assert verdict == "Kept", f"{row_id} claims CONFORMS but {ref} says {verdict}"
    print("CONFORMS rows checked against their probes:", [row for row, _ in conforming])


# --------------------------------------------------------------- Core 1: one writer at a time


def test_every_mutating_path_runs_under_the_lock() -> None:
    """store.v1 Core 1/Core 9 — grep the writer, not the docstring.

    A save, a forget, a usage log and an init that do not take the lock are exactly the
    four ways the steward's store was corrupted; this asserts the source, so a future
    edit that drops one is caught here and not in someone's real MEMORY.md.
    """
    source = (REPO_ROOT / "src" / "amplifier_memory" / "store.py").read_text(encoding="utf-8")
    print("\n".join(
        f"{n}: {line.strip()}"
        for n, line in enumerate(source.splitlines(), start=1)
        if "flock" in line or "_exclusive(" in line
    ))
    assert "fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)" in source, "no exclusive flock"
    for verb in ("def init", "def save", "def forget", "def log_usage", "def repair_store"):
        body = source.split(verb, 1)[1].split("\ndef ", 1)[0]
        assert "with _exclusive(" in body, f"{verb} does not take the store lock"


def test_a_git_failure_is_one_sentence_and_never_an_argv(
    store: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The steward saw `Command '['git', '-c', 'user.name=amplifier-memory', …]'` as an answer."""

    def broken_commit(*args: object, **kwargs: object) -> str:
        raise subprocess.CalledProcessError(
            returncode=128,
            cmd=["git", "-c", "user.name=amplifier-memory", "commit", "-m", "…"],
            output="",
            stderr="fatal: unable to write new index file\nhint: check the disk\n",
        )

    monkeypatch.setattr(_git, "commit", broken_commit)
    with pytest.raises(amplifier_memory.GitFailed) as caught:
        amplifier_memory.save("never use tabs", "never use tabs", "human", "s-1", ["never use tabs"])

    message = str(caught.value)
    print("raised:", message)
    assert message.count("\n") == 0, "a git failure is one sentence"
    assert "['git'" not in message and "Command " not in message, "the argv leaked"
    assert "fatal: unable to write new index file" in message, "git's own reason is missing"
    assert "commit failed" in message


def test_nothing_to_commit_is_reported_as_already_applied_not_as_a_failure(
    store: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A concurrent sweep that already carried this change is not a failed write.

    Reproduced with git's real refusal, taken from the installed git: the writer stages
    nothing new, git exits nonzero saying so, and the call still tells the truth.
    """
    amplifier_memory.save("keep me", "keep me", "human", "s-1", ["keep me"])
    real_commit = _git.commit

    def swept(home, message, paths, **kwargs):
        # Another writer sweeps this very change into its own commit first (the pair of
        # forgets in the steward's session landed in one commit, 8c75df6). This writer's
        # own `git commit` then finds nothing staged — git's real refusal, not a mock.
        real_commit(home, "concurrent writer: swept the same change", list(paths))
        return real_commit(home, message, paths, **kwargs)

    monkeypatch.setattr(_git, "commit", swept)
    result = amplifier_memory.forget("m-001", store, session_id="s-1")
    print(f"forget m-001 -> commit {result.commit[:12]} note={result.note!r}")
    assert result.note == store_mod.ALREADY_APPLIED
    assert "['git'" not in str(result.note)


def test_git_first_error_line_prefers_stderr_then_stdout() -> None:
    exc = subprocess.CalledProcessError(1, ["git", "commit"], output="nothing to commit\n", stderr="")
    print("stdout-only ->", _git.first_error_line(exc), "| nothing_to_commit:", _git.is_nothing_to_commit(exc))
    assert _git.first_error_line(exc) == "nothing to commit"
    assert _git.is_nothing_to_commit(exc)
    exc2 = subprocess.CalledProcessError(1, ["git", "commit"], output="x", stderr="fatal: boom\n")
    assert _git.first_error_line(exc2) == "fatal: boom"
    assert not _git.is_nothing_to_commit(exc2)


def test_a_corrupt_memory_file_is_refused_before_the_write_with_the_remedy(store: Path) -> None:
    """A writer that appends to a corrupt file buries the damage. This one refuses first."""
    path = store / "MEMORY.md"
    path.write_text("a headless fragment with no id\n", encoding="utf-8")
    _git.commit(store, "hand edit: corrupt", ["MEMORY.md"])
    before = path.read_text(encoding="utf-8")

    with pytest.raises(amplifier_memory.StoreMalformed) as caught:
        amplifier_memory.save("never use tabs", "never use tabs", "human", "s-1", ["never use tabs"])
    print("raised:", caught.value)
    assert "doctor --repair" in str(caught.value)
    assert "line 1" in str(caught.value)
    assert path.read_text(encoding="utf-8") == before, "the refused write touched the file"


def test_wellformed_accepts_exactly_what_core_3_describes() -> None:
    good = ["- [m-017] never use tabs", "## conventions", "", "   ", "# a comment"]
    bad = [" work, concrete time estimates, lists capped at 5", "m-001 no dash", "- [x-1] wrong id"]
    print("well-formed:", [(line, store_mod.wellformed(line)) for line in good])
    print("malformed:  ", [(line, store_mod.wellformed(line)) for line in bad])
    assert all(store_mod.wellformed(line) for line in good)
    assert not any(store_mod.wellformed(line) for line in bad)


# --------------------------------------------------------------- the one read for wrappers


def test_read_memory_text_hands_a_wrapper_the_bad_byte_as_u_fffd(store: Path) -> None:
    """AGENTS.md rule 11: the hook and the tool read through here, and it never raises.

    The strict read they used to do is run first, in the same test, so the two are
    measured against the same file rather than against a claim about it.
    """
    memory = store / "MEMORY.md"
    memory.write_bytes(b"- [m-001] Jos\xe9 prefers short reviews\n")

    with pytest.raises(UnicodeDecodeError) as strict:
        memory.read_text(encoding="utf-8")
    text = amplifier_memory.read_memory_text(store)

    print("strict read           ->", type(strict.value).__name__, strict.value)
    print("read_memory_text      ->", repr(text))
    print("verify_store still reports the byte ->", amplifier_memory.verify_store(store).render())

    assert text == "- [m-001] Jos\ufffd prefers short reviews\n"
    assert "\ufffd" in text
    # Tolerant is not silent: the byte is still reported where a remedy is named.
    assert amplifier_memory.verify_store(store).decode_error_offset == 13


def test_read_memory_text_still_refuses_a_store_that_is_not_there(memory_home: Path) -> None:
    """"No memories" and "no store" are different facts; session.v1 §10 needs the second."""
    with pytest.raises(amplifier_memory.StoreMissing) as caught:
        amplifier_memory.read_memory_text(memory_home)
    print("missing store ->", caught.value)
    assert "amplifier-memory init" in str(caught.value)
