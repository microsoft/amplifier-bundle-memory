"""Focused, provider-free proof for the atomic pending-suggestion correction."""

from __future__ import annotations

import concurrent.futures
import subprocess

import pytest

import amplifier_memory
from amplifier_memory import _git, inbox
from amplifier_memory.store import SaveResult

SOURCE_TEXT = "For Microsoft repository changes, name every file you expect to modify."
SOURCE_QUOTE = "For Microsoft repository changes, name every file you expect to modify."
CORRECTION = "Please remove the Microsoft-specific scope and make it apply to any repository."
CORRECTED = "For repository changes, name every file you expect to modify."


def source(store, *, session="source-human"):
    """Create one actual pending HUMAN-origin suggestion, never a fake inbox object."""
    amplifier_memory.record_session(store, session, "human")
    return inbox.append(
        store, [inbox.Candidate(SOURCE_TEXT, SOURCE_QUOTE, session, "2026-09-12")]
    )[0]


def snapshot(store):
    return {
        "memory": (store / "MEMORY.md").read_bytes(),
        "inbox": (store / "inbox.md").read_bytes(),
        "head": _git.head(store),
        "index": _git.git(
            ["ls-files", "--stage", "-z", "--", "MEMORY.md", "inbox.md"], cwd=store
        ).stdout,
        "cached_diff": _git.git(
            ["diff", "--cached", "--binary", "--", "MEMORY.md", "inbox.md"], cwd=store
        ).stdout,
    }


def correct(store, sid):
    return inbox.accept_corrected(
        sid, CORRECTED, CORRECTION, "correction-session", [CORRECTION], home=store
    )


def test_corrected_accept_is_one_commit_with_current_and_source_provenance(store):
    item = source(store)
    before = _git.commit_count(store)

    result = correct(store, item.id)
    memory = (store / "MEMORY.md").read_text(encoding="utf-8")
    pending = inbox.pending(store)
    message = _git.git(["log", "-1", "--format=%B"], cwd=store).stdout
    print(message)

    assert _git.commit_count(store) == before + 1
    assert memory == f"- [{result.id}] {CORRECTED}\n"
    assert SOURCE_TEXT not in memory
    assert [candidate.id for candidate in pending] == []
    assert f'quote: "{CORRECTION}"' in message
    assert "session: correction-session" in message
    assert "writer: assistant" in message
    assert "action: corrected-accept" in message
    assert f"source-suggestion-id: {item.id}" in message
    assert f'source-suggestion-quote: "{SOURCE_QUOTE}"' in message
    assert "source-suggestion-session: source-human" in message


@pytest.mark.parametrize(
    "text,quote,exc",
    [
        ("", CORRECTION, ValueError),
        (CORRECTED, "", amplifier_memory.QuoteNotHuman),
        (CORRECTED, "invented quote", amplifier_memory.QuoteNotHuman),
    ],
)
def test_validation_refusals_leave_every_target_and_head_unchanged(store, text, quote, exc):
    item = source(store)
    before = snapshot(store)

    with pytest.raises(exc):
        inbox.accept_corrected(item.id, text, quote, "correction-session", [CORRECTION], home=store)

    assert snapshot(store) == before


def test_nonhuman_source_refuses_without_mutation(store):
    item = inbox.append(
        store, [inbox.Candidate(SOURCE_TEXT, SOURCE_QUOTE, "worker-source", "2026-09-12")]
    )[0]
    amplifier_memory.record_session(store, "worker-source", "worker")
    before = snapshot(store)

    with pytest.raises(amplifier_memory.QuoteNotHuman, match="HUMAN-origin"):
        correct(store, item.id)

    assert snapshot(store) == before


def test_duplicate_and_cap_refusals_leave_source_pending(store):
    duplicate = source(store)
    amplifier_memory.save(CORRECTED, CORRECTED, "human", "other", [CORRECTED], home=store)
    duplicate_before = snapshot(store)
    with pytest.raises(amplifier_memory.DuplicateMemory):
        correct(store, duplicate.id)
    assert snapshot(store) == duplicate_before

    capped = store.parent / "capped"
    capped.mkdir()
    amplifier_memory.init(capped)
    item = source(capped, session="capped-source")
    (capped / "MEMORY.md").write_text(
        "".join(f"- [m-{number:03d}] filler {number}\n" for number in range(1, 201)),
        encoding="utf-8",
    )
    capped_before = snapshot(capped)
    with pytest.raises(amplifier_memory.CapExceeded):
        correct(capped, item.id)
    assert snapshot(capped) == capped_before


def stage_divergent_targets(store):
    """Give both correction targets distinct staged and working bytes."""
    (store / "MEMORY.md").write_bytes(b"- [m-009] staged memory line\n")
    (store / "inbox.md").write_bytes((store / "inbox.md").read_bytes() + b"# staged inbox note\n")
    _git.add(store, ["MEMORY.md", "inbox.md"])
    (store / "MEMORY.md").write_bytes(b"- [m-009] working memory line\n")
    (store / "inbox.md").write_bytes((store / "inbox.md").read_bytes() + b"# working inbox note\n")


@pytest.mark.parametrize("failed_target", ["MEMORY.md", "inbox.md"])
def test_write_failure_restores_divergent_target_index_and_worktree_exactly(
    store, monkeypatch, failed_target
):
    item = source(store)
    stage_divergent_targets(store)
    before = snapshot(store)
    original = inbox._atomic_write

    def fail_target(path, text):
        if path.name == failed_target:
            raise OSError(f"injected {failed_target} write failure")
        return original(path, text)

    monkeypatch.setattr(inbox, "_atomic_write", fail_target)
    with pytest.raises(OSError, match="injected"):
        correct(store, item.id)

    assert snapshot(store) == before


def test_known_unsuccessful_commit_restores_divergent_target_index_and_worktree_exactly(
    store, monkeypatch
):
    item = source(store)
    stage_divergent_targets(store)
    before = snapshot(store)

    def fail_commit(*args, **kwargs):
        raise amplifier_memory.GitFailed("injected known-unsuccessful commit")

    monkeypatch.setattr(inbox, "_commit_or_already_applied", fail_commit)
    with pytest.raises(amplifier_memory.GitFailed, match="known-unsuccessful"):
        correct(store, item.id)

    assert snapshot(store) == before


def test_generic_unchanged_head_commit_error_requires_inspection_without_rollback(store, monkeypatch):
    item = source(store)
    before = snapshot(store)

    monkeypatch.setattr(
        inbox,
        "_commit_or_already_applied",
        lambda *args, **kwargs: (_ for _ in ()).throw(RuntimeError("transport disconnected")),
    )
    with pytest.raises(
        amplifier_memory.CorrectedAcceptanceInspectionRequired,
        match="^commit outcome is unknown; inspect the memory store before retrying$",
    ):
        correct(store, item.id)

    after = snapshot(store)
    assert after["head"] == before["head"]
    assert after["memory"] != before["memory"]
    assert after["inbox"] != before["inbox"]


def test_failed_head_read_after_commit_error_requires_inspection(store, monkeypatch):
    item = source(store)
    original_head = inbox._git.head
    reads = 0

    def head_once_then_fail(path):
        nonlocal reads
        reads += 1
        if reads > 1:
            raise OSError("cannot read HEAD")
        return original_head(path)

    monkeypatch.setattr(inbox._git, "head", head_once_then_fail)
    monkeypatch.setattr(
        inbox,
        "_commit_or_already_applied",
        lambda *args, **kwargs: (_ for _ in ()).throw(RuntimeError("transport disconnected")),
    )
    with pytest.raises(
        amplifier_memory.CorrectedAcceptanceInspectionRequired,
        match="^commit outcome is unknown; inspect the memory store before retrying$",
    ):
        correct(store, item.id)


def test_landed_but_raised_commit_uses_head_evidence_and_returns_one_result(store, monkeypatch):
    item = source(store)
    original = inbox._commit_or_already_applied

    def landed_then_raised(*args, **kwargs):
        original(*args, **kwargs)
        raise RuntimeError("transport lost after commit")

    monkeypatch.setattr(inbox, "_commit_or_already_applied", landed_then_raised)
    result = correct(store, item.id)

    assert result.text == CORRECTED
    assert item.id not in (store / "inbox.md").read_text(encoding="utf-8")


def test_readback_rejects_unrelated_changed_path(store, monkeypatch):
    item = source(store)
    original = inbox._git.git

    def corrupt_changed_paths(args, **kwargs):
        result = original(args, **kwargs)
        if args[0] == "diff-tree":
            return subprocess.CompletedProcess(args, 0, stdout="MEMORY.md\ninbox.md\nunrelated.md\n")
        return result

    monkeypatch.setattr(inbox._git, "git", corrupt_changed_paths)
    with pytest.raises(
        amplifier_memory.CorrectedAcceptanceUnverified,
        match="^commit succeeded but readback is unverified$",
    ):
        correct(store, item.id)


def test_readback_rejects_wrong_commit_parent(store, monkeypatch):
    item = source(store)
    original = inbox._git.git

    def corrupt_parent(args, **kwargs):
        result = original(args, **kwargs)
        if args[0] == "rev-parse" and args[1].endswith("^"):
            return subprocess.CompletedProcess(args, 0, stdout="wrong-parent\n")
        return result

    monkeypatch.setattr(inbox._git, "git", corrupt_parent)
    with pytest.raises(
        amplifier_memory.CorrectedAcceptanceUnverified,
        match="^commit succeeded but readback is unverified$",
    ):
        correct(store, item.id)


def test_readback_rejects_altered_commit_metadata(store, monkeypatch):
    item = source(store)
    original = inbox._git.git

    def corrupt_metadata(args, **kwargs):
        result = original(args, **kwargs)
        if args[0] == "log" and "--format=%B" in args:
            return subprocess.CompletedProcess(
                args, 0, stdout=result.stdout.replace("writer: assistant", "writer: human")
            )
        return result

    monkeypatch.setattr(inbox._git, "git", corrupt_metadata)
    with pytest.raises(
        amplifier_memory.CorrectedAcceptanceUnverified,
        match="^commit succeeded but readback is unverified$",
    ):
        correct(store, item.id)


def test_readback_rejects_missing_source_removal(store, monkeypatch):
    item = source(store)
    original = inbox._git.show

    def corrupt_inbox(home, spec):
        content = original(home, spec)
        if spec.endswith(":inbox.md"):
            return item.render() + "\n"
        return content

    monkeypatch.setattr(inbox._git, "show", corrupt_inbox)
    with pytest.raises(
        amplifier_memory.CorrectedAcceptanceUnverified,
        match="^commit succeeded but readback is unverified$",
    ):
        correct(store, item.id)


def test_unrelated_staged_path_refuses_before_corrected_acceptance_mutates_targets(store):
    item = source(store)
    (store / "unrelated.md").write_text("keep staged work\n", encoding="utf-8")
    _git.add(store, ["unrelated.md"])
    before = snapshot(store)
    unrelated_before = _git.git(
        ["diff", "--cached", "--binary", "--", "unrelated.md"], cwd=store
    ).stdout

    with pytest.raises(amplifier_memory.WriteNotLanded, match="unrelated staged path"):
        correct(store, item.id)

    assert snapshot(store) == before
    assert _git.git(["diff", "--cached", "--binary", "--", "unrelated.md"], cwd=store).stdout == unrelated_before


def test_new_git_index_and_transition_arguments_are_documented():
    checks = {
        "ls-files": ("--stage", "-z"),
        "update-index": ("--index-info",),
        "diff": ("--cached", "--name-only", "--binary"),
        "diff-tree": ("--no-commit-id", "--name-only", "-r"),
    }
    for command, flags in checks.items():
        proc = subprocess.run(
            ["git", command, "--help"],
            capture_output=True,
            text=True,
            check=True,
            env={"MANPAGER": "cat", "GIT_PAGER": "cat"},
        )
        assert all(flag in proc.stdout for flag in flags)
        print(f"git {command} --help documents {flags}")


def test_postcommit_readback_failure_never_rolls_back_or_allocates_another_id(store, monkeypatch):
    item = source(store)
    monkeypatch.setattr(inbox, "_assert_corrected_acceptance", lambda *args: (_ for _ in ()).throw(OSError()))

    with pytest.raises(
        amplifier_memory.CorrectedAcceptanceUnverified,
        match="^commit succeeded but readback is unverified$",
    ):
        correct(store, item.id)

    assert CORRECTED in (store / "MEMORY.md").read_text(encoding="utf-8")
    assert item.id not in (store / "inbox.md").read_text(encoding="utf-8")


def test_stale_repeat_refuses_without_allocating_another_memory(store):
    item = source(store)
    result = correct(store, item.id)
    before = snapshot(store)

    with pytest.raises(amplifier_memory.UnknownSuggestion):
        correct(store, item.id)

    assert snapshot(store) == before
    assert (store / "MEMORY.md").read_text(encoding="utf-8") == f"- [{result.id}] {CORRECTED}\n"


def test_concurrent_calls_cannot_create_two_corrections_for_one_source(store):
    item = source(store)
    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
        futures = [executor.submit(correct, store, item.id) for _ in range(2)]
        outcomes = [future.exception() or future.result() for future in futures]

    saved = [outcome for outcome in outcomes if isinstance(outcome, SaveResult)]
    failures = [outcome for outcome in outcomes if isinstance(outcome, BaseException)]
    print("saved:", saved, "failures:", failures)
    assert len(saved) == 1
    assert len(failures) == 1 and isinstance(failures[0], amplifier_memory.UnknownSuggestion)
    assert (store / "MEMORY.md").read_text(encoding="utf-8").count(CORRECTED) == 1