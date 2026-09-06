---
name: edit
description: >-
  Replace what one memory says, keeping its id. Invoked as `/edit <id> <text>`;
  the text is the new memory and the quote both.
user-invocable: true
disable-model-invocation: true
allowed-tools:
  - memory
---

# /edit

`$ARGUMENTS` is a memory id followed by the new text — `m-004 When I say
"explain", go long with headers.` session.v2 §6: `/edit <id> <text>` replaces
one memory's text and keeps its id.

## Do this

1. Split `$ARGUMENTS` at the first space: the id, then the rest.

2. Call the `memory` tool once:

   ```
   memory(operation="edit", id="<the id>", text="<the rest>", writer="human")
   ```

   `writer="human"` is what makes this the human's own words: the tool passes
   the text as its own quote, which is what the writer requires.

3. Say nothing. The tool's result is the receipt: `edited m-004 — was: "<what
   it said>"` with `now: <what it says>` under it.

   Never restate a memory receipt or listing in your own words; the tool result is what the human reads.

4. If the tool refuses, relay its one line as it stands and stop. An unknown id
   is a one-line error, not an investigation: do not go looking through
   `MEMORY.md` for something close, and do not edit a different memory. The
   refusal already names the current ids.

## Why an edit, not a forget and a save

The id survives. Every reference to `m-004` — in this session, in `git log`, in
the human's own head — still points at the same memory, refined. A forget plus
a save retires the number and starts a new one, which is how "update 4" once
deleted the wrong line.

## Cite at use

When a memory changes what you would otherwise have done, write `per m-NNN` inline and call `cite` with that id. The
call is silent — nothing is printed, and the human has already read the citation
in your own sentence (session.v2 §8).

## Ids

Ids are the only names. A bare number N means m-00N, never a position in a list. Never guess an id: if it cannot be resolved, list the current ids and ask.

"Fix the ADHD one" is not an id. Call `memory(operation="list")`, show the ids,
and ask which.

## Do not

- Do not guess an id. If `$ARGUMENTS` has no id, say in one line:
  `Usage: /edit <id> <text> — e.g. /edit m-004 Cap lists at five. Use /memory to see the ids.`
- Do not edit more than one memory per invocation.
- Do not tidy, expand, or rephrase the text the human typed.
- Do not add commentary after the tool's result.

If `$ARGUMENTS` carries an id and nothing else, say in one line:
`Usage: /edit <id> <text> — the text is the new memory.`
