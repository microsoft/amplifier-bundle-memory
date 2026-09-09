"""Provider-free checks for session.v5's multi-turn review graders."""

import importlib.util
import shutil
import sys
from pathlib import Path

import pytest

from amplifier_memory import inbox

RUNNER = Path(__file__).resolve().parents[1] / "evaluations/review-recovery/multi_turn.py"
SPEC = importlib.util.spec_from_file_location("natural_review_probe", RUNNER)
module = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
sys.modules[SPEC.name] = module
SPEC.loader.exec_module(module)


def call(name, arguments, *, success=True, output="receipt"):
    return {"name": name, "arguments": arguments, "success": success, "output": output}


def expected_trace(*actions):
    return module.expected_review_trace(1, list(actions))


def canonical_calls(*actions):
    return [
        call("load_skill", {"skill_name": "memory", "arguments": "review"}),
        call("memory", {"operation": "review", "action": "list"}),
        *[
            call(
                "memory",
                {"operation": "review", "action": action, "id": suggestion_id},
                success=success,
            )
            for action, suggestion_id, success in actions
        ],
    ]


def test_exact_tool_trace_rejects_every_extra_wrong_or_reordered_call():
    actions = (("accept", "s-101", True), ("decline", "s-202", True))
    expected = expected_trace(*actions)
    good = canonical_calls(*actions)
    assert module.exact_tool_trace(good, expected)
    for actual in (
        good[1:],
        [*good, call("load_skill", {"skill_name": "memory", "arguments": "review"})],
        [call("load_skill", {"skill_name": "memory", "arguments": "review 2"}), *good[1:]],
        [good[0], call("memory", {"operation": "list", "action": "list"}), *good[2:]],
        [good[0], good[1], good[3], good[2]],
        good[:-1],
        [good[0], good[1], good[2], good[2], good[3]],
        [
            good[0],
            good[1],
            call("memory", {"operation": "review", "action": "accept", "id": "s-202"}),
            good[3],
        ],
        [
            good[0],
            good[1],
            good[2],
            call("memory", {"operation": "review", "action": "accept", "id": "s-202"}),
        ],
        [
            good[0],
            good[1],
            *good[2:],
            call("memory", {"operation": "review", "action": "skip", "id": "s-303"}),
        ],
        [
            good[0],
            good[1],
            call("memory", {"operation": "review", "action": "list"}),
            *good[2:],
        ],
    ):
        assert not module.exact_tool_trace(actual, expected)


def test_page_two_trace_requires_the_explicit_displayed_page_call():
    expected = module.expected_review_trace(2, [("accept", "s-606", True)])
    assert module.exact_tool_trace(
        [
            call("load_skill", {"skill_name": "memory", "arguments": "review 2"}),
            call("memory", {"operation": "review", "action": "list", "page": 2}),
            call("memory", {"operation": "review", "action": "accept", "id": "s-606"}),
        ],
        expected,
    )


def test_renderer_parser_uses_real_two_and_nine_item_sparse_pages(store):
    module._seed_sparse(inbox, store, 2)
    two = module.parse_displayed_review_items(inbox.render_review_page(1, store))
    assert [(item.number, item.id) for item in two] == [(1, "s-101"), (2, "s-202")]

    nine_store = store.parent / "nine"
    nine_store.mkdir()
    inbox_path = store / "inbox.md"
    shutil.copytree(store / ".git", nine_store / ".git")
    for name in ("MEMORY.md", "config.yaml", "declined.md", "sessions.jsonl"):
        shutil.copy2(store / name, nine_store / name)
    inbox_path.unlink()
    module._seed_sparse(inbox, nine_store, 9)
    first = module.parse_displayed_review_items(inbox.render_review_page(1, nine_store))
    second = module.parse_displayed_review_items(inbox.render_review_page(2, nine_store))
    assert [(item.number, item.id) for item in first] == [
        (1, "s-101"),
        (2, "s-202"),
        (3, "s-303"),
        (4, "s-404"),
        (5, "s-505"),
    ]
    assert [(item.number, item.id) for item in second] == [
        (1, "s-606"),
        (2, "s-707"),
        (3, "s-808"),
        (4, "s-909"),
    ]
    reply, actions = module._case_reply("paged-nonconsecutive", second)
    assert reply == f"accept #{second[0].number}, decline #{second[1].number}"
    assert actions == [("accept", "s-606", True), ("decline", "s-707", True)]
    text_reply, text_actions = module._case_reply("natural-text", second)
    assert second[0].text in text_reply
    assert text_actions == [("accept", "s-606", True)]


def test_exact_fenced_receipts_rejects_any_changed_or_extra_payload():
    receipts = ["saved m-001\n  text", "declined s-202"]
    good = "```text\nsaved m-001\n  text\ndeclined s-202\n```"
    assert module.exact_fenced_receipts(good, receipts)
    for final in (
        "prefix\n" + good,
        good + "\nsuffix",
        "```\nsaved m-001\n  text\n```",
        "```\nsaved m-001\n changed\ndeclined s-202\n```",
        "```\nsaved m-001\n  text\ndeclined s-202\ndeclined s-202\n```",
        "```\nsaved m-001\n  text\ncommentary\ndeclined s-202\n```",
    ):
        assert not module.exact_fenced_receipts(final, receipts)


def test_exact_refusal_relay_rejects_prefix_suffix_and_changed_line():
    refusal = "unknown suggestion id 's-101'"
    assert module.exact_refusal_relay(refusal, refusal)
    assert module.exact_refusal_relay(f"```\n{refusal}\n```", refusal)
    for final in (
        "sorry: " + refusal,
        refusal + "\nnext",
        "```\nunknown suggestion id 's-202'\n```",
        f"```\n{refusal}\nother receipt\n```",
    ):
        assert not module.exact_refusal_relay(final, refusal)


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("Which suggestion should I accept?", True),
        ("I will accept one.", False),
        ("Which suggestion should I accept", False),
        ("Which suggestion should I accept? And why?", False),
    ],
)
def test_concise_clarification_requires_one_bounded_question(text, expected):
    assert module.concise_clarification(text) is expected


def test_ambiguity_trace_rejects_a_partial_write_before_clarification():
    reply, actions = module._case_reply(
        "ambiguous",
        [
            module.DisplayedReviewItem(7, "s-101", "first"),
            module.DisplayedReviewItem(9, "s-202", "second"),
        ],
    )
    assert reply == "accept #7, decline that one"
    assert actions == []
    expected = expected_trace()
    assert module.exact_tool_trace(canonical_calls(), expected)
    partial = canonical_calls(("accept", "s-101", True))
    assert not module.exact_tool_trace(partial, expected)


def test_stale_id_refusal_requires_exact_relay_and_no_follow_up():
    actions = (("accept", "s-101", False),)
    calls = canonical_calls(*actions)
    refusal = "unknown suggestion id 's-101'"
    calls[-1]["output"] = refusal
    assert module.exact_tool_trace(calls, expected_trace(*actions))
    assert module.terminal_missing_id(f"```\n{refusal}\n```", calls, "s-101")
    assert not module.exact_tool_trace(
        [*calls, call("memory", {"operation": "review", "action": "decline", "id": "s-202"})],
        expected_trace(*actions),
    )


def test_stale_plan_removes_a_real_displayed_target_before_the_second_reply(store):
    module._seed_sparse(inbox, store, 2)
    displayed = module.parse_displayed_review_items(inbox.render_review_page(1, store))
    reply, actions = module._case_reply("stale-id", displayed)
    inbox.decline(displayed[0].id, store)
    assert displayed[0].id not in {item.id for item in inbox.pending(store)}
    assert reply == f"accept #{displayed[0].number}, decline #{displayed[1].number}"
    assert actions == [("accept", displayed[0].id, False)]


@pytest.mark.parametrize("mutation", ["unrelated", "memory", "decline", "inbox-removal"])
def test_store_proof_rejects_unrelated_and_extra_store_mutations(store, mutation):
    module._seed_sparse(inbox, store, 2)
    baseline = module.store_proof(store)
    candidate = store.parent / f"candidate-{mutation}"
    shutil.copytree(store, candidate)
    if mutation == "unrelated":
        (candidate / "unrelated.txt").write_text("unexpected\n", encoding="utf-8")
    elif mutation == "memory":
        inbox.accept("s-101", candidate, session_id="synthetic-natural-review")
    elif mutation == "decline":
        inbox.decline("s-101", candidate)
    else:
        inbox.expire(candidate, days=0)
    assert module.store_proof(candidate) != baseline


def test_store_oracle_requires_exact_bytes_and_commit_messages(store):
    module._seed_sparse(inbox, store, 2)
    actual = store.parent / "actual"
    oracle = store.parent / "oracle"
    shutil.copytree(store, actual)
    shutil.copytree(store, oracle)
    before = module.store_proof(actual)
    actions = [("accept", "s-101", True), ("decline", "s-202", True)]
    module._apply_oracle(inbox, actual, actions)
    module._apply_oracle(inbox, oracle, actions)
    assert module.store_proof(actual) == module.store_proof(oracle)
    assert module.store_proof(actual) != before
