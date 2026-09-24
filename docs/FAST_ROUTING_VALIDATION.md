# Standalone fast-routing validation

Validated on macOS with Core 2.0.1 on 2026-09-24. No real provider completion,
shared configuration write, live service change, or source-history mutation was
performed. The peer's authentication and scheduled Linux run still need validation
on that machine.

## Regression checks

- Focused inference, runtime, setup and CLI suites pass (see PR check record).
- Full library/ledger run: 513 passed, 10 failures. All ten reproduce on the
  unchanged baseline: nine Git man-page formatting assertions on macOS and one
  missing Linux `systemctl` executable.
- Module suites with their configured asyncio mode: 206 passed, one skipped,
  one failure. The failure also reproduces on baseline: macOS resolves `/home`
  under `/System/Volumes/Data`, conflicting with a Linux slug expectation.
- Ruff and diff whitespace checks pass. `setup --help` documents `--choose` and
  the optional workspace path. The existing uv installer flags were checked
  against `uv pip install --help`.

## Actual routing source and private preparation

Using routing-matrix commit `85419293c81f6c6ff2df5611104fe716e609125c`, an isolated
interpreter without amplifier-app-cli performed real Foundation preparation,
private dependency installation and Core mounting. Each case used providers-only
shared settings with synthetic provider implementations and local source overrides;
there was no explicit routing hook or routing entry. Separate processes mirror
standalone CLI invocations and avoid re-importing modules from different generations.

| Provider family | Fast model from synthetic catalog | Setup completions | Subsequent synthetic completion |
| --- | --- | ---: | ---: |
| OpenAI | gpt-5.6-luna | 0 | 1 |
| Anthropic | claude-haiku-4.5 | 0 | 1 |
| Gemini | gemini-3.7-flash | 0 | 1 |

Each setup retained the routing YAML assets in its private generation, left shared
settings byte-identical, created no shared project/session history, and preserved
an absent explicit memory model choice. Each subsequent completion used the routed
model rather than the deliberately different shared default.

## Provider request construction

Network connections were disabled while checking current provider request builders:

- Anthropic `9e2f20c9342253666d0bdb3dcf593a58456e72f9`: the requested Haiku model,
  `max_tokens: 4096`, and enabled thinking with `budget_tokens: 2048` reached the
  constructed request. The explicit enable flag is required by the provider.
- Gemini `e191990d3c7e031086ec1a40ed1f23fdac943cac`: the routing thinking-level directive
  became `LOW` through the provider's public per-call reasoning option, with the
  memory output ceiling retained.

These checks prove preparation, selection and request construction, not live API
acceptance, account authorization, absolute model prices or suggestion quality.
