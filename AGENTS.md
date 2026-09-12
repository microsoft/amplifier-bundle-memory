# amplifier-bundle-memory — repo conventions

Vision-first, contract-driven (Converge). `docs/VISION.md` governs the
contracts; the contracts govern the code. A change that contradicts a
contract lands in the contract first (proposal → owner's word), then in code.

## Non-negotiables (each one is a lesson already paid for)

1. **Simplicity is the requirement, not a style.** Before adding a
   mechanism, name the cost that was actually paid without it. The
   predecessor shipped a resident server, an evidence ladder, tombstones,
   fingerprints, semantic clustering, a pending pool, ceilings, and a 63-row
   ledger — and an empty store. The bar for a new moving part is "a human
   hit this."
2. **The success metric is memories the owner keeps.** Tests, harnesses, and
   ledgers are instruments; `amplifier-memory status` is the truth. A green
   suite over an empty store is a failing project.
3. **Prove it on the owner's real host, with the owner's real sessions,**
   before calling a wave done. Fixture-only proof let five real defects
   ship last time.
4. **Module sources and sibling deps are self-referential git URLs, never
   relative paths or bare names.** `source: git+https://github.com/microsoft/amplifier-bundle-memory@main#subdirectory=modules/<m>`
   in behaviors; `amplifier-memory @ git+https://github.com/microsoft/amplifier-bundle-memory@main`
   in module `pyproject.toml`. Relative sources resolve against the *loading*
   file; bare names hit the registry under `amplifier update`'s
   `--no-sources` refresh.
5. **Every shelled argv is verified against that CLI's `--help` in the same
   change, output shown.** `amplifier run --once` did not exist; it shipped
   anyway.
6. **Nothing runs at session end.** If a design needs session-end work, the
   design is wrong (crashes, camping, month-long sessions).
7. **Only the human's own words become memory.** Every save carries a
   verbatim quote that code verifies against a human turn.
8. **Announce every write and read in the transcript.** Silence is a defect.
9. **Retcon docs as always-true.** No "previously / now". Each concept in one
   place. Historical reasoning goes in changelogs and commit messages.
10. **Assert before you mutate; gate commits on the assert.** An unchained
    heredoc committed a stale ledger twice last time.
11. **All behaviour lives in the library; every surface is a thin adapter.**
    `src/amplifier_memory/` is the one home for logic (store writer, status,
    why, doctor, init, suggest). The CLI is `click` over it; the tool module,
    the inject hook and the Phase 2 timer call it directly. No wrapper
    carries logic, and no wrapper calls another wrapper (the tool never
    shells out to the CLI). See the `amplifier-tool-leverage-patterns`
    skill: L2 lib is the home; L3 tool and L4 CLI are adapters; L1 is not
    built because no consumer asks for it.
12. **The store holds memories; configuration travels with the instance.** store.v3 §2
    fixes the instance's layout: `<instance>/config.yaml` (`enabled`, `llm: judge:` —
    provider/model/bundle, role `fast` shipped) and `<instance>/sessions.jsonl` are
    plumbing, not memory — like `.lock`/`.gitignore`. `memory-config.toml` is retired
    (2026-09-07). A `config.yaml` that cannot be read reports one reason and the job
    inherits the app default rather than skipping the run.
13. **User-bus recovery tests use temporary owned UNIX sockets.** Do not rely on the
    host `/run/user` tree or call a real `systemctl --user`; assert the child
    environment at the subprocess boundary instead. Keep pytest's base directory
    short: deeply nested worktree paths can exceed the UNIX-socket pathname limit.
    Set `GIT_CEILING_DIRECTORIES` to the workspace ancestor, not the test worktree.
14. **A displayed review page is a snapshot, not a live position API.** Resolve a
    complete natural-language batch to its displayed stable ids before mutating;
    after a stale-id refusal, never relist and retarget a position.
15. **A correction's authority and wording are different facts.** Verify the
    actual human instruction as the quote; label derived wording assistant-authored.
    Classify literal input before trimming, and never substitute a generated
    replacement for the human's correction quote.
16. **Correction checks must represent the failure they claim to exclude.** A
    pending-only fixture cannot already activate its unwanted text; a fresh reader
    cannot inherit old history; provenance is checked in the actual commit, not
    inferred from the model's incoming writer label.

## Layout

```
docs/VISION.md        the direction (owner-ratified)
contracts/*.v1.md     store · session · cli · suggestions
ledger/               conformance rows, derived from contracts by the reconciler
modules/              hooks-memory-inject · tool-memory (thin adapters over the lib)
src/amplifier_memory/ THE library: store writer, status, why, doctor, init, suggest
src/amplifier_memory/cli.py   click wrapper; `amplifier-memory` entry point
skills/               remember · memory (the two user-invocable slash commands, session.v3 §6)
behaviors/, bundle.md the composable app bundle
tests/                in-process conformance; one real-session smoke
```

## Gates before a merge

`uv run pytest` · module suites · `uv run ruff check` · the contract's
Conformance section evidenced · **and** a real-host smoke: one session that
saves a memory and one that loads it, on this device.

## Lane acceptance criteria are re-derivable from durable artefacts

A criterion that lives only in a conversation is unverifiable the moment the transcript is
truncated, summarised, or read by someone else (three review cycles were spent on wave 14's
lane 14-B for exactly this). Every acceptance line in a lane brief therefore names a durable
artefact and the command that re-derives it — never "printed in the conversation":

- BEFORE: "Item resolved, read back with work_list, printed."
  AFTER:  "Item resolved; sha256 of `.items[0].resolution` from
  `amplifier-work-tracker list --project <p> --id <id> --json` equals `<hash>`, recorded in DONE.json."
- BEFORE: "print `ls -la` at lane start and lane end and show they match."
  AFTER:  "run the suite; the install-plane gate passes against `LANE_START_EPOCH`" — the
  reference instant is stamped by the MANAGER (in the brief), never taken by the worker.
- A criterion that cannot be re-derived is a defect in the brief: the worker routes it to the
  manager in `residuals` and does not argue it; whether it blocks the merge is the manager's
  call, not the worker's.

Worked example: lane 14-B's `RESOLUTION-78h.txt` + `resolution_artefacts` in its DONE.json.

The same rule for file ownership: a brief whose edit-only list does not contain the file a fix
genuinely needs is a brief defect — the worker stops and routes it in `residuals`, it does not
create a new module or edit an unlisted file to route around the list (lane W did exactly that on
2026-09-07 and reported it as a footnote; the code was fine, the process was not — item vfk).

## Converge — how this repository is run

- **Intent steward:** bkrabach. Their word is the law here. **Manager session:**
  the long-running session that derives, briefs, launches, verifies and
  integrates. **Worker session:** you, probably — one bounded item, your own
  branch, proof on exit.
- **Hard facts first:** read `PINS.md` before your first command.
- **Never edit a locked document** (first heading carries `(FROZEN <date>)`).
  Propose instead: a sibling `<contract>.vN-candidate.md` with the exact change,
  the evidence (a cost paid or a failure caught — preference is not evidence),
  and what does not change. The pre-push hook refuses the push otherwise; the
  refusal is the rule working.
- **Four calls reach the steward:** ratify · irreversible · a check only a
  person or device can perform · priority/stop. Anything else is a defect in
  the brief — say so, do not ask.
- **Finish honestly.** Done means seen working on this device, evidence in a
  file or printed output, never only inside a tool call. Stuck, with the cause,
  is a real answer.
- **Feedback** from the steward lands in `.converge/feedback/`; the manager
  session triages it. Return briefs live in `docs/workflow/OWNER-RETURN-LOG.md`;
  the manager's own verification runs in `docs/workflow/CHECK-RECORD.md`.

## Corrected-acceptance verification

- Failure recovery must restore actual index entries, not merely stage flags:
  staged content may differ from working-tree bytes. Test both independently.
- A success receipt requires the exact committed transition and provenance,
  not just a changed HEAD. Unknown commit outcomes and failed post-commit
  readback never justify rollback, retry, or a "nothing changed" claim.
- A revise-only evaluation records bytes, HEAD, and call boundaries before
  approval; final-state checks alone cannot prove the preview was inert.
- Positive conversation traces are recorded during actual tool execution,
  never assembled after writes. Keep selected-topic reads, body displays and
  later mutations in their recorded turn order; flattening calls loses that
  evidence. Scripted responders test the recorder and operations, not a model's
  natural-language behavior.
