"""hooks-memory-inject — put MEMORY.md in front of the model, and tell the human.

Serves `contracts/session.v2.md` (FROZEN 2026-09-06):

- §1  Loaded in every request — one marked block carrying the framing
      sentence and `MEMORY.md` verbatim, cache-stable, no topic bodies, and
      **no announce instruction**: the block is a pure function of the store.
- §2  Announce the load, once, in code — the hook renders one line to the
      human through `HookResult.user_message` on the session's first
      `provider:request` and on the first request after a compaction. It is
      not an instruction to the model, so a reply constraint on the human's
      turn cannot suppress it.
- §9  Nothing at session end — this module registers no session-end handler.
- §10 Fail open, never block — any store problem returns a no-injection
      result and appends one line to the error log. The handler never raises.

Registration (verified 2026-09-06 against the installed runtime):

- `provider:request` — the kernel discards a `session:start` HookResult, so
  injection happens here; it fires before every model call, which makes "the
  first request and every one after a compaction" (§1) true by construction.
  It is also on the whitelist of events whose `user_message` is displayed:
  `amplifier_module_loop_streaming` calls `coordinator.process_hook_result`
  at :2996-3005 (turn start) and :3204-3212 (in-loop), which reaches
  `amplifier_app_cli/ui/display.py:98-128`. That is the §2 channel.
- `context:compaction` — emitted by the shipped context manager at
  `amplifier_module_context_simple/__init__.py:1753-1755`
  (`await self._hooks.emit("context:compaction", stats)`, hooks wired at
  :118). This is the only public compaction signal in this build:
  `context:post_compact` is declared and never emitted (PINS.md), and
  context-simple's compaction is *ephemeral*, so the raw message list a hook
  can read never shrinks. The handler only sets a flag; the line itself is
  rendered on the next `provider:request`, which is where a `user_message`
  is displayed.

The block is rebuilt from the store on every request — no cache. `MEMORY.md`
is capped at 200 lines (store.v2 §3), so the read is cheap, and a memory
saved mid-session is visible on the next request without a cache-invalidation
mechanism existing at all.
"""

# Amplifier module metadata
__amplifier_module_type__ = "hook"

import logging
import os
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import amplifier_memory
from amplifier_core import HookResult

logger = logging.getLogger(__name__)

__version__ = "0.1.0"

#: session.v2 §1, verbatim. The conformance kit
#: (`conformance/session/inject/run.py`) re-extracts this sentence from the
#: locked contract and compares it byte-for-byte with this constant, so the
#: two can never drift apart silently.
FRAMING_SENTENCE = (
    "These are memories of how this human works — hints recorded from past sessions, "
    "not ground truth. Verify against current reality before acting on one. "
    "To change one: `/forget <id>`, `/edit <id> <text>` or `/remember <text>`."
)

BLOCK_SOURCE = "amplifier-memory"
BLOCK_OPEN = f'<system-reminder source="{BLOCK_SOURCE}">'
BLOCK_CLOSE = "</system-reminder>"

#: session.v2 §2, verbatim — the empty-store invitation. No backtick
#: workaround: this string is rendered through Rich *markup*
#: (`amplifier_app_cli/ui/display.py:122`), not `rich.markdown.Markdown`, so
#: `<text>`-style tokens survive. What the markup path *does* eat is a
#: bracketed tag, which is why `announce_line()` is asserted bracket-free and
#: single-line (`RENDER_UNSAFE`) rather than escaped: these strings are
#: code-owned and contain no brackets, so an escape would be a no-op that
#: hides the day one arrives.
ANNOUNCE_EMPTY = (
    'no memories yet. Tell me a standing preference — "never use tabs in YAML" — '
    "and I'll keep it in every session on this device."
)

#: `display.py:127` drops blank lines and `:122` interpolates the message into
#: a Rich markup string unescaped. A line carrying either is not renderable as
#: written; the tests assert every announce variant is clear of both.
RENDER_UNSAFE = ("\n", "[", "]")

MODULE_INFO: dict[str, Any] = {
    "name": "hooks-memory-inject",
    "version": __version__,
    "provides": ["session.v2#1", "session.v2#2", "session.v2#9", "session.v2#10"],
}


def _memory_home() -> Path:
    """store.v2 §1 — `${AMPLIFIER_MEMORY_HOME:-~/.amplifier/memory}`.

    Read on every call so a test (or a human) can move the store without
    remounting the module.
    """
    raw = os.environ.get("AMPLIFIER_MEMORY_HOME")
    if raw:
        return Path(raw).expanduser()
    return Path.home() / ".amplifier" / "memory"


def _error_log_path() -> Path:
    """session.v2 §10 — `~/.amplifier/memory-errors.log`, overridable."""
    raw = os.environ.get("AMPLIFIER_MEMORY_ERROR_LOG")
    if raw:
        return Path(raw).expanduser()
    return Path.home() / ".amplifier" / "memory-errors.log"


def log_usage(event: str, target: str, session_id: str | None) -> None:
    """Record a store read/load — store.v2 §8, through the one home for logic.

    Cadence: **once per session**, on the first request (the caller's
    `_load_logged` flag). `amplifier_memory.log_usage` commits by default, so
    once per session is one commit per session per store — the cheapest
    cadence that still answers store.v2 §8's question ("was this store loaded
    in that session?"). Logging per *request* would put dozens of commits in
    a store capped at 200 lines and answer nothing extra; batching to session
    end is not available at all, because nothing runs at session end
    (session.v2 §9).

    Never raises on its own account: the caller wraps this, and every failure
    mode inside (no store, unwritable store, git trouble) is §10 fail-open.
    """
    amplifier_memory.log_usage(event, target, session_id or "")


def count_memories(memory_text: str) -> int:
    """N — memory lines in `MEMORY.md` (store.v2 §3 shape: `- [m-NNN] …`)."""
    return sum(1 for line in memory_text.splitlines() if line.lstrip().startswith("- [m-"))


def count_topics(home: Path) -> int:
    """M — `topics/*.md` files. Their bodies are never injected (§1)."""
    topics = home / "topics"
    if not topics.is_dir():
        return 0
    return sum(1 for p in topics.iterdir() if p.is_file() and p.name.endswith(".md"))


def announce_line(n_memories: int, n_topics: int, *, compacted: bool = False) -> str | None:
    """session.v2 §2 — the one line the human reads, rendered by this module.

    Returns `None` when there is nothing true to say: an empty store after a
    compaction has no count to carry, and `0 memories still loaded.` is
    exactly the zero-valued count §6 bans from a receipt.

    Pluralisation is real here (v1's `1 memories` is gone). Topics are named
    only when there are some — never `0 topics`.
    """
    if compacted:
        if n_memories == 0:
            return None
        noun = "memory" if n_memories == 1 else "memories"
        return f"context compacted. {n_memories} {noun} still loaded."
    if n_memories == 0:
        return ANNOUNCE_EMPTY
    noun = "memory" if n_memories == 1 else "memories"
    if n_topics:
        topics = "topic" if n_topics == 1 else "topics"
        return f"{n_memories} {noun} loaded, {n_topics} {topics}. /memory to see them."
    if n_memories == 1:
        # §2 fixes the bare singular as exactly `1 memory loaded.` — no pointer.
        return "1 memory loaded."
    return f"{n_memories} {noun} loaded. /memory to see them."


def render_block(memory_text: str) -> str:
    """Build the injected block: framing · MEMORY.md verbatim. Nothing else.

    `memory_text` appears in the result as a contiguous substring — that is
    what "verbatim" means here and what the tests assert.

    session.v2 §1: no counter, no announce instruction. The counts moved into
    the rendered line (§2), which is what makes byte-identity across sessions
    with the same `MEMORY.md` true by construction rather than by care.
    """
    segments = [BLOCK_OPEN, FRAMING_SENTENCE, ""]
    if memory_text.strip():
        body = memory_text if memory_text.endswith("\n") else memory_text + "\n"
        segments.append(body)
    segments.append(BLOCK_CLOSE)
    return "\n".join(segments)


async def mount(coordinator, config: dict[str, Any] | None = None):
    """Register the one handler this module has.

    Returns `MODULE_INFO`. Measured against amplifier-core 1.6.0: the kernel
    treats a truthy `mount()` return as a cleanup function and registers it;
    a non-callable is then skipped silently at session cleanup (other
    cleanups still run, nothing raises). So this return costs nothing and
    still runs nothing at session end (§9) — but see README.md, "What the
    mount() return actually does".
    """
    hook = MemoryInjectHook(coordinator, config or {})
    hook.register(coordinator.hooks)
    logger.info("Mounted hooks-memory-inject")
    return MODULE_INFO


class MemoryInjectHook:
    """Two handlers: `provider:request` (§1 + §2) and `context:compaction` (§2)."""

    def __init__(self, coordinator, config: dict[str, Any] | None = None):
        self.coordinator = coordinator
        self.config = config or {}
        self.priority = self.config.get("priority", 5)
        # Session-scoped: one mount() per session, so one instance per
        # session. §2's "once" and store.v2 §8's one `loaded` event per
        # session both ride these.
        self._load_logged = False
        self._announced = False
        self._compaction_pending = False
        self._reported: set[str] = set()

    def register(self, hooks) -> None:
        hooks.register(
            "provider:request",
            self.on_provider_request,
            priority=self.priority,
            name="hooks-memory-inject",
        )
        # §2's "and on the first after a compaction". This handler renders
        # nothing itself — a `user_message` is only displayed on the events
        # loop-streaming passes through `process_hook_result`, and this is not
        # one of them. It arms the flag; the next `provider:request` renders.
        hooks.register(
            "context:compaction",
            self.on_context_compaction,
            priority=self.priority,
            name="hooks-memory-inject-compaction",
        )

    async def on_context_compaction(self, event: str, data: dict[str, Any]) -> None:
        """Arm §2's post-compaction line. Never raises, never injects."""
        self._compaction_pending = True
        return None

    async def on_provider_request(self, event: str, data: dict[str, Any]) -> HookResult:
        """session.v2 §1 — inject the block; §2 — render the line, once."""
        try:
            home = _memory_home()
            # AGENTS.md rule 11: the library owns the read, not this wrapper. It is
            # tolerant, so one hand-typed byte that is not UTF-8 (store.v2 Core 9
            # invites hand edits) arrives as U+FFFD in the block instead of raising
            # `UnicodeDecodeError` on every provider request. A store that is not
            # there still raises, and §10 below fails open on it.
            memory_text = amplifier_memory.read_memory_text(home)
            n_memories = count_memories(memory_text)
            n_topics = count_topics(home)
            block = render_block(memory_text)
        except Exception as exc:  # noqa: BLE001 — §10 says *any* failure fails open
            return self._fail_open(exc)

        if not self._load_logged:
            self._load_logged = True
            try:
                log_usage("loaded", "MEMORY.md", self._session_id())
            except Exception as exc:  # noqa: BLE001 — a usage-log failure is never fatal
                logger.debug("usage log failed: %s", exc)

        message = self._take_announce(n_memories, n_topics)

        return HookResult(
            action="inject_context",
            context_injection=block,
            context_injection_role="system",
            ephemeral=True,
            user_message=message,
            # `display.py:100-105` maps the level to the colour of the
            # `[hooks-memory-inject]` label only; "info" is the plain
            # informational notice (cyan), "warning" is reserved for §10.
            user_message_level="info",
        )

    def _take_announce(self, n_memories: int, n_topics: int) -> str | None:
        """§2 — the load line on the first request, then only after a compaction.

        Consuming state: whatever this returns is returned exactly once. A
        session with no compaction therefore renders exactly one line, no
        matter how many provider requests a turn makes.
        """
        if not self._announced:
            self._announced = True
            self._compaction_pending = False
            return announce_line(n_memories, n_topics)
        if self._compaction_pending:
            self._compaction_pending = False
            return announce_line(n_memories, n_topics, compacted=True)
        return None

    # -- §10 ---------------------------------------------------------------

    def _fail_open(self, exc: Exception) -> HookResult:
        """Proceed unchanged: no injection, one transcript line, one log line.

        Deduplicated per distinct reason per session so a store that is
        missing for a whole session costs one line, not one per request.
        """
        reason = f"{type(exc).__name__}: {exc}"
        first_time = reason not in self._reported
        if first_time:
            self._reported.add(reason)
            self._append_error_log(reason)
        return HookResult(
            action="continue",
            user_message=(
                f"amplifier-memory: memories not loaded ({reason}); session continues."
                if first_time
                else None
            ),
            user_message_level="warning",
        )

    def _append_error_log(self, reason: str) -> None:
        try:
            path = _error_log_path()
            path.parent.mkdir(parents=True, exist_ok=True)
            stamp = datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
            line = (
                f"{stamp} hooks-memory-inject session={self._session_id()} "
                f"store={_memory_home()} {reason}\n"
            )
            with path.open("a", encoding="utf-8") as fh:
                fh.write(line)
        except Exception as exc:  # noqa: BLE001 — see below
            # Failing to record a failure must not become a failure.
            logger.warning("could not append to memory error log: %s", exc)

    def _session_id(self) -> str | None:
        try:
            return self.coordinator.session_id
        except Exception:  # noqa: BLE001 — a missing session id must never break §1
            return None
