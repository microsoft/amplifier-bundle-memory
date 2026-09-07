"""Build the evaluation's fixtures out of the steward's own real recorded sessions.

AGENTS.md rule 3: prove it on the owner's real host, with the owner's real sessions.
A judge that scores well on invented transcripts has proved nothing — real sessions carry
the pasted stack traces, the half-sentences and the "ok do that" turns that make this
question hard. So every fixture here is a real session read through the job's own
`read_session`, selected by the job's own `is_root_session_id` / `spawned_by_this_job`.

Three scenarios, three failure modes:

`planted.json`       10 real sessions, each with 1–2 standing preferences from
                     `preferences.json` inserted as NEW human turns at random positions
                     (never the first turn — the first turn is the task). A correct model
                     returns exactly those, quoted verbatim. Measures **recall**.
`pure_task.json`     10 DIFFERENT real sessions, untouched, expected `[]` — and *screened*
                     by one `opus` call each, so a session that already contains a real
                     standing preference never becomes a false-positive fixture. Measures
                     **restraint**.
`already_known.json` the same 10 planted sessions, but `memory_lines` already names every
                     planted text, so §3's "anything already in this list" applies and a
                     correct model returns `[]`. Measures **deduplication**.

The output is the steward's own session text and is **git-ignored**; this script refuses
to write into a directory git does not ignore.
"""

from __future__ import annotations

import argparse
import json
import random
import subprocess
import sys
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path

import harness

from amplifier_memory.suggest import (
    TURN_CHARS,
    RecordedSession,
    is_root_session_id,
    read_session,
    spawned_by_this_job,
    substrate_root,
)

HERE = Path(__file__).resolve().parent
PREFERENCES = HERE / "preferences.json"
DEFAULT_FIXTURES = HERE / "fixtures"

#: A conversation, not a lane transcript: `compose_request` sends only human turns, and a
#: session with more than a dozen of them is a work session, not a exchange we can plant into.
MIN_TURNS = 3
MAX_TURNS = 12
#: Each turn long enough to be a sentence, short enough not to dominate the request.
MIN_TURN_CHARS = 20
MAX_TURN_CHARS = 1500
#: Never evaluate on an evaluation: those sessions are full of prompts about preferences.
BUNDLE_EXCLUDE = "evaluation"

SCREEN_QUESTION = (
    "Does any of these human turns state a standing preference or correction meant to "
    "hold beyond this task? Reply only YES or NO."
)
SCREEN_VARIANT = "opus"


# --------------------------------------------------------------------------- candidates


@dataclass
class Scan:
    """What the walk over the substrate saw — reported, so the sample is never a mystery."""

    directories: int = 0
    read: int = 0
    unreadable: int = 0
    too_large: int = 0
    job_spawned: int = 0
    wrong_turn_count: int = 0
    wrong_turn_length: int = 0
    excluded_bundle: int = 0
    kept: int = 0


def session_directories(root: Path) -> list[Path]:
    """Every root-session directory under the substrate — a cheap listing, no file reads."""
    found: list[Path] = []
    for sessions_dir in sorted(root.glob("*/sessions")):
        if not sessions_dir.is_dir():
            continue
        try:
            entries = sorted(sessions_dir.iterdir())
        except OSError:
            continue
        found += [entry for entry in entries if entry.is_dir() and is_root_session_id(entry.name)]
    return found


def usable(session: RecordedSession) -> bool:
    """A conversation we can plant into: the right shape of human turns."""
    turns = session.human_turns
    if not MIN_TURNS <= len(turns) <= MAX_TURNS:
        return False
    return all(MIN_TURN_CHARS <= len(turn.strip()) <= MAX_TURN_CHARS for turn in turns)


def collect_candidates(
    root: Path, rng: random.Random, want: int, max_mb: float, scan: Scan
) -> list[RecordedSession]:
    """`want` usable sessions, drawn in a seeded-random order over the whole substrate.

    The directory list is shuffled *before* anything is read, so the sample is random and
    reproducible without reading every transcript on the device (there are thousands).
    """
    directories = session_directories(root)
    scan.directories = len(directories)
    rng.shuffle(directories)

    kept: list[RecordedSession] = []
    limit_bytes = int(max_mb * 1024 * 1024)
    for directory in directories:
        if len(kept) >= want:
            break
        transcript = directory / "transcript.jsonl"
        try:
            if not transcript.is_file():
                scan.unreadable += 1
                continue
            if transcript.stat().st_size > limit_bytes:
                scan.too_large += 1
                continue
        except OSError:
            scan.unreadable += 1
            continue
        session = read_session(directory)
        scan.read += 1
        if session is None:
            scan.unreadable += 1
            continue
        if spawned_by_this_job(session):
            scan.job_spawned += 1
            continue
        if BUNDLE_EXCLUDE in session.bundle.lower():
            scan.excluded_bundle += 1
            continue
        turns = session.human_turns
        if not MIN_TURNS <= len(turns) <= MAX_TURNS:
            scan.wrong_turn_count += 1
            continue
        if not usable(session):
            scan.wrong_turn_length += 1
            continue
        kept.append(session)
    scan.kept = len(kept)
    return kept


# --------------------------------------------------------------------------- planting


def load_preferences() -> list[dict]:
    payload = json.loads(PREFERENCES.read_text(encoding="utf-8"))
    bank = payload["preferences"]
    if not isinstance(bank, list) or not bank:
        raise SystemExit(f"{PREFERENCES} holds no preferences")
    return bank


class Deck:
    """The bank, dealt without replacement and reshuffled when it runs out.

    Every preference gets used before any is used twice, so a variant cannot score well
    by happening to be good at one phrasing.
    """

    def __init__(self, bank: list[dict], rng: random.Random) -> None:
        self._bank = bank
        self._rng = rng
        self._pile: list[dict] = []

    def draw(self, exclude_ids: set[str]) -> dict:
        for _ in range(len(self._bank) + 2):
            if not self._pile:
                self._pile = list(self._bank)
                self._rng.shuffle(self._pile)
            card = self._pile.pop()
            if card["id"] not in exclude_ids:
                return card
        raise RuntimeError("preference bank exhausted")


def plant(session: RecordedSession, deck: Deck, rng: random.Random) -> dict:
    """One planted fixture: the session's turns with 1–2 preference sentences inserted."""
    turns = list(session.human_turns)
    how_many = rng.choice((1, 2))
    chosen: list[dict] = []
    used: set[str] = set()
    for _ in range(how_many):
        card = deck.draw(used)
        used.add(card["id"])
        chosen.append(card)
    for card in chosen:
        # Never position 0: the first turn is the task, and a preference stated there
        # reads as part of the brief rather than as a standing instruction.
        position = rng.randrange(1, len(turns) + 1)
        turns.insert(position, card["sentence"])
    return {
        "session_id": session.id,
        "bundle": session.bundle,
        "human_turns": turns,
        "memory_lines": [],
        "declined": [],
        "planted": [
            {"id": card["id"], "text": card["text"], "quote": card["sentence"]} for card in chosen
        ],
    }


def already_known_from(planted: list[dict]) -> list[dict]:
    """The planted fixtures again, with every planted text already in `MEMORY.md`."""
    out: list[dict] = []
    for n, fixture in enumerate(planted, 1):
        lines = [
            f"- [m-{n * 10 + index:03d}] {entry['text']}"
            for index, entry in enumerate(fixture["planted"], 1)
        ]
        out.append(
            dict(fixture, memory_lines=lines, planted=[], planted_but_known=fixture["planted"])
        )
    return out


# --------------------------------------------------------------------------- screening


@dataclass
class Screen:
    session_id: str
    verdict: str
    reply: str = ""
    error: str | None = None
    usage: dict = field(default_factory=dict)


def screen_prompt(human_turns: list[str]) -> str:
    """The screening question over the session's numbered human turns.

    Deliberately NOT `compose_request`: that one asks for the §3 JSON reply shape, which
    would fight the "reply only YES or NO" this screen needs. The turn body is built the
    same way — numbered, in order, each capped at `TURN_CHARS`.
    """
    lines = [SCREEN_QUESTION, "", "Human turns of the session, in order:"]
    for n, turn in enumerate(human_turns, 1):
        body = turn.strip()
        if len(body) > TURN_CHARS:
            body = body[:TURN_CHARS] + " …"
        lines.append(f"{n}. {body}")
    return "\n".join(lines)


def screen(session: RecordedSession) -> Screen:
    """One `opus` YES/NO call. Anything but a clear NO keeps the session OUT of pure_task."""
    raw = harness.run_amplifier(screen_prompt(list(session.human_turns)), SCREEN_VARIANT)
    usage = harness.parse_usage(raw.stderr).__dict__
    if raw.returncode != 0:
        return Screen(session.id, "error", error=raw.error or "call failed", usage=usage)
    try:
        reply = harness.reply_text(raw.stdout)
    except (ValueError, json.JSONDecodeError) as exc:
        return Screen(session.id, "error", error=f"unreadable stdout: {exc}", usage=usage)
    body = reply.strip().upper()
    if body.startswith("NO") or body == "NO.":
        verdict = "no"
    elif body.startswith("YES"):
        verdict = "yes"
    else:
        # Ambiguous is treated as YES on purpose: a pure_task fixture whose expected answer
        # is `[]` must be one we are sure about, or every variant's restraint score is noise.
        verdict = "unclear"
    return Screen(session.id, verdict, reply=reply.strip()[:400], usage=usage)


# --------------------------------------------------------------------------- writing


def refuse_if_not_ignored(directory: Path) -> None:
    """The fixtures are the steward's own session text. They never enter a commit."""
    probe = directory / "planted.json"
    result = subprocess.run(
        ["git", "check-ignore", "-q", str(probe)],
        cwd=str(HERE),
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        raise SystemExit(
            f"refusing to write real session text into {directory}: git does not ignore it.\n"
            "Add `evaluations/model-class/fixtures/` to the repository .gitignore first."
        )


def write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")


# --------------------------------------------------------------------------- the entry point


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="build_fixtures.py",
        description="Build model-class evaluation fixtures from real recorded sessions.",
    )
    parser.add_argument("--seed", type=int, default=7, help="RNG seed (the sample is reproducible)")
    parser.add_argument("--count", type=int, default=10, help="fixtures per scenario")
    parser.add_argument("--max-screens", type=int, default=25, help="cap on pure_task judge calls")
    parser.add_argument("--pool", type=int, default=60, help="usable sessions to draw from")
    parser.add_argument("--max-transcript-mb", type=float, default=8.0, help="skip bigger files")
    parser.add_argument("--out", default=str(DEFAULT_FIXTURES), help="fixtures directory")
    parser.add_argument("--base-path", default=None, help="substrate root override")
    return parser.parse_args(list(argv) if argv is not None else None)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    harness.refuse_under_pytest("build fixtures")

    out_dir = Path(args.out).expanduser()
    refuse_if_not_ignored(out_dir)

    root = substrate_root(args.base_path)
    if not root.is_dir():
        raise SystemExit(f"no substrate at {root}")

    rng = random.Random(args.seed)
    scan = Scan()
    need = max(args.pool, args.count * 2 + args.max_screens)
    candidates = collect_candidates(root, rng, need, args.max_transcript_mb, scan)
    print(
        f"scanned {scan.directories} root session dir(s), read {scan.read}, "
        f"kept {scan.kept} usable",
        file=sys.stderr,
    )
    if len(candidates) < args.count * 2:
        raise SystemExit(
            f"only {len(candidates)} usable session(s); need at least {args.count * 2}. "
            "Loosen --pool / --max-transcript-mb, or point --base-path at more sessions."
        )

    deck = Deck(load_preferences(), rng)
    planted_sessions = candidates[: args.count]
    planted = [plant(session, deck, rng) for session in planted_sessions]
    known = already_known_from(planted)

    screens: list[Screen] = []
    pure: list[dict] = []
    for session in candidates[args.count :]:
        if len(pure) >= args.count or len(screens) >= args.max_screens:
            break
        result = screen(session)
        screens.append(result)
        print(
            f"  screen {len(screens)}/{args.max_screens} {session.id[:8]}: {result.verdict}",
            file=sys.stderr,
        )
        if result.verdict == "no":
            pure.append(
                {
                    "session_id": session.id,
                    "bundle": session.bundle,
                    "human_turns": list(session.human_turns),
                    "memory_lines": [],
                    "declined": [],
                    "planted": [],
                    "screened": "no",
                }
            )

    built = datetime.now(UTC).isoformat(timespec="seconds")
    common = {"seed": args.seed, "built": built, "count": args.count}
    write_json(
        out_dir / "planted.json",
        {
            **common,
            "scenario": "planted",
            "expected": "the planted preferences",
            "fixtures": planted,
        },
    )
    write_json(
        out_dir / "pure_task.json",
        {
            **common,
            "scenario": "pure_task",
            "expected": "[]",
            "screened_with": SCREEN_VARIANT,
            "fixtures": pure,
        },
    )
    write_json(
        out_dir / "already_known.json",
        {**common, "scenario": "already_known", "expected": "[]", "fixtures": known},
    )
    write_json(
        out_dir / "screening.json",
        {
            **common,
            "question": SCREEN_QUESTION,
            "variant": SCREEN_VARIANT,
            "max_screens": args.max_screens,
            "scan": scan.__dict__,
            "screens": [entry.__dict__ for entry in screens],
        },
    )

    verdicts = {
        name: sum(1 for s in screens if s.verdict == name)
        for name in ("no", "yes", "unclear", "error")
    }
    print(
        f"\nplanted={len(planted)} pure_task={len(pure)} already_known={len(known)}  "
        f"screens={len(screens)} ({', '.join(f'{k}={v}' for k, v in verdicts.items())})\n"
        f"→ {out_dir}",
        file=sys.stderr,
    )
    if len(pure) < args.count:
        print(
            f"WARNING: only {len(pure)} pure_task fixture(s) — the screen cap "
            f"({args.max_screens}) was reached first.",
            file=sys.stderr,
        )
    return 0


if __name__ == "__main__":  # pragma: no cover - the script door
    raise SystemExit(main())
