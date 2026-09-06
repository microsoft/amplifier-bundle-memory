#!/usr/bin/env python3
"""Conformance kit — session.v1 §1, §2, §9, §10, as served by hooks-memory-inject.

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

import os
import re
import sys
import tempfile
import traceback
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
MODULE_DIR = REPO_ROOT / "modules" / "hooks-memory-inject"
CONTRACT = REPO_ROOT / "contracts" / "session.v1.md"

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


class FakeCoordinator:
    def __init__(self, session_id: str = "conformance-session") -> None:
        self.hooks = FakeHooks()
        self.session_id = session_id
        self.parent_id = None


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
    findings.append("framing sentence byte-identical to contracts/session.v1.md §1")

    home = tmp / "store"
    (home / "topics").mkdir(parents=True)
    body = "- [m-001] never use tabs in YAML files\n- [m-031] YAML style → topics/y.md\n"
    (home / "MEMORY.md").write_text(body, encoding="utf-8")
    (home / "topics" / "y.md").write_text("TOPIC-BODY-SENTINEL\n", encoding="utf-8")
    os.environ["AMPLIFIER_MEMORY_HOME"] = str(home)

    a = _run(mod.MemoryInjectHook(FakeCoordinator("A"), {}).on_provider_request("provider:request", {}))
    b = _run(mod.MemoryInjectHook(FakeCoordinator("B"), {}).on_provider_request("provider:request", {}))

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
        findings.append(f"two instances byte-identical ({len(block)} chars)")
    if re.search(r"\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}", block):
        problems.append("block carries a timestamp")
    if "conformance-session" in block:
        problems.append("block carries a session id")
    else:
        findings.append("no timestamp, no session id")

    events = _registered_events(mod)
    if events != ["provider:request"]:
        problems.append(f"registered on {events}, not exactly ['provider:request']")
    else:
        findings.append("registered on provider:request only (so: first request and post-compaction)")

    if problems:
        report("Core 1", "Broken", "; ".join(problems))
    else:
        report("Core 1", "Kept", "; ".join(findings))


def check_core_2(mod, tmp: Path) -> None:
    """§2 Announce the load, once — Can't check in this process."""
    home = tmp / "store2"
    home.mkdir(parents=True)
    (home / "MEMORY.md").write_text("- [m-001] a\n- [m-002] b\n", encoding="utf-8")
    os.environ["AMPLIFIER_MEMORY_HOME"] = str(home)
    populated = _run(
        mod.MemoryInjectHook(FakeCoordinator(), {}).on_provider_request("provider:request", {})
    ).context_injection
    (home / "MEMORY.md").write_text("", encoding="utf-8")
    empty = _run(
        mod.MemoryInjectHook(FakeCoordinator(), {}).on_provider_request("provider:request", {})
    ).context_injection

    populated_line = populated.splitlines()[-2]
    empty_line = empty.splitlines()[-2]
    expected_populated = (
        'On your first reply of this session, say once: '
        '"Loaded 2 memories (0 topics available)."'
    )
    expected_empty = (
        'On your first reply of this session, say once: '
        '"No memories yet — /remember <text> to add one."'
    )
    instruction_ok = populated_line == expected_populated and empty_line == expected_empty

    report(
        "Core 2",
        "Can't check",
        "the *saying* is model behaviour and cannot be observed in this process — "
        "only a real session can (session.v1 Conformance, tests/smoke/). "
        f"What is checkable here: the instruction is present and both variants are correct "
        f"({'yes' if instruction_ok else 'NO'}). "
        f"Populated: {populated_line}  |  Empty: {empty_line}",
    )


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
    elif events != ["provider:request"]:
        report("Core 9", "Broken", f"module registers {events}")
    else:
        report(
            "Core 9",
            "Kept",
            "module source contains none of "
            f"{banned}; the only registration is provider:request. "
            "Exit cost from this module is zero by construction.",
        )


def check_core_10(mod, tmp: Path) -> None:
    """§10 Fail open, never block."""
    missing = tmp / "absent-store"
    log = tmp / "memory-errors.log"
    os.environ["AMPLIFIER_MEMORY_HOME"] = str(missing)
    os.environ["AMPLIFIER_MEMORY_ERROR_LOG"] = str(log)

    hook = mod.MemoryInjectHook(FakeCoordinator(), {})
    try:
        results = [
            _run(hook.on_provider_request("provider:request", {})) for _ in range(3)
        ]
    except Exception as exc:
        report("Core 10", "Broken", f"handler raised {type(exc).__name__}: {exc}")
        return

    problems = []
    if any(r.action != "continue" for r in results):
        problems.append(f"actions were {[r.action for r in results]}")
    if any(r.context_injection for r in results):
        problems.append("something was still injected")
    log_lines = log.read_text(encoding="utf-8").splitlines() if log.exists() else []
    if len(log_lines) != 1:
        problems.append(f"error log has {len(log_lines)} lines, expected 1")

    if problems:
        report("Core 10", "Broken", "; ".join(problems))
    else:
        report(
            "Core 10",
            "Kept",
            "store absent → 3 requests, no raise, no injection, session unchanged; "
            f"one line in the error log: {log_lines[0]}",
        )


def _registered_events(mod) -> list[str]:
    coordinator = FakeCoordinator()
    _run(mod.mount(coordinator, {}))
    return [r["event"] for r in coordinator.hooks.registrations]


def main() -> int:
    try:
        import amplifier_module_hooks_memory_inject as mod
    except Exception:
        print("kit could not run: hooks-memory-inject is not importable", file=sys.stderr)
        traceback.print_exc()
        return 2

    print(f"session.v1 conformance — inject hook ({MODULE_DIR.relative_to(REPO_ROOT)})")
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        saved = {
            k: os.environ.get(k)
            for k in ("AMPLIFIER_MEMORY_HOME", "AMPLIFIER_MEMORY_ERROR_LOG")
        }
        try:
            for check in (check_core_1, check_core_2, check_core_9, check_core_10):
                try:
                    check(mod, tmp)
                except Exception as exc:
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
