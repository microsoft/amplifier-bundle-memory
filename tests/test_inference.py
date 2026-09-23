"""Synthetic providers only; no model, CLI, or saved conversation."""

import asyncio
from decimal import Decimal
from types import SimpleNamespace

import pytest

pytest.importorskip("amplifier_core")
pytest.importorskip("amplifier_foundation")

from amplifier_memory.inference import Completion, InferenceError, complete_once
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
    assert result.model_source == "response" and events[-1]["modelSource"] == "response"
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
    assert result.model == "chosen" and result.model_source == "request"


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
        asyncio.run(
            complete_once(
                "facts",
                providers={"a": provider},
                call=CallConfig(provider="a"),
                observe=events.append,
            )
        )
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
        asyncio.run(
            complete_once("facts", providers={"a": provider}, call=CallConfig(provider="a"))
        )
    assert len(provider.requests) == 1


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


def test_missing_role_resolver_never_silently_uses_unique_default():
    provider = Provider()
    with pytest.raises(InferenceError, match="no prepared resolver"):
        asyncio.run(complete_once("facts", providers={"a": provider}, default_provider="a"))
    assert provider.requests == []


def test_no_role_default_remains_supported_and_sdk_model_is_unknown():
    provider = Provider()
    provider.get_info = lambda: SimpleNamespace(defaults={"model": "declared-default"})
    result = asyncio.run(
        complete_once("facts", providers={"a": provider}, call=CallConfig(role=""))
    )
    assert len(provider.requests) == 1 and provider.requests[0].model is None
    assert result.model is None and result.model_source is None


def test_role_resolution_error_is_safe_and_does_not_call_default():
    provider = Provider()

    class Resolver:
        async def resolve(self, role):
            raise RuntimeError("secret provider URL")

    with pytest.raises(InferenceError, match="Model-role resolution failed") as exc:
        asyncio.run(complete_once("facts", providers={"a": provider}, role_resolver=Resolver()))
    assert "secret" not in str(exc.value) and provider.requests == []


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
