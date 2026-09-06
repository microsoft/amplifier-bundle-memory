# Lane lane-p-phase2-library — Phase 2's library and CLI keep suggestions.v1

Worker session, alone, in your own worktree of `amplifier-bundle-memory` on branch
`lane/amplifier_bundle_memory-b0g`. Work ONLY here; never merge to `main`; commit early, push after
every commit. **Never touch `~/.amplifier/memory`; never run the real `amplifier-memory suggest`,
`service install`, a real model call, or `update` from this lane** — temp stores, a fake base_path,
an injectable `model_call`, an injectable runner. The manager runs the real thing after merge.

Read first: `PINS.md`, `AGENTS.md` (rules 10, 11), **`contracts/suggestions.v1.md` (FROZEN — every
numbered clause is your spec; the §3 prompt text and §4 inbox shape are exact)**, `contracts/cli.v2.md`
§5 §6 §9, `contracts/store.v2.md` §6 §7, `src/amplifier_memory/store.py` (`save` ~:1089 and its writer
handling, `_assert_saved`, the lock), `doctor.py` (rows, `DoctorRow`), `cli.py`, `update.py` (the
injectable-runner pattern to copy), `conformance/cli/run.py` (kit shape to copy for
`conformance/suggestions/run.py`). The recorded-session layout measured on this device is in the
work item.

**Work item:** `amplifier_bundle_memory-b0g` — claim it
(`work_claim(project="amplifier_bundle_memory", item_id="amplifier_bundle_memory-b0g")`), read its
description in full (six numbered parts; the public signatures there are a contract with lane Q,
which is building the hook line and the tool's review surface against them right now — keep them
exactly), resolve with a reason for the steward, read it back with `work_list`, print it.

**File ownership — edit ONLY:** `src/amplifier_memory/{inbox,suggest,service}.py` (new),
`src/amplifier_memory/{doctor,cli,store}.py` (store.py: the writer `suggestion` only),
`src/amplifier_memory/__init__.py` (re-exports only), `tests/test_inbox.py`, `tests/test_suggest.py`,
`tests/test_service.py`, `tests/test_doctor.py`, `tests/test_cli.py`, `conformance/suggestions/**`
(new), `conformance/cli/run.py` (Core 6 probe), `ledger/rows.yaml` rows AMM-027..030, AMM-033..036,
AMM-006, AMM-025 (disposition/notes), `README.md` (a Phase 2 section). Off-limits: `modules/**`,
`skills/**`, `conformance/session/**`, contracts, docs/workflow.

## Outcome

Once a day a timer runs `amplifier-memory suggest`, which reads yesterday's recorded root sessions,
asks the model one exact question per session, verifies every candidate's quote in code against a
human turn, and appends the survivors to `inbox.md` with their verbatim quote and session; declined
texts are never proposed again; every run writes one log line even when it proposed nothing; when
the substrate or the model is missing it records that and exits cleanly. `review` accepts (through
the shared writer, writer `suggestion`), declines (to `declined.md`), or skips; `doctor` shows the
timer, the substrate, and the last run. Nothing is resident.

## Terminal states and the exit

Items end `PASS` / `FAIL-<cause>` / `BLOCKED-<cause>` / `PENDING-HUMAN`. Complete when every item is
terminal or the remainder is conclusively shown impossible with the blocker named. 150 min wall →
`BUDGET`: commit what is sound, write the marker. **Final act: `DONE.json`** (valid JSON — escape
control characters) in the worktree root: `{"lane":"lane-p-phase2-library","session_id":"…",
"verdict":"COMPLETE|BLOCKED|PARTIAL","branch":"lane/amplifier_bundle_memory-b0g","head":"…",
"pushed":true,"items":[…],"residuals":[…],"pending_human":[],"resources":[],"suite":"…"}`.

## Acceptance — every item names a file or a command whose output you print

1. **inbox.py** — the §4 shape byte-exact; `pending`, `append` (skips MEMORY.md/declined.md exact
   matches, merges duplicates), `accept` (through `store.save`, writer `suggestion`, commit body
   carries the quote and `suggestion-session: <id>`; item removed), `decline` (appends
   `- <YYYY-MM-DD> <text>` to declined.md; item removed), `skip`, `expire(days=30)`, `is_declined`.
   Every mutation is one commit through the store's existing lock + verify-after-commit. Tests
   printed: inbox.md before/after, `git log -1 --format=%B`, declined.md.
2. **suggest.py** — `run_suggest(...)` with the exact §3 prompt (assert the string), session
   selection (root UUID ids only; ≥2 user turns in 24h; exclude sessions whose first user turn
   starts with the prompt; ≤30 most recent), one `model_call` per session, JSON reply parsing with
   malformed → counted, §4 verification (quote verbatim in a user turn, whitespace-normalised),
   `inbox.append`, one log line per run (`<ts> sessions=N proposed=N rejected=N dropped_stale=N
   calls=N status=ok|degraded:<reason>`), bounds (`max_calls` exceeded → skip + report), fail open
   (missing base_path / raising model_call / malformed → `status=degraded:…`, exit 0, no inbox
   write). Default `model_call` shells out to `amplifier run --output json "<prompt>"` — document the
   argv and how the assistant text is read; never invoked in tests. Printed against the fixture.
3. **service.py** — `install|uninstall|status`: systemd `--user` `amplifier-memory-suggest.service`
   (Type=oneshot, ExecStart=<abs amplifier-memory> suggest) + `.timer` (OnCalendar=daily,
   Persistent=true); launchd plist branch on macOS; `daemon-reload` then `enable --now`; failed step
   → written files removed; injectable runner; `status` reads installed/enabled/last run. Printed
   with a fake runner including the rollback path.
4. **doctor** — rows `suggest timer` (installed · enabled · last run · last outcome from
   suggest.log), `substrate` (base path exists/readable), `inbox` (size, oldest); degraded when the
   last log line says degraded; still read-only (store byte-identical before/after). Printed.
5. **cli.py** — `suggest` (runs the job, prints the log line), `review` (`--list`, `--accept ID`,
   `--decline ID`, `--skip ID`; interactive a/d/s walk when a TTY), `service install|uninstall|status`
   replacing the Phase-1 stub; imports only `click` and `amplifier_memory` (grep printed).
6. **conformance/suggestions/run.py** — probes for Core 1–4, 7–10 on the fixture described in the
   item (discriminating pair; poisoning arm; declined not re-proposed; 31-day drop; substrate
   missing → degraded; timer units render + roll back). Exit 0, Kept where assertable, honesty form
   for anything a lane cannot check. `conformance/cli/run.py` Core 6 → Kept. Printed.
7. Root `uv run pytest -q` (baseline 173) and `uv run ruff check .` green. Printed.
8. Rows AMM-027..030, 033..036, AMM-006, AMM-025 → CONFORMS naming probes; `git diff --stat --
   ledger/rows.yaml` printed. README Phase 2 section written.
9. Item resolved and read back; a printed reason you know to be false is not evidence.

## Known

- Honesty gate: *"suggestions.v1 §N — Can't check in this lane because …"* in `run.py` and the reason.
- Sub-agent session ids on this device look like `0000000000000000-<hex>_<agent>`; roots are plain UUIDs.
- `store.save`'s writer=human path requires quote == text; writer `suggestion` must accept the
  suggestion's own quote (the human's verbatim words from the source session).
- Show command output inline; never assert a result without it.
