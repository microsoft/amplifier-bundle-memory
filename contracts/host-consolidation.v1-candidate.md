# Host-scoped consolidation API (DRAFT)

An embedding host needs opted-in recall of user-confirmed project decisions and
successful approaches. The personal suggestion contract deliberately excludes
those records. This separate library API lets a host select an explicit policy
without changing the personal store, session hook, CLI, or daily suggestion pass.

`amplifier_memory.consolidation.build_request(turns, policy="personal"|"workspace", known=[])`
accepts complete human text, bounds the encoded sources to 16,000 characters,
and asks for up to eight references with exact human quotations. `personal`
is the default. `workspace` includes settled project decisions, reasons, and
human-confirmed outcomes. Temporary requests and speculative suggestions do
not qualify. Both policies treat all source content as untrusted data.

Known references carry stable ids and text in an additional 12,000-character
bounded window. Corrections identify contradicted known ids in `supersedes`.
The host checks scope, chronology and revisions before applying supersession.

`verified_candidates(reply, turns, known=[])` reuses the suggestion parser and quote
verifier. It returns only supported quotations with bounded, explicitly
model-derived wording. Attribution verification is not a semantic classifier,
proof of an outcome, or permission to act.

`relevant(records, query, limit=5)` selects already-scoped records by shared
lexical terms and reports those terms. No shared term means no selection.
This is a transparent baseline, not semantic retrieval.

This module performs no I/O and calls no model. Hosts own source attribution,
consent, eligible idle/completed lifecycle, model routing, cost limits, scoped
storage, correction/deletion, read/write announcements, and request-boundary
delivery. The API starts no CLI session or OS timer and never reads an existing
memory instance. Existing frozen contracts remain unchanged.

Acceptance: ordinary preference, project decision, and confirmed-outcome cases;
forged quotation rejection; unsupported content exclusion; bounded complete
turns; unchanged default personal suggestion behavior. Real model and host
acceptance are separate from these pure contract tests.
