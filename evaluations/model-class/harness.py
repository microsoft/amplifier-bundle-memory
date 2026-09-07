"""Which model class does the `suggest` judge need? — the measuring instrument.

`src/amplifier_memory/suggest.py` sends ONE request per recorded session and asks for
the standing preferences the human stated, as a JSON list of `{"text", "quote"}`. Code
then parses the reply and verifies every quote verbatim against that session's human
turns. Everything downstream of the model is deterministic; the only open question is
**which model** can answer that one question well enough.

This harness re-runs exactly that question against a bank of fixtures built from real
sessions, once per model variant, and counts what came back. It imports the job's own
`build_prompt` / `compose_request` / `parse_reply` / `verify` / `_flatten` /
`_json_object_in` rather than restating them, so a change to the job changes the
measurement with it. Nothing here writes to the store, the inbox, or `MEMORY.md`.

The shelled argv
----------------
`amplifier run -p <variant> [-B <bundle>] --output-format json "<request>"`, which is
`suggest.RUN_ARGV` with the two flags inserted. Verified against `amplifier run --help`
on this device 2026-09-06 (AGENTS.md rule 5); the output is quoted in this directory's
README.md.

Where the numbers come from
---------------------------
stdout is the JSON object the CLI prints (`_json_object_in` tolerates the
`Bundle '…' prepared successfully` preamble); the assistant's text is `["response"]`.
Cost and the model actually used are on **stderr**, in the CLI's own usage block:

    │  📊 Token Usage (anthropic/claude-haiku-4-5) [2.7s]
    └─ Input: 86,854 (69% cached) | Output: 167 | Total: 87,021 | Cost: $0.04

stdout's `"model"` key is NOT the model that answered — measured on this device
2026-09-06, a `-p haiku` call printed `"model": "sol/gpt-5.6-sol"` on stdout while
stderr said `anthropic/claude-haiku-4-5`. The stderr string is the one recorded.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import time
from collections.abc import Iterable, Sequence
from concurrent.futures import ThreadPoolExecutor
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path

from amplifier_memory.suggest import (
    RUN_ARGV,
    MalformedReply,
    _flatten,
    _json_object_in,
    build_prompt,
    compose_request,
    parse_reply,
    verify,
)

HERE = Path(__file__).resolve().parent
FIXTURES_DIR = HERE / "fixtures"

#: The three scenarios, and what a correct judge does in each.
SCENARIOS = ("planted", "pure_task", "already_known")

#: The model variants on this host, small to large. `amplifier provider list`.
KNOWN_VARIANTS = ("haiku", "sonnet", "opus", "sol", "gemini")

DEFAULT_OUT_ROOT = Path(
    "/home/bkrabach/dev/amplifier-memory-team-ci/.amplifier/evaluation/amplifier-bundle-memory"
)

CALL_TIMEOUT = 300.0

_ANSI_RE = re.compile(r"\x1b\[[0-9;?]*[ -/]*[@-~]")
_MODEL_RE = re.compile(r"Token Usage \(([^)]+)\)")
_LATENCY_RE = re.compile(r"\[([\d.]+)s\]")
_INPUT_RE = re.compile(r"Input: ([\d,]+)")
_OUTPUT_RE = re.compile(r"Output: ([\d,]+)")
_COST_RE = re.compile(r"Cost: \$([\d.]+)")


def refuse_under_pytest(what: str) -> None:
    """Real model calls never happen inside the suite (suggest.default_model_call's rule).

    `test_harness.py` exercises the pure functions with fakes. A real call from a test
    would spend money on the steward's own sessions, which is exactly the door
    `suggest.default_model_call` already bolts shut.
    """
    if os.environ.get("PYTEST_CURRENT_TEST"):
        raise RuntimeError(f"refusing to {what} from a test: the harness makes real model calls")


# --------------------------------------------------------------------------- the CLI's numbers


def strip_ansi(text: str) -> str:
    """The CLI colours its usage block; the regexes want the plain characters."""
    return _ANSI_RE.sub("", text)


@dataclass
class Usage:
    """What one call cost, read off the CLI's own stderr usage block.

    `input_tokens`, `output_tokens`, `cost_usd` and `latency_s` are **sums** over every
    usage block the call printed (one per LLM iteration), because what a call cost is
    the sum of its iterations, not its first one. `model` is the first model string
    seen and `models` every distinct one, so a routed call cannot hide behind an average.
    """

    model: str | None = None
    models: list[str] = field(default_factory=list)
    input_tokens: int | None = None
    output_tokens: int | None = None
    cost_usd: float | None = None
    latency_s: float | None = None
    blocks: int = 0


def _sum_ints(pattern: re.Pattern[str], text: str) -> int | None:
    found = [int(value.replace(",", "")) for value in pattern.findall(text)]
    return sum(found) if found else None


def _sum_floats(pattern: re.Pattern[str], text: str) -> float | None:
    found = [float(value) for value in pattern.findall(text)]
    return round(sum(found), 6) if found else None


def parse_usage(stderr: str) -> Usage:
    """The usage block(s) on stderr as a `Usage`. Every field is None when absent.

    The model and the latency are read only off lines that carry `Token Usage (`, so a
    `[2.7s]`-shaped string anywhere else in the CLI's chatter cannot be mistaken for a
    latency. A stderr with no usage block at all yields an all-None `Usage` rather than
    a crash: a failed call still gets a record.
    """
    clean = strip_ansi(stderr or "")
    models: list[str] = []
    latencies: list[float] = []
    for line in clean.splitlines():
        if "Token Usage (" not in line:
            continue
        model = _MODEL_RE.search(line)
        if model:
            models.append(model.group(1).strip())
        latency = _LATENCY_RE.search(line)
        if latency:
            latencies.append(float(latency.group(1)))
    distinct: list[str] = []
    for name in models:
        if name not in distinct:
            distinct.append(name)
    return Usage(
        model=models[0] if models else None,
        models=distinct,
        input_tokens=_sum_ints(_INPUT_RE, clean),
        output_tokens=_sum_ints(_OUTPUT_RE, clean),
        cost_usd=_sum_floats(_COST_RE, clean),
        latency_s=round(sum(latencies), 3) if latencies else None,
        blocks=len(models),
    )


# --------------------------------------------------------------------------- the call


def build_argv(request: str, variant: str, bundle: str | None = None) -> list[str]:
    """`suggest.RUN_ARGV` with `-p <variant>` and an optional `-B <bundle>` inserted.

    Built from the job's own tuple so the evaluated argv can never drift from the
    evaluated job's.
    """
    head = [RUN_ARGV[0], RUN_ARGV[1], "-p", variant]
    if bundle:
        head += ["-B", bundle]
    return [*head, *RUN_ARGV[2:], request]


@dataclass
class RawCall:
    """One `subprocess.run`, after at most one retry."""

    argv: list[str]
    returncode: int | None
    stdout: str
    stderr: str
    wall_s: float
    retries: int = 0
    error: str | None = None


def run_amplifier(
    request: str,
    variant: str,
    bundle: str | None = None,
    *,
    timeout: float = CALL_TIMEOUT,
) -> RawCall:
    """One model call, retried once on a nonzero exit or a timeout.

    A retry is recorded, never hidden: a variant that needs a second attempt on half its
    calls is telling us something about its fitness for a daily unattended job.
    """
    refuse_under_pytest("call the model")
    argv = build_argv(request, variant, bundle)
    last = RawCall(argv=argv, returncode=None, stdout="", stderr="", wall_s=0.0)
    for attempt in range(2):
        started = time.monotonic()
        try:
            proc = subprocess.run(
                argv, capture_output=True, text=True, check=False, timeout=timeout
            )
        except subprocess.TimeoutExpired as exc:
            last = RawCall(
                argv=argv,
                returncode=None,
                stdout=exc.stdout or "" if isinstance(exc.stdout, str) else "",
                stderr=exc.stderr or "" if isinstance(exc.stderr, str) else "",
                wall_s=round(time.monotonic() - started, 3),
                retries=attempt,
                error=f"timeout after {timeout}s",
            )
        except (OSError, ValueError) as exc:
            last = RawCall(
                argv=argv,
                returncode=None,
                stdout="",
                stderr="",
                wall_s=round(time.monotonic() - started, 3),
                retries=attempt,
                error=f"{type(exc).__name__}: {exc}",
            )
        else:
            last = RawCall(
                argv=argv,
                returncode=proc.returncode,
                stdout=proc.stdout,
                stderr=proc.stderr,
                wall_s=round(time.monotonic() - started, 3),
                retries=attempt,
                error=None if proc.returncode == 0 else f"exit {proc.returncode}",
            )
            if proc.returncode == 0:
                return last
    return last


def reply_text(stdout: str) -> str:
    """The assistant's text out of the CLI's JSON, via the job's own tolerant reader."""
    payload = _json_object_in(stdout)
    if not isinstance(payload, dict):
        # ValueError, not TypeError: the caller records a bad reply, it never type-checks
        # one — the same call `suggest.default_model_call` makes at the same door.
        raise ValueError(  # noqa: TRY004
            f"stdout JSON is {type(payload).__name__}, expected an object"
        )
    response = payload.get("response")
    if not isinstance(response, str):
        keys = sorted(payload)
        raise ValueError(f"stdout JSON has no string 'response' (keys: {keys})")  # noqa: TRY004
    return response


# --------------------------------------------------------------------------- the scoring


def match_planted(quote: str, planted_quotes: Sequence[str]) -> tuple[int | None, str | None]:
    """Which planted sentence (if any) this candidate's quote is, and how it matched.

    Exact first, on `suggest._flatten`'d text — the same normalisation `verify` uses, so
    a match here means the same thing a match there does. A verbatim substring either
    way is accepted and *labelled*, because a model that returns half the planted
    sentence found the preference but did not quote the whole of it, and those are
    different failures.
    """
    needle = _flatten(quote)
    if not needle:
        return None, None
    flattened = [_flatten(planted) for planted in planted_quotes]
    for index, planted in enumerate(flattened):
        if planted and needle == planted:
            return index, "exact"
    for index, planted in enumerate(flattened):
        if planted and planted in needle:
            return index, "candidate_contains_planted"
    for index, planted in enumerate(flattened):
        if planted and needle in planted:
            return index, "planted_contains_candidate"
    return None, None


def score_reply(reply: str, fixture: dict) -> dict:
    """One reply against one fixture: shape, verbatim-ness, planted hits, extras."""
    human_turns = list(fixture.get("human_turns") or [])
    planted = list(fixture.get("planted") or [])
    planted_quotes = [entry.get("quote", "") for entry in planted]

    try:
        pairs = parse_reply(reply)
    except MalformedReply as exc:
        return {
            "shape_ok": False,
            "parse_error": str(exc),
            "candidates": [],
            "planted_total": len(planted),
            "planted_hits": 0,
            "planted_missed": [entry.get("text", "") for entry in planted],
            "extras": [],
        }

    candidates: list[dict] = []
    hit_indexes: set[int] = set()
    extras: list[dict] = []
    for text, quote in pairs:
        index, kind = match_planted(quote, planted_quotes)
        entry = {
            "text": text,
            "quote": quote,
            "verified": verify(quote, human_turns),
            "planted_index": index,
            "match_kind": kind,
        }
        candidates.append(entry)
        if index is None:
            extras.append(entry)
        else:
            hit_indexes.add(index)
    return {
        "shape_ok": True,
        "parse_error": None,
        "candidates": candidates,
        "planted_total": len(planted),
        "planted_hits": len(hit_indexes),
        "planted_missed": [
            entry.get("text", "") for n, entry in enumerate(planted) if n not in hit_indexes
        ],
        "extras": extras,
    }


# --------------------------------------------------------------------------- the run


def load_fixtures(scenario: str, fixtures_dir: Path = FIXTURES_DIR) -> list[dict]:
    """One scenario's fixture list. Missing file → a plain, actionable error."""
    path = fixtures_dir / f"{scenario}.json"
    if not path.is_file():
        raise SystemExit(
            f"no fixtures at {path} — run `uv run python {HERE / 'build_fixtures.py'}`"
        )
    payload = json.loads(path.read_text(encoding="utf-8"))
    entries = payload.get("fixtures") if isinstance(payload, dict) else payload
    if not isinstance(entries, list):
        raise SystemExit(f"{path} does not hold a fixture list")
    return entries


def request_for(fixture: dict) -> str:
    """Exactly what the job would send for this session — its call, not an imitation."""
    prompt = build_prompt(fixture.get("memory_lines") or [], fixture.get("declined") or [])
    return compose_request(prompt, fixture.get("human_turns") or [])


@dataclass
class Job:
    variant: str
    scenario: str
    fixture: dict


def run_job(job: Job, bundle: str | None, out_dir: Path) -> dict:
    """One (variant, scenario, fixture): ask, score, write the per-call record."""
    fixture = job.fixture
    session_id = str(fixture.get("session_id", "unknown"))
    request = request_for(fixture)
    raw = run_amplifier(request, job.variant, bundle)

    record: dict = {
        "variant": job.variant,
        "scenario": job.scenario,
        "session_id": session_id,
        "session8": session_id[:8],
        "argv": raw.argv[:-1] + ["<request>"],
        "request": request,
        "returncode": raw.returncode,
        "retries": raw.retries,
        "error": raw.error,
        "wall_s": raw.wall_s,
        "usage": asdict(parse_usage(raw.stderr)),
        # Carried so a second pass (judge_extras.py) is self-contained: it needs the turns
        # to judge an extra, and reconstructing them from the request would be guesswork.
        "human_turns": list(fixture.get("human_turns") or []),
        "memory_lines": list(fixture.get("memory_lines") or []),
        "planted": fixture.get("planted") or [],
        "expected_empty": not (fixture.get("planted") or []),
        "reply": None,
    }
    if raw.error is not None and raw.returncode != 0:
        record.update(
            shape_ok=False,
            parse_error=f"call failed: {raw.error}",
            candidates=[],
            planted_total=len(record["planted"]),
            planted_hits=0,
            planted_missed=[entry.get("text", "") for entry in record["planted"]],
            extras=[],
            stderr_tail="\n".join(strip_ansi(raw.stderr).splitlines()[-20:]),
        )
    else:
        try:
            reply = reply_text(raw.stdout)
        except (ValueError, json.JSONDecodeError) as exc:
            record.update(
                shape_ok=False,
                parse_error=f"unreadable stdout: {exc}",
                candidates=[],
                planted_total=len(record["planted"]),
                planted_hits=0,
                planted_missed=[entry.get("text", "") for entry in record["planted"]],
                extras=[],
                stdout_head=raw.stdout[:2000],
            )
        else:
            record["reply"] = reply
            record.update(score_reply(reply, fixture))

    target = out_dir / job.variant / job.scenario
    target.mkdir(parents=True, exist_ok=True)
    (target / f"{record['session8']}.json").write_text(
        json.dumps(record, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    return record


# --------------------------------------------------------------------------- the summary


def _mean(values: Iterable[float]) -> float | None:
    collected = [value for value in values if value is not None]
    return round(sum(collected) / len(collected), 4) if collected else None


def _pct(part: int, whole: int) -> float | None:
    return round(100.0 * part / whole, 1) if whole else None


def _ratio(part: int, whole: int) -> float | None:
    return round(part / whole, 3) if whole else None


def summarize_variant(records: Sequence[dict]) -> dict:
    """One variant's whole row: shape, verbatim, recall, extras, dedupe, cost, latency."""
    calls = len(records)
    shape_ok = sum(1 for record in records if record.get("shape_ok"))
    candidates = [entry for record in records for entry in record.get("candidates") or []]
    verified = sum(1 for entry in candidates if entry.get("verified"))

    planted_records = [record for record in records if record.get("scenario") == "planted"]
    planted_total = sum(record.get("planted_total", 0) for record in planted_records)
    planted_hits = sum(record.get("planted_hits", 0) for record in planted_records)

    pure = [record for record in records if record.get("scenario") == "pure_task"]
    pure_fp = sum(len(record.get("candidates") or []) for record in pure)

    known = [record for record in records if record.get("scenario") == "already_known"]
    known_empty = sum(
        1 for record in known if record.get("shape_ok") and not (record.get("candidates") or [])
    )

    usages = [record.get("usage") or {} for record in records]
    models: list[str] = []
    for usage in usages:
        for name in usage.get("models") or []:
            if name not in models:
                models.append(name)
    costs = [usage.get("cost_usd") for usage in usages if usage.get("cost_usd") is not None]

    return {
        "calls": calls,
        "failed_calls": sum(1 for record in records if record.get("error")),
        "retries": sum(record.get("retries", 0) for record in records),
        "shape_ok": shape_ok,
        "shape_ok_pct": _pct(shape_ok, calls),
        "candidates": len(candidates),
        "verbatim_pct": _pct(verified, len(candidates)),
        "planted_total": planted_total,
        "planted_hits": planted_hits,
        "recall": _ratio(planted_hits, planted_total),
        "extras": sum(len(record.get("extras") or []) for record in records),
        "pure_task_calls": len(pure),
        "pure_task_false_positives": pure_fp,
        "pure_task_fp_per_session": _ratio(pure_fp, len(pure)),
        "already_known_calls": len(known),
        "already_known_dedupe_rate": _ratio(known_empty, len(known)),
        "mean_input_tokens": _mean(usage.get("input_tokens") for usage in usages),
        "mean_output_tokens": _mean(usage.get("output_tokens") for usage in usages),
        "mean_cost_usd": _mean(costs),
        "total_cost_usd": round(sum(costs), 4) if costs else None,
        "mean_latency_s": _mean(usage.get("latency_s") for usage in usages),
        "models_seen": models,
    }


def summarize(records: Sequence[dict], meta: dict | None = None) -> dict:
    """Every variant's row, plus a per-scenario breakdown under each."""
    variants: list[str] = []
    for record in records:
        if record["variant"] not in variants:
            variants.append(record["variant"])
    out: dict = {"meta": dict(meta or {}), "variants": {}}
    out["meta"].setdefault("calls", len(records))
    for variant in variants:
        rows = [record for record in records if record["variant"] == variant]
        entry = summarize_variant(rows)
        entry["scenarios"] = {
            scenario: summarize_variant([r for r in rows if r["scenario"] == scenario])
            for scenario in SCENARIOS
            if any(r["scenario"] == scenario for r in rows)
        }
        out["variants"][variant] = entry
    return out


_COLUMNS: tuple[tuple[str, str], ...] = (
    ("variant", "variant"),
    ("calls", "calls"),
    ("shape_ok_pct", "shape ok %"),
    ("verbatim_pct", "verbatim %"),
    ("recall", "recall"),
    ("extras", "extras"),
    ("pure_task_fp_per_session", "pure_task FP/session"),
    ("already_known_dedupe_rate", "already_known dedupe"),
    ("mean_input_tokens", "mean in tok"),
    ("mean_cost_usd", "mean $"),
    ("total_cost_usd", "total $"),
    ("mean_latency_s", "mean latency s"),
    ("models_seen", "model seen"),
)


def _cell(value: object) -> str:
    if value is None:
        return "–"
    if isinstance(value, list):
        return ", ".join(str(item) for item in value) or "–"
    if isinstance(value, float):
        return f"{value:g}"
    return str(value)


def render_summary_md(summary: dict, precision: dict[str, float | None] | None = None) -> str:
    """The whole run as one markdown page: a row per variant, then a table per variant.

    `precision` (from `judge_extras.py`) adds one more column; without it the column is
    absent rather than blank, so a summary never implies a judgement nobody made.
    """
    meta = summary.get("meta") or {}
    columns = list(_COLUMNS)
    if precision is not None:
        columns.append(("precision", "precision"))

    lines = ["# model-class evaluation — the `suggest` judge", ""]
    for key in ("started", "finished", "scenarios", "limit", "bundle", "concurrency", "fixtures"):
        if meta.get(key) not in (None, ""):
            lines.append(f"- **{key}**: {_cell(meta[key])}")
    lines += ["", "## Variants", ""]
    lines.append("| " + " | ".join(label for _, label in columns) + " |")
    lines.append("| " + " | ".join("---" for _ in columns) + " |")
    for variant, entry in (summary.get("variants") or {}).items():
        row = dict(entry, variant=variant)
        if precision is not None:
            row["precision"] = precision.get(variant)
        lines.append("| " + " | ".join(_cell(row.get(key)) for key, _ in columns) + " |")

    for variant, entry in (summary.get("variants") or {}).items():
        lines += ["", f"### {variant} — by scenario", ""]
        lines.append(
            "| scenario | calls | shape ok % | candidates | verbatim % | recall | extras "
            "| mean in tok | mean $ | mean latency s |"
        )
        lines.append("| " + " | ".join("---" for _ in range(10)) + " |")
        for scenario, row in (entry.get("scenarios") or {}).items():
            lines.append(
                "| "
                + " | ".join(
                    [
                        scenario,
                        _cell(row.get("calls")),
                        _cell(row.get("shape_ok_pct")),
                        _cell(row.get("candidates")),
                        _cell(row.get("verbatim_pct")),
                        _cell(row.get("recall")),
                        _cell(row.get("extras")),
                        _cell(row.get("mean_input_tokens")),
                        _cell(row.get("mean_cost_usd")),
                        _cell(row.get("mean_latency_s")),
                    ]
                )
                + " |"
            )
    lines += [
        "",
        "Cost is the CLI's own `Cost: $…`, which it prints to two decimals — read totals,",
        "not single calls. `recall` is planted preferences found / planted; `extras` are",
        "candidates matching no planted sentence (judge them with `judge_extras.py`).",
        "",
    ]
    return "\n".join(lines)


# --------------------------------------------------------------------------- the entry point


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="harness.py",
        description="Run the suggest judge's one question against several model variants.",
    )
    parser.add_argument(
        "--variants",
        default="haiku,sonnet,opus",
        help=f"comma-separated `amplifier run -p` providers (known here: {', '.join(KNOWN_VARIANTS)})",
    )
    parser.add_argument(
        "--scenarios", default=",".join(SCENARIOS), help="comma-separated scenarios"
    )
    parser.add_argument("--limit", type=int, default=None, help="fixtures per scenario")
    parser.add_argument("--concurrency", type=int, default=4, help="calls in flight")
    parser.add_argument("--bundle", default=None, help="passed through as `amplifier run -B`")
    parser.add_argument("--out", default=None, help="results directory")
    parser.add_argument(
        "--smoke",
        action="store_true",
        help="one real haiku call on one planted fixture — proves the wiring, costs cents",
    )
    args = parser.parse_args(list(argv) if argv is not None else None)
    if args.smoke:
        args.variants, args.scenarios, args.limit = "haiku", "planted", 1
    args.variant_list = [name.strip() for name in args.variants.split(",") if name.strip()]
    args.scenario_list = [name.strip() for name in args.scenarios.split(",") if name.strip()]
    unknown = [name for name in args.scenario_list if name not in SCENARIOS]
    if unknown:
        raise SystemExit(
            f"unknown scenario(s): {', '.join(unknown)} (known: {', '.join(SCENARIOS)})"
        )
    if not args.variant_list:
        raise SystemExit("no variants: pass --variants with at least one provider name")
    return args


def default_out_dir(now: datetime | None = None) -> Path:
    stamp = (now or datetime.now()).strftime("%Y%m%d-%H%M%S")  # noqa: DTZ005 - a local run label
    return DEFAULT_OUT_ROOT / f"{stamp}-model-class"


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    refuse_under_pytest("run the harness")

    variants, scenarios = args.variant_list, args.scenario_list

    jobs: list[Job] = []
    counts: dict[str, int] = {}
    for scenario in scenarios:
        fixtures = load_fixtures(scenario)
        if args.limit is not None:
            fixtures = fixtures[: args.limit]
        counts[scenario] = len(fixtures)
        for variant in variants:
            jobs += [Job(variant=variant, scenario=scenario, fixture=fx) for fx in fixtures]

    out_dir = Path(args.out).expanduser() if args.out else default_out_dir()
    out_dir.mkdir(parents=True, exist_ok=True)
    started = datetime.now().astimezone()
    print(
        f"{len(jobs)} call(s): {len(variants)} variant(s) × "
        f"{', '.join(f'{k}={v}' for k, v in counts.items())} → {out_dir}",
        file=sys.stderr,
    )

    records: list[dict] = []
    done = 0
    with ThreadPoolExecutor(max_workers=max(1, args.concurrency)) as pool:
        for record in pool.map(lambda job: run_job(job, args.bundle, out_dir), jobs):
            records.append(record)
            done += 1
            state = "ok" if record.get("shape_ok") else (record.get("parse_error") or "failed")
            print(
                f"  [{done}/{len(jobs)}] {record['variant']}/{record['scenario']}/"
                f"{record['session8']}: {state}",
                file=sys.stderr,
            )

    meta = {
        "started": started.isoformat(timespec="seconds"),
        "finished": datetime.now().astimezone().isoformat(timespec="seconds"),
        "variants": variants,
        "scenarios": scenarios,
        "limit": args.limit,
        "bundle": args.bundle,
        "concurrency": args.concurrency,
        "fixtures": counts,
        "out": str(out_dir),
    }
    summary = summarize(records, meta)
    (out_dir / "summary.json").write_text(
        json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    (out_dir / "summary.md").write_text(render_summary_md(summary), encoding="utf-8")
    print(f"\n{out_dir / 'summary.md'}", file=sys.stderr)
    return 0


if __name__ == "__main__":  # pragma: no cover - the script door
    raise SystemExit(main())
