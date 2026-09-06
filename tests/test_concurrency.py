"""store.v1 Core 1 / Core 9 — concurrent writers, and a writer that never lies.

The defect these tests exist for is on record. In the steward's session of
2026-09-06 (`.converge/feedback/2026-09-06-kicked-the-tires-transcript.md`) three
`memory(save)` calls were issued in one model turn. The memory tool runs each in
`asyncio.to_thread`, so three read-modify-write-commit sequences interleaved on one
`MEMORY.md`:

- one call printed `Saved memory m-001 … (committed b5fb8cd)` and its line was **not**
  in the file;
- one call printed `write to MEMORY.md did not land; refusing to commit` and its line
  **was**;
- one landed as a headless fragment with no id, which the assistant then repaired by
  hand with bash — the one thing VISION principle 4 says never happens.

Later, two parallel `forget` calls: one succeeded, the other raised
`Command '['git', '-c', 'user.name=amplifier-memory', …]'` at the human, although both
removals had landed in one commit.

Every test below fails on the pre-lane writer and passes on this one. They print what
they observed, because a concurrency claim with no output is a claim.
"""

from __future__ import annotations

import os
import subprocess
import sys
import threading
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest

import amplifier_memory
from amplifier_memory import _git
from amplifier_memory import store as store_mod


def _committed_memory(home: Path) -> list[str]:
    """`MEMORY.md` as the committed tree has it — the only state worth asserting on."""
    text = _git.show(home, "HEAD:MEMORY.md")
    assert text is not None, "HEAD does not carry MEMORY.md"
    return [line for line in text.splitlines() if line.strip()]


def _save_commits(home: Path) -> list[str]:
    return [
        record["body"].splitlines()[0]
        for record in _git.log_records(home)
        if "action: save" in record["body"]
    ]


# --------------------------------------------------------------- acceptance 3: 8 saves


def test_eight_concurrent_saves_leave_eight_wellformed_lines_and_eight_commits(
    store: Path,
) -> None:
    texts = [f"concurrent preference number {i}" for i in range(1, 9)]

    with ThreadPoolExecutor(max_workers=8) as pool:
        results = list(
            pool.map(
                lambda text: amplifier_memory.save(text, text, "human", "s-cc", [text]),
                texts,
            )
        )

    committed = _committed_memory(store)
    ids = sorted(r.id for r in results)
    print("=== git show HEAD:MEMORY.md ===")
    print("\n".join(committed))
    print("ids returned by the 8 calls:", ids)
    print("save commits:", len(_save_commits(store)))
    print("git status --porcelain:", _git.git(["status", "--porcelain"], cwd=store).stdout or "(clean)")

    assert len(committed) == 8, f"{len(committed)} lines in the committed MEMORY.md, wanted 8"
    assert ids == [f"m-{i:03d}" for i in range(1, 9)], f"ids are not m-001..m-008 with no gap: {ids}"
    assert len(set(ids)) == 8, f"an id was issued twice: {ids}"
    assert all(store_mod.wellformed(line) for line in committed), committed
    assert len(_save_commits(store)) == 8, "a mutation was not one commit"

    # The claim each call made, checked against the committed tree — the assertion the
    # old writer did not make, and the reason m-001 could be reported saved and be gone.
    for result in results:
        assert result.line in committed, f"{result.id} was reported saved but is not committed"
    assert _git.git(["status", "--porcelain"], cwd=store).stdout.strip() == "", "store left dirty"


def test_eight_concurrent_saves_from_separate_processes(store: Path) -> None:
    """store.v1 Core 9 says *sessions*, not threads: this proves the lock crosses processes.

    `fcntl.flock` is per open file description, so a thread-only test would pass even if
    the process lock were the only thing holding the line.
    """
    program = (
        "import sys, amplifier_memory;"
        "t = sys.argv[1];"
        "r = amplifier_memory.save(t, t, 'human', 's-proc', [t]);"
        "print(r.id)"
    )
    procs = [
        subprocess.Popen(
            [sys.executable, "-c", program, f"another session wrote this, number {i}"],
            env=os.environ.copy(),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        for i in range(1, 5)
    ]
    outputs = [(p.wait(), *p.communicate()) for p in procs]

    committed = _committed_memory(store)
    print("=== four separate processes ===")
    for code, out, err in outputs:
        print(f"exit {code}: {out.strip() or err.strip().splitlines()[-1:]}")
    print("=== git show HEAD:MEMORY.md ===")
    print("\n".join(committed))

    assert [code for code, _, _ in outputs] == [0, 0, 0, 0], outputs
    ids = sorted(out.strip() for _, out, _ in outputs)
    assert ids == ["m-001", "m-002", "m-003", "m-004"], ids
    assert len(committed) == 4, committed
    assert len(_save_commits(store)) == 4, "four processes did not leave four commits"


# ------------------------------------------------------- acceptance 3: concurrent forgets


def test_two_concurrent_forgets_of_different_ids_both_report_truthfully(store: Path) -> None:
    for text in ("first thing to forget", "second thing to forget", "the one that stays"):
        amplifier_memory.save(text, text, "human", "s-1", [text])

    with ThreadPoolExecutor(max_workers=2) as pool:
        outcomes = list(
            pool.map(
                lambda mid: amplifier_memory.forget(mid, store, session_id="s-1"),
                ["m-001", "m-002"],
            )
        )

    committed = _committed_memory(store)
    print("=== after two concurrent forgets ===")
    print("\n".join(committed))
    for outcome in outcomes:
        print(f"forget {outcome.id}: commit {outcome.commit[:12]} note={outcome.note!r}")

    assert committed == ["- [m-003] the one that stays"], committed
    assert {o.id for o in outcomes} == {"m-001", "m-002"}
    for outcome in outcomes:
        # Truthful means: the id this call reported gone is gone from the committed tree.
        assert all(outcome.id not in line for line in committed)
        assert "['git'" not in str(outcome.note or ""), "a raw argv reached the caller"


def test_two_concurrent_saves_of_the_same_text_leave_one_line_and_one_refusal(
    store: Path,
) -> None:
    text = "never use tabs in YAML files"

    def attempt() -> object:
        try:
            return amplifier_memory.save(text, text, "human", "s-1", [text])
        except amplifier_memory.DuplicateMemory as exc:
            return exc

    with ThreadPoolExecutor(max_workers=2) as pool:
        outcomes = [f.result() for f in [pool.submit(attempt), pool.submit(attempt)]]

    committed = _committed_memory(store)
    saved = [o for o in outcomes if isinstance(o, store_mod.SaveResult)]
    refused = [o for o in outcomes if isinstance(o, amplifier_memory.DuplicateMemory)]
    print("=== two saves of the same text ===")
    print("\n".join(committed))
    print("saved:", [o.id for o in saved], "| refused:", [str(o) for o in refused])

    assert len(saved) == 1 and len(refused) == 1, outcomes
    assert committed == [f"- [{saved[0].id}] {text}"], committed


# ----------------------------------------------- acceptance 2: verify after the commit


def test_a_save_whose_line_is_not_in_the_committed_tree_never_reports_success(
    store: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The exact failure the steward saw, fault-injected: the commit lands, the line does not."""
    real_show = _git.show

    def clobbered(home: Path, spec: str) -> str | None:
        text = real_show(home, spec)
        if spec.endswith(":MEMORY.md") and text:
            # A concurrent writer's copy of the file, without this call's line.
            return "\n".join(line for line in text.splitlines() if "clobbered" not in line) + "\n"
        return text

    monkeypatch.setattr(_git, "show", clobbered)

    with pytest.raises(amplifier_memory.WriteNotLanded) as caught:
        amplifier_memory.save(
            "this line gets clobbered", "this line gets clobbered", "human", "s-1",
            ["this line gets clobbered"],
        )
    print("raised:", caught.value)
    assert "was not saved" in str(caught.value)
    assert "['git'" not in str(caught.value), "the refusal leaked an argv"


def test_a_forget_that_did_not_land_never_reports_success(
    store: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    amplifier_memory.save("a memory to remove", "a memory to remove", "human", "s-1",
                          ["a memory to remove"])
    stale = _git.show(store, "HEAD:MEMORY.md")
    monkeypatch.setattr(_git, "show", lambda home, spec: stale)

    with pytest.raises(amplifier_memory.WriteNotLanded) as caught:
        amplifier_memory.forget("m-001", store, session_id="s-1")
    print("raised:", caught.value)
    assert "was not forgotten" in str(caught.value)


# ------------------------------------------------------------- acceptance 1: the lock


def test_flock_is_held_for_the_whole_read_modify_write_commit(store: Path) -> None:
    """A second writer waits for the first — it does not interleave with it."""
    order: list[str] = []
    holding = threading.Event()
    release = threading.Event()

    def hold() -> None:
        with store_mod._exclusive(store):
            order.append("holder acquired")
            holding.set()
            release.wait(timeout=5)
            order.append("holder released")

    thread = threading.Thread(target=hold)
    thread.start()
    assert holding.wait(timeout=5), "the holder never acquired the lock"

    def save_later() -> None:
        release.set()

    threading.Timer(0.3, save_later).start()
    result = amplifier_memory.save("waited for the lock", "waited for the lock", "human", "s-1",
                                   ["waited for the lock"])
    order.append(f"save committed {result.commit[:12]}")
    thread.join(timeout=5)

    print("order:", order)
    assert order[:2] == ["holder acquired", "holder released"] or order[1] == "holder released", order
    assert order[-1].startswith("save committed")


def test_a_store_held_too_long_is_one_line_not_a_hang(
    store: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(store_mod, "LOCK_TIMEOUT_S", 0.3)
    held = threading.Event()
    done = threading.Event()

    def hold() -> None:
        # A *separate process's* flock is what a real second session holds; here a raw
        # open+flock in this process, taken without the module lock, stands in for it.
        import fcntl

        fd = os.open(store_mod._lock_path(store), os.O_RDWR | os.O_CREAT, 0o600)
        fcntl.flock(fd, fcntl.LOCK_EX)
        held.set()
        done.wait(timeout=5)
        fcntl.flock(fd, fcntl.LOCK_UN)
        os.close(fd)

    thread = threading.Thread(target=hold)
    thread.start()
    assert held.wait(timeout=5)
    try:
        with pytest.raises(amplifier_memory.StoreBusy) as caught:
            amplifier_memory.save("blocked", "blocked", "human", "s-1", ["blocked"])
    finally:
        done.set()
        thread.join(timeout=5)

    print("raised:", caught.value)
    message = str(caught.value)
    assert message.count("\n") == 0, "a refusal is one line"
    assert "busy" in message and "nothing was written" in message


def test_the_lock_file_is_not_one_of_the_store_files(store: Path) -> None:
    """store.v2 §2: a file not listed there is not memory — so the lock is not there.

    `.git/` and `.gitignore` are the clause's named plumbing and are filtered out here
    for the same reason: neither is memory.
    """
    amplifier_memory.save("never use tabs", "never use tabs", "human", "s-1", ["never use tabs"])
    plumbing = {".git", store_mod.STORE_GITIGNORE}
    listing = sorted(p.name for p in store.iterdir() if p.name not in plumbing)
    lock = store_mod._lock_path(store)
    print("store files:", listing)
    print("lock file:", lock.relative_to(store), "exists:", lock.exists())
    print("git status --porcelain:", _git.git(["status", "--porcelain"], cwd=store).stdout or "(clean)")

    assert listing == ["MEMORY.md", "declined.md", "inbox.md", "topics", "usage.jsonl"], listing
    assert lock.exists() and lock.parent.name == ".git"
    assert _git.git(["status", "--porcelain"], cwd=store).stdout.strip() == "", "the lock dirtied the store"
