---
name: forget
description: >-
  Remove one memory from the human's memory store by id and commit the removal.
  Invoked as `/forget m-017`.
user-invocable: true
disable-model-invocation: true
allowed-tools:
  - memory
---

# /forget

`$ARGUMENTS` is a memory id, like `m-017`. session.v1 §6: `/forget <id>`
removes the line, commits, and announces.

## Do this

1. Call the `memory` tool once:

   ```
   memory(operation="forget", id="$ARGUMENTS")
   ```

2. Say nothing. The tool's result is the announcement: `Forgot m-017.`, the
   text that was removed, and where it still lives (`still in git:
   amplifier-memory why m-017`).

   Never restate a memory receipt or listing in your own words; the tool result is what the human reads.

3. If the tool refuses, relay its one line as it stands and stop. An unknown
   id is a one-line error, not an investigation: do not go looking through
   `MEMORY.md` for something close, and do not forget a different memory. The
   refusal already names the current ids.

## Ids

Ids are the only names. A bare number N means m-00N, never a position in a list. Never guess an id: if it cannot be resolved, list the current ids and ask.

"Drop the third one" is not an id. Call `memory(operation="list")`, show the
ids, and ask which.

## Do not

- Do not guess an id. If `$ARGUMENTS` is not an id, say in one line:
  `Usage: /forget <id> — e.g. /forget m-017. Use /memory to see the ids.`
- Do not forget more than one memory per invocation.
- Do not offer to re-add it.

The id is never reused: forgetting `m-017` does not free that number.
