target: contracts/suggestions.v3.md

# suggestions.v3.v8 candidate — automatic standalone fast routing

The owner approved fixing standalone setup for users whose shared providers work in
app-cli without an explicit routing entry. Setup supplies routing-matrix through
Foundation and Core, without importing or invoking amplifier-app-cli. Shared routing
matrix, overrides and source configuration retain precedence. Private preparation
includes the routing data required by the resolver.

Setup previews the selected account/model without a completion. Interactive users
can keep fast routing or choose a configured provider/model. Only an explicit choice
writes the memory instance configuration; shared settings and existing choices stay
intact. Unresolved roles block unattended setup and timer readiness rather than
silently selecting a chat default. Explicit reasoning budgets fit the existing
4,096-token total-output ceiling. Private jobs and source histories keep the v7
ownership boundaries.

Conformance: tests/test_setup_routing.py exercises settings precedence, private matrix
integrity, provider lifecycle, no setup completions/history, model selection, and
unresolved-role readiness. tests/test_inference.py checks the actual provider request
boundary. docs/FAST_ROUTING_VALIDATION.md records the isolated current-routing smoke
and remaining live-host limits.
