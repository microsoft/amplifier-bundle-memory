"""`amplifier-memory` — click over the library, and nothing else (cli.v2 Core 9).

This file imports exactly two things: `click` and `amplifier_memory`. That is the
whole conformance statement for Core 9, and it is checked by
`tests/test_cli.py::test_cli_imports_only_click_and_the_library`, which greps this
file, and by the companion test that reaches every verb's behaviour with `click`
absent from `sys.modules`.

Every command body below is: parse -> one library call -> print -> exit code. A
wrapper that carries logic is a defect (cli.v2 Core 9), so the rendering of a
report lives on the report (`StatusReport.render`), not here.
"""

import click

import amplifier_memory


def _die(exc: Exception) -> None:
    """One line on stderr, nonzero exit — the CLI's whole error contract."""
    click.echo(f"error: {exc}", err=True)
    raise SystemExit(1)


class _Verbs(click.Group):
    """An unknown verb is a one-line error and exit 2 (cli.v2 Core 1)."""

    def resolve_command(self, ctx, args):
        try:
            return super().resolve_command(ctx, args)
        except click.UsageError:
            click.echo(
                f"error: unknown verb {args[0]!r}; try `amplifier-memory --help`", err=True
            )
            ctx.exit(2)


@click.group(cls=_Verbs)
@click.version_option(package_name="amplifier-memory")
def main() -> None:
    """Look at the memory store from a shell: what is in it, why, and is it healthy."""


@main.command()
def init() -> None:
    """Create the store (a git repo). A second run changes nothing."""
    result = amplifier_memory.init()
    if result.existed:
        click.echo(f"store already exists at {result.home}; nothing changed")
        return
    click.echo(f"created {result.home}: {', '.join(result.created)} (commit {result.commit[:12]})")


@main.command()
def status() -> None:
    """The numbers that say whether this is working: written, kept, forgotten."""
    click.echo(amplifier_memory.status().render())


@main.command()
@click.argument("memory_id")
def why(memory_id: str) -> None:
    """Why memory MEMORY_ID exists: text, quote, session, writer, date."""
    try:
        click.echo(amplifier_memory.format_why(amplifier_memory.why(memory_id)))
    except amplifier_memory.MemoryError as exc:
        _die(exc)


@main.command()
@click.option("--list", "list_only", is_flag=True, help="Print the inbox and stop.")
@click.option("--accept", "accept_id", metavar="ID", help="Accept suggestion ID and exit.")
@click.option("--decline", "decline_id", metavar="ID", help="Decline suggestion ID and exit.")
@click.option("--skip", "skip_id", metavar="ID", help="Leave suggestion ID pending and exit.")
def review(list_only: bool, accept_id: str, decline_id: str, skip_id: str) -> None:
    """Review pending suggestions: accept, decline or skip. An empty inbox says so."""
    try:
        done = amplifier_memory.review_action(
            accept_id=accept_id, decline_id=decline_id, skip_id=skip_id
        )
        if done or list_only or not amplifier_memory.is_interactive():
            click.echo(done or amplifier_memory.render_pending())
            return
        _walk()
    except amplifier_memory.MemoryError as exc:
        _die(exc)


def _walk() -> None:
    """One keystroke per item, until the inbox runs out or the human quits (Core 6)."""
    for item in amplifier_memory.pending():
        click.echo(f"\n  {item.render_review()}")
        keys = click.Choice(amplifier_memory.REVIEW_KEYS, case_sensitive=False)
        choice = click.prompt(amplifier_memory.REVIEW_PROMPT, type=keys, default="s")
        if choice.lower() == "q":
            break
        click.echo(f"  {amplifier_memory.review_one(item.id, choice)}")
    click.echo(f"\n{amplifier_memory.render_pending().splitlines()[0]}")


@main.command()
@click.option(
    "--repair",
    is_flag=True,
    help="Restore a malformed MEMORY.md from the last commit whose lines parse, and commit "
    "it. Prints the diff. Without this flag `doctor` writes nothing.",
)
def doctor(repair: bool) -> None:
    """Check the store and this install. Never mutates unless --repair is given."""
    if repair:
        try:
            result = amplifier_memory.repair_store()
        except amplifier_memory.MemoryError as exc:
            _die(exc)
        click.echo(result.render())
        raise SystemExit(0)
    report = amplifier_memory.doctor()
    click.echo(report.render())
    raise SystemExit(report.exit_code)


@main.command()
@click.argument("verb", type=click.Choice(amplifier_memory.SERVICE_VERBS))
def service(verb: str) -> None:
    """Manage the daily suggest timer: install, uninstall, status (and the four systemctl verbs)."""
    try:
        click.echo(amplifier_memory.service_status(verb))
    except ValueError as exc:
        _die(exc)


# cli.v2 Core 7: one run is enough. `--after-upgrade` is how the upgraded binary is told
# that the process which re-executed it already ran the uv-tool step; it is hidden because
# it is that hand-off's word, not a thing a steward types.
@main.command()
@click.option(
    "--after-upgrade",
    is_flag=True,
    hidden=True,
    help="Internal: the uv-tool step already ran in the process that re-executed this one.",
)
def update(after_upgrade: bool) -> None:
    """Refresh all three installed copies (tool, bundle cache, venv library), then doctor."""
    result = amplifier_memory.run_update(after_upgrade=after_upgrade)
    click.echo(result.render())
    raise SystemExit(result.exit_code)


@main.command()
@click.option("--last", is_flag=True, help="Print the last run's report and stop; run nothing.")
def suggest(last: bool) -> None:
    """Run the daily suggestion pass. Exit 0 even when degraded (suggestions.v1 Core 10)."""
    if last:
        click.echo(amplifier_memory.suggest_status())
        return
    click.echo(amplifier_memory.run_suggest().log_line)


# cli.v2 Core 1: `upgrade` is an alias of `update`, and hidden so `--help` lists the
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
