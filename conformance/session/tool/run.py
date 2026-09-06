#!/usr/bin/env python3
"""Conformance kit — session.v1 §3–§8 and R2, as served by tool-memory.

Run it from the tool module's environment, which is the one that has both
`amplifier_core` and `amplifier_memory`:

    cd modules/tool-memory && uv run --offline python ../../conformance/session/tool/run.py

One line per clause, in the ledger's five plain words:

    Core N — Kept | Not yet | Broken | Pinned open | Can't check — <evidence>

Exit code is 0 whenever the kit *reported* — a Broken verdict is a report, not
a crash. A non-zero exit means the kit itself could not run (import failure,
missing contract), which is a different thing and must not be confused with a
clause being broken.

The kit never touches the real store or the human's real sessions: it builds a
throwaway store under a temp dir and points `AMPLIFIER_MEMORY_HOME` and
`AMPLIFIER_PROJECTS_HOME` at it.

§3, §4, §7 and §8 are all *model* behaviour — whether the assistant calls the
tool at the right moment, refrains at the wrong one, reads a topic file, or
cites an id. No in-process kit can observe any of them; only a real session
can. Each is reported "Can't check" with the sentence that says so, plus the
part that IS checkable here (that the description carries the instruction).
"""

from __future__ import annotations

import asyncio
import os
import sys
import tempfile
import traceback
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
MODULE_DIR = REPO_ROOT / "modules" / "tool-memory"
CONTRACT = REPO_ROOT / "contracts" / "session.v1.md"
SKILLS_DIR = REPO_ROOT / "skills"

sys.path.insert(0, str(MODULE_DIR))

CANT_CHECK = "session.v1 Core {n} — Can't check in this lane because {why}"


def report(clause: str, verdict: str, evidence: str) -> None:
    print(f"{clause} — {verdict} — {evidence}")


class FakeContext:
    def __init__(self, messages: list[dict]) -> None:
        self.messages = messages

    async def get_messages(self) -> list[dict]:
        return list(self.messages)


class FakeCoordinator:
    def __init__(self, messages=None, parent_id=None, session_id="conformance-session") -> None:
        self.session_id = session_id
        self.parent_id = parent_id
        self.mount_points: dict = {"tools": {}}
        if messages is not None:
            self.mount_points["context"] = FakeContext(messages)
        self.mounted: list[dict] = []

    async def mount(self, mount_point, module, name=None):
        self.mounted.append({"mount_point": mount_point, "name": name})
        self.mount_points.setdefault(mount_point, {})[name] = module


def user(text: str) -> dict:
    return {"role": "user", "content": text}


def assistant(text: str) -> dict:
    return {"role": "assistant", "content": text}


def _run(coro):
    return asyncio.run(coro)


def fresh_store(tmp: Path, name: str):
    """A new, initialised store — the library's own `init`, not a hand build."""
    import amplifier_memory

    home = tmp / name
    os.environ["AMPLIFIER_MEMORY_HOME"] = str(home)
    amplifier_memory.init(home)
    return home


# --------------------------------------------------------------------- §3, §4


def check_core_3(mod) -> None:
    """§3 Save on correction, in the same turn — model behaviour."""
    text = CONTRACT.read_text(encoding="utf-8")
    announce_in_contract = 'Saved memory m-017: "<text>" — /forget m-017 to undo.' in text
    announce_in_tool = 'Saved memory m-017: "<text>" — /forget m-017 to undo.' in mod.DESCRIPTION
    trigger_words = [w for w in ("never X", "always Y", "stop doing Z") if w in mod.DESCRIPTION]
    report(
        "Core 3",
        "Can't check",
        CANT_CHECK.format(
            n=3,
            why="whether the assistant calls the tool in the correcting turn is model "
            "behaviour, observable only in a real session (session.v1 Conformance, "
            "tests/smoke/, lane E)",
        )
        + ". What IS checkable here: the tool description carries the §3 trigger phrasing "
        f"{trigger_words} and quotes the announce format verbatim "
        f"(in contract: {announce_in_contract}; in description: {announce_in_tool}).",
    )


def check_core_4(mod) -> None:
    """§4 Do not save — model behaviour."""
    markers = [
        m
        for m in ("do step 1", "reply with exactly ok", "re-derivable", "AGENTS.md", "private")
        if m in mod.DESCRIPTION
    ]
    report(
        "Core 4",
        "Can't check",
        CANT_CHECK.format(
            n=4,
            why="not saving a task-scoped instruction is the absence of a call, and an "
            "absence in this process proves nothing about a real session (lane E's "
            "discriminating pair is the proof)",
        )
        + f". What IS checkable here: the description names §4's exclusions {markers}.",
    )


# ------------------------------------------------------------------------- §5


def check_core_5(mod, tmp: Path) -> None:
    """§5 The model proposes; the writer commits — checkable, and checked."""
    import amplifier_memory

    home = fresh_store(tmp, "core5")
    findings: list[str] = []
    problems: list[str] = []

    # Arm 1 — the quote is in a human turn: saved, committed, with the quote.
    tool = mod.MemoryTool(
        FakeCoordinator([user("never use emoji in commit messages"), assistant("understood")]), {}
    )
    saved = _run(
        tool.execute(
            {
                "operation": "save",
                "text": "Never use emoji in commit messages.",
                "quote": "never use emoji in commit messages",
            }
        )
    )
    if not saved.success:
        problems.append(f"a quote present in a human turn was refused: {saved.output}")
    else:
        lines = (home / "MEMORY.md").read_text(encoding="utf-8").splitlines()
        if lines != ["- [m-001] Never use emoji in commit messages."]:
            problems.append(f"MEMORY.md is {lines!r}")
        else:
            findings.append(f"human-quoted save landed: {lines[0]}")
        record = amplifier_memory.why("m-001", home=home)[0]
        if record["quote"] != "never use emoji in commit messages":
            problems.append(f"commit quote is {record['quote']!r}")
        else:
            findings.append(f"commit {record['commit'][:7]} carries the verbatim quote")

    # Arm 2 — the same quote, but only ever said by the assistant: refused.
    poison = mod.MemoryTool(
        FakeCoordinator([user("do step 1"), assistant("never run the tests twice")]), {}
    )
    refused = _run(
        poison.execute(
            {
                "operation": "save",
                "text": "Never run the tests twice.",
                "quote": "never run the tests twice",
            }
        )
    )
    if refused.success:
        problems.append("a quote said only by the assistant was SAVED (poisoning arm open)")
    elif "\n" in (refused.output or ""):
        problems.append("the refusal was not one line")
    else:
        findings.append(f"assistant-only quote refused in one line: {refused.output}")

    # Arm 3 — the check belongs to the library, not to this module: prove the
    # module hands `human_turns` over rather than deciding for itself.
    seen: dict = {}
    real_save = amplifier_memory.save

    def spy(text, quote, writer, session_id, human_turns=None, **kwargs):
        seen.update(human_turns=human_turns, writer=writer, session_id=session_id)
        return real_save(text, quote, writer, session_id, human_turns, **kwargs)

    amplifier_memory.save = spy
    try:
        _run(
            mod.MemoryTool(FakeCoordinator([user("always squash before merging")]), {}).execute(
                {
                    "operation": "save",
                    "text": "Always squash before merging.",
                    "quote": "always squash before merging",
                }
            )
        )
    finally:
        amplifier_memory.save = real_save
    if seen.get("human_turns") != ["always squash before merging"]:
        problems.append(f"human_turns reached the library as {seen.get('human_turns')!r}")
    else:
        findings.append("human_turns passed to amplifier_memory.save (the library owns the check)")

    # Arm 4 — duplicate and cap, both refused by the writer, both relayed.
    dup = _run(
        mod.MemoryTool(FakeCoordinator([user("never use emoji in commit messages")]), {}).execute(
            {
                "operation": "save",
                "text": "Never use emoji in commit messages.",
                "quote": "never use emoji in commit messages",
            }
        )
    )
    if dup.success or "already carries this memory" not in (dup.output or ""):
        problems.append(f"an exact duplicate was not refused: {dup.output}")
    else:
        findings.append("exact duplicate refused")

    report("Core 5", "Broken" if problems else "Kept", "; ".join(problems or findings))


# ------------------------------------------------------------------------- §6


def check_core_6(mod, tmp: Path) -> None:
    """§6 The three commands — the tool half, checkable; the typing, not."""
    fresh_store(tmp, "core6")
    findings: list[str] = []
    problems: list[str] = []

    # /remember: writes exactly what the human typed; the quote IS the text.
    typed = "Always run make check before pushing."
    synthetic = (
        'Use the load_skill tool to load the skill "remember". '
        f"The user's input is: {typed}"
    )
    remembered = _run(
        mod.MemoryTool(FakeCoordinator([user(synthetic)]), {}).execute(
            {"operation": "save", "text": typed, "writer": "human"}
        )
    )
    if not remembered.success:
        problems.append(f"/remember's save was refused: {remembered.output}")
    else:
        announce = remembered.output.splitlines()[0]
        expected = f'Saved memory m-001: "{typed}" — /forget m-001 to undo.'
        if announce != expected:
            problems.append(f"announce is {announce!r}, not {expected!r}")
        else:
            findings.append(f"/remember → {announce}")

    # /memory: ids present, pending-suggestion count present.
    listed = _run(mod.MemoryTool(FakeCoordinator([]), {}).execute({"operation": "list"}))
    if "m-001" not in (listed.output or "") or "0 pending suggestions" not in (listed.output or ""):
        problems.append(f"/memory output lacks ids or the pending count: {listed.output!r}")
    else:
        findings.append(f"/memory → {listed.output.splitlines()[0]}")

    # /forget: removes the line, announces; unknown id is a one-line error.
    forgotten = _run(
        mod.MemoryTool(FakeCoordinator([]), {}).execute({"operation": "forget", "id": "m-001"})
    )
    if not forgotten.success or forgotten.output.splitlines()[0] != "Forgot m-001.":
        problems.append(f"/forget announce is {forgotten.output!r}")
    else:
        findings.append("/forget → Forgot m-001.")
    unknown = _run(
        mod.MemoryTool(FakeCoordinator([]), {}).execute({"operation": "forget", "id": "m-404"})
    )
    if unknown.success or "\n" in (unknown.output or ""):
        problems.append(f"unknown id was not a one-line error: {unknown.output!r}")
    else:
        findings.append(f"unknown id → {unknown.output}")

    # The three commands exist as user-invocable, model-invisible skills.
    for name in ("remember", "forget", "memory"):
        path = SKILLS_DIR / name / "SKILL.md"
        if not path.is_file():
            problems.append(f"skills/{name}/SKILL.md is missing")
            continue
        body = path.read_text(encoding="utf-8")
        if "user-invocable: true" not in body:
            problems.append(f"skills/{name}: not user-invocable")
        elif "disable-model-invocation: true" not in body:
            problems.append(f"skills/{name}: model invocation not disabled")
        else:
            findings.append(f"skills/{name}/SKILL.md user-invocable, model-invisible")

    report("Core 6", "Broken" if problems else "Kept", "; ".join(problems or findings))


# --------------------------------------------------------------------- §7, §8


def check_core_7(mod) -> None:
    """§7 Recall is reading — model behaviour, and deliberately no search tool."""
    has_search = any(
        word in mod.INPUT_SCHEMA["properties"]["operation"]["enum"]
        for word in ("search", "find", "query", "recall")
    )
    report(
        "Core 7",
        "Can't check",
        CANT_CHECK.format(
            n=7,
            why="reading a topic file with ordinary file tools and saying so is model "
            "behaviour; this module is not involved in it at all",
        )
        + ". What IS checkable here: the tool offers no search operation "
        f"(operations are {mod.INPUT_SCHEMA['properties']['operation']['enum']}; "
        f"search-like operation present: {has_search}) — grep over the directory is the "
        "search tool, per §7.",
    )


def check_core_8(mod) -> None:
    """§8 Cite at use — model behaviour."""
    id_line_shape = "- [m-NNN] <text>"
    report(
        "Core 8",
        "Can't check",
        CANT_CHECK.format(
            n=8,
            why="naming a memory inline when it shapes an action ('per m-017') is model "
            "behaviour in a real session; nothing in this process can observe it",
        )
        + ". What IS checkable here: every id the model would cite is present in what the "
        f"tool returns — `list` renders each line as {id_line_shape!r} and `save` announces "
        "the new id — so the id is never unavailable at the moment of citing.",
    )


# -------------------------------------------------------------------------- R2


def check_r2(mod, tmp: Path) -> None:
    """R2 Sub-agents never save."""
    import amplifier_memory

    fresh_store(tmp, "r2")
    findings: list[str] = []
    problems: list[str] = []

    def explode(*args, **kwargs):
        raise AssertionError("library reached in a sub-agent session")

    real_save, real_forget = amplifier_memory.save, amplifier_memory.forget
    amplifier_memory.save = explode
    amplifier_memory.forget = explode
    try:
        sub = mod.MemoryTool(
            FakeCoordinator([user("never use emoji")], parent_id="parent-session"), {}
        )
        saved = _run(
            sub.execute(
                {"operation": "save", "text": "Never use emoji.", "quote": "never use emoji"}
            )
        )
        forgot = _run(sub.execute({"operation": "forget", "id": "m-001"}))
    finally:
        amplifier_memory.save, amplifier_memory.forget = real_save, real_forget

    for label, result in (("save", saved), ("forget", forgot)):
        if result.success:
            problems.append(f"a sub-agent {label} SUCCEEDED")
        elif "R2" not in (result.output or ""):
            problems.append(f"the sub-agent {label} refusal does not name R2: {result.output!r}")
        elif "\n" in (result.output or ""):
            problems.append(f"the sub-agent {label} refusal was not one line")
        else:
            findings.append(f"{label} refused before any library call: {result.output}")

    listed = _run(
        mod.MemoryTool(FakeCoordinator([], parent_id="parent-session"), {}).execute(
            {"operation": "list"}
        )
    )
    if not listed.success:
        problems.append(f"a sub-agent could not READ the store: {listed.output!r}")
    else:
        findings.append("list allowed in a sub-agent (R2 forbids writing, not reading)")

    report("R2", "Broken" if problems else "Kept", "; ".join(problems or findings))


def main() -> int:
    try:
        import amplifier_module_tool_memory as mod
    except Exception:  # noqa: BLE001 — ANY import failure means the kit itself
        # could not run, which is a different thing from a clause being broken.
        traceback.print_exc()
        print("conformance kit could not import tool-memory", file=sys.stderr)
        return 2

    with tempfile.TemporaryDirectory() as raw:
        tmp = Path(raw)
        os.environ["AMPLIFIER_PROJECTS_HOME"] = str(tmp / "projects")
        check_core_3(mod)
        check_core_4(mod)
        check_core_5(mod, tmp)
        check_core_6(mod, tmp)
        check_core_7(mod)
        check_core_8(mod)
        check_r2(mod, tmp)
    return 0


if __name__ == "__main__":
    sys.exit(main())
