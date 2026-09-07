"""In-process conformance for store.v2 (FROZEN 2026-09-06) and cli.v2 Core 8-9.

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
    # store.v2 §6 / cli.v2 §3: a refinement keeps the id and records what it replaced.
    # The tool module calls this next wave; the CLI has no `edit` verb (cli.v2 backlog).
    "edit",
    "forget",
    "list_memories",
    # The one read path a wrapper uses (AGENTS.md rule 11). Added by this lane: the
    # inject hook and the memory tool each read `MEMORY.md` themselves, strictly, and
    # one hand-typed accented byte (store.v2 Core 9 invites hand edits) raised
    # `UnicodeDecodeError` inside a hook that runs on every provider request.
    "read_memory_text",
    "log_usage",
    # store.v2 §8: the `cited` event `status`'s citation rate (cli.v2 §2) is derived from.
    "record_citation",
    "why",
    "store_home",
    # store.v3 §1/§2/§11, added by this lane: a store is an INSTANCE. The resolution
    # order and the migration are one function each; `instance_enabled` is §11's
    # predicate, and the session record is session.v4 §13's plumbing. The modules, the
    # CLI and the job all read these rather than each resolving a path of their own.
    "default_home",
    "legacy_home",
    "legacy_store_present",
    "instance_enabled",
    "record_session",
    "session_origins",
    "origin_from_env",
    # The writer-safety surface, added by this lane: the store's own well-formedness
    # check and its one repair path (store.v2 Core 1/Core 3; the steward's 2026-09-06
    # store had to be repaired by hand because neither existed).
    "verify_store",
    "repair_store",
    "StoreCheck",
    "RepairResult",
    "MalformedLine",
    # The report surface, added by the CLI lane (cli.v2 Core 9: every verb's behaviour is a
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
    # The install plane, added by the install lane: `update` performs cli.v2 Core 7
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
    # Phase 2 (suggestions.v1), added by lane P. The inbox, the daily pass and the timer
    # are library functions first: `/memory review` inside a session and the tool module
    # call exactly these, never the CLI (cli.v2 Core 9, AGENTS.md rule 11).
    "SERVICE_UNIT",
    "TIMER_UNIT",
    # cli.v3 §6/§8, added by lane W: a timer belongs to an INSTANCE, so its unit name is
    # derived from that instance's path and `status` can list every one on the device;
    # and `init` is the whole verb the clause describes (the store primitive plus the
    # move offer, the one seeding question and this instance's timer) rather than only
    # `store.init`. `split_home` is Core 1's `--home`, parsed with no `click` in sight.
    "instance_tag",
    "service_unit",
    "timer_unit",
    "timer_present",
    "installed_timers",
    "InstalledTimer",
    "build_instance",
    "default_instance",
    "InstanceReport",
    "SEED_QUESTION",
    "SEED_DEFAULT",
    "HOME_FLAG",
    "split_home",
    "TIMER_ROW",
    "SUBSTRATE_ROW",
    "timer_row",
    "substrate_row",
    "service_install",
    "service_uninstall",
    "service_state",
    "ServiceResult",
    "ServiceStatus",
    "suggest_status",
    "INBOX",
    "DECLINED",
    "EXPIRY_DAYS",
    "Suggestion",
    "Candidate",
    "UnknownSuggestion",
    "pending",
    "append",
    "accept",
    "decline",
    "skip",
    "expire",
    "is_declined",
    "declined_entries",
    "declined_line",
    "declined_quotes",
    "declined_texts",
    "render_pending",
    # session.v3 §6 as amended 2026-09-07: `list` and `review` come back as one page
    # of markdown, and the LIBRARY renders it — the tool module and the CLI both call
    # these and print. `page_bounds` is §6's paging rule, in one place (AGENTS.md
    # rule 11), so `list 3` and `review 3` can never mean different thirds.
    "render_review_page",
    "render_list_page",
    # cli.v2 §2 / suggestions.v1 Core 9: when the daily pass last ran, read off
    # `suggest.log` through the same two functions `doctor` uses.
    "last_suggest_run",
    "page_bounds",
    "Page",
    "display_path",
    "review_one",
    "review_action",
    "reviewing_session_id",
    "is_interactive",
    "REVIEW_KEYS",
    "REVIEW_PROMPT",
    "run_suggest",
    "SuggestReport",
    "MalformedReply",
    "select_sessions",
    "last_log_line",
    "parse_log_line",
    "log_path",
    "PROMPT",
    "PROMPT_PREFIX",
    "RUN_ARGV",
    "STALE_NOTE",
    "MemoryError",
    "CapExceeded",
    "DuplicateMemory",
    "UnknownId",
    "QuoteNotHuman",
    "StoreMissing",
    # store.v3 §11: an instance carrying `enabled: false` refuses every write.
    "InstanceDisabled",
    # The refusals this lane added. Each one is a state the old writer reported as
    # success (or as a raw git argv dump) in the steward's real session.
    "StoreBusy",
    "WriteNotLanded",
    "StoreMalformed",
    "GitFailed",
    "PageOutOfRange",
]

TURNS = ["never use tabs in YAML files; always two-space indentation, please"]

#: store.v2 §2: "`.lock` and `.gitignore` inside the store are plumbing, not memory."
#: A listing of the store's *memory* filters both, exactly as the clause reads.
_PLUMBING = {".git", ".gitignore"}


def _git_log_oneline(home: Path) -> str:
    return _git.git(["log", "--oneline"], cwd=home).stdout.strip()


# --------------------------------------------------------------- acceptance 1 and 2


def test_public_api_is_exactly_the_contracted_surface() -> None:
    assert amplifier_memory.__all__ == EXPECTED_API
    for name in EXPECTED_API:
        assert hasattr(amplifier_memory, name), f"{name} is exported but missing"
    print("__all__ =", amplifier_memory.__all__)


def test_import_pulls_in_neither_click_nor_amplifier(tmp_path: Path) -> None:
    """cli.v2 Core 9: every behaviour is reachable by importing the library alone."""
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


# --------------------------------------------------------------- acceptance 3 (Core 2, cli.v2 Core 8)


def test_init_creates_the_layout_once_and_is_idempotent(memory_home: Path) -> None:
    first = amplifier_memory.init()
    assert first.existed is False
    assert sorted(first.created) == [
        ".gitignore",
        "MEMORY.md",
        "config.yaml",
        "declined.md",
        "inbox.md",
        "sessions.jsonl",
        "topics/",
        "topics/.gitkeep",
        "usage.jsonl",
    ]

    on_disk = sorted(p.name for p in memory_home.iterdir() if p.name not in _PLUMBING)
    assert on_disk == [
        "MEMORY.md",
        "config.yaml",
        "declined.md",
        "inbox.md",
        "sessions.jsonl",
        "topics",
        "usage.jsonl",
    ]
    assert (memory_home / "topics").is_dir()

    # store.v2 §1/§2: usage.jsonl is memory and is on disk, but git never tracks it, so
    # a session that only reads leaves no commit. `.gitignore` is the plumbing that says so.
    ignored = (memory_home / ".gitignore").read_text(encoding="utf-8")
    tracked = _git.git(["ls-files"], cwd=memory_home).stdout.split()
    print(f"tracked after init: {tracked}")
    print(f".gitignore: {[line for line in ignored.splitlines() if not line.startswith('#')]}")
    assert "usage.jsonl" in ignored.splitlines(), ignored
    assert "usage.jsonl" not in tracked, tracked
    # store.v3 §2: "`.lock`, `.gitignore`, `config.yaml` and `sessions.jsonl` inside the
    # store are plumbing, not memory." `config.yaml` is tracked — it is written once by
    # `init` and edited by a human, and both are changes worth a commit. `sessions.jsonl`
    # is not: the session hook appends to it at every session start (session.v4 §13), and
    # a tracked one would put a commit on the front of every session ever started.
    assert "sessions.jsonl" in ignored.splitlines(), ignored
    assert "sessions.jsonl" not in tracked, tracked
    assert sorted(tracked) == [
        ".gitignore",
        "MEMORY.md",
        "config.yaml",
        "declined.md",
        "inbox.md",
        "topics/.gitkeep",
    ]

    # store.v2 Core 9: the store repository carries NO identity of its own, so a human's
    # own `git commit` in the store is attributed to the human. The writer names itself
    # per commit instead (see test_the_store_repo_holds_no_identity_and_the_writer_names_itself).
    assert (
        _git.git(
            ["config", "--local", "--get", "user.name"], cwd=memory_home, check=False
        ).returncode
        != 0
    )
    assert (
        _git.git(
            ["config", "--local", "--get", "user.email"], cwd=memory_home, check=False
        ).returncode
        != 0
    )

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
            "always two-space indentation",
            "always two-space indentation",
            "assistant",
            "s-1",
            TURNS,
        )
    message = str(excinfo.value)
    print("201st refused:", message)
    assert "200" in message
    assert "topic file" in message
    assert "/memory forget" in message  # store.v2, amended 2026-09-07
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
            "prefer block scalars",
            "prefer block scalars",
            "human",
            "s-1",
            ["prefer block scalars"],
            topic="yaml-style",
        )
    print("151st topic line refused:", line_exc.value)
    assert line_exc.value.cap == 150

    for i in range(1, 50):
        (store / "topics" / f"t{i:02d}.md").write_text(f"Topic {i}.\n", encoding="utf-8")
    assert len(store_mod.topic_files(store)) == 50

    with pytest.raises(amplifier_memory.CapExceeded) as file_exc:
        amplifier_memory.save(
            "one more note",
            "one more note",
            "human",
            "s-1",
            ["one more note"],
            topic="overflow",
            topic_purpose="Notes that will not fit.",
        )
    print("51st topic file refused:", file_exc.value)
    assert file_exc.value.cap == 50
    assert not (store / "topics" / "overflow.md").exists()


def test_a_new_topic_file_begins_with_a_purpose(store: Path) -> None:
    result = amplifier_memory.save(
        "always two-space indentation",
        "always two-space indentation",
        "human",
        "s-1",
        ["always two-space indentation"],
        topic="yaml-style",
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
        amplifier_memory.save(
            "never use tabs", "never use tabs", "human", "s-1", ["never use tabs"]
        )
    print("duplicate refused:", excinfo.value)
    assert len(amplifier_memory.list_memories()) == 1


def test_forget_removes_the_line_and_the_id_is_never_reused(store: Path) -> None:
    first = amplifier_memory.save(
        "never use tabs", "never use tabs", "human", "s-1", ["never use tabs"]
    )
    second = amplifier_memory.save(
        "always rebase", "always rebase", "human", "s-1", ["always rebase"]
    )
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
    listing = sorted(p.name for p in store.iterdir() if p.name not in _PLUMBING)
    print(f"store contents={listing}; next id after an empty MEMORY.md={nxt.id}")
    assert nxt.id == "m-002"
    assert listing == [
        "MEMORY.md",
        "config.yaml",
        "declined.md",
        "inbox.md",
        "sessions.jsonl",
        "topics",
        "usage.jsonl",
    ]


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
    print(
        f"usage.jsonl after:  {len(after)} lines -> {[json.loads(x)['session_id'] for x in after]}"
    )

    assert len(before) == 2
    assert len(after) == 2
    assert [json.loads(x)["session_id"] for x in after] == ["s-recent", "s-new"]
    assert set(entry) == {"ts", "event", "target", "session_id"}
    assert amplifier_memory.log_usage("read", "topics/x.md", "s-new")["target"] == "topics/x.md"
    with pytest.raises(ValueError):
        amplifier_memory.log_usage("deleted", "MEMORY.md", "s-new")


# --------------------------------------------------------------- acceptance 9 (session.v2 Core 5)


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
    """session.v2 Core 6: for /remember the quote is the text itself."""
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
    nxt = amplifier_memory.save(
        "never use tabs", "never use tabs", "human", "s-1", ["never use tabs"]
    )
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
    # Added for store.v2 §1: is usage.jsonl still tracked, and stop tracking it without
    # deleting one line of it.
    "ls-files": ["--error-unmatch"],
    "rm": ["--cached"],
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
    assert len(lines) == 11, "store.v3 has eleven Core clauses; every one gets a line"
    for index, line in enumerate(lines, start=1):
        assert line.startswith(f"Core {index} — ")
        verdict = line.split(" — ")[1]
        assert verdict in {"Kept", "Not yet", "Broken", "Can't check"}


def test_ledger_rows_marked_conforms_name_a_probe_that_passes() -> None:
    """Acceptance 12: a row is CONFORMS only where its named probe passes.

    A ref is `<kit path>::<probe>`, and BOTH halves matter: every kit numbers its probes
    `probe_core_N`, so matching on the function name alone runs a cli.v2 row against the
    store kit's probe of the same number. That is how AMM-026 could read CONFORMS while
    `conformance/cli/run.py::probe_core_7` had never been called.
    """
    from conformance.cli import run as cli_kit
    from conformance.store import run as store_kit
    from conformance.suggestions import run as suggestions_kit

    kits = {
        "conformance/store/run.py": store_kit,
        "conformance/cli/run.py": cli_kit,
        # Added by lane P with the Phase 2 kit. A kit missing from this map is not a
        # failure here -- the loop below simply skips refs it does not know -- so a
        # suggestions.v1 row could read CONFORMS with nothing ever run. That is exactly
        # how AMM-026 read CONFORMS while its probe had never been called.
        "conformance/suggestions/run.py": suggestions_kit,
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
    """store.v2 Core 1/Core 9 — grep the writer, not the docstring.

    A save, a forget, a usage log and an init that do not take the lock are exactly the
    four ways the steward's store was corrupted; this asserts the source, so a future
    edit that drops one is caught here and not in someone's real MEMORY.md.
    """
    source = (REPO_ROOT / "src" / "amplifier_memory" / "store.py").read_text(encoding="utf-8")
    print(
        "\n".join(
            f"{n}: {line.strip()}"
            for n, line in enumerate(source.splitlines(), start=1)
            if "flock" in line or "_exclusive(" in line
        )
    )
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
        amplifier_memory.save(
            "never use tabs", "never use tabs", "human", "s-1", ["never use tabs"]
        )

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
    exc = subprocess.CalledProcessError(
        1, ["git", "commit"], output="nothing to commit\n", stderr=""
    )
    print(
        "stdout-only ->",
        _git.first_error_line(exc),
        "| nothing_to_commit:",
        _git.is_nothing_to_commit(exc),
    )
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
        amplifier_memory.save(
            "never use tabs", "never use tabs", "human", "s-1", ["never use tabs"]
        )
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
    """ "No memories" and "no store" are different facts; session.v2 §10 needs the second."""
    with pytest.raises(amplifier_memory.StoreMissing) as caught:
        amplifier_memory.read_memory_text(memory_home)
    print("missing store ->", caught.value)
    assert "amplifier-memory init" in str(caught.value)


# ---------------------------------------------- store.v2 §1/§8/§10: reading leaves no commit


def test_a_session_that_only_loads_leaves_no_commit_behind(store: Path) -> None:
    """store.v2 §1: appends to usage.jsonl are the one change written without a commit.

    Evidence for the clause: four `usage: loaded` commits landed in one afternoon on the
    steward's store, for sessions that changed nothing. This is the discriminating test —
    restore the commit inside `log_usage` and `after` is three higher than `before`.
    """
    before = _git.commit_count(store)
    for i in range(3):
        amplifier_memory.log_usage("loaded", "MEMORY.md", f"s-{i}")
    after = _git.commit_count(store)
    events = [json.loads(line) for line in (store / "usage.jsonl").read_text().splitlines()]

    print(f"git rev-list --count HEAD: {before} before, {after} after three loads")
    print(f"usage.jsonl: {[e['session_id'] for e in events]}")
    print(
        "git status --porcelain:",
        _git.git(["status", "--porcelain"], cwd=store).stdout or "(clean)",
    )

    assert after == before, f"three loads left {after - before} commit(s) behind"
    assert [e["event"] for e in events] == ["loaded"] * 3
    assert _git.git(["status", "--porcelain"], cwd=store).stdout.strip() == ""

    # …and a save still is exactly one commit: the exception is for reads alone.
    amplifier_memory.save("never use tabs", "never use tabs", "human", "s-1", ["never use tabs"])
    assert _git.commit_count(store) == before + 1


def test_usage_jsonl_is_untracked_and_a_pre_v2_store_migrates_once(store: Path) -> None:
    """store.v2 §1: the migration path the steward's own store needs.

    Their store still tracks `usage.jsonl` with ~10 `usage: loaded` commits. The first
    append after this version is installed (by `amplifier-memory update`) untracks it in
    one visible commit that says so, keeps every line of the file, and never runs again.
    """
    assert not _git.is_tracked(store, "usage.jsonl"), "a fresh v2 store tracks usage.jsonl"

    # Rebuild a pre-v2 store: no .gitignore, usage.jsonl tracked and carrying history.
    (store / ".gitignore").unlink()
    (store / "usage.jsonl").write_text(
        '{"ts": "2026-09-01T00:00:00+00:00", "event": "loaded", "target": "MEMORY.md", "session_id": "s-old"}\n',
        encoding="utf-8",
    )
    _git.commit(store, "usage: loaded MEMORY.md (session s-old)", ["usage.jsonl", ".gitignore"])
    assert _git.is_tracked(store, "usage.jsonl"), "the pre-v2 fixture does not track usage.jsonl"
    before = _git.commit_count(store)

    amplifier_memory.log_usage("loaded", "MEMORY.md", "s-new")
    migrated = _git.commit_count(store)
    subject = _git.git(["log", "-1", "--format=%s"], cwd=store).stdout.strip()
    body = _git.git(["log", "-1", "--format=%B"], cwd=store).stdout

    amplifier_memory.log_usage("loaded", "MEMORY.md", "s-newer")
    settled = _git.commit_count(store)
    kept_lines = (store / "usage.jsonl").read_text().splitlines()

    print(
        f"commits: {before} before, {migrated} after the first append, {settled} after the second"
    )
    print("migration subject:", subject)
    print("usage.jsonl sessions:", [json.loads(line)["session_id"] for line in kept_lines])

    assert migrated == before + 1, "the migration was not exactly one commit"
    assert subject == "store: stop tracking usage.jsonl (store.v2 \u00a71)", subject
    assert "amplifier-memory" in body and "update" in body, (
        "the commit does not say where it came from"
    )
    assert settled == migrated, "the migration ran a second time"
    assert not _git.is_tracked(store, "usage.jsonl"), "usage.jsonl is still tracked"
    assert [json.loads(line)["session_id"] for line in kept_lines] == ["s-old", "s-new", "s-newer"]
    assert "usage.jsonl" in (store / ".gitignore").read_text().splitlines()


def test_a_citation_is_recorded_against_a_memory_id_and_never_a_file(store: Path) -> None:
    """store.v2 §8: `cited` records the assistant naming a memory at use."""
    entry = amplifier_memory.record_citation("m-017", "s-1")
    print("record_citation ->", entry)
    assert entry["event"] == "cited" and entry["target"] == "m-017"
    assert set(entry) == {"ts", "event", "target", "session_id"}
    assert _git.commit_count(store) == 1, "a citation left a commit behind"

    for bad in ("MEMORY.md", "topics/yaml-style.md", "m-17", ""):
        with pytest.raises(ValueError):
            amplifier_memory.record_citation(bad, "s-1")
    with pytest.raises(ValueError):
        amplifier_memory.log_usage("cited", "topics/yaml-style.md", "s-1")
    print("a `cited` event refuses a file target")


# ------------------------------------------------------- store.v2 §6: edit keeps the id


def test_edit_keeps_the_id_and_records_what_it_replaced(store: Path) -> None:
    saved = amplifier_memory.save(
        "never use tabs in YAML files", TURNS[0], "assistant", "s-1", TURNS
    )
    before = (store / "MEMORY.md").read_text()
    edited = amplifier_memory.edit(
        "m-001", "never use tabs in YAML", TURNS[0], "assistant", "s-1", TURNS
    )
    after = (store / "MEMORY.md").read_text()
    message = _git.git(["log", "-1", "--format=%B"], cwd=store).stdout.strip()

    print("MEMORY.md before:", repr(before))
    print("MEMORY.md after: ", repr(after))
    print("git log -1 --format=%B:")
    print(message)

    assert saved.id == edited.id == "m-001", "the edit reassigned the id"
    assert after == "- [m-001] never use tabs in YAML\n"
    assert message.splitlines()[0] == "[m-001] never use tabs in YAML"
    assert 'was: "never use tabs in YAML files"' in message
    assert "action: edit" in message
    assert f"quote: {json.dumps(TURNS[0])}" in message
    assert "session: s-1" in message and "writer: assistant" in message
    assert _git.commit_count(store) == 3, "the edit was not exactly one commit"


def test_edit_makes_every_refusal_save_makes(store: Path) -> None:
    """The refusals are the point: an edit is a write, and writes are checked."""
    amplifier_memory.save("never use tabs", "never use tabs", "human", "s-1", ["never use tabs"])
    amplifier_memory.save("always rebase", "always rebase", "human", "s-1", ["always rebase"])
    frozen = (store / "MEMORY.md").read_text()

    refusals: dict[str, Exception] = {}
    cases = {
        "unknown id": lambda: amplifier_memory.edit(
            "m-404", "x y z", "x y z", "human", "s", ["x y z"]
        ),
        "line separator": lambda: amplifier_memory.edit(
            "m-001",
            "one\u2028two three",
            "one\u2028two three",
            "human",
            "s",
            ["one\u2028two three"],
        ),
        "byte cap": lambda: amplifier_memory.edit(
            "m-001", "x" * 2001, "x" * 2001, "human", "s", ["x" * 2001]
        ),
        "duplicate of another line": lambda: amplifier_memory.edit(
            "m-001", "always rebase", "always rebase", "human", "s", ["always rebase"]
        ),
        "no change": lambda: amplifier_memory.edit(
            "m-001", "never use tabs", "never use tabs", "human", "s", ["never use tabs"]
        ),
        "quote not human": lambda: amplifier_memory.edit(
            "m-001",
            "the tool said to use tabs",
            "always use tabs",
            "assistant",
            "s",
            ["never use tabs"],
        ),
    }
    # `ValueError` for the shape refusals (`_require_one_line`), the library's own
    # `MemoryError` subclasses for the rest — exactly as `save` raises them.
    for name, call in cases.items():
        with pytest.raises((ValueError, amplifier_memory.MemoryError)) as caught:
            call()
        refusals[name] = caught.value
        print(f"{name:<26} -> {type(caught.value).__name__}: {caught.value}")

    assert isinstance(refusals["unknown id"], amplifier_memory.UnknownId)
    assert isinstance(refusals["duplicate of another line"], amplifier_memory.DuplicateMemory)
    assert isinstance(refusals["quote not human"], amplifier_memory.QuoteNotHuman)
    assert (store / "MEMORY.md").read_text() == frozen, "a refused edit changed the file"
    assert _git.git(["status", "--porcelain"], cwd=store).stdout.strip() == ""


def test_forget_commits_a_forgot_subject(store: Path) -> None:
    """store.v2 §6: `git log --oneline` never shows a removal as a creation."""
    amplifier_memory.save("never use tabs", "never use tabs", "human", "s-1", ["never use tabs"])
    save_line = _git.git(["log", "--oneline", "-1"], cwd=store).stdout.strip()
    amplifier_memory.forget("m-001", session_id="s-1")
    forget_line = _git.git(["log", "--oneline", "-1"], cwd=store).stdout.strip()

    print("after save:  ", save_line)
    print("after forget:", forget_line)

    assert save_line.split(" ", 1)[1] == "[m-001] never use tabs"
    assert forget_line.split(" ", 1)[1] == "forgot [m-001] never use tabs"
    assert amplifier_memory.why("m-001")[0]["action"] == "forget"
    assert amplifier_memory.why("m-001")[0]["id"] == "m-001", "the forgot marker broke id parsing"


# --------------------------------------------------------------------------
# session.v3 §6 — the paging rule, in ONE place (AGENTS.md rule 11)
# --------------------------------------------------------------------------


def sizes(n: int, *, base: int = amplifier_memory.store.PAGE_BASE) -> list[int]:
    """Every page's item count, walked through the public function."""
    out: list[int] = []
    page = 1
    while True:
        bounds = amplifier_memory.page_bounds(n, page, base=base)
        out.append(bounds.stop - bounds.start)
        if page >= bounds.pages:
            return out
        page += 1


def test_page_bounds_is_sixes_and_a_five_for_seventeen() -> None:
    """§6, verbatim: 17 items are 6 · 6 · 5 — never 6 · 6 · 6 · 1."""
    print("17 ->", sizes(17))
    assert sizes(17) == [6, 6, 5]


def test_page_bounds_never_leaves_a_page_two_short() -> None:
    """§6: no page holds fewer than one less than the others. 13 is 5 · 4 · 4."""
    print("13 ->", sizes(13), "| 9 ->", sizes(9))
    assert sizes(13) == [5, 4, 4]
    assert sizes(9) == [5, 4]


def test_page_bounds_leaves_eight_on_one_page() -> None:
    """§6: up to 8 items is one page, so the ceremony of paging never appears."""
    print("8 ->", sizes(8), "| paged:", amplifier_memory.page_bounds(8, 1).paged)
    assert sizes(8) == [8]
    assert amplifier_memory.page_bounds(8, 1).paged is False


def test_page_bounds_pages_the_listing_at_twenty_lines() -> None:
    """§6's `list` base: 45 lines are 15 · 15 · 15 (ceil(45/20) = 3 pages)."""
    base = amplifier_memory.store.LIST_PAGE_BASE
    print(f"45 at base {base} ->", sizes(45, base=base))
    assert base == 20
    assert sizes(45, base=base) == [15, 15, 15]


def test_a_page_past_the_last_one_names_the_last_page() -> None:
    """§6: refused in one line, never clamped — page 3 is not what page 4 asked for."""
    with pytest.raises(amplifier_memory.PageOutOfRange) as refused:
        amplifier_memory.page_bounds(17, 4)
    print(refused.value)
    assert str(refused.value) == "no page 4 \u2014 the last page is 3."
    assert "\n" not in str(refused.value)


def test_the_paging_arithmetic_has_exactly_one_home() -> None:
    """AGENTS.md rule 11: `review` and `list` divide the same way, in the same code."""
    source = Path(amplifier_memory.__file__).parent
    divides = sorted(
        path.name
        for path in source.glob("*.py")
        if "-(-" in path.read_text(encoding="utf-8") or "ceil(" in path.read_text(encoding="utf-8")
    )
    print("modules doing page arithmetic:", divides)
    assert divides == ["store.py"]


# ------------------------------------------------ store.v3 §1: which instance (all four cases)


def _fake_home(monkeypatch: pytest.MonkeyPatch, root: Path) -> Path:
    """Point `Path.home()` at a temp directory, with no instance env set."""
    monkeypatch.delenv(store_mod.HOME_ENV, raising=False)
    monkeypatch.setenv("HOME", str(root))
    monkeypatch.setenv("USERPROFILE", str(root))
    assert Path.home() == root, Path.home()
    return root


def test_store_home_prefers_an_explicit_instance_over_the_env_and_the_default(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """§1's first step: "an explicit `home` from the caller" — the mount plan's, or `--home`."""
    _fake_home(monkeypatch, tmp_path / "house")
    monkeypatch.setenv(store_mod.HOME_ENV, str(tmp_path / "from-the-env"))
    resolved = amplifier_memory.store_home(tmp_path / "named-by-the-caller")
    print(f"explicit home wins: {resolved}")
    assert resolved == tmp_path / "named-by-the-caller"
    assert amplifier_memory.store_home("~/somewhere") == tmp_path / "house" / "somewhere", (
        "a ~ in an explicit home is expanded against the caller's own home directory"
    )


def test_store_home_falls_back_to_the_env_when_no_instance_is_named(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """§1's second step: "else `$AMPLIFIER_MEMORY_HOME`"."""
    _fake_home(monkeypatch, tmp_path / "house")
    monkeypatch.setenv(store_mod.HOME_ENV, str(tmp_path / "from-the-env"))
    resolved = amplifier_memory.store_home()
    print(f"{store_mod.HOME_ENV} honoured: {resolved}")
    assert resolved == tmp_path / "from-the-env"


def test_store_home_is_the_v3_default_when_nothing_else_says_otherwise(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """§1's third step: "else the default `~/.amplifier-memory`" — on a machine with neither."""
    house = _fake_home(monkeypatch, tmp_path / "house")
    house.mkdir(parents=True)
    resolved = amplifier_memory.store_home()
    print(f"no env, nothing on disk: {resolved}")
    assert resolved == house / store_mod.DEFAULT_HOME_NAME == house / ".amplifier-memory"
    assert amplifier_memory.legacy_store_present() is False


def test_store_home_keeps_the_older_path_while_it_is_the_only_store(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """§1's migration: "when the default does not exist and `~/.amplifier/memory` does".

    A device that has never seen v3 keeps reading and writing the store it already has —
    no migration, no lost memories — until `init` offers to move it (cli.v3 §8).
    """
    house = _fake_home(monkeypatch, tmp_path / "house")
    legacy = house / ".amplifier" / "memory"
    legacy.mkdir(parents=True)
    print(f"only the older store exists: {amplifier_memory.store_home()}")
    assert amplifier_memory.legacy_home() == legacy
    assert amplifier_memory.legacy_store_present() is True
    assert amplifier_memory.store_home() == legacy
    assert amplifier_memory.default_home() == legacy

    # ...and the moment the default exists, the default wins again.
    (house / store_mod.DEFAULT_HOME_NAME).mkdir()
    print(f"once the default exists: {amplifier_memory.store_home()}")
    assert amplifier_memory.store_home() == house / store_mod.DEFAULT_HOME_NAME


def test_store_home_is_what_every_surface_asks(store: Path) -> None:
    """§1 is one function: nothing else in the library builds a store path of its own."""
    source = Path(amplifier_memory.__file__).parent
    hardcoded = sorted(
        path.name
        for path in source.glob("*.py")
        if '".amplifier-memory"' in path.read_text(encoding="utf-8")
        or '".amplifier" / "memory"' in path.read_text(encoding="utf-8")
    )
    print("modules naming a store path:", hardcoded)
    assert hardcoded == ["store.py"], (
        "the resolution order lives in `store.store_home` alone; every other surface asks it"
    )


# ------------------------------- store.v3 §2 / session.v4 §13: sessions.jsonl, one line per session


def test_a_session_is_recorded_once_with_its_origin_and_read_back(store: Path) -> None:
    """session.v4 §13: `{session_id, origin, first_seen}`, idempotent per session id."""
    first = amplifier_memory.record_session(store, "s-abc", "worker")
    again = amplifier_memory.record_session(store, "s-abc", "human")
    amplifier_memory.record_session(store, "s-def")
    lines = (store / "sessions.jsonl").read_text(encoding="utf-8").splitlines()
    print("\n".join(lines))
    print("origins:", amplifier_memory.session_origins(store))

    assert [json.loads(line)["session_id"] for line in lines] == ["s-abc", "s-def"], (
        "a second sighting of one session must not add a line"
    )
    assert again == first, "the first sighting wins: neither origin nor first_seen moves"
    assert sorted(first) == ["first_seen", "origin", "session_id"]
    assert amplifier_memory.session_origins(store) == {"s-abc": "worker", "s-def": "human"}


def test_an_unknown_origin_is_refused_and_an_unset_one_is_human(
    store: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """§13 names five origins and says "Unset means `human`" — neither is guessed at."""
    monkeypatch.delenv(store_mod.ORIGIN_ENV, raising=False)
    assert amplifier_memory.origin_from_env() == "human"
    monkeypatch.setenv(store_mod.ORIGIN_ENV, "recipe")
    assert amplifier_memory.origin_from_env() == "recipe"

    with pytest.raises(ValueError) as refused:
        amplifier_memory.record_session(store, "s-1", "cron")
    print(refused.value)
    assert "unknown session origin 'cron'" in str(refused.value)
    assert (store / "sessions.jsonl").read_text(encoding="utf-8") == "", "nothing was written"


def test_sessions_jsonl_is_plumbing_and_a_session_start_leaves_no_commit(store: Path) -> None:
    """store.v3 §2, quoted: "`.lock`, `.gitignore`, `config.yaml` and `sessions.jsonl`
    inside the store are plumbing, not memory: never injected, never suggested, never
    cited."

    §2 fixes what the file *is*, not whether git tracks it; this test pins the choice
    that follows from §1 ("a session that only *reads* memory leaves no commit behind").
    The session hook appends one line at **every** session start (session.v4 §13), so a
    tracked `sessions.jsonl` would put a commit on the front of every session ever
    started — the four-commits-in-an-afternoon defect §1 was written to end. It is
    therefore **ignored**, exactly like `usage.jsonl`, and written without a commit.
    """
    before = _git.commit_count(store)
    for i in range(5):
        amplifier_memory.record_session(store, f"s-{i}", "human")
    after = _git.commit_count(store)
    tracked = _git.git(["ls-files"], cwd=store).stdout.split()
    porcelain = _git.git(["status", "--porcelain"], cwd=store).stdout.strip()
    print(f"commits before={before} after={after}; tracked={tracked}; status={porcelain!r}")

    assert after == before, "five session starts made a commit"
    assert "sessions.jsonl" not in tracked
    assert "sessions.jsonl" in (store / ".gitignore").read_text(encoding="utf-8").splitlines()
    assert porcelain == "", "the store is left clean — an ignored file is not a change"


def test_a_store_from_before_v3_starts_ignoring_sessions_in_one_visible_commit(
    store: Path,
) -> None:
    """A store created by v2 has no `sessions.jsonl` stanza; the migration adds one, once."""
    ignore = store / ".gitignore"
    ignore.write_text("usage.jsonl\n", encoding="utf-8")
    _git.commit(store, "hand edit: a .gitignore as store.v2 wrote it", [".gitignore"])
    before = _git.commit_count(store)

    amplifier_memory.record_session(store, "s-1", "human")
    amplifier_memory.record_session(store, "s-2", "human")
    subjects = _git.git(["log", "--oneline", "-2"], cwd=store).stdout.strip()
    print(f"commits: {before} -> {_git.commit_count(store)}\n{subjects}")

    assert _git.commit_count(store) == before + 1, "the migration is one commit, not one per record"
    assert store_mod.IGNORE_SESSIONS_SUBJECT in subjects
    assert "sessions.jsonl" in ignore.read_text(encoding="utf-8").splitlines()
    assert _git.git(["status", "--porcelain"], cwd=store).stdout.strip() == ""


# ---------------------------------------------- store.v3 §11: `enabled: false` makes it inert


def _disable(home: Path) -> None:
    """A human's own edit: `enabled: false` in the instance's config, committed as theirs."""
    from amplifier_memory import llm_config

    (home / llm_config.CONFIG_NAME).write_text(
        llm_config.default_body(enabled=False), encoding="utf-8"
    )
    _git.commit(home, "hand edit: turn this instance off", [llm_config.CONFIG_NAME])


def test_an_inert_instance_refuses_every_write_in_one_line(store: Path) -> None:
    """§11: "`enabled: false` makes the instance inert." Nothing is written, nothing committed."""
    amplifier_memory.save("first, a memory", "first, a memory", "human", "s", ["first, a memory"])
    _disable(store)
    assert amplifier_memory.instance_enabled(store) is False

    before = (store / "MEMORY.md").read_text(encoding="utf-8")
    commits = _git.commit_count(store)
    writes = {
        "save": lambda: amplifier_memory.save("x", "x is a thing", "human", "s", ["x is a thing"]),
        "edit": lambda: amplifier_memory.edit(
            "m-001", "x", "x is a thing", "human", "s", ["x is a thing"]
        ),
        "forget": lambda: amplifier_memory.forget("m-001", session_id="s"),
        "record_session": lambda: amplifier_memory.record_session(store, "s-1", "human"),
        "inbox.append": lambda: amplifier_memory.append(
            store, [amplifier_memory.Candidate(text="t", quote="q", session="s")]
        ),
        "inbox.decline": lambda: amplifier_memory.decline("s-001", store),
        "inbox.accept": lambda: amplifier_memory.accept("s-001", store, session_id="s"),
    }
    for name, call in writes.items():
        with pytest.raises(amplifier_memory.InstanceDisabled) as refused:
            call()
        print(f"{name}: {refused.value}")
        assert (
            str(refused.value) == f"memory is disabled for this instance ({store}: enabled: false)."
        )
        assert "\n" not in str(refused.value), "one line, not a paragraph"

    assert (store / "MEMORY.md").read_text(encoding="utf-8") == before, "a refusal wrote something"
    assert _git.commit_count(store) == commits, "a refusal committed something"
    assert _git.git(["status", "--porcelain"], cwd=store).stdout.strip() == ""


def test_reading_an_inert_instance_still_works(store: Path) -> None:
    """§11 silences the *session plane*; it does not corrupt or hide the memories."""
    amplifier_memory.save("keep me", "keep me", "human", "s", ["keep me"])
    _disable(store)
    print(amplifier_memory.list_memories(store))
    assert [m["text"] for m in amplifier_memory.list_memories(store)] == ["keep me"]
    assert amplifier_memory.instance_enabled(store) is False
    assert amplifier_memory.instance_enabled() is False, "the same instance, resolved by env"


def test_an_instance_with_no_config_and_one_with_a_broken_config_are_both_live(store: Path) -> None:
    """Every store made before v3 has no `config.yaml`, and a typo must not switch memory off."""
    from amplifier_memory import llm_config

    (store / llm_config.CONFIG_NAME).unlink()
    print("no config.yaml ->", amplifier_memory.instance_enabled(store))
    assert amplifier_memory.instance_enabled(store) is True

    (store / llm_config.CONFIG_NAME).write_text("enabled: false\nllm: [oops\n", encoding="utf-8")
    print("unreadable config.yaml ->", amplifier_memory.instance_enabled(store))
    assert amplifier_memory.instance_enabled(store) is True
    assert amplifier_memory.save("still live", "still live", "human", "s", ["still live"]).id
