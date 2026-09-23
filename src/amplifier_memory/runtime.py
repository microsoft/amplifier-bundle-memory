"""Explicit setup and private sessions for portable memory inference.

Foundation owns settings merging and module preparation. Core owns mount/cleanup.
Only setup activates sources; readiness and ordinary jobs cannot install anything.
"""

from __future__ import annotations

import asyncio
import copy
import hashlib
import importlib
import importlib.metadata
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path
from uuid import uuid4

from .inference import InferenceError, _credential_environment, _expand, complete_once
from .llm_config import CallConfig, load
from .store import store_home

PROVIDER_SOURCES = {
    f"provider-{name}": f"git+https://github.com/microsoft/amplifier-module-provider-{name}@main"
    for name in ("openai", "anthropic", "azure-openai", "gemini", "ollama")
}

BASE_SOURCES = {
    "loop-basic": "git+https://github.com/microsoft/amplifier-module-loop-basic@main",
    "context-simple": "git+https://github.com/microsoft/amplifier-module-context-simple@main",
}


def runtime_home(home=None):
    return store_home(home).resolve() / "runtime"


def _json(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"))


def _hash(value):
    return hashlib.sha256(value.encode()).hexdigest()


def _write(path, value):
    from amplifier_foundation.settings import atomic_write

    atomic_write(path, json.dumps(value, indent=2) + "\n", private=True)


def _private_root(home):
    if not load(home).enabled:
        raise InferenceError("Memory instance is disabled; no runtime written")
    root = runtime_home(home)
    if root.is_symlink():
        raise InferenceError("Memory runtime cannot be a symlink")
    root.mkdir(parents=True, exist_ok=True, mode=0o700)
    ignore = root / ".gitignore"
    if not ignore.exists():
        ignore.write_text("# Generated private job state; never memory or committed content.\n*\n")
    elif ignore.is_symlink() or "*" not in ignore.read_text().splitlines():
        raise InferenceError("Memory runtime has an incompatible ignore file; no job started")
    return root


def _versions():
    version = importlib.metadata.version("amplifier-core")
    if tuple(int(part) for part in version.split(".")[:3]) < (2, 0, 1):
        raise InferenceError("Memory runtime requires published amplifier-core >=2.0.1")
    packages = {}
    for distribution in importlib.metadata.distributions():
        name = distribution.metadata["Name"].lower().replace("_", "-")
        direct = distribution.read_text("direct_url.json") or ""
        packages[name] = {"version": distribution.version, "sourceHash": _hash(direct)}
    return {"packages": packages, "memoryCode": _tree(Path(__file__).parent)}


def _plan(paths, choice):
    from amplifier_foundation.settings import read_settings

    if choice.bundle:
        raise InferenceError(
            "Explicit bundle requires host-resolved inference; no account substituted"
        )
    settings = read_settings(paths)
    config = settings.get("config", {})
    if settings.get("modules") or settings.get("overrides"):
        raise InferenceError("These module overrides require host-resolved inference")
    overrides = settings.get("sources", {}).get("modules", {})
    if not isinstance(overrides, dict):
        raise InferenceError("Module sources must be a mapping")
    providers = []
    for original in config.get("providers", []):
        if not original.get("enabled", True):
            continue
        row = copy.deepcopy(original)
        row.pop("enabled", None)
        module = row.get("module", "")
        if not isinstance(module, str) or not re.fullmatch(r"provider-[a-z0-9][a-z0-9-]*", module):
            raise InferenceError("Invalid configured provider module")
        row["instance_id"] = row.pop("id", None) or row.get("instance_id") or module[9:]
        row["source"] = overrides.get(module) or row.get("source")
        if not row["source"]:
            row["source"] = PROVIDER_SOURCES.get(module)
            if not row["source"]:
                raise InferenceError("Custom provider needs an explicit source before setup")
        priority = row.get("config", {}).get("priority", 100)
        if isinstance(priority, bool) or not isinstance(priority, (int, float)):
            raise InferenceError("Provider priority must be numeric")
        providers.append(row)
    if not providers:
        raise InferenceError("No configured providers; configure a shared provider before setup")
    names = [row["instance_id"] for row in providers]
    if len(names) != len(set(names)):
        raise InferenceError("Duplicate configured provider account")
    if choice.provider and choice.provider not in names:
        raise InferenceError("Configured provider account is unavailable")
    hooks = [
        copy.deepcopy(row)
        for row in config.get("hooks", [])
        if row.get("module") == "hooks-routing" and row.get("enabled", True)
    ]
    for hook in hooks:
        hook.pop("enabled", None)
        hook["source"] = (
            overrides.get("hooks-routing")
            or hook.get("source")
            or (
                "git+https://github.com/microsoft/amplifier-bundle-routing-matrix@main"
                "#subdirectory=modules/hooks-routing"
            )
        )
    session = {
        key: {"module": module, "source": overrides.get(module) or source}
        for key, (module, source) in zip(("orchestrator", "context"), BASE_SOURCES.items())
    }
    session["metadata"] = {"visibility": "internal", "purpose": "memory.suggestion"}
    plan = {"session": session, "providers": providers, "hooks": hooks, "tools": [], "agents": {}}
    sources = {}
    for row in [*providers, *hooks, session["orchestrator"], session["context"]]:
        module, source = row["module"], row["source"]
        if not isinstance(source, str) or not source:
            raise InferenceError("Configured module source must be explicit")
        if module in sources and sources[module] != source:
            raise InferenceError(
                "One module cannot resolve to two different sources in one runtime"
            )
        sources[module] = source
    return plan, sources


def _owned(root, path):
    if not path.resolve().is_relative_to(root.resolve()):
        raise InferenceError("Memory runtime path escapes its private root")
    return path


def _tree(path):
    path = Path(path)
    return {
        str(p.relative_to(path)): hashlib.sha256(p.read_bytes()).hexdigest()
        for p in sorted(path.rglob("*"))
        if p.is_file()
        and not any(
            part in {".git", ".venv", "__pycache__", ".pytest_cache"} or part.endswith(".egg-info")
            for part in p.relative_to(path).parts
        )
        and p.suffix in {".py", ".toml", ".yaml", ".yml", ".json", ".md"}
    }


async def prepare(home=None, *, workspace=None, shared_home=None):
    """Explicit setup; sanitize activation/install errors that may contain secrets."""
    try:
        return await _prepare(home, workspace=workspace, shared_home=shared_home)
    except (InferenceError, asyncio.CancelledError):
        raise
    except Exception as exc:  # noqa: BLE001 - source URLs may contain credentials
        raise InferenceError(
            f"Memory setup failed ({type(exc).__name__}); no runtime activated"
        ) from None


async def _prepare(home=None, *, workspace=None, shared_home=None):
    """Prepare only providers, routing, basic loop and context."""
    from amplifier_foundation.bundle import Bundle
    from amplifier_foundation.paths.resolution import get_amplifier_home

    root = _private_root(home)
    _versions()
    shared = Path(shared_home or get_amplifier_home()).expanduser().resolve()
    workspace = Path(workspace or Path.cwd()).resolve()
    paths = [
        shared / "settings.yaml",
        workspace / ".amplifier/settings.yaml",
        workspace / ".amplifier/settings.local.yaml",
    ]
    choice = load(home).call()
    plan, sources = _plan(paths, choice)
    generation = _owned(root, root / "generations" / uuid4().hex)
    generation.mkdir(parents=True, mode=0o700)
    # Prevent a provider's Git dependency from rebuilding or downgrading the kernel.
    overrides = generation / "overrides.txt"
    overrides.write_text(f"amplifier-core=={importlib.metadata.version('amplifier-core')}\n")
    bundle = Bundle(
        name="memory-inference",
        version="1",
        session=plan["session"],
        providers=plan["providers"],
        hooks=plan["hooks"],
    )
    prepared = await bundle.prepare(cache_dir=generation / "cache", strict=True, install_deps=False)
    module_paths = {}
    for name in sources:
        selected = prepared.resolver.resolve(name).resolve()
        target = _owned(root, generation / "modules" / name)
        if any(p.is_symlink() for p in selected.rglob("*") if ".git" not in p.parts):
            raise InferenceError("Module source contains symlinks; use a self-contained source")
        # Local source policies are read-only inputs, too. Install only private copies.
        shutil.copytree(
            selected,
            target,
            ignore=shutil.ignore_patterns(
                ".git", ".venv", "node_modules", "__pycache__", "*.egg-info", ".pytest_cache"
            ),
        )
        module_paths[name] = str(target)
    # Installation is confined to this explicit setup surface, never inference.
    from uv import find_uv_bin

    argv = [
        find_uv_bin(),
        "pip",
        "install",
        "--python",
        sys.executable,
        "--no-sources",
        "--only-binary",
        "amplifier-core",
        "--default-index",
        "https://pypi.org/simple",
        "--cache-dir",
        str(generation / "uv-cache"),
        "--overrides",
        str(overrides),
    ]
    for path in sorted(set(module_paths.values())):
        argv.extend(["-e", path])
    installed = await asyncio.to_thread(subprocess.run, argv, capture_output=True, text=True)
    if installed.returncode:
        raise InferenceError("Provider setup dependency installation failed; no runtime activated")
    importlib.invalidate_caches()
    receipt = {
        "schema": 1,
        "python": sys.executable,
        "versions": _versions(),
        "settingsPaths": list(map(str, paths)),
        "sharedHome": str(shared),
        "configurationHash": _hash(_json(plan)),
        "sources": sources,
        "modulePaths": module_paths,
        "moduleHashes": {name: _tree(path) for name, path in module_paths.items()},
    }
    _write(generation / "prepared.json", receipt)
    _write(root / "prepared.json", receipt)
    return readiness(home)


def readiness(home=None):
    """Read-only and offline. Does not mount providers, import them or log in."""
    try:
        root = runtime_home(home)
        if root.is_symlink():
            raise InferenceError("Memory runtime cannot be a symlink")
        receipt = json.loads(_owned(root, root / "prepared.json").read_text())
        if Path(receipt["python"]).absolute() != Path(sys.executable).absolute():
            raise InferenceError(
                "Prepared runtime belongs to another Python environment; run setup"
            )
        if receipt["schema"] != 1 or receipt["versions"] != _versions():
            raise InferenceError("Runtime packages changed; run amplifier-memory setup")
        plan, sources = _plan(receipt["settingsPaths"], load(home).call())
        if _hash(_json(plan)) != receipt["configurationHash"] or sources != receipt["sources"]:
            raise InferenceError("Provider configuration changed; run amplifier-memory setup")
        for name, path in receipt["modulePaths"].items():
            _owned(root, Path(path))
            if not Path(path).is_dir() or _tree(path) != receipt["moduleHashes"][name]:
                raise InferenceError(
                    "Prepared module changed or disappeared; run amplifier-memory setup"
                )
        if set(sources) != set(receipt["modulePaths"]):
            raise InferenceError("Incomplete prepared runtime; run amplifier-memory setup")
        return receipt
    except InferenceError:
        raise
    except (OSError, ValueError, KeyError, importlib.metadata.PackageNotFoundError):
        raise InferenceError(
            "Memory inference is not prepared; run amplifier-memory setup"
        ) from None


async def complete(prompt, *, home=None, call: CallConfig | None = None):
    """One private session, one tool-free request, cleanup even on cancellation."""
    from amplifier_foundation.bundle import Bundle, BundleModuleResolver, PreparedBundle

    receipt = readiness(home)
    choice = call or load(home).call()
    plan, sources = _plan(receipt["settingsPaths"], choice)
    if sources != receipt["sources"]:
        raise InferenceError("Unprepared module source; run amplifier-memory setup")
    environment = _credential_environment(Path(receipt["sharedHome"]))
    plan = _expand(plan, environment)
    root = _private_root(home)
    job = _owned(root, root / "jobs" / uuid4().hex)
    job.mkdir(parents=True, mode=0o700)
    manifest = {
        "session_id": "memory-" + job.name,
        "visibility": "internal",
        "purpose": "memory.suggestion",
        "origin": "internal",
        "status": "starting",
    }
    _write(job / "metadata.json", manifest)
    session = None
    transcript = [{"role": "user", "content": prompt}]

    def observe(event):
        from amplifier_foundation.settings import atomic_write

        path = job / "events.jsonl"
        old = path.read_text() if path.exists() else ""
        atomic_write(path, old + _json(event) + "\n", private=True)

    try:
        prepared = PreparedBundle(
            mount_plan=plan,
            resolver=BundleModuleResolver({k: Path(v) for k, v in receipt["modulePaths"].items()}),
            bundle=Bundle(name="memory-inference", version="1"),
        )
        # Keep ownership before initialize: cleanup must also cover partial mount failures.
        from amplifier_core import AmplifierSession

        session = AmplifierSession(
            copy.deepcopy(prepared.mount_plan), session_id=manifest["session_id"]
        )
        await session.coordinator.mount("module-source-resolver", prepared.resolver)
        session.coordinator.register_capability("session.working_dir", str(job))
        await session.initialize()
        providers = session.coordinator.get("providers") or {}
        if set(providers) != {row["instance_id"] for row in plan["providers"]}:
            raise InferenceError(
                "A configured provider did not mount; no fallback account selected"
            )
        resolver = session.coordinator.get_capability("model_role_resolver")
        if plan["hooks"] and resolver is None:
            raise InferenceError("Configured routing did not mount")
        priorities = [
            (row.get("config", {}).get("priority", 100), row["instance_id"])
            for row in plan["providers"]
        ]
        best = min(priority for priority, _ in priorities)
        defaults = [name for priority, name in priorities if priority == best]
        result = await complete_once(
            prompt,
            providers=providers,
            call=choice,
            role_resolver=resolver,
            default_provider=defaults[0] if len(defaults) == 1 else None,
            observe=observe,
        )
        transcript.append({"role": "assistant", "content": result.text})
        manifest.update(
            status="completed", provider=result.provider, model=result.model, usage=result.usage
        )
        return result
    except asyncio.CancelledError:
        manifest["status"] = "cancelled"
        raise
    except Exception as exc:
        manifest.update(status="failed", errorType=type(exc).__name__)
        if isinstance(exc, InferenceError):
            raise
        raise InferenceError(f"Memory session failed ({type(exc).__name__})") from None
    finally:
        try:
            if session is not None:
                await session.cleanup()
        except Exception as exc:  # noqa: BLE001 - sanitize cleanup errors
            manifest.update(cleanupErrorType=type(exc).__name__)
            if manifest["status"] == "completed":
                manifest["status"] = "cleanup_failed"
                raise InferenceError(
                    f"Memory session cleanup failed ({type(exc).__name__})"
                ) from None
        finally:
            from amplifier_foundation.settings import atomic_write

            atomic_write(
                job / "transcript.jsonl",
                "".join(_json(row) + "\n" for row in transcript),
                private=True,
            )
            _write(job / "metadata.json", manifest)


def standalone_suggest(home=None):
    """Dedicated CLI-process boundary, never used by an embedding host.

    Providers may read implicit credential environment variables when mounting.
    Populate missing values in THIS standalone process from shared keys.env;
    caller-supplied environment wins. Async library/host entrypoints never do this.
    """
    import os

    from .suggest import run_suggest

    if load(home).enabled:
        try:
            receipt = readiness(home)
        except InferenceError:
            # Preserve run_suggest's bounded/degraded report when setup is missing.
            pass
        else:
            for name, value in _credential_environment(Path(receipt["sharedHome"])).items():
                os.environ.setdefault(name, value)
    return run_suggest(home)
