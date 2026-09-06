# cli.v1 — `amplifier-memory`

**Status:** DRAFT · **Governs:** the `amplifier-memory` command
**Who builds against it:** humans at a shell; `doctor` consumers; the
install path in README.

## Purpose

The CLI is how a human looks at the store without a session, installs the
bundle's device-side pieces, and asks "why". It is small on purpose: the
store is files, so `cat`, `grep`, and `git log` already do most of the work.

## Core

1. **Verbs.** `init` · `status` · `why <id>` · `review` · `doctor` ·
   `service {install,uninstall,start,stop,restart,status,logs}` · `update`
   (alias `upgrade`). Nothing else. Read verbs work with nothing installed
   but the store.
2. **`status`** prints the numbers VISION §9 cares about, from git and
   `usage.jsonl`: memories in `MEMORY.md`; written / forgotten in the last 7
   and 30 days; **kept** (written ≥7 days ago and still present); topics and
   how many are stale (unread 90 days); pending suggestions; last suggest
   run. One screen. This is the project's success metric made visible.
3. **`why <id>`** prints the git commits mentioning `[<id>]`: the text, the
   verbatim quote, session id, writer, and date — creation, edits, and
   forget if any. It is `git log --grep`, formatted.
4. **`review`** is the shell form of `/memory review` (suggestions.v1 §6).
   With an empty inbox it says so and exits 0.
5. **`doctor`** never mutates. Rows: store present and is a git repo · cap
   headroom (`MEMORY.md` N/200, topics N/50) · stale topics count · inbox
   size and oldest · suggest timer installed/enabled/last run/last outcome
   (Phase 2) · substrate present (Phase 2 only; INFO when Phase 2 is not
   installed) · **update check** — installed commit vs `git ls-remote` of
   the pinned ref, WARN with the remedy when behind, INFO "not checkable"
   offline, never RED. Exit code is nonzero only on failed checks.
6. **`service`** manages only the Phase 2 suggest timer (systemd `--user` /
   launchd). `install` renders units, `daemon-reload → enable --now`, and
   rolls back written units if any step fails. Phase 1 has no service; the
   verb reports that plainly.
7. **`update`** upgrades the uv tool and refreshes the registered app bundle,
   restarts the timer if installed, ends by running `doctor`, and prints the
   stale-in-memory note: sessions started before the refresh keep the old
   module code until restarted.
8. **`init`** creates the store.v1 layout at the store location and makes
   the initial commit. Idempotent: a second run reports the store exists and
   changes nothing. It is the README's step 3 and the only setup Phase 1
   needs.

## Reserved

- **R1 — `status` "kept" definition.** Present ≥7 days after write. Revisit if
  the owner's forget cadence makes 7 days uninformative.

## Explicitly backlogged

- `--json` output — no consumer yet.
- A `remember`/`forget` shell verb — the session commands cover it; add only
  if the owner reaches for the shell first.

## Conformance

- Verb surface exactly as §1; unknown verb is a one-line error.
- `status` numbers match a fixture store's git history exactly (written,
  forgotten, kept computed from commit dates).
- `why` returns the commit(s) for an id; unknown id is a one-line error.
- `doctor` is byte-identical before/after on the store (no mutation); update
  check trio: behind → WARN with remedy / current → OK / offline → INFO.
- `service install` round-trip leaves no units behind; failing enable step
  removes written units.
- `init` twice is a no-op with a message.

## Changelog

- 2026-09-06 — Initial draft.
