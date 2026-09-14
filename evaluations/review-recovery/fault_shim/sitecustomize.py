"""Opt-in import-time installer for one synthetic native rationale process."""

from __future__ import annotations

import importlib
from pathlib import Path

from rationale_faults import FaultSpec, install, register_exit_status

SPEC = FaultSpec.from_env()
STATUS = None
TOOL = None
INSTALLED_EXECUTE = None
if SPEC is not None:
    TOOL = importlib.import_module("amplifier_module_tool_memory")
    inbox = importlib.import_module("amplifier_memory.inbox")
    STATUS = install(TOOL, inbox, SPEC, shim_source=Path(__file__))
    INSTALLED_EXECUTE = TOOL.MemoryTool.execute
    register_exit_status(STATUS, Path(SPEC.telemetry))