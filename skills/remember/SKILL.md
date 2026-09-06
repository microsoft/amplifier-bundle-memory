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

2. Say nothing. The tool's result is the announcement, already in the shape
   session.v1 §3 fixes — `Saved memory m-017: "<text>" — /forget m-017 to undo.`
   with `your words, verbatim` under it.

   Never restate a memory receipt or listing in your own words; the tool result is what the human reads.

3. If the tool refuses, relay its one line as it stands and stop. Common
   refusals: the memory already exists; `MEMORY.md` is full; there is no store
   yet (`amplifier-memory init`); this is a sub-agent session, which never
   writes.

## Saving wording you drafted

You **can** write memories the human did not type. When they approve lines you
proposed — "remember these", "yes, save those" — save them with
`writer="assistant"` and `quote` set to their approval phrase, **one per call**,
waiting for each result:

```
memory(operation="save", text="<line 1>", quote="<their approval phrase>")
memory(operation="save", text="<line 2>", quote="<their approval phrase>")
```

The last result carries the whole batch: `Saved N memories — my wording, your
go-ahead: "<quote>". Reword any line and I'll replace it; /forget <id> drops
one.` followed by the lines. Add nothing to it.

Never claim you cannot save something the human has approved. You can.

## A ruleset goes in a topic file

Anything that will not fit on one line — a ruleset, a style guide, a checklist —
goes to `topics/<slug>.md`, one call per line, and leaves **one** pointer line
in `MEMORY.md` (store.v1 §3, §5):

```
memory(operation="save", text="<rule 1>", quote="<their words>",
       topic="yaml-style", topic_purpose="How to write YAML for me.")
memory(operation="save", text="YAML/JSON style conventions → topics/yaml-style.md",
       quote="<their words>")
```

## Ids

Ids are the only names. A bare number N means m-00N, never a position in a list. Never guess an id: if it cannot be resolved, list the current ids and ask.

## Do not

- Do not ask whether to save it. The human already said to.
- Do not save anything other than `$ARGUMENTS` under `/remember`.
- Do not call the tool more than once per line, or in parallel.
- Do not add commentary after the tool's result.

If `$ARGUMENTS` is empty, say in one line:
`Usage: /remember <text> — the text is the memory.`
