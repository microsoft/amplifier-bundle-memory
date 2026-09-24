"""One tool-free provider request using host-owned providers.

The portable entrypoint delegates to the prepared Core/Foundation private-session
runtime. Hosts can call complete_once with providers they already own.
"""

from __future__ import annotations

import asyncio
import inspect
import os
import re
import shlex
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from typing import Any

from .llm_config import CallConfig

MAX_OUTPUT_TOKENS = 4096


class InferenceError(RuntimeError):
    """Safe diagnostic; provider exception bodies may contain credentials/input."""


@dataclass(frozen=True)
class Completion:
    text: str
    provider: str
    model: str | None
    usage: dict[str, Any] | None
    model_source: str | None = None


def request_options(options):
    """Translate only supported inference knobs, never arbitrary wire payloads."""
    options = dict(options)
    allowed = {
        "model",
        "temperature",
        "max_output_tokens",
        "top_p",
        "stop",
        "reasoning_effort",
        "thinking_budget_tokens",
        "extra_request_params",
    }
    if set(options) - allowed:
        raise InferenceError("Routing returned unsupported inference options; no call made")
    cap = options.get("max_output_tokens")
    if cap is not None and (isinstance(cap, bool) or not isinstance(cap, int) or cap < 1):
        raise InferenceError("Invalid routing output budget; no call made")
    cap = min(cap or MAX_OUTPUT_TOKENS, MAX_OUTPUT_TOKENS)
    options["max_output_tokens"] = cap
    provider_options = {}
    if "thinking_budget_tokens" in options:
        budget = options.pop("thinking_budget_tokens")
        if isinstance(budget, bool) or not isinstance(budget, int) or budget < 1024 or cap < 2048:
            raise InferenceError("Thinking budget is incompatible with memory output limit")
        # Leave room for the answer inside the existing total-output ceiling.
        provider_options["extended_thinking"] = True
        provider_options["thinking_budget_tokens"] = min(budget, cap // 2)
        provider_options["thinking_budget_buffer"] = (
            cap - provider_options["thinking_budget_tokens"]
        )
    if "extra_request_params" in options:
        extra = options.pop("extra_request_params")
        thinking = extra.get("thinking_config") if isinstance(extra, dict) else None
        if (
            not isinstance(extra, dict)
            or set(extra) != {"thinking_config"}
            or not isinstance(thinking, dict)
            or set(thinking) != {"thinking_level"}
            or thinking["thinking_level"] not in {"minimal", "low", "medium", "high"}
        ):
            raise InferenceError("Routing returned unsupported inference options; no call made")
        effort = thinking["thinking_level"]
        if options.get("reasoning_effort", effort) != effort:
            raise InferenceError("Conflicting routing thinking settings; no call made")
        # Gemini's public per-call reasoning knob maps to this exact level.
        options["reasoning_effort"] = effort
    if options.get("model"):
        # Some providers consume the public model kwarg rather than request.model.
        provider_options["model"] = options["model"]
    return options, provider_options


async def resolve_selection(providers, choice, role_resolver=None, default_provider=None):
    """Resolve once without a completion; shared by setup and inference."""
    selected = choice.provider or default_provider
    options: dict[str, Any] = {}
    if choice.inherits and choice.role:
        if role_resolver is None:
            raise InferenceError(
                "Requested model role has no prepared resolver. Configure routing, "
                "explicitly choose provider/model, or use host-resolved inference"
            )
        try:
            preferences = await role_resolver.resolve(choice.role)
        except asyncio.CancelledError:
            raise
        except Exception as exc:  # noqa: BLE001 - sanitize provider-backed resolver failures
            raise InferenceError(f"Model-role resolution failed ({type(exc).__name__})") from None
        if not preferences:
            raise InferenceError("Configured model role has no available provider; no call made")
        preference = preferences[0]
        selected = preference.provider
        options = dict(preference.config or {})
        options["model"] = preference.model
    if selected is None:
        if len(providers) != 1:
            raise InferenceError("No unambiguous default provider; supply host-resolved inference")
        selected = next(iter(providers))
    if selected not in providers:
        raise InferenceError("Configured provider is unavailable; no call made")
    if choice.model:
        options["model"] = choice.model
    options, provider_options = request_options(options)
    return selected, options, provider_options


async def complete_once(
    prompt: str,
    *,
    providers: Mapping[str, Any],
    call: CallConfig | None = None,
    role_resolver: Any = None,
    default_provider: str | None = None,
    observe: Callable[[dict], Any] | None = None,
    resolved_bundle: str | None = None,
) -> Completion:
    """Use the host's existing provider/auth/routing, without a tool loop.

    Provider ownership stays with the host. This function propagates cancellation
    but never closes a shared provider, mutates its configuration, or starts a
    session. ``observe`` receives safe lifecycle facts, never prompt/error bodies.
    """
    from amplifier_core.message_models import ChatRequest, ChatResponse, Message

    choice = call or CallConfig()
    if choice.bundle and choice.bundle != resolved_bundle:
        raise InferenceError("Configured bundle requires host-resolved inference; no call made")
    if not isinstance(prompt, str) or not prompt.strip():
        raise InferenceError("Memory inference requires a nonempty prompt")
    selected, options, provider_options = await resolve_selection(
        providers, choice, role_resolver, default_provider
    )
    provider = providers[selected]
    request = ChatRequest(
        messages=[Message(role="user", content=prompt)],
        tools=[],
        tool_choice="none",
        timeout=None,
        metadata={"purpose": "memory.suggestion"},
        **options,
    )

    async def event(status: str, **facts):
        if observe is not None:
            value = observe(
                {
                    "purpose": "memory.suggestion",
                    "status": status,
                    "provider": selected,
                    "model": options.get("model"),
                    **facts,
                }
            )
            if inspect.isawaitable(value):
                await value

    await event("started")
    try:
        # No retry/fallback loop and no elapsed completion deadline here.
        response = ChatResponse.model_validate(await provider.complete(request, **provider_options))
        if response.tool_calls or any(
            block.type in {"tool_call", "tool_use"} for block in response.content
        ):
            raise InferenceError("Provider returned a tool call to a tool-free request")
        text = "".join(block.text for block in response.content if block.type == "text")
        if not text.strip():
            raise InferenceError("Provider returned no assistant text")
        if response.finish_reason not in {None, "stop", "end_turn", "completed", "stop_sequence"}:
            raise InferenceError("Provider did not complete the memory response")
        usage = (
            response.usage.model_dump(
                mode="json",
                include={
                    "input_tokens",
                    "output_tokens",
                    "total_tokens",
                    "reasoning_tokens",
                    "cache_read_tokens",
                    "cache_write_tokens",
                    "cost_usd",
                },
            )
            if response.usage is not None
            else None
        )
        reported_model = getattr(response, "model", None)
        requested_model = options.get("model")
        result = Completion(
            text,
            selected,
            reported_model or requested_model,
            usage,
            "response" if reported_model else "request" if requested_model else None,
        )
        await event(
            "completed", usage=usage, resolvedModel=result.model, modelSource=result.model_source
        )
        return result
    except asyncio.CancelledError:
        await event("cancelled")
        raise
    except Exception as exc:
        await event("failed", errorType=type(exc).__name__)
        if isinstance(exc, InferenceError):
            raise
        raise InferenceError(f"Memory provider request failed ({type(exc).__name__})") from None


def _expand(value, environment):
    """Materialize explicit environment placeholders without guessing accounts."""
    if isinstance(value, str):

        def substitute(match):
            name = match.group(1)
            if name not in environment:
                raise InferenceError("A configured provider environment value is unavailable")
            return environment[name]

        return re.sub(r"\$\{([A-Za-z_][A-Za-z0-9_]*)\}", substitute, value)
    if isinstance(value, dict):
        return {key: _expand(item, environment) for key, item in value.items()}
    if isinstance(value, list):
        return [_expand(item, environment) for item in value]
    return value


def _credential_environment(home):
    """Read referenced shared keys without changing the caller's environment."""
    keys = {}
    path = home / "keys.env"
    if path.is_file():
        for raw in path.read_text().splitlines():
            line = raw.strip().removeprefix("export ")
            if not line or line.startswith("#") or "=" not in line:
                continue
            name, value = line.split("=", 1)
            if re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", name.strip()):
                keys[name.strip()] = " ".join(shlex.split(value, comments=True))
    return {**keys, **os.environ}


async def complete_installed(
    prompt: str, *, call: CallConfig | None = None, home=None
) -> Completion:
    """Use the explicitly prepared private Core/Foundation session runtime."""
    from .runtime import complete

    return await complete(prompt, home=home, call=call)


def default_completion(prompt: str, *, call: CallConfig | None = None, home=None) -> Completion:
    """Synchronous timer/library entrypoint; async hosts use complete_once."""
    if os.environ.get("PYTEST_CURRENT_TEST"):
        raise InferenceError("Tests must inject model_call; real inference is disabled")
    return asyncio.run(complete_installed(prompt, call=call, home=home))
