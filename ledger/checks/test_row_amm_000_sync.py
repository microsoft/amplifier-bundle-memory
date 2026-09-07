"""Row AMM-000 (SYNC): the ledger is pinned to the exact contract text it was derived from.

A mismatch here is never a silent bump. It means a locked contract changed under
the ledger, and every row must be re-reviewed against the new text.
"""

from __future__ import annotations

import hashlib
import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
ROWS = REPO_ROOT / "ledger" / "rows.yaml"


def _sync_pins() -> list[tuple[str, str]]:
    """The `path`/`sha256` pairs of row AMM-000, read without a YAML dependency."""
    text = ROWS.read_text(encoding="utf-8")
    start = text.index("- id: AMM-000")
    end = text.index("\n- id: ", start)
    block = text[start:end]
    paths = re.findall(r"- path:\s*(\S+)", block)
    hashes = re.findall(r"sha256:\s*([0-9a-f]{64})", block)
    assert len(paths) == len(hashes) == 5, (
        f"AMM-000 pins {len(paths)} paths and {len(hashes)} hashes"
    )
    return list(zip(paths, hashes, strict=True))


def test_row_amm_000_sync() -> None:
    for relative, expected in _sync_pins():
        path = REPO_ROOT / relative
        assert path.is_file(), f"AMM-000 pins {relative}, which does not exist"
        actual = hashlib.sha256(path.read_bytes()).hexdigest()
        print(f"{relative}: {actual}")
        assert actual == expected, (
            f"{relative} has changed under the ledger (pinned {expected}, found {actual}). "
            "A locked contract moved: re-review every row before touching this pin."
        )


def test_the_pinned_documents_are_the_locked_ones() -> None:
    """The four locked contracts, plus the vision they are derived from.

    `docs/VISION.v2.md` joined the pin on 2026-09-07: a silent change to the document
    that governs the contracts is the same drift this row exists to catch. It is pinned
    as a governing document, not as a contract with rows of its own.
    """
    pinned = sorted(path for path, _ in _sync_pins())
    assert pinned == [
        "contracts/cli.v3.md",
        "contracts/session.v4.md",
        "contracts/store.v3.md",
        "contracts/suggestions.v2.md",
        "docs/VISION.v2.md",
    ], pinned
    for relative in pinned:
        heading = (REPO_ROOT / relative).read_text(encoding="utf-8").splitlines()[0]
        assert "(FROZEN" in heading, f"{relative} is pinned by AMM-000 but is not locked: {heading}"
