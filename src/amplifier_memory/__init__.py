"""amplifier_memory — the one home for memory behaviour (AGENTS.md rule 11).

Import this and you have the whole store: `init`, `save`, `forget`,
`list_memories`, `log_usage`, `why`, `store_home`, the reports `status`, `review`,
`doctor` and `update_check`, and the exceptions a refusal raises. It depends on the
standard library alone — no `click`, no `amplifier_*` — so the CLI, the memory tool,
the inject hook and the Phase 2 job are all thin adapters over the same code
(cli.v1 Core 9).

Every `amplifier-memory` verb is one of these functions plus printing:

| verb      | function                                        |
|-----------|-------------------------------------------------|
| `init`    | `init()`                                        |
| `status`  | `status()` -> `StatusReport.render()`           |
| `why`     | `why(id)` -> `format_why()`                     |
| `review`  | `review()`                                      |
| `doctor`  | `doctor()` -> `DoctorReport.render()`           |
| `service` | `service_status(verb)`                          |
| `update`  | `update_plan()` + `doctor()`                    |
| `suggest` | `suggest_status()`                              |
"""

from .doctor import (
    SERVICE_VERBS,
    DoctorReport,
    DoctorRow,
    doctor,
    installed_commit,
    remote_commit,
    service_status,
    suggest_status,
    update_check,
    update_plan,
)
from .status import (
    StatusReport,
    format_why,
    review,
    status,
)
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

__all__ = [  # noqa: RUF022 - contract order (store, then the report surface), not alphabetical
    "init",
    "save",
    "forget",
    "list_memories",
    "log_usage",
    "why",
    "store_home",
    "status",
    "StatusReport",
    "review",
    "format_why",
    "doctor",
    "DoctorReport",
    "DoctorRow",
    "update_check",
    "update_plan",
    "installed_commit",
    "remote_commit",
    "service_status",
    "SERVICE_VERBS",
    "suggest_status",
    "MemoryError",
    "CapExceeded",
    "DuplicateMemory",
    "UnknownId",
    "QuoteNotHuman",
    "StoreMissing",
]
