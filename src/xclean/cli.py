"""Command line runner. Thin layer over the core."""

from typing import Annotated

import typer

from xclean import __version__

app = typer.Typer(no_args_is_help=True, help="Bulk-remove your own X content and activity.")


def _show_version(value: bool) -> None:
    if value:
        typer.echo(f"xclean {__version__}")
        raise typer.Exit()


@app.callback()
def root(
    version: Annotated[
        bool,
        typer.Option("--version", callback=_show_version, is_eager=True, help="Show version."),
    ] = False,
) -> None:
    """Bulk-remove your own X content and activity."""


def main() -> None:
    app()
