"""The engineering council's hostile corpus, as a suite (2026-09-06 review, B1-B4, B7).

Every test here is a defect that was **reproduced by execution** against the installed
library before it was fixed, not a hypothetical. Each one prints the evidence a human
would look at: the refusal sentence, the sha256 of `MEMORY.md` before and after, the
`git status --porcelain` output, the doctor row, the discarded line.

The corpus:

| input | was | is |
|---|---|---|
| `U+2028` in a memory text | written to disk, then "did not land", then published by the hook | refused before any write |
| `U+0085`, lone `\\r`, other separators | same | refused before any write |
| a BOM in a memory text | saved invisibly; two identical-looking memories | refused before any write |
| one raw `\\xe9` byte in `MEMORY.md` | `UnicodeDecodeError` out of six functions incl. `doctor` | a `[FAIL]` row naming the byte offset, exit 1, no traceback |
| a 131 KB memory text | `OSError` from git's argv, *after* `git add` staged it | refused before any write |
| a commit that fails after the write | the new text left in the working tree and the index | file restored from HEAD, index clean |
| `quote='e'` | accepted, and a fabricated provenance record | `QuoteNotHuman` |
| `doctor --repair` | restored `MEMORY.md` to `''` without saying what it deleted | names every discarded line before committing |
"""

from __future__ import annotations

import hashlib
import subprocess
import sys
from pathlib import Path

import pytest

import amplifier_memory
from amplifier_memory import _git
from amplifier_memory import store as store_mod

TURNS = ["never use tabs in YAML files; always two-space indentation, please"]


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _porcelain(home: Path) -> str:
    return _git.git(["status", "--porcelain"], cwd=home).stdout.strip()


def _seed(home: Path) -> None:
    amplifier_memory.save(
        "never use tabs in YAML files", "never use tabs in YAML files", "human", "s-1",
        ["never use tabs in YAML files"], home=home,
    )


# --------------------------------------------------------------- acceptance 2: separators


@pytest.mark.parametrize(
    ("name", "char"),
    [
        ("U+2028 LINE SEPARATOR", "\u2028"),
        ("U+2029 PARAGRAPH SEPARATOR", "\u2029"),
        ("U+0085 NEXT LINE", "\x85"),
        ("U+000D CARRIAGE RETURN", "\r"),
        ("U+000B LINE TABULATION", "\v"),
        ("U+000C FORM FEED", "\f"),
        ("U+001C FILE SEPARATOR", "\x1c"),
        ("U+001D GROUP SEPARATOR", "\x1d"),
        ("U+001E RECORD SEPARATOR", "\x1e"),
    ],
)
def test_a_line_separator_is_refused_before_anything_is_written(
    store: Path, name: str, char: str
) -> None:
    """store.v1 Core 3: one memory is one line — and the file is untouched by the refusal."""
    _seed(store)
    memory = store / "MEMORY.md"
    before = _sha256(memory)

    text = f"never use tabs{char}always two-space indentation"
    with pytest.raises(ValueError) as caught:
        amplifier_memory.save(text, text, "human", "s-1", [text], home=store)

    after = _sha256(memory)
    print(f"{name}: {caught.value}")
    print(f"  sha256 before={before}\n  sha256 after ={after}\n  status={_porcelain(store)!r}")
    assert f"U+{ord(char):04X}" in str(caught.value)
    assert before == after, "the refused text reached the disk"
    assert _porcelain(store) == "", "the refused text was left staged"


def test_the_u2028_probe_end_to_end_leaves_the_store_usable(store: Path) -> None:
    """B1, as the council ran it: refuse, file byte-identical, and the NEXT save succeeds.

    The old failure was not only that the corruption was written; it was that the store
    was then wedged — `_require_wellformed` refused every later save.
    """
    _seed(store)
    memory = store / "MEMORY.md"
    before = memory.read_bytes()

    with pytest.raises(ValueError) as caught:
        amplifier_memory.save(
            "never use tabs\u2028always two-space", "never use tabs\u2028always two-space",
            "human", "s-1", ["never use tabs\u2028always two-space"], home=store,
        )
    print("refused:", caught.value)
    print("file on disk unchanged:", memory.read_bytes() == before, memory.read_bytes())

    healthy = amplifier_memory.save(
        "always two-space indentation", "always two-space indentation", "human", "s-1",
        ["always two-space indentation"], home=store,
    )
    print("the next save still works:", healthy.line)
    assert memory.read_bytes() != before  # because the healthy save landed
    assert healthy.line in memory.read_text(encoding="utf-8")
    assert amplifier_memory.verify_store(store).ok
    assert _porcelain(store) == ""


def test_a_bom_or_a_control_character_in_a_memory_is_refused(store: Path) -> None:
    """A BOM is invisible: it would make two identical-looking memories compare unequal."""
    _seed(store)
    before = _sha256(store / "MEMORY.md")

    for label, text in (
        ("BOM U+FEFF", "\ufeffnever use tabs in YAML files"),
        ("NUL U+0000", "never use tabs\x00in YAML"),
        ("DEL U+007F", "never use tabs\x7fin YAML"),
    ):
        with pytest.raises(ValueError) as caught:
            amplifier_memory.save(text, text, "human", "s-1", [text], home=store)
        print(f"{label}: {caught.value}")
    print("sha256 unchanged:", _sha256(store / "MEMORY.md") == before)
    assert _sha256(store / "MEMORY.md") == before
    assert _porcelain(store) == ""


# --------------------------------------------------------------- acceptance 4: the argv floor


def test_an_oversize_memory_is_refused_before_it_can_be_staged(store: Path) -> None:
    """B3: 131 KB used to reach git's argv, raise OSError, and leave the file staged."""
    _seed(store)
    memory = store / "MEMORY.md"
    before = _sha256(memory)

    text = "x" * 131_072
    with pytest.raises(ValueError) as caught:
        amplifier_memory.save(text, text, "human", "s-1", [text], home=store)

    print("refused:", caught.value)
    print(f"  sha256 before={before}\n  sha256 after ={_sha256(memory)}")
    print(f"  git status --porcelain: {_porcelain(store)!r}")
    assert str(store_mod.MEMORY_BYTE_CAP) in str(caught.value).replace(",", "")
    assert "131,072 bytes" in str(caught.value)
    assert _sha256(memory) == before
    assert _porcelain(store) == "", "the refused save left something staged"


def test_a_large_but_legal_memory_commits_through_stdin_not_argv(store: Path) -> None:
    """The discriminating half: right under the cap still works, message intact in git."""
    text = "never use tabs in YAML files, " + "and always two-space indent, " * 60
    text = text[: store_mod.MEMORY_BYTE_CAP - 1].strip()
    saved = amplifier_memory.save(text, text, "human", "s-1", [text], home=store)
    body = _git.log_records(store)[0]["body"]
    print(f"saved {saved.id} with a {len(text)}-byte text; commit message carries it:",
          body.splitlines()[0][:80] + "…")
    assert text in body, "the commit message lost the text when it went through stdin"


def test_the_id_regex_is_bounded(store: Path) -> None:
    """A pasted line with a 400-digit id can no longer become an int this code trusts."""
    _seed(store)
    memory = store / "MEMORY.md"
    memory.write_text(
        memory.read_text(encoding="utf-8") + f"- [m-{'9' * 400}] pasted from somewhere\n",
        encoding="utf-8",
    )
    check = amplifier_memory.verify_store(store)
    print("verify_store on a 400-digit id:", check.render())
    assert not check.ok, "an unbounded id was accepted as a well-formed memory line"


# --------------------------------------------------------------- acceptance 1: rollback


def test_a_commit_that_fails_after_the_write_reverts_the_working_tree(
    store: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """B1/B3's shared root: a refusal must not leave the new text on disk or in the index."""
    _seed(store)
    memory = store / "MEMORY.md"
    before = memory.read_bytes()

    def exploding_commit(*args: object, **kwargs: object) -> str:
        raise subprocess.CalledProcessError(
            128, ["git", "commit"], output="", stderr="fatal: unable to write new index file"
        )

    monkeypatch.setattr(_git, "commit", exploding_commit)

    with pytest.raises(amplifier_memory.GitFailed) as caught:
        amplifier_memory.save(
            "always rebase before pushing", "always rebase before pushing", "human", "s-1",
            ["always rebase before pushing"], home=store,
        )

    print("refused:", caught.value)
    print("MEMORY.md reverted to HEAD:", memory.read_bytes() == before)
    print("bytes on disk:", memory.read_bytes())
    print(f"git status --porcelain: {_porcelain(store)!r}")
    assert memory.read_bytes() == before, "the failed save left its line in the working tree"
    assert _porcelain(store) == "", "the failed save left its line staged for the next commit"
    assert "always rebase" not in memory.read_text(encoding="utf-8")


def test_the_working_tree_is_asserted_not_only_the_committed_tree(
    store: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """B6: the hook reads the working file, so a clean commit over a corrupt file is a lie."""
    _seed(store)
    memory = store / "MEMORY.md"
    real_commit = _git.commit

    def commit_then_clobber(home: Path, message: str, paths: list[str], **kwargs: object) -> str:
        sha = real_commit(home, message, paths, **kwargs)  # type: ignore[arg-type]
        # An editor saving over the file in the window between the commit and the
        # assert. The committed tree is now clean and the working tree is not — and the
        # working tree is the one `hooks-memory-inject` publishes to the model.
        memory.write_text("- [m-001] never use tabs in YAML files\n", encoding="utf-8")
        return sha

    monkeypatch.setattr(_git, "commit", commit_then_clobber)

    with pytest.raises(amplifier_memory.WriteNotLanded) as caught:
        amplifier_memory.save(
            "always rebase before pushing", "always rebase before pushing", "human", "s-1",
            ["always rebase before pushing"], home=store,
        )
    print("refused:", caught.value)
    print("working tree on disk:", memory.read_text(encoding="utf-8").rstrip())
    assert "working-tree" in str(caught.value)


# --------------------------------------------------------------- acceptance 3: one bad byte


def _corrupt_with_a_raw_byte(home: Path) -> int:
    memory = home / "MEMORY.md"
    raw = memory.read_bytes() + b"- [m-002] Jos\xe9 prefers short reviews\n"
    memory.write_bytes(raw)
    return raw.index(b"\xe9")


def test_one_non_utf8_byte_is_survivable_by_every_reader(store: Path) -> None:
    """B2: `save` · `verify_store` · `list_memories` · `status` · `doctor` — six for six."""
    _seed(store)
    offset = _corrupt_with_a_raw_byte(store)

    memories = amplifier_memory.list_memories(store)
    check = amplifier_memory.verify_store(store)
    report = amplifier_memory.doctor(store, installed_sha=None, remote_sha=None)
    print(f"raw 0xe9 byte at offset {offset}")
    for memory in memories:
        print("  list_memories ->", memory)
    print("verify_store reports the bad one:", check.render())
    print("status survives:", amplifier_memory.status(store).render().splitlines()[0])
    print("doctor exit code:", report.exit_code)
    # Every line still comes back — the undecodable byte is U+FFFD in the text, so the
    # human sees which memory carries it — and the byte itself is reported by
    # `verify_store` (and so by the `doctor` row), which is where a remedy is named.
    assert [m["id"] for m in memories] == ["m-001", "m-002"]
    assert "\ufffd" in memories[1]["text"]
    assert check.decode_error_offset == offset
    assert not check.ok
    assert report.exit_code == 1


def test_doctor_prints_a_fail_row_for_the_bad_byte_with_no_traceback(store: Path) -> None:
    """cli.v1 Core 5: doctor never crashes on the store it inspects. Run as a real process."""
    _seed(store)
    offset = _corrupt_with_a_raw_byte(store)

    proc = subprocess.run(
        [sys.executable, "-c", "from amplifier_memory.cli import main; main()", "doctor"],
        capture_output=True,
        text=True,
        check=False,
        env={
            **__import__("os").environ,
            "AMPLIFIER_MEMORY_HOME": str(store),
        },
    )
    print(proc.stdout)
    print("stderr:", proc.stderr or "(empty)")
    print("exit code:", proc.returncode)
    assert proc.returncode == 1, "a store that cannot be decoded is a failed check"
    assert "Traceback" not in proc.stderr and "Traceback" not in proc.stdout
    assert "UnicodeDecodeError" not in proc.stderr
    assert f"byte offset {offset} is not UTF-8" in proc.stdout
    assert "[FAIL]" in proc.stdout


def test_a_store_with_a_bad_byte_refuses_a_save_instead_of_burying_it(store: Path) -> None:
    _seed(store)
    _corrupt_with_a_raw_byte(store)
    with pytest.raises(amplifier_memory.StoreMalformed) as caught:
        amplifier_memory.save(
            "always rebase", "always rebase before pushing to main", "assistant", "s-1",
            ["always rebase before pushing to main"], home=store,
        )
    print("save into a corrupt store refused:", caught.value)
    assert "not UTF-8" in str(caught.value)


# --------------------------------------------------------------- acceptance 5: honest repair


def test_repair_names_every_line_it_discards_before_it_commits(store: Path) -> None:
    """B7: a repair that deletes a memory must say which memory it deleted."""
    _seed(store)
    memory = store / "MEMORY.md"
    memory.write_text(
        memory.read_text(encoding="utf-8") + "always two-space indentation\n", encoding="utf-8"
    )
    _git.commit(store, "hand edit: a headless fragment, as the transcript found it", ["MEMORY.md"])
    head_before = _git.head(store)

    said: list[tuple[str, str]] = []
    result = amplifier_memory.repair_store(
        store, announce=lambda line: said.append((line, _git.head(store)))
    )

    for line, head in said:
        print(f"[HEAD {head[:12]}] {line}")
    print("committed:", result.commit[:12], "restored from:", result.restored_from[:12])
    assert result.discarded == ["always two-space indentation"]
    assert any("always two-space indentation" in line for line, _ in said)
    assert all(head == head_before for _, head in said), (
        "the discarded lines were announced only after the commit"
    )
    assert result.commit != head_before
    assert amplifier_memory.verify_store(store).ok


def test_repair_truncates_a_pasted_blob_in_its_report(store: Path) -> None:
    _seed(store)
    memory = store / "MEMORY.md"
    memory.write_text(memory.read_text(encoding="utf-8") + "z" * 500 + "\n", encoding="utf-8")
    _git.commit(store, "hand edit: a pasted blob", ["MEMORY.md"])

    said: list[str] = []
    result = amplifier_memory.repair_store(store, announce=said.append)
    print("\n".join(said))
    assert len(result.discarded[0]) == store_mod.DISCARD_PREVIEW_CHARS
    assert result.discarded[0].endswith("\u2026")


# --------------------------------------------------------------- acceptance 6: the quote floor


def test_a_one_letter_quote_no_longer_authorises_a_memory(store: Path) -> None:
    """B4, verbatim: `quote='e'` against the steward's own turn used to be accepted."""
    turn = "Great remember these for me"
    # 'e', 'for' and 'these' are all real substrings of the turn — the council's exploit.
    for quote in ("e", "for", "these"):
        with pytest.raises(amplifier_memory.QuoteNotHuman) as caught:
            amplifier_memory.save(
                "bkrabach prefers dark mode and lives in Seattle", quote, "assistant", "s-1",
                [turn], home=store,
            )
        print(f"quote={quote!r} refused: {caught.value}")
        assert "too short to identify a human turn" in str(caught.value)

    # 'ok' is not in the turn at all: refused by the older half of the same check.
    with pytest.raises(amplifier_memory.QuoteNotHuman) as caught:
        amplifier_memory.save(
            "always deploy straight to prod without review", "ok", "assistant", "s-1",
            [turn], home=store,
        )
    print(f"quote='ok' refused: {caught.value}")
    assert "does not appear verbatim" in str(caught.value)

    real = amplifier_memory.save(
        "never use tabs in YAML files", "never use tabs in YAML files", "assistant", "s-1",
        TURNS, home=store,
    )
    print(f"a real quoted sentence still saves: {real.id} <- {TURNS[0]!r}")
    assert amplifier_memory.list_memories(store) == [
        {
            "id": real.id,
            "text": "never use tabs in YAML files",
            "source": "MEMORY.md",
            "lineno": 1,
            "raw": real.line,
        }
    ]


def test_a_quote_that_is_the_whole_human_turn_is_exempt_from_the_floor(store: Path) -> None:
    """`/remember use uv` is the human's whole turn: it identifies itself, however short.

    The floor exists because a *fragment* of a longer turn can be picked to mean anything.
    A quote equal to the entire turn cannot: there is nothing else in the turn.
    """
    saved = amplifier_memory.save("use uv", "use uv", "human", "s-1", ["use uv"], home=store)
    print(f"whole-turn quote 'use uv' accepted as {saved.id}")

    with pytest.raises(amplifier_memory.QuoteNotHuman) as caught:
        amplifier_memory.save(
            "use tabs", "use tabs", "human", "s-1", ["please never use tabs anywhere"], home=store
        )
    print("the same 8-character quote, as a fragment of a longer turn:", caught.value)
    assert "too short to identify a human turn" in str(caught.value)
