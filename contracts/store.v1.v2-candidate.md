# Proposal: store.v1 → v2 (CANDIDATE)

**Changes:** `contracts/store.v1.md` (FROZEN 2026-09-06). Written 2026-09-06 by the manager
session. The original stays the law until the steward's word lands below.

## Target lines and exact changes

**§1 "Every mutation is one commit."** Add one sentence:
> Appends to `usage.jsonl` are the one exception: they are written without a commit, so a
> session that only *reads* memory leaves no commit behind. Everything a human would call a
> change — a save, an edit, a forget, a topic write — is still exactly one commit.

**§8 usage.jsonl events** — currently `event: loaded|read`. Change to:
> `event: loaded|read|cited` — `cited` records `{ts, event: cited, target: m-NNN, session_id}`
> each time the assistant names a memory at use (session.v1 §8). `status` derives the citation
> rate from it.

**§6 provenance** — add to the commit-message fields: `action: save|edit|forget|topic` and, for
`edit`, `was: "<previous text>"`. (Both already appear in the writer's commits; this writes down
what is already true so `why` can promise them.)

## Evidence

- One `usage: loaded MEMORY.md` commit per session accrued in the steward's real store: 4 in
  one afternoon, 6 in the Dana store across two sessions and one init. At ten sessions a day
  that is ~3,600 commits a year with no change to any memory — §10 says the store is "bounded
  by construction" and git history is the one surface that is not. Forget commits are also
  indistinguishable from saves in `git log --oneline` (Dana, store state): the subject line is
  the same; only the body carries `action:`.
- Cite-at-use fired zero times in every real session; there is no instrument for it.

## What does NOT change

§2 layout (no new files), §3–§5 caps, §7 declined.md, §9 two writers one path, §10's bounds,
R1, R2. `usage.jsonl` is still truncated to 90 days on each write. Hand edits are still
legitimate without ceremony.

## Steward's word

**ratified** — 2026-09-06 20:55, in conversation: "lgtm, do it". Locked as the corresponding `*.v2.md`.
