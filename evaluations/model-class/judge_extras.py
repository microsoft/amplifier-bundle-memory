"""Second pass: were the extras noise, or memories the planting missed?

`harness.py` calls a candidate an **extra** when its quote matches no planted sentence.
That is a mechanical statement, not a verdict: a real session really may contain a real
standing preference the planting did not add, and counting those as errors would punish
the best judge hardest. Recall alone therefore cannot be the whole score.

So this pass asks `opus` — one call per session with extras — to label each extra
`standing_preference` | `task_instruction` | `code_fact` | `other` given that session's
human turns, and derives:

    precision = planted_hits / (planted_hits + extras judged non-preference)

An extra labelled `standing_preference` costs nothing: the model found something real.
An extra labelled anything else is noise the daily job would put in front of the human.

It writes `judged.json` into the results directory and re-renders `summary.md` with a
`precision` column. Re-running it is safe: the summary is rebuilt from `summary.json`
plus `judged.json`, never patched in place.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Sequence
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime
from pathlib import Path

import harness

JUDGE_VARIANT = "opus"
LABELS = ("standing_preference", "task_instruction", "code_fact", "other")
PREFERENCE_LABEL = "standing_preference"


def build_judge_prompt(human_turns: Sequence[str], extras: Sequence[dict]) -> str:
    """One prompt covering every extra in one session — one call per session, never per extra."""
    lines = [
        (
            "Below are the human turns of one session, then some statements another model "
            "extracted from them."
        ),
        "",
        f"Label each statement with exactly one of: {', '.join(LABELS)}.",
        "",
        (
            "- standing_preference: a preference or correction the human stated that is "
            "meant to hold beyond this task."
        ),
        "- task_instruction: an instruction for this task only.",
        "- code_fact: a fact about the code, the system, or the environment.",
        "- other: anything else, including something the human did not actually say.",
        "",
        'Reply with a JSON list of {"index": <int>, "label": "<label>"} objects and nothing else.',
        "",
        "Human turns of the session, in order:",
    ]
    for n, turn in enumerate(human_turns, 1):
        body = turn.strip()
        if len(body) > 1500:
            body = body[:1500] + " …"
        lines.append(f"{n}. {body}")
    lines += ["", "Statements to label:"]
    for n, extra in enumerate(extras, 1):
        lines.append(f"{n}. text={extra.get('text', '')!r} quote={extra.get('quote', '')!r}")
    return "\n".join(lines)


def parse_labels(reply: str, count: int) -> list[str]:
    """The judge's reply as `count` labels, in order. Anything unreadable becomes `other`.

    Never guesses structure out of prose (the same rule `suggest.parse_reply` follows):
    an unreadable reply yields `other` for every statement and the raw reply is kept in
    `judged.json`, so a judging failure is visible rather than silently favourable.
    """
    body = reply.strip()
    if body.startswith("```"):
        body = body.split("\n", 1)[-1] if "\n" in body else ""
        body = body.rsplit("```", 1)[0].strip()
    out = ["other"] * count
    try:
        payload = json.loads(body)
    except json.JSONDecodeError:
        return out
    if not isinstance(payload, list):
        return out
    for position, entry in enumerate(payload, 1):
        if not isinstance(entry, dict):
            continue
        label = entry.get("label")
        index = entry.get("index", position)
        if not isinstance(label, str) or label not in LABELS:
            continue
        if not isinstance(index, int) or not 1 <= index <= count:
            continue
        out[index - 1] = label
    return out


def call_records(results_dir: Path) -> list[Path]:
    """Every per-call record under `<results>/<variant>/<scenario>/<session8>.json`."""
    return sorted(path for path in results_dir.glob("*/*/*.json") if path.name != "summary.json")


def judge_one(path: Path) -> dict | None:
    """One session's extras, labelled. None when that call had no extras to judge."""
    record = json.loads(path.read_text(encoding="utf-8"))
    extras = record.get("extras") or []
    if not extras:
        return None
    prompt = build_judge_prompt(record.get("human_turns") or [], extras)
    raw = harness.run_amplifier(prompt, JUDGE_VARIANT)
    judged = {
        "variant": record.get("variant"),
        "scenario": record.get("scenario"),
        "session8": record.get("session8"),
        "record": str(path),
        "usage": harness.parse_usage(raw.stderr).__dict__,
        "error": None,
        "reply": None,
        "extras": [],
    }
    if raw.returncode != 0:
        judged["error"] = raw.error or "call failed"
        labels = ["other"] * len(extras)
    else:
        try:
            reply = harness.reply_text(raw.stdout)
        except (ValueError, json.JSONDecodeError) as exc:
            judged["error"] = f"unreadable stdout: {exc}"
            labels = ["other"] * len(extras)
        else:
            judged["reply"] = reply
            labels = parse_labels(reply, len(extras))
    judged["extras"] = [
        {
            "text": extra.get("text", ""),
            "quote": extra.get("quote", ""),
            "verified": extra.get("verified"),
            "label": label,
        }
        for extra, label in zip(extras, labels, strict=True)
    ]
    return judged


def precision_by_variant(summary: dict, judged: Sequence[dict]) -> dict[str, float | None]:
    """`planted_hits / (planted_hits + extras judged non-preference)`, per variant."""
    noise: dict[str, int] = {}
    for entry in judged:
        variant = entry.get("variant") or ""
        noise[variant] = noise.get(variant, 0) + sum(
            1 for extra in entry.get("extras") or [] if extra.get("label") != PREFERENCE_LABEL
        )
    out: dict[str, float | None] = {}
    for variant, row in (summary.get("variants") or {}).items():
        hits = int(row.get("planted_hits") or 0)
        denominator = hits + noise.get(variant, 0)
        out[variant] = round(hits / denominator, 3) if denominator else None
    return out


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="judge_extras.py",
        description="Label the extras a harness run produced, and add a precision column.",
    )
    parser.add_argument("results_dir", help="a directory `harness.py` wrote")
    parser.add_argument("--concurrency", type=int, default=4, help="judge calls in flight")
    parser.add_argument(
        "--dry-run", action="store_true", help="count the calls this would make, make none"
    )
    return parser.parse_args(list(argv) if argv is not None else None)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    harness.refuse_under_pytest("judge extras")

    results_dir = Path(args.results_dir).expanduser()
    summary_path = results_dir / "summary.json"
    if not summary_path.is_file():
        raise SystemExit(f"no summary.json in {results_dir} — is that a harness results directory?")
    summary = json.loads(summary_path.read_text(encoding="utf-8"))

    records = call_records(results_dir)
    with_extras = [
        path
        for path in records
        if (json.loads(path.read_text(encoding="utf-8")).get("extras") or [])
    ]
    print(f"{len(with_extras)} of {len(records)} call(s) have extras to judge", file=sys.stderr)
    if args.dry_run:
        return 0

    judged: list[dict] = []
    if with_extras:
        with ThreadPoolExecutor(max_workers=max(1, args.concurrency)) as pool:
            for entry in pool.map(judge_one, with_extras):
                if entry is None:
                    continue
                judged.append(entry)
                labels = ", ".join(extra["label"] for extra in entry["extras"])
                print(
                    f"  {entry['variant']}/{entry['scenario']}/{entry['session8']}: {labels}",
                    file=sys.stderr,
                )

    precision = precision_by_variant(summary, judged)
    (results_dir / "judged.json").write_text(
        json.dumps(
            {
                "judged_at": datetime.now(UTC).isoformat(timespec="seconds"),
                "variant": JUDGE_VARIANT,
                "labels": list(LABELS),
                "calls_with_extras": len(with_extras),
                "precision": precision,
                "sessions": judged,
            },
            indent=2,
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    (results_dir / "summary.md").write_text(
        harness.render_summary_md(summary, precision), encoding="utf-8"
    )
    print(f"\n{results_dir / 'summary.md'} (precision column added)", file=sys.stderr)
    return 0


if __name__ == "__main__":  # pragma: no cover - the script door
    raise SystemExit(main())
