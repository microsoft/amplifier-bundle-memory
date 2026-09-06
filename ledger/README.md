# ledger

`rows.yaml` holds one row per Core clause of every locked contract, seeded by the manager
session on 2026-09-06 and re-checked by `converge:reconciler` after every wave lands. Rows
are never hand-edited into agreement with the code; a GAP row carries the work item that
closes it.

Reminder from AGENTS.md §2: the ledger measures contract adherence;
`amplifier-memory status` measures whether the project works. Both must be
green — the second one first.
