"""`amplifier-memory` — click over the library, and nothing else (cli.v3 Core 9).

This file imports exactly two things: `click` and `amplifier_memory`. That is the
whole conformance statement for Core 9, and it is checked by
`tests/test_cli.py::test_cli_imports_only_click_and_the_library`, which greps this
file, and by the companion test that reaches every verb's behaviour with `click`
absent from `sys.modules`.

Every command body below is: parse -> one library call -> print -> exit code. A
wrapper that carries logic is a defect (cli.v3 Core 9), so the rendering of a
report lives on the report (`StatusReport.render`), not here.

**`--home` (cli.v3 Core 1).** Every verb acts on the instance `--home` names; without
it the instance resolves as store.v3 §1 says (`$AMPLIFIER_MEMORY_HOME`, else
`~/.amplifier-memory`). It is declared **once, on the group**, which is what `--help`
shows — and `_Verbs.parse_args` lifts it out of the argument list wherever a human
actually typed it, so `amplifier-memory --home X status` and `amplifier-memory status
--home X` are the same command. The clause's own examples are written the second way
(`service uninstall --home <instance>`), and a flag that works in only one position is
a trap, not a surface.
"""

import click

import amplifier_memory

#: cli.v3 Core 1's flag, named by the library so the surface cannot drift from it.
HOME_FLAG = amplifier_memory.HOME_FLAG


def _die(exc: Exception) -> None:
    """One line on stderr, nonzero exit — the CLI's whole error contract."""
    click.echo(f"error: {exc}", err=True)
    raise SystemExit(1)


def _hoist_home(args: list[str]) -> list[str]:
    """cli.v3 Core 1: `--home` after the verb is the same as `--home` before it."""
    try:
        rest, home = amplifier_memory.split_home(args)
    except ValueError as exc:
        raise click.UsageError(str(exc)) from exc
    return rest if home is None else [HOME_FLAG, home, *rest]


class _Verbs(click.Group):
    """The eight verbs, `--home` in any position, and a one-line error for anything else."""

    def parse_args(self, ctx, args):
        return super().parse_args(ctx, _hoist_home(list(args)))

    def resolve_command(self, ctx, args):
        try:
            return super().resolve_command(ctx, args)
        except click.UsageError:
            click.echo(f"error: unknown verb {args[0]!r}; try `amplifier-memory --help`", err=True)
            ctx.exit(2)


@click.group(cls=_Verbs)
@click.option(
    HOME_FLAG,
    "home",
    metavar="INSTANCE",
    default=None,
    help="The memory instance to act on. Default: $AMPLIFIER_MEMORY_HOME, else "
    "~/.amplifier-memory. Works before or after the verb.",
)
@click.version_option(package_name="amplifier-memory")
@click.pass_context
def main(ctx: click.Context, home: str | None) -> None:
    """Look at the memory store from a shell: what is in it, why, and is it healthy."""
    ctx.obj = home


@main.command()
@click.option(
    "--no-timer",
    is_flag=True,
    help="Create the store only. For a host that must not run the daily suggestion pass.",
)
@click.pass_obj
def init(home: str | None, no_timer: bool) -> None:
    """Create the instance (a git repo) and install its daily suggest timer.

    This is the only setup step. A second run changes nothing.
    """
    click.echo(amplifier_memory.build_instance(home, timer=not no_timer).render())


@main.command()
@click.pass_obj
def status(home: str | None) -> None:
    """The numbers that say whether this is working: written, kept, forgotten."""
    click.echo(amplifier_memory.status(home).render())


@main.command()
@click.argument("memory_id")
@click.pass_obj
def why(home: str | None, memory_id: str) -> None:
    """Why memory MEMORY_ID exists: text, quote, session, writer, date."""
    try:
        click.echo(amplifier_memory.format_why(amplifier_memory.why(memory_id, home)))
    except amplifier_memory.MemoryError as exc:
        _die(exc)


@main.command()
@click.option("--list", "list_only", is_flag=True, help="Print the inbox and stop.")
@click.option("--accept", "accept_id", metavar="ID", help="Accept suggestion ID and exit.")
@click.option("--decline", "decline_id", metavar="ID", help="Decline suggestion ID and exit.")
@click.option("--skip", "skip_id", metavar="ID", help="Leave suggestion ID pending and exit.")
@click.pass_obj
def review(
    home: str | None, list_only: bool, accept_id: str, decline_id: str, skip_id: str
) -> None:
    """Review pending suggestions: accept, decline or skip. An empty inbox says so."""
    try:
        done = amplifier_memory.review_action(
            accept_id=accept_id, decline_id=decline_id, skip_id=skip_id, home=home
        )
        if done or list_only or not amplifier_memory.is_interactive():
            click.echo(done or amplifier_memory.render_pending(home))
            return
        _walk(home)
    except amplifier_memory.MemoryError as exc:
        _die(exc)


def _walk(home: str | None) -> None:
    """One keystroke per item, until the inbox runs out or the human quits (Core 6)."""
    for item in amplifier_memory.pending(home):
        click.echo(f"\n  {item.render_review()}")
        keys = click.Choice(amplifier_memory.REVIEW_KEYS, case_sensitive=False)
        choice = click.prompt(amplifier_memory.REVIEW_PROMPT, type=keys, default="s")
        if choice.lower() == "q":
            break
        click.echo(f"  {amplifier_memory.review_one(item.id, choice, home)}")
    click.echo(f"\n{amplifier_memory.render_pending(home).splitlines()[0]}")


@main.command()
@click.option(
    "--repair",
    is_flag=True,
    help="Restore a malformed MEMORY.md from the last commit whose lines parse, and commit "
    "it. Prints the diff. Without this flag `doctor` writes nothing.",
)
@click.pass_obj
def doctor(home: str | None, repair: bool) -> None:
    """Check the instance and this install. Never mutates unless --repair is given."""
    if repair:
        try:
            result = amplifier_memory.repair_store(home)
        except amplifier_memory.MemoryError as exc:
            _die(exc)
        click.echo(result.render())
        raise SystemExit(0)
    report = amplifier_memory.doctor(home)
    click.echo(report.render())
    raise SystemExit(report.exit_code)


@main.command()
@click.argument("verb", type=click.Choice(amplifier_memory.SERVICE_VERBS))
@click.pass_obj
def service(home: str | None, verb: str) -> None:
    """Manage this instance's daily suggest timer: install, uninstall, status (and the rest)."""
    try:
        click.echo(amplifier_memory.service_status(verb, home=home))
    except ValueError as exc:
        _die(exc)


# cli.v3 Core 7: one run is enough. `--after-upgrade` is how the upgraded binary is told
# that the process which re-executed it already ran the uv-tool step; it is hidden because
# it is that hand-off's word, not a thing a steward types.
@main.command()
@click.option(
    "--after-upgrade",
    is_flag=True,
    hidden=True,
    help="Internal: the uv-tool step already ran in the process that re-executed this one.",
)
@click.pass_obj
def update(home: str | None, after_upgrade: bool) -> None:
    """Refresh all three installed copies (tool, bundle cache, venv library), then doctor."""
    result = amplifier_memory.run_update(after_upgrade=after_upgrade, home=home)
    click.echo(result.render())
    raise SystemExit(result.exit_code)


@main.command()
@click.option("--last", is_flag=True, help="Print the last run's report and stop; run nothing.")
@click.pass_obj
def suggest(home: str | None, last: bool) -> None:
    """Run the daily suggestion pass. Exit 0 even when degraded (suggestions.v2 Core 10)."""
    if last:
        click.echo(amplifier_memory.suggest_status(home))
        return
    click.echo(amplifier_memory.run_suggest(home).log_line)


# cli.v3 Core 1: `upgrade` is an alias of `update`, and hidden so `--help` lists the
# eight verbs the clause names and nothing more.
main.add_command(
    click.Command(
        "upgrade",
        callback=update.callback,
        params=list(update.params),
        help=update.help,
        hidden=True,
    )
)


if __name__ == "__main__":  # pragma: no cover - the console script calls main() directly
    main()
