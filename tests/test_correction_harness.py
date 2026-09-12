"""Provider-free tests for the bounded natural-memory correction evaluator."""

import asyncio
import importlib.util
import sys
from pathlib import Path

RUNNER = Path(__file__).resolve().parents[1] / "evaluations/review-recovery/corrections.py"
SPEC = importlib.util.spec_from_file_location("memory_correction_probe", RUNNER)
module = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
sys.modules[SPEC.name] = module
SPEC.loader.exec_module(module)


def call(arguments, *, success=True, output="receipt", name="memory"):
    """Synthetic grader input; runtime evidence must use TraceCall.from_tool_result()."""
    return module.TraceCall(
        name=name,
        arguments=arguments,
        result=type("ToolResult", (), {"success": success, "output": output})(),
        _result_token=module._TRACE_RESULT_TOKEN,
    )


def test_trace_factory_rejects_a_harness_shaped_result():
    try:
        module.TraceCall.from_tool_result("memory", {"operation": "list"}, object())
    except TypeError as exc:
        assert "actual ToolResult" in str(exc)
    else:
        raise AssertionError("a non-ToolResult must not become evaluator evidence")


def existing_proof(replacement):
    after_memory = (
        b"- [m-003] Use ISO dates in logs.\n"
        + b"- [m-008] Keep dependency changes focused.\n"
        + f"- [m-014] {replacement}\n".encode()
    )
    unrelated = {
        "m-003": b"- [m-003] Use ISO dates in logs.\n",
        "m-008": b"- [m-008] Keep dependency changes focused.\n",
    }
    return {"MEMORY.md": after_memory.decode(), "HEAD": "after"}, after_memory, unrelated


def grade_existing(calls, replacement, correction, *, last_commit=None, after=None):
    proof, after_memory, unrelated = existing_proof(replacement)
    if after is not None:
        proof = after
    return module.grade_existing_correction(
        calls=calls,
        final="```\n" + calls[-1].result.output + "\n```",
        correction=correction,
        old="old catalog wording",
        after=proof,
        fresh_readback="**3 memories**\n- **m-014** " + replacement,
        last_commit=last_commit
        or f"action: edit\nwriter: assistant\nquote: {module.json.dumps(correction)}\n",
        after_memory=after_memory,
        unrelated_before=unrelated,
    )


def test_existing_correction_grade_requires_complete_trace_and_committed_provenance():
    correction = "Please remove the catalog-specific scope and apply this to any document."
    replacement = "When changing any document, clearly state which records you intend to touch and why."
    calls = [
        call({"operation": "list"}, output="**3 memories**\n- **m-014** old catalog wording"),
        call(
            {
                "operation": "edit",
                "id": "m-014",
                "text": replacement,
                "quote": correction,
                "writer": "assistant",
            },
            output='edited m-014 — was: "old catalog wording"\n  now: ' + replacement,
        ),
    ]
    checks = grade_existing(calls, replacement, correction)

    assert all(checks.values()), checks

    mislabeled = [calls[0], call({**calls[1].arguments, "writer": "human"}, output=calls[1].result.output)]
    normalized = grade_existing(mislabeled, replacement, correction)
    assert normalized["derived_text_call_is_assistant_authored"] is False
    assert not all(normalized.values()), normalized

    edit = calls[-1].arguments
    negatives = {
        "extra list": calls + [call({"operation": "list"})],
        "skip": calls + [call({"operation": "review", "action": "skip", "id": "s-001"})],
        "save": calls + [call({"operation": "save", "text": "Unrelated.", "quote": "Unrelated."})],
        "accept": calls + [call({"operation": "review", "action": "accept", "id": "s-001"})],
        "decline": calls + [call({"operation": "review", "action": "decline", "id": "s-001"})],
        "other tool": calls + [call({"operation": "list"}, name="other")],
        "repeated edit": calls + [call(edit)],
        "refused edit": [calls[0], call(edit, success=False)],
        "wrong id": [calls[0], call({**edit, "id": "m-015"})],
    }
    for label, bad_calls in negatives.items():
        bad = grade_existing(bad_calls, replacement, correction)
        assert not all(bad.values()), label

    # Incoming arguments alone do not prove provenance: inspect the real commit body.
    for stored in (
        f"action: edit\nwriter: human\nquote: {module.json.dumps(correction)}\n",
        f"action: edit\nwriter: assistant\nquote: {module.json.dumps(replacement)}\n",
    ):
        bad = grade_existing(calls, replacement, correction, last_commit=stored)
        assert bad["stored_provenance_is_actual_commit"] is False

    mismatched, _, _ = existing_proof(replacement)
    mismatched["MEMORY.md"] = mismatched["MEMORY.md"].replace(replacement, "a different rewrite")
    assert not all(grade_existing(calls, replacement, correction, after=mismatched).values())


def test_pending_correction_grade_requires_revise_only_then_one_corrected_accept():
    before_memory = (
        "- [m-003] Use ISO dates in logs.\n- [m-008] Keep dependency changes focused.\n"
    )
    source = (
        f'- [s-001] {module.OLD}\n  quote: "{module.PENDING_SOURCE_QUOTE}"  '
        "session: synthetic-pending-correction  2026-09-12\n"
    )
    before = {"MEMORY.md": before_memory, "inbox.md": source, "declined.md": "", "HEAD": "before"}
    before_bytes = {name: value.encode() for name, value in before.items() if name != "HEAD"}
    initial = call({"operation": "review", "action": "list"}, output="**1. s-001** — original")
    correction = "Please revise the pending suggestion."
    replacement = "Corrected document wording."
    accepted = call(
        {
            "operation": "review",
            "action": "accept",
            "id": "s-001",
            "text": replacement,
            "quote": correction,
        },
        output="corrected s-001 → saved as m-009",
    )
    final = "```\ncorrected s-001 → saved as m-009\n```"
    after_memory = (before_memory + f"- [m-009] {replacement}\n").encode()
    after = {
        "MEMORY.md": after_memory.decode(),
        "inbox.md": "",
        "declined.md": "",
        "HEAD": "after",
    }
    commit = (
        f'quote: {module.json.dumps(correction)}\nsession: synthetic-natural-correction\n'
        "writer: assistant\naction: corrected-accept\n"
        "source-suggestion-id: s-001\n"
        f"source-suggestion-quote: {module.json.dumps(module.PENDING_SOURCE_QUOTE)}\n"
        "source-suggestion-session: synthetic-pending-correction\n"
    )

    def grade(calls, **changes):
        return module.grade_pending_correction(
            calls=calls,
            proposal=f"s-001\n{correction}\nproposed corrected text",
            final=final,
            correction=correction,
            before=before,
            after_revise=changes.pop("after_revise", before),
            after=changes.pop("after", after),
            before_bytes=before_bytes,
            after_revise_bytes=changes.pop("after_revise_bytes", before_bytes),
            after_memory=changes.pop("after_memory", after_memory),
            calls_before_approval=changes.pop("calls_before_approval", 1),
            before_commit_count=changes.pop("before_commit_count", 4),
            after_commit_count=changes.pop("after_commit_count", 5),
            last_commit=changes.pop("last_commit", commit),
            fresh_readback=changes.pop("fresh_readback", replacement),
        )

    good = grade([initial, accepted])
    assert all(good.values()), good

    for action in (
        {"operation": "list"},
        {"operation": "review", "action": "skip", "id": "s-001"},
        {"operation": "save", "text": "Unrelated.", "quote": "Unrelated."},
        {"operation": "review", "action": "decline", "id": "s-001"},
    ):
        bad = grade([initial, accepted, call(action)])
        assert not all(bad.values()), action

    wrong_states = (
        {"after_revise": {**before, "HEAD": "mutated"}},
        {"after_revise_bytes": {**before_bytes, "MEMORY.md": b"preapproval write\n"}},
        {"calls_before_approval": 2},
        {"last_commit": commit.replace(module.PENDING_SOURCE_QUOTE, "wrong source quote")},
        {"last_commit": commit.replace("synthetic-pending-correction", "wrong source session")},
        {"after_memory": after_memory.replace(b"m-009", b"m-010")},
        {"after_memory": after_memory + b"- [m-010] extra memory\n"},
        {"after": {**after, "MEMORY.md": after["MEMORY.md"] + module.OLD}},
        {"after_commit_count": 6},
    )
    for changes in wrong_states:
        assert not all(grade([initial, accepted], **changes).values()), changes


def test_fresh_synthetic_context_is_empty_and_cannot_observe_old_history_mutations():
    original = module.SyntheticContext([{"role": "user", "content": "old history"}])
    fresh = module.SyntheticContext()
    original.append({"role": "user", "content": "later mutation"})

    assert asyncio.run(original.get_messages()) == [
        {"role": "user", "content": "old history"},
        {"role": "user", "content": "later mutation"},
    ]
    assert asyncio.run(fresh.get_messages()) == []


def test_fixture_target_is_last_and_pending_original_is_not_active():
    for case in ("existing", "compound"):
        lines = module.fixture_memory(case).splitlines()
        assert len(lines) == 3
        assert lines[-1] == f"- [m-014] {module.OLD}"
    pending = module.fixture_memory("pending")
    assert module.OLD not in pending
    assert "m-014" not in pending
    assert all("heading" not in text.lower() for text in module.UNRELATED_MEMORIES.values())


def test_compound_grade_requires_the_success_then_refusal_in_one_ordered_fence():
    saved = "saved m-015 — /memory forget m-015 to undo.\n  Keep headings."
    refusal = "refused: the memory write could not be completed; see /tmp/error.log"
    calls = [
        call({"operation": "save", "text": "Keep headings.", "quote": "Keep headings."}, output=saved),
        call(
            {"operation": "edit", "id": "m-014", "text": "replacement"},
            success=False,
            output=refusal,
        ),
    ]
    after_memory = (
        b"- [m-003] Use ISO dates in logs.\n"
        + b"- [m-008] Keep dependency changes focused.\n"
        + f"- [m-014] {module.OLD}\n".encode()
        + b"- [m-015] Keep headings.\n"
    )
    unrelated = {
        "m-003": b"- [m-003] Use ISO dates in logs.\n",
        "m-008": b"- [m-008] Keep dependency changes focused.\n",
    }
    after = {"MEMORY.md": after_memory.decode(), "head": "two"}
    checks = module.grade_compound_outcome(
        calls=calls,
        final=f"```\n{saved}\n{refusal}\n```",
        before={"head": "one"},
        after=after,
        after_memory=after_memory,
        unrelated_before=unrelated,
    )
    assert all(checks.values()), checks
    wrong_sequence = [calls[0], call({"operation": "edit", "id": "m-013"}, success=False, output=refusal)]
    assert not all(
        module.grade_compound_outcome(
            calls=wrong_sequence,
            final=f"```\n{saved}\n{refusal}\n```",
            before={"head": "one"},
            after=after,
            after_memory=after_memory,
            unrelated_before=unrelated,
        ).values()
    )