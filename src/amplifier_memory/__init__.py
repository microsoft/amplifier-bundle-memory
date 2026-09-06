"""amplifier_memory — the one home for memory behaviour (AGENTS.md rule 11).

Import this and you have the whole store: `init`, `save`, `forget`,
`list_memories`, `log_usage`, `why`, `store_home`, and the exceptions a refusal
raises. It depends on the standard library alone — no `click`, no `amplifier_*`
— so the CLI, the memory tool, the inject hook and the Phase 2 job are all thin
adapters over the same code (cli.v1 Core 9).
"""

from .store import (
    CapExceeded,
    DuplicateMemory,
    MemoryError,
    QuoteNotHuman,
    StoreMissing,
    UnknownId,
    forget,
    init,
    list_memories,
    log_usage,
    save,
    store_home,
    why,
)

__all__ = [  # noqa: RUF022 - contract order (lane brief acceptance 2), not alphabetical
    "init",
    "save",
    "forget",
    "list_memories",
    "log_usage",
    "why",
    "store_home",
    "MemoryError",
    "CapExceeded",
    "DuplicateMemory",
    "UnknownId",
    "QuoteNotHuman",
    "StoreMissing",
]
