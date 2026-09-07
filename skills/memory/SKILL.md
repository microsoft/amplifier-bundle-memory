---
name: memory
description: "Your memory store: overview, list, review, forget, edit, help."
user-invocable: true
disable-model-invocation: true
allowed-tools:
  - memory
---

# /memory

session.v3 §6. `$ARGUMENTS` is empty, or starts with one word that chooses what
happens. Dispatch on that first word; the rest of the line is the argument.

## Dispatch

| `$ARGUMENTS` | Call |
|---|---|
| empty | `memory(operation="overview")` |
| `list` | `memory(operation="list")` |
| `review` | `memory(operation="review")` |
| `review accept s-042` | `memory(operation="review", action="accept", id="s-042")` |
| `review decline s-042` | `memory(operation="review", action="decline", id="s-042")` |
| `review skip s-042` | `memory(operation="review", action="skip", id="s-042")` |
| `forget m-017` | `memory(operation="forget", id="m-017")` |
| `edit m-004 <text>` | `memory(operation="edit", id="m-004", text="<text>", quote="<text>", writer="human")` |
| `remember <text>` | `memory(operation="save", text="<text>", quote="<text>", writer="human")` |
| `help` | the **Help** section below — no tool call |
| anything else | the **Help** section below — no tool call |

One call per invocation, and nothing after it.

**Relay the tool's result exactly as it stands.**

If the tool refuses, relay its one line as it stands and stop. A refusal is not
an investigation: do not go looking through `MEMORY.md` for something close, and
never act on a different id than the one named. No store yet means
`amplifier-memory init`.

## `edit` and `remember` write the human's own words

`writer="human"` is what makes them the human's words, and the text is its own
quote — that is what the writer requires (session.v3 §5). Split `$ARGUMENTS` at
the first space after the first word: `edit` takes an id then the new text;
`remember` takes the text and nothing else. Do not tidy, expand, or rephrase
what was typed.

An `edit` keeps the id. Every reference to `m-004` — in this session, in `git
log`, in the human's own head — still points at the same memory, refined. A
forget plus a save retires the number and starts a new one, which is how
"update 4" once deleted the wrong line.

## `review`

suggestions.v1 §6. The daily job proposes lines it heard and never writes one
itself; this is where they are answered, one id at a time. Ids here are `s-NNN`.

Accept writes the line through the same writer every save uses. Decline is final
and reversible only by hand, so never decline an id that was not named — when
the answer is "no" with no id, ask which. Skip changes nothing and leaves the
item waiting. Nothing about a suggestion is ever in your context: you learn what
is waiting by calling `review`, the same way the human does.

## Ids

Ids are the only names. A bare number N means m-00N, never a position in a list. Never guess an id: if it cannot be resolved, list the current ids and ask.

"Fix the ADHD one" and "drop the third one" are not ids — call
`memory(operation="list")` and ask which. A forgotten id is never reused.

## Cite at use

When a memory changes what you would otherwise have done, write `per m-NNN` inline and call `cite` with that id.

## Do not

- Do not summarise, group, re-order, re-bullet, or editorialise a result.
- Do not drop the ids.
- Do not act on more than one memory per invocation.
- Do not read or print topic file bodies; opening one is a separate,
  deliberate act (session.v3 §7).
- Do not suggest memories to forget unless asked.

## Help

Print this section as your whole answer — the table, then the paragraph. Make no
tool call.

| Command | What it does |
|---|---|
| `/remember <text>` | saves exactly what you typed |
| `/memory` | the overview: what is waiting, what is stored, the last 7 days |
| `/memory list` | every memory, with its id |
| `/memory review [accept\|decline\|skip <id>]` | walk what the daily job proposed |
| `/memory forget <id>` | removes one memory; it stays in git |
| `/memory edit <id> <text>` | replaces one memory's text, keeping its id |
| `/memory remember <text>` | the same as `/remember <text>` |
| `/memory help` | this table |

Memory is one file, `~/.amplifier/memory/MEMORY.md`, put in front of the model
on every request of every session on this device — so a preference stated once
holds in the next session without being said again. The assistant also saves on
its own, in the same turn, when you state something meant to hold beyond the
current task ("never X", "always Y", "stop doing Z"), always with your own words
as the quote; it does not save task instructions or facts it can work out for
itself. The store is a git repository you can `cat`, `grep` and edit by hand:
every save, edit and forget is one commit, and `amplifier-memory why m-017`
replays one memory's history. A ruleset — anything longer than one line — goes
to `topics/<slug>.md` with a single pointer line in `MEMORY.md`, so it is read
when it is relevant instead of loaded every time.
