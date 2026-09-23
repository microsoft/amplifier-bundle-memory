target: contracts/suggestions.v3.md

# suggestions.v3.v7 candidate — private portable inference (DRAFT)

The owner requires portable memory inference without amplifier-app-cli. Unified's
mounted-provider consolidation remains direct; this change replaces the separate
portable suggestion runner's amplifier-run subprocess.

Core/Foundation are declared standalone runtime dependencies. Explicit `setup`
prepares configured provider/routing sources in a memory-owned runtime subtree and
installs dependencies in the standalone tool environment. Normal inference cannot
install, refresh sources or invoke another application. Offline readiness checks
precede timer enablement and reject changed settings/packages/source contents.

Each suggestion request uses an AmplifierSession for public module mounting and
cleanup, then makes one tool-free typed provider call without an agent loop.
Shared configuration is read with Foundation's scoped settings API. Account,
model, role, explicit source and credential configuration are preserved within
the documented supported settings shape. Unsupported bundle/module composition
requires host-resolved inference; no account is silently substituted.

Generated session metadata, transcript and usage events live below
`store_home()/runtime/jobs`. Prepared caches live below the same runtime root.
They are internal memory jobs, excluded from suggestion source ingestion and Git.
Existing memory homes, histories, source sessions and provenance files are preserved.
Provider-owned credential refresh writes retain their configured ownership.

Healthy provider requests have no fixed elapsed completion deadline. Existing
per-pass call/input budgets remain and output is capped at4096tokens. Cancellation
propagates; owned provider mounts clean up on success, error and cancellation.
Host-supplied providers are never closed by complete_once. Usage records identify
actual provider/model; unknown usage and cost remain unknown.

The existing human eligibility, fenced prompt, quote verification, inbox review,
disabled-instance and source-history preservation rules remain. There is no
historical archive/delete/backfill. CLI doctor/update have no automatic app-cli
prerequisite; optional legacy interop remains explicit.

Tests cover Core2 private sessions, default suggest callback, readiness, cancellation,
source/config drift and private persistence with synthetic providers. Fresh uv-tool
acceptance additionally runs real Foundation source preparation and routing.
No real provider quality, real credential refresh or operating-system timer run is
claimed by these isolated checks.
