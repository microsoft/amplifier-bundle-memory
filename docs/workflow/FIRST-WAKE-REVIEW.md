# First wake — what was found, what is proposed

Written 2026-09-06 by the manager session, before any code exists. This is the
record the steward can hold against what they already know. Nothing here is a
decision; the decisions are the calls at the end.

## The four answers

1. **What is this?** Today the repository is a vision, four draft contracts, a
   README and a rules file — words about a small memory system for Amplifier,
   and no code at all.
2. **Who is it for?** One person on one device: the steward, in every Amplifier
   session they run here. The systems that would be surprised by a silent
   change are the Amplifier CLI (which loads the bundle into every session),
   git (which is the store's audit log), and — in Phase 2 only — the
   context-intelligence session capture the daily job reads.
3. **What does it promise today?** Nothing is enforced yet, but the README
   already reads like a promise: an install in four commands, three slash
   commands (`/remember`, `/forget`, `/memory`), a `MEMORY.md` under
   `~/.amplifier/memory` that every session loads, and one success measure —
   five kept memories after a week of real use.
4. **What is in flight?** Nothing in this repository. Outside it, one fact
   matters: the predecessor, `amplifier-engram`, is still wired into the
   steward's sessions through the `anchors-amp-dev` bundle (its recall tools
   are live in this very session) while its store on this device does not
   exist. Installing this bundle beside it means two memory blocks per request
   until one is removed.

## Contract review — where the drafts meet the substrate

Read against the actual kernel, CLI and foundation checkouts in this workspace
(evidence in `PINS.md` → *Substrate facts*). Each item is either an **edit**
the steward can accept in a word, or a **note** that changes no text.

- **E1 (store.v1 §1 ↔ cli.v1 §8).** store.v1 §1 says the store is "initialized
  by `amplifier-memory install`"; cli.v1 §1/§8 and the README say `init`. One
  name. Recommend `init`.
- **E2 (cli.v1 §1 ↔ suggestions.v1 §1).** The verb list ends "Nothing else",
  but suggestions.v1 §1 has the timer run `amplifier-memory suggest`. Add
  `suggest` to cli.v1 §1 as the Phase 2 verb (in Phase 1 it reports "Phase 2
  not installed" and exits 0).
- **E3 (session.v1 §1).** The clause names a mechanism — "at session start and
  again after every context compaction" — that the kernel does not offer: hook
  results on `session:start` are discarded, and `context:post_compact` is
  declared but never emitted. The proven pattern (used by two shipped hooks)
  is ephemeral injection on every `provider:request`, which is present at
  start and after any compaction by construction. Recommend rewording to the
  observable: *"The block is present in every model request of the session,
  including the first and every one after a compaction."* Cache-stability
  (§1) and announce-once (§2) stay as written.
- **E4 (session.v1 §6).** The CLI's slash-command registry is closed to
  bundles; the only extension point is a user-invocable skill, so `/remember
  <text>` reaches the model as a skill body with the text in `$ARGUMENTS`, and
  the model calls the memory tool. It is still the highest-precision path
  *only if* the writer applies the same human-turn check (the quote is the
  text; it must appear in a human turn). Recommend adding one sentence to §6:
  *"The commands are user-invocable skills; the writer applies §5's human-turn
  check to them like any other save."* Open verification for a lane: confirm
  the CLI records the `/remember …` line as a user turn.
- **N1 (session.v1 §5).** After a compaction, `get_messages()` may no longer
  hold the original human turn verbatim. The writer falls back to
  `transcript.jsonl` for the quote check. Implementation note; no edit.
- **N2 (session.v1 §2, §3, §8).** "Loaded N memories", "Saved memory …", and
  "per m-017" are model behaviours the hook can only instruct. They are
  checkable only in a real session, which is how the Conformance section
  already frames them. No edit; the real-host smoke is the check.
- **N3 (session.v1 R2).** Sub-agent refusal is implementable exactly:
  `coordinator.parent_id is not None` → the writer refuses. No edit.
- **N4 (VISION / install).** AGENTS.md rule 4 makes every module source a
  self-referential GitHub URL, so the bundle cannot be installed through
  `amplifier bundle add … --app` until `github.com/bkrabach/amplifier-memory`
  exists. That repository does not exist today. Creating it is the steward's
  call (see the calls below).
- **N5 (suggestions.v1).** Locking it now costs a proposal for every change
  Phase 1's evidence will suggest, and by its own R1 nothing derives from it
  until Phase 1's gate is met. Recommend leaving it `(DRAFT)` — held loosely
  — and ratifying the other four.

## The solution — contracts mapped to Amplifier parts

One repository, `amplifier-memory`, published as both an app bundle and a `uv
tool`. Phase 1 only; Phase 2 waits for its gate.

```
src/amplifier_memory/
  store.py        the deterministic writer: id assignment, 200/150/50 caps,
                  duplicate refusal, git commit with the store.v1 §6 message,
                  usage.jsonl append + 90-day truncation, `init`.
                  The ONE writer both the tool and the CLI call.
  cli.py          amplifier-memory: init · status · why · review · doctor ·
                  service · update · (suggest: "Phase 2 not installed")
modules/hooks-memory-inject/
                  provider:request, ephemeral, role=system:
                  <system-reminder source="amplifier-memory"> framing sentence
                  + MEMORY.md verbatim + the announce-once instruction.
                  Byte-identical for identical MEMORY.md. Logs `loaded` once
                  per session. Fails open (session.v1 §10).
modules/tool-memory/
                  tool `memory`: save(text, quote, writer) · forget(id) · list().
                  save: refuse if parent_id set (R2); quote must appear in a
                  role=user message (get_messages(), fallback transcript.jsonl);
                  then store.py. Every refusal returns a one-line reason.
skills/remember/  skills/forget/  skills/memory/
                  user-invocable, disable-model-invocation; body: call the
                  memory tool with $ARGUMENTS and announce in one line.
behaviors/memory-session.yaml   hook + tool + skills source, self-referential URLs
bundle.md                       root; default behavior = memory-session
conformance/<contract>/run.py   the check per contract → ledger verdicts
tests/                          in-process (temp store); tests/smoke/ real host
```

Why this shape: the store writer is the single seam (store.v1 *Purpose*), so it
is one module with one API and everything else is a thin caller. The hook has
no write path; the tool has no file-format knowledge; the CLI reads git and
files. That is the smallest set of parts that keeps every clause checkable.

## Proposed waves (after the word)

Width is a collision decision: lanes below touch disjoint files.

- **Wave 1 (2 lanes).** A: `src/amplifier_memory/store.py` + its tests +
  `conformance/store/` (store.v1 §1–§10). B: `modules/hooks-memory-inject/` +
  `conformance/session/inject` (session.v1 §1, §2, §9, §10) — reads files only,
  no dependency on A.
- **Wave 2 (2 lanes).** C: `modules/tool-memory/` + `skills/` + `behaviors/` +
  `bundle.md` (session.v1 §3–§8, R2) against A's landed API. D:
  `src/amplifier_memory/cli.py` + tests (cli.v1 §1–§5, §8; §6–§7 report
  "Phase 1 has no service") against A.
- **Wave 3 (1 lane).** E: install on this device per README steps 1–4, `doctor`
  update-check trio, `update` verb, and `tests/smoke/real_session.sh` — one
  session saves, one loads, on this host. This is the merge gate AGENTS.md
  names; nothing is called done before it runs.
- Then the **7-day gate**: the steward uses it; `amplifier-memory status`
  decides whether Phase 2 begins.

Rough size: each wave is one to two hours of lane time; Phase 1 installable on
this device inside a day of wall clock, then a week of real use.
