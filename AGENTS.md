# amplifier-memory — repo conventions

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
   relative paths or bare names.** `source: git+https://github.com/bkrabach/amplifier-memory@main#subdirectory=modules/<m>`
   in behaviors; `amplifier-memory @ git+https://github.com/bkrabach/amplifier-memory@main`
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

## Layout

```
docs/VISION.md        the direction (owner-ratified)
contracts/*.v1.md     store · session · cli · suggestions
ledger/               conformance rows, derived from contracts by the reconciler
modules/              hooks-memory-inject · tool-memory (Amplifier modules)
src/amplifier_memory/ store writer, CLI, suggest job
behaviors/, bundle.md the composable app bundle
tests/                in-process conformance; one real-session smoke
```

## Gates before a merge

`uv run pytest` · module suites · `uv run ruff check` · the contract's
Conformance section evidenced · **and** a real-host smoke: one session that
saves a memory and one that loads it, on this device.
