target: contracts/suggestions.v3.md

# suggestions.v3.v7 candidate — sessionless inference (DRAFT)

The owner explicitly requires memory inference to work without
`amplifier-app-cli`. The portable runner's `amplifier run` subprocess used full
agent startup and persisted a conversation for a single suggestion request,
which exposed internal work in ordinary chat lists. Unified's mounted-provider
consolidation is already direct; this proposal changes the portable runner.

Replace the Core 3 inference mechanism with a single tool-free provider request
using Core's typed request/response protocol. Keep the host's configured
provider account, model-role selection and credentials. An explicit unavailable
provider, unsupported bundle/source composition, or unavailable configured role
fails with a setup diagnostic; it must not install a runtime or silently select
a different account. The host may instead supply its already resolved providers
through the existing model-call injection seam.

No agent session, tool loop, CLI executable/import, hidden install, or new
conversation persistence is required. Healthy LLM calls have no fixed elapsed
completion deadline. Existing per-run call and request-size budgets remain;
output has an explicit token cap. Cancellation propagates and locally owned
provider mounts are cleaned up without closing host-owned clients.

For Core 8/9, report the selected provider/model and actual usage when supplied.
Unknown usage and cost remain unknown, not zero or an estimate based on a
historical default model. Preserve existing log fields and parse older lines.

The same human-origin eligibility, fenced prompt, quote verification, inbox
review/approval, disabled-instance behavior, and read-only source histories
remain in effect. There is no historical session deletion, archive or backfill.

Conformance evidence is in `tests/test_inference.py` and the default callback
integration in `tests/test_suggest.py`. Synthetic installed providers exercise
selection, error/cancellation cleanup, absent CLI, and no new session files.
Real-host/provider acceptance remains a separate gate; this proposal and its
isolated tests do not claim live deployment or authorization to replay jobs.
