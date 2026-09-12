"""Integrity coverage for the ratified correction and prior-memory decision records.

These tests protect the exact decision authority and honest ledger state.  They
do not execute, or claim to execute, the pending corrected-acceptance behavior.
"""

import ast
import re
from hashlib import sha256
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
ROWS = REPO_ROOT / "ledger" / "rows.yaml"
ADDENDA = {
    "contracts/session.v5.v8-candidate.md": (
        "contracts/session.v5.md",
        "# session.v5.v8 candidate — conversational corrected acceptance (DRAFT)",
    ),
    "contracts/suggestions.v3.v5-candidate.md": (
        "contracts/suggestions.v3.md",
        "# suggestions.v3.v5 candidate — corrected acceptance of a pending suggestion (DRAFT)",
    ),
}
PUBLIC_COPY_HASHES = {
    "contracts/session.v5.v8-candidate.md":
        "1894bcb2c9e3fb7d5e71d7ba29e62f4aa797d69e844f06ed2ea284ab8ae527ae",
    "contracts/suggestions.v3.v5-candidate.md":
        "91333145597d89a3365bc114af32e8dc589156d446dad4f19996754f79960c26",
    "contracts/session.v5.v9-candidate.md":
        "ef2a502af1929109aa12017ba6c22d3c6d2bbe726328764dd6f14ac1aa3dae3a",
}
REPLACEMENT_BLOCK_HASHES = {
    "contracts/session.v5.v8-candidate.md": (
        "5d0ee4e16028e0c133e6771ae4c87d50d9c3b6b5acd99b315d27432e0757ce4b",
        "4a3d002a4766e825c40c80718367491ace9a54e681a63d27bf634a96844b631e",
        "22a7656159b3366e0c0b45d0a91cd3c494b4b4c1b46b4a9296db18c90ab5007d",
        "f3314a4a26448f4716379ae34f688ee895fc362346c587b60872652f7c8f9a5d",
        "c9c4a3333db394286f7e08f68aa1836e7ef8f27490fd16b5f808bb16f1ebd608",
    ),
    "contracts/suggestions.v3.v5-candidate.md": (
        "4432b8246a7894bd77fd31d2bdbf71c35eec03698cc09b038d46971d294e0297",
        "4e215be88832d8013de14991d7a3a29ba46fc45d5666222648c667681dc14e3b",
    ),
    "contracts/session.v5.v9-candidate.md": (
        "0f21f81c61d96a4f4cc27372047d036aa6d12293e5d0f0887092d76560bc6b1b",
        "e74ff681ee6ad7fb02da3b402ae0bef8c90dd1671cf65b10a758968e4f7d043f",
        "be384a0e6d65fa57d848950d15a8f510b581b4964d5ca451456c720bed19211c",
        "6fd9da162380b799abc882d684388ea7dd1bf422593d4a6eb7afa1a30c4030a2",
    ),
}
PRIOR_MEMORY_ADDENDUM = "contracts/session.v5.v9-candidate.md"


def _row_block(row_id: str) -> str:
    text = ROWS.read_text(encoding="utf-8")
    start = text.index(f"- id: {row_id}\n")
    end = text.find("\n- id: ", start + 1)
    return text[start:] if end == -1 else text[start:end]


def _replacement_digests(text: str) -> tuple[str, ...]:
    blocks = re.findall(r"Replacement:\n\n```\n(.*?)\n```", text, re.DOTALL)
    return tuple(sha256(block.encode()).hexdigest() for block in blocks)


def test_public_addenda_keep_their_targets_and_verified_replacement_blocks() -> None:
    """Publication redacts narrative only; the proposed contract text remains exact."""
    for relative, (target, heading) in ADDENDA.items():
        content = (REPO_ROOT / relative).read_bytes()
        assert sha256(content).hexdigest() == PUBLIC_COPY_HASHES[relative]
        text = (REPO_ROOT / relative).read_text(encoding="utf-8")
        assert text.startswith(f"target: {target}\n")
        assert heading in text
        assert _replacement_digests(text) == REPLACEMENT_BLOCK_HASHES[relative]
        assert "Sanitized publication copy." in text
        assert "Only nonnormative evidence and ratification prose has been redacted." in text
        assert "Ratification applies to the exact replacements above" in " ".join(text.split())


def test_corrected_acceptance_rows_preserve_the_verified_evidence_boundary() -> None:
    """Indexed deterministic proof is not native/model evidence or a new lock."""
    expected = {
        "AMM-047": (
            "contracts/session.v5.v8-candidate.md",
            "disposition: CONFORMS",
            "For one existing, pending HUMAN-origin stable `s-NNN`",
        ),
        "AMM-048": (
            "contracts/suggestions.v3.v5-candidate.md",
            "disposition: CONFORMS",
            "For one existing pending, HUMAN-origin stable `s-NNN`",
        ),
        "AMM-049": (
            "contracts/session.v5.v8-candidate.md",
            "disposition: NOT-ASSERTABLE",
            "Native conversational/model behavior cannot be established",
        ),
    }
    for row_id, (record, disposition, required_text) in expected.items():
        block = _row_block(row_id)
        assert f"file: {record}" in block
        assert disposition in block
        assert required_text in block
        if row_id == "AMM-049":
            assert "disposition: CONFORMS" not in block
            assert "kind: none" in block
        else:
            assert "previous_disposition: GAP" in block
            assert "kind: indexed" in block
            reference = block.split("    ref: ", 1)[1].splitlines()[0]
            path, name = reference.split("::")
            tree = ast.parse((REPO_ROOT / path).read_text(encoding="utf-8"))
            assert any(isinstance(node, ast.FunctionDef) and node.name == name for node in tree.body)


def test_sync_pins_remain_the_five_locked_governing_documents() -> None:
    """Decision records never masquerade as a sixth locked-document pin."""
    sync = _row_block("AMM-000")
    for candidate in ADDENDA:
        assert candidate not in sync
    assert PRIOR_MEMORY_ADDENDUM not in sync
    assert sync.count("sha256:") == 5


def test_full_corrected_acceptance_applicability_is_quoted() -> None:
    expected = {
        "AMM-047": (
            "For one existing, pending HUMAN-origin stable `s-NNN` in that frozen map, a "
            "clear natural authorization to accept corrected text — for example, `accept "
            "it but ...` — is a **corrected accept** exception, not a new command and not "
            "ordinary accept."
        ),
        "AMM-048": (
            "For one existing pending, HUMAN-origin stable `s-NNN`, a clear natural "
            "authorization to accept corrected text — for example, `accept it but ...` — "
            "is **corrected accept**, not a new command and not ordinary accept."
        ),
    }
    for row_id, quote in expected.items():
        quoted = _row_block(row_id).split("quote: >-", 1)[1].split("  disposition:", 1)[0]
        assert " ".join(quoted.split()) == quote


def test_prior_memory_addendum_has_its_own_exact_ratification() -> None:
    """The publication copy preserves v9's exact proposed text, not private narrative."""
    content = (REPO_ROOT / PRIOR_MEMORY_ADDENDUM).read_bytes()
    assert sha256(content).hexdigest() == PUBLIC_COPY_HASHES[PRIOR_MEMORY_ADDENDUM]
    text = content.decode("utf-8")
    assert text.startswith("target: contracts/session.v5.md\n")
    assert "(DRAFT)" in text.splitlines()[2]
    assert _replacement_digests(text) == REPLACEMENT_BLOCK_HASHES[PRIOR_MEMORY_ADDENDUM]
    assert "Sanitized publication copy." in text
    assert "Ratification applies to the four exact replacements above" in " ".join(text.split())


def test_prior_memory_rows_separate_recorded_checks_from_native_evidence() -> None:
    authority = " ".join((REPO_ROOT / PRIOR_MEMORY_ADDENDUM).read_text().split())
    for row_id in ("AMM-050", "AMM-051", "AMM-052"):
        block = _row_block(row_id)
        assert f"file: {PRIOR_MEMORY_ADDENDUM}" in block
        quote = block.split("quote: >-", 1)[1].split("  disposition:", 1)[0]
        assert " ".join(quote.split()) in authority
        if row_id == "AMM-052":
            assert "disposition: NOT-ASSERTABLE" in block
            assert "kind: none" in block
        else:
            assert "disposition: CONFORMS" in block
            assert "kind: indexed" in block
            reference = block.split("    ref: ", 1)[1].splitlines()[0]
            path, name = reference.split("::")
            tree = ast.parse((REPO_ROOT / path).read_text())
            assert any(
                isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == name
                for node in tree.body
            )