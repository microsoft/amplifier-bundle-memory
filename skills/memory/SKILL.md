---
name: memory
description: >-
  Print the human's memory store — every memory with its id, and the path to
  edit them by hand. Invoked as `/memory`.
user-invocable: true
disable-model-invocation: true
allowed-tools:
  - memory
---

# /memory

session.v1 §6: `/memory` prints `MEMORY.md` with ids. `$ARGUMENTS` is ignored —
this command takes none.

## Do this

1. Call the `memory` tool once:

   ```
   memory(operation="list")
   ```

2. Say nothing. The tool's result **is** the listing the human reads: the count,
   one `- [m-NNN] <text>` line per memory, and the hand-edit path last.

   Never restate a memory receipt or listing in your own words; the tool result is what the human reads.

   Printing it a second time in your own prose is the defect this line exists to
   prevent: on 2026-09-06 a two-item listing cost 28 lines of screen because
   every result was rendered twice.

3. If the tool refuses, relay its one line as it stands. No store yet means
   `amplifier-memory init`.

## Ids

Ids are the only names. A bare number N means m-00N, never a position in a list. Never guess an id: if it cannot be resolved, list the current ids and ask.

## Do not

- Do not summarise, group, re-order, re-bullet, or editorialise the list.
- Do not drop the ids.
- Do not read or print topic file bodies. They are counted, not opened;
  reading one is a separate, deliberate act (session.v1 §7).
- Do not suggest memories to forget unless asked.
