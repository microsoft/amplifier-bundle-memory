"""Tests for tool-memory — session.v1 §5, §6, R2, and the refusal relay.

Every test that stands as evidence prints what it measured; run with `-s` to
see it. Nothing here touches a real store: `AMPLIFIER_MEMORY_HOME` points at a
tmp_path in every test, and `AMPLIFIER_PROJECTS_HOME` at another, so the
transcript fallback never reads the human's real sessions either.
"""

import json
from datetime import datetime

import amplifier_memory
import pytest

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


IDS_RULE = (
    "Ids are the only names. A bare number N means m-00N, never a position in a list. "
    "Never guess an id: if it cannot be resolved, list the current ids and ask."
)
NO_RESTATE_RULE = (
    "Never restate a memory receipt or listing in your own words; "
    "the tool result is what the human reads."
)


def test_description_is_short_and_carries_both_halves_of_the_contract():
    lines = mod.DESCRIPTION.splitlines()
    print(f"description: {len(lines)} lines")
    print(mod.DESCRIPTION)

    assert len(lines) <= 20
    assert "SAVE when" in mod.DESCRIPTION  # §3
    assert "DO NOT SAVE" in mod.DESCRIPTION  # §4
    assert 'Saved memory m-017: "<text>" — /forget m-017 to undo.' in mod.DESCRIPTION  # §3


def test_description_carries_the_ids_rule_and_the_no_restate_rule_verbatim():
    """Both were typed by hand into the goal; a paraphrase is a different rule."""
    assert IDS_RULE in mod.DESCRIPTION
    assert NO_RESTATE_RULE in mod.DESCRIPTION


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
    assert "You can save wording you drafted." in mod.DESCRIPTION


def test_operations_are_exactly_save_forget_list():
    assert mod.INPUT_SCHEMA["properties"]["operation"]["enum"] == ["save", "forget", "list"]


# --------------------------------------------------------------------------
# Acceptance 3 — session.v1 §5: the human-turn check, both arms
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
    assert result.output.startswith('Saved memory m-001: "Never use emoji in commit messages."')
    assert "— /forget m-001 to undo." in result.output.splitlines()[0]
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
    session_dir = (
        tmp_path
        / "projects"
        / mod.project_slug()
        / "sessions"
        / "test-session"
    )
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
# Acceptance 4 — session.v1 R2: a sub-agent never writes
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
    assert "0 memories" in result.output


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
    lines = [f"- [m-{n:03d}] filler {n}" for n in range(1, amplifier_memory.store.MEMORY_LINE_CAP + 1)]
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
        "/forget one you no longer need, or ask me to move a group into a topic file."
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
    synthetic = f"Use the load_skill tool to load the skill \"remember\". The user's input is: {typed}"
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
        "Forgot m-001.",
        "Never use emoji.",
        "still in git: amplifier-memory why m-001",
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
        "2 memories",
        "- [m-001] Never use emoji.",
        "- [m-002] Always squash before merging.",
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
    assert result.output.splitlines()[0] == "1 memory"


async def test_topics_are_counted_only_when_there_are_some(store):
    memory = tool(messages=[user("never use emoji"), user("two-space indent in YAML")])
    await memory.execute(
        {"operation": "save", "text": "Never use emoji.", "quote": "never use emoji"}
    )
    before = await memory.execute({"operation": "list"})
    print("no topics ->", before.output.splitlines()[0])
    assert before.output.splitlines()[0] == "1 memory"

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
    assert after.output.splitlines()[0] == "1 memory, 1 topic"


async def test_empty_list_says_what_to_do(store):
    result = await tool(messages=[]).execute({"operation": "list"})
    print("empty list ->\n" + result.output)
    assert result.output.splitlines() == [
        "0 memories",
        "No memories yet — /remember <text> to add one.",
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
        f'Saved memory m-001: "{typed}" — /forget m-001 to undo.',
        "your words, verbatim",
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
        (
            'Saved memory m-001: "When I say explain, go long with headers." '
            "— /forget m-001 to undo."
        ),
        'my wording, your go-ahead: "remember these for me"',
    ]
    assert "committed " not in result.output


async def test_a_batch_of_drafted_lines_reports_itself_once_at_the_end(store):
    """Acceptance 3: three saves, one approval phrase, the last result carries all."""
    approval = "remember these for me"
    memory = tool(messages=[user(f"Great, {approval}")])
    outputs = []
    for text in ("Lead with the next action.", "Number multi-step work.", "Cap lists at five."):
        result = await memory.execute(
            {"operation": "save", "text": text, "quote": approval, "writer": "assistant"}
        )
        outputs.append(result.output)
        print(f"--- save {len(outputs)} ---\n{result.output}")

    last = outputs[-1].splitlines()
    assert last[0] == 'Saved memory m-003: "Cap lists at five." — /forget m-003 to undo.'
    assert last[1] == (
        'Saved 3 memories — my wording, your go-ahead: "remember these for me". '
        "Reword any line and I'll replace it; /forget <id> drops one."
    )
    assert last[2:] == [
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
    assert second.output.splitlines()[1] == 'my wording, your go-ahead: "and this one too"'


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
    assert pointer.output.splitlines()[1] == f'my wording, your go-ahead: "{said}"'
    assert "Saved 3 memories" not in pointer.output


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


async def test_any_other_failure_says_nothing_was_lost_and_logs_a_line(store, tmp_path, monkeypatch):
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
    assert result.output == (
        f"not saved — nothing changed, nothing lost. Details: {log}"
    )
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
