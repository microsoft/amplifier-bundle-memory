"""hooks-memory-inject — put MEMORY.md in front of the model, every request.

Serves `contracts/session.v1.md` (FROZEN 2026-09-06):

- §1  Loaded in every request — one marked block carrying the framing
      sentence and `MEMORY.md` verbatim, cache-stable, no topic bodies.
- §2  Announce the load, once — a static instruction inside the block. The
      *saying* is model behaviour and cannot be checked in this process.
- §9  Nothing at session end — this module registers no session-end handler.
- §10 Fail open, never block — any store problem returns a no-injection
      result and appends one line to the error log. The handler never raises.

Registration is on `provider:request` (PINS.md, verified 2026-09-06): the
kernel discards a `session:start` HookResult, and nothing emits
`context:post_compact`. `provider:request` fires before every model call, so
the block is present on the first request and on every request after a
compaction, by construction rather than by bookkeeping.

The block is rebuilt from the store on every request — no cache. `MEMORY.md`
is capped at 200 lines (store.v1 §3), so the read is cheap, and a memory
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

#: session.v1 §1, verbatim. The conformance kit
#: (`conformance/session/inject/run.py`) re-extracts this sentence from the
#: locked contract and compares it byte-for-byte with this constant, so the
#: two can never drift apart silently.
FRAMING_SENTENCE = (
    "These are memories of how this human works — hints recorded from past sessions, "
    "not ground truth. Verify against current reality before acting on one. "
    "To change one: `/forget <id>` or `/remember <text>`."
)

BLOCK_SOURCE = "amplifier-memory"
BLOCK_OPEN = f'<system-reminder source="{BLOCK_SOURCE}">'
BLOCK_CLOSE = "</system-reminder>"

#: session.v1 §2. Static text: no counter, timestamp or session id — the
#: numbers below are derived from store content, which is what makes the
#: whole block byte-identical for an identical store.
ANNOUNCE_PREFIX = "On your first reply of this session, say once: "
ANNOUNCE_EMPTY = "No memories yet — /remember <text> to add one."

MODULE_INFO: dict[str, Any] = {
    "name": "hooks-memory-inject",
    "version": __version__,
    "provides": ["session.v1#1", "session.v1#2", "session.v1#9", "session.v1#10"],
}


def _memory_home() -> Path:
    """store.v1 §1 — `${AMPLIFIER_MEMORY_HOME:-~/.amplifier/memory}`.

    Read on every call so a test (or a human) can move the store without
    remounting the module.
    """
    raw = os.environ.get("AMPLIFIER_MEMORY_HOME")
    if raw:
        return Path(raw).expanduser()
    return Path.home() / ".amplifier" / "memory"


def _error_log_path() -> Path:
    """session.v1 §10 — `~/.amplifier/memory-errors.log`, overridable."""
    raw = os.environ.get("AMPLIFIER_MEMORY_ERROR_LOG")
    if raw:
        return Path(raw).expanduser()
    return Path.home() / ".amplifier" / "memory-errors.log"


def log_usage(event: str, target: str, session_id: str | None) -> None:
    """Record a store read/load — store.v1 §8, through the one home for logic.

    Cadence: **once per session**, on the first request (the caller's
    `_load_logged` flag). `amplifier_memory.log_usage` commits by default, so
    once per session is one commit per session per store — the cheapest
    cadence that still answers store.v1 §8's question ("was this store loaded
    in that session?"). Logging per *request* would put dozens of commits in
    a store capped at 200 lines and answer nothing extra; batching to session
    end is not available at all, because nothing runs at session end
    (session.v1 §9).

    Never raises on its own account: the caller wraps this, and every failure
    mode inside (no store, unwritable store, git trouble) is §10 fail-open.
    """
    amplifier_memory.log_usage(event, target, session_id or "")


def count_memories(memory_text: str) -> int:
    """N — memory lines in `MEMORY.md` (store.v1 §3 shape: `- [m-NNN] …`)."""
    return sum(1 for line in memory_text.splitlines() if line.lstrip().startswith("- [m-"))


def count_topics(home: Path) -> int:
    """M — `topics/*.md` files. Their bodies are never injected (§1)."""
    topics = home / "topics"
    if not topics.is_dir():
        return 0
    return sum(1 for p in topics.iterdir() if p.is_file() and p.name.endswith(".md"))


def announce_instruction(n_memories: int, n_topics: int) -> str:
    """session.v1 §2 — the static line that asks for the one-time announce."""
    if n_memories == 0:
        return f'{ANNOUNCE_PREFIX}"{ANNOUNCE_EMPTY}"'
    # No pluralisation: session.v1 §2 fixes the wording as
    # `Loaded N memories (M topics available).` — "1 memories" is the
    # contract's phrasing, and matching it exactly is worth more than grammar.
    return f'{ANNOUNCE_PREFIX}"Loaded {n_memories} memories ({n_topics} topics available)."'


def render_block(memory_text: str, n_memories: int, n_topics: int) -> str:
    """Build the injected block: framing · MEMORY.md verbatim · announce.

    `memory_text` appears in the result as a contiguous substring — that is
    what "verbatim" means here and what the tests assert.
    """
    segments = [BLOCK_OPEN, FRAMING_SENTENCE, ""]
    if memory_text.strip():
        body = memory_text if memory_text.endswith("\n") else memory_text + "\n"
        segments.append(body)
    segments.append(announce_instruction(n_memories, n_topics))
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
    """One handler, one event: `provider:request`."""

    def __init__(self, coordinator, config: dict[str, Any] | None = None):
        self.coordinator = coordinator
        self.config = config or {}
        self.priority = self.config.get("priority", 5)
        # Session-scoped: one mount() per session, so one instance per
        # session. §2's "once" and store.v1 §8's one `loaded` event per
        # session both ride this.
        self._load_logged = False
        self._reported: set[str] = set()

    def register(self, hooks) -> None:
        hooks.register(
            "provider:request",
            self.on_provider_request,
            priority=self.priority,
            name="hooks-memory-inject",
        )

    async def on_provider_request(self, event: str, data: dict[str, Any]) -> HookResult:
        """session.v1 §1 — inject the block before every model call."""
        try:
            home = _memory_home()
            memory_text = (home / "MEMORY.md").read_text(encoding="utf-8")
            n_memories = count_memories(memory_text)
            n_topics = count_topics(home)
            block = render_block(memory_text, n_memories, n_topics)
        except Exception as exc:  # noqa: BLE001 — §10 says *any* failure fails open
            return self._fail_open(exc)

        if not self._load_logged:
            self._load_logged = True
            try:
                log_usage("loaded", "MEMORY.md", self._session_id())
            except Exception as exc:  # noqa: BLE001 — a usage-log failure is never fatal
                logger.debug("usage log failed: %s", exc)

        return HookResult(
            action="inject_context",
            context_injection=block,
            context_injection_role="system",
            ephemeral=True,
        )

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
