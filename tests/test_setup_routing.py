"""Setup uses real Core lifecycle with isolated settings and synthetic providers."""

from pathlib import Path

import pytest
import yaml
from click.testing import CliRunner

from amplifier_memory import runtime
from amplifier_memory.cli import main
from amplifier_memory.inference import InferenceError, request_options
from amplifier_memory.llm_config import CallConfig, load
from amplifier_memory.setup import setup_inference


def test_routing_settings_sources_and_custom_matrix_are_preserved(private_runtime):
    f = private_runtime()
    path = f.shared / "settings.yaml"
    settings = yaml.safe_load(path.read_text())
    settings["config"].pop("hooks")
    settings["sources"]["bundles"] = {"routing-matrix": "git+https://example.invalid/fork@main"}
    settings["routing"] = {"matrix": "economy", "overrides": {"fast": "custom"}}
    settings["overrides"] = {
        "hooks-routing": {"config": {"default_matrix": "quality", "placement": "inject"}}
    }
    (f.shared / "routing").mkdir()
    path.write_text(yaml.safe_dump(settings))
    original = path.read_bytes()
    plan, _ = runtime._plan(f.receipt["settingsPaths"], CallConfig())
    hook = plan["hooks"][0]
    assert (
        hook["source"] == "git+https://example.invalid/fork@main#subdirectory=modules/hooks-routing"
    )
    assert hook["config"] == {
        "default_matrix": "economy",
        "overrides": {"fast": "custom"},
        "placement": "inject",
        "custom_routing_dirs": [str(f.shared / "routing")],
    }
    assert path.read_bytes() == original


def test_disabled_routing_is_not_reenabled(private_runtime):
    f = private_runtime()
    path = f.shared / "settings.yaml"
    settings = yaml.safe_load(path.read_text())
    settings["config"]["hooks"][0]["enabled"] = False
    path.write_text(yaml.safe_dump(settings))
    plan, _ = runtime._plan(f.receipt["settingsPaths"], CallConfig())
    assert plan["hooks"] == []


def test_routing_assets_are_private_and_checked(private_runtime):
    f = private_runtime()
    source = f.shared / "routing"
    source.mkdir()
    (source / "mine.yaml").write_text("roles: {}\n")
    target = runtime.runtime_home(f.home) / "generations/data/routing"
    runtime._copy_routing_assets(source, target)
    receipt = dict(f.receipt)
    current, _ = runtime._plan(receipt["settingsPaths"], CallConfig())
    receipt["configurationHash"] = runtime._hash(runtime._json(current))
    receipt["assetHashes"] = {str(target): runtime._tree(target)}
    receipt["assetInputs"] = {str(source): {"path": str(target), "hashes": runtime._tree(source)}}
    runtime._write(runtime.runtime_home(f.home) / "prepared.json", receipt)
    plan = {"hooks": [{"config": {"custom_routing_dirs": [str(source)]}}]}
    runtime._private_routing_paths(plan, receipt)
    assert plan["hooks"][0]["config"]["custom_routing_dirs"] == [str(target)]
    runtime.readiness(f.home)
    (source / "mine.yaml").write_text("roles: {fast: []}\n")
    with pytest.raises(InferenceError, match="Custom routing changed"):
        runtime.readiness(f.home)
    (source / "mine.yaml").write_text("roles: {}\n")
    (target / "mine.yaml").unlink()
    with pytest.raises(InferenceError, match="Prepared routing data changed"):
        runtime.readiness(f.home)


def test_provider_options_preserve_intent_inside_memory_budget():
    request, provider = request_options({"model": "haiku", "thinking_budget_tokens": 32000})
    assert request == {"model": "haiku", "max_output_tokens": 4096}
    assert provider == {
        "model": "haiku",
        "extended_thinking": True,
        "thinking_budget_tokens": 2048,
        "thinking_budget_buffer": 2048,
    }
    request, provider = request_options(
        {"model": "flash", "extra_request_params": {"thinking_config": {"thinking_level": "low"}}}
    )
    assert request["reasoning_effort"] == "low" and provider == {"model": "flash"}
    for unsafe in (
        {"extra_request_params": {"tools": []}},
        {"thinking_budget_tokens": True},
        {"thinking_budget_tokens": 32000, "max_output_tokens": 1024},
        {
            "reasoning_effort": "high",
            "extra_request_params": {"thinking_config": {"thinking_level": "low"}},
        },
    ):
        with pytest.raises(InferenceError):
            request_options(unsafe)


def prepared_fixture(private_runtime, monkeypatch):
    f = private_runtime()

    async def prepare(*args, **kwargs):
        return dict(f.receipt)

    monkeypatch.setattr(runtime, "prepare", prepare)
    return f


def test_setup_preview_no_completion_or_shared_history(private_runtime, monkeypatch):
    f = prepared_fixture(private_runtime, monkeypatch)
    original = (f.shared / "settings.yaml").read_bytes()
    output = []
    result = setup_inference(f.home, emit=output.append)
    assert "Ready" in result and "account-b / role-model" in output[0]
    assert f.module.calls == [] and set(f.module.closed) == {"account-a", "account-b"}
    assert not (f.home / "runtime/jobs").exists()
    assert not list(f.shared.rglob("transcript.jsonl"))
    assert (f.shared / "settings.yaml").read_bytes() == original
    assert runtime.readiness(f.home)["selection"]["role"] == "fast"
    assert not (f.home / "config.yaml").exists()


def test_setup_keeps_existing_explicit_choice(private_runtime, monkeypatch):
    f = prepared_fixture(private_runtime, monkeypatch)
    path = f.home / "config.yaml"
    path.write_text(
        "enabled: true\nllm:\n  judge:\n    provider: account-a\n    model: own-model\n"
    )
    original = path.read_bytes()
    setup_inference(f.home, emit=lambda _: None, choose=lambda options: 1)
    assert path.read_bytes() == original
    assert runtime.readiness(f.home)["selection"]["model"] == "own-model"
    assert f.module.calls == []


def test_picker_changes_only_memory_choice(private_runtime, monkeypatch):
    f = prepared_fixture(private_runtime, monkeypatch)

    # The synthetic module is imported by Core; list_models is independent of complete.
    async def choose_catalog(self):
        return ["cheap-model", "premium-model"]

    # Mount once without completing, then patch the reusable test provider class.
    setup_inference(f.home, emit=lambda _: None)
    monkeypatch.setattr(f.module.Provider, "list_models", choose_catalog)
    (f.home / "config.yaml").write_text("enabled: true\n")
    settings = (f.shared / "settings.yaml").read_bytes()
    decisions = iter([2, 2])  # Change; then account-a / cheap-model after Keep automatic.
    setup_inference(f.home, emit=lambda _: None, choose=lambda options: next(decisions))
    assert load(f.home).call().provider == "account-a"
    assert load(f.home).call().model == "cheap-model"
    assert yaml.safe_load((f.home / "config.yaml").read_text())["enabled"] is True
    assert (f.shared / "settings.yaml").read_bytes() == settings
    assert f.module.calls == []


def test_unresolved_role_blocks_timer_readiness(private_runtime, monkeypatch):
    f = prepared_fixture(private_runtime, monkeypatch)
    hook = next(Path(f.receipt["modulePaths"]["hooks-routing"]).rglob("__init__.py"))
    hook.write_text(
        hook.read_text().replace(
            'assert role == "fast"', 'raise RuntimeError("fixture unavailable")'
        )
    )
    with pytest.raises(InferenceError, match="setup --choose"):
        setup_inference(f.home, emit=lambda _: None)
    with pytest.raises(InferenceError, match="selection is incomplete"):
        runtime.readiness(f.home)
    assert f.module.calls == [] and set(f.module.closed) == {"account-a", "account-b"}


def test_setup_cli_choose_and_help(monkeypatch):
    import amplifier_memory

    seen = []
    monkeypatch.setattr(
        amplifier_memory, "setup_inference", lambda *a, **kw: seen.append(kw) or "Ready"
    )
    result = CliRunner().invoke(main, ["setup", "--choose", "--workspace", "/tmp"])
    assert result.exit_code == 0, result.output
    assert callable(seen[0]["choose"]) and seen[0]["workspace"] == "/tmp"
    assert "--choose" in CliRunner().invoke(main, ["setup", "--help"]).output


def test_unresolved_role_can_choose_without_expensive_default(private_runtime, monkeypatch):
    f = prepared_fixture(private_runtime, monkeypatch)
    hook = next(Path(f.receipt["modulePaths"]["hooks-routing"]).rglob("__init__.py"))
    hook.write_text(
        hook.read_text().replace('assert role == "fast"', 'raise RuntimeError("no route")')
    )
    provider = next(Path(f.receipt["modulePaths"]["provider-fixture"]).rglob("__init__.py"))
    provider.write_text(
        provider.read_text().replace(
            "async def list_models(self): return []",
            'async def list_models(self): return ["cheap-model"]',
        )
    )
    f.receipt["moduleHashes"] = {
        name: runtime._tree(path) for name, path in f.receipt["modulePaths"].items()
    }
    setup_inference(f.home, emit=lambda _: None, choose=lambda options: 1)
    assert load(f.home).call() == CallConfig(provider="account-a", model="cheap-model")
    assert runtime.readiness(f.home)["selection"]["role"] is None
    assert f.module.calls == []


def test_cleanup_failure_is_sanitized_and_keeps_setup_pending(private_runtime, monkeypatch):
    f = prepared_fixture(private_runtime, monkeypatch)
    from amplifier_core import AmplifierSession

    cleanup = AmplifierSession.cleanup

    async def failed_cleanup(self):
        await cleanup(self)
        raise RuntimeError("private-secret")

    monkeypatch.setattr(AmplifierSession, "cleanup", failed_cleanup)
    with pytest.raises(InferenceError, match="cleanup failed") as caught:
        setup_inference(f.home, emit=lambda _: None)
    assert "private-secret" not in str(caught.value)
    with pytest.raises(InferenceError, match="selection is incomplete"):
        runtime.readiness(f.home)
    assert f.module.calls == []
