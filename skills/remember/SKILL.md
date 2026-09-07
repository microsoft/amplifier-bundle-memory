---
name: remember
description: "Save what you typed as a memory, in your own words. `/remember <text>`."
user-invocable: true
disable-model-invocation: true
allowed-tools:
  - memory
---

# /remember

session.v4 §6. `$ARGUMENTS` is the memory, exactly as the human typed it. Do not
rewrite it, tidy it, expand it, or turn it into a question.

## Do this

1. Call the `memory` tool once:

   ```
   memory(operation="save", text="$ARGUMENTS", quote="$ARGUMENTS", writer="human")
   ```

   `writer="human"` is what makes this the human's own words: the text is its
   own quote, which is what the writer requires (session.v4 §5).

2. **Relay the tool's result exactly as it stands — relayed verbatim and never reworded —
   inside a fenced code block.** The receipt is three lines and the fence is what
   keeps them three lines: outside one, markdown folds them into a paragraph. Add
   nothing before or after the fence.

3. If the tool refuses, relay its one line as it stands and stop. Common
   refusals: the memory already exists; `MEMORY.md` is full; there is no store
   yet (`amplifier-memory init`); this instance is switched off
   (`memory is disabled for this instance (<path>: enabled: false).`,
   session.v4 §12); this session declared a non-human origin and so never writes
   (session.v4 §13); this is a sub-agent session, which never writes (R2).
   The last three are facts about the session, not about the text — relay the
   line and stop rather than rewording the memory and trying again.

If `$ARGUMENTS` is empty, answer in one line:
`Usage: /remember <text> — the text is the memory.`

## Saving wording you drafted

You **can** write memories the human did not type. When they approve lines you
proposed — "remember these", "yes, save those" — save them with
`writer="assistant"` and `quote` set to their approval phrase, **one per call**,
waiting for each result:

```
memory(operation="save", text="<line 1>", quote="<their approval phrase>", batch_of=2)
memory(operation="save", text="<line 2>", quote="<their approval phrase>", batch_of=2)
```

`batch_of` is how many lines you are saving — you are the only one who knows,
and it is what lets the tool render the set once, on the last call. Relay that
last result exactly as it stands.

Never claim you cannot save something the human has approved. You can.

## A ruleset goes in a topic file

Anything that will not fit on one line — a ruleset, a style guide, a checklist —
goes to `topics/<slug>.md`, one call per line, and leaves **one** pointer line
in `MEMORY.md` (store.v2 §3, §5):

```
memory(operation="save", text="<rule 1>", quote="<their words>",
       topic="yaml-style", topic_purpose="How to write YAML for me.")
memory(operation="save", text="YAML/JSON style conventions → topics/yaml-style.md",
       quote="<their words>")
```

## Ids

Ids are the only names. A bare number N means m-00N, never a position in a list. Never guess an id: if it cannot be resolved, list the current ids and ask.

## Cite at use

When a memory changes what you would otherwise have done, write `per m-NNN` inline and call `cite` with that id.

## Do not

- Do not ask whether to save it. The human already said to.
- Do not save anything other than `$ARGUMENTS` under `/remember`.
- Do not call the tool more than once per line, or in parallel.
- Do not add commentary after the tool's result.
