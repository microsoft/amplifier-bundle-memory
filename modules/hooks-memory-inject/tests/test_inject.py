"""Tests for hooks-memory-inject — session.v1 §1, §2, §9, §10.

Every test that stands as evidence prints what it measured; run with
`-s` to see it. Nothing here touches a real store: `AMPLIFIER_MEMORY_HOME`
and `AMPLIFIER_MEMORY_ERROR_LOG` are pointed at a tmp_path in every test.
"""

import os
import pathlib
import re
import stat

import pytest

import amplifier_module_hooks_memory_inject as mod

# --------------------------------------------------------------------------
# Fakes — a hook registry and a coordinator, no amplifier-core session needed
# --------------------------------------------------------------------------


class FakeHooks:
    def __init__(self):
        self.registrations = []

    def register(self, event, handler, priority=0, name=None):
        self.registrations.append(
            {"event": event, "handler": handler, "priority": priority, "name": name}
        )


class FakeCoordinator:
    def __init__(self, session_id="test-session"):
        self.hooks = FakeHooks()
        self.session_id = session_id
        self.parent_id = None


@pytest.fixture
def store(tmp_path, monkeypatch):
    """An empty store directory, wired up via the documented env vars."""
    home = tmp_path / "memory"
    home.mkdir()
    monkeypatch.setenv("AMPLIFIER_MEMORY_HOME", str(home))
    monkeypatch.setenv("AMPLIFIER_MEMORY_ERROR_LOG", str(tmp_path / "memory-errors.log"))
    return home


def write_memory(home, lines):
    (home / "MEMORY.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


async def fire(hook):
    return await hook.on_provider_request("provider:request", {})


# --------------------------------------------------------------------------
# Acceptance 1 — one handler, on provider:request
# --------------------------------------------------------------------------


async def test_mount_registers_exactly_one_provider_request_handler(store):
    coordinator = FakeCoordinator()
    info = await mod.mount(coordinator, {})

    regs = coordinator.hooks.registrations
    print("registrations:", [(r["event"], r["priority"], r["name"]) for r in regs])
    print("mount() returned:", info)

    assert len(regs) == 1
    assert regs[0]["event"] == "provider:request"
    assert regs[0]["priority"] == 5  # default
    assert set(info) == {"name", "version", "provides"}


async def test_priority_comes_from_config(store):
    coordinator = FakeCoordinator()
    await mod.mount(coordinator, {"priority": 42})
    assert coordinator.hooks.registrations[0]["priority"] == 42


# --------------------------------------------------------------------------
# Acceptance 2 — the HookResult shape and the framing sentence
# --------------------------------------------------------------------------


async def test_hook_result_shape_and_framing_sentence(store):
    write_memory(store, ["- [m-001] never use tabs in YAML files"])
    hook = mod.MemoryInjectHook(FakeCoordinator(), {})

    result = await fire(hook)
    block = result.context_injection

    print("=== injected block ===")
    print(block)
    print("=== end block ===")

    assert result.action == "inject_context"
    assert result.context_injection_role == "system"
    assert result.ephemeral is True

    inner_first_line = block.splitlines()[1]
    assert inner_first_line == mod.FRAMING_SENTENCE
    assert block.splitlines()[0] == '<system-reminder source="amplifier-memory">'
    assert block.splitlines()[-1] == "</system-reminder>"


async def test_memory_md_appears_verbatim(store):
    body = "## style\n- [m-001] never use tabs in YAML files\n- [m-002] two-space indent\n"
    (store / "MEMORY.md").write_text(body, encoding="utf-8")
    hook = mod.MemoryInjectHook(FakeCoordinator(), {})

    block = (await fire(hook)).context_injection
    print("verbatim substring present:", body in block)
    assert body in block


# --------------------------------------------------------------------------
# Acceptance 3 — cache stability (session.v1 Conformance 1)
# --------------------------------------------------------------------------


async def test_two_instances_produce_byte_identical_blocks(store):
    write_memory(store, ["- [m-001] a", "- [m-002] b"])
    (store / "topics").mkdir()
    (store / "topics" / "x.md").write_text("TOPIC-BODY-SENTINEL\n", encoding="utf-8")

    a = await fire(mod.MemoryInjectHook(FakeCoordinator("session-A"), {}))
    b = await fire(mod.MemoryInjectHook(FakeCoordinator("session-B"), {}))

    print("len(a)=", len(a.context_injection), "len(b)=", len(b.context_injection))
    print("identical:", a.context_injection == b.context_injection)
    assert a.context_injection == b.context_injection


async def test_block_carries_no_timestamp_counter_or_session_id(store):
    write_memory(store, ["- [m-001] a"])
    hook = mod.MemoryInjectHook(FakeCoordinator("session-DEADBEEF"), {})
    block = (await fire(hook)).context_injection

    iso = re.compile(r"\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}")
    print("ISO-timestamp match:", iso.search(block))
    assert iso.search(block) is None
    assert "session-DEADBEEF" not in block
    # A counter of requests/turns would have to name itself; none does. The
    # only numbers in the block outside MEMORY.md's own ids are the two
    # store-derived counts in the announce line, which are content, not state.
    for word in ("turn ", "request #", "call #", "iteration"):
        assert word not in block.lower()


async def test_topic_bodies_are_not_injected(store):
    write_memory(store, ["- [m-031] YAML style → topics/yaml-style.md"])
    (store / "topics").mkdir()
    (store / "topics" / "yaml-style.md").write_text("TOPIC-BODY-SENTINEL\n", encoding="utf-8")

    block = (await fire(mod.MemoryInjectHook(FakeCoordinator(), {}))).context_injection
    print("sentinel in block:", "TOPIC-BODY-SENTINEL" in block)
    print("pointer line in block:", "topics/yaml-style.md" in block)
    assert "TOPIC-BODY-SENTINEL" not in block
    assert "topics/yaml-style.md" in block  # the pointer line still rides along


# --------------------------------------------------------------------------
# Acceptance 4 — the §2 announce instruction, both variants
# --------------------------------------------------------------------------


async def test_announce_instruction_counts_memories_and_topics(store):
    write_memory(store, ["- [m-001] a", "## heading", "- [m-002] b", "- [m-003] c"])
    (store / "topics").mkdir()
    (store / "topics" / "one.md").write_text("x\n", encoding="utf-8")
    (store / "topics" / "two.md").write_text("x\n", encoding="utf-8")
    (store / "topics" / "notes.txt").write_text("x\n", encoding="utf-8")  # not a topic

    block = (await fire(mod.MemoryInjectHook(FakeCoordinator(), {}))).context_injection
    last_line = block.splitlines()[-2]
    print("announce line:", last_line)

    assert last_line == (
        'On your first reply of this session, say once: '
        '"Loaded 3 memories (2 topics available)."'
    )


async def test_announce_instruction_empty_store_variant(store):
    (store / "MEMORY.md").write_text("", encoding="utf-8")

    block = (await fire(mod.MemoryInjectHook(FakeCoordinator(), {}))).context_injection
    print("=== empty-store block ===")
    print(block)
    last_line = block.splitlines()[-2]

    assert last_line == (
        'On your first reply of this session, say once: '
        '"No memories yet — /remember <text> to add one."'
    )


# --------------------------------------------------------------------------
# Acceptance 5 — §10 fail open
# --------------------------------------------------------------------------


async def test_missing_store_fails_open_and_logs_one_line(tmp_path, monkeypatch):
    log = tmp_path / "memory-errors.log"
    monkeypatch.setenv("AMPLIFIER_MEMORY_HOME", str(tmp_path / "does-not-exist"))
    monkeypatch.setenv("AMPLIFIER_MEMORY_ERROR_LOG", str(log))

    hook = mod.MemoryInjectHook(FakeCoordinator(), {})
    results = [await fire(hook) for _ in range(3)]

    print("actions:", [r.action for r in results])
    print("injections:", [r.context_injection for r in results])
    print("error log:", log.read_text(encoding="utf-8").rstrip())

    assert all(r.action == "continue" for r in results)
    assert all(r.context_injection is None for r in results)
    assert len(log.read_text(encoding="utf-8").splitlines()) == 1


@pytest.mark.skipif(
    hasattr(os, "geteuid") and os.geteuid() == 0,
    reason="root ignores file permissions; chmod 000 would not be unreadable",
)
async def test_unreadable_memory_file_fails_open(store, tmp_path):
    path = store / "MEMORY.md"
    path.write_text("- [m-001] a\n", encoding="utf-8")
    path.chmod(0o000)
    try:
        hook = mod.MemoryInjectHook(FakeCoordinator(), {})
        result = await fire(hook)
        log_text = (tmp_path / "memory-errors.log").read_text(encoding="utf-8")
        print("action:", result.action, "| user_message:", result.user_message)
        print("error log:", log_text.rstrip())
        assert result.action == "continue"
        assert result.context_injection is None
        assert "PermissionError" in log_text
    finally:
        path.chmod(stat.S_IRUSR | stat.S_IWUSR)


async def test_handler_never_raises_even_with_a_broken_error_log(store, monkeypatch):
    """The last line of defence: recording a failure cannot become a failure."""
    monkeypatch.setenv("AMPLIFIER_MEMORY_HOME", str(store / "nope"))
    monkeypatch.setenv("AMPLIFIER_MEMORY_ERROR_LOG", "/proc/definitely/not/writable.log")

    result = await fire(mod.MemoryInjectHook(FakeCoordinator(), {}))
    print("action with unwritable error log:", result.action)
    assert result.action == "continue"


# --------------------------------------------------------------------------
# Acceptance 8 — one `loaded` usage event per session
# --------------------------------------------------------------------------


async def test_usage_logged_once_per_session(store, monkeypatch):
    write_memory(store, ["- [m-001] a"])
    calls = []
    monkeypatch.setattr(
        mod, "log_usage", lambda event, target, session_id: calls.append((event, target))
    )

    hook = mod.MemoryInjectHook(FakeCoordinator(), {})
    for _ in range(3):
        await fire(hook)

    print("usage stub calls across 3 requests:", calls)
    assert calls == [("loaded", "MEMORY.md")]


# --------------------------------------------------------------------------
# Acceptance 7 — size of the block at store.v1's worst case
# --------------------------------------------------------------------------


async def test_worst_case_block_size_is_measured_not_assumed(store):
    """200 lines × 120 chars — store.v1 §3's cap at its widest.

    session.v1 §1 says *verbatim*, so the block cannot be smaller than the
    file. This test measures; it does not enforce a 10 KB ceiling, because
    at this store size no such ceiling can be met without breaking §1.
    See README.md, "Size".
    """
    line = "- [m-001] " + "x" * 110
    assert len(line) == 120
    write_memory(store, [line] * 200)

    block = (await fire(mod.MemoryInjectHook(FakeCoordinator(), {}))).context_injection
    size = len(block.encode("utf-8"))
    memory_size = (store / "MEMORY.md").stat().st_size
    print(f"MEMORY.md worst case: {memory_size} bytes")
    print(f"injected block: {size} bytes ({size / 1024:.1f} KB)")
    print(f"block overhead beyond MEMORY.md: {size - memory_size} bytes")
    print(f"<= 10 KB (HOOKS_API.md's documented default limit)? {size <= 10 * 1024}")

    # What IS enforceable: the block adds under 500 bytes to the file itself.
    assert size - memory_size < 500


async def test_typical_store_is_well_under_10kb(store):
    write_memory(store, [f"- [m-{i:03d} ] a memory about something" for i in range(40)])
    block = (await fire(mod.MemoryInjectHook(FakeCoordinator(), {}))).context_injection
    size = len(block.encode("utf-8"))
    print(f"40-memory store: block is {size} bytes")
    assert size <= 10 * 1024


# --------------------------------------------------------------------------
# Ledger probes — the rows this lane owns name these by id.
# Thin, so each row points at one runnable thing that either passes or does
# not. The wider evidence lives in the tests above and in
# `conformance/session/inject/run.py`.
# --------------------------------------------------------------------------


async def test_row_amm_010(store):
    """AMM-010 — session.v1 Core 1, Loaded in every request."""
    body = "- [m-001] never use tabs in YAML files\n"
    (store / "MEMORY.md").write_text(body, encoding="utf-8")
    (store / "topics").mkdir()
    (store / "topics" / "y.md").write_text("TOPIC-BODY-SENTINEL\n", encoding="utf-8")

    first = await fire(mod.MemoryInjectHook(FakeCoordinator("A"), {}))
    second = await fire(mod.MemoryInjectHook(FakeCoordinator("B"), {}))
    block = first.context_injection
    print("AMM-010 block:\n" + block)

    assert first.action == "inject_context"
    assert first.context_injection_role == "system"
    assert first.ephemeral is True
    assert block.splitlines()[1] == mod.FRAMING_SENTENCE
    assert body in block
    assert "TOPIC-BODY-SENTINEL" not in block
    assert block == second.context_injection


async def test_row_amm_018(store):
    """AMM-018 — session.v1 Core 9, Nothing at session end."""
    text = pathlib.Path(mod.__file__).read_text(encoding="utf-8")
    coordinator = FakeCoordinator()
    await mod.mount(coordinator, {})
    events = [r["event"] for r in coordinator.hooks.registrations]
    print("AMM-018 registered events:", events)

    assert events == ["provider:request"]
    for needle in ("session:end", "session_end", "atexit"):
        assert needle not in text


async def test_row_amm_019(tmp_path, monkeypatch):
    """AMM-019 — session.v1 Core 10, Fail open, never block."""
    log = tmp_path / "memory-errors.log"
    monkeypatch.setenv("AMPLIFIER_MEMORY_HOME", str(tmp_path / "absent"))
    monkeypatch.setenv("AMPLIFIER_MEMORY_ERROR_LOG", str(log))

    hook = mod.MemoryInjectHook(FakeCoordinator(), {})
    results = [await fire(hook) for _ in range(3)]
    print("AMM-019 error log:", log.read_text(encoding="utf-8").rstrip())

    assert [r.action for r in results] == ["continue"] * 3
    assert all(r.context_injection is None for r in results)
    assert len(log.read_text(encoding="utf-8").splitlines()) == 1
