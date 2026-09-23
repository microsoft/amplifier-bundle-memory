"""One tool-free provider request, without an agent or persisted conversation.

Hosts supply their mounted providers and optional model-role resolver. The small
standalone adapter below uses installed modules and shared Foundation settings;
it neither composes a new agent bundle nor installs anything. A host must resolve
an explicitly selected bundle before calling this interface.
"""

from __future__ import annotations

import asyncio
import importlib.metadata
import inspect
import json
import os
import re
import shlex
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from pathlib import Path
from types import SimpleNamespace
from typing import Any
from urllib.parse import parse_qs, unquote, urlsplit
from uuid import uuid4

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
    selected = choice.provider or default_provider
    options: dict[str, Any] = {}
    if choice.inherits and choice.role and role_resolver is not None:
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
    provider = providers[selected]
    if choice.model:
        options["model"] = choice.model
    # Routing may supply inference knobs, not messages, tools, credentials,
    # endpoints or a second request. Unknown knobs fail rather than disappear.
    allowed = {"model", "temperature", "max_output_tokens", "top_p", "stop", "reasoning_effort"}
    if set(options) - allowed:
        raise InferenceError("Routing returned unsupported inference options; no call made")
    cap = options.get("max_output_tokens")
    if cap is not None and (isinstance(cap, bool) or not isinstance(cap, int) or cap < 1):
        raise InferenceError("Invalid routing output budget; no call made")
    options["max_output_tokens"] = min(cap or MAX_OUTPUT_TOKENS, MAX_OUTPUT_TOKENS)
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
        response = ChatResponse.model_validate(await provider.complete(request))
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
        result = Completion(
            text, selected, getattr(response, "model", None) or options.get("model"), usage
        )
        await event("completed", usage=usage, resolvedModel=result.model)
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


def _require_installed_source(module, source):
    """A declared source must match installed provenance, never trigger fetch."""
    entries = list(importlib.metadata.entry_points(group="amplifier.modules", name=module))
    if len(entries) != 1 or entries[0].dist is None:
        raise InferenceError(
            "Configured module requires one installed source; no installation attempted"
        )
    if not source:
        return entries[0]
    direct = json.loads(entries[0].dist.read_text("direct_url.json") or "{}")
    if not isinstance(source, str):
        raise InferenceError("Configured module source requires host-resolved inference")
    if source.startswith("git+"):
        uri, _, fragment = source[4:].partition("#")
        parsed = urlsplit(uri)
        _repo_path, at, ref = parsed.path.rpartition("@")
        repo = uri[: -(len(ref) + 1)] if at else uri
        subdir = parse_qs(fragment).get("subdirectory", [None])[0]
        matches = repo.removesuffix(".git") == direct.get("url", "").removesuffix(
            ".git"
        ) and subdir == direct.get("subdirectory")
        if at:
            vcs = direct.get("vcs_info", {})
            matches = matches and ref in {vcs.get("requested_revision"), vcs.get("commit_id")}
    elif source.startswith("file://"):
        matches = (
            direct.get("url", "").startswith("file://")
            and Path(unquote(urlsplit(source).path)).resolve()
            == Path(unquote(urlsplit(direct["url"]).path)).resolve()
        )
    else:
        matches = False
    if not matches:
        raise InferenceError(
            "Configured module source differs from installed runtime; host resolution required"
        )
    return entries[0]


async def complete_installed(prompt: str, *, call: CallConfig | None = None) -> Completion:
    """Standalone installed-runtime adapter. No subprocesses or session storage.

    Bundle-specific configuration belongs to the calling host; the standalone
    adapter never silently substitutes shared defaults for an explicit bundle.
    Missing Foundation/Core/provider modules fail with a setup diagnostic.
    """
    choice = call or CallConfig()
    if choice.bundle:
        raise InferenceError("Configured bundle requires host-resolved inference; no call made")
    try:
        from amplifier_core import ModuleCoordinator
        from amplifier_foundation.paths.resolution import get_amplifier_home
        from amplifier_foundation.settings import read_settings
    except ImportError:
        raise InferenceError(
            "Install the inference runtime or supply host-resolved inference"
        ) from None

    workspace = Path.cwd()
    shared_home = get_amplifier_home()
    try:
        settings = read_settings(
            (
                shared_home / "settings.yaml",
                workspace / ".amplifier" / "settings.yaml",
                workspace / ".amplifier" / "settings.local.yaml",
            )
        )
        config = settings.get("config", {})
        declarations = [row for row in config.get("providers", []) if row.get("enabled", True)]
        # Source override composition is host policy. Never ignore it and load
        # another installed implementation under the same provider name.
        source_policy = settings.get("sources", {}).get("modules") or settings.get("overrides")
        registered = settings.get("modules", {})
        if source_policy or registered.get("providers") or registered.get("hooks"):
            raise InferenceError("Module source overrides require host-resolved inference")
    except InferenceError:
        raise
    except Exception as exc:  # noqa: BLE001 - configuration errors become safe setup diagnostics
        raise InferenceError(
            f"Shared inference settings unavailable ({type(exc).__name__})"
        ) from None
    if not declarations:
        raise InferenceError("No shared provider configuration; supply host-resolved inference")
    # A call context supplies the standard coordinator's read-only configuration
    # and event correlation. It is not an AmplifierSession and is never persisted.
    context = SimpleNamespace(
        config={"providers": declarations}, session_id=f"memory-inference-{uuid4()}", parent_id=None
    )
    coordinator = ModuleCoordinator(session=context)
    providers = {}
    defaults = []
    try:
        environment = _credential_environment(shared_home)
        for row in declarations:
            module = row.get("module")
            if not isinstance(module, str) or not module.startswith("provider-"):
                raise InferenceError("Invalid configured provider module")
            name = row.get("id") or row.get("instance_id") or module.removeprefix("provider-")
            if not isinstance(name, str) or not name.strip():
                raise InferenceError("Invalid configured provider identity")
            if name in providers:
                raise InferenceError("Duplicate configured provider identity")
            # Use the public module entry-point/mount contract, with no resolver
            # fallback or activator that could fetch/install another implementation.
            previous = dict(coordinator.get("providers") or {})
            entry = _require_installed_source(module, row.get("source"))
            cleanup = await entry.load()(coordinator, _expand(row.get("config", {}), environment))
            if cleanup:
                coordinator.register_cleanup(cleanup)
            mounted = coordinator.get("providers") or {}
            key = module.removeprefix("provider-")
            provider = mounted.get(key)
            if provider is None or provider is previous.get(key):
                raise InferenceError("Configured provider did not mount; no call made")
            providers[name] = provider
            await coordinator.mount("providers", provider, name=name)
            if key != name:
                if key in previous:
                    await coordinator.mount("providers", previous[key], name=key)
                else:
                    await coordinator.unmount("providers", name=key)
            priority = row.get("config", {}).get("priority", 100)
            if isinstance(priority, bool) or not isinstance(priority, (int, float)):
                raise InferenceError("Invalid configured provider priority")
            defaults.append((priority, name))
        # Only the configured routing module is mounted, never general hooks.
        # It registers its resolver without session:start or prompt execution.
        routing_configured = False
        for row in config.get("hooks", []):
            if row.get("module") == "hooks-routing" and row.get("enabled", True):
                routing_configured = True
                entry = _require_installed_source("hooks-routing", row.get("source"))
                cleanup = await entry.load()(
                    coordinator, _expand(row.get("config", {}), environment)
                )
                if cleanup:
                    coordinator.register_cleanup(cleanup)
        resolver = coordinator.get_capability("model_role_resolver")
        if routing_configured and choice.inherits and choice.role and resolver is None:
            raise InferenceError("Configured routing did not provide a model-role resolver")
        best = min(priority for priority, _ in defaults)
        default_names = [name for priority, name in defaults if priority == best]
        default_provider = default_names[0] if len(default_names) == 1 else None
        return await complete_once(
            prompt,
            providers=providers,
            call=choice,
            role_resolver=resolver,
            default_provider=default_provider,
        )
    except asyncio.CancelledError:
        raise
    except Exception as exc:
        if isinstance(exc, InferenceError):
            raise
        raise InferenceError(f"Installed inference setup failed ({type(exc).__name__})") from None
    finally:
        await coordinator.cleanup()


def default_completion(prompt: str, *, call: CallConfig | None = None) -> Completion:
    """Synchronous timer/library entrypoint; async hosts use complete_once."""
    if os.environ.get("PYTEST_CURRENT_TEST"):
        raise InferenceError("Tests must inject model_call; real inference is disabled")
    return asyncio.run(complete_installed(prompt, call=call))
