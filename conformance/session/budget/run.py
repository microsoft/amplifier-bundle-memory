#!/usr/bin/env python3
"""Conformance kit — session.v3's budget clauses, one probe per clause.

Run it:

    python3 conformance/session/budget/run.py

Every probe prints what it measured and either returns 0 or raises
`SystemExit(1)`. `main()` runs every `probe_*` in this module and exits with
the worst code any of them produced, so a probe added here later is picked up
without editing `main()`.
"""

from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
THIS_FILE = Path(__file__).resolve()

#: session.v3 Conformance — "Nothing the model is given asserts what the human
#: can or cannot see of a tool call … Checked by grep for the presuming phrases
#: (the ones Part A of `session.v2.v3-candidate.md` removed)".
#:
#: These are exactly those phrases. The rule they replace is
#: relay-verbatim-never-reword, which says what the model must DO with the
#: text and claims nothing about what reaches the human's screen — because
#: many clients hide tool calls, and some collapse them behind a scroll.
#: Matching is case-insensitive, which makes this a superset of the literal
#: list and never a subset. Measured on this branch: `modules/tool-memory/
#: tests/test_tool_memory.py:916` reads "The human reads nothing." — one
#: capital letter, and a literal-case grep walks straight past the very
#: sentence the clause exists to catch.
PRESUMING_PHRASES = (
    "the human reads",
    "Say nothing",
    "counted, not read",
    "what the human reads",
    "the human reads nothing",
)

_NEEDLES = tuple(phrase.lower() for phrase in PRESUMING_PHRASES)

#: The four roots the clause names. `contracts/` is deliberately absent: the
#: lock-time correction to the candidate's Change 4 says the grep scans the
#: implementation, not the contract — a check cannot scan the sentence that
#: defines it. This file is excluded twice over: it lives outside every root
#: below, and `_scan_files` skips it by path anyway.
SCAN_ROOTS = ("modules", "skills", "behaviors", "bundle.md")

#: Build artefacts and vendored trees. Every one of these is gitignored, so a
#: hit inside one is not part of the committed state and would make the probe
#: report on bytes nobody ships.
SKIP_DIRS = frozenset(
    {
        ".git",
        ".venv",
        "venv",
        "__pycache__",
        ".pytest_cache",
        ".ruff_cache",
        ".mypy_cache",
        "node_modules",
        "dist",
        "build",
        "site-packages",
    }
)

SKIP_SUFFIXES = frozenset({".lock", ".pyc", ".pyo", ".so", ".png", ".jpg", ".gif", ".pdf"})


def _scan_files(root: Path) -> list[Path]:
    """Every readable text file under the clause's four roots, sorted.

    A missing root is not an error: a fixture tree carries only the roots the
    fixture needs, and the probe must be runnable against one.
    """
    found: list[Path] = []
    for name in SCAN_ROOTS:
        target = root / name
        if not target.exists():
            continue
        candidates = [target] if target.is_file() else sorted(target.rglob("*"))
        for path in candidates:
            if not path.is_file():
                continue
            if any(part in SKIP_DIRS for part in path.parts):
                continue
            if path.suffix in SKIP_SUFFIXES:
                continue
            if path.resolve() == THIS_FILE:
                continue
            found.append(path)
    return found


def presuming_hits(root: Path) -> list[tuple[str, int, str]]:
    """`(path, line number, the line)` for every presuming phrase under `root`.

    Decoding is tolerant (`errors="replace"`): store.v2 §9 invites hand edits,
    and one byte that is not UTF-8 must not turn a check into a crash.
    """
    hits: list[tuple[str, int, str]] = []
    for path in _scan_files(root):
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        for lineno, line in enumerate(text.splitlines(), start=1):
            lowered = line.lower()
            if any(needle in lowered for needle in _NEEDLES):
                rel = path.relative_to(root).as_posix()
                hits.append((rel, lineno, line.strip()))
    return hits


def probe_no_presumption(repo_root: Path | str | None = None) -> int:
    """session.v3 Conformance — nothing the model is given presumes a screen.

    Prints every remaining hit as `path:line: text` and raises `SystemExit(1)`
    if there is one; returns 0 when the four roots are clean. Pass `repo_root`
    to point it at a fixture tree instead of this repository.
    """
    root = Path(repo_root).resolve() if repo_root else REPO_ROOT
    scanned = _scan_files(root)
    hits = presuming_hits(root)

    print(f"probe_no_presumption — {len(scanned)} files under {SCAN_ROOTS} of {root}")
    print(f"  phrases (matched case-insensitively): {list(PRESUMING_PHRASES)}")
    print("  contracts/ is not scanned (the check cannot scan the sentence that defines it)")
    print(f"  this kit's own source is excluded: {THIS_FILE.name}")
    for rel, lineno, text in hits:
        print(f"{rel}:{lineno}: {text}")

    if hits:
        print(f"probe_no_presumption — Broken — {len(hits)} presuming phrase(s) remain")
        raise SystemExit(1)
    print(
        "probe_no_presumption — Kept — no presuming phrase in "
        "modules/, skills/, behaviors/, bundle.md"
    )
    return 0


def main() -> int:
    """Run every `probe_*` in this module; exit with the worst code."""
    codes: list[int] = []
    for name, probe in sorted(vars(sys.modules[__name__]).items()):
        if not name.startswith("probe_") or not callable(probe):
            continue
        try:
            codes.append(int(probe() or 0))
        except SystemExit as exc:  # a probe reporting Broken, not a crash
            codes.append(int(exc.code or 0))
    return max(codes, default=0)


if __name__ == "__main__":
    raise SystemExit(main())
