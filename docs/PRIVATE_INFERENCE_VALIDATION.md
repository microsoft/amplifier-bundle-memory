# Private inference validation

The portable runner is independent of amplifier-app-cli. Unified's existing
mounted-provider consolidation path is unchanged.

Validated on 2026-09-23 with Python 3.13, published Core 2.0.1 and Foundation
2a63c56ef11e5e9b49a1268c4845e3046d397230:

- A fresh, non-editable uv-tool install included its declared runtime dependencies
  and no amplifier-app-cli distribution/executable. Core came from the public
  PyPI wheel; no Core build or downgrade occurred.
- The actual `setup` command prepared sources in the memory instance, copied local
  modules before installation, and used its own declared uv binary. The actual
  console `suggest` command then used the default callback, real Core mounting,
  real Foundation scoped settings and the real hooks-routing module.
- A synthetic provider received one tool-free request for the named account and
  routed model. It returned one verified proposal and measured usage. Inference
  could not connect to the network, run a non-Git subprocess, or write Python
  files outside the private test root. Source transcripts/settings stayed exact.
- Service installation was refused before setup and rendered after offline
  readiness, without starting any operating-system service.
- `tests/test_runtime.py` covers failure/cancellation/cleanup, account and role
  precedence, setup failure preserving the prior receipt, disabled instances,
  changed sources, library environment preservation, standalone credential
  loading, and exclusion of private jobs from Git and source ingestion.

The full library suite passed 480 tests. Ten host-tool documentation checks failed
on this Mac and reproduced unchanged on base b224eea: Linux `systemctl` is absent,
and Git manual overstrike formatting breaks literal argument searches. After the
last setup safeguards, the focused runtime suite passed all 18 tests. Ruff and
`uv lock --check` passed. Synthetic timer fixtures explicitly model systemd;
they do not prove launchd/systemd activation on a real host.

Run the focused acceptance locally:

```bash
uv sync
uv run pytest tests/test_runtime.py tests/test_inference.py tests/test_suggest.py
```

The fresh-tool exercise additionally used controlled local module sources and
real routing, never a provider account or a model. It does not prove provider SDK
compatibility for every configured source, real OAuth refresh, model quality, or
live service operation. Arbitrary host bundle composition remains an explicit
host-resolved-inference requirement. No saved history was migrated or deleted.
