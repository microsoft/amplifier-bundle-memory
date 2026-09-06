"""Tests for hooks-memory-inject — session.v2 §1, §2, §9, §10.

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


async def test_mount_registers_provider_request_and_compaction(store):
    """Two events, and nothing else — §1/§2 inject and render, §9 stays true.

    `context:compaction` is the shipped context manager's own event
    (`amplifier_module_context_simple/__init__.py:1753-1755`); the handler
    only arms a flag, because a `user_message` is displayed on
    `provider:request`, not there.
    """
    coordinator = FakeCoordinator()
    info = await mod.mount(coordinator, {})

    regs = coordinator.hooks.registrations
    print("registrations:", [(r["event"], r["priority"], r["name"]) for r in regs])
    print("mount() returned:", info)

    assert [r["event"] for r in regs] == ["provider:request", "context:compaction"]
    assert all(r["priority"] == 5 for r in regs)  # default
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
# Acceptance 3 — cache stability (session.v2 Conformance 1)
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
    # A counter of requests/turns would have to name itself; none does. Under
    # session.v2 §1 the counts are not in the block at all — they moved into
    # the rendered line (§2), so the only numbers here are MEMORY.md's own ids.
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
# Acceptance 4 — §2, the line the hook RENDERS (and §1, the block that no
# longer instructs anyone to say it)
# --------------------------------------------------------------------------


def fixture_rows() -> dict[str, tuple[str, str | None]]:
    """tests/fixtures/announce-lines.txt — (origin, the bytes the human reads)."""
    path = pathlib.Path(__file__).parent / "fixtures" / "announce-lines.txt"
    out: dict[str, tuple[str, str | None]] = {}
    for raw in path.read_text(encoding="utf-8").splitlines():
        if not raw.strip() or raw.startswith("#"):
            continue
        key, origin, text = raw.split("\t")
        out[key] = (origin, None if text == "-" else text)
    return out


def fixture_lines() -> dict[str, str | None]:
    return {key: text for key, (_origin, text) in fixture_rows().items()}


async def test_block_carries_no_announce_instruction(store):
    """§1 — the block instructs nobody. This is what makes it cache-stable."""
    write_memory(store, ["- [m-001] a", "- [m-002] b", "- [m-003] c"])
    (store / "topics").mkdir()
    (store / "topics" / "y.md").write_text("x\n", encoding="utf-8")

    result = await fire(mod.MemoryInjectHook(FakeCoordinator(), {}))
    block = result.context_injection
    print("=== block ===")
    print(block)

    for needle in ("say once", "On your first reply", "Loaded 3 memories", "announce"):
        assert needle not in block, f"the block still instructs: {needle!r}"
    # No count anywhere in the framing — the counts live in the rendered line.
    assert block.splitlines()[1] == mod.FRAMING_SENTENCE
    assert "/edit <id> <text>" in block  # session.v2 §1's new framing sentence


async def test_block_is_byte_identical_across_instances_by_sha(store):
    """§1 Conformance — same MEMORY.md, two hook instances, same bytes."""
    import hashlib

    write_memory(store, ["- [m-001] a", "- [m-002] b", "- [m-003] c"])
    a = (await fire(mod.MemoryInjectHook(FakeCoordinator("A"), {}))).context_injection
    b = (await fire(mod.MemoryInjectHook(FakeCoordinator("B"), {}))).context_injection
    sha_a = hashlib.sha256(a.encode("utf-8")).hexdigest()
    sha_b = hashlib.sha256(b.encode("utf-8")).hexdigest()
    print("sha256 A:", sha_a)
    print("sha256 B:", sha_b)
    assert sha_a == sha_b


async def test_announce_is_rendered_once_then_never_again(store):
    """§2 — request 1 carries the line; request 2 (and 3) carry None."""
    write_memory(store, ["- [m-001] a", "- [m-002] b", "- [m-003] c"])
    hook = mod.MemoryInjectHook(FakeCoordinator(), {})

    messages = [(await fire(hook)).user_message for _ in range(3)]
    for i, m in enumerate(messages, start=1):
        print(f"request {i}: user_message={m!r}")

    assert messages[0] == "3 memories loaded. /memory to see them."
    assert messages[1] is None
    assert messages[2] is None


async def test_announce_level_is_info_not_warning(store):
    """§10's channel is 'warning'; a normal load is a plain informational line.

    `amplifier_app_cli/ui/display.py:100-105` maps info→cyan, warning→yellow,
    error→red for the `[hooks-memory-inject]` label.
    """
    write_memory(store, ["- [m-001] a"])
    result = await fire(mod.MemoryInjectHook(FakeCoordinator(), {}))
    print("level:", result.user_message_level, "| message:", result.user_message)
    assert result.user_message_level == "info"


@pytest.mark.parametrize(
    ("case", "memories", "topics"),
    [
        ("plural", 3, 0),
        ("plural_with_topics", 3, 2),
        ("singular", 1, 0),
        ("singular_with_topics", 1, 2),
        ("empty", 0, 0),
    ],
)
async def test_announce_variants_match_fixtures(store, case, memories, topics):
    """§2 — every variant, byte-compared to tests/fixtures/announce-lines.txt."""
    expected = fixture_lines()[case]
    if memories:
        write_memory(store, [f"- [m-{i:03d}] memory {i}" for i in range(1, memories + 1)])
    else:
        (store / "MEMORY.md").write_text("", encoding="utf-8")
    if topics:
        (store / "topics").mkdir()
        for i in range(topics):
            (store / "topics" / f"t{i}.md").write_text("x\n", encoding="utf-8")

    message = (await fire(mod.MemoryInjectHook(FakeCoordinator(), {}))).user_message
    print(f"{case}: rendered={message!r}")
    print(f"{case}: fixture ={expected!r}")
    assert message == expected


async def test_announce_after_a_compaction(store):
    """§2 — the first request after a compaction says so, then falls silent.

    The signal is the shipped context manager's own `context:compaction`
    event; this test drives the handler the kernel would call.
    """
    write_memory(store, ["- [m-001] a", "- [m-002] b", "- [m-003] c"])
    hook = mod.MemoryInjectHook(FakeCoordinator(), {})

    first = (await fire(hook)).user_message
    quiet = (await fire(hook)).user_message
    await hook.on_context_compaction("context:compaction", {"strategy_level": 1})
    after = (await fire(hook)).user_message
    quiet_again = (await fire(hook)).user_message

    print("request 1        :", repr(first))
    print("request 2        :", repr(quiet))
    print("after compaction :", repr(after))
    print("next request     :", repr(quiet_again))

    fixtures = fixture_lines()
    assert first == fixtures["plural"]
    assert quiet is None
    assert after == fixtures["compacted"]
    assert quiet_again is None


async def test_compaction_before_the_first_request_still_announces_the_load(store):
    """A compaction cannot steal the session's first line — order is explicit."""
    write_memory(store, ["- [m-001] a"])
    hook = mod.MemoryInjectHook(FakeCoordinator(), {})
    await hook.on_context_compaction("context:compaction", {})
    first = (await fire(hook)).user_message
    second = (await fire(hook)).user_message
    print("first:", repr(first), "| second:", repr(second))
    assert first == fixture_lines()["singular"]
    assert second is None


async def test_compaction_on_an_empty_store_says_nothing(store):
    """`0 memories still loaded.` is a zero-valued count; §2 renders nothing."""
    (store / "MEMORY.md").write_text("", encoding="utf-8")
    hook = mod.MemoryInjectHook(FakeCoordinator(), {})
    await fire(hook)
    await hook.on_context_compaction("context:compaction", {})
    after = (await fire(hook)).user_message
    print("empty store after compaction:", repr(after))
    assert after is fixture_lines()["compacted_empty"] is None


class SpyDisplay:
    """The kernel's DisplaySystem protocol (amplifier_core/display.py)."""

    def __init__(self):
        self.calls = []

    def show_message(self, message, level="info", source="hook"):
        self.calls.append((message, level, source))


class DisplayCoordinator(FakeCoordinator):
    def __init__(self, session_id="test-session"):
        super().__init__(session_id)
        self.display_system = SpyDisplay()


async def test_the_line_is_rendered_through_the_display_system(store):
    """§2 — with a display system present, the hook renders it itself."""
    write_memory(store, ["- [m-001] a", "- [m-002] b", "- [m-003] c"])
    coordinator = DisplayCoordinator()
    hook = mod.MemoryInjectHook(coordinator, {})

    first = await fire(hook)
    second = await fire(hook)
    print("show_message calls:", coordinator.display_system.calls)
    print("user_message on the result:", repr(first.user_message))

    assert coordinator.display_system.calls == [
        ("3 memories loaded. /memory to see them.", "info", "amplifier-memory")
    ]
    # Rendered here, so the result does not also carry it — never two lines.
    assert first.user_message is None
    assert second.user_message is None
    assert first.action == "inject_context" and first.context_injection


async def test_without_a_display_system_the_line_falls_back_to_user_message(store):
    """A host with no display system still gets one line to dispatch."""
    write_memory(store, ["- [m-001] a"])
    result = await fire(mod.MemoryInjectHook(FakeCoordinator(), {}))
    print("no display system -> user_message:", repr(result.user_message))
    assert result.user_message == "1 memory loaded."


async def test_a_display_system_that_raises_does_not_break_the_request(store):
    """§10 — rendering is never allowed to become a failure."""

    class Exploding(SpyDisplay):
        def show_message(self, message, level="info", source="hook"):
            raise RuntimeError("terminal on fire")

    write_memory(store, ["- [m-001] a"])
    coordinator = DisplayCoordinator()
    coordinator.display_system = Exploding()
    result = await fire(mod.MemoryInjectHook(coordinator, {}))
    print("action:", result.action, "| fallback user_message:", repr(result.user_message))
    assert result.action == "inject_context"
    assert result.user_message == "1 memory loaded."  # fell back, did not raise


async def test_kernel_aggregation_drops_user_message_when_a_hook_injects(store):
    """Why `_render` exists — measured against the installed kernel.

    The kernel aggregates every handler's result for an event into one. As
    soon as ANY handler returns `inject_context`, the aggregate's
    `user_message` is None. This hook injects, and a real session carries
    other injecting hooks besides, so `user_message` on `provider:request`
    is not a channel that reaches the human here. If this test ever starts
    failing, the kernel has been fixed and `_render` can be reconsidered.
    """
    from amplifier_core import HookResult
    from amplifier_core.coordinator import ModuleCoordinator

    write_memory(store, ["- [m-001] a"])

    async def another_injector(event, data):
        return HookResult(
            action="inject_context",
            context_injection="ANOTHER-BLOCK",
            context_injection_role="system",
            ephemeral=True,
        )

    async def messenger(event, data):
        return HookResult(action="continue", user_message="MSG", user_message_level="info")

    display = SpyDisplay()
    coordinator = ModuleCoordinator(display_system=display)
    coordinator.hooks.register("provider:request", messenger, priority=1, name="messenger")
    coordinator.hooks.register("provider:request", another_injector, priority=10, name="other")

    aggregated = await coordinator.hooks.emit("provider:request", {})
    await coordinator.process_hook_result(aggregated, "provider:request", "orchestrator")
    print("aggregate user_message:", repr(aggregated.user_message))
    print("show_message calls:", display.calls)
    assert aggregated.user_message is None
    assert display.calls == []

    # And the same coordinator, with this hook mounted, still renders — by
    # the direct path, which the aggregation cannot swallow.
    display2 = SpyDisplay()
    coordinator2 = ModuleCoordinator(display_system=display2)
    await mod.mount(coordinator2, {})
    coordinator2.hooks.register("provider:request", another_injector, priority=10, name="other")
    await coordinator2.hooks.emit("provider:request", {})
    print("with this hook mounted:", display2.calls)
    assert display2.calls == [("1 memory loaded.", "info", "amplifier-memory")]


def test_every_announce_variant_is_render_safe():
    """The display path interpolates into Rich markup and drops blank lines.

    `display.py:122` interpolates unescaped — a `[tag]` would be silently
    consumed — and `:127` skips empty lines of a multi-line message. Every
    line this module can render is single-line and bracket-free, so neither
    can bite. This test is the tripwire for the day someone adds one.
    """
    variants = [
        mod.announce_line(n, m, compacted=c)
        for n in (0, 1, 3, 200)
        for m in (0, 1, 2)
        for c in (False, True)
    ]
    for text in variants:
        if text is None:
            continue
        print(repr(text))
        for bad in mod.RENDER_UNSAFE:
            assert bad not in text, f"{bad!r} in {text!r}"


def test_announce_renders_through_the_cli_display_path():
    """Acceptance 4 — the rendered text equals the intended text.

    Not a Markdown check: this channel is `CLIDisplaySystem.show_message`
    (`amplifier_app_cli/ui/display.py:98-128`), which prints through Rich
    *markup*. That is why session.v1's backtick workaround for `<text>` is
    gone — markup does not eat angle brackets.
    """
    display_mod = _load_cli_display()
    if display_mod is None:
        pytest.skip("amplifier_app_cli is not importable from this environment")

    import io

    from rich.console import Console

    for text in [
        mod.announce_line(3, 0),
        mod.announce_line(3, 2),
        mod.announce_line(1, 0),
        mod.announce_line(0, 0),
        mod.announce_line(3, 0, compacted=True),
    ]:
        buf = io.StringIO()
        display = display_mod.CLIDisplaySystem()
        display.console = Console(file=buf, width=200, no_color=True, highlight=False)
        display.show_message(text, "info", "hook:hooks-memory-inject")
        rendered = buf.getvalue().rstrip("\n")
        print(f"rendered: {rendered!r}")
        assert rendered == f"[hooks-memory-inject] {text}"


def _load_cli_display():
    """Import `amplifier_app_cli.ui.display` from wherever the CLI is installed.

    The module's own venv does not depend on the app; the app is what renders
    the line, so the proof has to reach it. Appended to `sys.path` (never
    prepended) so nothing here can shadow this venv's own packages.
    """
    import importlib
    import sys

    try:
        return importlib.import_module("amplifier_app_cli.ui.display")
    except ImportError:
        pass
    for candidate in sorted(
        pathlib.Path.home().glob(".local/share/uv/tools/amplifier/lib/python*/site-packages")
    ):
        if (candidate / "amplifier_app_cli").is_dir():
            sys.path.append(str(candidate))
            try:
                return importlib.import_module("amplifier_app_cli.ui.display")
            except ImportError:
                return None
    return None


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
# Acceptance 5b — §10's line REACHES the human (item 87j)
#
# §10 says the failure is "one line in the transcript". Until this lane the
# line was only ever set on `HookResult.user_message`, which the kernel's
# aggregation nulls the moment any handler on the event injects — so the line
# existed in the field and never on a terminal. Observed live: session
# f5cc2a7f (2026-09-06) failed open, wrote the error-log line, printed nothing.
# --------------------------------------------------------------------------


async def test_fail_open_line_reaches_the_display_even_with_another_injector(
    tmp_path, monkeypatch
):
    """The acceptance criterion, measured against the installed kernel.

    A real `ModuleCoordinator`, this hook mounted, and a second injecting hook
    registered on the same event — which is what a real session looks like.
    The line reaches the spy once; the error log gains one line; and the
    bundle's own block is absent from the aggregate (fail open: nothing of
    ours was injected).
    """
    from amplifier_core import HookResult
    from amplifier_core.coordinator import ModuleCoordinator

    log = tmp_path / "memory-errors.log"
    monkeypatch.setenv("AMPLIFIER_MEMORY_HOME", str(tmp_path / "absent-store"))
    monkeypatch.setenv("AMPLIFIER_MEMORY_ERROR_LOG", str(log))

    async def another_injector(event, data):
        return HookResult(
            action="inject_context",
            context_injection="ANOTHER-BLOCK",
            context_injection_role="system",
            ephemeral=True,
        )

    display = SpyDisplay()
    coordinator = ModuleCoordinator(display_system=display)
    await mod.mount(coordinator, {})
    coordinator.hooks.register("provider:request", another_injector, priority=10, name="other")

    aggregated = await coordinator.hooks.emit("provider:request", {})
    await coordinator.process_hook_result(aggregated, "provider:request", "orchestrator")

    print("aggregate action:", aggregated.action)
    print("aggregate user_message:", repr(aggregated.user_message))
    print("aggregate context_injection:", repr(aggregated.context_injection))
    print("show_message calls:", display.calls)
    print("error log:", log.read_text(encoding="utf-8").rstrip())

    # 1. The line reached the human, exactly once, on the warning channel.
    assert len(display.calls) == 1
    message, level, source = display.calls[0]
    assert message.startswith("amplifier-memory: memories not loaded (")
    assert message.endswith("); session continues.")
    assert "StoreMissing" in message
    assert (level, source) == ("warning", "amplifier-memory")

    # 2. It did NOT also ride user_message — the aggregation would have
    #    dropped it anyway (that is the bug), so this is one line, not two.
    assert aggregated.user_message is None

    # 3. Fail open: our block is absent, the other hook's is untouched.
    assert mod.FRAMING_SENTENCE not in (aggregated.context_injection or "")
    assert "ANOTHER-BLOCK" in (aggregated.context_injection or "")

    # 4. One line in the error log.
    assert len(log.read_text(encoding="utf-8").splitlines()) == 1


async def test_fail_open_line_is_rendered_once_per_reason(tmp_path, monkeypatch):
    """Three failing requests, one line — the dedup rides the rendered path too."""
    log = tmp_path / "memory-errors.log"
    monkeypatch.setenv("AMPLIFIER_MEMORY_HOME", str(tmp_path / "absent-store"))
    monkeypatch.setenv("AMPLIFIER_MEMORY_ERROR_LOG", str(log))

    coordinator = DisplayCoordinator()
    hook = mod.MemoryInjectHook(coordinator, {})
    results = [await fire(hook) for _ in range(3)]

    print("show_message calls:", coordinator.display_system.calls)
    print("user_messages:", [r.user_message for r in results])

    assert len(coordinator.display_system.calls) == 1
    assert all(r.user_message is None for r in results)  # rendered, not returned
    assert len(log.read_text(encoding="utf-8").splitlines()) == 1


async def test_without_a_display_system_the_fail_open_line_falls_back(tmp_path, monkeypatch):
    """A host with no display system still gets exactly one line to dispatch."""
    monkeypatch.setenv("AMPLIFIER_MEMORY_HOME", str(tmp_path / "absent-store"))
    monkeypatch.setenv("AMPLIFIER_MEMORY_ERROR_LOG", str(tmp_path / "memory-errors.log"))

    results = [await fire(mod.MemoryInjectHook(FakeCoordinator(), {})) for _ in range(1)]
    print("fallback user_message:", repr(results[0].user_message))
    assert results[0].user_message.startswith("amplifier-memory: memories not loaded (")
    assert results[0].user_message_level == "warning"


async def test_a_bad_byte_in_a_readable_store_does_not_trigger_the_fail_open_line(
    store, tmp_path
):
    """The discriminating arm: U+FFFD is lane J's job, not §10's.

    A file that decodes tolerantly is not a store failure — every memory is
    still there — so the human gets the §2 announce and no §10 line, and the
    error log is never created.
    """
    (store / "MEMORY.md").write_bytes(b"- [m-001] Jos\xe9 prefers short reviews\n")
    log = tmp_path / "memory-errors.log"

    coordinator = DisplayCoordinator()
    result = await fire(mod.MemoryInjectHook(coordinator, {}))

    print("show_message calls:", coordinator.display_system.calls)
    print("action:", result.action)
    print("error log exists:", log.exists())

    assert coordinator.display_system.calls == [
        ("1 memory loaded.", "info", "amplifier-memory")
    ]
    assert not any("not loaded" in m for m, _, _ in coordinator.display_system.calls)
    assert result.action == "inject_context"
    assert "\ufffd" in result.context_injection
    assert not log.exists(), "a readable file with a bad byte is not a §10 failure"


def test_fail_open_reason_is_one_line_and_bounded():
    """§10 says one line. An exception's str() is bounded by nothing."""

    class Sprawling(Exception):
        pass

    exc = Sprawling("first line\nsecond line\n\n  third   line " + "x" * 500)
    reason = mod.fail_open_reason(exc)
    line = mod.fail_open_line(reason)
    print("reason:", repr(reason))
    print("line:", repr(line[:120] + "…"))

    assert "\n" not in reason and "\n" not in line
    assert len(reason) <= mod.REASON_MAX
    assert reason.startswith("Sprawling: first line second line third line")
    assert line == f"amplifier-memory: memories not loaded ({reason}); session continues."


def test_fail_open_line_survives_the_rich_markup_channel():
    """A bracketed reason is eaten by the display path unless it is escaped.

    Measured against the CLI's own `CLIDisplaySystem` (rich 14.3.3 on this
    device): `display.py:122` interpolates the message into a Rich markup
    string unescaped, so an unescaped `[foo]` is consumed as a style tag and
    the rest of the line with it. `[Errno 2]` happens to survive — a tag must
    start with `[a-z#/@]` — which is exactly why the escape cannot be left to
    luck. Unlike §2's lines, this one carries text the module does not own.
    """
    display_mod = _load_cli_display()
    if display_mod is None:
        pytest.skip("amplifier_app_cli is not importable from this environment")

    import io

    from rich.console import Console

    for reason in [
        "KeyError: [foo]",
        "OSError: [Errno 2] No such file or directory: '/x/MEMORY.md'",
        "StoreMissing: no memory store at /x (no MEMORY.md); run `amplifier-memory init` first",
    ]:
        line = mod.fail_open_line(reason)
        buf = io.StringIO()
        display = display_mod.CLIDisplaySystem()
        display.console = Console(file=buf, width=300, no_color=True, highlight=False)
        display.show_message(line, "warning", "hook:hooks-memory-inject")
        rendered = buf.getvalue().rstrip("\n")
        print(f"reason {reason!r}\n  -> {rendered!r}")

        expected = (
            f"[hooks-memory-inject] amplifier-memory: memories not loaded "
            f"({reason}); session continues."
        )
        assert rendered == expected, "the reason did not survive the markup channel"


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
# Acceptance 7 — size of the block at store.v2's worst case
# --------------------------------------------------------------------------


async def test_worst_case_block_size_is_measured_not_assumed(store):
    """200 lines × 120 chars — store.v2 §3's cap at its widest.

    session.v2 §1 says *verbatim*, so the block cannot be smaller than the
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
    """AMM-010 — session.v2 Core 1, Loaded in every request."""
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
    assert "say once" not in block  # §1: no announce instruction in the block


async def test_row_amm_011(store):
    """AMM-011 — session.v2 Core 2, Announce the load, once, in code.

    In-process half: the line the hook hands the runtime, once per session,
    plus the post-compaction variant. The rendered half — that the runtime
    actually prints it on a real terminal — is
    tests/smoke/evidence/announce-rendered-*.txt, because a clause is proven
    at the outermost layer it reaches.
    """
    fixtures = fixture_lines()
    write_memory(store, ["- [m-001] a", "- [m-002] b", "- [m-003] c"])
    hook = mod.MemoryInjectHook(FakeCoordinator(), {})

    first = await fire(hook)
    second = await fire(hook)
    await hook.on_context_compaction("context:compaction", {"strategy_level": 1})
    third = await fire(hook)

    print("AMM-011 request 1:", repr(first.user_message), first.user_message_level)
    print("AMM-011 request 2:", repr(second.user_message))
    print("AMM-011 after compaction:", repr(third.user_message))

    assert first.user_message == fixtures["plural"]
    assert first.user_message_level == "info"
    assert first.action == "inject_context"  # one result does both
    assert second.user_message is None
    assert third.user_message == fixtures["compacted"]
    assert "say once" not in (first.context_injection or "")


async def test_row_amm_018(store):
    """AMM-018 — session.v2 Core 9, Nothing at session end."""
    text = pathlib.Path(mod.__file__).read_text(encoding="utf-8")
    coordinator = FakeCoordinator()
    await mod.mount(coordinator, {})
    events = [r["event"] for r in coordinator.hooks.registrations]
    print("AMM-018 registered events:", events)

    assert events == ["provider:request", "context:compaction"]
    for needle in ("session:end", "session_end", "atexit"):
        assert needle not in text


async def test_row_amm_019(tmp_path, monkeypatch):
    """AMM-019 — session.v2 Core 10, Fail open, never block.

    Both halves of the clause: the session proceeds unchanged (no raise, no
    injection), and the failure is *one line in the transcript* — rendered
    through the display system, because `user_message` alone never arrives
    (item 87j) — plus one line in the error log.
    """
    log = tmp_path / "memory-errors.log"
    monkeypatch.setenv("AMPLIFIER_MEMORY_HOME", str(tmp_path / "absent"))
    monkeypatch.setenv("AMPLIFIER_MEMORY_ERROR_LOG", str(log))

    coordinator = DisplayCoordinator()
    hook = mod.MemoryInjectHook(coordinator, {})
    results = [await fire(hook) for _ in range(3)]
    print("AMM-019 shown:", coordinator.display_system.calls)
    print("AMM-019 error log:", log.read_text(encoding="utf-8").rstrip())

    assert [r.action for r in results] == ["continue"] * 3
    assert all(r.context_injection is None for r in results)
    assert len(log.read_text(encoding="utf-8").splitlines()) == 1
    assert len(coordinator.display_system.calls) == 1
    message, level, source = coordinator.display_system.calls[0]
    assert message.startswith("amplifier-memory: memories not loaded (")
    assert message.endswith("); session continues.")
    assert (level, source) == ("warning", "amplifier-memory")


# --------------------------------------------------------------------------
# Row gux — §10 is not the answer to a hand-typed byte; the block is
# --------------------------------------------------------------------------


async def test_one_byte_that_is_not_utf8_is_injected_as_u_fffd_and_logs_nothing(store, tmp_path):
    """store.v2 §9 invites hand edits; this hook fires on every provider request.

    Read strictly, one accented byte raised `UnicodeDecodeError` here and the session
    lost its memories for its whole life. It is not a store failure — the file is
    readable and every memory is still in it — so §10's decline is the wrong answer
    and the error log stays empty. The byte is shown, not hidden, so the human can
    see which memory carries it.
    """
    (store / "MEMORY.md").write_bytes(b"- [m-001] Jos\xe9 prefers short reviews\n")
    log = tmp_path / "memory-errors.log"

    with pytest.raises(UnicodeDecodeError) as strict:
        (store / "MEMORY.md").read_text(encoding="utf-8")
    result = await fire(mod.MemoryInjectHook(FakeCoordinator(), {}))

    print("the read the hook used to do ->", type(strict.value).__name__, strict.value)
    print("action:", result.action)
    print("block:\n" + (result.context_injection or ""))
    print("error log exists:", log.exists())

    assert result.action == "inject_context"
    assert "\ufffd" in result.context_injection
    assert "- [m-001] Jos\ufffd prefers short reviews" in result.context_injection
    # The count still comes from the tolerantly-read text — and under session.v2
    # it is rendered to the human, not written into the block.
    print("user_message:", repr(result.user_message))
    assert result.user_message == "1 memory loaded."
    assert not log.exists(), "a readable file with a bad byte is not a §10 failure"


# --------------------------------------------------------------------------
# Lane Q — suggestions.v1 §5: the second line, and nothing in the block
# --------------------------------------------------------------------------


class FakeInbox:
    """`amplifier_memory.inbox`'s one function, as this hook uses it.

    The real module is lane P's; this stands in for it so the surface can be
    proven before the library exists, and so the raising arm can be produced
    on demand.
    """

    def __init__(self, items, explode=None):
        self.items = items
        self.explode = explode
        self.calls = []

    def pending(self, home):
        self.calls.append(home)
        if self.explode is not None:
            raise self.explode
        return list(self.items)


def suggestion(sid, text):
    """Enough of lane P's Suggestion for a hook that only ever counts them."""
    return type("Suggestion", (), {"id": sid, "text": text})()


def install_inbox(monkeypatch, inbox):
    import amplifier_memory

    monkeypatch.setattr(amplifier_memory, "inbox", inbox, raising=False)
    return inbox


def remove_inbox(monkeypatch):
    import amplifier_memory

    monkeypatch.delattr(amplifier_memory, "inbox", raising=False)


async def test_three_waiting_render_one_extra_line_under_the_load_line(store, monkeypatch):
    """suggestions.v1 §5 — the count, on the same occasion as §2's line."""
    write_memory(store, ["- [m-001] a", "- [m-002] b", "- [m-003] c"])
    install_inbox(
        monkeypatch,
        FakeInbox(
            [
                suggestion("s-042", "NEVER-IN-CONTEXT-1"),
                suggestion("s-043", "NEVER-IN-CONTEXT-2"),
                suggestion("s-044", "NEVER-IN-CONTEXT-3"),
            ]
        ),
    )
    coordinator = DisplayCoordinator()
    hook = mod.MemoryInjectHook(coordinator, {})

    first = await fire(hook)
    second = await fire(hook)
    print("show_message calls:")
    for call in coordinator.display_system.calls:
        print("   ", call)
    print("user_message on request 1:", repr(first.user_message))
    print("user_message on request 2:", repr(second.user_message))

    assert coordinator.display_system.calls == [
        ("3 memories loaded. /memory to see them.", "info", "amplifier-memory"),
        ("3 suggestions waiting. /memory review to see them.", "info", "amplifier-memory"),
    ]
    assert first.user_message is None and second.user_message is None


async def test_one_waiting_is_the_singular_line(store, monkeypatch):
    write_memory(store, ["- [m-001] a"])
    install_inbox(monkeypatch, FakeInbox([suggestion("s-042", "x")]))
    coordinator = DisplayCoordinator()
    await fire(mod.MemoryInjectHook(coordinator, {}))
    print("show_message calls:", coordinator.display_system.calls)
    assert coordinator.display_system.calls[1][0] == "1 suggestion waiting. /memory review to see it."


async def test_an_empty_inbox_renders_no_second_line(store, monkeypatch):
    write_memory(store, ["- [m-001] a"])
    install_inbox(monkeypatch, FakeInbox([]))
    coordinator = DisplayCoordinator()
    await fire(mod.MemoryInjectHook(coordinator, {}))
    print("show_message calls:", coordinator.display_system.calls)
    assert coordinator.display_system.calls == [
        ("1 memory loaded.", "info", "amplifier-memory")
    ]


async def test_the_injected_block_is_identical_with_and_without_an_inbox(store, monkeypatch):
    """§5 — only accepted memories are loaded: nothing about a suggestion is injected."""
    write_memory(store, ["- [m-001] a", "- [m-002] b", "- [m-003] c"])
    remove_inbox(monkeypatch)
    without = (await fire(mod.MemoryInjectHook(FakeCoordinator(), {}))).context_injection
    install_inbox(
        monkeypatch,
        FakeInbox([suggestion("s-042", "NEVER-IN-CONTEXT"), suggestion("s-043", "ALSO-NEVER")]),
    )
    with_inbox = (await fire(mod.MemoryInjectHook(FakeCoordinator(), {}))).context_injection

    print("=== block with an inbox of 2 ===")
    print(with_inbox)
    print("identical to the no-inbox block:", with_inbox == without)

    assert with_inbox == without
    for leak in ("NEVER-IN-CONTEXT", "ALSO-NEVER", "s-042", "s-043", "suggestion"):
        assert leak not in with_inbox


async def test_no_inbox_in_this_build_renders_nothing_and_logs_nothing(
    store, tmp_path, monkeypatch
):
    """§5's surface is off, not broken, in a build with no inbox."""
    write_memory(store, ["- [m-001] a"])
    remove_inbox(monkeypatch)
    log = tmp_path / "memory-errors.log"
    coordinator = DisplayCoordinator()

    result = await fire(mod.MemoryInjectHook(coordinator, {}))

    print("show_message calls:", coordinator.display_system.calls)
    print("error log exists:", log.exists())
    assert coordinator.display_system.calls == [
        ("1 memory loaded.", "info", "amplifier-memory")
    ]
    assert result.action == "inject_context"
    assert not log.exists()


async def test_an_inbox_that_raises_costs_one_log_line_and_no_line(store, tmp_path, monkeypatch):
    """Fail open (session.v2 §10's rule, applied to §5's count)."""
    write_memory(store, ["- [m-001] a"])
    install_inbox(monkeypatch, FakeInbox([], explode=OSError("inbox.md is a directory")))
    log = tmp_path / "memory-errors.log"
    coordinator = DisplayCoordinator()
    hook = mod.MemoryInjectHook(coordinator, {})

    first = await fire(hook)
    await hook.on_context_compaction("context:compaction", {})
    await fire(hook)  # the second occasion: same reason, still one log line

    lines = log.read_text(encoding="utf-8").splitlines() if log.exists() else []
    print("show_message calls:", coordinator.display_system.calls)
    print("error log:", lines)

    assert first.action == "inject_context" and first.context_injection
    assert all("suggestion" not in message for message, _, _ in coordinator.display_system.calls)
    assert len(lines) == 1
    assert "inbox not read: OSError: inbox.md is a directory" in lines[0]


async def test_the_second_line_returns_after_a_compaction_and_never_between(store, monkeypatch):
    """§5 rides §2's occasions exactly: the first request, and the first after a compaction."""
    write_memory(store, ["- [m-001] a", "- [m-002] b", "- [m-003] c"])
    install_inbox(monkeypatch, FakeInbox([suggestion("s-042", "x"), suggestion("s-043", "y")]))
    coordinator = DisplayCoordinator()
    hook = mod.MemoryInjectHook(coordinator, {})

    await fire(hook)
    await fire(hook)
    await hook.on_context_compaction("context:compaction", {})
    await fire(hook)
    await fire(hook)

    print("4 requests + one compaction ->")
    for call in coordinator.display_system.calls:
        print("   ", call[0])
    assert [message for message, _, _ in coordinator.display_system.calls] == [
        "3 memories loaded. /memory to see them.",
        "2 suggestions waiting. /memory review to see them.",
        "context compacted. 3 memories still loaded.",
        "2 suggestions waiting. /memory review to see them.",
    ]


async def test_without_a_display_system_both_lines_fall_back_to_user_message(store, monkeypatch):
    write_memory(store, ["- [m-001] a"])
    install_inbox(monkeypatch, FakeInbox([suggestion("s-042", "x")]))
    result = await fire(mod.MemoryInjectHook(FakeCoordinator(), {}))
    print("no display system -> user_message:", repr(result.user_message))
    assert result.user_message == (
        "1 memory loaded.\n1 suggestion waiting. /memory review to see it."
    )


def test_suggestions_line_is_the_contract_line_and_nothing_at_zero():
    print("0 ->", repr(mod.suggestions_line(0)))
    print("1 ->", repr(mod.suggestions_line(1)))
    print("3 ->", repr(mod.suggestions_line(3)))
    assert mod.suggestions_line(0) is None
    assert mod.suggestions_line(-1) is None
    assert mod.suggestions_line(1) == "1 suggestion waiting. /memory review to see it."
    assert mod.suggestions_line(3) == "3 suggestions waiting. /memory review to see them."
    for line in (mod.suggestions_line(1), mod.suggestions_line(3)):
        assert not any(bad in line for bad in mod.RENDER_UNSAFE)
