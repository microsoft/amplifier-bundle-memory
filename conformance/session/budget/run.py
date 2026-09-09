#!/usr/bin/env python3
"""Conformance kit — session.v5's budget clauses: what this bundle puts into EVERY model
request (§11, `probe_core_11`) and that none of it asserts what the human can see
(Conformance, `probe_no_presumption`). One probe per clause; `main()` runs every
`probe_*` here and exits with the worst code.

Run it from the tool module's environment, which is the one that has
`amplifier_core`, `amplifier_memory` and `tiktoken`:

    cd modules/tool-memory && uv run --offline python ../../conformance/session/budget/run.py

session.v5 §11 caps four sources at **500 cl100k tokens** together: the memory
tool's description, its parameter text, the skills' names and descriptions, and
§1's framing sentence. `MEMORY.md` itself is the product and is not counted.

The steward measured 1,011 fixed tokens against 147 of actual memories on
2026-09-07 and said: "minimize the # of tokens needed for any of the things
always injected into the context of the llm request … in fact, report on that
accounting for me". So this kit **prints the per-source breakdown** every run,
whether it passes or not. A ceiling with no itemised bill is a number nobody can
act on.

Unlike `conformance/session/tool/run.py`, this kit exits **non-zero when the
clause is broken**, not only when the kit cannot run: §11 is a budget, and a
budget that reports overspending with exit 0 is not a budget. Exit 2 still means
the kit itself could not run (a missing import, an unreadable skill), which is a
different thing and must not be read as "the ceiling holds".

Every source is read from the thing that actually ships:

* the description and the parameter text from the **imported module object**,
  never from a copy in this file — a kit measuring its own transcription would
  pass forever after the module changed;
* each skill's two lines from its own `SKILL.md` frontmatter, which is what the
  runtime shows the model;
* the framing sentence from `amplifier_module_hooks_memory_inject`'s constant,
  imported, never re-typed.
"""

from __future__ import annotations

import json
import sys
import traceback
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
TOOL_MODULE = REPO_ROOT / "modules" / "tool-memory"
INJECT_MODULE = REPO_ROOT / "modules" / "hooks-memory-inject"
SKILLS_DIR = REPO_ROOT / "skills"

sys.path.insert(0, str(TOOL_MODULE))
sys.path.insert(0, str(INJECT_MODULE))

#: session.v5 §11, verbatim: "at most 500 tokens".
CEILING = 500
#: §11 names the encoding, so the kit does not get to choose one.
ENCODING = "cl100k_base"


def report(clause: str, verdict: str, evidence: str) -> None:
    print(f"{clause} — {verdict} — {evidence}")


def schema_text(schema: dict) -> str:
    """Every readable string in the tool's parameter schema.

    Names, enum values and descriptions — everything a provider serialises into
    the request as words. JSON punctuation is left out: it is real cost, but it
    is not text anyone can edit, and counting it would hide the part that can be.
    The raw serialisation is printed below as a separate, informational line so
    nothing is quietly left off the bill.
    """
    parts: list[str] = []
    for name, prop in schema.get("properties", {}).items():
        parts.append(name)
        parts.extend(prop.get("enum") or [])
        parts.append(prop.get("description", ""))
    return "\n".join(parts)


def skill_lines() -> list[tuple[str, str]]:
    """(skill, the name+description line the runtime shows the model).

    The frontmatter is parsed as YAML — a folded `description: >-` block and a
    one-line quoted `description: "…"` are the same value to the runtime and to
    this meter. A skill whose frontmatter cannot be read is raised, not skipped:
    an unmeasured source is not a free source.
    """
    import yaml

    out: list[tuple[str, str]] = []
    for path in sorted(SKILLS_DIR.glob("*/SKILL.md")):
        body = path.read_text(encoding="utf-8")
        blocks = body.split("---", 2)
        if len(blocks) < 3:
            raise ValueError(f"{path} has no frontmatter to measure")
        meta = yaml.safe_load(blocks[1]) or {}
        name, described = meta.get("name"), meta.get("description")
        if not name or not described:
            raise ValueError(f"{path} frontmatter has no name/description to measure")
        out.append((path.parent.name, f"{str(name).strip()}: {' '.join(str(described).split())}"))
    return out


def probe_core_11() -> int:
    """§11 — the four injected sources, itemised, against the 500-token ceiling."""
    import amplifier_module_tool_memory as tool
    import tiktoken
    from amplifier_module_hooks_memory_inject import FRAMING_SENTENCE

    encode = tiktoken.get_encoding(ENCODING).encode

    sources: list[tuple[str, str]] = [
        ("tool DESCRIPTION", tool.DESCRIPTION),
        ("tool INPUT_SCHEMA text", schema_text(tool.INPUT_SCHEMA)),
    ]
    sources += [(f"skill {name}", line) for name, line in skill_lines()]
    sources.append(("inject framing sentence", FRAMING_SENTENCE))

    print(f"session.v5 §11 — every model request pays this, in {ENCODING} tokens:")
    print()
    total = 0
    for label, text in sources:
        count = len(encode(text))
        total += count
        print(f"  {count:>4}  {label}")
    print(f"  {'-' * 4}")
    print(f"  {total:>4}  total (ceiling {CEILING})")
    print()
    print(
        "  for scale: MEMORY.md itself is the product and is not counted; the four "
        "sources above are, and they are what a session pays before a single memory "
        "is loaded."
    )
    print(
        f"  informational: the whole INPUT_SCHEMA as JSON is "
        f"{len(encode(json.dumps(tool.INPUT_SCHEMA, ensure_ascii=False)))} tokens — the "
        "structure a provider serialises around the parameter text counted above."
    )
    print()

    if total > CEILING:
        report(
            "session.v5 Core 11",
            "Broken",
            f"{total} tokens injected into every model request, {total - CEILING} over the "
            f"{CEILING} ceiling; the breakdown above names where they are",
        )
        return 1
    report(
        "session.v5 Core 11",
        "Kept",
        f"{total} of {CEILING} tokens ({CEILING - total} spare); breakdown printed above",
    )
    return 0


# --- session.v5 Conformance: the no-presumption grep (lane 13-C) -----------------

THIS_FILE = Path(__file__).resolve()

#: session.v5 Conformance — "Nothing the model is given asserts what the human
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
    """session.v5 Conformance — nothing the model is given presumes a screen.

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
    try:
        sys.exit(main())
    except Exception:  # noqa: BLE001 — the kit could not run, which is not a verdict
        traceback.print_exc()
        print("conformance kit could not measure the injected budget", file=sys.stderr)
        sys.exit(2)
