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
def review() -> None:
    """Review pending suggestions (Phase 2). An empty inbox says so."""
    try:
        click.echo(amplifier_memory.review())
    except amplifier_memory.MemoryError as exc:
        _die(exc)


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
    """Manage the Phase 2 suggest timer. Phase 1 has no service."""
    click.echo(amplifier_memory.service_status(verb))


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
def suggest() -> None:
    """Run the daily suggestion pass (Phase 2)."""
    click.echo(amplifier_memory.suggest_status())


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
