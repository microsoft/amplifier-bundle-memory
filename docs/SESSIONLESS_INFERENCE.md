# Memory suggestion inference

A portable `run_suggest` pass makes one tool-free provider request per eligible
source session, within its call/input budgets. Its private Core session mounts and
cleans up prepared modules; it never executes an agent loop or registers a normal
chat. Session metadata, transcripts and usage events stay under the resolved
memory home's `runtime/jobs`. Existing source histories and quote verification
are unchanged. This filename is retained for existing links.

Unified's consolidation uses its own mounted provider directly. Neither path
requires an amplifier-app-cli package, executable or import.

## Host-owned providers

An async host can use `complete_once` from `amplifier_memory.inference` with its
mounted `providers`, `default_provider` and public `model_role_resolver`.
`CallConfig` carries the memory instance's explicit provider/model/bundle or role.
A synchronous `run_suggest(model_call=...)` callback can return `Completion` or a
plain string. The host retains provider ownership: the adapter never closes shared
clients or changes environment. Cancellation propagates and no retry/tool loop is
added. Safe lifecycle observations exclude prompts and raw error bodies.

## Prepared standalone runtime

The package declares Core ≥2.0.1, Foundation and uv dependencies. Storage imports
remain lightweight. Run `amplifier-memory setup --workspace /path/to/project`
explicitly to resolve configured sources and install their dependencies in the
tool environment. Private source copies, caches and preparation receipts live
under `store_home()/runtime`. Inference and readiness never install or activate
modules. Timer installation/start/restart requires offline readiness.

Foundation merges shared, workspace and workspace-local settings. The supported
shape is `config.providers` plus an explicit `config.hooks` entry for
`hooks-routing`. Provider account `id`/`instance_id`, configuration and priority
are retained. `sources.modules` overrides take precedence over module-row sources.
Known provider, loop-basic, context-simple and routing source defaults track their
Microsoft repositories' `main`; custom providers require explicit sources.
Preparation receipts bind exact installed contents and configuration. They do not
prove every upstream default SDK works or perform an inference-time freshness check.

For example, a host that intends the balanced routing policy can declare:

```yaml
config:
  providers:
    - id: work-openai
      module: provider-openai
      config:
        api_key: ${OPENAI_API_KEY}
  hooks:
    - module: hooks-routing
      config:
        default_matrix: balanced
```

Keep the user's actual routing configuration; this example is not a policy to
substitute for a configured bundle. Arbitrary bundle includes are not composed.
If a requested role (normally `fast`) has no prepared resolver, setup/inference
fails visibly. Configure the routing hook explicitly, choose a provider/model
explicitly, or use host-resolved inference. A role never silently falls through
to a provider default. An embedding caller that explicitly supplies no role can
use an unambiguous default provider. Explicit selections are never rerouted.

`${NAME}` credential references read shared `keys.env`, with process environment
taking precedence. The dedicated console process also supplies missing environment
keys for SDK-owned credential loading; embedding APIs never modify environment.
Provider-owned OAuth refresh writes retain the provider's configured ownership.
No credentials are copied into job receipts.

Only providers, explicit routing and the minimal loop/context lifecycle are
mounted. General user hooks, tools, recursive memory jobs and workspace instructions
are excluded. Owned sessions clean up on success, error and cancellation. Output
is capped at 4,096 tokens; healthy requests have no fixed completion deadline.

Shared settings may contain an interactive `modules.tools` list and tool,
general-hook, context or loop overrides. These are outside private inference and
do not change its provider plan or invalidate readiness. The private loop/context
keep their own minimal configuration. Provider/account overrides, routing-hook
overrides, other legacy mount sections and unknown override names require
host-resolved inference; they are never silently discarded.

The memory tool and injection-hook packages declare Foundation directly, matching
the library's Git requirement. This supports host installers that retain an
installed library version while resolving modules with `--no-sources`; nested
Git requirements must remain visible at the module installation boundary.

## Receipts and limits

`SuggestReport.inference` and private job receipts carry provider identity and
measured usage. Model provenance distinguishes a response-reported model
(`modelSource: response`) from the explicit/routed request (`request`). If neither
is available, the model remains unknown; an SDK's declared default is not claimed
as a confirmed response model. Unknown token/cost values remain unknown.

Explicit bundle selection and unsupported module composition require host-resolved
inference. Routing options outside supported typed request knobs fail visibly.
Readiness verifies environment, settings and source contents without mounting a
provider; it does not prove live authentication or provider SDK compatibility.
Legacy pure argv/flag helpers remain import-compatible but no runner executes them.

See [Private inference validation](PRIVATE_INFERENCE_VALIDATION.md) for the exact
synthetic fresh-install acceptance and remaining real-host gates.
