# Suggestion job provenance

The default suggestion judge launches `amplifier run --output-format json` with
these values in a private copy of its child environment:

- `AMPLIFIER_SESSION_VISIBILITY=internal`
- `AMPLIFIER_SESSION_PURPOSE=memory.suggestion`
- `AMPLIFIER_SESSION_ORIGIN=agent`

Only this implementation job gets the declaration. The caller's environment,
provider routing, credentials, CLI arguments, timer scheduling, and retry
behavior are unchanged. No raw environment values are logged.

The compatible CLI persists visibility and purpose as creation metadata. Unified
can then keep this history available for diagnostics while excluding it from
ordinary chat lists and default searches. A generic agent origin does not make
other standalone CLI conversations internal. End-to-end presentation requires
both the CLI persistence support and the Unified consumer support; an older CLI
ignores the visibility declaration. Historical unmarked sessions are not
rewritten or classified by prompt wording.
