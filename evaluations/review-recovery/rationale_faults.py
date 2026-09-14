"""Narrow, auditable faults for the bounded native rationale evaluator.

The shim never invents a tool result, receipt, session id, or execution trace.
It only forwards a deliberately altered argument to the *loaded* MemoryTool,
then writes separate JSONL telemetry for the evaluator to inspect.
"""

from __future__ import annotations

import asyncio
import atexit
import base64
import contextvars
import hashlib
import json
import os
import subprocess
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

_READBACK_ACTIVE: contextvars.ContextVar[bool] = contextvars.ContextVar(
    "native_rationale_readback_active", default=False
)


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _hash(value: Any) -> str:
    return hashlib.sha256(
        json.dumps(value, ensure_ascii=True, sort_keys=True, default=str).encode("utf-8")
    ).hexdigest()


def _utf8_bytes(value: object) -> int | None:
    if not isinstance(value, str):
        return 0
    try:
        return len(value.encode("utf-8"))
    except UnicodeEncodeError:
        return None


def _git(home: Path, *args: str) -> str | None:
    try:
        return subprocess.check_output(
            ["git", "-C", str(home), *args], text=True, stderr=subprocess.DEVNULL
        ).strip()
    except (OSError, subprocess.CalledProcessError):
        return None


def _transition(home: Path, stable_id: str) -> dict[str, Any]:
    """Record facts needed to prove a readback error happened after a real commit."""

    return {
        "head": _git(home, "rev-parse", "HEAD"),
        "inbox_sha256": _sha(home / "inbox.md") if (home / "inbox.md").is_file() else None,
        "declined_sha256": _sha(home / "declined.md") if (home / "declined.md").is_file() else None,
        "stable_id_in_inbox": stable_id in (home / "inbox.md").read_text(encoding="utf-8"),
        "stable_id": stable_id,
    }


def _append(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(value, ensure_ascii=True, sort_keys=True) + "\n")


@dataclass(frozen=True)
class FaultSpec:
    """The exact synthetic-store-only instrumentation boundary."""

    home: Path
    stable_id: str
    ordinal: int
    kind: str
    telemetry: Path

    @classmethod
    def from_env(cls) -> FaultSpec | None:
        encoded = os.environ.get("NATIVE_RATIONALE_FAULT_SPEC")
        if not encoded or os.environ.get("NATIVE_RATIONALE_SYNTHETIC") != "1":
            return None
        try:
            value = json.loads(base64.urlsafe_b64decode(encoded.encode("ascii")).decode("utf-8"))
            spec = cls(
                home=Path(value["home"]).resolve(),
                stable_id=str(value["stable_id"]),
                ordinal=int(value["ordinal"]),
                kind=str(value["kind"]),
                telemetry=Path(value["telemetry"]).resolve(),
            )
        except (KeyError, TypeError, ValueError, UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise RuntimeError("invalid NATIVE_RATIONALE_FAULT_SPEC") from exc
        if (
            not spec.home.is_absolute()
            or not spec.telemetry.is_absolute()
            or spec.ordinal < 1
            or spec.kind not in {"noop", "invalid-utf8", "overlong", "unverified", "readback"}
            or ".release-verification" not in spec.home.parts
        ):
            raise RuntimeError("unsafe NATIVE_RATIONALE_FAULT_SPEC")
        return spec


def _fault_reason(kind: str) -> str:
    if kind == "invalid-utf8":
        return "\ud800"
    if kind == "overlong":
        return "é" * 1001
    if kind == "unverified":
        return "__native_reason_not_in_any_typed_human_turn__"
    raise AssertionError(f"{kind} does not replace a reason")


def install(
    tool_module: Any,
    inbox_module: Any,
    spec: FaultSpec,
    *,
    shim_source: Path | None = None,
) -> Callable[[], dict[str, Any]]:
    """Wrap the object imported by the module loader and return its live status."""

    tool_class = getattr(tool_module, "MemoryTool", None)
    original = getattr(tool_class, "execute", None)
    if tool_class is None or not asyncio.iscoroutinefunction(original):
        raise RuntimeError("fault shim could not find async MemoryTool.execute")
    if getattr(original, "__native_rationale_fault_wrapper__", False):
        raise RuntimeError("fault shim refuses duplicate MemoryTool.execute wrapper")
    original_committed = getattr(inbox_module, "_committed", None)
    if spec.kind == "readback" and not callable(original_committed):
        raise RuntimeError("fault shim could not find inbox._committed")

    fingerprints = {
        "shim_source": str(shim_source.resolve()) if shim_source is not None else None,
        "shim_source_sha256": _sha(shim_source.resolve()) if shim_source is not None else None,
        "tool_module": str(Path(tool_module.__file__).resolve()),
        "tool_module_sha256": _sha(Path(tool_module.__file__).resolve()),
        "library_module": str(Path(inbox_module.__file__).resolve()),
        "library_module_sha256": _sha(Path(inbox_module.__file__).resolve()),
        "original_execute_module": getattr(original, "__module__", None),
        "original_execute_qualname": getattr(original, "__qualname__", None),
        "original_callable_identity": (
            f"{getattr(original, '__module__', None)}:{getattr(original, '__qualname__', None)}:{id(original)}"
        ),
    }
    state: dict[str, Any] = {
        "all_declines": 0,
        "activation_count": 0,
        "matched": False,
        "readback_count": 0,
        "wrong_id_at_ordinal": False,
        "duplicate_or_unused": False,
        "fingerprints": fingerprints,
    }

    async def wrapped(self: Any, input: dict[str, Any]) -> Any:
        original_args = dict(input or {})
        forwarded = dict(original_args)
        home = Path(self.home()).resolve()
        is_decline = (
            home == spec.home
            and original_args.get("operation") == "review"
            and original_args.get("action") == "decline"
        )
        if is_decline:
            state["all_declines"] += 1
        at_scheduled_ordinal = is_decline and state["all_declines"] == spec.ordinal
        id_matches = original_args.get("id") == spec.stable_id
        if at_scheduled_ordinal and not id_matches:
            state["wrong_id_at_ordinal"] = True
            _append(
                spec.telemetry,
                {
                    "event": "wrong-id-at-ordinal",
                    "home": str(home),
                    "all_decline_ordinal": state["all_declines"],
                    "expected_stable_id": spec.stable_id,
                    "original_args": original_args,
                },
            )
            raise RuntimeError("fault shim saw wrong stable id at scheduled decline ordinal")
        matched = bool(at_scheduled_ordinal and id_matches)
        if is_decline and state["all_declines"] > spec.ordinal:
            state["duplicate_or_unused"] = True
        if matched:
            if state["matched"]:
                state["duplicate_or_unused"] = True
                raise RuntimeError("fault shim saw duplicate scheduled decline")
            state["matched"] = True
            state["activation_count"] += 1
            if spec.kind not in {"noop", "readback"}:
                forwarded["reason"] = _fault_reason(spec.kind)

        injected_reason = forwarded.get("reason")
        before = _transition(home, spec.stable_id) if matched and spec.kind == "readback" else None
        if before is not None:
            state["readback_before"] = before
        token = _READBACK_ACTIVE.set(bool(matched and spec.kind == "readback"))
        try:
            result = await original(self, forwarded)
        except BaseException as exc:
            _append(
                spec.telemetry,
                {
                    "event": "tool-result",
                    "activation": matched,
                    "all_decline_ordinal": state["all_declines"],
                    "before_transition": before,
                    "error": type(exc).__name__,
                    "forwarded_args": forwarded,
                    "forwarded_sha256": _hash(forwarded),
                    "home": str(home),
                    "injected_reason": injected_reason if matched else None,
                    "injected_reason_utf8_bytes": _utf8_bytes(injected_reason),
                    "injected_reason_absent_from_human_provenance": (
                        matched and spec.kind == "unverified"
                    ),
                    "kind": spec.kind,
                    "original_args": original_args,
                    "original_sha256": _hash(original_args),
                    "stable_id": spec.stable_id,
                },
            )
            raise
        finally:
            _READBACK_ACTIVE.reset(token)
        _append(
            spec.telemetry,
            {
                "event": "tool-result",
                "activation": matched,
                "all_decline_ordinal": state["all_declines"],
                "before_transition": before,
                "forwarded_args": forwarded,
                "forwarded_sha256": _hash(forwarded),
                "home": str(home),
                "injected_reason": injected_reason if matched else None,
                "injected_reason_utf8_bytes": _utf8_bytes(injected_reason),
                "injected_reason_absent_from_human_provenance": (
                    matched and spec.kind == "unverified"
                ),
                "kind": spec.kind,
                "original_args": original_args,
                "original_sha256": _hash(original_args),
                "stable_id": spec.stable_id,
            },
        )
        return result

    wrapped.__native_rationale_fault_wrapper__ = True  # type: ignore[attr-defined]
    tool_class.execute = wrapped
    fingerprints["effective_execute_module"] = wrapped.__module__
    fingerprints["effective_execute_qualname"] = wrapped.__qualname__
    fingerprints["current_callable_identity"] = (
        f"{wrapped.__module__}:{wrapped.__qualname__}:{id(wrapped)}"
    )
    fingerprints["effective_wrapper"] = bool(
        getattr(tool_class.execute, "__native_rationale_fault_wrapper__", False)
    )

    if spec.kind == "readback":

        def committed(home: Path, target: str) -> str | None:
            value = original_committed(home, target)
            if _READBACK_ACTIVE.get() and Path(home).resolve() == spec.home and target == "declined.md":
                after = _transition(spec.home, spec.stable_id)
                commits = (
                    _git(spec.home, "rev-list", "--count", f"{state['readback_before']['head']}..{after['head']}")
                    if state.get("readback_before", {}).get("head") and after.get("head")
                    else None
                )
                state["readback_count"] += 1
                _append(
                    spec.telemetry,
                    {
                        "event": "committed-decline-readback",
                        "before": state.get("readback_before"),
                        "after": after,
                        "commit_count": commits,
                        "commit_parent": _git(spec.home, "rev-parse", "HEAD^"),
                        "changed_paths": (
                            (_git(spec.home, "diff-tree", "--no-commit-id", "--name-only", "-r", "HEAD") or "")
                            .splitlines()
                        ),
                        "committed_declined": value,
                        "committed_declined_sha256": hashlib.sha256(
                            (value or "").encode("utf-8")
                        ).hexdigest(),
                    },
                )
                raise OSError("injected committed-decline readback failure")
            return value

        inbox_module._committed = committed

    def status() -> dict[str, Any]:
        return {
            **state,
            "effective_object_is_wrapper": tool_class.execute is wrapped,
            "readback_before": state.get("readback_before"),
        }
    return status


def register_exit_status(status: Callable[[], dict[str, Any]], telemetry: Path) -> None:
    """Persist final activation/fingerprint proof even when the CLI returns normally."""

    atexit.register(lambda: _append(telemetry, {"event": "shim-status", **status()}))