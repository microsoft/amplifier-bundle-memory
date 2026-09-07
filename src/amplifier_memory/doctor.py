"""The install-plane reports: `doctor`, the update check, `service`, `suggest`, `update`.

cli.v2 Core 9: every behaviour a verb exposes is a public library function first,
so `amplifier-memory doctor` is `click.echo(amplifier_memory.doctor().render())` and
an exit code. This module imports only the standard library: no `click`.

**`doctor` never mutates** (cli.v2 Core 5). Nothing here writes, commits, stages, or
creates a file; the only shell-out is a read-only `git ls-remote` for the update
check, and that is injectable so a test never touches the network.
`tests/test_doctor.py` proves the no-mutation claim by hashing every file in the
store before and after.

The one repair path — `amplifier-memory doctor --repair` — is `store.repair_store`,
which lives in `store.py` with every other writer and is reached only when the flag is
given. `doctor()` itself, this module, still writes nothing under any circumstances.

cli.v2 clause map
-----------------
Core 5  `doctor` ........ `doctor`, `DoctorReport`, `update_check`
Core 6  `service` ....... `service_status`
Core 7  `update` ........ `update_plan` (the upgrade itself is not built here)
Core 1  `suggest` ....... `suggest_status`
Core 5  `llm judge` ..... `llm_row` (suggestions.v1 Core 8: which model, and what it cost)
"""

from __future__ import annotations

import hashlib
import json
import os
import shutil
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from pathlib import Path

from . import _git, inbox, llm_config, service, suggest
from .status import STALE_TOPIC_DAYS, status
from .store import (
    MEMORY_LINE_CAP,
    TOPIC_FILE_CAP,
    _read_lines,
    store_home,
    topic_files,
    verify_store,
)
from .suggest import last_log_line, parse_log_line, substrate_root

# AGENTS.md rule 4: the self-referential git URL, never a bare name or a relative path.
REPO_URL = "https://github.com/bkrabach/amplifier-bundle-memory"
PINNED_REF = "main"

OK, WARN, FAIL, INFO = "OK", "WARN", "FAIL", "INFO"
# cli.v2 Core 5: "Exit code is nonzero only on failed checks." WARN and INFO are not failures.
FAILING_LEVELS = (FAIL,)


@dataclass
class DoctorRow:
    """One doctor line: a name, a level, and what was actually observed."""

    name: str
    level: str
    detail: str

    def render(self) -> str:
        return f"  [{self.level:<4}] {self.name:<21} {self.detail}"


@dataclass
class DoctorReport:
    home: Path
    rows: list[DoctorRow] = field(default_factory=list)

    @property
    def exit_code(self) -> int:
        """cli.v2 Core 5: nonzero only on a failed check."""
        return 1 if any(row.level in FAILING_LEVELS for row in self.rows) else 0

    def render(self) -> str:
        head = f"amplifier-memory doctor \u2014 store: {self.home}"
        return "\n".join([head, "", *(row.render() for row in self.rows)])


# --------------------------------------------------------------------------- update check


def installed_commit() -> str | None:
    """The commit this install was built from, or None when it is not knowable.

    A `uv tool install git+https://…` records the resolved commit in the
    distribution's `direct_url.json` (PEP 610). A working-tree/editable install has
    no such record, and that is reported honestly as "not checkable", never guessed.
    """
    try:
        from importlib.metadata import PackageNotFoundError, distribution

        raw = distribution("amplifier-memory").read_text("direct_url.json")
    except (ImportError, PackageNotFoundError, OSError):
        return None
    if raw is None:
        return None
    try:
        return json.loads(raw).get("vcs_info", {}).get("commit_id") or None
    except (json.JSONDecodeError, AttributeError):
        return None


def remote_commit(url: str = REPO_URL, ref: str = PINNED_REF) -> str | None:
    """`git ls-remote <url> <ref>`, or None offline. The only network call in this bundle."""
    return _git.ls_remote(url, ref, cwd=Path.cwd())


# ----------------------------------------------------------- the three installed things
#
# A device runs THREE copies of this bundle, and until 2026-09-06 `doctor` compared one:
#
#   1. the `amplifier-memory` uv tool          - the shell verb (`installed_commit`)
#   2. the bundle cache clone(s)               - where the modules and skills are LOADED from
#   3. `amplifier_memory` in the amplifier venv - what those modules IMPORT
#
# Measured that day on the steward's device: after `update` reported `[ok] refresh the app
# bundle` and `doctor` reported `[OK] update current`, a real session still printed v1's
# `Loaded 2 memories (0 topics available).` - (2) sat at 0afc6a8 and (3) at a pre-K1 commit
# for four waves, and nothing in this file could see it. The record is
# `docs/workflow/CHECK-RECORD.md`, addendum 2026-09-06 22:05Z.

#: The labels the update row uses, in the order it names them.
UV_TOOL = "uv tool"
BUNDLE_CACHE = "bundle cache"
ENV_LIBRARY = "env library"

#: The app-bundle URI, spelled the one way that composes (see `update.py`'s docstring).
_APP_URI = f"git+{REPO_URL}@{PINNED_REF}#subdirectory=behaviors/memory-session.yaml"

#: How many characters of a sha the rows print. `git`'s own short form.
SHORT = 7

#: "the caller said nothing", as distinct from "the caller said None" (= no venv found).
_UNSET_PYTHON = object()


def _amplifier_dir(amplifier_home: str | os.PathLike[str] | None = None) -> Path:
    """`~/.amplifier`, or `$AMPLIFIER_HOME`, or whatever the caller injected.

    The resolution order is amplifier's own (`amplifier_foundation.paths.resolution.
    get_amplifier_home`: `AMPLIFIER_HOME` env var, else `~/.amplifier`), read from the
    installed foundation rather than assumed. Injectable so a test never reads this
    device's real cache.
    """
    if amplifier_home is not None:
        return Path(amplifier_home).expanduser()
    env = os.environ.get("AMPLIFIER_HOME")
    return Path(env).expanduser() if env else Path.home() / ".amplifier"


def _url_and_ref(app_bundle_uri: str) -> tuple[str, str]:
    """Split `git+https://host/owner/repo@ref#fragment` into (`https://host/owner/repo`, ref).

    Exactly amplifier's own split: `GitSourceHandler._build_git_url` drops the `git+`
    prefix and the fragment, and `parsed.ref or "HEAD"` supplies the ref.
    """
    uri = app_bundle_uri.split("#", 1)[0].removeprefix("git+")
    scheme, _, rest = uri.partition("://")
    path, at, ref = rest.rpartition("@")
    if not at:  # no ref in the URI: amplifier's own default
        path, ref = rest, "HEAD"
    return f"{scheme}://{path}", ref


def cache_dir_name(app_bundle_uri: str) -> str:
    """The directory name amplifier caches this URI under: `<repo>-<16 hex>`.

    Derived, not guessed: `amplifier_foundation/sources/git.py::_get_cache_path` names it
    `sha256(f"{git_url}@{ref}").hexdigest()[:16]` with `git_url` carrying neither the
    `git+` prefix nor the `#subdirectory=` fragment. Verified against this device
    (2026-09-06): this function returns `amplifier-bundle-memory-450b259c7cb6895f`, which
    is the directory `~/.amplifier/cache/` actually holds.

    Derivation is preferred over "scan every clone and match its `origin`" because it
    answers even when the cache is absent (the install case). `bundle_cache_dirs` still
    falls back to an `origin` match, because a URI spelled differently from the one this
    library pins would otherwise refresh nothing and say nothing - which is the precise
    silence this whole section exists to end.
    """
    url, ref = _url_and_ref(app_bundle_uri)
    key = hashlib.sha256(f"{url}@{ref}".encode()).hexdigest()[:16]
    return f"{url.rstrip('/').rsplit('/', 1)[-1]}-{key}"


def bundle_cache_dirs(
    app_bundle_uri: str, amplifier_home: str | os.PathLike[str] | None = None
) -> list[Path]:
    """Every cache clone the modules and skills of this bundle are loaded from.

    Two locations, both real on this device: `<home>/cache/<name>-<hash>` (modules,
    context, behaviors) and `<home>/cache/skills/<name>-<hash>` (the slash commands).
    Only directories that exist are returned; an empty list means "nothing installed
    here", which `update` answers with the `amplifier bundle add` path.
    """
    root = _amplifier_dir(amplifier_home)
    name = cache_dir_name(app_bundle_uri)
    parents = [root / "cache", root / "cache" / "skills"]
    found = [parent / name for parent in parents if (parent / name).is_dir()]
    if found:
        return found

    # Fallback: the URI is spelled differently from the one that made the clone (a
    # different ref, or an https/ssh spelling). Match the clone's own `origin` instead.
    url, _ = _url_and_ref(app_bundle_uri)
    repo = url.rstrip("/").rsplit("/", 1)[-1]
    wanted = _same_remote(url)
    for parent in parents:
        if not parent.is_dir():
            continue
        for candidate in sorted(parent.glob(f"{repo}-*")):
            if candidate.is_dir() and _origin_url(candidate) == wanted:
                found.append(candidate)
    return found


def _same_remote(url: str) -> str:
    """One spelling for comparing remotes: no `file://`, no `.git`, no trailing slash.

    `git clone /path/to/repo` records the bare path as `origin` even when the URI that
    named it said `file:///path/to/repo`; https URLs are unaffected.
    """
    return url.removeprefix("file://").rstrip("/").removesuffix(".git")


def _origin_url(clone: Path) -> str | None:
    """`git -C <clone> remote get-url origin`, normalised, or None when not a clone."""
    proc = _git.git(["remote", "get-url", "origin"], cwd=clone, check=False)
    if proc.returncode != 0 or not proc.stdout.strip():
        return None
    return _same_remote(proc.stdout.strip())


def commit_of_cache(cache_dir: str | os.PathLike[str]) -> str | None:
    """The commit a cache clone is sitting at, or None when it is not a git clone.

    None is a real answer, not a failure: `amplifier bundle add` may one day cache a
    zip or an http source, and `update` falls back to remove/add for exactly that.
    """
    path = Path(cache_dir)
    if not path.is_dir():
        return None
    proc = _git.git(["rev-parse", "HEAD"], cwd=path, check=False)
    if proc.returncode != 0:
        return None
    return proc.stdout.strip() or None


def amplifier_env_python() -> Path | None:
    """The python of the environment the `amplifier` CLI runs in, or None.

    `shutil.which("amplifier")` -> resolve the symlink (`~/.local/bin/amplifier` points
    into `~/.local/share/uv/tools/amplifier/bin/`) -> that directory's `python`. This is
    the interpreter whose `site-packages` holds the `amplifier_memory` the *modules*
    import - a different copy from the one running this code.
    """
    exe = shutil.which("amplifier")
    if exe is None:
        return None
    bin_dir = Path(exe).resolve().parent
    for name in ("python", "python3", "python.exe"):
        candidate = bin_dir / name
        if candidate.exists():
            return candidate
    return None


def _dist_info_direct_urls(python: Path) -> list[Path]:
    """Every `amplifier_memory-*.dist-info/direct_url.json` in that python's env."""
    venv = python.parent.parent
    patterns = (
        "lib/python*/site-packages/amplifier_memory-*.dist-info/direct_url.json",
        "Lib/site-packages/amplifier_memory-*.dist-info/direct_url.json",
    )
    return sorted(path for pattern in patterns for path in venv.glob(pattern))


def commit_of_env_library(python: str | os.PathLike[str] | None) -> str | None:
    """The commit of the `amplifier_memory` installed in that python's environment.

    Where uv records it: the distribution's `direct_url.json` (PEP 610), written by the
    installer next to `METADATA` in `site-packages/amplifier_memory-<version>.dist-info/`.
    Read on this device it says
    `{"url": "https://github.com/bkrabach/amplifier-bundle-memory",
      "vcs_info": {"vcs": "git", "commit_id": "0f7e0fc\u2026", "requested_revision": "main"}}`.
    This is the same record `installed_commit()` reads for *this* process's own install;
    the difference is whose environment is asked.

    None when there is no such install, or when it was made from a working tree (no
    `direct_url.json`): not knowable is reported, never guessed.
    """
    if python is None:
        return None
    for direct_url in _dist_info_direct_urls(Path(python)):
        try:
            raw = json.loads(direct_url.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        commit = raw.get("vcs_info", {}).get("commit_id")
        if commit:
            return str(commit)
    return None


def installed_commits(
    *,
    app_bundle_uri: str = _APP_URI,
    amplifier_home: str | os.PathLike[str] | None = None,
    env_python: str | os.PathLike[str] | None | object = _UNSET_PYTHON,
) -> dict[str, str | None]:
    """The commit of each of the three installed things. None means "not found".

    Reads only: `git rev-parse` in a clone, a JSON file in a venv, and this process's own
    distribution metadata. Every input is injectable so a test never reads this device.

    The bundle cache is one leg when its clones agree, and one leg per clone when they do
    not - a `cache/` and a `cache/skills/` at different commits is exactly the kind of
    half-updated device this row exists to name.
    """
    legs: dict[str, str | None] = {UV_TOOL: installed_commit()}

    dirs = bundle_cache_dirs(app_bundle_uri, amplifier_home)
    commits = {directory: commit_of_cache(directory) for directory in dirs}
    if not commits:
        legs[BUNDLE_CACHE] = None
    elif len(set(commits.values())) == 1:
        legs[BUNDLE_CACHE] = next(iter(commits.values()))
    else:
        for directory, commit in commits.items():
            legs[f"{BUNDLE_CACHE} ({directory.parent.name}/)"] = commit

    python = amplifier_env_python() if env_python is _UNSET_PYTHON else env_python
    legs[ENV_LIBRARY] = commit_of_env_library(python if python is None else Path(str(python)))
    return legs


def update_check(
    installed: str | None | Mapping[str, str | None], remote_sha: str | None
) -> DoctorRow:
    """cli.v2 Core 5's update check, as a pure function of what is installed vs the remote.

    `installed` is a mapping of leg name -> commit (`installed_commits()`), or a single
    sha for the one-leg question. Behind -> WARN naming WHICH leg is behind and the
    remedy. All legs current -> OK naming all of them. A leg that cannot be found, or a
    remote that cannot be read -> INFO "not checkable". Never RED: an update check that
    cannot run is not a broken store, and a missing venv is not a corrupt one.
    """
    legs: dict[str, str | None] = (
        {UV_TOOL: installed} if installed is None or isinstance(installed, str) else dict(installed)
    )
    if remote_sha is None:
        return DoctorRow(
            "update",
            INFO,
            f"not checkable \u2014 {REPO_URL}@{PINNED_REF} could not be read "
            "(offline, or not a git install)",
        )

    known = {name: sha for name, sha in legs.items() if sha}
    missing = [name for name, sha in legs.items() if not sha]
    absent = ", ".join(f"{name} not found" for name in missing)
    if not known:
        return DoctorRow(
            "update",
            INFO,
            f"not checkable \u2014 the installed commit could not be read ({absent or 'no install'})",
        )

    behind = [
        f"{name} {sha[:SHORT]} behind {PINNED_REF} {remote_sha[:SHORT]}"
        for name, sha in known.items()
        if sha != remote_sha
    ]
    if behind:
        tail = f"; {absent}" if absent else ""
        return DoctorRow(
            "update",
            WARN,
            f"behind \u2014 {'; '.join(behind)}{tail}; remedy: `amplifier-memory update`",
        )

    current = " \u00b7 ".join(f"{name} {sha[:SHORT]}" for name, sha in known.items())
    if missing:
        return DoctorRow(
            "update", INFO, f"{current} == {PINNED_REF}; {absent} \u2014 not checkable"
        )
    return DoctorRow("update", OK, f"current ({current} == {PINNED_REF})")


# --------------------------------------------------------------------------- doctor


_UNSET = object()


#: cli.v2 §5's own row: "`MEMORY.md` well-formed — every line parses as store.v2 §3 and
#: decodes as UTF-8, or FAIL naming the line or byte offset and the last commit whose
#: file parsed clean". Its own row, not a clause of the `store` row: "the store is a git
#: repo" and "its contents parse" are different questions with different remedies, and
#: reading one answer for both is how a corrupt file hid behind a healthy-looking store.
WELLFORMED_ROW = "MEMORY.md well-formed"


def _wellformed_row(home: Path) -> DoctorRow:
    """cli.v2 §5's `MEMORY.md well-formed` row. Reads only; names the remedy on FAIL."""
    check = verify_store(home)
    return DoctorRow(WELLFORMED_ROW, OK if check.ok else FAIL, check.render())


def _store_rows(home: Path) -> list[DoctorRow]:
    """The store-side rows of cli.v2 §5, in the order the clause lists them."""
    report = status(home)
    memory_lines = len(_read_lines(home / "MEMORY.md"))
    topics = topic_files(home)
    caps = f"MEMORY.md {memory_lines}/{MEMORY_LINE_CAP}, topics {len(topics)}/{TOPIC_FILE_CAP}"
    cap_level = WARN if (memory_lines >= MEMORY_LINE_CAP or len(topics) >= TOPIC_FILE_CAP) else OK
    rows = [DoctorRow("caps", cap_level, caps), _wellformed_row(home)]

    if report.stale_topics:
        names = ", ".join(report.stale_topics)
        rows.append(
            DoctorRow(
                "stale topics",
                INFO,
                f"{len(report.stale_topics)} unread {STALE_TOPIC_DAYS} days ({names}) \u2014 "
                "keep? nothing is deleted automatically",
            )
        )
    else:
        rows.append(DoctorRow("stale topics", OK, f"0 unread {STALE_TOPIC_DAYS} days"))

    items = inbox.parse(_read_lines(home / inbox.INBOX))
    rows.append(DoctorRow("inbox", OK, f"{len(items)} pending, oldest {_oldest(items)}"))
    return rows


def _oldest(items: list[inbox.Suggestion]) -> str:
    """The oldest inbox entry's date, and how close it is to the 30-day drop (Core 6).

    suggestions.v1 §4 dates every item, so this is read off the file rather than guessed.
    """
    if not items:
        return "n/a (inbox empty)"
    dates = sorted(item.date for item in items)
    return f"{dates[0]} (dropped unreviewed after {inbox.EXPIRY_DAYS} days)"


#: cli.v2 §5 / suggestions.v1 Core 8: the two Phase 2 rows.
TIMER_ROW = "suggest timer"
SUBSTRATE_ROW = "substrate"


def timer_row(
    *,
    home: str | os.PathLike[str] | None = None,
    runner: service.Runner | None = None,
    config_dir: str | os.PathLike[str] | None = None,
    platform: str | None = None,
) -> DoctorRow:
    """cli.v2 §5: suggest timer installed · enabled · last run · last outcome.

    Reads only — `service.status` runs `systemctl --user is-enabled`, which is a query,
    and the last run comes out of `suggest.log`, which the job wrote. The row goes WARN,
    never FAIL: a machine with no timer is a machine where Phase 1 still works, and a
    degraded last run is a report, not a broken store (cli.v2 Core 5: "Exit code is
    nonzero only on failed checks").
    """
    state = service.status(runner=runner, config_dir=config_dir, platform=platform, home=home)
    if not state.installed:
        return DoctorRow(
            TIMER_ROW,
            INFO,
            "not installed \u2014 the daily pass runs only when a timer is installed; "
            "remedy: `amplifier-memory service install`",
        )
    enabled = "enabled" if state.enabled else "NOT enabled"
    last = state.last_run or "never run"
    outcome = state.last_status or "n/a"
    # The unit is NAMED, and named off disk (`ServiceStatus.unit_name` reads `units`,
    # which holds only files that exist). A row that says "installed · enabled" without
    # it left the steward unable to tell WHICH timer was answering on 2026-09-07 - the
    # pre-v3 device-wide one, as it turned out, not the instanced one `init` had printed.
    detail = (
        f"installed \u00b7 {enabled} \u00b7 unit {state.unit_name} \u00b7 last run {last} "
        f"\u00b7 last outcome {outcome}"
    )
    if state.enabled and (state.last_status or "ok").startswith("ok"):
        return DoctorRow(TIMER_ROW, OK, detail)
    return DoctorRow(TIMER_ROW, WARN, detail)


#: suggestions.v1 Core 8 (bounded cost, *visible*): which model the job's LLM calls use.
LLM_ROW = "llm judge"


#: cli.v3 §5's own words for a judge nobody named, and the name of the default itself.
#: Both are the library's constants, re-exported here rather than re-declared: the judge
#: sentence is composed once, in `suggest.Judge.render`, and this row prints that. Three
#: surfaces read these names off this module - the row, the kit's probe, and the test -
#: and all three now see the same strings the daily job's own log line uses.
INHERITED = suggest.INHERITS_DEFAULT
APP_DEFAULT = suggest.APP_DEFAULT


def last_cost(home: str | os.PathLike[str] | None = None) -> str:
    """cli.v3 §5: the last run's **measured** cost, read off `suggest.log`.

    Measured, not estimated: the number of model calls the run made and the provider (and
    model) it was billed to are what the job itself wrote after doing the work
    (suggestions.v2 §9). "no run yet" is a real answer and is said as one.
    """
    line = last_log_line(home)
    if not line:
        return "no run yet, so no measured cost"
    fields = parse_log_line(line)
    provider = fields.get("provider", "?")
    model = f" model={fields.get('model')}" if fields.get("model") else ""
    return (
        f"last run {fields.get('ts', '?')} cost {fields.get('calls', '?')} model call(s) "
        f"on provider={provider}{model}"
    )


def llm_row(
    config: llm_config.LlmConfig | None = None,
    *,
    home: str | os.PathLike[str] | None = None,
    help_text: str | None = None,
    help_runner: Callable[[], str] | None = None,
) -> DoctorRow:
    """cli.v3 §5's judge row: which provider and model the daily pass will use — or whose.

    One call into the library and two additions of this surface's own. The sentence is
    `suggest.judge_detail` — the same one the daily job composes (suggestions.v2 Core 8,
    AGENTS.md rule 11) — so `doctor` and the job can never name different models on the
    same day. This row adds the **last run's measured cost**, which the clause asks for
    and the job's own sentence does not carry, and the remedy for an unusable file.

    Three states, and the middle one is the point of the clause:

    * **configured** — `config.yaml` names a provider (and maybe a model): print them.
    * **role** — nothing is named, but this host resolves roles: the recorded role and
      the flag it resolves through. While `amplifier run` documents no `--model-role`,
      this arm cannot fire on this device and the sentence says so in the next one.
    * **inherited** — the pass runs on the app's default. The row says `inherits the
      app's default`, names that default, and carries the measured cost, so a bill
      nobody chose is visible instead of silent.

    An unusable `config.yaml` is WARN, never FAIL: the run still happens and still
    inherits (suggestions.v2 Core 10), so nothing is broken — but the user believes they
    chose a model and did not, and the judge sentence carries the reason through its own
    origin (`LlmConfig.source`).

    Reads two files and writes none: this instance's `config.yaml` (store.v3 §2 — it
    travels with the instance) and the last line of its `suggest.log`. `help_text` and
    `help_runner` are `suggest.host_help`'s injection points, passed straight through so
    a probe can ask for a named state without shelling out to `amplifier run --help`.
    """
    settings = llm_config.load(home) if config is None else config
    judge = suggest.judge_detail(settings, home=home, help_text=help_text, help_runner=help_runner)
    detail = f"{judge} \u00b7 {last_cost(home)}"
    if settings.reason:
        return DoctorRow(LLM_ROW, WARN, f"{detail} \u00b7 remedy: fix or delete {settings.path}")
    return DoctorRow(LLM_ROW, OK, detail)


def substrate_row(base_path: str | os.PathLike[str] | None = None) -> DoctorRow:
    """cli.v2 §5 / suggestions.v1 Core 2: the recorded-session capture the job reads.

    A **required** dependency of Phase 2 and of nothing else, so its absence is WARN with
    the consequence named — the daily pass will fail open and propose nothing — never a
    failed check.
    """
    root = substrate_root(base_path)
    if not root.is_dir():
        return DoctorRow(
            SUBSTRATE_ROW,
            WARN,
            f"missing at {root} \u2014 `suggest` will record `degraded:substrate missing` and "
            "propose nothing; it is the context-intelligence bundle's local session capture",
        )
    if not os.access(root, os.R_OK):
        return DoctorRow(SUBSTRATE_ROW, WARN, f"present at {root} but not readable by this user")
    projects = sum(1 for child in root.glob("*/sessions") if child.is_dir())
    return DoctorRow(SUBSTRATE_ROW, OK, f"readable at {root} ({projects} project(s) recorded)")


def doctor(
    home: str | os.PathLike[str] | None = None,
    *,
    installed_sha: str | None | object = _UNSET,
    remote_sha: str | None | object = _UNSET,
    base_path: str | os.PathLike[str] | None = None,
    service_runner: service.Runner | None = None,
    config_dir: str | os.PathLike[str] | None = None,
    llm: llm_config.LlmConfig | None = None,
) -> DoctorReport:
    """cli.v2 Core 5. Reads only; never writes, stages, or commits.

    `installed_sha` and `remote_sha` are injectable so the update check can be
    exercised in all three states with no network. `base_path`, `service_runner` and
    `config_dir` are injectable for the same reason on the Phase 2 rows: a test must be
    able to ask about a timer without touching this device's own units. `llm` is the
    instance's LLM-call config, injectable so a test never depends on this device's own
    `config.yaml` (`llm_config.load` refuses to read it under pytest anyway).

    Every row is asked about **this instance** (`home`): its timer's unit name carries
    the instance (cli.v3 §6), and its `config.yaml` and `suggest.log` travel with it.
    """
    path = store_home(home)
    rows: list[DoctorRow] = []

    has_memory = (path / "MEMORY.md").is_file()
    is_repo = path.is_dir() and _git.is_repo(path)
    if has_memory and is_repo:
        rows.append(DoctorRow("store", OK, f"present and a git repo at {path}"))
        rows.extend(_store_rows(path))
    else:
        missing = "no MEMORY.md" if not has_memory else "not a git repository"
        rows.append(
            DoctorRow("store", FAIL, f"{missing} at {path}; remedy: `amplifier-memory init`")
        )
        rows.append(DoctorRow("caps", INFO, "skipped: no store to measure"))
        rows.append(DoctorRow(WELLFORMED_ROW, INFO, "skipped: no store to read"))
        rows.append(DoctorRow("stale topics", INFO, "skipped: no store to measure"))
        rows.append(DoctorRow("inbox", INFO, "skipped: no store to measure"))

    rows.append(timer_row(home=path, runner=service_runner, config_dir=config_dir))
    rows.append(substrate_row(base_path))
    rows.append(llm_row(llm, home=path))
    installed = installed_commits() if installed_sha is _UNSET else installed_sha
    remote = remote_commit() if remote_sha is _UNSET else remote_sha
    rows.append(
        update_check(
            installed if isinstance(installed, str | Mapping) or installed is None else None,
            remote if isinstance(remote, str) or remote is None else None,
        )
    )
    return DoctorReport(home=path, rows=rows)


# --------------------------------------------------------------------------- service / suggest / update

SERVICE_VERBS = service.VERBS

# The steps `update` performs, in order. Named here, in the library, so the CLI prints
# the plan rather than inventing one; `update.py` executes exactly these and no others.
# Each argv is verified against its own `--help` by tests/test_update.py, which prints
# the help it relied on (AGENTS.md rule 5).
#
# Steps 2 and 3 refresh the two installed things `update` used to leave behind - the
# cache clone the modules and skills load from, and the library inside the amplifier
# venv that those modules import (see "the three installed things" above). The
# remove-then-add is kept as step 2's fallback only: measured on this device
# (2026-09-06) `amplifier bundle add` re-registers the URI without moving the cache
# clone off its old commit, `amplifier bundle update` cannot reach an app bundle
# registered by URI at all, and the root-bundle URI composes nothing (a self-include
# the loader skips). All three findings are evidenced in tests/smoke/ and in
# `docs/workflow/CHECK-RECORD.md`.

#: cli.v2 Core 7's last requirement, in one place. `update` prints it every run.
STALE_NOTE = (
    "Note: sessions started before the refresh keep the old module code until they "
    "restart. Nothing is hot-reloaded."
)

UPDATE_STEPS = (
    f"uv tool upgrade amplifier-memory   (the CLI, from {REPO_URL}@{PINNED_REF})",
    (
        f"git fetch origin && git reset --hard origin/{PINNED_REF} in every bundle cache "
        "clone (~/.amplifier/cache/ and cache/skills/) - what sessions load modules and "
        f"skills from; a clone that is not a git checkout falls back to `amplifier bundle "
        f"remove {_APP_URI} --app` then `add`"
    ),
    (
        "uv pip install --python <the amplifier venv's python> --refresh "
        f"--reinstall-package amplifier-memory 'amplifier-memory @ git+{REPO_URL}@{PINNED_REF}' "
        "  (the library those modules import; skipped with a warning when no amplifier "
        "venv is found)"
    ),
    "restart the suggest timer, if one is installed (Phase 2 only)",
    "run `amplifier-memory doctor`",
)


def service_status(
    verb: str,
    *,
    runner: service.Runner | None = None,
    config_dir: str | os.PathLike[str] | None = None,
    executable: str | os.PathLike[str] | None = None,
    platform: str | None = None,
    home: str | os.PathLike[str] | None = None,
) -> str:
    """cli.v3 §6, as one string: **this instance's** suggest timer, managed.

    The whole behaviour lives in `service.py`; this is the name the CLI, `update` and the
    conformance kit already call, kept so one clause has one entry point. Every argument
    is injectable so nothing in a test reaches this device's own units.

    `home=None` is resolved here (store.v3 §1) rather than left un-instanced: every unit
    this verb touches then carries the instance in its name (§6), which is what stops one
    instance's `uninstall` from reaching another's timer. `service.py` keeps the
    un-instanced name for `home=None` because a pre-v3 device timer still has it.
    """
    return service.run_verb(
        verb,
        runner=runner,
        config_dir=config_dir,
        executable=executable,
        platform=platform,
        home=store_home(home),
    )


def suggest_status(home: str | os.PathLike[str] | None = None) -> str:
    """suggestions.v1 Core 9, read back: what the last run of the daily pass reported.

    A report, not the run — `amplifier-memory suggest` performs the pass
    (`amplifier_memory.run_suggest`). This is what `doctor` and a curious human read
    afterwards, and "never run" is a real answer rather than an empty string.
    """
    line = last_log_line(home)
    if line is None:
        return (
            "the suggestion pass has not run on this device yet.\n"
            "Install the daily timer with `amplifier-memory service install`, or run it once "
            "now with `amplifier-memory suggest`."
        )
    fields = parse_log_line(line)
    return (
        f"last run {fields.get('ts', '?')}: {fields.get('sessions', '?')} session(s) read, "
        f"{fields.get('proposed', '?')} proposed, {fields.get('rejected', '?')} rejected by "
        f"verification, {fields.get('dropped_stale', '?')} dropped as stale, "
        f"{fields.get('calls', '?')} model call(s), status {fields.get('status', '?')}.\n"
        f"{line}"
    )


def update_plan() -> str:
    """cli.v2 Core 7, as text: the four steps `update` runs, in order.

    `amplifier_memory.run_update` performs exactly these steps and prints this plan
    above its results, so the plan and the run can never describe different things.
    """
    steps = "\n".join(f"  {i}. {step}" for i, step in enumerate(UPDATE_STEPS, start=1))
    return f"`amplifier-memory update` runs, in order:\n{steps}\n\n{STALE_NOTE}"


__all__ = [
    "APP_DEFAULT",
    "BUNDLE_CACHE",
    "ENV_LIBRARY",
    "INHERITED",
    "LLM_ROW",
    "PINNED_REF",
    "REPO_URL",
    "SERVICE_VERBS",
    "STALE_NOTE",
    "SUBSTRATE_ROW",
    "TIMER_ROW",
    "UPDATE_STEPS",
    "UV_TOOL",
    "DoctorReport",
    "DoctorRow",
    "amplifier_env_python",
    "bundle_cache_dirs",
    "cache_dir_name",
    "commit_of_cache",
    "commit_of_env_library",
    "doctor",
    "installed_commit",
    "installed_commits",
    "last_cost",
    "llm_row",
    "remote_commit",
    "service_status",
    "substrate_row",
    "suggest_status",
    "timer_row",
    "update_check",
    "update_plan",
]
