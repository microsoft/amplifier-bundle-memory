---
name: memory
description: "Your memory store: overview, list, review, forget, edit, help."
argument-hint: "[list|review|forget|edit|remember|help] [arguments]"
metadata:
  amplifier.completions: completions.json
user-invocable: true
disable-model-invocation: true
---

# /memory

session.v5 §6. `$ARGUMENTS` is empty, or starts with one word that chooses what
happens. Dispatch on that first word; the rest of the line is the argument.

## Dispatch

| `$ARGUMENTS` | Call |
|---|---|
| empty | `memory(operation="overview")` |
| `list` | `memory(operation="list")` |
| `list 2` | `memory(operation="list", page=2)` |
| `review` | `memory(operation="review", action="list")` |
| `review 2` | `memory(operation="review", action="list", page=2)` |
| `review accept s-042` | `memory(operation="review", action="accept", id="s-042")` |
| `review decline s-042` | `memory(operation="review", action="decline", id="s-042")` |
| `review skip s-042` | `memory(operation="review", action="skip", id="s-042")` |
| `forget m-017` | `memory(operation="forget", id="m-017")` |
| `edit m-004 <text>` | `memory(operation="edit", id="m-004", text="<text>", quote="<text>", writer="human")` |
| `remember <text>` | `memory(operation="save", text="<text>", quote="<text>", writer="human")` |
| `help` | the **Help** section below — no tool call |
| anything else | the **Help** section below — no tool call |

For reads and ordinary single-id requests, make the stated call and relay its
result. The defined multi-call exceptions are a frozen multi-id **`review`**
batch and an approved conversational prior-memory consolidation: in the latter,
edit the survivor first and then forget each displayed duplicate in order. Stop
on a refusal and relay every actual result in order. Several stable ids in one
breath are several calls, in the order they were said.

**Relay the tool's result exactly as it stands — it is relayed verbatim and never reworded.**
Two shapes, and which one you use depends on what came back:

**The overview and every receipt go inside a fenced code block**, like this:

    ```
    17 suggestions waiting. /memory review to walk them.
    4 memories. /memory list to see them.
    last 7 days: 6 written, 1 forgotten, 2 cited.
    /memory list · review · forget <id> · edit <id> <text> · help
    ```

The fence is not decoration. Outside one, markdown folds those lines into a
single paragraph and treats `<id>` and `<text>` as tags and drops them.
No text before the fence, none after.

**A `list` page and a `review` page go bare — no fence.** They are already
markdown: bold ids, blockquoted quotes, one blank line between items. A fence
would show the asterisks as asterisks and refuse to wrap, which is the wall
they exist to replace. Paste the page as it stands, with nothing before or
after it.

When one clear request needs multiple independent memory calls, make them one
at a time in the stated order and wait for each result. A later refusal does
not undo an earlier success. Stop after that refusal and relay every earlier
successful receipt followed by the refusal, in order, inside one fence. Never
replace that compound result with a blanket “nothing changed” message.

If the tool refuses, relay its one line as it stands and stop, except for the
one read-only correction in **`review`** below. A refusal is not an
investigation: do not go looking through `MEMORY.md` for something close, and
never act on a different id than the one named. No store yet means
`amplifier-memory init`.

Three refusals are about this session rather than this command, and each one is
final — relay the line and stop, do not retry, do not look for another route:

- `memory is disabled for this instance (<path>: enabled: false).` — the
  instance is switched off (session.v5 §12). Every operation answers this, reads
  included, and nothing is written. The remedy is a human editing `enabled` in
  that `config.yaml`; it is not yours to change.
- `refused: session.v4 §13 — a worker session never …` — this session declared a
  non-human origin, so it may not save, edit or forget. Reading still works: the
  memories still apply, the work is still this human's. Nobody is here to answer
  a suggestion either, so no suggestions line is shown.
- `refused: session.v4 R2 — a sub-agent session never …` — the same rule, one
  step down: a sub-agent inherits the memories and never writes.

## Pages

`list` and `review` come back one page at a time, and the page says which page
it is. `<page>` selects one: `/memory review 2` is `page=2`.

**`next` is this call again with `page + 1`.** Nothing remembers a page for you
— read the page number off the header you just relayed and add one. A page past
the last is refused in one line that names the last page; relay it and stop.

## `edit` and `remember` write the human's own words

`writer="human"` is what makes them the human's words, and the text is its own
quote — that is what the writer requires (session.v5 §5). Split `$ARGUMENTS` at
the first space after the first word: `edit` takes an id then the new text;
`remember` takes the text and nothing else. Do not tidy, expand, or rephrase
what was typed.

An `edit` keeps the id. Every reference to `m-004` — in this session, in `git
log`, in the human's own head — still points at the same memory, refined. A
forget plus a save retires the number and starts a new one, which is how
"update 4" once deleted the wrong line.

## Conversational prior-memory management

After you have relayed a real `list` page in this conversation, a later natural
reply may refer to an entry in that **shown snapshot** by its stable `m-NNN` id,
unambiguous displayed text or description, or an explicit displayed position
such as `#2` or `the first memory`. This is the narrow conversational exception:
literal `/memory edit` and `/memory forget`, direct tool calls, and shell commands
still take stable ids only. A bare number in one of those forms means an id, never
a current position.

Freeze every stated action and its resolved `m-NNN` target from the displayed
snapshot before any mutation. This works for an older or nonconsecutive id and
for an entry on a later page that was actually shown. If the target, action, or
map is ambiguous, conflicting, or lost, ask one short clarification question and
make no call. Never guess. If a mapped id is missing or stale, relay that refusal
and stop: do not list again, rebind a position, retarget a remaining action, or
look for a close match.

A pointer ending `→ topics/<slug>.md` is read-only: never pass its id to `edit`
or `forget`. When the human selects a displayed pointer, use the existing
`read_file` capability only for that exact `topics/<slug>.md` path beneath the
instance whose `MEMORY.md` path the displayed list named. Relay the real topic
body bare before resolving a later reference to one of its actual `m-NNN` lines.
Do not enumerate topics, construct a path from a guess, write files, install or
grant a capability. If `read_file` is unavailable or refuses, or the displayed
instance/path cannot be established, state that limitation and stop.

For one clear reword, call the existing operation once:
`memory(operation="edit", id=<frozen m-NNN>, text=<derived replacement>,
quote=<the human's exact correction>, writer="assistant")`. The actual human
instruction is the quote; derived wording is assistant-authored. For one clear
removal, call `memory(operation="forget", id=<frozen m-NNN>)`. Neither requires
another confirmation. Relay the actual receipt exactly in a fence.

**Consolidation is a preview, not a new command or bulk operation.** Before any
write, show the exact survivor `m-NNN`, assistant-derived replacement, actual
human correction quote, and ordered duplicate `m-NNN` ids. Make no call for that
preview. Only an immediately later `yes` or `do it` approves that exact displayed
map; no approval or a decline writes nothing. On approval, edit the survivor
first using the human quote and `writer="assistant"`, then forget the named
duplicates one at a time in their shown order. If the edit fails, do not forget
anything. If a later forget fails, stop immediately. Relay each actual earlier
receipt and the later refusal unchanged in one fence, in call order. Never call
the result atomic or say nothing changed after an earlier success.

This is different from correcting a **pending suggestion** (`s-NNN`): follow
the corrected-acceptance flow in **`review`**. Never accept original text and
then edit it, and never turn a pending suggestion into an unrelated new memory.

## `review`

suggestions.v2 §6. The daily job proposes lines it heard and never writes one
itself; this is where they are answered, one id at a time. Ids here are `s-NNN`.

Accept writes the line through the same writer every save uses. Decline is final
and reversible only by hand, so never decline a suggestion whose target is
unclear — when an answer such as "no" cannot clearly resolve from the displayed
page, ask which. Skip changes nothing and leaves the item waiting. Nothing about
a suggestion is ever in your context: you learn what is waiting by calling
`review`, the same way the human does.

**One read-only correction.** Exactly once, correct a first call to
`accept`, `decline`, or `skip` with no id to
`memory(operation="review", action="list", page=<requested page>)` only when
the original request was `review` or `review <page>` and the first result is
that action's `refused: review <action> needs the suggestion id, e.g. s-042`
argument refusal. Preserve the requested page (use page 1 when none was
requested). If the correction succeeds, relay only its bare rendered page; do
not present the first argument error. A second failure is terminal.

Never use this correction for a user-requested `accept`, `decline`, or `skip`
whose target cannot clearly resolve from the displayed page; ask which id
instead. Disabled instances, unavailable review, worker or sub-agent write
refusals, unknown ids, privacy or writer refusals, and library failures are
final: relay them and stop. Never invent an id, turn a requested write into a
read, or inspect files to route around a refusal.

**Conversational addressing from a displayed page.** After you have relayed a
real `review` page in this conversation, a later natural-language reply may
refer to that displayed page by `#1`, `first one`, or unambiguous text from one
item. Resolve each clear reference to that page's stable `s-NNN` id before
making a call. This is only for the conversational reply to the displayed page:
tool inputs, shell commands, and `/memory review accept|decline|skip` still
require stable ids.

For a batch such as "accept #1, decline #2", resolve the **complete** requested
batch first and freeze its action-to-id map. Then call the stable ids one at a
time in the human's stated order; do not list again between calls, and relay all
receipts together inside one fence. No confirmation is needed when every action
and target is clear. If you explicitly stated the complete map in your
immediately preceding reply, "yes" approves that exact map without retyping
ids.

If any reference or map is unknown, lost, ambiguous, or conflicting, ask one
concise clarification question and make no write. If a mapped stable id is
missing or stale, stop calling tools: do not list again, rebind a position,
substitute another item, or shift a remaining action. If an earlier action in
this same batch succeeded, relay each earlier receipt followed by this refusal
together in one fence, in call order. Otherwise relay the refusal as it stands.
Do not infer an unnamed decline or accept every displayed item.

**Corrected acceptance of one pending suggestion.** For a clear `accept it but
...` against one stable id from that displayed, frozen page, derive the corrected
text but preserve the human's exact correction as `quote`. Call
`memory(operation="review", action="accept", id=<s-NNN>, text=<derived corrected
text>, quote=<actual correction>)`. Do not pass a writer: this path records the
derived wording as assistant-authored. Both `text` and `quote` are required; a
missing one is a refusal, never an ordinary accept.

For a clear request to revise without accepting, display the derived corrected
text, the actual correction quote, and the exact `s-NNN` proposal-to-id map with
no tool call and no receipt. Only an immediately later `yes` or `do it` approves
that exact displayed map; then make the corrected-accept call above. A decline
of that proposal leaves its source pending; an explicit `review decline s-NNN`
is the ordinary decline. A missing, ambiguous, or stale map, no approval, or any
refusal leaves the source pending. Do not re-list, rebind, or retarget it.

**Several stable ids in one breath are several calls.** "accept s-002 and
s-003, skip s-004" is three calls, in that order, one id each — the tool takes
one id and this is not a limitation to work around. Make them all, then relay
their results together, inside one fence, in the order they were made — include
successful receipts and a later refusal if one occurs. Never say that nothing
changed after an earlier call succeeded, and never hide that success behind the
last refusal.

A page numbers its items so they can be read. A direct tool, shell, or slash
command `accept 2` is refused, and the refusal names the ids that page holds.

## Ids

Outside conversational review and conversational prior-memory addressing from an
actual displayed page, ids are the only names. A bare number N means m-00N,
never a position in a list. Never guess an id. A forgotten id is never reused.

## Cite at use

When a memory changes what you would otherwise have done, write `per m-NNN` inline and call `cite` with that id.

## Do not

- Do not summarise, group, re-order, re-bullet, or editorialise a result.
- Do not drop the ids.
- Do not put more than one stable id in a tool call. A clear conversational
  review batch may use one tool call per resolved id, in the human's stated
  order.
- Do not read or print a topic body except after the human selects its displayed
  pointer, using the exact bounded `read_file` procedure above.
- Do not suggest memories to forget unless asked.

## Help

Print this section as your whole answer — the table, then the paragraph. Make no
tool call.

| Command | What it does |
|---|---|
| `/remember <text>` | saves exactly what you typed |
| `/memory` | the overview: what is waiting, what is stored, the last 7 days |
| `/memory list [<page>]` | every memory, with its id |
| `/memory review [<page> \| accept\|decline\|skip <id>]` | walk what the daily job proposed |
| `/memory forget <id>` | removes one memory; it stays in git |
| `/memory edit <id> <text>` | replaces one memory's text, keeping its id |
| `/memory remember <text>` | the same as `/remember <text>` |
| `/memory help` | this table |

Memory is one file, `MEMORY.md`, put in front of the model on every request of
every session on this device — so a preference stated once holds in the next
session without being said again. It lives in a memory *instance*, a directory
of its own; `/memory list` ends by naming this session's, and an app can point a
session at a different one, in which case the load line at the start of the
session names it too. The assistant also saves on
its own, in the same turn, when you state something meant to hold beyond the
current task ("never X", "always Y", "stop doing Z"), always with your own words
as the quote; it does not save task instructions or facts it can work out for
itself. The store is a git repository you can `cat`, `grep` and edit by hand:
every save, edit and forget is one commit, and `amplifier-memory why m-017`
replays one memory's history. A ruleset — anything longer than one line — goes
to `topics/<slug>.md` with a single pointer line in `MEMORY.md`, so it is read
when it is relevant instead of loaded every time.
