# Memory suggestion inference

A portable `run_suggest` pass makes one tool-free provider request per eligible
session, within its existing call/request-size budgets. It does not launch
`amplifier run`, construct an agent session, register a chat, or write another
conversation transcript. Existing histories and suggestion quote verification
are unchanged.

Unified's own memory consolidation already calls its mounted provider directly.
This adapter replaces the portable suggestion runner's separate CLI path; it
requires no change to Unified and introduces no CLI dependency.

## Host-owned providers

An async host can import `complete_once` from `amplifier_memory.inference` and
supply its mounted `providers`, `default_provider`, and optional public
`model_role_resolver`. Pass a `CallConfig` to retain the memory instance's choice.
The result contains text, the selected account, the reported model when known,
and measured usage when available. A synchronous `run_suggest(model_call=...)`
callback can return that `Completion`, or continue returning a plain string.

The host retains provider ownership. Cancellation propagates; the adapter never
closes shared clients or starts a retry/tool loop. An optional `observe` callback
receives safe started/completed/failed/cancelled facts, excluding prompts and raw
provider exception bodies. The synchronous default uses the installed adapter
below, not an async host's running event loop.

## Installed standalone runtime

Provision Core, Foundation and the selected provider/routing modules in the
calling environment as explicit host dependencies. The base memory package keeps
its lightweight dependency graph; importing its storage APIs does not load a model
runtime. The adapter never fetches or installs modules, probes another executable,
or changes the process environment.
It uses public `amplifier.modules` entry points and their `mount` contract.

Foundation merges shared, project and project-local settings. Enabled
`config.providers` declarations retain their module, account `id`/`instance_id`,
configuration and priority. Explicit `${NAME}` credential references use
`keys.env` with process environment taking precedence. SDK-specific credential
loading remains owned by the installed provider; no account is guessed or copied.
Keys that exist only in `keys.env` and require process-global environment must
be explicitly referenced in provider configuration or supplied by the host.

Selection order:

1. An explicit provider/model/bundle choice wins over the role.
2. Otherwise the configured routing module resolves the requested role (`fast`
   by default). An empty result or missing configured resolver fails visibly.
3. Without configured routing, the unique highest-priority provider is used.
   Ties are ambiguous; an arbitrary account is never selected.

Only provider modules and explicitly configured `hooks-routing` are mounted.
No general hooks, session lifecycle, tools, bundle preparation or persistence
runs. Owned mount cleanup executes on success, error and cancellation. Request
output is capped at 4,096 tokens; no elapsed completion deadline is imposed while
the provider request remains healthy. Transport/auth behavior remains provider-owned.

## Explicit limits

The standalone adapter does not reproduce an application's bundle composition,
source overrides, session-specific routing or custom orchestration. An explicit
bundle or module-source override requires host-resolved inference and fails
before inference rather than substituting a default. A declared source must
match the installed distribution's direct URL, subdirectory and requested ref
or commit. Mutable-ref receipts establish installed provenance, not upstream
freshness; there is no network update check. Frozen installations recording only
a resolved commit for a declared branch require the host-resolved path.

Routing options outside the supported typed request knobs fail visibly rather
than disappear. Host-resolved bundles must be explicitly identified by the host.
Missing optional runtime modules produce setup diagnostics, never installation.

`SuggestReport.inference` contains completed-call receipts. The existing run log
adds known token/cost totals and explicit unknown counts; absent costs are not
reported as free. Failure diagnostics remain in the degraded run status. The
provider protocol may apply its own retries; this adapter adds none. Legacy pure
argv/flag formatting helpers remain import-compatible but no runner executes them.

## Validation

`tests/test_inference.py` covers explicit/role/default selection, account/auth
binding, installed source refusal, tool-free output, usage, cancellation and
cleanup. `test_default_suggest_callback_runs_installed_provider_without_cli`
exercises the un-injected default suggestion callback through real Core requests
and a synthetic installed provider, retaining original transcript bytes and
verifying candidate quotes. Optional-runtime tests skip if Core/Foundation are
not provisioned. No test requires a model call or a real memory store.

Real provider authentication and real-host memory acceptance are separate from
these synthetic checks and are not claimed by this change.
