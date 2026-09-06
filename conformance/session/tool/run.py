#!/usr/bin/env python3
"""Conformance kit — session.v2 §3–§8 and R2, as served by tool-memory.

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

**What v2 changed for this kit.** In v1 every one of §3, §6 and §8 was model
behaviour end to end, so the kit could only say "Can't check". In v2 the
receipts are rendered by this module, in code — so the *rendering* half of §3,
§6 and §8 is now asserted here, byte for byte, and reported under its own
clause name (`Core 3 (receipt)`). The other half — whether the assistant calls
the tool in the correcting turn, refrains at the wrong one, reads a topic file,
or cites an id in its prose — is still observable only in a real session, and is
still reported "Can't check" with the sentence that says so.
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
MODULE_SOURCE = MODULE_DIR / "amplifier_module_tool_memory" / "__init__.py"
CONTRACT = REPO_ROOT / "contracts" / "session.v2.md"
SKILLS_DIR = REPO_ROOT / "skills"
BEHAVIOR = REPO_ROOT / "behaviors" / "memory-session.yaml"
BUNDLE = REPO_ROOT / "bundle.md"

sys.path.insert(0, str(MODULE_DIR))

CANT_CHECK = "session.v2 Core {n} — Can't check in this lane because {why}"

#: The four commands §6 names, and the two rules every one of them carries. A
#: paraphrase is a different rule, so both are compared byte for byte.
COMMANDS = ("remember", "edit", "forget", "memory")
IDS_RULE = (
    "Ids are the only names. A bare number N means m-00N, never a position in a list. "
    "Never guess an id: if it cannot be resolved, list the current ids and ask."
)
NO_RESTATE_RULE = (
    "Never restate a memory receipt or listing in your own words; "
    "the tool result is what the human reads."
)
CITE_RULE = (
    "When a memory changes what you would otherwise have done, write `per m-NNN` "
    "inline and call `cite` with that id."
)

#: §6: "No receipt carries a commit sha, a phase name, a zero-valued count, or a
#: `<placeholder>`." Each entry is a literal that must appear in no receipt and
#: nowhere in the module's own source.
FORBIDDEN_IN_A_RECEIPT = (
    "Saved memory",
    "Forgot m-",
    "committed ",
    "Phase 1",
    "Phase 2",
    "0 topic",
    "0 memories",
    "0 pending",
    "pending suggestions",
    "<placeholder>",
)

#: The v1 receipts and the words that produced them, in the files that render a
#: receipt at all. A literal left in the source is a receipt waiting to happen.
STALE_IN_SOURCE = FORBIDDEN_IN_A_RECEIPT


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


def sha_like(line: str) -> bool:
    """A bare hex run of 7+ characters — the shape of a commit sha (§6)."""
    run = 0
    for char in line + " ":
        if char in "0123456789abcdef":
            run += 1
            continue
        if run >= 7:
            return True
        run = 0
    return False


def scan_receipt(where: str, output: str) -> list[str]:
    """Everything §6 forbids, found in one rendered receipt."""
    problems = [f"{where} carries {bad!r}" for bad in FORBIDDEN_IN_A_RECEIPT if bad in output]
    problems += [
        f"{where} carries something sha-shaped: {line!r}"
        for line in output.splitlines()
        if sha_like(line)
    ]
    return problems


# ------------------------------------------------------------------- §3, §4


def check_core_3(mod, tmp: Path) -> None:
    """§3 — the receipt is rendered here (checked); the calling is not (not)."""
    home = fresh_store(tmp, "core3")
    findings: list[str] = []
    problems: list[str] = []

    contract = CONTRACT.read_text(encoding="utf-8")
    for literal in (
        "saved m-017 — /forget m-017 to undo.",
        "your words, verbatim",
        'my wording, your go-ahead: "<the quote>"',
    ):
        if literal not in contract:
            problems.append(f"{literal!r} is not in the locked contract; the kit is out of date")

    # Arm 1 — the human's own words. Three lines, byte for byte.
    typed = "Never use tabs in YAML files you write for me."
    human = _run(
        mod.MemoryTool(FakeCoordinator([user(typed)]), {}).execute(
            {"operation": "save", "text": typed, "writer": "human"}
        )
    )
    expected = [
        "saved m-001 — /forget m-001 to undo.",
        f"  {typed}",
        "  your words, verbatim",
    ]
    got = (human.output or "").splitlines()
    if not human.success or got != expected:
        problems.append(f"the writer=human receipt is {got!r}, not {expected!r}")
    else:
        findings.append("writer=human receipt byte-identical to the §3 fixture")
    problems += scan_receipt("the writer=human receipt", human.output or "")

    # Arm 2 — the assistant's wording, the human's go-ahead.
    approval = "Great, remember these for me"
    tool = mod.MemoryTool(FakeCoordinator([user(typed), user(approval)]), {})
    drafted = _run(
        tool.execute(
            {
                "operation": "save",
                "text": "Lead with the next action.",
                "quote": approval,
                "writer": "assistant",
            }
        )
    )
    expected = [
        "saved m-002 — /forget m-002 to undo.",
        "  Lead with the next action.",
        f'  my wording, your go-ahead: "{approval}"',
    ]
    got = (drafted.output or "").splitlines()
    if not drafted.success or got != expected:
        problems.append(f"the writer=assistant receipt is {got!r}, not {expected!r}")
    else:
        findings.append("writer=assistant receipt byte-identical to the §3 fixture")
    problems += scan_receipt("the writer=assistant receipt", drafted.output or "")

    # Arm 3 — the batch: the LAST result carries the set, the earlier ones do not.
    batch_tool = mod.MemoryTool(FakeCoordinator([user(typed), user(approval)]), {})
    results = [
        _run(
            batch_tool.execute(
                {
                    "operation": "save",
                    "text": text,
                    "quote": approval,
                    "writer": "assistant",
                    "batch_of": 3,
                }
            )
        )
        for text in ("Number the steps.", "Cap lists at five.", "No preamble.")
    ]
    for index, result in enumerate(results[:-1], start=1):
        if len((result.output or "").splitlines()) != 3:
            problems.append(
                f"save {index} of a batch of 3 is not three lines: {result.output!r}"
            )
        elif "saved 2 memories" in (result.output or "") or "saved 3 memories" in (
            result.output or ""
        ):
            problems.append(f"save {index} of a batch of 3 carries a running summary")
    last = (results[-1].output or "").splitlines()
    expected_tail = [
        (
            f'saved 3 memories — my wording, your go-ahead: "{approval}". '
            "Reword any line and I'll replace it; /forget <id> drops one."
        ),
        "- [m-003] Number the steps.",
        "- [m-004] Cap lists at five.",
        "- [m-005] No preamble.",
    ]
    if last[3:] != expected_tail:
        problems.append(f"the last batch receipt ends {last[3:]!r}, not {expected_tail!r}")
    elif last[:3] != [
        "saved m-005 — /forget m-005 to undo.",
        "  No preamble.",
        f'  my wording, your go-ahead: "{approval}"',
    ]:
        problems.append(f"the last batch receipt does not open with its own receipt: {last[:3]!r}")
    else:
        findings.append(
            "batch of 3: the first two are their own three-line receipt, the last adds "
            "the set once"
        )

    # The store agrees with the receipts: five memories, ids m-001..m-005.
    lines = (home / "MEMORY.md").read_text(encoding="utf-8").splitlines()
    if len(lines) != 5:
        problems.append(f"MEMORY.md holds {len(lines)} lines after five saves")
    else:
        findings.append(f"MEMORY.md holds the five lines the receipts announced: {lines[0]!r} …")

    report("Core 3 (receipt)", "Broken" if problems else "Kept", "; ".join(problems or findings))
    report(
        "Core 3 (calling)",
        "Can't check",
        CANT_CHECK.format(
            n=3,
            why="whether the assistant calls the tool in the correcting turn is model "
            "behaviour, observable only in a real session (session.v2 Conformance, "
            "tests/smoke/, lane E)",
        )
        + ". What IS checkable here: the tool description carries §3's trigger phrasing "
        f"{[w for w in ('never X', 'always Y', 'stop doing Z') if w in mod.DESCRIPTION]} "
        "and no announce format at all — the receipt above is rendered by the tool, so "
        "there is nothing left for the model to restate.",
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


# ----------------------------------------------------------------------- §5


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
            findings.append("the commit carries the verbatim quote")

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
    expected = (
        "can't save that one — you haven't said it in your own words yet. "
        "Type it and I'll record it verbatim."
    )
    if refused.success:
        problems.append("a quote said only by the assistant was SAVED (poisoning arm open)")
    elif refused.output != expected:
        problems.append(f"the no-human-words refusal is {refused.output!r}, not §5's line")
    else:
        findings.append(f"assistant-only quote refused in §5's one line: {refused.output}")

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

    # Arm 4 — duplicate, cap and any-other-failure: §5's exact one-liners.
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

    (home / "MEMORY.md").write_text(
        "\n".join(f"- [m-{n:03d}] filler {n}" for n in range(1, 201)) + "\n", encoding="utf-8"
    )
    full = _run(
        mod.MemoryTool(FakeCoordinator([user("one more please")]), {}).execute(
            {"operation": "save", "text": "One more.", "quote": "one more please"}
        )
    )
    expected = (
        "not saved — MEMORY.md is full (200 of 200 lines). /forget one you no longer "
        "need, or ask me to move a group into a topic file."
    )
    if full.success or full.output != expected:
        problems.append(f"the cap refusal is {full.output!r}, not §5's line")
    else:
        findings.append(f"at the cap: {full.output}")

    log = tmp / "core5-errors.log"
    os.environ["AMPLIFIER_MEMORY_ERROR_LOG"] = str(log)
    real_save = amplifier_memory.save

    def explode(*args, **kwargs):
        raise amplifier_memory.GitFailed("commit failed: could not lock ref")

    amplifier_memory.save = explode
    try:
        broke = _run(
            mod.MemoryTool(FakeCoordinator([user("one more please")]), {}).execute(
                {"operation": "save", "text": "One more.", "quote": "one more please"}
            )
        )
    finally:
        amplifier_memory.save = real_save
        os.environ.pop("AMPLIFIER_MEMORY_ERROR_LOG", None)
    expected = f"not saved — nothing changed, nothing lost. Details: {log}"
    if broke.success or broke.output != expected:
        problems.append(f"the any-other-failure refusal is {broke.output!r}, not §5's line")
    elif not log.is_file() or "could not lock ref" not in log.read_text(encoding="utf-8"):
        problems.append("the refusal named a log the tool did not write")
    else:
        findings.append(f"any other failure: {broke.output} (and the log has the line)")

    report("Core 5", "Broken" if problems else "Kept", "; ".join(problems or findings))


# ----------------------------------------------------------------------- §6


def check_core_6(mod, tmp: Path) -> None:
    """§6 The four commands — the tool half and the skills, checkable and checked."""
    home = fresh_store(tmp, "core6")
    findings: list[str] = []
    problems: list[str] = []

    contract = CONTRACT.read_text(encoding="utf-8")
    for literal in (
        '`edited m-004 — was: "<old>"`',
        "`forgot m-002 — still in git: amplifier-memory why m-002`",
        "no memory m-004 — forgotten 2026-09-06. Current: m-003, m-005. Say the",
    ):
        if literal not in contract:
            problems.append(f"{literal!r} is not in the locked contract; the kit is out of date")

    # /remember: writes exactly what the human typed; the quote IS the text.
    typed = "Always run make check before pushing."
    refined = "Always run make check before pushing, and paste the first failure."

    def synthetic(skill: str, said: str) -> dict:
        """The prompt the CLI builds for a slash command (PINS.md, lane E)."""
        return user(
            f'Use the load_skill tool to load the skill "{skill}". '
            f"The user's input is: {said}"
        )

    tool = mod.MemoryTool(
        FakeCoordinator(
            [
                synthetic("remember", typed),
                synthetic("edit", f"m-001 {refined}"),
                synthetic("remember", "Number the steps."),
                synthetic("remember", "Cap lists at five."),
                synthetic("remember", "Two-space indent in every YAML file."),
            ]
        ),
        {},
    )
    remembered = _run(tool.execute({"operation": "save", "text": typed, "writer": "human"}))
    if not remembered.success:
        problems.append(f"/remember's save was refused: {remembered.output}")
    else:
        findings.append(f"/remember → {remembered.output.splitlines()[0]}")

    # /memory, one memory: the singular, the bullet, the hand-edit path last.
    listed = _run(tool.execute({"operation": "list"}))
    lines = (listed.output or "").splitlines()
    expected = [
        "1 memory",
        f"- [m-001] {typed}",
        f"edit by hand: $EDITOR {home / 'MEMORY.md'}",
    ]
    if lines != expected:
        problems.append(f"/memory with one memory is {lines!r}, not {expected!r}")
    else:
        findings.append("/memory with one memory: singular header, one bullet, hand-edit path")
    problems += scan_receipt("the one-memory listing", listed.output or "")

    # /edit: the id survives, the receipt shows what it was and what it now is.
    if not hasattr(mod.amplifier_memory, "edit"):
        problems.append(
            "amplifier_memory.edit is absent in this build; /edit cannot be asserted here"
        )
    else:
        edited = _run(
            tool.execute(
                {
                    "operation": "edit",
                    "id": "m-001",
                    "text": refined,
                    "writer": "human",
                }
            )
        )
        expected = [f'edited m-001 — was: "{typed}"', f"  now: {refined}"]
        got = (edited.output or "").splitlines()
        if not edited.success or got != expected:
            problems.append(f"the /edit receipt is {got!r}, not {expected!r}")
        elif (home / "MEMORY.md").read_text(encoding="utf-8").strip() != f"- [m-001] {refined}":
            problems.append("the edit did not keep the id in MEMORY.md")
        else:
            findings.append(f"/edit → {got[0]} / {got[1]} (id kept)")
        problems += scan_receipt("the /edit receipt", edited.output or "")

    # /memory, three memories and a topic file: `, N topics` only when > 0.
    for text in ("Number the steps.", "Cap lists at five."):
        _run(tool.execute({"operation": "save", "text": text, "writer": "human"}))
    listed = _run(tool.execute({"operation": "list"}))
    if (listed.output or "").splitlines()[0] != "3 memories":
        problems.append(f"/memory header is {(listed.output or '').splitlines()[:1]!r}")
    elif ", 0 topics" in (listed.output or "") or " topics" in (listed.output or ""):
        problems.append("/memory named topics when the store has none")
    else:
        findings.append(f"/memory with three memories → {(listed.output or '').splitlines()[0]}")
    topical = _run(
        tool.execute(
            {
                "operation": "save",
                "text": "Two-space indent in every YAML file.",
                "writer": "human",
                "topic": "yaml-style",
                "topic_purpose": "How to write YAML for me.",
            }
        )
    )
    if not topical.success:
        problems.append(f"the topic save was refused: {topical.output}")
    listed = _run(tool.execute({"operation": "list"}))
    if (listed.output or "").splitlines()[0] != "3 memories, 1 topic":
        problems.append(
            f"/memory with a topic file is {(listed.output or '').splitlines()[:1]!r}, "
            "not ['3 memories, 1 topic']"
        )
    else:
        findings.append(f"/memory with a topic → {(listed.output or '').splitlines()[0]}")

    # /forget: removes the line, and echoes what left, under where it still lives.
    forgotten = _run(tool.execute({"operation": "forget", "id": "m-002"}))
    got = (forgotten.output or "").splitlines()
    expected = [
        "forgot m-002 — still in git: amplifier-memory why m-002",
        "  Number the steps.",
    ]
    if not forgotten.success or got != expected:
        problems.append(f"/forget receipt is {got!r}, not {expected!r}")
    else:
        findings.append(f"/forget → {got[0]} + the removed text")
    problems += scan_receipt("the /forget receipt", forgotten.output or "")

    # An unknown id: one line, the fate, the current ids — never a guess.
    unknown = _run(tool.execute({"operation": "forget", "id": "m-002"}))
    if unknown.success or "\n" in (unknown.output or ""):
        problems.append(f"unknown id was not a one-line error: {unknown.output!r}")
    elif not unknown.output.startswith("no memory m-002 — forgotten "):
        problems.append(f"unknown id does not name the fate: {unknown.output!r}")
    elif "Current: m-001, m-003, m-004. Say the id." not in unknown.output:
        problems.append(f"unknown id does not name the current ids: {unknown.output!r}")
    else:
        findings.append(f"unknown id → {unknown.output}")

    # The four commands exist as user-invocable, model-invisible skills, and
    # carry the two rules that keep ids unguessable and receipts unrepeated.
    for name in COMMANDS:
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
        elif CITE_RULE not in body:
            problems.append(f"skills/{name}: the cite-at-use rule is missing or paraphrased")
        else:
            findings.append(
                f"skills/{name}/SKILL.md user-invocable, model-invisible, all three rules"
            )

    # The new command is registered where a reader looks for it.
    for path in (BEHAVIOR, BUNDLE):
        if "/edit" not in path.read_text(encoding="utf-8"):
            problems.append(f"{path.name} does not register /edit")
    if not problems:
        findings.append("/edit registered in behaviors/memory-session.yaml and bundle.md")

    # The v1 receipts, and the false line, in every file that could carry them.
    for path in [*sorted(SKILLS_DIR.glob("*/SKILL.md")), MODULE_SOURCE]:
        body = path.read_text(encoding="utf-8")
        stale = [bad for bad in STALE_IN_SOURCE if bad in body]
        if stale:
            problems.append(f"{path.name} still carries {stale}")
        said = [
            c
            for c in ("can't write these", "cannot write these", "you type them")
            if c in body.lower()
        ]
        if said:
            problems.append(f"{path.name} still claims the assistant cannot save: {said}")

    report("Core 6", "Broken" if problems else "Kept", "; ".join(problems or findings))


# ------------------------------------------------------------- store.v2 §5


def check_store_5(mod, tmp: Path) -> None:
    """store.v2 §5: a ruleset reaches a topic file, and leaves ONE pointer line."""
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

    report("store.v2 Core 5", "Broken" if problems else "Kept", "; ".join(problems or findings))


# ------------------------------------------------------------------- §7, §8


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


def check_core_8(mod, tmp: Path) -> None:
    """§8 Cite at use — the counting is here (checked); the citing is not."""
    import json

    home = fresh_store(tmp, "core8")
    findings: list[str] = []
    problems: list[str] = []

    if not hasattr(mod.amplifier_memory, "record_citation"):
        problems.append(
            "amplifier_memory.record_citation is absent in this build; §8's instrument "
            "cannot be asserted here"
        )
    else:
        said = "Always cite the memory you acted on."
        tool = mod.MemoryTool(FakeCoordinator([user(said)]), {})
        seeded = _run(tool.execute({"operation": "save", "text": said, "writer": "human"}))
        if not seeded.success:
            problems.append(f"the memory to cite could not be saved: {seeded.output}")
        cited = _run(tool.execute({"operation": "cite", "id": "m-001"}))
        if not cited.success:
            problems.append(f"cite of a real id was refused: {cited.output!r}")
        elif (cited.output or "") != "":
            problems.append(f"cite spoke to the human: {cited.output!r}")
        else:
            findings.append("cite returns nothing the human reads")
        events = [
            json.loads(line)
            for line in (home / "usage.jsonl").read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]
        recorded = [e for e in events if e.get("event") == "cited"]
        if not recorded:
            problems.append(f"no `cited` event in usage.jsonl: {events!r}")
        elif recorded[-1].get("target") != "m-001":
            problems.append(f"the `cited` event names {recorded[-1].get('target')!r}")
        else:
            findings.append(f"usage.jsonl gained {recorded[-1]}")

        unknown = _run(tool.execute({"operation": "cite", "id": "m-404"}))
        if unknown.success or "no memory m-404" not in (unknown.output or ""):
            problems.append(f"cite of an unknown id was not §6's one line: {unknown.output!r}")
        else:
            findings.append(f"cite of an unknown id → {unknown.output}")

    if CITE_RULE not in mod.DESCRIPTION:
        problems.append("the tool description does not tell the model to cite")
    else:
        findings.append("the description tells the model to write `per m-NNN` and call cite")

    report("Core 8 (counting)", "Broken" if problems else "Kept", "; ".join(problems or findings))
    report(
        "Core 8 (citing)",
        "Can't check",
        CANT_CHECK.format(
            n=8,
            why="naming a memory inline when it shapes an action ('per m-004') is model "
            "behaviour in a real session; nothing in this process can observe it",
        )
        + ". What IS checkable here: the instrument that counts it exists and works "
        "(Core 8 (counting), above), and every id the model would cite is present in what "
        "the tool returns — `list` renders each line as '- [m-NNN] <text>' and `save` "
        "announces the new id.",
    )


# ------------------------------------------------------------------------ R2


def check_r2(mod, tmp: Path) -> None:
    """R2 Sub-agents never write."""
    import amplifier_memory

    fresh_store(tmp, "r2")
    findings: list[str] = []
    problems: list[str] = []

    def explode(*args, **kwargs):
        raise AssertionError("library reached in a sub-agent session")

    real = (amplifier_memory.save, amplifier_memory.forget, amplifier_memory.edit)
    amplifier_memory.save = explode
    amplifier_memory.forget = explode
    amplifier_memory.edit = explode
    try:
        sub = mod.MemoryTool(
            FakeCoordinator([user("never use emoji")], parent_id="parent-session"), {}
        )
        saved = _run(
            sub.execute(
                {"operation": "save", "text": "Never use emoji.", "quote": "never use emoji"}
            )
        )
        edited = _run(
            sub.execute(
                {
                    "operation": "edit",
                    "id": "m-001",
                    "text": "Never use emoji anywhere.",
                    "quote": "never use emoji",
                }
            )
        )
        forgot = _run(sub.execute({"operation": "forget", "id": "m-001"}))
    finally:
        amplifier_memory.save, amplifier_memory.forget, amplifier_memory.edit = real

    for label, result in (("save", saved), ("edit", edited), ("forget", forgot)):
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

    if not CONTRACT.is_file():
        print(f"contract not found: {CONTRACT}", file=sys.stderr)
        return 2

    with tempfile.TemporaryDirectory() as raw:
        tmp = Path(raw)
        os.environ["AMPLIFIER_PROJECTS_HOME"] = str(tmp / "projects")
        check_core_3(mod, tmp)
        check_core_4(mod)
        check_core_5(mod, tmp)
        check_core_6(mod, tmp)
        check_store_5(mod, tmp)
        check_core_7(mod)
        check_core_8(mod, tmp)
        check_r2(mod, tmp)
    return 0


if __name__ == "__main__":
    sys.exit(main())
