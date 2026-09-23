"""Synthetic providers only; no model, CLI, or saved conversation."""

import asyncio
import importlib.abc
import sys
from decimal import Decimal
from types import SimpleNamespace

import pytest

pytest.importorskip("amplifier_core")
pytest.importorskip("amplifier_foundation")

from amplifier_memory.inference import Completion, InferenceError, complete_installed, complete_once
from amplifier_memory.llm_config import CallConfig


@pytest.fixture(autouse=True)
def isolated_shared_home(monkeypatch, tmp_path):
    monkeypatch.setenv("AMPLIFIER_HOME", str(tmp_path / "shared"))


def response(text="[]", **kw):
    from amplifier_core.message_models import ChatResponse, TextBlock

    return ChatResponse(content=[TextBlock(text=text)], **kw)


class Provider:
    def __init__(self, reply=None, error=None):
        self.reply, self.error, self.requests, self.closed = reply, error, [], False

    async def complete(self, request):
        self.requests.append(request)
        if self.error:
            raise self.error
        return self.reply or response()

    async def close(self):
        self.closed = True


def test_role_auth_identity_and_one_tool_free_request():
    from amplifier_core.message_models import Usage

    provider = Provider(
        response(
            usage=Usage(
                input_tokens=20, output_tokens=3, total_tokens=23, cost_usd=Decimal("0.0003")
            ),
            model="actual-model",
        )
    )
    other, events = Provider(), []

    class Resolver:
        async def resolve(self, role):
            assert role == "fast"
            return [
                SimpleNamespace(
                    provider="b", model="fast-model", config={"reasoning_effort": "low"}
                )
            ]

    result = asyncio.run(
        complete_once(
            "synthetic facts",
            providers={"a": other, "b": provider},
            role_resolver=Resolver(),
            default_provider="a",
            observe=events.append,
        )
    )
    assert (
        isinstance(result, Completion) and result.provider == "b" and result.model == "actual-model"
    )
    assert result.usage["cost_usd"] == "0.0003"
    assert len(provider.requests) == 1 and other.requests == []
    req = provider.requests[0]
    assert req.model == "fast-model" and req.reasoning_effort == "low"
    assert req.tools == [] and req.tool_choice == "none" and req.timeout is None
    assert req.max_output_tokens == 4096 and req.conversation_id is None
    assert [e["status"] for e in events] == ["started", "completed"]
    assert not provider.closed and "synthetic facts" not in str(events)


def test_explicit_selection_avoids_role_and_preserves_unknown_usage():
    class Resolver:
        async def resolve(self, role):
            raise AssertionError("explicit provider must not reroute")

    provider = Provider()
    result = asyncio.run(
        complete_once(
            "facts",
            providers={"a": provider},
            call=CallConfig(provider="a", model="chosen"),
            role_resolver=Resolver(),
        )
    )
    assert provider.requests[0].model == "chosen" and result.usage is None


@pytest.mark.parametrize(
    "choice", [CallConfig(provider="missing"), CallConfig(bundle="custom"), CallConfig()]
)
def test_unresolved_selection_does_not_call(choice):
    providers = {"a": Provider(), "b": Provider()}
    with pytest.raises(InferenceError):
        asyncio.run(complete_once("facts", providers=providers, call=choice))
    assert not any(p.requests for p in providers.values())


def test_host_resolved_bundle():
    provider = Provider()
    asyncio.run(
        complete_once(
            "facts",
            providers={"a": provider},
            call=CallConfig(bundle="custom"),
            resolved_bundle="custom",
        )
    )
    assert len(provider.requests) == 1


@pytest.mark.parametrize("error", [RuntimeError("private-secret"), asyncio.CancelledError()])
def test_failure_cancel_attribution_and_no_retry(error):
    provider, events = Provider(error=error), []
    with pytest.raises((InferenceError, asyncio.CancelledError)) as caught:
        asyncio.run(complete_once("facts", providers={"a": provider}, observe=events.append))
    assert len(provider.requests) == 1 and not provider.closed
    assert "private-secret" not in str(caught.value) + str(events)
    assert events[-1]["status"] == (
        "cancelled" if isinstance(error, asyncio.CancelledError) else "failed"
    )


@pytest.mark.parametrize(
    "reply",
    [
        response(""),
        response("partial", finish_reason="length"),
        response("[]", tool_calls=[{"id": "call", "name": "exec", "arguments": {}}]),
    ],
)
def test_bad_reply_cannot_trigger_more_work(reply):
    provider = Provider(reply)
    with pytest.raises(InferenceError):
        asyncio.run(complete_once("facts", providers={"a": provider}))
    assert len(provider.requests) == 1


def installed_fixture(monkeypatch, config, error=None):
    import amplifier_foundation.settings

    calls, providers = [], []
    monkeypatch.setattr(
        amplifier_foundation.settings, "read_settings", lambda paths: {"config": config}
    )

    class Entry:
        def __init__(self, name):
            self.name = name
            self.dist = SimpleNamespace(read_text=lambda _: "{}")

        def load(self):
            async def mount(coordinator, config):
                module = self.name
                calls.append((module, config))
                if module == "hooks-routing":

                    class Resolver:
                        async def resolve(self, role):
                            assert role == "fast"
                            return [SimpleNamespace(provider="second", model="routed", config={})]

                    coordinator.register_capability("model_role_resolver", Resolver())
                    return None
                assert module == "provider-fixture"
                provider = Provider(error=error)
                providers.append(provider)
                await coordinator.mount("providers", provider, name="fixture")
                return provider.close

            return mount

    import amplifier_memory.inference

    monkeypatch.setattr(
        amplifier_memory.inference.importlib.metadata,
        "entry_points",
        lambda *, group, name: [Entry(name)],
    )
    return calls, providers


def test_installed_named_accounts_routing_auth_and_cleanup(monkeypatch):
    monkeypatch.setenv("FIXTURE_PROVIDER_KEY", "private-sentinel")
    calls, providers = installed_fixture(
        monkeypatch,
        {
            "providers": [
                {
                    "module": "provider-fixture",
                    "id": "first",
                    "config": {"api_key": "wrong", "priority": 20},
                },
                {
                    "module": "provider-fixture",
                    "id": "second",
                    "config": {"api_key": "${FIXTURE_PROVIDER_KEY}", "priority": 10},
                },
            ],
            "hooks": [{"module": "hooks-routing", "config": {}}, {"module": "hooks-logging"}],
        },
    )
    result = asyncio.run(complete_installed("facts"))
    assert result.provider == "second" and result.model == "routed"
    assert calls[1][1]["api_key"] == "private-sentinel"
    assert [name for name, _ in calls] == ["provider-fixture", "provider-fixture", "hooks-routing"]
    assert providers[0].requests == [] and len(providers[1].requests) == 1
    assert all(p.closed for p in providers) and "private-sentinel" not in repr(result)


@pytest.mark.parametrize("error", [RuntimeError("private-secret"), asyncio.CancelledError()])
def test_owned_cleanup_on_error_and_cancellation(monkeypatch, error):
    _, providers = installed_fixture(
        monkeypatch, {"providers": [{"module": "provider-fixture"}]}, error
    )
    with pytest.raises((InferenceError, asyncio.CancelledError)):
        asyncio.run(complete_installed("facts"))
    assert len(providers[0].requests) == 1 and providers[0].closed


def test_no_cli_or_subprocess_or_agent_session_or_history(monkeypatch, tmp_path):
    import shutil
    import subprocess

    import amplifier_core

    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("AMPLIFIER_HOME", str(tmp_path / "shared"))
    monkeypatch.setattr(shutil, "which", lambda _: None)

    def forbidden(*args, **kwargs):
        raise AssertionError("No CLI, subprocess or session allowed")

    monkeypatch.setattr(subprocess, "run", forbidden)
    monkeypatch.setattr(subprocess, "Popen", forbidden)
    monkeypatch.setattr(amplifier_core, "AmplifierSession", forbidden)
    _, providers = installed_fixture(monkeypatch, {"providers": [{"module": "provider-fixture"}]})

    class DenyCLI(importlib.abc.MetaPathFinder):
        def find_spec(self, fullname, path=None, target=None):
            if fullname.startswith("amplifier_app_cli"):
                forbidden()

    guard = DenyCLI()
    sys.meta_path.insert(0, guard)
    try:
        result = asyncio.run(complete_installed("facts"))
    finally:
        sys.meta_path.remove(guard)
    assert result.text == "[]" and providers[0].closed
    assert not list(tmp_path.rglob("transcript.jsonl")) and not list(
        tmp_path.rglob("metadata.json")
    )


def test_explicit_bundle_refused_before_loading(monkeypatch):
    def forbidden(*a, **kw):
        raise AssertionError("Runtime should not load")

    import amplifier_core

    monkeypatch.setattr(amplifier_core, "ModuleCoordinator", forbidden)
    with pytest.raises(InferenceError, match="host-resolved inference"):
        asyncio.run(complete_installed("facts", call=CallConfig(bundle="custom")))


def test_shared_key_file_is_materialized_without_environment_mutation(monkeypatch, tmp_path):
    import os

    shared = tmp_path / "shared"
    shared.mkdir()
    (shared / "keys.env").write_text('export FIXTURE_KEY="private fixture key"\n')
    monkeypatch.delenv("FIXTURE_KEY", raising=False)
    calls, _ = installed_fixture(
        monkeypatch,
        {"providers": [{"module": "provider-fixture", "config": {"api_key": "${FIXTURE_KEY}"}}]},
    )
    asyncio.run(complete_installed("facts"))
    assert calls[0][1]["api_key"] == "private fixture key"
    assert "FIXTURE_KEY" not in os.environ


def test_mismatched_installed_source_fails_without_mount_or_request(monkeypatch):
    calls, providers = installed_fixture(
        monkeypatch,
        {
            "providers": [
                {"module": "provider-fixture", "source": "git+https://example.invalid/other@main"}
            ]
        },
    )
    with pytest.raises(InferenceError, match="differs from installed"):
        asyncio.run(complete_installed("facts"))
    assert calls == [] and providers == []


def test_missing_entrypoint_cannot_fall_back_to_install_or_filesystem(monkeypatch):
    import amplifier_memory.inference

    calls, _ = installed_fixture(monkeypatch, {"providers": [{"module": "provider-fixture"}]})
    monkeypatch.setattr(
        amplifier_memory.inference.importlib.metadata, "entry_points", lambda **kw: []
    )
    with pytest.raises(InferenceError, match="no installation attempted"):
        asyncio.run(complete_installed("facts"))
    assert calls == []


def test_source_overrides_are_not_silently_ignored(monkeypatch):
    import amplifier_foundation.settings

    calls, _ = installed_fixture(monkeypatch, {})
    monkeypatch.setattr(
        amplifier_foundation.settings,
        "read_settings",
        lambda paths: {
            "config": {"providers": [{"module": "provider-fixture"}]},
            "sources": {"modules": {"provider-fixture": "git+https://example.invalid/other@main"}},
        },
    )
    with pytest.raises(InferenceError, match="source overrides"):
        asyncio.run(complete_installed("facts"))
    assert calls == []


def test_empty_role_resolution_never_silently_uses_expensive_default():
    provider = Provider()

    class Resolver:
        async def resolve(self, role):
            return []

    with pytest.raises(InferenceError, match="no available provider"):
        asyncio.run(
            complete_once(
                "facts", providers={"a": provider}, default_provider="a", role_resolver=Resolver()
            )
        )
    assert provider.requests == []


@pytest.mark.parametrize(
    "requested, installed, accepted",
    [
        ("main", "main", True),
        ("other", "main", False),
        ("a" * 40, "a" * 40, True),
        ("a" * 40, "b" * 40, False),
    ],
)
def test_configured_source_ref_must_match_installed_receipt(
    monkeypatch, requested, installed, accepted
):
    import json

    from amplifier_memory.inference import _require_installed_source

    entry = SimpleNamespace(
        dist=SimpleNamespace(
            read_text=lambda _: json.dumps(
                {
                    "url": "https://example.invalid/provider",
                    "vcs_info": {"requested_revision": installed, "commit_id": installed},
                    "subdirectory": "module",
                }
            )
        )
    )
    monkeypatch.setattr(
        "amplifier_memory.inference.importlib.metadata.entry_points", lambda **kw: [entry]
    )
    source = f"git+https://example.invalid/provider.git@{requested}#subdirectory=module"
    if accepted:
        assert _require_installed_source("provider-fixture", source) is entry
    else:
        with pytest.raises(InferenceError, match="host resolution required"):
            _require_installed_source("provider-fixture", source)


def test_role_resolution_error_is_safe_and_does_not_call_default():
    provider = Provider()

    class Resolver:
        async def resolve(self, role):
            raise RuntimeError("secret provider URL")

    with pytest.raises(InferenceError, match="Model-role resolution failed") as exc:
        asyncio.run(complete_once("facts", providers={"a": provider}, role_resolver=Resolver()))
    assert "secret" not in str(exc.value) and provider.requests == []


def test_configured_routing_without_resolver_does_not_select_default(monkeypatch):
    from amplifier_core import ModuleCoordinator

    _, providers = installed_fixture(
        monkeypatch,
        {"providers": [{"module": "provider-fixture"}], "hooks": [{"module": "hooks-routing"}]},
    )
    monkeypatch.setattr(ModuleCoordinator, "get_capability", lambda *a, **kw: None)
    with pytest.raises(InferenceError, match="did not provide"):
        asyncio.run(complete_installed("facts"))
    assert providers[0].requests == [] and providers[0].closed


def test_output_budget_is_capped_and_unsupported_routing_fails():
    provider = Provider()

    class Resolver:
        def __init__(self):
            self.config = {"max_output_tokens": 10000}

        async def resolve(self, role):
            return [SimpleNamespace(provider="a", model="chosen", config=self.config)]

    resolver = Resolver()
    asyncio.run(complete_once("facts", providers={"a": provider}, role_resolver=resolver))
    assert provider.requests[0].max_output_tokens == 4096
    resolver.config = {"extra_request_params": {"unknown": 1}}
    with pytest.raises(InferenceError, match="unsupported inference options"):
        asyncio.run(complete_once("facts", providers={"a": provider}, role_resolver=resolver))
    assert len(provider.requests) == 1
