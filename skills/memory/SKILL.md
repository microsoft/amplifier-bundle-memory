---
name: memory
description: >-
  Print the human's memory store — every memory with its id, plus the pending
  suggestion count. Invoked as `/memory`.
user-invocable: true
disable-model-invocation: true
allowed-tools:
  - memory
---

# /memory

session.v1 §6: `/memory` prints `MEMORY.md` with ids and the pending-suggestion
count. `$ARGUMENTS` is ignored — this command takes none.

## Do this

1. Call the `memory` tool once:

   ```
   memory(operation="list")
   ```

2. Print the tool's output as it stands: the header line
   (`N memories, M topic files, 0 pending suggestions`) followed by one line
   per memory, each carrying its `[m-NNN]` id. The ids are the point — they
   are what `/forget` takes.

   In Phase 1 the pending-suggestion count is always 0, because nothing
   proposes suggestions yet. Print it anyway; it is part of the command.

3. If the tool refuses, relay its one line as it stands. No store yet means
   `amplifier-memory init`.

## Do not

- Do not summarise, group, re-order, or editorialise the list.
- Do not drop the ids.
- Do not read or print topic file bodies. They are listed by count only;
  reading one is a separate, deliberate act (session.v1 §7).
- Do not suggest memories to forget unless asked.
