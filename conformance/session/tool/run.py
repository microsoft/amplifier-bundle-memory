#!/usr/bin/env python3
"""Conformance kit — session.v5 §3–§8 and R2, as served by tool-memory.

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
CONTRACT = REPO_ROOT / "contracts" / "session.v5.md"
SKILLS_DIR = REPO_ROOT / "skills"
BEHAVIOR = REPO_ROOT / "behaviors" / "memory-session.yaml"
BUNDLE = REPO_ROOT / "bundle.md"

sys.path.insert(0, str(MODULE_DIR))

CANT_CHECK = "session.v5 Core {n} — Can't check in this lane because {why}"

#: session.v5 §6: "Two, and only two, user-invocable skills ship with the bundle."
#: `/remember <text>` writes what the human typed; `/memory` is everything else,
#: by its first word.
COMMANDS = ("remember", "memory")
#: The rules a command's skill carries, each quoted from §6 rather than
#: paraphrased — a paraphrase is a different rule. `RELAY_RULE` replaced v2's
#: no-restate sentence, which asserted what the human could see of a tool call:
#: v3 states the rule only as relay-verbatim-never-reword (Conformance, Part A of
#: `session.v2.v3-candidate.md`).
REMEMBER_IDS_RULE = "Ids are the only names"
MEMORY_IDS_RULE = "Outside conversational review addressing from the actual displayed review page"
NATURAL_REVIEW_RULES = (
    "Conversational addressing from a displayed page.",
    "resolve the **complete** requested",
    "batch first and freeze its action-to-id map",
    '"yes" approves that exact map',
    "do not list again between calls",
    "substitute another item",
    "direct tool, shell, or slash",
)
RELAY_RULE = "relayed verbatim and never reworded"
#: How the relay stays verbatim once it leaves the tool: the steward's transcript
#: of 2026-09-07 (session 628cc503) shows the four §6 lines relayed as one folded
#: paragraph with `<id>` and `<text>` gone — markdown treated them as tags. A
#: fenced code block keeps the bytes, the line breaks and the angle brackets.
FENCE_RULE = "fenced code block"
#: §6's first-word dispatch, as a human meets it.
FIRST_WORDS = ("list", "review", "forget", "edit", "remember", "help")

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


def contract_text() -> str:
    """The locked contract as one flat line.

    A receipt the contract prints across two wrapped lines is the same receipt;
    comparing against the file's raw bytes would report "the kit is out of date"
    for a line break in prose. Both sides are flattened before comparing.
    """
    return " ".join(CONTRACT.read_text(encoding="utf-8").split())


def quoted(literal: str) -> str:
    return " ".join(literal.split())


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
    os.environ["AMPLIFIER_SESSION_ORIGIN"] = "human"
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

    contract = contract_text()
    for literal in (
        "saved m-017 — /memory forget m-017 to undo.",
        "your words, verbatim",
        'my wording, your go-ahead: "<the quote>"',
    ):
        if quoted(literal) not in contract:
            problems.append(f"{literal!r} is not in the locked contract; the kit is out of date")

    # Arm 1 — the human's own words. Three lines, byte for byte.
    typed = "Never use tabs in YAML files you write for me."
    human = _run(
        mod.MemoryTool(FakeCoordinator([user(typed)]), {}).execute(
            {"operation": "save", "text": typed, "writer": "human"}
        )
    )
    expected = [
        "saved m-001 — /memory forget m-001 to undo.",
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
        "saved m-002 — /memory forget m-002 to undo.",
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
            problems.append(f"save {index} of a batch of 3 is not three lines: {result.output!r}")
        elif "saved 2 memories" in (result.output or "") or "saved 3 memories" in (
            result.output or ""
        ):
            problems.append(f"save {index} of a batch of 3 carries a running summary")
    last = (results[-1].output or "").splitlines()
    expected_tail = [
        (
            f'saved 3 memories — my wording, your go-ahead: "{approval}". '
            "Reword any line and I'll replace it; /memory forget <id> drops one."
        ),
        "- [m-003] Number the steps.",
        "- [m-004] Cap lists at five.",
        "- [m-005] No preamble.",
    ]
    if last[3:] != expected_tail:
        problems.append(f"the last batch receipt ends {last[3:]!r}, not {expected_tail!r}")
    elif last[:3] != [
        "saved m-005 — /memory forget m-005 to undo.",
        "  No preamble.",
        f'  my wording, your go-ahead: "{approval}"',
    ]:
        problems.append(f"the last batch receipt does not open with its own receipt: {last[:3]!r}")
    else:
        findings.append(
            "batch of 3: the first two are their own three-line receipt, the last adds the set once"
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
            "behaviour, observable only in a real session (session.v5 Conformance, "
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
        "not saved — MEMORY.md is full (200 of 200 lines). /memory forget one you no "
        "longer need, or ask me to move a group into a topic file."
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

    contract = contract_text()
    for literal in (
        '`edited m-004 — was: "<old>"`',
        "`forgot m-002 — still in git: amplifier-memory why m-002`",
        "no memory m-004 — forgotten 2026-09-06. Current: m-003, m-005. Say the",
        "`34 suggestions waiting. /memory review to walk them.`",
        "`/memory list · review · forget <id> · edit <id> <text> · help`",
        # §6 as amended 2026-09-07 — the paged markdown surface, in its own words.
        "a bold header `**N memories**`",
        "one line per memory as `- **m-NNN** <text>`",
        "`— page P of Q` only when paged",
        "17 items are 6 · 6 · 5, 13 are 5 · 4 · 4, 9 are 5 · 4, never 6 · 6 · 6 · 1",
        "`list` and `review` pages bare",
    ):
        if quoted(literal) not in contract:
            problems.append(f"{literal!r} is not in the locked contract; the kit is out of date")

    # /remember: writes exactly what the human typed; the quote IS the text.
    typed = "Always run make check before pushing."
    refined = "Always run make check before pushing, and paste the first failure."

    def synthetic(skill: str, said: str) -> dict:
        """The prompt the CLI builds for a slash command (PINS.md, lane E)."""
        return user(
            f'Use the load_skill tool to load the skill "{skill}". The user\'s input is: {said}'
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

    # /memory list, one memory: the singular, the bullet, the hand-edit path last.
    # §6 as amended 2026-09-07 renders it as markdown, in the library.
    listed = _run(tool.execute({"operation": "list"}))
    lines = (listed.output or "").splitlines()
    expected = [
        "**1 memory**",
        f"- **m-001** {typed}",
        f"edit by hand: $EDITOR {home / 'MEMORY.md'}",
    ]
    if lines != expected:
        problems.append(f"/memory list with one memory is {lines!r}, not {expected!r}")
    else:
        findings.append("/memory list with one memory: singular header, one bullet, path")
    problems += scan_receipt("the one-memory listing", listed.output or "")

    # /memory edit: the id survives, the receipt shows what it was and what it now is.
    if not hasattr(mod.amplifier_memory, "edit"):
        problems.append(
            "amplifier_memory.edit is absent in this build; edit cannot be asserted here"
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
            problems.append(f"the edit receipt is {got!r}, not {expected!r}")
        elif (home / "MEMORY.md").read_text(encoding="utf-8").strip() != f"- [m-001] {refined}":
            problems.append("the edit did not keep the id in MEMORY.md")
        else:
            findings.append(f"/memory edit → {got[0]} / {got[1]} (id kept)")
        problems += scan_receipt("the edit receipt", edited.output or "")

    # /memory list, three memories and a topic file: `, N topics` only when > 0.
    for text in ("Number the steps.", "Cap lists at five."):
        _run(tool.execute({"operation": "save", "text": text, "writer": "human"}))
    listed = _run(tool.execute({"operation": "list"}))
    if (listed.output or "").splitlines()[0] != "**3 memories**":
        problems.append(f"/memory list header is {(listed.output or '').splitlines()[:1]!r}")
    elif ", 0 topics" in (listed.output or "") or " topics" in (listed.output or ""):
        problems.append("/memory list named topics when the store has none")
    else:
        findings.append(
            f"/memory list with three memories → {(listed.output or '').splitlines()[0]}"
        )
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
    if (listed.output or "").splitlines()[0] != "**3 memories, 1 topic**":
        problems.append(
            f"/memory list with a topic file is {(listed.output or '').splitlines()[:1]!r}, "
            "not ['**3 memories, 1 topic**']"
        )
    else:
        findings.append(f"/memory list with a topic → {(listed.output or '').splitlines()[0]}")

    # /memory forget: removes the line, and echoes what left, under where it still lives.
    forgotten = _run(tool.execute({"operation": "forget", "id": "m-002"}))
    got = (forgotten.output or "").splitlines()
    expected = [
        "forgot m-002 — still in git: amplifier-memory why m-002",
        "  Number the steps.",
    ]
    if not forgotten.success or got != expected:
        problems.append(f"the forget receipt is {got!r}, not {expected!r}")
    else:
        findings.append(f"/memory forget → {got[0]} + the removed text")
    problems += scan_receipt("the forget receipt", forgotten.output or "")

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

    # §6: TWO user-invocable, model-invisible skills — and no third. `/memory`
    # carries the first-word dispatch that used to be three separate commands.
    shipped = sorted(path.parent.name for path in SKILLS_DIR.glob("*/SKILL.md"))
    if shipped != sorted(COMMANDS):
        problems.append(f"skills/ ships {shipped}, not §6's two: {sorted(COMMANDS)}")
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
        elif name == "remember" and REMEMBER_IDS_RULE not in body:
            problems.append(f"skills/{name}: the non-review ids rule is missing or paraphrased")
        elif name == "memory" and MEMORY_IDS_RULE not in body:
            problems.append(f"skills/{name}: the scoped review ids rule is missing or paraphrased")
        elif RELAY_RULE not in body:
            problems.append(f"skills/{name}: the relay-verbatim rule is missing or paraphrased")
        elif FENCE_RULE not in body:
            problems.append(f"skills/{name}: the relay is not told to use a fenced code block")
        else:
            findings.append(
                f"skills/{name}/SKILL.md user-invocable, model-invisible, all three rules"
            )

    # §6's first words all reach a human somewhere they will look: the /memory
    # skill is where the dispatch lives.
    memory_skill = SKILLS_DIR / "memory" / "SKILL.md"
    if memory_skill.is_file():
        body = memory_skill.read_text(encoding="utf-8")
        undocumented = [word for word in FIRST_WORDS if f"/memory {word}" not in body]
        if undocumented:
            problems.append(f"skills/memory/SKILL.md does not document {undocumented}")
        else:
            findings.append(f"skills/memory/SKILL.md documents every first word {FIRST_WORDS}")
        missing_review_rules = [rule for rule in NATURAL_REVIEW_RULES if rule not in body]
        if missing_review_rules:
            problems.append(
                "skills/memory/SKILL.md is missing natural-review safeguards "
                f"{missing_review_rules!r}"
            )
        else:
            findings.append(
                "skills/memory/SKILL.md scopes natural references to a displayed page, "
                "freezes batches, preserves stale-id refusal, and keeps direct APIs id-only"
            )

    # The commands are registered where a reader looks for them.
    for path in (BEHAVIOR, BUNDLE):
        body = path.read_text(encoding="utf-8")
        missing = [command for command in ("/remember", "/memory") if command not in body]
        if missing:
            problems.append(f"{path.name} does not register {missing}")
    if not problems:
        findings.append("/remember and /memory registered in the behavior and bundle.md")

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


def check_core_6_overview(mod, tmp: Path) -> None:
    """§6's bare `/memory`: at most four lines, suggestions first, status's figures.

    Its own store, because the figures are the point: six saves, two forgets and
    two citations make a store whose numbers are known, and any leftover from
    another check would be a number this kit cannot vouch for.
    """
    import amplifier_memory

    home = fresh_store(tmp, "core6-overview")
    findings: list[str] = []
    problems: list[str] = []

    contract = contract_text()
    for literal in (
        "`34 suggestions waiting. /memory review to walk them.`",
        # §6 fixes the singular as `1 suggestion`; the rest of the line is the
        # plural's, with `them` → `it` (work item amplifier_bundle_memory-nyh).
        "singular `1 suggestion`",
        "`/memory list · review · forget <id> · edit <id> <text> · help`",
    ):
        if quoted(literal) not in contract:
            problems.append(f"{literal!r} is not in the locked contract; the kit is out of date")

    # §6's bare `/memory`: at most four lines, suggestions first, every figure the
    # one `amplifier-memory status` prints. Six saves, two forgets and two
    # citations make a store whose numbers are known without counting anything
    # twice; the inbox is written in suggestions.v2 §4's own two-line shape.
    overview_tool = mod.MemoryTool(
        FakeCoordinator([user(f"Preference {n}.") for n in range(1, 7)]), {}
    )
    for n in range(1, 7):
        _run(
            overview_tool.execute(
                {"operation": "save", "text": f"Preference {n}.", "writer": "human"}
            )
        )
    for mid in ("m-005", "m-006"):
        _run(overview_tool.execute({"operation": "forget", "id": mid}))
    for mid in ("m-001", "m-002"):
        _run(overview_tool.execute({"operation": "cite", "id": mid}))

    empty_inbox = _run(overview_tool.execute({"operation": "overview"}))
    (home / "inbox.md").write_text(
        "".join(
            f"- [s-{n:03d}] preference number {n}\n"
            f'  quote: "say it {n}"  session: bc214bdf  2026-09-05\n'
            for n in range(1, 35)
        ),
        encoding="utf-8",
    )
    full_inbox = _run(overview_tool.execute({"operation": "overview"}))
    expected = [
        "34 suggestions waiting. /memory review to walk them.",
        "4 memories. /memory list to see them.",
        "last 7 days: 6 written, 2 forgotten, 2 cited.",
        "/memory list · review · forget <id> · edit <id> <text> · help",
    ]
    got = (full_inbox.output or "").splitlines()
    if got != expected:
        problems.append(f"the bare /memory overview is {got!r}, not {expected!r}")
    else:
        findings.append(f"bare /memory → {got[0]} … ({len(got)} lines, suggestions first)")
    problems += scan_receipt("the overview", full_inbox.output or "")

    empty = (empty_inbox.output or "").splitlines()
    if len(empty) != 3 or "review" in (empty_inbox.output or ""):
        problems.append(f"with an empty inbox the overview is {empty!r}")
    else:
        findings.append("empty inbox: no suggestions line, no `review` in the command line")

    (home / "inbox.md").write_text(
        '- [s-001] preference number 1\n  quote: "say it 1"  session: bc214bdf  2026-09-05\n',
        encoding="utf-8",
    )
    one = _run(overview_tool.execute({"operation": "overview"})).output or ""
    if one.splitlines()[0] != "1 suggestion waiting. /memory review to walk it.":
        problems.append(f"with one waiting item the overview opens {one.splitlines()[:1]!r}")
    else:
        findings.append(f"one waiting item → {one.splitlines()[0]}")

    # The figures are `status`'s own, not a second count (AGENTS.md rule 11).
    report_now = amplifier_memory.status()
    if (report_now.memories, report_now.topics) != (4, 0) or (
        report_now.written_7,
        report_now.forgotten_7,
        report_now.cited_7,
    ) != (6, 2, 2):
        problems.append(f"the overview and status disagree: {report_now}")
    else:
        findings.append("every figure in the overview is the one `amplifier-memory status` reads")

    report("Core 6 (overview)", "Broken" if problems else "Kept", "; ".join(problems or findings))


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
            problems.append(f"cite rendered a receipt: {cited.output!r}")
        else:
            findings.append("cite returns an empty result — no receipt to relay")
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

    # §11 moved the cite instruction out of the description: it is not one of the
    # six things a model needs on EVERY turn, and the skills teach it on demand.
    # What must still be true here is that the operation exists and is named in
    # the parameter text the model reads when it calls the tool.
    operations = mod.INPUT_SCHEMA["properties"]["operation"]["enum"]
    if "cite" not in operations:
        problems.append(f"the tool has no `cite` operation: {operations}")
    elif "cite" in mod.DESCRIPTION:
        problems.append(
            "the description still teaches citing; §11 gives the description six "
            "teachings and this is not one of them"
        )
    else:
        findings.append(f"`cite` is an operation ({operations}) and not a description paragraph")

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
        "the tool returns — `list` renders each line as '- **m-NNN** <text>' and `save` "
        "announces the new id.",
    )


# --------------------------------------------------------- suggestions.v2 §6

REVIEW_FIXTURES = MODULE_DIR / "tests" / "fixtures" / "review-lines.txt"


def review_fixtures() -> dict[str, str]:
    """The exact bytes `review` renders, one block per case.

    The same file the module's own tests compare against, read here so the kit
    and the suite can never disagree about what the human is supposed to see.
    """
    cases: dict[str, list[str]] = {}
    current: str | None = None
    for line in REVIEW_FIXTURES.read_text(encoding="utf-8").splitlines():
        if line.startswith("## "):
            current = line[3:].strip()
            cases[current] = []
        elif current is not None:
            cases[current].append(line)
    return {key: "\n".join(body) for key, body in cases.items()}


class FakeSuggestion:
    def __init__(self, sid, text, quote, session, date):
        self.id = sid
        self.text = text
        self.quote = quote
        self.session = session
        self.date = date


class FakeSaveResult:
    def __init__(self, mid, text, target="MEMORY.md"):
        self.id = mid
        self.text = text
        self.target = target


class FakeInbox:
    """`amplifier_memory.inbox`, at lane P's published signatures.

    `pending(home) -> list[Suggestion]` · `accept(sid, home, *, session_id)` ·
    `decline(sid, home)` · `skip(sid, home)`. The stand-in is what lets §6's
    surface be measured before the library lands; what it cannot prove is said
    in the verdict rather than folded into it.
    """

    def __init__(self, items):
        self.items = list(items)
        self.calls: list[tuple] = []

    def pending(self, home):
        self.calls.append(("pending", str(home)))
        return list(self.items)

    def render_review_page(self, page=1, home=None):
        """The seam the tool calls for a page — deliberately NOT a rendering.

        Every page in this kit is rendered by the real library from a real inbox
        (`check_the_pages`); this stand-in exists only so the R2 arm can prove a
        *read* was allowed, and returns a marker no fixture will ever match.
        """
        self.calls.append(("render_review_page", page, str(home)))
        return f"<{len(self.items)} waiting>"

    def accept(self, sid, home, *, session_id):
        self.calls.append(("accept", sid, str(home), session_id))
        item = next(s for s in self.items if s.id == sid)
        self.items = [s for s in self.items if s.id != sid]
        return FakeSaveResult("m-001", item.text)

    def decline(self, sid, home):
        self.calls.append(("decline", sid, str(home)))
        self.items = [s for s in self.items if s.id != sid]

    def skip(self, sid, home):
        self.calls.append(("skip", sid, str(home)))


WAITING = [
    FakeSuggestion(
        "s-042",
        "never use tabs in YAML; two-space indentation",
        "never use tabs in YAML files I ask you to write…",
        "bc214bdf",
        "2026-09-05",
    ),
    FakeSuggestion(
        "s-043",
        "Lead with the next action.",
        "lead with the next action, always",
        "9f31ab07",
        "2026-09-06",
    ),
    FakeSuggestion(
        "s-044",
        "Cap lists at five items.",
        "cap your lists at five items",
        "9f31ab07",
        "2026-09-06",
    ),
]


# §6 as amended 2026-09-07 — the seeded inbox the pages are rendered from. The same
# spelling `modules/tool-memory/tests/test_tool_memory.py` and `tests/test_inbox.py`
# use; the shared fixture file is what keeps the three identical.
SEED_SESSION = "d9c3bf04"
SEED_DATE = "2026-09-07"


def seeded_inbox(home: Path, n: int):
    """`n` real items in a real `inbox.md`, appended through the library's own `append`."""
    import amplifier_memory

    return amplifier_memory.inbox.append(
        home,
        [
            amplifier_memory.inbox.Candidate(
                text=f"Preference {i:02d}: one standing line the daily pass proposed.",
                quote=(
                    f"for future reference, preference {i:02d}: always do it this way, "
                    "in every session on this device, not just in this one"
                ),
                session=SEED_SESSION,
                date=SEED_DATE,
            )
            for i in range(1, n + 1)
        ],
    )


def check_the_pages(mod, tmp: Path, fixtures: dict[str, str], findings: list[str]) -> list[str]:
    """§6's paged markdown, rendered by the LIBRARY from a real inbox on disk.

    Nothing here is a stand-in: `render_review_page` parses `inbox.md` back off the
    disk, so the quote in the page is the quote the file carries or the comparison
    fails. That is the whole point — a page fixture that passed because a fake was
    handed pre-rendered text would prove nothing about what a human reads.
    """
    problems: list[str] = []
    home = fresh_store(tmp, "pages17")
    written = seeded_inbox(home, 17)
    tool = mod.MemoryTool(FakeCoordinator([]), {})

    for label, payload, key in (
        ("page omitted (17 waiting)", {}, "page_one_of_seventeen"),
        ("explicit list (17 waiting)", {"action": "list"}, "page_one_of_seventeen"),
        ("explicit list page 3 of 17", {"action": "list", "page": 3}, "page_three_of_seventeen"),
    ):
        got = _run(tool.execute({"operation": "review", **payload}))
        if not got.success or (got.output or "") != fixtures[key]:
            problems.append(f"{label} is {got.output!r}, not the fixture {key}")
        else:
            findings.append(f"{label}: byte-identical to fixtures/{key}")

    # The quote is the whole trust story of a suggestion: printed whole, or the page
    # is a line accepted on the strength of an ellipsis.
    page = (_run(tool.execute({"operation": "review"})).output or "").splitlines()
    quoted = [line[2:].strip('"') for line in page if line.startswith('> "')]
    if quoted != [item.quote for item in written[:6]]:
        problems.append(f"the page's quotes are not inbox.md's: {quoted!r}")
    else:
        findings.append(f"6 quotes on page 1, each byte-identical to inbox.md ({len(quoted[0])}c)")

    # A page past the last one: one line, naming the last page, nothing written.
    before = (home / "inbox.md").read_bytes()
    beyond = _run(tool.execute({"operation": "review", "page": 4}))
    if beyond.success or (beyond.output or "") != fixtures["page_beyond"]:
        problems.append(f"page 4 of 3 answered {beyond.output!r}")
    elif (home / "inbox.md").read_bytes() != before:
        problems.append("a refused page changed inbox.md")
    else:
        findings.append(f"page 4 of 3 -> {beyond.output}")

    # §6: ids are the only names. A bare number is a position and is refused with
    # the ids the page holds — and writes nothing.
    position = _run(tool.execute({"operation": "review", "action": "accept", "id": "2"}))
    if position.success or (position.output or "") != fixtures["position"]:
        problems.append(f"`accept 2` answered {position.output!r}, not fixtures/position")
    elif (home / "inbox.md").read_bytes() != before:
        problems.append("`accept 2` changed inbox.md")
    elif (home / "MEMORY.md").read_text(encoding="utf-8").strip():
        problems.append("`accept 2` wrote a memory")
    else:
        findings.append(f"`accept 2` -> {position.output}")

    # An action without its required id is an argument refusal, never an implied
    # listing. All three store files and the commit remain exactly where they were.
    from amplifier_memory import _git

    before_files = {
        name: (home / name).read_bytes() for name in ("MEMORY.md", "inbox.md", "declined.md")
    }
    before_head = _git.head(home)
    missing_id = [
        _run(tool.execute({"operation": "review", "action": action, "id": ""}))
        for action in ("accept", "decline", "skip")
    ]
    expected_missing = [
        f"refused: review {action} needs the suggestion id, e.g. s-042"
        for action in ("accept", "decline", "skip")
    ]
    if [result.output for result in missing_id] != expected_missing or any(
        result.success for result in missing_id
    ):
        problems.append(f"missing-id review actions did not refuse exactly: {missing_id!r}")
    elif {name: (home / name).read_bytes() for name in before_files} != before_files:
        problems.append("a missing-id review action changed a store file")
    elif _git.head(home) != before_head:
        problems.append("a missing-id review action changed git HEAD")
    else:
        findings.append(
            "missing-id accept, decline and skip refuse; MEMORY.md, inbox.md, declined.md and HEAD unchanged"
        )

    corrected = _run(tool.execute({"operation": "review", "action": "list", "page": 3}))
    if not corrected.success or (corrected.output or "") != fixtures["page_three_of_seventeen"]:
        problems.append(
            f"the deterministic missing-id correction did not render page 3: {corrected.output!r}"
        )
    else:
        findings.append(
            "deterministic missing-id correction: explicit list preserves page 3 (not evidence a model chose it)"
        )

    # Two ids are two calls, each with its own §6 receipt (the skill makes them).
    receipts = [
        _run(tool.execute({"operation": "review", "action": "accept", "id": sid}))
        for sid in ("s-001", "s-002")
    ]
    saved = [r.output.splitlines()[0] for r in receipts if r.success]
    if len(saved) != 2 or saved != [
        "saved m-001 \u2014 /memory forget m-001 to undo.",
        "saved m-002 \u2014 /memory forget m-002 to undo.",
    ]:
        problems.append(f"two ids did not produce two receipts: {[r.output for r in receipts]!r}")
    else:
        findings.append(f"two ids -> two calls, two receipts: {saved}")

    # Up to 8 is one page, and a `— page 1 of 1` suffix is never printed.
    eight = fresh_store(tmp, "pages8")
    seeded_inbox(eight, 8)
    tool = mod.MemoryTool(FakeCoordinator([]), {})
    got = _run(tool.execute({"operation": "review", "action": "list"}))
    if not got.success or (got.output or "") != fixtures["page_of_eight"]:
        problems.append(f"8 waiting is {got.output!r}, not the fixture page_of_eight")
    else:
        findings.append("8 waiting: one page, no page suffix (fixtures/page_of_eight)")

    fresh_store(tmp, "suggestions6")
    return problems


def check_suggestions_6(mod, tmp: Path) -> None:
    """suggestions.v2 §6 Review is one keystroke per item."""
    import amplifier_memory

    fresh_store(tmp, "suggestions6")
    fixtures = review_fixtures()
    findings: list[str] = []
    problems: list[str] = []

    had_real = hasattr(amplifier_memory, "inbox")
    real = getattr(amplifier_memory, "inbox", None)
    action_schema = mod.INPUT_SCHEMA["properties"]["action"]
    if action_schema.get("enum") != ["list", "accept", "decline", "skip"]:
        problems.append(
            f"review action enum is {action_schema.get('enum')!r}, not explicit list plus three actions"
        )
    elif mod.INPUT_SCHEMA.get("required") != ["operation"]:
        problems.append(
            f"review schema required is {mod.INPUT_SCHEMA.get('required')!r}, not ['operation']"
        )
    else:
        findings.append(
            "strict-shaped schema admits action=list while only operation remains required"
        )

    def review(inbox, **payload):
        if inbox is None:
            if hasattr(amplifier_memory, "inbox"):
                del amplifier_memory.inbox
        else:
            amplifier_memory.inbox = inbox
        tool = mod.MemoryTool(FakeCoordinator([]), {})
        return _run(tool.execute({"operation": "review", **payload}))

    try:
        # The PAGES — §6 as amended 2026-09-07. Rendered by the library from a REAL
        # temp inbox, appended through `inbox.append`, and compared byte for byte
        # against the shared fixture file. A stand-in is deliberately not used here:
        # a page that passes because a fake was fed pre-rendered text proves nothing
        # about what the human will read.
        if had_real:
            problems += check_the_pages(mod, tmp, fixtures, findings)
        else:
            findings.append(
                "the pages could not be rendered: amplifier_memory.inbox is not in this build"
            )
        # The empty inbox: one line, and no zero-valued count. Real store, real
        # library — `fresh_store` above left `suggestions6` with an empty inbox.
        got = (
            _run(
                mod.MemoryTool(FakeCoordinator([]), {}).execute(
                    {"operation": "review", "action": "list"}
                )
            )
            if had_real
            else review(FakeInbox([]), action="list")
        )
        if not got.success or (got.output or "") != fixtures["listing_none"]:
            problems.append(f"an empty inbox answered {got.output!r}, not fixtures/listing_none")
        else:
            findings.append("none waiting: byte-identical to fixtures/listing_none")

        # accept · decline · skip — session.v5 §3's shapes, §6's words.
        inbox = FakeInbox(WAITING)
        accepted = review(inbox, action="accept", id="s-042")
        if not accepted.success or (accepted.output or "") != fixtures["accept"]:
            problems.append(f"the accept receipt is {accepted.output!r}")
        elif ("accept", "s-042", str(amplifier_memory.store_home()), "conformance-session") not in (
            inbox.calls
        ):
            problems.append(f"accept did not reach the library with the session: {inbox.calls}")
        else:
            findings.append(
                "accept → session.v5 §3's three lines, third line "
                f"{accepted.output.splitlines()[2]!r}, written by the library with this "
                "session's id"
            )

        for action, key in (("decline", "decline"), ("skip", "skip")):
            inbox = FakeInbox(WAITING)
            got = review(inbox, action=action, id="s-042")
            if not got.success or (got.output or "") != fixtures[key]:
                problems.append(f"the {action} receipt is {got.output!r}, not fixtures/{key}")
            elif (action, "s-042", str(amplifier_memory.store_home())) not in inbox.calls:
                problems.append(f"{action} did not reach the library: {inbox.calls}")
            else:
                findings.append(f"{action} → {got.output!r}")

        # An id that is not waiting, and a build with no inbox at all.
        unknown = review(FakeInbox(WAITING), action="accept", id="s-999")
        if unknown.success or (unknown.output or "") != fixtures["unknown"]:
            problems.append(f"an unknown id answered {unknown.output!r}")
        else:
            findings.append(f"unknown id → {unknown.output}")
        missing = review(None, action="list")
        if missing.success or (missing.output or "") != fixtures["unavailable"]:
            problems.append(f"with no inbox the tool answered {missing.output!r}")
        else:
            findings.append(f"no inbox in the build → {missing.output}")

        # R2: a sub-agent reads the inbox and never writes to it.
        sub = mod.MemoryTool(FakeCoordinator([], parent_id="parent-session"), {})
        amplifier_memory.inbox = FakeInbox(WAITING)
        refused = [
            _run(sub.execute({"operation": "review", "action": action, "id": "s-042"}))
            for action in ("accept", "decline")
        ]
        listed = _run(sub.execute({"operation": "review", "action": "list"}))
        if any(r.success or "R2" not in (r.output or "") for r in refused):
            problems.append(f"a sub-agent was allowed to write: {[r.output for r in refused]}")
        elif not listed.success:
            problems.append(f"a sub-agent could not read the inbox: {listed.output!r}")
        else:
            findings.append("R2: a sub-agent may list the inbox and may not accept or decline")
    finally:
        if had_real:
            amplifier_memory.inbox = real
        elif hasattr(amplifier_memory, "inbox"):
            del amplifier_memory.inbox

    # The walk exists where a human and a model look for it: §6 puts `review`
    # behind `/memory`'s first word, and the procedure in the skill (§11).
    skill = (SKILLS_DIR / "memory" / "SKILL.md").read_text(encoding="utf-8")
    for needle in (
        "/memory review",
        'action="list"',
        'action="accept"',
        'action="decline"',
        'action="skip"',
        "Exactly once, correct a first call",
        "the original request was `review` or `review <page>`",
        "Preserve the requested page",
        "A second failure is terminal.",
        "Never use this correction for a user-requested `accept`, `decline`, or `skip`",
        "or inspect files to route around a refusal.",
    ):
        if needle not in skill:
            problems.append(f"skills/memory/SKILL.md does not document {needle!r}")
    if RELAY_RULE not in skill:
        problems.append("skills/memory/SKILL.md: the relay-verbatim rule is missing or paraphrased")

    # §6 as amended 2026-09-07: the fence is scoped. The overview and every receipt
    # go inside one (their `<id>` placeholders and line breaks do not survive markdown
    # outside one); a `list` or `review` page goes BARE, because it IS markdown and a
    # fence would refuse to wrap it — which is the wall the amendment removed.
    scoping = {
        "the fence around the overview and the receipts": (
            "The overview and every receipt go inside a fenced code block"
        ),
        "a page relayed bare": "A `list` page and a `review` page go bare",
        "`next` is page + 1": "`next` is this call again with `page + 1`",
        "several ids are several calls": "Several stable ids in one breath are several calls",
    }
    for label, needle in scoping.items():
        if needle not in skill:
            problems.append(f"skills/memory/SKILL.md does not say {label}: {needle!r} is absent")
    if not [label for label, needle in scoping.items() if needle not in skill]:
        findings.append(f"skills/memory/SKILL.md scopes the relay: {sorted(scoping)}")
    if "/memory review" not in BUNDLE.read_text(encoding="utf-8"):
        problems.append("bundle.md does not register /memory review")
    if not problems:
        findings.append(
            "skills/memory/SKILL.md documents /memory review with all three actions and the "
            "relay-verbatim rule; bundle.md carries its row"
        )

    recovery_limit = (
        "the deterministic dispatch and scripted missing-id sequence are checked above, but cannot "
        "prove a model chose the one allowed correction; manager Terra scenarios remain pending"
    )
    if problems:
        report("suggestions.v2 Core 6", "Broken", "; ".join(problems))
        report("suggestions.v3 Core 6 (skill recovery)", "Can't check", recovery_limit)
        return
    if had_real:
        report("suggestions.v2 Core 6", "Kept", "; ".join(findings))
        report("suggestions.v3 Core 6 (skill recovery)", "Can't check", recovery_limit)
        return
    report(
        "suggestions.v2 Core 6",
        "Can't check",
        "suggestions.v2 §6 — Can't check in this lane because amplifier_memory.inbox is not in "
        "this build: accept's write, decline's declined.md line and skip's leave-it-waiting are "
        "the library's, and here they are a stand-in at lane P's published signatures. What IS "
        "checked: " + "; ".join(findings),
    )
    report("suggestions.v3 Core 6 (skill recovery)", "Can't check", recovery_limit)


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


def check_core_12(mod, tmp: Path) -> None:
    """§12 Which instance a session uses is configuration."""
    import amplifier_memory
    from amplifier_memory import llm_config

    findings: list[str] = []
    problems: list[str] = []

    # The plan's `home:` decides which store the tool reads and writes, even
    # when the environment names a different one.
    planned = tmp / "c12-planned"
    other = fresh_store(tmp, "c12-other")
    amplifier_memory.init(planned)
    amplifier_memory.save(
        "never use tabs in YAML files",
        "never use tabs in YAML",
        "assistant",
        "seed",
        ["never use tabs in YAML"],
        home=planned,
    )
    tool = mod.MemoryTool(FakeCoordinator([user("never use emoji")]), {"home": str(planned)})
    listed = _run(tool.execute({"operation": "list"}))
    if "never use tabs in YAML files" not in (listed.output or ""):
        problems.append(f"`home:` did not choose the store: list said {listed.output!r}")
    else:
        findings.append(
            f"`config: home: {planned}` listed that instance while $AMPLIFIER_MEMORY_HOME "
            f"named {other} — the plan wins"
        )

    saved = _run(
        tool.execute({"operation": "save", "text": "Never use emoji.", "quote": "never use emoji"})
    )
    wrote_planned = "Never use emoji." in (planned / "MEMORY.md").read_text(encoding="utf-8")
    wrote_other = "Never use emoji." in (other / "MEMORY.md").read_text(encoding="utf-8")
    if not saved.success or not wrote_planned or wrote_other:
        problems.append(
            f"save went to the wrong instance (planned={wrote_planned}, other={wrote_other}): "
            f"{saved.output!r}"
        )
    else:
        findings.append(
            f"save landed in the planned instance and nowhere else ({saved.output.splitlines()[0]})"
        )

    # `enabled: false` — every operation refuses with §12's one line, nothing
    # is written, and the description the model pays for is that line too.
    inert = tmp / "c12-inert"
    amplifier_memory.init(inert)
    before = (inert / "MEMORY.md").read_text(encoding="utf-8")
    (inert / "config.yaml").write_text(llm_config.default_body(enabled=False), encoding="utf-8")
    off = mod.MemoryTool(FakeCoordinator([user("never use emoji")]), {"home": str(inert)})
    expected = f"memory is disabled for this instance ({inert}: enabled: false)."
    operations = [
        {"operation": "save", "text": "Never use emoji.", "quote": "never use emoji"},
        {"operation": "edit", "id": "m-001", "text": "x", "quote": "never use emoji"},
        {"operation": "forget", "id": "m-001"},
        {"operation": "list"},
        {"operation": "overview"},
        {"operation": "cite", "id": "m-001"},
        {"operation": "review"},
        {"operation": "review", "action": "list"},
    ]
    wrong = [
        (call["operation"], result.success, result.output)
        for call in operations
        for result in [_run(off.execute(call))]
        if result.success or result.output != expected
    ]
    if wrong:
        problems.append(f"an inert instance did not refuse every operation in one line: {wrong}")
    elif (inert / "MEMORY.md").read_text(encoding="utf-8") != before:
        problems.append("an inert instance was written to")
    elif off.description != expected:
        problems.append(f"an inert instance still advertises {off.description!r}")
    else:
        findings.append(
            f"enabled: false → all {len(operations)} operation payloads "
            f"({', '.join(str(c['operation']) for c in operations)}) refuse with one line, "
            f"{expected!r}; MEMORY.md unchanged; the tool's description IS that line, so an "
            "inert instance advertises nothing to the model either"
        )

    # The line is the library's own, not a paraphrase of it.
    try:
        amplifier_memory.save(
            "x", "never use emoji", "assistant", "s", ["never use emoji"], home=inert
        )
    except amplifier_memory.InstanceDisabled as exc:
        if str(exc) != expected:
            problems.append(f"the tool's line {expected!r} differs from the library's {str(exc)!r}")
        else:
            findings.append("the refusal is byte-identical to the library's own InstanceDisabled")
    else:
        problems.append("the library let a write through to an inert instance")

    # Discriminating arm: enabled: true is an ordinary session.
    live = tmp / "c12-live"
    amplifier_memory.init(live)
    (live / "config.yaml").write_text(llm_config.default_body(enabled=True), encoding="utf-8")
    on = mod.MemoryTool(FakeCoordinator([user("never use emoji")]), {"home": str(live)})
    ok = _run(
        on.execute({"operation": "save", "text": "Never use emoji.", "quote": "never use emoji"})
    )
    if not ok.success:
        problems.append(f"enabled: true refused a save: {ok.output!r}")
    elif on.description != mod.DESCRIPTION:
        problems.append("enabled: true did not advertise the full description")
    else:
        findings.append(
            f"discriminating arm: the same config with enabled: true saves "
            f"({ok.output.splitlines()[0]}) and advertises the full description"
        )

    report("Core 12", "Broken" if problems else "Kept", "; ".join(problems or findings))


def check_core_13(mod, tmp: Path) -> None:
    """§13 Which sessions have a human in them."""
    import amplifier_memory

    findings: list[str] = []
    problems: list[str] = []
    saved_origin = os.environ.get("AMPLIFIER_SESSION_ORIGIN")
    home = fresh_store(tmp, "c13")
    seeded_inbox(home, 1)

    def explode(*args, **kwargs):
        raise AssertionError("library reached in a session with no human in it")

    try:
        # A worker session: reads still work, writes are refused by name.
        os.environ["AMPLIFIER_SESSION_ORIGIN"] = "worker"
        real = (amplifier_memory.save, amplifier_memory.forget, amplifier_memory.edit)
        amplifier_memory.save = explode
        amplifier_memory.forget = explode
        amplifier_memory.edit = explode
        try:
            worker = mod.MemoryTool(FakeCoordinator([user("never use emoji")]), {"home": str(home)})
            results = {
                "save": _run(
                    worker.execute(
                        {
                            "operation": "save",
                            "text": "Never use emoji.",
                            "quote": "never use emoji",
                        }
                    )
                ),
                "edit": _run(
                    worker.execute(
                        {
                            "operation": "edit",
                            "id": "m-001",
                            "text": "Never use emoji anywhere.",
                            "quote": "never use emoji",
                        }
                    )
                ),
                "forget": _run(worker.execute({"operation": "forget", "id": "m-001"})),
            }
            listed = _run(worker.execute({"operation": "list"}))
            review_listed = _run(worker.execute({"operation": "review", "action": "list"}))
        finally:
            amplifier_memory.save, amplifier_memory.forget, amplifier_memory.edit = real

        for label, result in results.items():
            output = result.output or ""
            if result.success:
                problems.append(f"a worker session {label} SUCCEEDED")
            elif "worker" not in output or "§13" not in output:
                problems.append(f"the worker {label} refusal does not name the origin: {output!r}")
            elif "\n" in output:
                problems.append(f"the worker {label} refusal was not one line")
            else:
                findings.append(f"{label} refused before any library call: {output}")
        if not listed.success:
            problems.append(f"a worker session could not READ the store: {listed.output!r}")
        elif not review_listed.success:
            problems.append(
                f"a worker session could not READ the suggestion inbox: {review_listed.output!r}"
            )
        else:
            findings.append(
                "memory list and explicit review list allowed in a worker session — §13 forbids writing, "
                "not reading; the memories still apply, the work is still this human's"
            )

        # The refusal is R2's shape with the origin in R2's place.
        r2 = mod.MemoryTool(FakeCoordinator([], parent_id="parent"), {"home": str(home)})
        os.environ.pop("AMPLIFIER_SESSION_ORIGIN", None)
        sub = _run(
            r2.execute(
                {"operation": "save", "text": "Never use emoji.", "quote": "never use emoji"}
            )
        )
        worker_line = results["save"].output or ""
        if (sub.output or "").replace("R2", "§13").replace("sub-agent", "worker").replace(
            "a root session", "a session"
        ) != worker_line:
            problems.append(
                f"§13's refusal is not R2's refusal with the origin named: {worker_line!r} vs "
                f"{sub.output!r}"
            )
        else:
            findings.append(
                f"the same shape as R2's, naming the origin instead: {sub.output!r} → "
                f"{worker_line!r}"
            )

        # Unset means human: the discriminating arm, on the same store.
        human = mod.MemoryTool(FakeCoordinator([user("never use emoji")]), {"home": str(home)})
        ok = _run(
            human.execute(
                {"operation": "save", "text": "Never use emoji.", "quote": "never use emoji"}
            )
        )
        if not ok.success:
            problems.append(f"unset origin refused a save: {ok.output!r}")
        else:
            findings.append(
                f"discriminating arm: unset $AMPLIFIER_SESSION_ORIGIN saves as it always did "
                f"({ok.output.splitlines()[0]})"
            )

        # Every non-human origin the contract names, refused by its own name.
        refused = []
        for origin in ("recipe", "agent", "eval"):
            os.environ["AMPLIFIER_SESSION_ORIGIN"] = origin
            tool = mod.MemoryTool(FakeCoordinator([user("never use emoji")]), {"home": str(home)})
            out = _run(
                tool.execute(
                    {"operation": "save", "text": "Never use tabs.", "quote": "never use emoji"}
                )
            )
            if out.success or origin not in (out.output or ""):
                problems.append(f"origin={origin} was not refused by name: {out.output!r}")
            else:
                refused.append(origin)
        if refused:
            findings.append(f"refused by name for every non-human origin: {', '.join(refused)}")
    finally:
        if saved_origin is None:
            os.environ.pop("AMPLIFIER_SESSION_ORIGIN", None)
        else:
            os.environ["AMPLIFIER_SESSION_ORIGIN"] = saved_origin

    report("Core 13", "Broken" if problems else "Kept", "; ".join(problems or findings))


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
        check_core_6_overview(mod, tmp)
        check_store_5(mod, tmp)
        check_core_7(mod)
        check_core_8(mod, tmp)
        check_r2(mod, tmp)
        check_core_12(mod, tmp)
        check_core_13(mod, tmp)
        check_suggestions_6(mod, tmp)
    return 0


if __name__ == "__main__":
    sys.exit(main())
