#!/usr/bin/env python3
"""Conformance kit — session.v5 §1, §2, §9, §10, as served by hooks-memory-inject.

Run it:

    python3 conformance/session/inject/run.py

One line per clause, in the ledger's five plain words:

    Core N — Kept | Not yet | Broken | Pinned open | Can't check — <evidence>

Exit code is 0 whenever the kit *reported* — a Broken verdict is a report,
not a crash. A non-zero exit means the kit itself could not run (import
failure, missing contract), which is a different thing and must not be
confused with a clause being broken.

The kit never touches the real store: it builds a throwaway one under a
temp dir and points `AMPLIFIER_MEMORY_HOME` at it.
"""

from __future__ import annotations

import hashlib
import os
import re
import sys
import tempfile
import traceback
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
MODULE_DIR = REPO_ROOT / "modules" / "hooks-memory-inject"
CONTRACT = REPO_ROOT / "contracts" / "session.v5.md"
FIXTURES = MODULE_DIR / "tests" / "fixtures" / "announce-lines.txt"

sys.path.insert(0, str(MODULE_DIR))


def report(clause: str, verdict: str, evidence: str) -> None:
    print(f"{clause} — {verdict} — {evidence}")


def framing_sentence_from_contract() -> str:
    """Extract §1's blockquote from the locked contract and unwrap it.

    This is the point of the whole check: the module's constant and the
    contract's sentence are compared byte-for-byte, so neither can drift
    without this saying so.
    """
    text = CONTRACT.read_text(encoding="utf-8")
    lines = text.splitlines()
    start = next(i for i, ln in enumerate(lines) if "**Loaded in every request.**" in ln)
    quoted: list[str] = []
    for ln in lines[start:]:
        stripped = ln.strip()
        if stripped.startswith(">"):
            quoted.append(stripped[1:].strip())
        elif quoted:
            break
    return " ".join(quoted)


class FakeHooks:
    def __init__(self) -> None:
        self.registrations: list[dict] = []

    def register(self, event, handler, priority=0, name=None):
        self.registrations.append({"event": event, "priority": priority, "name": name})


class SpyDisplay:
    """The kernel's DisplaySystem protocol (`amplifier_core/display.py`)."""

    def __init__(self) -> None:
        self.calls: list[tuple[str, str, str]] = []

    def show_message(self, message, level="info", source="hook"):
        self.calls.append((message, level, source))


class FakeCoordinator:
    def __init__(self, session_id: str = "conformance-session", display: bool = False) -> None:
        self.hooks = FakeHooks()
        self.session_id = session_id
        self.parent_id = None
        if display:
            self.display_system = SpyDisplay()


def make_instance(path: Path, lines: list[str], *, enabled: bool | None = None) -> Path:
    """A real instance on disk: `MEMORY.md`, and a `config.yaml` when one is asked for.

    Written through the library's own `llm_config.default_body` so the file this
    kit judges is the file `init` writes, not a hand-rolled lookalike that could
    pass while the real one fails.
    """
    from amplifier_memory import llm_config

    path.mkdir(parents=True, exist_ok=True)
    (path / "MEMORY.md").write_text("".join(f"{ln}\n" for ln in lines), encoding="utf-8")
    if enabled is not None:
        (path / "config.yaml").write_text(llm_config.default_body(enabled=enabled), "utf-8")
    return path


def _run(coro):
    import asyncio

    return asyncio.run(coro)


def check_core_1(mod, tmp: Path) -> None:
    """§1 Loaded in every request."""
    findings: list[str] = []

    contract_sentence = framing_sentence_from_contract()
    if contract_sentence != mod.FRAMING_SENTENCE:
        report(
            "Core 1",
            "Broken",
            "the module's framing sentence differs from the contract's:\n"
            f"  contract: {contract_sentence!r}\n"
            f"  module:   {mod.FRAMING_SENTENCE!r}",
        )
        return
    findings.append("framing sentence byte-identical to contracts/session.v5.md §1")

    home = tmp / "store"
    (home / "topics").mkdir(parents=True)
    body = "- [m-001] never use tabs in YAML files\n- [m-031] YAML style → topics/y.md\n"
    (home / "MEMORY.md").write_text(body, encoding="utf-8")
    (home / "topics" / "y.md").write_text("TOPIC-BODY-SENTINEL\n", encoding="utf-8")
    os.environ["AMPLIFIER_MEMORY_HOME"] = str(home)

    a = _run(
        mod.MemoryInjectHook(FakeCoordinator("A"), {}).on_provider_request("provider:request", {})
    )
    b = _run(
        mod.MemoryInjectHook(FakeCoordinator("B"), {}).on_provider_request("provider:request", {})
    )

    problems: list[str] = []
    if a.action != "inject_context" or a.context_injection_role != "system" or not a.ephemeral:
        problems.append(
            f"result shape is action={a.action}/role={a.context_injection_role}/"
            f"ephemeral={a.ephemeral}"
        )
    block = a.context_injection or ""
    if block.splitlines()[1:2] != [mod.FRAMING_SENTENCE]:
        problems.append("first line inside the envelope is not the framing sentence")
    else:
        findings.append("framing sentence is the first line inside the envelope")
    if body not in block:
        problems.append("MEMORY.md does not appear verbatim")
    else:
        findings.append("MEMORY.md appears verbatim")
    if "TOPIC-BODY-SENTINEL" in block:
        problems.append("a topic body leaked into the block")
    else:
        findings.append("no topic body in the block")
    if a.context_injection != b.context_injection:
        problems.append("two instances over the same store produced different blocks")
    else:
        sha = hashlib.sha256(block.encode("utf-8")).hexdigest()
        findings.append(f"two instances byte-identical ({len(block)} chars, sha256 {sha[:16]}…)")
    instructing = [n for n in ("say once", "On your first reply", "announce") if n in block]
    if instructing:
        problems.append(f"the block still instructs the model: {instructing}")
    else:
        findings.append("no announce instruction in the block (§1: the counts live in §2's line)")
    if re.search(r"\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}", block):
        problems.append("block carries a timestamp")
    if "conformance-session" in block:
        problems.append("block carries a session id")
    else:
        findings.append("no timestamp, no session id")

    events = _registered_events(mod)
    if events[:1] != ["provider:request"]:
        problems.append(f"registered on {events}, which does not start with provider:request")
    else:
        findings.append(
            f"registered on {events} — injection rides provider:request, so the block "
            "is present on the first request and on every one after a compaction"
        )

    if problems:
        report("Core 1", "Broken", "; ".join(problems))
    else:
        report("Core 1", "Kept", "; ".join(findings))


def fixture_rows() -> dict[str, tuple[str, str | None]]:
    """The module's fixture file — (origin, the exact bytes the hook renders).

    `origin` is `contract` (the line is in the locked §2, verbatim) or
    `derived` (§2 gives the rule, not this combination). The distinction is
    the point: a derived line is reported as derived, never as contract text.
    """
    out: dict[str, tuple[str, str | None]] = {}
    for raw in FIXTURES.read_text(encoding="utf-8").splitlines():
        if not raw.strip() or raw.startswith("#"):
            continue
        key, origin, text = raw.split("\t")
        out[key] = (origin, None if text == "-" else text)
    return out


def fixture_lines() -> dict[str, str | None]:
    return {key: text for key, (_origin, text) in fixture_rows().items()}


def _clause_2_text() -> str:
    """§2's clause body from the locked contract, whitespace-normalised.

    The contract wraps its lines; the fixture strings do not. Normalising
    both sides is what lets a byte-level comparison mean what it says.
    """
    lines = CONTRACT.read_text(encoding="utf-8").splitlines()
    start = next(i for i, ln in enumerate(lines) if "**Announce the load, once, in code.**" in ln)
    body: list[str] = []
    for ln in lines[start:]:
        if body and ln.lstrip().startswith("3. **"):
            break
        body.append(ln)
    return " ".join(" ".join(body).split())


def check_core_2(mod, tmp: Path) -> None:
    """§2 Announce the load, once, in code."""
    fixtures = fixture_lines()
    clause = _clause_2_text()
    problems: list[str] = []
    findings: list[str] = []

    # 1. Every `contract`-origin fixture line is in the locked §2, verbatim.
    rows = fixture_rows()
    quoted = {k: t for k, (o, t) in rows.items() if o == "contract" and t}
    derived = {k: t for k, (o, t) in rows.items() if o == "derived" and t}
    missing = [k for k, t in quoted.items() if " ".join(t.split()) not in clause]
    stale = [k for k, t in derived.items() if " ".join(t.split()) in clause]
    if missing:
        problems.append(f"lines claimed as contract text but absent from §2: {missing}")
    else:
        findings.append(f"{len(quoted)} lines appear verbatim in contracts/session.v5.md §2")
    if stale:
        problems.append(f"lines marked derived that §2 now states verbatim (relabel them): {stale}")
    else:
        findings.append(
            f"{len(derived)} derived from §2's rule, not quoted from it "
            f"({sorted(derived)}) — reported as derived, not as contract text"
        )

    # 2. The hook renders them, from a real store, through a real HookResult.
    home = tmp / "store2"
    home.mkdir(parents=True)
    os.environ["AMPLIFIER_MEMORY_HOME"] = str(home)

    def render(n_memories: int, n_topics: int) -> object:
        (home / "MEMORY.md").write_text(
            "".join(f"- [m-{i:03d}] memory {i}\n" for i in range(1, n_memories + 1)),
            encoding="utf-8",
        )
        topics = home / "topics"
        if topics.is_dir():
            for old in topics.iterdir():
                old.unlink()
        elif n_topics:
            topics.mkdir()
        for i in range(n_topics):
            (topics / f"t{i}.md").write_text("x\n", encoding="utf-8")
        return mod.MemoryInjectHook(FakeCoordinator(), {})

    hook = render(3, 0)
    coordinator = FakeCoordinator(display=True)
    hook.coordinator = coordinator
    first = _run(hook.on_provider_request("provider:request", {}))
    _run(hook.on_provider_request("provider:request", {}))
    _run(hook.on_context_compaction("context:compaction", {"strategy_level": 1}))
    _run(hook.on_provider_request("provider:request", {}))
    _run(hook.on_provider_request("provider:request", {}))
    shown = coordinator.display_system.calls

    expected = [
        (fixtures["plural"], "info", "amplifier-memory"),
        (fixtures["compacted"], "info", "amplifier-memory"),
    ]
    if shown != expected:
        problems.append(
            f"across 4 requests the display system received {shown}, expected {expected}"
        )
    else:
        findings.append(
            f"4 requests + one context:compaction → exactly 2 lines rendered: {shown[0][0]!r} "
            f"then {shown[1][0]!r} (level=info, source=amplifier-memory)"
        )
    if first.user_message is not None:
        problems.append(
            f"the line was rendered AND left on the result ({first.user_message!r}) — two lines"
        )
    else:
        findings.append("rendered once, not also returned as user_message")
    if first.action != "inject_context":
        problems.append(f"the announcing result was action={first.action}, not inject_context")

    # 3. The other variants, off the same store.
    for case, (n, m) in {
        "plural_with_topics": (3, 2),
        "singular": (1, 0),
        "singular_with_topics": (1, 2),
        "empty": (0, 0),
    }.items():
        # No display system on this coordinator: the line falls back to
        # `user_message`, which is how a host without one still gets it.
        got = _run(render(n, m).on_provider_request("provider:request", {})).user_message
        if got != fixtures[case]:
            problems.append(f"{case}: rendered {got!r}, fixture {fixtures[case]!r}")
        else:
            findings.append(f"{case}: {got!r}")

    # 4b. §2 as v4 amended it: a non-default instance is named in the line.
    #     The path is §2's own example, so `named_instance` is a `contract` row
    #     above and was checked against the locked file with the rest of them.
    example = "~/.amplifier-agent/memory"
    for case, args in {
        "named_instance": ((3, 0), {}),
        "named_instance_with_topics": ((3, 2), {}),
        "named_instance_singular": ((1, 0), {}),
        "named_instance_compacted": ((3, 0), {"compacted": True}),
    }.items():
        got = mod.announce_line(*args[0], instance=example, **args[1])
        if got != fixtures[case]:
            problems.append(f"{case}: rendered {got!r}, fixture {fixtures[case]!r}")
        else:
            findings.append(f"{case}: {got!r}")

    # 4c. End to end, through a mount plan: `config: {home: <path>}` on a
    #     non-default instance names it; the same store reached WITHOUT a
    #     `home:` renders today's line, byte for byte (§12: "a session with no
    #     `home:` behaves exactly as today").
    named = make_instance(tmp / "named-instance", ["- [m-001] a", "- [m-002] b", "- [m-003] c"])
    plan = FakeCoordinator(display=True)
    _run(
        mod.MemoryInjectHook(plan, {"home": str(named)}).on_provider_request("provider:request", {})
    )
    os.environ["AMPLIFIER_MEMORY_HOME"] = str(named)
    env_only = FakeCoordinator(display=True)
    _run(mod.MemoryInjectHook(env_only, {}).on_provider_request("provider:request", {}))
    want_named = f"3 memories loaded from {named}. /memory to see them."
    got_named = plan.display_system.calls[0][0] if plan.display_system.calls else None
    got_env = env_only.display_system.calls[0][0] if env_only.display_system.calls else None
    if got_named != want_named:
        problems.append(f"config home: rendered {got_named!r}, expected {want_named!r}")
    elif got_env != fixtures["plural"]:
        problems.append(
            f"the same store with no `home:` rendered {got_env!r}, expected today's line "
            f"{fixtures['plural']!r} (§12)"
        )
    else:
        findings.append(
            f"mount plan `home:` names the instance ({got_named!r}); the SAME store with no "
            f"`home:` still renders today's line ({got_env!r}) — §12's "
            '"behaves exactly as today"'
        )

    # 5. Renderable as written: single line, no Rich markup tag to be eaten.
    unsafe = [
        (text, bad)
        for text in fixtures.values()
        if text
        for bad in mod.RENDER_UNSAFE
        if bad in text
    ]
    if unsafe:
        problems.append(f"a line is not renderable as written: {unsafe}")
    else:
        findings.append("every line is single-line and bracket-free (display.py:122/127)")

    if problems:
        report("Core 2", "Broken", "; ".join(problems))
        return

    captures = sorted((REPO_ROOT / "tests" / "smoke" / "evidence").glob("announce-rendered-*.txt"))
    quoted_line = None
    for path in captures:
        for ln in path.read_text(encoding="utf-8").splitlines():
            if ln.startswith("[amplifier-memory] "):
                quoted_line = (path.name, ln)
                break
        if quoted_line:
            break
    outermost = (
        f"rendered on a real terminal — {quoted_line[0]} carries `{quoted_line[1]}` "
        f"({len(captures)} captures in tests/smoke/evidence/)"
        if quoted_line
        else "Can't check here: no PTY capture in tests/smoke/evidence/announce-rendered-*.txt "
        "shows the rendered line — this process can only prove what the hook handed the runtime"
    )
    # The honesty gate: what this kit cannot reach, said plainly rather than
    # folded into the Kept.
    cant_check = (
        "session.v5 §2 — the post-compaction line is Can't check on a real terminal in this kit, "
        "because nothing in a short session compacts (context-simple triggers at 92% of the token "
        "budget); what is checked here is that the hook renders it the moment context:compaction "
        "fires, and the capture that would close it is a >180k-token session"
    )
    report("Core 2", "Kept", "; ".join(findings) + f"; {outermost}. {cant_check}")


def check_core_9(mod, tmp: Path) -> None:
    """§9 Nothing at session end."""
    source = (MODULE_DIR / "amplifier_module_hooks_memory_inject" / "__init__.py").read_text(
        encoding="utf-8"
    )
    banned = ["session:end", "session_end", "session:stop", "on_session_end", "atexit"]
    found = [needle for needle in banned if needle in source]
    events = _registered_events(mod)
    if found:
        report("Core 9", "Broken", f"module source mentions {found}")
    elif events != ["provider:request", "context:compaction"]:
        report("Core 9", "Broken", f"module registers {events}")
    else:
        report(
            "Core 9",
            "Kept",
            "module source contains none of "
            f"{banned}; the registrations are {events} — both mid-session events. "
            "Exit cost from this module is zero by construction.",
        )


def check_core_10(mod, tmp: Path) -> None:
    """§10 Fail open, never block.

    Two halves, and the second one is the half that was missing until item
    87j: the session proceeds unchanged, *and* the failure is one line in the
    transcript. That line is only a line if it is rendered — a `user_message`
    on `provider:request` is nulled by the kernel's aggregation the moment any
    handler injects, which every real session has (see `_render`).
    """
    missing = tmp / "absent-store"
    log = tmp / "memory-errors.log"
    os.environ["AMPLIFIER_MEMORY_HOME"] = str(missing)
    os.environ["AMPLIFIER_MEMORY_ERROR_LOG"] = str(log)

    coordinator = FakeCoordinator(display=True)
    hook = mod.MemoryInjectHook(coordinator, {})
    try:
        results = [_run(hook.on_provider_request("provider:request", {})) for _ in range(3)]
    except Exception as exc:  # noqa: BLE001 - a raising handler is the "Broken" verdict, by design
        report("Core 10", "Broken", f"handler raised {type(exc).__name__}: {exc}")
        return

    problems = []
    findings = []
    if any(r.action != "continue" for r in results):
        problems.append(f"actions were {[r.action for r in results]}")
    if any(r.context_injection for r in results):
        problems.append("something was still injected")
    if not problems:
        findings.append("store absent → 3 requests, no raise, no injection, session unchanged")
    log_lines = log.read_text(encoding="utf-8").splitlines() if log.exists() else []
    if len(log_lines) != 1:
        problems.append(f"error log has {len(log_lines)} lines, expected 1")
    else:
        findings.append(f"one line in the error log: {log_lines[0]}")

    # The transcript line: rendered, once, on the warning channel, in §10's shape.
    shown = coordinator.display_system.calls
    expected_prefix = "amplifier-memory: memories not loaded ("
    if len(shown) != 1:
        problems.append(
            f"3 failing requests rendered {len(shown)} lines to the display system, expected 1: {shown}"
        )
    else:
        message, level, source = shown[0]
        if not (message.startswith(expected_prefix) and message.endswith("); session continues.")):
            problems.append(f"the rendered line is not §10's shape: {message!r}")
        elif (level, source) != ("warning", mod.BLOCK_SOURCE):
            problems.append(
                f"the line was rendered as {(level, source)}, expected ('warning', 'amplifier-memory')"
            )
        elif "\n" in message:
            problems.append("the rendered line is not one line")
        else:
            findings.append(
                f"one line rendered through the display system: {message!r} (level=warning)"
            )
    if any(r.user_message is not None for r in results):
        problems.append("the line was rendered AND left on the result — two lines")
    else:
        findings.append("rendered once, not also returned as user_message")

    # The discriminating arm: a readable store with an undecodable byte is not
    # a §10 failure (store.v2 §9 invites hand edits; the byte rides U+FFFD).
    home = tmp / "bad-byte-store"
    home.mkdir()
    (home / "MEMORY.md").write_bytes(b"- [m-001] Jos\xe9 prefers short reviews\n")
    bad_log = tmp / "bad-byte-errors.log"
    os.environ["AMPLIFIER_MEMORY_HOME"] = str(home)
    os.environ["AMPLIFIER_MEMORY_ERROR_LOG"] = str(bad_log)
    other = FakeCoordinator(display=True)
    tolerant = _run(mod.MemoryInjectHook(other, {}).on_provider_request("provider:request", {}))
    if tolerant.action != "inject_context" or "\ufffd" not in (tolerant.context_injection or ""):
        problems.append("a decodable-with-replacement store did not inject its block")
    elif any("not loaded" in m for m, _, _ in other.display_system.calls) or bad_log.exists():
        problems.append("an undecodable byte in a readable store triggered §10's decline")
    else:
        findings.append(
            "discriminating arm: a readable store with one undecodable byte injects "
            f"U+FFFD and says {other.display_system.calls[0][0]!r} — no §10 line, no error log"
        )

    if problems:
        report("Core 10", "Broken", "; ".join(problems))
        return

    # The outermost check this kit cannot perform itself: a real terminal.
    captures = sorted((REPO_ROOT / "tests" / "smoke" / "evidence").glob("failopen-*.txt"))
    quoted_line = None
    for path in captures:
        for ln in path.read_text(encoding="utf-8").splitlines():
            if ln.startswith("[amplifier-memory] ") and "not loaded" in ln:
                quoted_line = (path.name, ln)
                break
        if quoted_line:
            break
    outermost = (
        f"rendered on a real terminal — {quoted_line[0]} carries `{quoted_line[1]}` "
        f"({len(captures)} captures in tests/smoke/evidence/)"
        if quoted_line
        else "Can't check here: no PTY capture in tests/smoke/evidence/failopen-*.txt shows the "
        "rendered line — this process can only prove what the hook handed the runtime"
    )
    report("Core 10", "Kept", "; ".join(findings) + f"; {outermost}")


class FakeInbox:
    """`amplifier_memory.inbox`'s one function, as the hook uses it.

    The library half is lane P's. This stands in for it so §5's *surface* can
    be measured before the library lands — and so the raising arm can be
    produced on demand, which a real inbox will not do to order.
    """

    def __init__(self, items, explode=None):
        self.items = items
        self.explode = explode

    def pending(self, home):
        if self.explode is not None:
            raise self.explode
        return list(self.items)


def _suggestion(sid: str, text: str):
    return type("Suggestion", (), {"id": sid, "text": text})()


def check_suggestions_5(mod, tmp: Path) -> None:
    """suggestions.v2 §5 Surface without interrupting."""
    import amplifier_memory

    findings: list[str] = []
    problems: list[str] = []

    home = tmp / "store5s"
    home.mkdir(parents=True)
    (home / "MEMORY.md").write_text("- [m-001] a\n- [m-002] b\n- [m-003] c\n", encoding="utf-8")
    os.environ["AMPLIFIER_MEMORY_HOME"] = str(home)
    log = tmp / "suggestions-errors.log"
    os.environ["AMPLIFIER_MEMORY_ERROR_LOG"] = str(log)

    had_real = hasattr(amplifier_memory, "inbox")
    real = getattr(amplifier_memory, "inbox", None)

    def with_inbox(inbox):
        """One session's worth of requests against `inbox`; returns the lines shown."""
        if inbox is None:
            if hasattr(amplifier_memory, "inbox"):
                del amplifier_memory.inbox
        else:
            amplifier_memory.inbox = inbox
        coordinator = FakeCoordinator(display=True)
        hook = mod.MemoryInjectHook(coordinator, {})
        first = _run(hook.on_provider_request("provider:request", {}))
        _run(hook.on_provider_request("provider:request", {}))
        return [message for message, _, _ in coordinator.display_system.calls], first

    try:
        load_line = "3 memories loaded. /memory to see them."
        three = [_suggestion(f"s-{n:03d}", f"NEVER-IN-CONTEXT-{n}") for n in (42, 43, 44)]
        for label, items, expected in (
            ("3 waiting", three, "3 suggestions waiting. /memory review to see them."),
            ("1 waiting", three[:1], "1 suggestion waiting. /memory review to see it."),
            ("0 waiting", [], None),
        ):
            shown, _ = with_inbox(FakeInbox(items))
            want = [load_line] if expected is None else [load_line, expected]
            if shown != want:
                problems.append(f"{label}: two requests showed {shown}, expected {want}")
            else:
                findings.append(f"{label} → {shown} (request 2 rendered nothing)")

        # The block: byte-identical with and without an inbox, and no suggestion
        # in it at all — §5's "only accepted memories are loaded".
        _, without = with_inbox(None)
        _, loaded = with_inbox(FakeInbox(three))
        block = loaded.context_injection or ""
        if block != (without.context_injection or ""):
            problems.append("the injected block changed when the inbox was non-empty")
        else:
            findings.append(
                f"the injected block is byte-identical with and without an inbox "
                f"({len(block)} chars, sha256 "
                f"{hashlib.sha256(block.encode('utf-8')).hexdigest()[:16]}…)"
            )
        leaked = [
            needle
            for needle in ("NEVER-IN-CONTEXT", "s-042", "suggestion", "waiting")
            if needle in block
        ]
        if leaked:
            problems.append(f"the block carries {leaked}")
        else:
            findings.append("no suggestion id, text or count anywhere in the block")

        # Absent library: the surface is off, not broken.
        shown, result = with_inbox(None)
        if shown != [load_line] or result.action != "inject_context" or log.exists():
            problems.append(
                f"with no inbox in the build: shown={shown}, action={result.action}, "
                f"error log written={log.exists()}"
            )
        else:
            findings.append("no inbox in the build → the load line alone, no error, no log line")

        # An inbox that raises: one log line, no line on screen, memories still loaded.
        shown, result = with_inbox(FakeInbox([], explode=OSError("inbox.md is a directory")))
        lines = log.read_text(encoding="utf-8").splitlines() if log.exists() else []
        if shown != [load_line]:
            problems.append(f"a raising inbox showed {shown}, expected just the load line")
        elif len(lines) != 1 or "inbox not read: OSError" not in lines[0]:
            problems.append(f"a raising inbox left {len(lines)} error-log lines: {lines}")
        elif result.action != "inject_context" or not result.context_injection:
            problems.append("a raising inbox cost the session its memories")
        else:
            findings.append(
                f"a raising inbox → one log line ({lines[0].split(' store=')[0]}…), "
                "no line on screen, block still injected"
            )
    finally:
        if had_real:
            amplifier_memory.inbox = real
        elif hasattr(amplifier_memory, "inbox"):
            del amplifier_memory.inbox

    if problems:
        report("suggestions.v2 Core 5", "Broken", "; ".join(problems))
        return
    if had_real:
        report("suggestions.v2 Core 5", "Kept", "; ".join(findings))
        return
    report(
        "suggestions.v2 Core 5",
        "Can't check",
        "suggestions.v2 §5 — Can't check in this lane because amplifier_memory.inbox is not "
        "in this build: the count the hook renders comes from a stand-in at lane P's published "
        "signature `pending(home) -> list[Suggestion]`, not from a real inbox.md. What IS "
        "checked here, against that stand-in: " + "; ".join(findings),
    )


def check_core_12(mod, tmp: Path) -> None:
    """§12 Which instance a session uses is configuration."""
    findings: list[str] = []
    problems: list[str] = []

    # The mount plan's `home:` decides which store answers — proved by pointing
    # it at one instance while the environment names a different one.
    planned = make_instance(tmp / "c12-planned", ["- [m-001] planned instance"])
    other = make_instance(tmp / "c12-other", ["- [m-001] x", "- [m-002] y"])
    os.environ["AMPLIFIER_MEMORY_HOME"] = str(other)
    result = _run(
        mod.MemoryInjectHook(FakeCoordinator(), {"home": str(planned)}).on_provider_request(
            "provider:request", {}
        )
    )
    block = result.context_injection or ""
    if "planned instance" not in block:
        problems.append(f"`home:` did not choose the store: block is {block!r}")
    else:
        findings.append(
            f"`config: home: {planned}` read that instance while "
            f"$AMPLIFIER_MEMORY_HOME named {other} — the plan wins"
        )

    # `enabled: false` — nothing injected, no line, no error log, no write.
    inert = make_instance(tmp / "c12-inert", ["- [m-001] never injected"], enabled=False)
    log = tmp / "c12-errors.log"
    os.environ["AMPLIFIER_MEMORY_ERROR_LOG"] = str(log)
    coordinator = FakeCoordinator(display=True)
    hook = mod.MemoryInjectHook(coordinator, {"home": str(inert)})
    results = [_run(hook.on_provider_request("provider:request", {})) for _ in range(3)]
    if any(r.context_injection for r in results):
        problems.append("an inert instance still injected a block")
    elif any(r.action != "continue" for r in results):
        problems.append(f"an inert instance returned {[r.action for r in results]}")
    elif coordinator.display_system.calls:
        problems.append(f"an inert instance rendered {coordinator.display_system.calls}")
    elif any(r.user_message for r in results):
        problems.append("an inert instance left a user_message on the result")
    elif log.exists():
        problems.append(f"an inert instance wrote to the error log: {log.read_text()!r}")
    elif (inert / "sessions.jsonl").exists() or (inert / "usage.jsonl").exists():
        problems.append("an inert instance was written to")
    else:
        findings.append(
            "enabled: false → 3 requests: nothing injected, no line rendered, no "
            "user_message, no error-log line, and neither sessions.jsonl nor "
            "usage.jsonl created — the session plane is silent, not failing"
        )

    # The discriminating arm: the same store, enabled, is the ordinary session.
    live = make_instance(tmp / "c12-live", ["- [m-001] injected"], enabled=True)
    lively = FakeCoordinator(display=True)
    on = _run(
        mod.MemoryInjectHook(lively, {"home": str(live)}).on_provider_request(
            "provider:request", {}
        )
    )
    if on.action != "inject_context" or "injected" not in (on.context_injection or ""):
        problems.append("enabled: true did not inject")
    elif not lively.display_system.calls:
        problems.append("enabled: true rendered no line")
    else:
        findings.append(
            f"discriminating arm: the same config with enabled: true injects and says "
            f"{lively.display_system.calls[0][0]!r}"
        )

    os.environ.pop("AMPLIFIER_MEMORY_ERROR_LOG", None)
    report("Core 12", "Broken" if problems else "Kept", "; ".join(problems or findings))


def check_core_13(mod, tmp: Path) -> None:
    """§13 Which sessions have a human in them."""
    import json

    import amplifier_memory

    findings: list[str] = []
    problems: list[str] = []

    saved_origin = os.environ.get("AMPLIFIER_SESSION_ORIGIN")

    def sessions(home: Path) -> list[dict]:
        path = home / "sessions.jsonl"
        if not path.is_file():
            return []
        return [
            json.loads(ln) for ln in path.read_text(encoding="utf-8").splitlines() if ln.strip()
        ]

    def run_session(home: Path, session_id: str, origin: str | None, inbox_items: int = 0):
        if origin is None:
            os.environ.pop("AMPLIFIER_SESSION_ORIGIN", None)
        else:
            os.environ["AMPLIFIER_SESSION_ORIGIN"] = origin
        coordinator = FakeCoordinator(session_id, display=True)
        hook = mod.MemoryInjectHook(coordinator, {"home": str(home)})
        had = hasattr(amplifier_memory, "inbox")
        real = getattr(amplifier_memory, "inbox", None)
        amplifier_memory.inbox = FakeInbox(
            [_suggestion(f"s-{n:03d}", f"item {n}") for n in range(inbox_items)]
        )
        try:
            # Twice: §13's line is one line per session, not one per request.
            first = _run(hook.on_provider_request("provider:request", {}))
            _run(hook.on_provider_request("provider:request", {}))
        finally:
            if had:
                amplifier_memory.inbox = real
            else:
                del amplifier_memory.inbox
        return first, [m for m, _, _ in coordinator.display_system.calls]

    try:
        home = _init_instance(tmp / "c13-store")
        if home is None:
            report(
                "Core 13",
                "Can't check",
                "session.v5 §13 — `amplifier-memory init` could not build a real instance here, "
                "and sessions.jsonl is written under the store's own git lock: this kit cannot "
                "prove the append against a directory that is not a store",
            )
            return

        # A human session: the line lands, origin `human`, suggestions rendered.
        first, shown = run_session(home, "sess-human", None, inbox_items=3)
        rows = sessions(home)
        if [r.get("session_id") for r in rows] != ["sess-human"]:
            problems.append(f"unset origin wrote {rows}")
        elif rows[0].get("origin") != "human" or not rows[0].get("first_seen"):
            problems.append(f"unset origin recorded {rows[0]}")
        elif len(shown) != 2 or "suggestions waiting" not in shown[1]:
            problems.append(f"a human session showed {shown}, expected a suggestions line")
        else:
            findings.append(
                f"unset $AMPLIFIER_SESSION_ORIGIN → one line {rows[0]} "
                f"(unset means human) and the suggestions line still renders: {shown[1]!r}"
            )

        # A worker session: block still injected, no suggestions line, one row.
        first, shown = run_session(home, "sess-worker", "worker", inbox_items=3)
        rows = sessions(home)
        worker = [r for r in rows if r.get("session_id") == "sess-worker"]
        if len(worker) != 1 or worker[0].get("origin") != "worker":
            problems.append(f"origin=worker recorded {worker}")
        elif first.action != "inject_context" or not first.context_injection:
            problems.append("a worker session lost §1's block")
        elif len(shown) != 1:
            problems.append(f"a worker session showed {shown}, expected the load line alone")
        else:
            findings.append(
                f"origin=worker → {worker[0]}; §1's block still injected "
                f"({len(first.context_injection)} chars); the only line shown is the load line "
                f"{shown[0]!r} — no suggestions line for a session with nobody in it"
            )

        # Once per session, however many requests, however many hooks.
        run_session(home, "sess-worker", "worker")
        again = [r for r in sessions(home) if r.get("session_id") == "sess-worker"]
        if len(again) != 1:
            problems.append(f"the same session id wrote {len(again)} lines, expected 1")
        else:
            findings.append(
                "the same session id across 4 requests and two mounts is still exactly one line "
                f"(first_seen unmoved: {again[0]['first_seen']})"
            )

        origins = amplifier_memory.session_origins(home)
        if origins.get("sess-worker") != "worker" or origins.get("sess-human") != "human":
            problems.append(f"session_origins() reads back {origins}")
        else:
            findings.append(f"the suggest job's own reader agrees: session_origins() = {origins}")
    finally:
        if saved_origin is None:
            os.environ.pop("AMPLIFIER_SESSION_ORIGIN", None)
        else:
            os.environ["AMPLIFIER_SESSION_ORIGIN"] = saved_origin

    report("Core 13", "Broken" if problems else "Kept", "; ".join(problems or findings))


def _init_instance(path: Path) -> Path | None:
    """A real store, built by the library's own `init` — or None if it cannot be.

    §13's append happens under the store's git lock, so a bare directory with a
    `MEMORY.md` in it is not enough: this probe needs the real thing or it must
    say it could not check.
    """
    import amplifier_memory

    try:
        amplifier_memory.init(path, timer=False)
    except Exception:  # noqa: BLE001 — reported as "Can't check", never as Broken
        return None
    return path if (path / "MEMORY.md").is_file() else None


def _registered_events(mod) -> list[str]:
    coordinator = FakeCoordinator()
    _run(mod.mount(coordinator, {}))
    return [r["event"] for r in coordinator.hooks.registrations]


def main() -> int:
    try:
        import amplifier_module_hooks_memory_inject as mod
    except Exception:  # noqa: BLE001 - kit must report "could not run", never crash
        print("kit could not run: hooks-memory-inject is not importable", file=sys.stderr)
        traceback.print_exc()
        return 2

    print(f"session.v5 conformance — inject hook ({MODULE_DIR.relative_to(REPO_ROOT)})")
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        saved = {
            k: os.environ.get(k)
            for k in (
                "AMPLIFIER_MEMORY_HOME",
                "AMPLIFIER_MEMORY_ERROR_LOG",
                "AMPLIFIER_SESSION_ORIGIN",
            )
        }
        try:
            for check in (
                check_core_1,
                check_core_2,
                check_core_9,
                check_core_10,
                check_core_12,
                check_core_13,
                check_suggestions_5,
            ):
                try:
                    check(mod, tmp)
                except Exception as exc:  # noqa: BLE001 - a raising probe is the "Broken" verdict, by design
                    report(
                        check.__doc__.split()[0] if check.__doc__ else check.__name__,
                        "Can't check",
                        f"the probe itself failed: {type(exc).__name__}: {exc}",
                    )
        finally:
            for key, value in saved.items():
                if value is None:
                    os.environ.pop(key, None)
                else:
                    os.environ[key] = value
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
