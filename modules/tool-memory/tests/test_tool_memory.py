"""Tests for tool-memory — session.v4 §3, §5, §6, §8, §12, §13, R2, and the refusal relay.

Every test that stands as evidence prints what it measured; run with `-s` to
see it. Nothing here touches a real store: `AMPLIFIER_MEMORY_HOME` points at a
tmp_path in every test, and `AMPLIFIER_PROJECTS_HOME` at another, so the
transcript fallback never reads the human's real sessions either.
"""

import json
import pathlib
import re
from datetime import datetime

import amplifier_memory
import pytest
from amplifier_memory import _git

import amplifier_module_tool_memory as mod

# --------------------------------------------------------------------------
# Fakes — a coordinator and a context module, no amplifier-core session needed
# --------------------------------------------------------------------------


class FakeContext:
    """Shaped like the shipped context module: `get_messages()` is async."""

    def __init__(self, messages=None):
        self.messages = messages or []

    async def get_messages(self):
        return list(self.messages)


class FakeCoordinator:
    def __init__(self, session_id="test-session", parent_id=None, context=None):
        self.session_id = session_id
        self.parent_id = parent_id
        self.mount_points = {"tools": {}}
        if context is not None:
            self.mount_points["context"] = context
        self.mounted = []

    async def mount(self, mount_point, module, name=None):
        self.mounted.append({"mount_point": mount_point, "name": name, "module": module})
        self.mount_points.setdefault(mount_point, {})[name] = module


def user(text):
    return {"role": "user", "content": text}


def assistant(text):
    return {"role": "assistant", "content": text}


@pytest.fixture
def store(tmp_path, monkeypatch):
    """A real, initialised store in a temp dir — the library does the work."""
    home = tmp_path / "memory"
    monkeypatch.setenv("AMPLIFIER_MEMORY_HOME", str(home))
    monkeypatch.setenv("AMPLIFIER_PROJECTS_HOME", str(tmp_path / "projects"))
    amplifier_memory.init(home)
    return home


def tool(messages=None, parent_id=None, session_id="test-session"):
    context = FakeContext(messages) if messages is not None else None
    return mod.MemoryTool(FakeCoordinator(session_id, parent_id, context), {})


# --------------------------------------------------------------------------
# Acceptance 2 — one tool, named `memory`, mounted the one legal way
# --------------------------------------------------------------------------


async def test_mount_mounts_exactly_one_tool_named_memory():
    coordinator = FakeCoordinator()
    info = await mod.mount(coordinator, {})

    print("mounted:", [(m["mount_point"], m["name"]) for m in coordinator.mounted])
    print("mount() returned:", info)

    assert len(coordinator.mounted) == 1
    assert coordinator.mounted[0]["mount_point"] == "tools"
    assert coordinator.mounted[0]["name"] == "memory"
    assert coordinator.mount_points["tools"]["memory"].name == "memory"


#: session.v4 §11 — the six things the description may teach, and nothing else.
#: One marker each, so a rewrite that drops a teaching fails here rather than in a
#: session six weeks later.
SIX_TEACHINGS = {
    "when to save (§3)": "SAVE when",
    "when not to (§4)": "DO NOT SAVE",
    "one call at a time": "Save ONE memory per call",
    "the verbatim quote (§5)": "Only the human's own words become memory",
    "relay, never reword": "relayed verbatim and never reworded",
    "relay refusals": "receipt or refusal",
}

#: §11: slash commands, the review walk, batches and topic files are taught by the
#: skills and by `/memory help`, loaded on demand — never on every turn. The
#: lookbehind is the difference between the command `/edit` and the field label
#: `save/edit:`, which is parameter text and belongs where it is.
SLASH_COMMAND = re.compile(r"(?<![A-Za-z0-9])/(memory|remember|edit|forget)\b")
TAUGHT_BY_THE_SKILLS = ("topics/", "batch_of=", "operation=")

#: session.v4 Conformance: nothing the model is given asserts what the human can
#: or cannot see of a tool call. Assembled from fragments so this file is not the
#: one thing the repo-wide grep finds.
PRESUMING = ("the human " + "reads", "Say " + "nothing", "counted, " + "not read")


def schema_text() -> str:
    """Every readable string in `INPUT_SCHEMA`: names, enum values, descriptions."""
    out: list[str] = []
    for name, prop in mod.INPUT_SCHEMA["properties"].items():
        out.append(name)
        out.extend(prop.get("enum", []) or [])
        out.append(prop.get("description", ""))
    return "\n".join(out)


def test_description_teaches_the_six_things_and_nothing_more():
    print(f"description: {len(mod.DESCRIPTION.splitlines())} lines")
    print(mod.DESCRIPTION)

    missing = [name for name, marker in SIX_TEACHINGS.items() if marker not in mod.DESCRIPTION]
    assert not missing, f"the description no longer teaches {missing}"
    # §3's receipt is NOT in the description: it is rendered by the tool, so there
    # is no announce format left for the model to reproduce or garble.
    assert "Saved memory" not in mod.DESCRIPTION
    assert "saved m-" not in mod.DESCRIPTION


def test_the_description_and_the_parameter_text_carry_no_slash_command():
    """§11: what the skills teach on demand is not paid for on every turn."""
    both = mod.DESCRIPTION + "\n" + schema_text()
    commands = SLASH_COMMAND.findall(both)
    taught = [marker for marker in TAUGHT_BY_THE_SKILLS if marker in mod.DESCRIPTION]
    print("slash commands:", commands, "| taught by the skills:", taught)
    assert commands == []
    assert taught == []


def test_nothing_the_model_is_given_presumes_what_the_human_can_see():
    both = mod.DESCRIPTION + "\n" + schema_text()
    assert [phrase for phrase in PRESUMING if phrase in both] == []


def test_the_description_and_the_parameter_text_fit_the_budget():
    """§11's ceiling, on this bundle's largest two sources. The kit measures all four.

    The bound is 345, not 330: §6 as amended 2026-09-07 gives `list` and `review` a
    `<page>`, and the `page` property's name and description measured **12 cl100k
    tokens** on the day they were added (190 + 140 → 190 + 152). That is the whole of
    the growth, it is named here rather than absorbed quietly, and the contract's own
    ceiling — 500 across all four sources — is asserted by
    `conformance/session/budget/run.py`, which prints the itemised bill every run.
    """
    tiktoken = pytest.importorskip("tiktoken")
    encode = tiktoken.get_encoding("cl100k_base").encode
    description, parameters = len(encode(mod.DESCRIPTION)), len(encode(schema_text()))
    print(
        f"DESCRIPTION {description} + INPUT_SCHEMA text {parameters} = {description + parameters}"
    )
    assert description + parameters <= 345


def test_description_never_says_the_assistant_cannot_save_a_drafted_line():
    """The worst line of the 2026-09-06 transcript: false, and named by 5/6 lenses."""
    # Assembled from fragments on purpose: the lane's own acceptance is a grep
    # for these phrases across skills/ and modules/tool-memory/, and a test file
    # that spelled them out would be the only thing it ever found.
    false_claims = [
        "can't write " + "these",
        "cannot write " + "these",
        "you type " + "them",
    ]
    lowered = mod.DESCRIPTION.lower()
    for false_claim in false_claims:
        assert false_claim not in lowered


def test_operations_are_exactly_save_edit_forget_list_overview_cite_review():
    assert mod.INPUT_SCHEMA["properties"]["operation"]["enum"] == [
        "save",
        "edit",
        "forget",
        "list",
        "overview",
        "cite",
        "review",
    ]


# --------------------------------------------------------------------------
# Acceptance 3 — session.v2 §5: the human-turn check, both arms
# --------------------------------------------------------------------------


async def test_row_amm_014_quote_in_a_human_turn_is_saved(store):
    memory = tool(messages=[user("never use emoji in commit messages"), assistant("ok")])
    result = await memory.execute(
        {
            "operation": "save",
            "text": "Never use emoji in commit messages.",
            "quote": "never use emoji in commit messages",
        }
    )
    print("save ->", result.output)

    assert result.success is True
    assert result.output.splitlines()[:2] == [
        "saved m-001 — /memory forget m-001 to undo.",
        "  Never use emoji in commit messages.",
    ]
    lines = (store / "MEMORY.md").read_text(encoding="utf-8").splitlines()
    print("MEMORY.md:", lines)
    assert lines == ["- [m-001] Never use emoji in commit messages."]


async def test_row_amm_014_quote_only_in_an_assistant_turn_is_refused(store):
    memory = tool(messages=[user("do step 1"), assistant("never use emoji in commit messages")])
    result = await memory.execute(
        {
            "operation": "save",
            "text": "Never use emoji in commit messages.",
            "quote": "never use emoji in commit messages",
        }
    )
    print("refusal ->", result.output)

    assert result.success is False
    assert "\n" not in result.output
    assert result.output == mod.REFUSAL_NO_HUMAN_WORDS
    assert (store / "MEMORY.md").read_text(encoding="utf-8") == ""


async def test_content_blocks_are_flattened_so_a_block_provider_still_verifies(store):
    blocks = [{"type": "text", "text": "always run make check before pushing"}]
    memory = tool(messages=[{"role": "user", "content": blocks}])
    result = await memory.execute(
        {
            "operation": "save",
            "text": "Always run make check before pushing.",
            "quote": "always run make check before pushing",
        }
    )
    print("blocks ->", result.output)
    assert result.success is True


async def test_transcript_is_the_fallback_when_no_context_module_is_mounted(store, tmp_path):
    session_dir = tmp_path / "projects" / mod.project_slug() / "sessions" / "test-session"
    session_dir.mkdir(parents=True)
    (session_dir / "transcript.jsonl").write_text(
        json.dumps(user("prefer tabs over spaces")) + "\n", encoding="utf-8"
    )

    memory = tool(messages=None)  # no context mount point at all
    result = await memory.execute(
        {
            "operation": "save",
            "text": "Prefer tabs over spaces.",
            "quote": "prefer tabs over spaces",
        }
    )
    print("transcript fallback ->", result.output)
    assert result.success is True


async def test_the_tool_does_not_reimplement_the_check_it_passes_human_turns(store, monkeypatch):
    """The library owns §5. Proven by intercepting the call, not by reading."""
    seen = {}
    real_save = amplifier_memory.save

    def spy(text, quote, writer, session_id, human_turns=None, **kwargs):
        seen.update(
            text=text, quote=quote, writer=writer, session_id=session_id, human_turns=human_turns
        )
        return real_save(text, quote, writer, session_id, human_turns, **kwargs)

    monkeypatch.setattr(amplifier_memory, "save", spy)
    memory = tool(messages=[user("always squash before merging")])
    await memory.execute(
        {
            "operation": "save",
            "text": "Always squash before merging.",
            "quote": "always squash before merging",
        }
    )
    print("library received:", seen)
    assert seen["human_turns"] == ["always squash before merging"]
    assert seen["writer"] == "assistant"
    assert seen["session_id"] == "test-session"


# --------------------------------------------------------------------------
# Acceptance 4 — session.v2 R2: a sub-agent never writes
# --------------------------------------------------------------------------


async def test_r2_sub_agent_save_is_refused_before_any_library_call(store, monkeypatch):
    def explode(*args, **kwargs):
        raise AssertionError("the library must not be reached in a sub-agent session")

    monkeypatch.setattr(amplifier_memory, "save", explode)
    memory = tool(messages=[user("never use emoji")], parent_id="parent-session")
    result = await memory.execute(
        {"operation": "save", "text": "Never use emoji.", "quote": "never use emoji"}
    )
    print("R2 save ->", result.output)

    assert result.success is False
    assert "R2" in result.output
    assert "\n" not in result.output


async def test_r2_sub_agent_forget_is_refused(store):
    memory = tool(messages=[], parent_id="parent-session")
    result = await memory.execute({"operation": "forget", "id": "m-001"})
    print("R2 forget ->", result.output)
    assert result.success is False
    assert "R2" in result.output


async def test_r2_sub_agent_list_is_allowed(store):
    memory = tool(messages=[], parent_id="parent-session")
    result = await memory.execute({"operation": "list"})
    print("R2 list ->", result.output)
    assert result.success is True
    assert "no memories yet" in result.output


# --------------------------------------------------------------------------
# Acceptance 5 — every library refusal is relayed as one line
# --------------------------------------------------------------------------


async def test_duplicate_is_relayed_in_one_line(store):
    memory = tool(messages=[user("never use emoji")])
    payload = {"operation": "save", "text": "Never use emoji.", "quote": "never use emoji"}
    await memory.execute(payload)
    result = await memory.execute(payload)
    print("duplicate ->", result.output)
    assert result.success is False
    assert "\n" not in result.output
    assert result.output == "already remembered as m-001 — nothing changed."


async def test_unknown_id_is_relayed_in_one_line(store):
    memory = tool(messages=[])
    result = await memory.execute({"operation": "forget", "id": "m-999"})
    print("unknown id ->", result.output)
    assert result.success is False
    assert "\n" not in result.output
    assert result.output == "no memory m-999 — never issued. Current: none. Say the id."


async def test_cap_exceeded_is_relayed_in_one_line(store, monkeypatch):
    lines = [
        f"- [m-{n:03d}] filler {n}" for n in range(1, amplifier_memory.store.MEMORY_LINE_CAP + 1)
    ]
    (store / "MEMORY.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    memory = tool(messages=[user("one more thing")])
    result = await memory.execute(
        {"operation": "save", "text": "One more thing.", "quote": "one more thing"}
    )
    print("cap ->", result.output)
    assert result.success is False
    assert "\n" not in result.output
    assert result.output == (
        "not saved — MEMORY.md is full (200 of 200 lines). "
        "/memory forget one you no longer need, or ask me to move a group into a topic file."
    )


async def test_store_missing_says_how_to_create_the_store(tmp_path, monkeypatch):
    monkeypatch.setenv("AMPLIFIER_MEMORY_HOME", str(tmp_path / "nowhere"))
    monkeypatch.setenv("AMPLIFIER_PROJECTS_HOME", str(tmp_path / "projects"))
    memory = tool(messages=[user("never use emoji")])
    result = await memory.execute(
        {"operation": "save", "text": "Never use emoji.", "quote": "never use emoji"}
    )
    print("store missing ->", result.output)
    assert result.success is False
    assert "\n" not in result.output
    assert "amplifier-memory init" in result.output


async def test_a_refusal_is_never_a_traceback(store):
    memory = tool(messages=[])
    result = await memory.execute({"operation": "sabotage"})
    print("unknown operation ->", result.output)
    assert result.success is False
    assert "Traceback" not in result.output


# --------------------------------------------------------------------------
# Acceptance 6 — the writers, and the Phase 1 refusal of `suggestion`
# --------------------------------------------------------------------------


async def test_row_amm_015_writer_human_passes_quote_equal_to_text(store, monkeypatch):
    seen = {}
    real_save = amplifier_memory.save

    def spy(text, quote, writer, session_id, human_turns=None, **kwargs):
        seen.update(text=text, quote=quote, writer=writer)
        return real_save(text, quote, writer, session_id, human_turns, **kwargs)

    monkeypatch.setattr(amplifier_memory, "save", spy)
    typed = "Always run make check before pushing."
    # What the CLI actually puts in context for `/remember <text>` is a
    # synthetic prompt that carries the typed text verbatim inside it.
    synthetic = (
        f'Use the load_skill tool to load the skill "remember". The user\'s input is: {typed}'
    )
    memory = tool(messages=[user(synthetic)])
    result = await memory.execute({"operation": "save", "text": typed, "writer": "human"})

    print("human write ->", result.output)
    print("library received:", seen)
    assert result.success is True
    assert seen["quote"] == seen["text"] == typed
    assert seen["writer"] == "human"


async def test_writer_suggestion_is_refused(store):
    memory = tool(messages=[user("never use emoji")])
    result = await memory.execute(
        {
            "operation": "save",
            "text": "Never use emoji.",
            "quote": "never use emoji",
            "writer": "suggestion",
        }
    )
    print("suggestion ->", result.output)
    assert result.success is False
    assert "is not available" in result.output
    assert "Phase 1" not in result.output


async def test_assistant_save_without_a_quote_is_refused(store):
    memory = tool(messages=[user("never use emoji")])
    result = await memory.execute({"operation": "save", "text": "Never use emoji."})
    print("no quote ->", result.output)
    assert result.success is False
    assert "verbatim words" in result.output


# --------------------------------------------------------------------------
# Acceptance 7 — §6: forget and list announce as the contract words them
# --------------------------------------------------------------------------


async def test_row_amm_015_forget_removes_the_line_and_announces(store):
    memory = tool(messages=[user("never use emoji")])
    await memory.execute(
        {"operation": "save", "text": "Never use emoji.", "quote": "never use emoji"}
    )
    result = await memory.execute({"operation": "forget", "id": "m-001"})
    print("forget ->\n" + result.output)

    assert result.success is True
    # §6's literal, kept; two lines added under it, because the one operation
    # whose result a human cannot see echoed nothing back.
    assert result.output.splitlines() == [
        "forgot m-001 — still in git: amplifier-memory why m-001",
        "  Never use emoji.",
    ]
    assert (store / "MEMORY.md").read_text(encoding="utf-8") == ""


async def test_row_amm_015_list_prints_ids_first_and_the_hand_edit_path(store):
    memory = tool(messages=[user("never use emoji"), user("always squash before merging")])
    await memory.execute(
        {"operation": "save", "text": "Never use emoji.", "quote": "never use emoji"}
    )
    await memory.execute(
        {
            "operation": "save",
            "text": "Always squash before merging.",
            "quote": "always squash before merging",
        }
    )
    result = await memory.execute({"operation": "list"})
    print("list ->\n" + result.output)

    assert result.success is True
    assert result.output.splitlines() == [
        "**2 memories**",
        "- **m-001** Never use emoji.",
        "- **m-002** Always squash before merging.",
        f"edit by hand: $EDITOR {store}/MEMORY.md",
    ]
    # store.v1 §9's hand-edit path is the free edit verb; nothing else says so.
    assert "0 pending suggestions" not in result.output
    assert "topic files" not in result.output
    assert "Phase 1" not in result.output


async def test_one_memory_is_not_1_memories(store):
    memory = tool(messages=[user("never use emoji")])
    await memory.execute(
        {"operation": "save", "text": "Never use emoji.", "quote": "never use emoji"}
    )
    result = await memory.execute({"operation": "list"})
    print("one ->\n" + result.output)
    assert result.output.splitlines()[0] == "**1 memory**"


async def test_topics_are_counted_only_when_there_are_some(store):
    memory = tool(messages=[user("never use emoji"), user("two-space indent in YAML")])
    await memory.execute(
        {"operation": "save", "text": "Never use emoji.", "quote": "never use emoji"}
    )
    before = await memory.execute({"operation": "list"})
    print("no topics ->", before.output.splitlines()[0])
    assert before.output.splitlines()[0] == "**1 memory**"

    await memory.execute(
        {
            "operation": "save",
            "text": "Two-space indent, never tabs.",
            "quote": "two-space indent in YAML",
            "topic": "yaml-style",
            "topic_purpose": "How to write YAML for me.",
        }
    )
    after = await memory.execute({"operation": "list"})
    print("one topic ->", after.output.splitlines()[0])
    assert after.output.splitlines()[0] == "**1 memory, 1 topic**"


async def test_empty_list_says_what_to_do(store):
    result = await tool(messages=[]).execute({"operation": "list"})
    print("empty list ->\n" + result.output)
    # §6 forbids a zero-valued count: an empty store is told what to do instead.
    assert result.output.splitlines() == [
        "no memories yet — /remember <text> to add one.",
        f"edit by hand: $EDITOR {store}/MEMORY.md",
    ]


def test_the_default_store_renders_as_a_tilde_path(monkeypatch):
    """`~/.amplifier/memory/MEMORY.md`, not `/home/<someone>/…`."""
    monkeypatch.delenv("AMPLIFIER_MEMORY_HOME", raising=False)
    from pathlib import Path

    got = mod.display_path(Path.home() / ".amplifier" / "memory" / "MEMORY.md")
    print("default path renders as:", got)
    assert got == "~/.amplifier/memory/MEMORY.md"


# --------------------------------------------------------------------------
# Lane H — provenance on every save receipt (Dana F4: the assistant's own
# rewrite appeared in quotation marks, indistinguishable from the human's words)
# --------------------------------------------------------------------------


async def test_save_receipt_marks_the_humans_own_words(store):
    typed = "Always run make check before pushing."
    memory = tool(messages=[user(f"The user's input is: {typed}")])
    result = await memory.execute({"operation": "save", "text": typed, "writer": "human"})
    print("human save ->\n" + result.output)

    assert result.output.splitlines() == [
        "saved m-001 — /memory forget m-001 to undo.",
        f"  {typed}",
        "  your words, verbatim",
    ]
    assert "committed " not in result.output


async def test_save_receipt_marks_the_assistants_wording_with_the_approving_quote(store):
    memory = tool(messages=[user("Great, remember these for me")])
    result = await memory.execute(
        {
            "operation": "save",
            "text": "When I say explain, go long with headers.",
            "quote": "remember these for me",
            "writer": "assistant",
        }
    )
    print("assistant save ->\n" + result.output)

    assert result.output.splitlines() == [
        "saved m-001 — /memory forget m-001 to undo.",
        "  When I say explain, go long with headers.",
        '  my wording, your go-ahead: "remember these for me"',
    ]
    assert "committed " not in result.output


async def test_a_batch_of_drafted_lines_reports_itself_once_at_the_end(store):
    """Acceptance 3: three saves, one approval phrase, the last result carries all."""
    approval = "remember these for me"
    memory = tool(messages=[user(f"Great, {approval}")])
    outputs = []
    for text in ("Lead with the next action.", "Number multi-step work.", "Cap lists at five."):
        result = await memory.execute(
            {
                "operation": "save",
                "text": text,
                "quote": approval,
                "writer": "assistant",
                "batch_of": 3,
            }
        )
        outputs.append(result.output)
        print(f"--- save {len(outputs)} ---\n{result.output}")

    # The first two results are their own three-line receipt and NOTHING else: a
    # summary reprinted after every save is the noise the batch line replaces.
    for earlier in outputs[:-1]:
        assert len(earlier.splitlines()) == 3
        assert "memories —" not in earlier

    last = outputs[-1].splitlines()
    assert last[:3] == [
        "saved m-003 — /memory forget m-003 to undo.",
        "  Cap lists at five.",
        '  my wording, your go-ahead: "remember these for me"',
    ]
    assert last[3] == (
        'saved 3 memories — my wording, your go-ahead: "remember these for me". '
        "Reword any line and I'll replace it; /memory forget <id> drops one."
    )
    assert last[4:] == [
        "- [m-001] Lead with the next action.",
        "- [m-002] Number multi-step work.",
        "- [m-003] Cap lists at five.",
    ]


async def test_a_new_approval_phrase_starts_a_new_batch(store):
    memory = tool(messages=[user("remember these"), user("and this one too")])
    await memory.execute(
        {"operation": "save", "text": "One.", "quote": "remember these", "writer": "assistant"}
    )
    second = await memory.execute(
        {"operation": "save", "text": "Two.", "quote": "and this one too", "writer": "assistant"}
    )
    print("new phrase ->\n" + second.output)
    assert second.output.splitlines()[2] == '  my wording, your go-ahead: "and this one too"'


async def test_the_pointer_line_is_not_counted_in_the_topic_files_batch(store):
    """Two topic lines and the MEMORY.md pointer are not peers; the receipt says so."""
    said = "keep my YAML rules somewhere"
    memory = tool(messages=[user(said)])
    for text in ("Use two-space indent.", "Never a tab character."):
        await memory.execute(
            {
                "operation": "save",
                "text": text,
                "quote": said,
                "topic": "yaml-style",
                "topic_purpose": "How to write YAML for me.",
            }
        )
    pointer = await memory.execute(
        {"operation": "save", "text": "YAML style → topics/yaml-style.md", "quote": said}
    )
    print("pointer ->\n" + pointer.output)
    assert pointer.output.splitlines()[2] == f'  my wording, your go-ahead: "{said}"'
    assert "3 memories —" not in pointer.output


# --------------------------------------------------------------------------
# Lane H — the topic-file write path (store.v1 §5; the highest-value miss)
# --------------------------------------------------------------------------


async def test_a_ruleset_goes_to_a_topic_file_plus_one_pointer_line(store):
    said = "keep my ADHD rules somewhere"
    memory = tool(messages=[user(said)])
    for text in ("Lead with the next action.", "Cap lists at five items."):
        result = await memory.execute(
            {
                "operation": "save",
                "text": text,
                "quote": said,
                "topic": "adhd-style",
                "topic_purpose": "How to shape a reply for me.",
            }
        )
        print("topic save ->\n" + result.output)

    pointer = await memory.execute(
        {
            "operation": "save",
            "text": "How to shape a reply for me → topics/adhd-style.md",
            "quote": said,
        }
    )
    print("pointer save ->\n" + pointer.output)

    topic_lines = (store / "topics" / "adhd-style.md").read_text(encoding="utf-8").splitlines()
    memory_lines = (store / "MEMORY.md").read_text(encoding="utf-8").splitlines()
    print("topics/adhd-style.md:", topic_lines)
    print("MEMORY.md:", memory_lines)

    assert topic_lines == [
        "How to shape a reply for me.",
        "- [m-001] Lead with the next action.",
        "- [m-002] Cap lists at five items.",
    ]
    assert memory_lines == ["- [m-003] How to shape a reply for me → topics/adhd-style.md"]
    # The receipt names both files, so the model knows the pointer is still owed.
    assert "topics/adhd-style.md" in result.output
    assert "MEMORY.md needs one pointer line" in result.output


async def test_a_new_topic_file_without_a_purpose_is_refused_in_one_line(store):
    memory = tool(messages=[user("remember this")])
    result = await memory.execute(
        {
            "operation": "save",
            "text": "Something.",
            "quote": "remember this",
            "topic": "nameless",
        }
    )
    print("no purpose ->", result.output)
    assert result.success is False
    assert "\n" not in result.output
    assert "topic_purpose" in result.output


# --------------------------------------------------------------------------
# Lane H — the remaining refusals from the proposal's table
# --------------------------------------------------------------------------


async def test_unknown_id_names_when_it_went_and_what_is_left(store):
    memory = tool(messages=[user("a"), user("b")])
    await memory.execute({"operation": "save", "text": "A.", "quote": "a"})
    await memory.execute({"operation": "save", "text": "B.", "quote": "b"})
    await memory.execute({"operation": "forget", "id": "m-001"})

    result = await memory.execute({"operation": "forget", "id": "m-001"})
    print("forgotten id ->", result.output)
    assert result.success is False
    assert "\n" not in result.output
    today = datetime.now().astimezone().date().isoformat()
    assert result.output == f"no memory m-001 — forgotten {today}. Current: m-002. Say the id."


async def test_any_other_failure_says_nothing_was_lost_and_logs_a_line(
    store, tmp_path, monkeypatch
):
    log = tmp_path / "memory-errors.log"
    monkeypatch.setenv("AMPLIFIER_MEMORY_ERROR_LOG", str(log))

    def explode(*args, **kwargs):
        raise amplifier_memory.GitFailed("commit failed: could not lock ref")

    monkeypatch.setattr(amplifier_memory, "save", explode)
    memory = tool(messages=[user("never use emoji")])
    result = await memory.execute(
        {"operation": "save", "text": "Never use emoji.", "quote": "never use emoji"}
    )
    print("any failure ->", result.output)
    print("log line ->", log.read_text(encoding="utf-8").strip())

    assert result.success is False
    assert "\n" not in result.output
    assert result.output == (f"not saved — nothing changed, nothing lost. Details: {log}")
    # The refusal names a file; the file has the line in it.
    assert "could not lock ref" in log.read_text(encoding="utf-8")


# --------------------------------------------------------------------------
# The slug rule, verified against the CLI's own rule rather than assumed
# --------------------------------------------------------------------------


def test_project_slug_matches_the_cli_rule(tmp_path):
    from pathlib import Path

    got = mod.project_slug(Path("/home/user/repos/myapp"))
    print("slug:", got)
    assert got == "-home-user-repos-myapp"


# --------------------------------------------------------------------------
# Row gux — a hand-typed byte that is not UTF-8, on both of this tool's reads
# --------------------------------------------------------------------------


def _append_a_raw_byte(store):
    """The hand edit store.v1 §9 invites, done with the wrong editor encoding."""
    path = store / "MEMORY.md"
    path.write_bytes(path.read_bytes() + b"- [m-002] Jos\xe9 prefers short reviews\n")
    return path


async def test_row_gux_list_shows_the_bad_byte_and_names_doctor(store):
    """The listing still comes back whole, and says what the U+FFFD is."""
    memory = tool(messages=[user("never use emoji")])
    await memory.execute(
        {"operation": "save", "text": "Never use emoji.", "quote": "never use emoji"}
    )
    path = _append_a_raw_byte(store)

    with pytest.raises(UnicodeDecodeError) as strict:
        path.read_text(encoding="utf-8")
    result = await memory.execute({"operation": "list"})
    print("the strict read ->", type(strict.value).__name__, strict.value)
    print("list ->\n" + result.output)

    assert result.success is True
    assert result.output.splitlines() == [
        "**2 memories**",
        "- **m-001** Never use emoji.",
        "- **m-002** Jos\ufffd prefers short reviews",
        f"edit by hand: $EDITOR {store}/MEMORY.md",
        "store has a byte that is not UTF-8 — run amplifier-memory doctor",
    ]


async def test_row_gux_a_clean_store_gets_no_such_note(store):
    """The note is evidence, not decoration: nothing says it when nothing is wrong."""
    result = await tool(messages=[]).execute({"operation": "list"})
    print("clean list ->\n" + result.output)
    assert mod.LIST_STORE_NOT_UTF8 not in result.output


async def test_row_gux_saving_into_a_store_with_a_bad_byte_refuses_in_one_line(
    store, tmp_path, monkeypatch
):
    """Honest scope note: `save` does not crash — it refuses, by design, before writing.

    The library refuses to append to a file it cannot vouch for (`_require_wellformed`),
    which is right: appending would bury the damage. And the refusal carries the remedy:
    `StoreMalformed` (like `StoreMissing`) is relayed in its own words, so the one line
    carries `amplifier-memory doctor --repair` rather than a pointer to a log
    (item zp4).
    """
    # The refusal path logs a line; point it at tmp_path so no test ever appends to
    # the human's real `~/.amplifier/memory-errors.log`.
    monkeypatch.setenv("AMPLIFIER_MEMORY_ERROR_LOG", str(tmp_path / "memory-errors.log"))
    memory = tool(messages=[user("never use emoji")])
    await memory.execute(
        {"operation": "save", "text": "Never use emoji.", "quote": "never use emoji"}
    )
    _append_a_raw_byte(store)

    result = await memory.execute(
        {"operation": "save", "text": "Always squash first.", "quote": "never use emoji"}
    )
    print("save into a store with a bad byte ->", repr(result.output))

    assert result.success is False
    assert len(result.output.splitlines()) == 1
    assert "Traceback" not in result.output
    assert "codec can't decode" not in result.output
    # item zp4: the remedy reaches the human in the one line, not only the log.
    print("human sees ->", result.output)
    assert "amplifier-memory doctor --repair" in result.output
    assert not (tmp_path / "memory-errors.log").exists() or "doctor --repair" not in (
        tmp_path / "memory-errors.log"
    ).read_text(encoding="utf-8")


async def test_row_gux_a_transcript_byte_that_is_not_utf8_no_longer_costs_the_save(store, tmp_path):
    """This tool's OTHER strict read: the session transcript it falls back to.

    Not a store file — the session's own — so the library accessor does not apply, but
    the same tolerance does. Read strictly, one byte in an earlier turn turned a good
    save into `'utf-8' codec can't decode byte 0xe9…` and the memory was lost.
    """
    session = tmp_path / "projects" / mod.project_slug() / "sessions" / "test-session"
    session.mkdir(parents=True)
    transcript = session / "transcript.jsonl"
    transcript.write_bytes(
        b'{"role": "user", "content": "caf\xe9 was closed"}\n'
        + (json.dumps({"role": "user", "content": "never use emoji"}) + "\n").encode("utf-8")
    )

    with pytest.raises(UnicodeDecodeError) as strict:
        transcript.read_text(encoding="utf-8")
    turns = mod.read_transcript_human_turns("test-session")
    # No context module on this coordinator, so the save takes the disk fallback.
    result = await tool().execute(
        {"operation": "save", "text": "Never use emoji.", "quote": "never use emoji"}
    )
    print("the strict read ->", type(strict.value).__name__, strict.value)
    print("turns from disk ->", turns)
    print("save ->\n" + result.output)

    assert turns == ["caf\ufffd was closed", "never use emoji"]
    assert result.success is True
    assert result.output.splitlines()[0] == "saved m-001 — /memory forget m-001 to undo."


# --------------------------------------------------------------------------
# Lane K2 — session.v2 §6 `/edit` and §8 `cite`
# --------------------------------------------------------------------------


async def test_edit_keeps_the_id_and_the_receipt_says_what_it_was(store):
    """§6: a refinement, not a new memory — and the human sees the difference."""
    typed = "When I say explain, go long."
    refined = 'When I say "explain" or "walk me through", go long with headers.'
    memory = tool(
        messages=[
            user(f"The user's input is: {typed}"),
            user(f"The user's input is: {refined}"),
        ]
    )
    await memory.execute({"operation": "save", "text": typed, "writer": "human"})
    result = await memory.execute(
        {"operation": "edit", "id": "m-001", "text": refined, "writer": "human"}
    )
    print("edit ->\n" + result.output)
    print("MEMORY.md:", (store / "MEMORY.md").read_text(encoding="utf-8").strip())

    assert result.success is True
    assert result.output.splitlines() == [
        f'edited m-001 — was: "{typed}"',
        f"  now: {refined}",
    ]
    # The id survives: that is the whole point of an edit (store.v2 §3).
    assert (store / "MEMORY.md").read_text(encoding="utf-8") == f"- [m-001] {refined}\n"


async def test_edit_of_an_unknown_id_is_the_one_line_refusal(store):
    memory = tool(messages=[user("The user's input is: Something else entirely here.")])
    result = await memory.execute(
        {
            "operation": "edit",
            "id": "m-404",
            "text": "Something else entirely here.",
            "writer": "human",
        }
    )
    print("edit unknown ->", result.output)

    assert result.success is False
    assert "\n" not in result.output
    assert result.output.startswith("no memory m-404 — never issued.")
    assert result.output.endswith("Say the id.")


async def test_edit_is_refused_in_a_sub_agent_session(store):
    memory = tool(messages=[user("never mind")], parent_id="parent-session")
    result = await memory.execute(
        {"operation": "edit", "id": "m-001", "text": "Anything.", "quote": "never mind"}
    )
    print("sub-agent edit ->", result.output)
    assert result.success is False
    assert "R2" in result.output


async def test_cite_is_silent_and_writes_a_cited_usage_event(store):
    """§8: the instrument, not the rate. cite returns no receipt text."""
    said = "Always cite the memory you acted on."
    memory = tool(messages=[user(said)])
    await memory.execute({"operation": "save", "text": said, "writer": "human"})
    result = await memory.execute({"operation": "cite", "id": "m-001"})
    events = [
        json.loads(line)
        for line in (store / "usage.jsonl").read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    print("cite ->", repr(result.output))
    print("usage.jsonl:", events)

    assert result.success is True
    assert result.output == ""
    cited = [e for e in events if e["event"] == "cited"]
    assert cited and cited[-1]["target"] == "m-001"
    assert cited[-1]["session_id"] == "test-session"


async def test_cite_of_an_unknown_id_is_the_one_line_refusal(store):
    result = await tool(messages=[]).execute({"operation": "cite", "id": "m-404"})
    print("cite unknown ->", result.output)
    assert result.success is False
    assert result.output.startswith("no memory m-404 —")


async def test_a_batch_without_batch_of_never_prints_a_running_summary(store):
    """Without the model's count the tool cannot know which save is last.

    Silence is the honest answer: three correct three-line receipts, and no
    summary reprinted after every save.
    """
    approval = "remember these for me"
    memory = tool(messages=[user(f"Great, {approval}")])
    outputs = []
    for text in ("One thing.", "Two things.", "Three things."):
        result = await memory.execute(
            {"operation": "save", "text": text, "quote": approval, "writer": "assistant"}
        )
        outputs.append(result.output)
        print(f"--- save {len(outputs)} ---\n{result.output}")

    for output in outputs:
        assert len(output.splitlines()) == 3
        assert "memories —" not in output


# --------------------------------------------------------------------------
# Lane Q — suggestions.v2 §6: the review listing and its three receipts
# --------------------------------------------------------------------------

FIXTURES = pathlib.Path(__file__).parent / "fixtures" / "review-lines.txt"


def review_fixtures():
    """The exact bytes `review` renders, one block per case."""
    cases: dict[str, list[str]] = {}
    current = None
    for line in FIXTURES.read_text(encoding="utf-8").splitlines():
        if line.startswith("## "):
            current = line[3:].strip()
            cases[current] = []
        elif current is None:
            continue  # the header comment
        else:
            cases[current].append(line)
    return {key: "\n".join(body) for key, body in cases.items()}


class FakeSuggestion:
    """Lane P's `Suggestion` dataclass, as this module reads it."""

    def __init__(self, sid, text, quote, session, date):
        self.id = sid
        self.text = text
        self.quote = quote
        self.session = session
        self.date = date


class FakeSaveResult:
    """What lane P's `inbox.accept` hands back — the library's own SaveResult."""

    def __init__(self, mid, text, target="MEMORY.md"):
        self.id = mid
        self.text = text
        self.target = target


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


class FakeInbox:
    """`amplifier_memory.inbox`'s five functions, at lane P's signatures.

    Records every call, so a test can assert what the adapter passed the
    library rather than only what it printed.
    """

    def __init__(self, items=None, explode=None):
        self.items = list(items if items is not None else WAITING)
        self.explode = explode
        self.calls = []

    def pending(self, home):
        self.calls.append(("pending", home))
        if isinstance(self.explode, tuple) and self.explode[0] == "pending":
            raise self.explode[1]
        return list(self.items)

    def render_review_page(self, page=1, home=None):
        """The seam the tool calls for a page — deliberately NOT a rendering.

        Every page assertion in this file goes through the real library against a
        real temp inbox (`seeded_inbox`); this stand-in exists only so the R2 and
        error-path tests can prove that a *read* was allowed, and returns a marker
        no fixture will ever match.
        """
        self.calls.append(("render_review_page", page, home))
        return f"<{len(self.items)} waiting>"

    def accept(self, sid, home, *, session_id):
        self.calls.append(("accept", sid, home, session_id))
        if isinstance(self.explode, tuple) and self.explode[0] == "accept":
            raise self.explode[1]
        item = next(s for s in self.items if s.id == sid)
        self.items = [s for s in self.items if s.id != sid]
        return FakeSaveResult("m-001", item.text)

    def decline(self, sid, home):
        self.calls.append(("decline", sid, home))
        self.items = [s for s in self.items if s.id != sid]

    def skip(self, sid, home):
        self.calls.append(("skip", sid, home))


def install_inbox(monkeypatch, inbox):
    monkeypatch.setattr(amplifier_memory, "inbox", inbox, raising=False)
    return inbox


def remove_inbox(monkeypatch):
    monkeypatch.delattr(amplifier_memory, "inbox", raising=False)


# §6 as amended 2026-09-07 — the seeded inbox every page assertion below is
# rendered from. Spelled identically in `conformance/session/tool/run.py`; the
# shared fixture file is what keeps the two spellings identical.
SEED_SESSION = "d9c3bf04"
SEED_DATE = "2026-09-07"


def seeded_inbox(home, n):
    """`n` real items in a real inbox, appended through the library's own `append`.

    Not a stand-in and not pre-rendered text: `render_review_page` reads `inbox.md`
    back off the disk, which is the only way a page test can prove the quote it
    prints is the quote the file carries.
    """
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


async def test_review_page_one_of_seventeen_is_six_items_of_markdown(store):
    """§6: 17 waiting is 6 · 6 · 5, and page 1 says which page it is."""
    seeded_inbox(store, 17)
    result = await tool(messages=[]).execute({"operation": "review"})
    print("=== /memory review (page omitted) ===")
    print(result.output)
    print("=== end ===")

    assert result.success is True
    assert result.output == review_fixtures()["page_one_of_seventeen"]
    assert result.output.splitlines()[0] == "**17 suggestions waiting** \u2014 page 1 of 3"
    assert len([line for line in result.output.splitlines() if line.startswith("**")]) == 7


async def test_explicit_list_equals_omitted_none_and_empty_review_actions(store):
    """An explicit read action is the compatible omitted-action listing, byte for byte."""
    seeded_inbox(store, 17)
    calls = [
        {"operation": "review"},
        {"operation": "review", "action": None},
        {"operation": "review", "action": ""},
        {"operation": "review", "action": "list"},
    ]

    results = [await tool(messages=[]).execute(call) for call in calls]
    print(
        "review listing actions:",
        [
            (call.get("action"), result.output.splitlines()[0])
            for call, result in zip(calls, results)
        ],
    )

    assert all(result.success for result in results)
    assert [result.output for result in results] == [
        review_fixtures()["page_one_of_seventeen"]
    ] * len(calls)


async def test_a_page_quotes_the_inbox_byte_for_byte_and_never_truncates(store):
    """The quote is the whole trust story: it is printed whole or the page is a lie."""
    seeded_inbox(store, 17)
    page = await tool(messages=[]).execute({"operation": "review", "page": 2})
    raw = (store / "inbox.md").read_text(encoding="utf-8")
    quoted = [line[2:].strip('"') for line in page.output.splitlines() if line.startswith('> "')]
    print("quotes on page 2:", len(quoted))
    print(quoted[0])

    assert len(quoted) == 6
    for quote in quoted:
        assert f'quote: "{quote}"' in raw
        assert not quote.endswith("\u2026")


async def test_review_page_three_is_the_short_page_and_offers_no_next(store):
    seeded_inbox(store, 17)
    result = await tool(messages=[]).execute({"operation": "review", "action": "list", "page": 3})
    print(result.output)

    assert result.output == review_fixtures()["page_three_of_seventeen"]
    assert "`next`" not in result.output.splitlines()[-1]


async def test_eight_items_are_one_page_and_say_no_page_at_all(store):
    """§6: up to 8 is one page — and a `— page 1 of 1` suffix would be noise."""
    seeded_inbox(store, 8)
    result = await tool(messages=[]).execute({"operation": "review"})
    print(result.output.splitlines()[0])

    assert result.output == review_fixtures()["page_of_eight"]
    assert result.output.splitlines()[0] == "**8 suggestions waiting**"


async def test_a_page_past_the_last_one_is_refused_and_names_the_last(store):
    seeded_inbox(store, 17)
    result = await tool(messages=[]).execute({"operation": "review", "page": 4})
    print(repr(result.output))

    assert result.success is False
    assert result.output == review_fixtures()["page_beyond"]


async def test_a_bare_number_is_a_position_and_is_refused_with_the_pages_ids(store):
    """§6: ids are the only names. Nothing is written, and the inbox is untouched."""
    seeded_inbox(store, 17)
    before = (store / "inbox.md").read_bytes()
    result = await tool(messages=[]).execute({"operation": "review", "action": "accept", "id": "2"})
    print(repr(result.output))

    assert result.success is False
    assert result.output == review_fixtures()["position"]
    assert "\n" not in result.output
    assert (store / "inbox.md").read_bytes() == before
    assert (store / "MEMORY.md").read_text(encoding="utf-8") == ""


async def test_review_of_an_empty_inbox_counts_to_nothing(store, monkeypatch):
    """§6 bans a zero-valued count: an empty inbox says what is true instead."""
    result = await tool(messages=[]).execute({"operation": "review", "action": "list"})
    print(repr(result.output))
    assert result.success is True
    assert result.output == review_fixtures()["listing_none"]


async def test_a_full_schema_payload_can_explicitly_list_a_requested_page(store):
    """A strict-shaped caller can supply every field without changing a read into a write."""
    seeded_inbox(store, 17)
    payload = {
        "operation": "review",
        "action": "list",
        "text": "ignored because this is a read",
        "quote": "ignored because this is a read",
        "writer": "assistant",
        "id": "s-001",
        "page": 3,
        "topic": "ignored",
        "topic_purpose": "ignored",
        "batch_of": 2,
    }
    before = {
        name: (store / name).read_bytes() for name in ("MEMORY.md", "inbox.md", "declined.md")
    }
    head = _git.head(store)

    result = await tool(messages=[]).execute(payload)
    print("full review-list payload ->", result.output.splitlines()[0])

    assert set(payload) == set(mod.INPUT_SCHEMA["properties"])
    assert mod.INPUT_SCHEMA["required"] == ["operation"]
    assert result.success is True
    assert result.output == review_fixtures()["page_three_of_seventeen"]
    assert {name: (store / name).read_bytes() for name in before} == before
    assert _git.head(store) == head


async def test_the_empty_inbox_line_is_the_librarys_own(store):
    """One sentence, one home: the tool's constant and the library's page agree."""
    print(mod.REVIEW_EMPTY, "|", amplifier_memory.inbox.REVIEW_EMPTY)
    assert mod.REVIEW_EMPTY == amplifier_memory.inbox.REVIEW_EMPTY


async def test_accept_renders_the_save_receipt_with_its_provenance(store, monkeypatch):
    inbox = install_inbox(monkeypatch, FakeInbox())
    result = await tool(messages=[]).execute(
        {"operation": "review", "action": "accept", "id": "s-042"}
    )
    print("=== accept receipt ===")
    print(result.output)
    print("library calls:", inbox.calls)

    assert result.success is True
    assert result.output == review_fixtures()["accept"]
    # The library did the writing, with the session id only this process knows.
    assert ("accept", "s-042", store, "test-session") in inbox.calls


async def test_decline_says_it_is_final_and_how_to_reverse_it(store, monkeypatch):
    inbox = install_inbox(monkeypatch, FakeInbox())
    result = await tool(messages=[]).execute(
        {"operation": "review", "action": "decline", "id": "s-042"}
    )
    print(repr(result.output))
    assert result.success is True
    assert result.output == review_fixtures()["decline"]
    assert ("decline", "s-042", store) in inbox.calls


async def test_skip_leaves_the_item_waiting(store, monkeypatch):
    inbox = install_inbox(monkeypatch, FakeInbox())
    result = await tool(messages=[]).execute(
        {"operation": "review", "action": "skip", "id": "s-042"}
    )
    print(repr(result.output))
    assert result.success is True
    assert result.output == review_fixtures()["skip"]
    assert ("skip", "s-042", store) in inbox.calls
    assert [s.id for s in inbox.items] == ["s-042", "s-043", "s-044"]


async def test_an_unknown_suggestion_id_names_what_is_waiting(store, monkeypatch):
    """Ids are the only names — never a near-miss guess (session.v2 §6)."""
    inbox = install_inbox(monkeypatch, FakeInbox())
    result = await tool(messages=[]).execute(
        {"operation": "review", "action": "accept", "id": "s-999"}
    )
    print(repr(result.output))
    assert result.success is False
    assert "\n" not in result.output
    assert result.output == review_fixtures()["unknown"]
    # Nothing was attempted against the library beyond the read.
    assert [call[0] for call in inbox.calls] == ["pending"]


async def test_an_action_on_an_empty_inbox_is_the_empty_line(store, monkeypatch):
    install_inbox(monkeypatch, FakeInbox([]))
    result = await tool(messages=[]).execute(
        {"operation": "review", "action": "decline", "id": "s-042"}
    )
    print(repr(result.output))
    assert result.success is False
    assert result.output == review_fixtures()["listing_none"]


@pytest.mark.parametrize("action", ["accept", "decline", "skip"])
@pytest.mark.parametrize("missing_id", [None, ""])
async def test_missing_id_review_actions_refuse_without_changing_the_store(
    store, action, missing_id
):
    """Malformed action calls stay refusals; no implicit listing or write is permitted."""
    seeded_inbox(store, 1)
    before = {
        name: (store / name).read_bytes() for name in ("MEMORY.md", "inbox.md", "declined.md")
    }
    head = _git.head(store)

    result = await tool(messages=[]).execute(
        {"operation": "review", "action": action, "id": missing_id}
    )
    print(f"{action} with id={missing_id!r} -> {result.output!r}")

    assert result.success is False
    assert result.output == f"refused: review {action} needs the suggestion id, e.g. s-042"
    assert {name: (store / name).read_bytes() for name in before} == before
    assert _git.head(store) == head


async def test_a_deterministic_missing_id_correction_lists_the_requested_page(store):
    """This scripted sequence proves the tool surface, not that a model self-corrects."""
    seeded_inbox(store, 17)
    before = {
        name: (store / name).read_bytes() for name in ("MEMORY.md", "inbox.md", "declined.md")
    }
    head = _git.head(store)
    memory = tool(messages=[])

    mistaken = await memory.execute({"operation": "review", "action": "skip", "id": ""})
    corrected = await memory.execute({"operation": "review", "action": "list", "page": 3})
    print(
        "deterministic missing-id correction:",
        mistaken.output,
        "->",
        corrected.output.splitlines()[0],
    )

    assert mistaken.success is False
    assert mistaken.output == "refused: review skip needs the suggestion id, e.g. s-042"
    assert corrected.success is True
    assert corrected.output == review_fixtures()["page_three_of_seventeen"]
    assert {name: (store / name).read_bytes() for name in before} == before
    assert _git.head(store) == head


async def test_review_without_the_library_says_which_command_fixes_it(store, monkeypatch):
    remove_inbox(monkeypatch)
    result = await tool(messages=[]).execute({"operation": "review", "action": "list"})
    print(repr(result.output))
    assert result.success is False
    assert result.output == review_fixtures()["unavailable"]


async def test_an_unknown_review_action_is_refused_in_one_line(store, monkeypatch):
    install_inbox(monkeypatch, FakeInbox())
    result = await tool(messages=[]).execute(
        {"operation": "review", "action": "delete", "id": "s-042"}
    )
    print(repr(result.output))
    assert result.success is False
    assert "list, accept, decline, skip" in result.output


async def test_accept_and_decline_are_refused_in_a_sub_agent_session(store, monkeypatch):
    """session.v2 R2 — a sub-agent may read the inbox and may not write."""
    inbox = install_inbox(monkeypatch, FakeInbox())
    sub = tool(messages=[], parent_id="parent-session")
    accepted = await sub.execute({"operation": "review", "action": "accept", "id": "s-042"})
    declined = await sub.execute({"operation": "review", "action": "decline", "id": "s-042"})
    listed = await sub.execute({"operation": "review", "action": "list"})

    print("sub-agent accept ->", accepted.output)
    print("sub-agent decline ->", declined.output)
    print("sub-agent list ->", listed.output.splitlines()[0])

    for result in (accepted, declined):
        assert result.success is False
        assert "R2" in result.output
        assert "\n" not in result.output
    assert listed.success is True
    assert [call[0] for call in inbox.calls] == [
        "pending",
        "pending",
        "pending",
        "render_review_page",
    ]


async def test_a_library_failure_is_one_line_and_a_log_line(store, tmp_path, monkeypatch):
    """§10 — a signature that moved under us costs a sentence, not a session."""
    log = tmp_path / "memory-errors.log"
    monkeypatch.setenv("AMPLIFIER_MEMORY_ERROR_LOG", str(log))
    install_inbox(
        monkeypatch, FakeInbox(explode=("accept", TypeError("accept() got an unexpected kwarg")))
    )
    result = await tool(messages=[]).execute(
        {"operation": "review", "action": "accept", "id": "s-042"}
    )
    print(repr(result.output))
    print("error log:", log.read_text(encoding="utf-8").strip() if log.exists() else "(none)")

    assert result.success is False
    assert result.output == f"not saved — nothing changed, nothing lost. Details: {log}"
    assert "unexpected kwarg" in log.read_text(encoding="utf-8")


async def test_review_is_one_word_in_the_enum_and_one_clause_of_parameter_text(store):
    """§11: the review procedure lives in the skill, not on every model request."""
    print("operations:", mod.INPUT_SCHEMA["properties"]["operation"]["enum"])
    print("actions:", mod.INPUT_SCHEMA["properties"]["action"]["enum"])
    print("action clause:", mod.INPUT_SCHEMA["properties"]["action"]["description"])
    assert "review" in mod.INPUT_SCHEMA["properties"]["operation"]["enum"]
    assert mod.INPUT_SCHEMA["properties"]["action"]["enum"] == ["list", "accept", "decline", "skip"]
    assert mod.INPUT_SCHEMA["required"] == ["operation"]
    clause = mod.INPUT_SCHEMA["properties"]["action"]["description"]
    assert clause.count(".") <= 1 and len(clause.splitlines()) == 1
    assert "review" not in mod.DESCRIPTION


def test_memory_skill_dispatches_explicit_listing_and_scopes_missing_id_recovery():
    """The recovery sequence is deterministic guidance, not proof a model chose it."""
    skill = pathlib.Path(__file__).parents[3] / "skills" / "memory" / "SKILL.md"
    text = skill.read_text(encoding="utf-8")

    for needle in (
        '`review` | `memory(operation="review", action="list")`',
        '`review 2` | `memory(operation="review", action="list", page=2)`',
        "Exactly once, correct a first call",
        "the original request was `review` or `review <page>`",
        "Preserve the requested page",
        "A second failure is terminal.",
        "Never use this correction for a user-requested `accept`, `decline`, or `skip`",
        "or inspect files to route around a refusal.",
    ):
        assert needle in text


@pytest.mark.skipif(
    not hasattr(amplifier_memory, "inbox"),
    reason="amplifier_memory.inbox is not in this build — lane P owns the library half; "
    "the surface above is proven against a fake at lane P's published signatures",
)
async def test_accept_writes_through_the_real_library(store):
    """The end-to-end arm: the real inbox, the real writer, a real MEMORY.md."""
    home = amplifier_memory.store_home()
    (home / "inbox.md").write_text(
        "- [s-001] never use tabs in YAML; two-space indentation\n"
        '  quote: "never use tabs in YAML files I ask you to write"'
        "  session: bc214bdf  2026-09-05\n",
        encoding="utf-8",
    )
    memory = tool(messages=[])
    listed = await memory.execute({"operation": "review"})
    print("=== real listing ===")
    print(listed.output)
    accepted = await memory.execute({"operation": "review", "action": "accept", "id": "s-001"})
    print("=== real accept ===")
    print(accepted.output)
    print("MEMORY.md:", (home / "MEMORY.md").read_text(encoding="utf-8"))

    assert accepted.success is True
    assert accepted.output.splitlines()[2] == "  suggested from session bc214bdf, accepted by you"
    assert "never use tabs in YAML" in (home / "MEMORY.md").read_text(encoding="utf-8")


# --------------------------------------------------------------------------
# session.v4 §6 — the bare `/memory` overview: at most four lines, suggestions
# first. The figures are the library's (`StatusReport`), the same report
# `amplifier-memory status` renders; this operation is the second rendering.
# --------------------------------------------------------------------------


def inbox_items(store, count, first=1):
    """`count` well-formed inbox items — suggestions.v2 §4's two lines each."""
    lines = []
    for n in range(first, first + count):
        lines.append(f"- [s-{n:03d}] preference number {n}")
        lines.append(f'  quote: "say it {n}"  session: bc214bdf  2026-09-05')
    (store / "inbox.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


async def four_memories_six_written_two_forgotten_two_cited(store):
    """Six saves, two forgets, two citations — a store whose figures are known.

    Written and forgotten come from the store's git history and citations from
    `usage.jsonl` (cli.v2 §2), so they are made the only way they are ever made:
    by saving, forgetting and citing.
    """
    memory = tool(messages=[user(f"Preference {n}.") for n in range(1, 7)])
    for n in range(1, 7):
        result = await memory.execute(
            {"operation": "save", "text": f"Preference {n}.", "writer": "human"}
        )
        assert result.success, result.output
    for mid in ("m-005", "m-006"):
        assert (await memory.execute({"operation": "forget", "id": mid})).success
    for mid in ("m-001", "m-002"):
        assert (await memory.execute({"operation": "cite", "id": mid})).success
    return memory


async def test_overview_is_four_lines_with_suggestions_first(store):
    memory = await four_memories_six_written_two_forgotten_two_cited(store)
    inbox_items(store, 34)

    result = await memory.execute({"operation": "overview"})
    print("=== bare /memory ===")
    print(result.output)
    report = amplifier_memory.status()
    print(
        f"status(): memories={report.memories} topics={report.topics} "
        f"written_7={report.written_7} forgotten_7={report.forgotten_7} "
        f"cited_7={report.cited_7} pending={report.pending_suggestions}"
    )

    assert result.success is True
    assert result.output.splitlines() == [
        "34 suggestions waiting. /memory review to walk them.",
        "4 memories. /memory list to see them.",
        "last 7 days: 6 written, 2 forgotten, 2 cited.",
        "/memory list \u00b7 review \u00b7 forget <id> \u00b7 edit <id> <text> \u00b7 help",
    ]
    # §6's own numbers, and the only claim that matters about them: they are the
    # figures `amplifier-memory status` prints, not a second count.
    assert (report.memories, report.topics) == (4, 0)
    assert (report.written_7, report.forgotten_7, report.cited_7) == (6, 2, 2)
    assert report.pending_suggestions == 34


def test_the_overview_renders_the_contract_s_own_example_byte_for_byte():
    """§6's four lines, from a report built by hand — the fixture, not a store.

    A store cannot hold 4 memories after 6 writes and 1 forget, so the clause's
    own example is asserted here, where the figures can be exactly its own.
    """
    report = amplifier_memory.StatusReport(
        home=pathlib.Path("/nowhere"),
        memories=4,
        topics=0,
        written_7=6,
        forgotten_7=1,
        cited_7=2,
        pending_suggestions=34,
    )
    print(report.render_overview())
    assert report.render_overview().splitlines() == [
        "34 suggestions waiting. /memory review to walk them.",
        "4 memories. /memory list to see them.",
        "last 7 days: 6 written, 1 forgotten, 2 cited.",
        "/memory list \u00b7 review \u00b7 forget <id> \u00b7 edit <id> <text> \u00b7 help",
    ]


async def test_overview_with_an_empty_inbox_has_no_suggestions_line_and_no_review(store):
    memory = await four_memories_six_written_two_forgotten_two_cited(store)

    result = await memory.execute({"operation": "overview"})
    print("=== bare /memory, empty inbox ===")
    print(result.output)
    lines = result.output.splitlines()

    assert len(lines) == 3
    assert lines == [
        "4 memories. /memory list to see them.",
        "last 7 days: 6 written, 2 forgotten, 2 cited.",
        "/memory list \u00b7 forget <id> \u00b7 edit <id> <text> \u00b7 help",
    ]
    assert "review" not in result.output


async def test_overview_with_one_waiting_item_is_singular(store):
    memory = await four_memories_six_written_two_forgotten_two_cited(store)
    inbox_items(store, 1)

    result = await memory.execute({"operation": "overview"})
    print("=== bare /memory, one waiting ===")
    print(result.output)

    assert result.output.splitlines()[0] == "1 suggestion waiting. /memory review to walk it."
    assert result.output.splitlines()[-1].startswith("/memory list \u00b7 review \u00b7")


async def test_overview_of_an_empty_store_counts_nothing_to_zero(store):
    result = await tool(messages=[]).execute({"operation": "overview"})
    print("=== bare /memory, empty store ===")
    print(result.output)

    assert result.output.splitlines() == [
        "no memories yet \u2014 /remember <text> to add one.",
        "/memory list \u00b7 forget <id> \u00b7 edit <id> <text> \u00b7 help",
    ]
    for zero in ("0 memories", "0 topics", "0 written", "0 forgotten", "0 cited"):
        assert zero not in result.output


async def test_overview_of_a_missing_store_is_one_line_with_the_remedy(tmp_path, monkeypatch):
    monkeypatch.setenv("AMPLIFIER_MEMORY_HOME", str(tmp_path / "nowhere"))
    result = await tool(messages=[]).execute({"operation": "overview"})
    print("no store ->", result.output)

    assert result.success is False
    assert "\n" not in result.output
    assert "amplifier-memory init" in result.output


async def test_overview_reads_the_same_figures_status_reads(store, monkeypatch):
    """AGENTS.md 11: one home for the numbers. The operation renders a report."""
    memory = await four_memories_six_written_two_forgotten_two_cited(store)
    real = amplifier_memory.status
    calls = []

    def spy(*args, **kwargs):
        calls.append((args, kwargs))
        return real(*args, **kwargs)

    monkeypatch.setattr(amplifier_memory, "status", spy)
    result = await memory.execute({"operation": "overview"})
    print("status() calls made by one overview:", len(calls))
    print(result.output)

    assert len(calls) == 1, "the overview counted something itself"


# --------------------------------------------------------------------------
# session.v4 §12 — which instance a session uses is configuration
# --------------------------------------------------------------------------


def instance_tool(home, messages=None, parent_id=None, session_id="test-session"):
    """A tool whose mount plan names `home` — §12's `config: home: <path>`."""
    context = FakeContext(messages) if messages is not None else None
    return mod.MemoryTool(FakeCoordinator(session_id, parent_id, context), {"home": str(home)})


def set_enabled(home, enabled):
    from amplifier_memory import llm_config

    (home / "config.yaml").write_text(llm_config.default_body(enabled=enabled), encoding="utf-8")


async def test_mount_plan_home_chooses_the_instance(store, tmp_path):
    """§12 — the plan's instance is read and written, not the environment's."""
    planned = tmp_path / "planned"
    amplifier_memory.init(planned)

    result = await instance_tool(planned, [user("never use emoji")]).execute(
        {"operation": "save", "text": "Never use emoji.", "quote": "never use emoji"}
    )

    print(result.output)
    assert result.success
    assert "Never use emoji." in (planned / "MEMORY.md").read_text(encoding="utf-8")
    assert "Never use emoji." not in (store / "MEMORY.md").read_text(encoding="utf-8")


async def test_no_home_in_the_plan_behaves_exactly_as_today(store):
    """§12 — "absent, the store contract's resolution order decides"."""
    result = await tool([user("never use emoji")]).execute(
        {"operation": "save", "text": "Never use emoji.", "quote": "never use emoji"}
    )

    print(result.output)
    assert result.success
    assert "Never use emoji." in (store / "MEMORY.md").read_text(encoding="utf-8")


@pytest.mark.parametrize(
    "call",
    [
        {"operation": "save", "text": "Never use emoji.", "quote": "never use emoji"},
        {"operation": "edit", "id": "m-001", "text": "x", "quote": "never use emoji"},
        {"operation": "forget", "id": "m-001"},
        {"operation": "list"},
        {"operation": "overview"},
        {"operation": "cite", "id": "m-001"},
        {"operation": "review"},
    ],
)
async def test_an_inert_instance_refuses_every_operation_in_one_line(store, tmp_path, call):
    """§12 — "refuses every operation with one line", and writes nothing."""
    inert = tmp_path / "inert"
    amplifier_memory.init(inert)
    set_enabled(inert, False)
    before = (inert / "MEMORY.md").read_text(encoding="utf-8")

    result = await instance_tool(inert, [user("never use emoji")]).execute(call)

    print(f"{call['operation']}: {result.output!r}")
    assert not result.success
    assert result.output == f"memory is disabled for this instance ({inert}: enabled: false)."
    assert "\n" not in result.output
    assert (inert / "MEMORY.md").read_text(encoding="utf-8") == before


async def test_the_inert_refusal_is_the_librarys_own_sentence(store, tmp_path):
    """One sentence, not three paraphrases: the tool's line IS the library's."""
    inert = tmp_path / "inert"
    amplifier_memory.init(inert)
    set_enabled(inert, False)

    refused = await instance_tool(inert, [user("never use emoji")]).execute({"operation": "list"})
    with pytest.raises(amplifier_memory.InstanceDisabled) as raised:
        amplifier_memory.save(
            "x", "never use emoji", "assistant", "s", ["never use emoji"], home=inert
        )

    print("tool:   ", refused.output)
    print("library:", str(raised.value))
    assert refused.output == str(raised.value)


async def test_an_inert_instance_advertises_nothing(store, tmp_path):
    """§12 — neither command is advertised; the description is §12's line instead."""
    inert = tmp_path / "inert"
    amplifier_memory.init(inert)
    set_enabled(inert, False)

    off = instance_tool(inert)
    print("description:", off.description)
    assert off.description == f"memory is disabled for this instance ({inert}: enabled: false)."
    assert off.description != mod.DESCRIPTION


async def test_an_inert_instance_is_still_mounted(store, tmp_path):
    """§12's second half — "where a plan requires it to be" it is there, refusing.

    The IRON LAW: a plan that names this module requires the tool to be mounted,
    and a silent skip would fail protocol compliance for every agent composing
    this behavior.
    """
    inert = tmp_path / "inert"
    amplifier_memory.init(inert)
    set_enabled(inert, False)

    coordinator = FakeCoordinator()
    await mod.mount(coordinator, {"home": str(inert)})

    print("mounted:", [(m["mount_point"], m["name"]) for m in coordinator.mounted])
    assert coordinator.mount_points["tools"]["memory"].name == "memory"


async def test_the_same_instance_enabled_is_an_ordinary_session(store, tmp_path):
    """The discriminating arm: the same file, `enabled: true`."""
    live = tmp_path / "live"
    amplifier_memory.init(live)
    set_enabled(live, True)

    on = instance_tool(live, [user("never use emoji")])
    result = await on.execute(
        {"operation": "save", "text": "Never use emoji.", "quote": "never use emoji"}
    )

    print(result.output)
    assert result.success
    assert on.description == mod.DESCRIPTION


# --------------------------------------------------------------------------
# session.v4 §13 — which sessions have a human in them
# --------------------------------------------------------------------------


@pytest.mark.parametrize("origin", ["worker", "recipe", "agent", "eval"])
@pytest.mark.parametrize(
    "call, verb",
    [
        (
            {"operation": "save", "text": "Never use emoji.", "quote": "never use emoji"},
            "never saves",
        ),
        (
            {
                "operation": "edit",
                "id": "m-001",
                "text": "Never use emoji anywhere.",
                "quote": "never use emoji",
            },
            "never writes to the store",
        ),
        ({"operation": "forget", "id": "m-001"}, "never writes to the store"),
    ],
)
async def test_a_non_human_session_may_not_write(store, monkeypatch, origin, call, verb):
    """§13 — save, edit and forget refused, one line, naming the origin."""
    monkeypatch.setenv("AMPLIFIER_SESSION_ORIGIN", origin)

    result = await tool([user("never use emoji")]).execute(call)

    print(f"{origin} {call['operation']}: {result.output!r}")
    assert not result.success
    assert result.output.startswith(
        f"refused: session.v4 \u00a713 \u2014 a {origin} session {verb}; "
    )
    assert "\n" not in result.output


async def test_a_non_human_session_may_still_read(store, monkeypatch):
    """§13 refuses writing, not reading — the memories still apply."""
    monkeypatch.setenv("AMPLIFIER_SESSION_ORIGIN", "worker")

    amplifier_memory.inbox.append(
        store,
        [
            amplifier_memory.inbox.Candidate(
                text="Never use emoji.",
                quote="never use emoji",
                session="abcd1234",
                date="2026-09-07",
            )
        ],
    )
    result = await tool([]).execute({"operation": "review", "action": "list"})

    print(result.output)
    assert result.success
    assert "**1 suggestion waiting**" in result.output


@pytest.mark.parametrize("action", ["accept", "decline"])
async def test_a_non_human_session_may_not_answer_a_suggestion(store, monkeypatch, action):
    """§13 — accept and decline write under other names (the reason R2 covers them too)."""
    amplifier_memory.inbox.append(
        store,
        [
            amplifier_memory.inbox.Candidate(
                text="Never use emoji.",
                quote="never use emoji",
                session="abcd1234",
                date="2026-09-07",
            )
        ],
    )
    monkeypatch.setenv("AMPLIFIER_SESSION_ORIGIN", "worker")

    result = await tool([user("never use emoji")]).execute(
        {"operation": "review", "action": action, "id": "s-001"}
    )

    print(result.output)
    assert not result.success
    assert "\u00a713" in result.output and "worker" in result.output


async def test_an_unset_origin_writes_exactly_as_today(store, monkeypatch):
    """§13 — "a launcher that exports nothing is treated as human, exactly as today"."""
    monkeypatch.delenv("AMPLIFIER_SESSION_ORIGIN", raising=False)

    result = await tool([user("never use emoji")]).execute(
        {"operation": "save", "text": "Never use emoji.", "quote": "never use emoji"}
    )

    print(result.output)
    assert result.success


async def test_the_origin_refusal_is_r2s_refusal_with_the_origin_named(store, monkeypatch):
    """§13 — "exactly the way it refuses a sub-agent today … naming the origin"."""
    monkeypatch.delenv("AMPLIFIER_SESSION_ORIGIN", raising=False)
    sub = await tool([user("never use emoji")], parent_id="parent").execute(
        {"operation": "save", "text": "Never use emoji.", "quote": "never use emoji"}
    )
    monkeypatch.setenv("AMPLIFIER_SESSION_ORIGIN", "worker")
    worker = await tool([user("never use emoji")]).execute(
        {"operation": "save", "text": "Never use emoji.", "quote": "never use emoji"}
    )

    print("R2: ", sub.output)
    print("§13:", worker.output)
    assert (
        sub.output.replace("R2", "\u00a713")
        .replace("sub-agent", "worker")
        .replace("a root session", "a session")
        == worker.output
    )


async def test_a_sub_agent_of_a_worker_session_is_still_refused_as_a_sub_agent(store, monkeypatch):
    """R2 is asked first: it is the narrower fact, and it is still true."""
    monkeypatch.setenv("AMPLIFIER_SESSION_ORIGIN", "worker")

    result = await tool([user("never use emoji")], parent_id="parent").execute(
        {"operation": "save", "text": "Never use emoji.", "quote": "never use emoji"}
    )

    print(result.output)
    assert "R2" in result.output
