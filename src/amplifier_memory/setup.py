"""Standalone setup preview and model selection. No provider completions."""

from __future__ import annotations

import asyncio
import copy
import os
from pathlib import Path
from uuid import uuid4

import yaml

from . import runtime
from .inference import InferenceError, _credential_environment, _expand, resolve_selection
from .llm_config import CallConfig, config_path, load


def setup_inference(home=None, *, workspace=None, emit=print, choose=None):
    """Dedicated console boundary; optional chooser returns a one-based option."""
    return asyncio.run(_setup(home, workspace=workspace, emit=emit, choose=choose))


async def _setup(home, *, workspace, emit, choose):
    receipt = await runtime.prepare(home, workspace=workspace)
    # A failed preview must not leave the timer reporting a qualified runtime.
    receipt["selectionPending"] = True
    root = runtime.runtime_home(home)
    runtime._write(root / "prepared.json", receipt)
    environment = _credential_environment(Path(receipt["sharedHome"]))
    for name, value in environment.items():
        os.environ.setdefault(name, value)
    choice = load(home).call()
    plan, _ = runtime._plan(receipt["settingsPaths"], choice)
    plan = _expand(plan, environment)
    runtime._private_routing_paths(plan, receipt)
    from amplifier_core import AmplifierSession
    from amplifier_foundation.bundle import BundleModuleResolver

    session = AmplifierSession(copy.deepcopy(plan), session_id="memory-setup-" + uuid4().hex)
    try:
        await session.coordinator.mount(
            "module-source-resolver",
            BundleModuleResolver({k: Path(v) for k, v in receipt["modulePaths"].items()}),
        )
        session.coordinator.register_capability("session.working_dir", str(root))
        await session.initialize()
        providers = session.coordinator.get("providers") or {}
        if set(providers) != {row["instance_id"] for row in plan["providers"]}:
            raise InferenceError("A configured provider did not mount; setup incomplete")
        resolver = session.coordinator.get_capability("model_role_resolver")
        priorities = [
            (row.get("config", {}).get("priority", 100), row["instance_id"])
            for row in plan["providers"]
        ]
        best = min(value for value, _ in priorities)
        defaults = [name for value, name in priorities if value == best]
        default = defaults[0] if len(defaults) == 1 else None
        selection, problem = None, None
        try:
            selection = await resolve_selection(providers, choice, resolver, default)
        except InferenceError as exc:
            problem = str(exc)
        if selection:
            emit(describe_selection(selection, choice, resolver, providers))
        else:
            emit("No model selected: " + problem)
        emit("Memory output limit: 4096 tokens; explicit thinking budgets are capped at 2048.")
        if choose is not None and selection:
            decision = choose(["Keep this selection", "Choose another provider/model"])
            if decision == 1:
                choose = None
            elif decision != 2:
                raise InferenceError("Model selection cancelled; setup incomplete")
        if choose is not None:
            options = []
            choices = []
            if selection:
                options.append(
                    "Keep automatic fast routing" if choice.inherits else "Keep existing selection"
                )
                choices.append(choice)
            # Offer automatic routing without changing an existing explicit choice.
            if not choice.inherits and resolver is not None:
                try:
                    automatic = await resolve_selection(providers, CallConfig(), resolver, default)
                except InferenceError:
                    pass
                else:
                    options.append(
                        "Use automatic fast routing: "
                        + automatic[0]
                        + " / "
                        + automatic[1]["model"]
                    )
                    choices.append(CallConfig())
            for account, provider in providers.items():
                try:
                    models = await provider.list_models()
                except Exception as exc:  # noqa: BLE001 - provider diagnostics can contain credentials
                    emit(f"Model list unavailable for {account} ({type(exc).__name__}).")
                    continue
                for model in models:
                    name = model if isinstance(model, str) else getattr(model, "id", None)
                    if not isinstance(name, str) or not name:
                        continue
                    options.append(f"{account} / {name}")
                    choices.append(CallConfig(provider=account, model=name))
            if not choices:
                raise InferenceError("No available model choices; check provider configuration")
            index = choose(options)
            if (
                isinstance(index, bool)
                or not isinstance(index, int)
                or not 1 <= index <= len(choices)
            ):
                raise InferenceError("Model selection cancelled; setup incomplete")
            selected_choice = choices[index - 1]
            selection = await resolve_selection(providers, selected_choice, resolver, default)
            if selected_choice != choice:
                save_choice(home, selected_choice)
                choice = selected_choice
            emit(describe_selection(selection, choice, resolver, providers))
        if selection is None:
            raise InferenceError(problem + "; run amplifier-memory setup --choose")
        selected, options, provider_options = selection
        receipt["selection"] = {
            "provider": selected,
            "model": options.get("model"),
            "role": choice.role if choice.inherits else None,
            "matrix": getattr(resolver, "name", None) if choice.inherits else None,
            "requestOptions": options,
            "providerOptions": provider_options,
        }
        # Cleanup is part of acceptance, before permitting timer startup.
    except (InferenceError, asyncio.CancelledError):
        raise
    except Exception as exc:  # noqa: BLE001 - provider diagnostics can contain credentials
        raise InferenceError(
            f"Model setup failed ({type(exc).__name__}); no completion made"
        ) from None
    finally:
        try:
            await session.cleanup()
        except Exception as exc:  # noqa: BLE001 - sanitize provider cleanup errors too
            raise InferenceError(
                f"Model cleanup failed ({type(exc).__name__}); setup incomplete"
            ) from None
    receipt.pop("selectionPending", None)
    runtime._write(root / "prepared.json", receipt)
    return "Ready. Run amplifier-memory service restart for an existing timer, or service install."


def describe_selection(selection, choice, resolver, providers):
    account, options, _ = selection
    model = options.get("model")
    if not model:
        info = providers[account].get_info()
        model = getattr(info, "defaults", {}).get("model") or "provider default (not reported)"
    policy = (
        f"{choice.role} via {getattr(resolver, 'name', 'configured routing')}"
        if choice.inherits
        else "explicit memory selection"
    )
    return (
        f"Memory model: {account} / {model} ({policy}). "
        "Fast routing is a curated recommendation, not a lowest-price guarantee."
    )


def save_choice(home, choice):
    """Change only the judge choice; shared settings and memories stay untouched."""
    from amplifier_foundation.settings import atomic_write

    config = load(home)
    if not config.usable:
        raise InferenceError("Memory configuration is invalid; fix it before selecting a model")
    path = config_path(home)
    if path.is_symlink():
        raise InferenceError("Memory configuration cannot be a symlink")
    payload = yaml.safe_load(path.read_text()) if path.exists() else {}
    payload = payload or {}
    payload.setdefault("llm", {})["judge"] = {
        "provider": choice.provider,
        "model": choice.model,
        "bundle": choice.bundle,
        "role": choice.role,
    }
    atomic_write(path, yaml.safe_dump(payload, sort_keys=False), private=True)
