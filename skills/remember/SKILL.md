---
name: remember
description: >-
  Write exactly what the human typed into their memory store, as their own words.
  Invoked as `/remember <text>`; the text is the memory and the quote both.
user-invocable: true
disable-model-invocation: true
allowed-tools:
  - memory
---

# /remember

`$ARGUMENTS` is the memory, exactly as the human typed it. Do not rewrite it,
tidy it, expand it, or turn it into a question. session.v1 §6: `/remember
<text>` writes exactly what the human typed.

## Do this

1. Call the `memory` tool once:

   ```
   memory(operation="save", text="$ARGUMENTS", writer="human")
   ```

   `writer="human"` is what makes this the human's own words: the tool passes
   the text as its own quote, which is what the writer requires.

2. Announce the result in **one line**, and nothing else:

   `Saved memory m-017: "<text>" — /forget m-017 to undo.`

   The tool's first output line is already exactly that. Relay it.

3. If the tool refuses, relay its one line as it stands and stop. Common
   refusals: the memory already exists; `MEMORY.md` is at its 200-line cap;
   there is no store yet (`amplifier-memory init`); this is a sub-agent
   session, which never writes.

## Do not

- Do not ask whether to save it. The human already said to.
- Do not save anything other than `$ARGUMENTS`.
- Do not call the tool more than once.
- Do not add commentary after the announce line.

If `$ARGUMENTS` is empty, say in one line:
`Usage: /remember <text> — the text is the memory.`
