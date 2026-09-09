"""Regression coverage for optional slash-command completion artifacts."""

from __future__ import annotations

import json
import re
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
MEMORY_SKILL = ROOT / "skills" / "memory" / "SKILL.md"
REMEMBER_SKILL = ROOT / "skills" / "remember" / "SKILL.md"


def _frontmatter(path: Path) -> dict[str, object]:
    """Read only a skill's YAML frontmatter."""
    _, frontmatter, _ = path.read_text(encoding="utf-8").split("---", 2)
    return yaml.safe_load(frontmatter)


def test_memory_completion_sidecar_matches_dispatch_and_help() -> None:
    """Advertised words remain real /memory commands, not a second command model."""
    skill = MEMORY_SKILL.read_text(encoding="utf-8")
    metadata = _frontmatter(MEMORY_SKILL)
    sidecar_path = MEMORY_SKILL.with_name("completions.json")
    sidecar = json.loads(sidecar_path.read_bytes().decode("utf-8"))

    assert metadata["argument-hint"] == "[list|review|forget|edit|remember|help] [arguments]"
    assert metadata["metadata"] == {"amplifier.completions": "completions.json"}
    assert sidecar == {
        "version": 1,
        "arguments": [
            {
                "after": [],
                "values": ["list", "review", "forget", "edit", "remember", "help"],
            },
            {"after": ["review"], "values": ["accept", "decline", "skip"]},
        ],
    }

    dispatch = skill.split("## Dispatch", 1)[1].split("\nOne call", 1)[0]
    dispatch_words = set(re.findall(r"\| `([a-z]+)(?: [^`]*)?` \|", dispatch))
    review_actions = set(re.findall(r"\| `review ([a-z]+) s-042`", dispatch))
    help_section = skill.split("## Help", 1)[1]
    help_words = set(re.findall(r"\| `/memory ([a-z]+)(?: [^`]*)?` \|", help_section))

    assert set(sidecar["arguments"][0]["values"]) == dispatch_words == help_words
    assert set(sidecar["arguments"][1]["values"]) == review_actions
    assert '| empty | `memory(operation="overview")` |' in dispatch


def test_remember_completion_hint_remains_free_form() -> None:
    """The /remember hint describes text without inventing fixed choices."""
    metadata = _frontmatter(REMEMBER_SKILL)
    skill = REMEMBER_SKILL.read_text(encoding="utf-8")

    assert metadata["argument-hint"] == "<text>"
    assert "metadata" not in metadata
    assert (
        'memory(operation="save", text="$ARGUMENTS", quote="$ARGUMENTS", writer="human")' in skill
    )


def test_review_skill_allows_clear_page_references_and_one_id_per_tool_call() -> None:
    """Conversational batches stay narrow without restoring the old literal-id contradiction."""
    skill = MEMORY_SKILL.read_text(encoding="utf-8")

    assert "never decline an id that was not named" not in skill
    assert "Do not act on more than one memory per invocation." not in skill
    assert "cannot clearly resolve from the displayed page" in skill
    assert "one stable id in a tool call" in skill
    assert "one tool call per resolved id" in skill
