"""The daily suggestion pass — suggestions.v1 Core 2, 3, 4, 8, 9, 10.

`amplifier-memory suggest` reads yesterday's recorded sessions, asks the model one
question per session, verifies every candidate's quote **in code** against a human turn,
and appends the survivors to `inbox.md`. It writes nothing to `MEMORY.md`, ever
(Core 6 is the only path there, and it needs a human keystroke).

suggestions.v1 clause map
-------------------------
Core 2   input: recorded root sessions, 24h / ≥2 human turns / ≤30 ... `select_sessions`
Core 3   one question, one call per session, exactly §3's prompt ..... `PROMPT`, `build_prompt`
Core 4   code verifies before it proposes ........................... `verify`, `run_suggest`
Core 8   bounded cost, visible (≤30 calls; exceed → skip + report) ... `run_suggest`
Core 9   report, even when empty (one log line per run) ............. `SuggestReport.log_line`
Core 10  fail open: substrate missing / model raising / malformed ... `run_suggest`

Where the sessions are
----------------------
``${AMPLIFIER_CONTEXT_INTELLIGENCE_BASE_PATH:-~/.amplifier/projects}/<project-slug>/
sessions/<session-id>/{metadata.json,transcript.jsonl}`` — measured on this device
2026-09-06: `metadata.json` carries `session_id`, `created`, `bundle`, `model`,
`turn_count`, `working_dir`; each `transcript.jsonl` line is `{role, content, metadata}`
with roles `user` / `assistant` / `tool`, a **str** `content` on user turns and a list of
blocks on assistant turns, and `metadata.timestamp` in ISO-8601.

Root sessions are the ones whose directory name is a plain UUID. A sub-agent's is
`0000000000000000-<hex>_<agent>` (measured on this device), and Core 2 excludes it: a
sub-agent has no human interlocutor, so nothing in it is a human's standing preference.

The default model call
----------------------
``amplifier run --output-format json "<prompt>"``. The flag is ``--output-format``, not
``--output``: verified against ``amplifier run --help`` on this device 2026-09-06, whose
output `tests/test_suggest.py::test_the_default_argv_matches_amplifier_run_help` prints
(AGENTS.md rule 5 — `amplifier run --once` did not exist and shipped anyway). The JSON it
prints on success is ``{"status": "success", "response": "<assistant text>",
"session_id": …, "bundle": …, "model": …, "timestamp": …}`` (amplifier_app_cli/main.py
~:4440), so the assistant's text is ``json.loads(stdout)["response"]``.

It is injectable, and **no test in this repository ever calls it**: `model_call` is a
parameter, every test passes a fake, and `tests/conftest.py` replaces the process runner
for the whole suite.

This module imports only the standard library and this package: no `click`.
"""

from __future__ import annotations

import json
import os
import re
import subprocess
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from pathlib import Path

from . import inbox
from .store import _read_text, _require_store, store_home

#: suggestions.v1 Core 9: "Every run appends one line to `~/.amplifier/memory/suggest.log`."
LOG_NAME = "suggest.log"

#: suggestions.v1 Core 2 / R2: the starting bounds, tuned on `doctor` evidence, never taste.
WINDOW_HOURS = 24
MAX_SESSIONS = 30
MIN_HUMAN_TURNS = 2
#: Core 8: "≤30 model calls per run, one run per day."
MAX_CALLS = 30

#: Core 2: a root session id is a plain UUID; a sub-agent's is `0000000000000000-<hex>_<agent>`.
_ROOT_ID_RE = re.compile(
    r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$", re.IGNORECASE
)

#: Core 2: "sessions spawned by this job … are excluded". A session this job started
#: carries the §3 prompt as its first human turn, and its bundle names the job.
_JOB_BUNDLE_MARKERS = ("amplifier-memory-suggest", "memory-suggest")

#: suggestions.v1 §3, verbatim, up to the list it asks the model to skip. This much of
#: the prompt never varies, so it is also the fingerprint that recognises a session this
#: job spawned (Core 2).
PROMPT_PREFIX = (
    "List the explicit standing preferences or corrections this human stated \u2014 things "
    "meant to hold beyond this task. Quote each verbatim from a human turn. Skip task "
    "instructions, facts about the code, and anything already in this list:"
)

#: The whole of §3, with the two placeholders the clause names, and the full stop that
#: sits inside the clause's own quotation marks. `build_prompt` fills the placeholders.
PROMPT = f"{PROMPT_PREFIX} <MEMORY.md> <declined.md>."

#: What the reply must be: a JSON list of `{text, quote}` (Core 3, "Output is structured").
REPLY_SHAPE = 'a JSON list of {"text": "…", "quote": "…"} objects'

#: The one argv the default model call runs. See the module docstring for the verification.
RUN_ARGV: tuple[str, ...] = ("amplifier", "run", "--output-format", "json")

ModelCall = Callable[[str], str]


# --------------------------------------------------------------------------- the report


@dataclass
class SuggestReport:
    """One run's whole outcome — and its one log line (Core 9)."""

    when: datetime
    sessions: int = 0
    proposed: int = 0
    rejected: int = 0
    dropped_stale: int = 0
    calls: int = 0
    status: str = "ok"
    #: Candidates dropped by `inbox.append` as already known (a MEMORY.md line, a
    #: decline, or a duplicate). Reported here rather than in the fixed log line.
    already_known: int = 0
    #: Sessions not asked because the call budget ran out (Core 8: skip and report).
    skipped_over_budget: int = 0
    proposals: list[inbox.Suggestion] = field(default_factory=list)
    dropped: list[inbox.Suggestion] = field(default_factory=list)

    @property
    def degraded(self) -> bool:
        return self.status != "ok"

    @property
    def log_line(self) -> str:
        """Core 9's line, in the fixed shape `doctor` parses back out of `suggest.log`."""
        return (
            f"{self.when.isoformat(timespec='seconds')} "
            f"sessions={self.sessions} proposed={self.proposed} rejected={self.rejected} "
            f"dropped_stale={self.dropped_stale} calls={self.calls} status={self.status}"
        )

    def render(self) -> str:
        return self.log_line


# --------------------------------------------------------------------------- the substrate


def substrate_root(base_path: str | os.PathLike[str] | None = None) -> Path:
    """suggestions.v1 Core 2's location: the context-intelligence local session capture."""
    if base_path is not None:
        return Path(base_path).expanduser()
    env = os.environ.get("AMPLIFIER_CONTEXT_INTELLIGENCE_BASE_PATH", "").strip()
    if env:
        return Path(env).expanduser()
    return Path.home() / ".amplifier" / "projects"


@dataclass(frozen=True)
class RecordedSession:
    """One recorded root session, read off disk: its id, its bundle, its human turns."""

    id: str
    path: Path
    bundle: str
    human_turns: tuple[str, ...]
    #: The timestamps of those human turns, in the order they were said.
    turn_times: tuple[datetime, ...]

    @property
    def last_human_turn_at(self) -> datetime | None:
        return self.turn_times[-1] if self.turn_times else None


def _parse_time(raw: object) -> datetime | None:
    if not isinstance(raw, str) or not raw.strip():
        return None
    try:
        parsed = datetime.fromisoformat(raw)
    except ValueError:
        return None
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=UTC)


def _turn_text(content: object) -> str:
    """A transcript line's content as text, whether it is a str or a list of blocks."""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = [
            block.get("text", "")
            for block in content
            if isinstance(block, dict) and isinstance(block.get("text"), str)
        ]
        return "\n".join(part for part in parts if part)
    return ""


def read_session(directory: Path) -> RecordedSession | None:
    """One session directory as a `RecordedSession`, or None when it cannot be read.

    Never raises on a malformed transcript: a half-written JSONL line (the capture is
    append-only and a session may be live) is skipped, and the rest of the file is still
    read. Core 10's fail-open starts here, not at the top-level try.
    """
    metadata_path = directory / "metadata.json"
    transcript_path = directory / "transcript.jsonl"
    if not transcript_path.is_file():
        return None
    try:
        metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        metadata = {}
    if not isinstance(metadata, dict):
        metadata = {}
    created = _parse_time(metadata.get("created"))

    turns: list[str] = []
    times: list[datetime] = []
    for line in _read_text(transcript_path).splitlines():
        if not line.strip():
            continue
        try:
            record = json.loads(line)
        except json.JSONDecodeError:
            continue
        if not isinstance(record, dict) or record.get("role") != "user":
            continue
        text = _turn_text(record.get("content"))
        if not text.strip():
            continue
        stamp = record.get("metadata")
        when = _parse_time(stamp.get("timestamp")) if isinstance(stamp, dict) else None
        turns.append(text)
        times.append(when or created or datetime.fromtimestamp(0, UTC))
    return RecordedSession(
        id=directory.name,
        path=directory,
        bundle=str(metadata.get("bundle") or ""),
        human_turns=tuple(turns),
        turn_times=tuple(times),
    )


def is_root_session_id(session_id: str) -> bool:
    """Core 2: only a root session (a human interlocutor) is read."""
    return bool(_ROOT_ID_RE.match(session_id))


def spawned_by_this_job(session: RecordedSession) -> bool:
    """Core 2: a session this job spawned is excluded — by its prompt and by its bundle.

    Two tests, because either alone has a hole: the bundle string is whatever the caller
    passed, and a human could conceivably paste the prompt. Both are cheap.
    """
    if any(marker in session.bundle for marker in _JOB_BUNDLE_MARKERS):
        return True
    first = session.human_turns[0].strip() if session.human_turns else ""
    return first.startswith(PROMPT_PREFIX)


def select_sessions(
    base_path: str | os.PathLike[str] | None = None,
    *,
    now: datetime | None = None,
    window_hours: int = WINDOW_HOURS,
    max_sessions: int = MAX_SESSIONS,
) -> list[RecordedSession]:
    """suggestions.v1 Core 2, in full: root · ≥2 human turns in the window · ≤30, newest first."""
    root = substrate_root(base_path)
    if not root.is_dir():
        return []
    cutoff = (now or datetime.now(UTC)) - timedelta(hours=window_hours)

    found: list[RecordedSession] = []
    for sessions_dir in sorted(root.glob("*/sessions")):
        if not sessions_dir.is_dir():
            continue
        for directory in sorted(sessions_dir.iterdir()):
            if not directory.is_dir() or not is_root_session_id(directory.name):
                continue
            session = read_session(directory)
            if session is None or spawned_by_this_job(session):
                continue
            recent = [when for when in session.turn_times if when >= cutoff]
            if len(recent) < MIN_HUMAN_TURNS:
                continue
            found.append(session)
    found.sort(key=lambda s: s.last_human_turn_at or datetime.fromtimestamp(0, UTC), reverse=True)
    return found[:max_sessions]


# --------------------------------------------------------------------------- the question


def build_prompt(memory_lines: Sequence[str], declined: Sequence[str]) -> str:
    """suggestions.v1 §3's prompt, with `<MEMORY.md>` and `<declined.md>` filled in.

    The sentence is the clause's, character for character — `tests/test_suggest.py::
    test_the_prompt_is_section_3_verbatim` asserts the string against the contract file
    — and the two lists are appended in the order §3 names them. A store with nothing in
    either list still gets both placeholders, spelled `(none)`, so the model is never
    handed a dangling colon.
    """
    known = "; ".join(line.strip() for line in memory_lines if line.strip()) or "(none)"
    refused = "; ".join(line.strip() for line in declined if line.strip()) or "(none)"
    return f"{PROMPT_PREFIX} <MEMORY.md: {known}> <declined.md: {refused}>."


def _json_object_in(stdout: str) -> object:
    """The JSON object `amplifier run --output-format json` prints, tolerating a preamble.

    Measured on the steward's device on 2026-09-06 (the first real run): stdout began
    with `Bundle 'anchors' prepared successfully` on its own line before the JSON, so a
    bare `json.loads(stdout)` failed at char 0 on all thirty calls and the run ended
    `degraded`. The object starts at the first `{` that begins a line; anything before it
    is the CLI talking, not the reply. Raises `json.JSONDecodeError` when no object is
    found, which the caller turns into the same `did not print JSON` reason as before.
    """
    for line_start in (m.start() for m in re.finditer(r"(?m)^\{", stdout)):
        try:
            payload, _ = json.JSONDecoder().raw_decode(stdout[line_start:])
        except json.JSONDecodeError:
            continue
        return payload
    return json.loads(stdout)


def default_model_call(prompt: str, *, timeout: float = 300.0) -> str:
    """`amplifier run --output-format json "<prompt>"`, returning the assistant's text.

    See the module docstring for the argv's verification and the JSON shape. Raises
    `RuntimeError` on a nonzero exit or an unreadable reply — `run_suggest` catches it,
    counts it, and the run ends `degraded` (Core 10).

    It refuses outright when reached from a test or a conformance probe. The sibling
    guard in `service._default_runner` was written after a probe enabled a real timer on
    the steward's device (2026-09-06); this one is the same guard on the more expensive
    door — a check that reached here would spend real model calls on the steward's own
    recorded sessions. Every caller in this repository injects `model_call`.
    """
    if os.environ.get("PYTEST_CURRENT_TEST"):
        raise RuntimeError(
            "refusing to call the model from a test: pass an explicit `model_call=` to "
            "`run_suggest` (and point AMPLIFIER_CONTEXT_INTELLIGENCE_BASE_PATH at a fixture)"
        )
    argv = [*RUN_ARGV, prompt]
    try:
        proc = subprocess.run(argv, capture_output=True, text=True, check=False, timeout=timeout)
    except (OSError, ValueError, subprocess.TimeoutExpired) as exc:
        raise RuntimeError(f"{' '.join(RUN_ARGV)} failed: {type(exc).__name__}: {exc}") from exc
    if proc.returncode != 0:
        reason = (proc.stderr or proc.stdout or "").strip().splitlines()
        raise RuntimeError(
            f"{' '.join(RUN_ARGV)} exited {proc.returncode}: {reason[-1] if reason else 'no output'}"
        )
    try:
        payload = _json_object_in(proc.stdout)
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"{' '.join(RUN_ARGV)} did not print JSON: {exc}") from exc
    response = payload.get("response") if isinstance(payload, dict) else None
    if not isinstance(response, str):
        raise RuntimeError(  # noqa: TRY004 - the caller counts a bad reply, it never type-checks it
            f"{' '.join(RUN_ARGV)} printed no assistant text (keys: "
            f"{sorted(payload) if isinstance(payload, dict) else type(payload).__name__})"
        )
    return response


class MalformedReply(ValueError):
    """The model's reply was not `REPLY_SHAPE`. Counted, never guessed at."""


def parse_reply(reply: str) -> list[tuple[str, str]]:
    """The reply as `(text, quote)` pairs, or `MalformedReply`.

    Tolerates the one wrapper models add on their own — a ```json fence — and nothing
    else. Inventing structure out of prose is exactly the guessing Core 4 forbids.
    """
    body = reply.strip()
    if body.startswith("```"):
        body = body.split("\n", 1)[-1] if "\n" in body else ""
        body = body.rsplit("```", 1)[0].strip()
    if not body:
        raise MalformedReply(f"empty reply; expected {REPLY_SHAPE}")
    try:
        payload = json.loads(body)
    except json.JSONDecodeError as exc:
        raise MalformedReply(f"not JSON ({exc}); expected {REPLY_SHAPE}") from exc
    if not isinstance(payload, list):
        raise MalformedReply(f"reply is {type(payload).__name__}, expected {REPLY_SHAPE}")
    out: list[tuple[str, str]] = []
    for entry in payload:
        if not isinstance(entry, dict):
            raise MalformedReply(f"list entry is {type(entry).__name__}, expected {REPLY_SHAPE}")
        text, quote = entry.get("text"), entry.get("quote")
        if not isinstance(text, str) or not isinstance(quote, str):
            raise MalformedReply(f"entry is missing text/quote; expected {REPLY_SHAPE}")
        out.append((text.strip(), quote))
    return out


def _flatten(text: str) -> str:
    return " ".join(text.split())


def verify(quote: str, human_turns: Sequence[str]) -> bool:
    """suggestions.v1 Core 4: the quote must appear verbatim in a human turn of that session.

    Whitespace-normalised on both sides, because a transcript re-wraps and a model
    re-flows; nothing else is relaxed. This is the poisoning gate: a candidate whose
    quote is absent from every human turn is rejected and counted, so a model that
    invents a preference cannot get it into the inbox, let alone into memory
    (AGENTS.md rule 7).
    """
    if not quote.strip():
        return False
    needle = _flatten(quote)
    return any(needle in _flatten(turn) for turn in human_turns)


# --------------------------------------------------------------------------- the log


def log_path(home: str | os.PathLike[str] | None = None) -> Path:
    """`<store>/suggest.log` (suggestions.v1 Core 9)."""
    return store_home(home) / LOG_NAME


def _ensure_ignored(home: Path) -> None:
    """Keep `suggest.log` out of `git status`, without inventing a layout file.

    store.v2 §2 fixes the store's layout and says a file not listed there is not memory.
    `suggest.log` is not listed — it is a run log, like `usage.jsonl` is a usage log —
    so it is neither committed nor allowed to leave the store's tree dirty. It is
    excluded through `.git/info/exclude`, git's own per-clone ignore file, which lives
    inside `.git/` exactly as the write lock does (store.py: "plumbing, not memory").
    Doing it in the tracked `.gitignore` would mean changing a committed file.
    """
    exclude = home / ".git" / "info" / "exclude"
    if not exclude.parent.is_dir():
        return
    body = _read_text(exclude)
    if LOG_NAME in body.splitlines():
        return
    prefix = "" if body.endswith("\n") or not body else "\n"
    with exclude.open("a", encoding="utf-8") as handle:
        handle.write(f"{prefix}{LOG_NAME}\n")


def append_log(report: SuggestReport, home: str | os.PathLike[str] | None = None) -> Path:
    """Core 9: one line per run, even when nothing was proposed. Never committed."""
    path = log_path(home)
    path.parent.mkdir(parents=True, exist_ok=True)
    _ensure_ignored(path.parent)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(f"{report.log_line}\n")
    return path


def last_log_line(home: str | os.PathLike[str] | None = None) -> str | None:
    """The most recent run's line, for `doctor` (Core 8). None when the job never ran."""
    lines = [line for line in _read_text(log_path(home)).splitlines() if line.strip()]
    return lines[-1] if lines else None


def parse_log_line(line: str) -> dict[str, str]:
    """A log line back into its fields — `{ts, sessions, proposed, …, status}`.

    `status` is read as **everything after `status=`**, not as one whitespace-delimited
    token: a degraded reason is a sentence (`degraded:substrate missing`), and splitting
    it on space is how `doctor` came to report `degraded:substrate` — a different, and
    less alarming, claim than the one the run actually made. That is why the clause puts
    `status` last in the line.
    """
    head, sep, status = line.partition("status=")
    parts = head.split()
    out: dict[str, str] = {"ts": parts[0]} if parts else {}
    for part in parts[1:]:
        key, found, value = part.partition("=")
        if found:
            out[key] = value
    if sep:
        out["status"] = status.strip()
    return out


# --------------------------------------------------------------------------- the run


def run_suggest(
    home: str | os.PathLike[str] | None = None,
    *,
    base_path: str | os.PathLike[str] | None = None,
    now: datetime | None = None,
    model_call: ModelCall | None = None,
    max_sessions: int = MAX_SESSIONS,
    max_calls: int = MAX_CALLS,
    window_hours: int = WINDOW_HOURS,
) -> SuggestReport:
    """One daily pass: read, ask, verify, propose, log. Exits 0 for the timer, always.

    The order is the contract's, and each step is refusable without losing the run:

    1. `expire` first (Core 6) — so the count of what went stale is in *this* run's line.
    2. `select_sessions` (Core 2). No substrate directory → `degraded:substrate missing`,
       no call, no inbox write, one log line (Core 10).
    3. one `model_call` per session (Core 3), bounded by `max_calls` (Core 8). A call
       that raises is counted and the run continues with the sessions that answered.
    4. `verify` every candidate in code (Core 4); rejects are counted.
    5. `inbox.append` the survivors (Core 4) — which drops anything already known.
    6. one log line (Core 9), whatever happened.

    `model_call` is injected by every caller in this repository's tests; left None it is
    `default_model_call`, whose argv the module docstring documents and verifies.
    """
    when = now or datetime.now(UTC)
    report = SuggestReport(when=when)
    reasons: list[str] = []
    survivors: list[inbox.Candidate] = []

    try:
        path = _require_store(home)
    except Exception as exc:  # noqa: BLE001 - Core 10: a missing store is reported, never raised
        report.status = f"degraded:{_reason(exc)}"
        return report

    try:
        report.dropped = inbox.expire(path, now=when)
        report.dropped_stale = len(report.dropped)
    except Exception as exc:  # noqa: BLE001 - Core 10
        reasons.append(f"expire failed ({_reason(exc)})")

    root = substrate_root(base_path)
    if not root.is_dir():
        report.status = "degraded:substrate missing"
        append_log(report, path)
        return report

    try:
        sessions = select_sessions(
            base_path, now=when, window_hours=window_hours, max_sessions=max_sessions
        )
    except Exception as exc:  # noqa: BLE001 - Core 10
        report.status = f"degraded:substrate unreadable ({_reason(exc)})"
        append_log(report, path)
        return report

    report.sessions = len(sessions)
    prompt = build_prompt(inbox.memory_texts(path), inbox.declined_texts(path))
    ask = model_call or default_model_call

    for session in sessions:
        if report.calls >= max_calls:
            report.skipped_over_budget += 1
            continue
        report.calls += 1
        try:
            reply = ask(prompt)
        except Exception as exc:  # noqa: BLE001 - Core 10: the model is allowed to be absent
            reasons.append(f"model call failed for {session.id[:8]} ({_reason(exc)})")
            continue
        try:
            candidates = parse_reply(reply)
        except MalformedReply as exc:
            report.rejected += 1
            reasons.append(f"malformed reply from {session.id[:8]} ({exc})")
            continue
        for text, quote in candidates:
            if not text or not verify(quote, session.human_turns):
                report.rejected += 1
                continue
            survivors.append(
                inbox.Candidate(
                    text=text,
                    quote=quote,
                    session=session.id[:8],
                    date=when.date().isoformat(),
                )
            )

    if report.skipped_over_budget:
        reasons.append(
            f"max_calls={max_calls} reached, {report.skipped_over_budget} session(s) skipped"
        )

    try:
        proposals = inbox.append(path, survivors)
    except Exception as exc:  # noqa: BLE001 - Core 10: a refused inbox write is not a crash
        proposals = []
        reasons.append(f"inbox write failed ({_reason(exc)})")
    report.proposals = proposals
    report.proposed = len(proposals)
    report.already_known = len(survivors) - report.proposed

    if reasons:
        report.status = f"degraded:{'; '.join(reasons)}"
    append_log(report, path)
    return report


def _reason(exc: BaseException) -> str:
    """One short sentence from an exception — never a traceback in a log line."""
    return f"{type(exc).__name__}: {exc}".replace("\n", " ")[:160]


__all__ = [
    "LOG_NAME",
    "MAX_CALLS",
    "MAX_SESSIONS",
    "MIN_HUMAN_TURNS",
    "PROMPT",
    "PROMPT_PREFIX",
    "RUN_ARGV",
    "WINDOW_HOURS",
    "MalformedReply",
    "RecordedSession",
    "SuggestReport",
    "append_log",
    "build_prompt",
    "default_model_call",
    "is_root_session_id",
    "last_log_line",
    "log_path",
    "parse_log_line",
    "parse_reply",
    "read_session",
    "run_suggest",
    "select_sessions",
    "spawned_by_this_job",
    "substrate_root",
    "verify",
]
