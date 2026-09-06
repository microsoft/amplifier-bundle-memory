# cli.v2 — `amplifier-memory` (FROZEN 2026-09-06)

**Governs:** the `amplifier-memory` command
**Who builds against it:** humans at a shell; `doctor` consumers; the
install path in README. The tool module, the inject hook and the Phase 2 job
build against the same `amplifier_memory` library the CLI wraps — never
against the CLI.
**Supersedes:** `cli.v1.md` (locked 2026-09-06 14:28; changed by the
ratified proposal `cli.v1.v2-candidate.md`).

## Purpose

The CLI is how a human looks at the store without a session, installs the
bundle's device-side pieces, and asks "why". It is small on purpose: the
store is files, so `cat`, `grep`, and `git log` already do most of the work.
It holds no behaviour of its own: every verb is one call into the
`amplifier_memory` library, which is the reference implementation.

## Core

1. **Verbs.** `init` · `status` · `why <id>` · `review` · `doctor` ·
   `service {install,uninstall,start,stop,restart,status,logs}` · `update`
   (alias `upgrade`) · `suggest` (Phase 2; in Phase 1 it prints "Phase 2 not
   installed" and exits 0). Nothing else. Read verbs work with nothing
   installed but the store.
2. **`status`** prints the numbers VISION §9 cares about, from git and
   `usage.jsonl`: memories in `MEMORY.md`; written / forgotten in the last 7
   and 30 days; **kept** — written ≥ 7 days ago and still present, where an
   `edit` keeps the original write date and a forget + re-save of the same
   intent counts once from the first write; **citation rate** — `cited`
   events over `loaded` events in the last 30 days, printed as a floor;
   topics and how many are stale (unread 90 days); pending suggestions; last
   suggest run. One screen. This is the project's success metric made
   visible.
3. **`why <id>`** prints the git commits mentioning `[<id>]`: the text, the
   verbatim quote, session id, writer, action and date — creation, each edit
   as `was:` → `now:`, and forget if any, with forget entries marked `forgot`
   in their first line so a removal is never mistaken for a creation. It is
   `git log --grep`, formatted.
4. **`review`** is the shell form of `/memory review` (suggestions.v1 §6).
   With an empty inbox it says so and exits 0.
5. **`doctor`** never mutates. Rows: store present and is a git repo · cap
   headroom (`MEMORY.md` N/200, topics N/50) · **`MEMORY.md` well-formed** —
   every line parses as store.v2 §3 and decodes as UTF-8, or FAIL naming the
   line or byte offset and the last commit whose file parsed clean · stale
   topics count · inbox size and oldest · suggest timer
   installed/enabled/last run/last outcome (Phase 2) · substrate present
   (Phase 2 only; INFO when Phase 2 is not installed) · **update check** —
   installed commit vs `git ls-remote` of the pinned ref, WARN with the
   remedy when behind, INFO "not checkable" offline, never RED. Exit code is
   nonzero only on failed checks. **`doctor --repair`** is the one explicit
   exception to "never mutates": it restores `MEMORY.md` from the last commit
   whose file parsed clean, prints the diff and every line it discards before
   committing, and commits `repair: …` visibly. It is the sanctioned repair;
   the model never edits the store by hand.
6. **`service`** manages only the Phase 2 suggest timer (systemd `--user` /
   launchd). `install` renders units, `daemon-reload → enable --now`, and
   rolls back written units if any step fails. Phase 1 has no service; the
   verb reports that plainly.
7. **`update`** upgrades the uv tool and refreshes the registered app bundle,
   restarts the timer if installed, ends by running `doctor`, and prints the
   stale-in-memory note: sessions started before the refresh keep the old
   module code until restarted.
8. **`init`** creates the store.v2 layout at the store location and makes
   the initial commit. Idempotent: a second run reports the store exists and
   changes nothing. It is the README's step 3 and the only setup Phase 1
   needs.
9. **Thin wrapper.** The CLI is a `click` surface over the `amplifier_memory`
   library and adds only argument parsing, output formatting and exit codes.
   Every behaviour a verb exposes exists as a public, importable library
   function first; the tool module, the hook and the Phase 2 job call that
   function, never the CLI. A wrapper that carries logic is a defect.

## Reserved

- **R1 — `status` "kept" definition.** Present ≥ 7 days after write, edits
  keeping the date (pre-registered in
  `docs/workflow/GATE-DEFINITION-2026-09-06.md` before the first reading).
  Revisit if the owner's forget cadence makes 7 days uninformative.

## Explicitly backlogged

- `--json` output — no consumer yet.
- A `remember`/`forget`/`edit` shell verb — the session commands cover it;
  `$EDITOR ~/.amplifier/memory/MEMORY.md` is the shell edit (store.v2 §9);
  add a verb only if the owner reaches for the shell first.

## Conformance

- Verb surface exactly as §1; unknown verb is a one-line error.
- `status` numbers match a fixture store's git history exactly (written,
  forgotten, kept computed from commit dates with edits keeping the date;
  citation rate from `usage.jsonl`).
- `why` returns the commit(s) for an id including `was:`/`now:` for edits and
  a `forgot` marker for removals; unknown id is a one-line error.
- `doctor` is byte-identical before/after on the store (no mutation); the
  well-formed row FAILs on a headless fragment and on a non-UTF-8 byte, naming
  the offset, with no traceback; `doctor --repair` restores and commits
  visibly, printing what it discards first; update check trio: behind → WARN
  with remedy / current → OK / offline → INFO.
- `service install` round-trip leaves no units behind; failing enable step
  removes written units.
- `init` twice is a no-op with a message.
- Every CLI verb's behaviour is reachable by importing `amplifier_memory`
  alone (no `click`, no subprocess); `cli.py` imports only `click` and
  `amplifier_memory`.

## Changelog

- **2026-09-06 — v2 locked (FROZEN 2026-09-06).** The steward's word,
  verbatim "lgtm, do it", is recorded in `docs/workflow/OWNER-RETURN-LOG.md`
  (entry 2026-09-06 20:55). Ratifies `cli.v1.v2-candidate.md` as written:
  §2 citation rate and the pre-registered kept definition; §3 edits and the
  `forgot` marker; §5 the well-formed row and `doctor --repair` as the
  explicit exception. Evidence: the steward's assistant repaired the store by
  hand with `printf` because no sanctioned repair existed (2026-09-06
  transcript); `git log --oneline` showed a save and its forget as identical
  lines (Dana persona run).
- 2026-09-06 — v1 locked; see `cli.v1.md`.
