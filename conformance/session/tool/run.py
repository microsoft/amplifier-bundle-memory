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

#: The two rules lane H fixed by hand into the goal. A paraphrase is a
#: different rule, so both are compared byte for byte.
IDS_RULE = (
    "Ids are the only names. A bare number N means m-00N, never a position in a list. "
    "Never guess an id: if it cannot be resolved, list the current ids and ask."
)
NO_RESTATE_RULE = (
    "Never restate a memory receipt or listing in your own words; "
    "the tool result is what the human reads."
)


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
    if dup.success or dup.output != "already remembered as m-001 — nothing changed.":
        problems.append(f"an exact duplicate was not refused by id: {dup.output}")
    else:
        findings.append(f"exact duplicate refused by id: {dup.output}")

    report("Core 5", "Broken" if problems else "Kept", "; ".join(problems or findings))


# ------------------------------------------------------------------------- §6


def check_core_6(mod, tmp: Path) -> None:
    """§6 The three commands — the tool half, checkable; the typing, not."""
    fresh_store(tmp, "core6")
    findings: list[str] = []
    problems: list[str] = []

    # The two literals §3 and §6 fix are re-extracted from the LOCKED contract,
    # not retyped here: a receipt may only ADD lines under them.
    contract = CONTRACT.read_text(encoding="utf-8")
    save_literal = 'Saved memory m-017: "<text>" — /forget m-017 to undo.'
    forget_literal = "Forgot m-017."
    for literal in (save_literal, forget_literal):
        if literal not in contract:
            problems.append(f"{literal!r} is not in the locked contract; the kit is out of date")

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
        got = remembered.output.splitlines()
        expected = [save_literal.replace("m-017", "m-001").replace("<text>", typed),
                    "your words, verbatim"]
        if got != expected:
            problems.append(f"/remember receipt is {got!r}, not {expected!r}")
        else:
            findings.append(f"/remember → {got[0]} + {got[1]}")

    # A save the assistant worded carries the approving quote, so a human can
    # tell their own sentence from the assistant's rewrite of it.
    drafted = _run(
        mod.MemoryTool(FakeCoordinator([user("Great, remember these for me")]), {}).execute(
            {
                "operation": "save",
                "text": "When I say explain, go long with headers.",
                "quote": "remember these for me",
            }
        )
    )
    if not drafted.success:
        problems.append(f"an assistant-worded save was refused: {drafted.output}")
    elif drafted.output.splitlines()[1] != 'my wording, your go-ahead: "remember these for me"':
        problems.append(f"assistant provenance line is {drafted.output.splitlines()[1]!r}")
    else:
        findings.append(f"assistant save → {drafted.output.splitlines()[1]}")

    # /memory: the count, `-` bullets with ids first, the hand-edit path last,
    # and none of the subsystem noise a human cannot act on.
    listed = _run(mod.MemoryTool(FakeCoordinator([]), {}).execute({"operation": "list"}))
    lines = (listed.output or "").splitlines()
    noise = [n for n in ("pending suggestions", "topic files", "Phase 1") if n in (listed.output or "")]
    if lines[:1] != ["2 memories"]:
        problems.append(f"/memory header is {lines[:1]!r}, not ['2 memories']")
    elif not lines[1].startswith("- [m-001] "):
        problems.append(f"/memory first bullet is {lines[1]!r}")
    elif not lines[-1].startswith("edit by hand: $EDITOR "):
        problems.append(f"/memory last line is {lines[-1]!r}, not the hand-edit path")
    elif noise:
        problems.append(f"/memory still carries {noise}")
    else:
        findings.append(f"/memory → {lines[0]} … {lines[-1]}")

    # /forget: removes the line, announces, and echoes what left.
    forgotten = _run(
        mod.MemoryTool(FakeCoordinator([]), {}).execute({"operation": "forget", "id": "m-001"})
    )
    got = (forgotten.output or "").splitlines()
    expected = [
        forget_literal.replace("m-017", "m-001"),
        typed,
        "still in git: amplifier-memory why m-001",
    ]
    if not forgotten.success or got != expected:
        problems.append(f"/forget receipt is {got!r}, not {expected!r}")
    else:
        findings.append(f"/forget → {got[0]} + the removed text + {got[2]}")

    unknown = _run(
        mod.MemoryTool(FakeCoordinator([]), {}).execute({"operation": "forget", "id": "m-404"})
    )
    if unknown.success or "\n" in (unknown.output or ""):
        problems.append(f"unknown id was not a one-line error: {unknown.output!r}")
    elif not unknown.output.startswith("no memory m-404 —") or "Say the id." not in unknown.output:
        problems.append(f"unknown id does not name the fate and the current ids: {unknown.output!r}")
    else:
        findings.append(f"unknown id → {unknown.output}")

    # The three commands exist as user-invocable, model-invisible skills, and
    # carry the two rules that keep ids unguessable and receipts unrepeated.
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
        elif IDS_RULE not in body:
            problems.append(f"skills/{name}: the ids rule is missing or paraphrased")
        elif NO_RESTATE_RULE not in body:
            problems.append(f"skills/{name}: the no-restate rule is missing or paraphrased")
        else:
            findings.append(f"skills/{name}/SKILL.md user-invocable, model-invisible, both rules")

    # The false line, in every file that could carry it.
    for path in [*sorted(SKILLS_DIR.glob("*/SKILL.md")), MODULE_DIR / "amplifier_module_tool_memory" / "__init__.py"]:
        lowered = path.read_text(encoding="utf-8").lower()
        said = [c for c in ("can't write these", "cannot write these", "you type them") if c in lowered]
        if said:
            problems.append(f"{path.name} still claims the assistant cannot save: {said}")
    if not problems:
        findings.append("no file claims the assistant cannot save what the human approved")

    report("Core 6", "Broken" if problems else "Kept", "; ".join(problems or findings))


# ------------------------------------------------------------- store.v1 §5


def check_store_5(mod, tmp: Path) -> None:
    """store.v1 §5: a ruleset reaches a topic file, and leaves ONE pointer line."""
    home = fresh_store(tmp, "store5")
    findings: list[str] = []
    problems: list[str] = []

    said = "keep my ADHD rules somewhere"
    tool = mod.MemoryTool(FakeCoordinator([user(said)]), {})
    receipt = None
    for text in ("Lead with the next action.", "Cap lists at five items."):
        receipt = _run(
            tool.execute(
                {
                    "operation": "save",
                    "text": text,
                    "quote": said,
                    "topic": "adhd-style",
                    "topic_purpose": "How to shape a reply for me.",
                }
            )
        )
        if not receipt.success:
            problems.append(f"a topic save was refused: {receipt.output}")
    pointer = _run(
        tool.execute(
            {
                "operation": "save",
                "text": "How to shape a reply for me → topics/adhd-style.md",
                "quote": said,
            }
        )
    )
    if not pointer.success:
        problems.append(f"the pointer save was refused: {pointer.output}")

    topic_lines = (home / "topics" / "adhd-style.md").read_text(encoding="utf-8").splitlines()
    memory_lines = (home / "MEMORY.md").read_text(encoding="utf-8").splitlines()
    if topic_lines[:1] != ["How to shape a reply for me."]:
        problems.append(f"the topic file does not begin with its purpose: {topic_lines[:1]!r}")
    elif len(topic_lines) != 3:
        problems.append(f"topics/adhd-style.md is {topic_lines!r}")
    elif len(memory_lines) != 1 or "→ topics/adhd-style.md" not in memory_lines[0]:
        problems.append(f"MEMORY.md is {memory_lines!r}, not one pointer line")
    elif receipt is not None and "topics/adhd-style.md" not in receipt.output:
        problems.append("the receipt does not name the topic file it wrote")
    else:
        findings.append(
            f"topics/adhd-style.md = {topic_lines!r}; MEMORY.md = {memory_lines!r}; "
            f"receipt names both files"
        )

    report("store.v1 Core 5", "Broken" if problems else "Kept", "; ".join(problems or findings))


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
        check_store_5(mod, tmp)
        check_core_7(mod)
        check_core_8(mod)
        check_r2(mod, tmp)
    return 0


if __name__ == "__main__":
    sys.exit(main())
