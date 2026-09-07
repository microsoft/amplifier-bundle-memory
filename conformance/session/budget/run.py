#!/usr/bin/env python3
"""Conformance kit — what this bundle puts into EVERY model request.

Run it from the tool module's environment, which is the one that has
`amplifier_core`, `amplifier_memory` and `tiktoken`:

    cd modules/tool-memory && uv run --offline python ../../conformance/session/budget/run.py

session.v3 §11 caps four sources at **500 cl100k tokens** together: the memory
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
import re
import sys
import traceback
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
TOOL_MODULE = REPO_ROOT / "modules" / "tool-memory"
INJECT_MODULE = REPO_ROOT / "modules" / "hooks-memory-inject"
SKILLS_DIR = REPO_ROOT / "skills"

sys.path.insert(0, str(TOOL_MODULE))
sys.path.insert(0, str(INJECT_MODULE))

#: session.v3 §11, verbatim: "at most 500 tokens".
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

    The frontmatter's folded `description: >-` block is flattened to one line,
    which is how it arrives in the catalogue. A skill whose frontmatter cannot be
    read is raised, not skipped: an unmeasured source is not a free source.
    """
    out: list[tuple[str, str]] = []
    for path in sorted(SKILLS_DIR.glob("*/SKILL.md")):
        body = path.read_text(encoding="utf-8")
        blocks = body.split("---", 2)
        if len(blocks) < 3:
            raise ValueError(f"{path} has no frontmatter to measure")
        frontmatter = blocks[1]
        name = re.search(r"^name:\s*(.+)$", frontmatter, re.MULTILINE)
        described = re.search(r"^description:\s*>-?\s*\n((?:[ \t]+.*\n)+)", frontmatter, re.MULTILINE)
        if name is None or described is None:
            raise ValueError(f"{path} frontmatter has no name/description to measure")
        out.append((path.parent.name, f"{name.group(1).strip()}: {' '.join(described.group(1).split())}"))
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

    print(f"session.v3 §11 — every model request pays this, in {ENCODING} tokens:")
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
            "session.v3 Core 11",
            "Broken",
            f"{total} tokens injected into every model request, {total - CEILING} over the "
            f"{CEILING} ceiling; the breakdown above names where they are",
        )
        return 1
    report(
        "session.v3 Core 11",
        "Kept",
        f"{total} of {CEILING} tokens ({CEILING - total} spare); breakdown printed above",
    )
    return 0


def main() -> int:
    probes = (probe_core_11,)
    return max(probe() for probe in probes)


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception:  # noqa: BLE001 — the kit could not run, which is not a verdict
        traceback.print_exc()
        print("conformance kit could not measure the injected budget", file=sys.stderr)
        sys.exit(2)
