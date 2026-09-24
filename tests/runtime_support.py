"""Synthetic source packages mounted by real Core, with no provider network."""

import sys
from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4

import yaml

from amplifier_memory import runtime
from amplifier_memory.llm_config import load

PROVIDER = """import asyncio
from amplifier_core.message_models import ChatResponse, TextBlock, Usage
__amplifier_module_type__ = "provider"
mounted, calls, closed = [], [], []
started = asyncio.Event()
class Provider:
 name = "fixture"
 def __init__(self, config): self.config = config
 def get_info(self):
  from amplifier_core import ProviderInfo
  return ProviderInfo(id=self.name, display_name="Fixture", credential_env_vars=[], defaults={"model":self.config["default_model"]}, capabilities=[])
 async def list_models(self): return []
 def parse_tool_calls(self, response): return []
 async def complete(self, request, **kwargs):
  calls.append((self.config, request))
  assert request.tools == [] and request.tool_choice == "none" and request.timeout is None
  prompt = str(request.messages[0].content)
  if prompt == "FAIL": raise RuntimeError("private-error-body")
  if prompt == "WAIT":
   started.set()
   await asyncio.Event().wait()
  return ChatResponse(content=[TextBlock(text=self.config["reply"])], model=request.model or self.config["default_model"], usage=Usage(input_tokens=33, output_tokens=9, total_tokens=42))
async def mount(coordinator, config):
 mounted.append(config)
 await coordinator.mount("providers", Provider(config), name="fixture")
 async def cleanup(): closed.append(config["account"])
 return cleanup
"""
HOOK = """from types import SimpleNamespace
__amplifier_module_type__ = "hook"
class Resolver:
 async def resolve(self, role):
  assert role == "fast"
  return [SimpleNamespace(provider="account-b", model="role-model", config={"reasoning_effort":"low"})]
async def mount(coordinator, config):
 coordinator.register_capability("model_role_resolver", Resolver())
"""
LOOP = """__amplifier_module_type__ = "orchestrator"
class Loop:
 async def execute(self, prompt, context, providers, tools, hooks): raise AssertionError("No agent loop allowed")
async def mount(coordinator, config): await coordinator.mount("orchestrator", Loop())
"""
CONTEXT = """__amplifier_module_type__ = "context"
class Context:
 async def add_message(self, message): pass
 async def get_messages_for_request(self): return []
 async def get_messages(self): return []
 async def set_messages(self, messages): pass
 async def clear(self): pass
async def mount(coordinator, config): await coordinator.mount("context", Context())
"""


def make_runtime(tmp_path, monkeypatch, *, home=None, reply="[]"):
    home = home or tmp_path / "memory"
    shared = tmp_path / "shared"
    shared.mkdir(exist_ok=True)
    workspace = tmp_path / "workspace"
    (workspace / ".amplifier").mkdir(parents=True, exist_ok=True)
    (workspace / "AGENTS.md").write_text("MUST NOT BE INCLUDED IN INFERENCE")
    monkeypatch.setenv("AMPLIFIER_HOME", str(shared))
    monkeypatch.setenv("FIXTURE_KEY", "process-key")
    (shared / "keys.env").write_text("FIXTURE_KEY=file-key\n")
    root = runtime._private_root(home)
    paths = {}
    provider_package = None
    for name, code in [
        ("provider-fixture", PROVIDER),
        ("hooks-routing", HOOK),
        ("loop-basic", LOOP),
        ("context-simple", CONTEXT),
    ]:
        path = root / "generations" / uuid4().hex / name
        package = "amplifier_module_" + name.replace("-", "_") + "_" + uuid4().hex[:8]
        package_path = path / package
        package_path.mkdir(parents=True)
        (package_path / "__init__.py").write_text(code)
        (path / "pyproject.toml").write_text(
            f'[project]\nname="amplifier-module-{name}"\nversion="0.0.0"\ndependencies=[]\n[project.entry-points."amplifier.modules"]\n{name}="{package}:mount"\n'
        )
        paths[name] = str(path)
        if name == "provider-fixture":
            provider_package = package
    rows = [
        {
            "id": account,
            "module": "provider-fixture",
            "source": Path(paths["provider-fixture"]).as_uri(),
            "config": {
                "account": account,
                "default_model": "shared-model",
                "api_key": "${FIXTURE_KEY}",
                "token_file_path": str(shared / (account + ".json")),
                "reply": reply,
            },
        }
        for account in ["account-a", "account-b"]
    ]
    settings = {
        "config": {
            "providers": rows,
            "hooks": [{"module": "hooks-routing", "source": Path(paths["hooks-routing"]).as_uri()}],
        },
        "sources": {
            "modules": {
                name: Path(paths[name]).as_uri() for name in ["loop-basic", "context-simple"]
            }
        },
    }
    (shared / "settings.yaml").write_text(yaml.safe_dump(settings))
    (workspace / ".amplifier/settings.yaml").write_text(
        yaml.safe_dump(
            {
                "config": {
                    "providers": [
                        {
                            "id": "account-a",
                            "module": "provider-fixture",
                            "config": {"default_model": "workspace-model"},
                        }
                    ]
                }
            }
        )
    )
    (workspace / ".amplifier/settings.local.yaml").write_text(
        yaml.safe_dump(
            {
                "config": {
                    "providers": [
                        {
                            "id": "account-a",
                            "module": "provider-fixture",
                            "config": {"default_model": "local-model"},
                        }
                    ]
                }
            }
        )
    )
    settings_paths = [
        str(shared / "settings.yaml"),
        str(workspace / ".amplifier/settings.yaml"),
        str(workspace / ".amplifier/settings.local.yaml"),
    ]
    plan, sources = runtime._plan(settings_paths, load(home).call())
    receipt = {
        "schema": 1,
        "python": sys.executable,
        "versions": runtime._versions(),
        "settingsPaths": settings_paths,
        "sharedHome": str(shared),
        "configurationHash": runtime._hash(runtime._json(plan)),
        "sources": sources,
        "modulePaths": paths,
        "moduleHashes": {name: runtime._tree(path) for name, path in paths.items()},
    }
    runtime._write(root / "prepared.json", receipt)

    class Fixture(SimpleNamespace):
        @property
        def module(self):
            return sys.modules[provider_package]

    return Fixture(
        home=home, shared=shared, workspace=workspace, receipt=receipt, package=provider_package
    )
