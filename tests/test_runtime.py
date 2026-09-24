"""Private inference runtime; no real provider or shared data."""

import asyncio
import json
import subprocess

import pytest

from amplifier_memory import runtime
from amplifier_memory.inference import InferenceError
from amplifier_memory.llm_config import CallConfig


def test_actual_core_mount_routing_accounts_and_private_cleanup(private_runtime):
    fixture = private_runtime()
    original = (fixture.shared / "settings.yaml").read_bytes()
    result = asyncio.run(runtime.complete("synthetic facts", home=fixture.home))
    assert (result.provider, result.model) == ("account-b", "role-model")
    assert sorted(fixture.module.closed) == sorted(row["account"] for row in fixture.module.mounted)
    mounted = {row["account"]: row for row in fixture.module.mounted}
    assert mounted["account-a"]["default_model"] == "local-model"
    assert mounted["account-b"]["api_key"] == "process-key"
    assert mounted["account-b"]["token_file_path"] == str(fixture.shared / "account-b.json")
    assert (fixture.shared / "settings.yaml").read_bytes() == original
    assert not list(fixture.shared.rglob("transcript.jsonl"))
    job = next((fixture.home / "runtime/jobs").iterdir())
    meta = json.loads((job / "metadata.json").read_text())
    assert (meta["visibility"], meta["purpose"], meta["status"]) == (
        "internal",
        "memory.suggestion",
        "completed",
    )
    assert meta["usage"]["total_tokens"] == 42
    assert "process-key" not in (job / "metadata.json").read_text()
    assert "MUST NOT" not in (job / "transcript.jsonl").read_text()


def test_explicit_account_overrides_role(private_runtime):
    f = private_runtime()
    result = asyncio.run(
        runtime.complete(
            "facts", home=f.home, call=CallConfig(provider="account-a", model="explicit")
        )
    )
    assert (result.provider, result.model) == ("account-a", "explicit")
    assert len(f.module.calls) == 1


def test_interactive_tool_and_context_settings_do_not_block_private_jobs(private_runtime):
    import yaml

    f = private_runtime()
    path = f.shared / "settings.yaml"
    settings = yaml.safe_load(path.read_text())
    settings["modules"] = {"tools": [{"module": "tool-filesystem", "config": {"write": False}}]}
    settings["overrides"] = {
        "tool-computer-use": {"config": {"fixture": "not loaded"}},
        "hook-context-intelligence": {"config": {"fixture": "not loaded"}},
        "context-simple": {"config": {"fixture": "not inherited"}},
    }
    path.write_text(yaml.safe_dump(settings))
    original = path.read_bytes()
    # These unrelated settings do not change the existing prepared provider plan.
    runtime.readiness(f.home)
    result = asyncio.run(runtime.complete("synthetic facts", home=f.home))
    assert (result.provider, result.model) == ("account-b", "role-model")
    assert path.read_bytes() == original
    assert not list(f.shared.rglob("transcript.jsonl"))
    job = next((f.home / "runtime/jobs").iterdir())
    assert json.loads((job / "metadata.json").read_text())["visibility"] == "internal"
    plan, _ = runtime._plan(f.receipt["settingsPaths"], CallConfig())
    assert plan["tools"] == []
    assert "config" not in plan["session"]["context"]
    assert [row["module"] for row in plan["hooks"]] == ["hooks-routing"]


@pytest.mark.parametrize("override", ["provider-fixture", "account-a", "hooks-routing", "unknown"])
def test_relevant_or_unknown_overrides_still_require_host(private_runtime, override):
    import yaml

    f = private_runtime()
    path = f.shared / "settings.yaml"
    settings = yaml.safe_load(path.read_text())
    settings["overrides"] = {override: {"config": {"fixture": True}}}
    path.write_text(yaml.safe_dump(settings))
    with pytest.raises(InferenceError, match="host-resolved"):
        asyncio.run(runtime.complete("facts", home=f.home))
    assert not (f.home / "runtime/jobs").exists()
    assert f.package not in __import__("sys").modules


@pytest.mark.parametrize(
    "identity",
    [
        {"module": "provider-tool-account"},
        {"module": "provider-fixture", "instance_id": "tool-account"},
    ],
)
def test_provider_account_with_interactive_prefix_is_not_ignored(private_runtime, identity):
    import yaml

    f = private_runtime()
    path = f.shared / "settings.yaml"
    settings = yaml.safe_load(path.read_text())
    settings["config"]["providers"] = [identity]
    settings["overrides"] = {"tool-account": {"config": {"default_model": "changed"}}}
    path.write_text(yaml.safe_dump(settings))
    with pytest.raises(InferenceError, match="host-resolved"):
        runtime.readiness(f.home)
    assert not (f.home / "runtime/jobs").exists()


@pytest.mark.parametrize(
    "modules",
    [
        {"providers": [{"module": "provider-fixture"}]},
        {"hooks": [{"module": "hooks-routing"}]},
        {"tools": [{"module": "provider-fixture"}]},
        {"tools": "invalid"},
    ],
)
def test_legacy_provider_composition_is_not_silently_ignored(private_runtime, modules):
    import yaml

    f = private_runtime()
    path = f.shared / "settings.yaml"
    settings = yaml.safe_load(path.read_text())
    settings["modules"] = modules
    path.write_text(yaml.safe_dump(settings))
    with pytest.raises(InferenceError, match="host-resolved"):
        runtime.readiness(f.home)
    assert not (f.home / "runtime/jobs").exists()


@pytest.mark.parametrize("cancel", [False, True])
def test_failure_and_cancel_cleanup(private_runtime, cancel):
    f = private_runtime()

    async def run():
        if not cancel:
            with pytest.raises(InferenceError, match="RuntimeError") as exc:
                await runtime.complete("FAIL", home=f.home)
            assert "private-error-body" not in str(exc.value)
            return
        task = asyncio.create_task(runtime.complete("WAIT", home=f.home))
        # The provider starts after mounting; wait without a completion deadline.
        while f.package not in __import__("sys").modules:
            if task.done():
                await task
            await asyncio.sleep(0)
        await f.module.started.wait()
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task

    asyncio.run(run())
    assert sorted(f.module.closed) == sorted(row["account"] for row in f.module.mounted)
    meta = json.loads(next((f.home / "runtime/jobs").glob("*/metadata.json")).read_text())
    assert meta["status"] == ("cancelled" if cancel else "failed")


def test_readiness_offline_no_mount_or_install(private_runtime, monkeypatch):
    f = private_runtime()

    def forbidden(*a, **kw):
        raise AssertionError("No subprocess")

    monkeypatch.setattr(subprocess, "run", forbidden)
    assert runtime.readiness(f.home)["sources"] == f.receipt["sources"]
    assert f.package not in __import__("sys").modules
    (f.shared / "settings.yaml").write_text("config: {}\n")
    with pytest.raises(InferenceError):
        runtime.readiness(f.home)


def test_changed_source_ref_and_bytes_reject(private_runtime):
    f = private_runtime()
    source = next(
        __import__("pathlib").Path(f.receipt["modulePaths"]["provider-fixture"]).rglob("*.py")
    )
    source.write_text(source.read_text() + "\n# changed\n")
    with pytest.raises(InferenceError, match="changed or disappeared"):
        asyncio.run(runtime.complete("facts", home=f.home))
    assert not (f.home / "runtime/jobs").exists()


def test_unprepared_never_installs(memory_home, monkeypatch):
    monkeypatch.setattr(subprocess, "run", lambda *a, **kw: pytest.fail("hidden install"))
    with pytest.raises(InferenceError, match="setup"):
        asyncio.run(runtime.complete("facts", home=memory_home))
    assert not (memory_home / "runtime/jobs").exists()


def test_timer_install_and_start_require_readiness(memory_home, tmp_path):
    from amplifier_memory import service

    calls = []
    runner = lambda argv: calls.append(argv) or (0, "")
    unit_dir = tmp_path / "units"
    blocked = service.install(
        home=memory_home,
        config_dir=unit_dir,
        executable="/bin/amplifier-memory",
        platform="systemd",
        runner=runner,
    )
    assert not blocked.ok and "setup" in blocked.render()
    assert calls == [] and not unit_dir.exists()


def test_timer_ready_renders_without_provider_mount(private_runtime, tmp_path):
    from amplifier_memory import service

    f = private_runtime()
    calls = []
    result = service.install(
        home=f.home,
        config_dir=tmp_path / "units",
        executable="/bin/amplifier-memory",
        platform="systemd",
        runner=lambda argv: calls.append(argv) or (0, ""),
    )
    assert result.ok and calls
    assert f.package not in __import__("sys").modules


def test_job_is_not_reingested_or_git_committed(private_runtime, store):
    from amplifier_memory.suggest import read_session

    private_runtime(home=store)
    before = subprocess.check_output(["git", "-C", str(store), "status", "--porcelain"])
    asyncio.run(runtime.complete("facts", home=store))
    after = subprocess.check_output(["git", "-C", str(store), "status", "--porcelain"])
    assert before == after == b""
    job = next((store / "runtime/jobs").iterdir())
    assert read_session(job) is None


def test_runtime_symlink_does_not_write_elsewhere(memory_home, tmp_path):
    memory_home.mkdir()
    elsewhere = tmp_path / "elsewhere"
    elsewhere.mkdir()
    (memory_home / "runtime").symlink_to(elsewhere, target_is_directory=True)
    with pytest.raises(InferenceError):
        runtime._private_root(memory_home)
    assert not list(elsewhere.iterdir())


@pytest.mark.parametrize("existing", [True, False])
def test_runtime_ignore_symlink_never_writes_target(memory_home, tmp_path, existing):
    root = memory_home / "runtime"
    root.mkdir(parents=True)
    target = tmp_path / "outside-ignore"
    if existing:
        target.write_text("original")
    (root / ".gitignore").symlink_to(target)
    with pytest.raises(InferenceError, match="cannot be a symlink"):
        runtime._private_root(memory_home)
    assert target.exists() == existing
    if existing:
        assert target.read_text() == "original"


def test_bundle_include_only_routing_fails_before_setup_or_request(private_runtime, monkeypatch):
    import yaml

    f = private_runtime()
    settings_path = f.shared / "settings.yaml"
    settings = yaml.safe_load(settings_path.read_text())
    settings["config"].pop("hooks")
    settings["config"]["providers"] = settings["config"]["providers"][:1]
    settings["bundle"] = {"active": "work"}
    settings["includes"] = ["routing-matrix"]
    settings_path.write_text(yaml.safe_dump(settings))
    monkeypatch.setattr(subprocess, "run", lambda *a, **kw: pytest.fail("No setup or install"))
    with pytest.raises(InferenceError, match="bundle includes are not composed"):
        asyncio.run(runtime.complete("facts", home=f.home))
    assert f.package not in __import__("sys").modules
    assert not (f.home / "runtime/jobs").exists()
    # Explicit selection does not claim to inherit unavailable bundle routing.
    plan, _ = runtime._plan(f.receipt["settingsPaths"], CallConfig(provider="account-a"))
    assert plan["hooks"] == []


def test_custom_source_required_and_unsupported_bundle_fail(private_runtime):
    f = private_runtime()
    with pytest.raises(InferenceError, match="host-resolved"):
        asyncio.run(runtime.complete("facts", home=f.home, call=CallConfig(bundle="custom")))
    settings = __import__("yaml").safe_load((f.shared / "settings.yaml").read_text())
    for provider in settings["config"]["providers"]:
        provider.pop("source")
    (f.shared / "settings.yaml").write_text(__import__("yaml").safe_dump(settings))
    with pytest.raises(InferenceError, match="explicit source"):
        runtime.readiness(f.home)


def test_disabled_instance_setup_and_call_leave_no_jobs(private_runtime):
    f = private_runtime()
    (f.home / "config.yaml").write_text("enabled: false\n")
    with pytest.raises(InferenceError, match="disabled"):
        asyncio.run(runtime.prepare(f.home, shared_home=f.shared, workspace=f.workspace))
    with pytest.raises(InferenceError, match="disabled"):
        asyncio.run(runtime.complete("facts", home=f.home))
    assert not (f.home / "runtime/jobs").exists()


def test_default_update_never_invokes_or_discovers_another_cli(monkeypatch, store):
    from amplifier_memory import update

    calls = []
    monkeypatch.setattr("amplifier_memory.runtime.readiness", lambda home=None: {})
    monkeypatch.setattr(
        __import__("importlib").import_module("amplifier_memory.doctor"),
        "amplifier_env_python",
        lambda: pytest.fail("CLI discovery"),
    )
    result = update.run_update(
        home=store,
        runner=lambda argv: calls.append(argv) or (0, ""),
        timer_installed=False,
        installed_commit_fn=lambda: "unchanged",
        doctor_fn=lambda: __import__("amplifier_memory").doctor(
            store, installed_sha=None, remote_sha=None
        ),
    )
    assert calls == [("uv", "tool", "upgrade", "amplifier-memory")]
    assert result.exit_code == 0


def test_standalone_credential_boundary_only_populates_missing_values(private_runtime, monkeypatch):
    import importlib
    import os

    f = private_runtime()
    (f.shared / "keys.env").write_text("FIXTURE_KEY=file-key\nMEMORY_TEST_ONLY=file-only\n")
    monkeypatch.delenv("MEMORY_TEST_ONLY", raising=False)
    seen = []
    monkeypatch.setattr(
        importlib.import_module("amplifier_memory.suggest"),
        "run_suggest",
        lambda home: seen.append(dict(os.environ)),
    )
    before = dict(os.environ)
    runtime.standalone_suggest(f.home)
    assert seen[0]["FIXTURE_KEY"] == "process-key"
    assert seen[0]["MEMORY_TEST_ONLY"] == "file-only"
    assert all(seen[0][key] == value for key, value in before.items())
    os.environ.pop("MEMORY_TEST_ONLY")


def test_library_inference_never_changes_credential_environment(private_runtime, monkeypatch):
    import os

    f = private_runtime()
    (f.shared / "keys.env").write_text("FIXTURE_KEY=file-key\nMEMORY_TEST_ONLY=file-only\n")
    monkeypatch.delenv("MEMORY_TEST_ONLY", raising=False)
    before = dict(os.environ)
    asyncio.run(runtime.complete("facts", home=f.home))
    assert dict(os.environ) == before


def test_cleanup_failure_is_safe_and_recorded(private_runtime, monkeypatch):
    import amplifier_core

    real = amplifier_core.AmplifierSession

    class Session:
        def __init__(self, *a, **kw):
            self.real = real(*a, **kw)

        @property
        def coordinator(self):
            return self.real.coordinator

        async def initialize(self):
            return await self.real.initialize()

        async def cleanup(self):
            await self.real.cleanup()
            raise RuntimeError("private-cleanup-secret")

    monkeypatch.setattr(amplifier_core, "AmplifierSession", Session)
    f = private_runtime()
    with pytest.raises(InferenceError, match="cleanup failed") as exc:
        asyncio.run(runtime.complete("facts", home=f.home))
    assert "private-cleanup-secret" not in str(exc.value)
    meta = json.loads(next((f.home / "runtime/jobs").glob("*/metadata.json")).read_text())
    assert meta["status"] == "cleanup_failed" and meta["cleanupErrorType"] == "RuntimeError"
    assert sorted(f.module.closed) == sorted(row["account"] for row in f.module.mounted)


def test_failed_explicit_setup_preserves_selected_receipt(private_runtime, monkeypatch):
    from pathlib import Path
    from types import SimpleNamespace

    from amplifier_foundation.bundle import Bundle, BundleModuleResolver

    f = private_runtime()
    selected = f.home / "runtime/prepared.json"
    before = selected.read_bytes()

    async def prepared(self, **kwargs):
        assert kwargs["strict"] is True and kwargs["install_deps"] is False
        return SimpleNamespace(
            resolver=BundleModuleResolver(
                {name: Path(path) for name, path in f.receipt["modulePaths"].items()}
            )
        )

    monkeypatch.setattr(Bundle, "prepare", prepared)
    argv = []

    def fail(command, **kwargs):
        argv.append(command)
        return SimpleNamespace(returncode=1, stderr="private-install-error")

    monkeypatch.setattr(subprocess, "run", fail)
    with pytest.raises(InferenceError, match="installation failed") as exc:
        asyncio.run(runtime.prepare(f.home, workspace=f.workspace, shared_home=f.shared))
    assert selected.read_bytes() == before and len(argv) == 1
    assert "--only-binary" in argv[0] and "amplifier-core" in argv[0]
    assert "private-install-error" not in str(exc.value)
