"""amplifier_memory — the one home for memory behaviour (AGENTS.md rule 11).

Import this and you have the whole store: `init`, `save`, `edit`, `forget`,
`list_memories`, `log_usage`, `record_citation`, `why`, `store_home`, the reports
`status`, `review`,
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
| `doctor --repair` | `repair_store()` -> `RepairResult.render()` |
| `service` | `service_status(verb)`                          |
| `update`  | `run_update()` -> `UpdateReport.render()`       |
| `suggest` | `suggest_status()`                              |
"""

from .doctor import (
    SERVICE_VERBS,
    STALE_NOTE,
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
    GitFailed,
    MalformedLine,
    MemoryError,
    QuoteNotHuman,
    RepairResult,
    StoreBusy,
    StoreCheck,
    StoreMalformed,
    StoreMissing,
    UnknownId,
    WriteNotLanded,
    edit,
    forget,
    init,
    list_memories,
    log_usage,
    read_memory_text,
    record_citation,
    repair_store,
    save,
    store_home,
    verify_store,
    why,
)
from .update import (
    APP_BUNDLE_URI,
    BUNDLE_ADD_ARGV,
    BUNDLE_REMOVE_ARGV,
    UPGRADE_CLI_ARGV,
    StepResult,
    UpdateReport,
    run_update,
)

__all__ = [  # noqa: RUF022 - contract order (store, then the report surface), not alphabetical
    "init",
    "save",
    "edit",
    "forget",
    "list_memories",
    "read_memory_text",
    "log_usage",
    "record_citation",
    "why",
    "store_home",
    "verify_store",
    "repair_store",
    "StoreCheck",
    "RepairResult",
    "MalformedLine",
    "status",
    "StatusReport",
    "review",
    "format_why",
    "doctor",
    "DoctorReport",
    "DoctorRow",
    "update_check",
    "update_plan",
    "run_update",
    "UpdateReport",
    "StepResult",
    "APP_BUNDLE_URI",
    "UPGRADE_CLI_ARGV",
    "BUNDLE_REMOVE_ARGV",
    "BUNDLE_ADD_ARGV",
    "installed_commit",
    "remote_commit",
    "service_status",
    "SERVICE_VERBS",
    "suggest_status",
    "STALE_NOTE",
    "MemoryError",
    "CapExceeded",
    "DuplicateMemory",
    "UnknownId",
    "QuoteNotHuman",
    "StoreMissing",
    "StoreBusy",
    "WriteNotLanded",
    "StoreMalformed",
    "GitFailed",
]
