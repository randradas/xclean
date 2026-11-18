"""Command line runner. Thin layer over the core. Only this module prints."""

import webbrowser
from pathlib import Path
from typing import Annotated

import typer
from rich.console import Console

from xclean import __version__, auth, config, paths
from xclean.tokens import TokenStore, UserTokens, default_token_store
from xclean.xclient import XClient, XError

app = typer.Typer(no_args_is_help=True, help="Bulk-remove your own X content and activity.")
out = Console()
err = Console(stderr=True)


def _show_version(value: bool) -> None:
    if value:
        out.print(f"xclean {__version__}")
        raise typer.Exit()


@app.callback()
def root(
    version: Annotated[
        bool,
        typer.Option("--version", callback=_show_version, is_eager=True, help="Show version."),
    ] = False,
) -> None:
    """Bulk-remove your own X content and activity."""


def _fail(message: str) -> typer.Exit:
    err.print(f"[red]Error:[/red] {message}")
    return typer.Exit(1)


def _config_path() -> Path:
    return paths.config_dir() / "config.toml"


def _config() -> config.Config:
    try:
        return config.load(_config_path())
    except config.ConfigError as e:
        raise _fail(str(e)) from None


def _token_store() -> TokenStore:
    return default_token_store(paths.data_dir(), warn=lambda m: err.print(f"[yellow]{m}[/yellow]"))


def _client(cfg: config.Config) -> XClient:
    if not cfg.client_id:
        raise _fail("not set up; run `xclean login --client-id <your X app client ID>`")
    return XClient(UserTokens(_token_store(), cfg.client_id))


@app.command()
def login(
    client_id: Annotated[
        str | None, typer.Option(help="Client ID of your X app. Needed the first time.")
    ] = None,
) -> None:
    """Log in to X in the browser. Remembered until you log out."""
    cfg = _config()
    if client_id:
        cfg = config.Config(client_id=client_id, redirect_uri=cfg.redirect_uri)
        config.save(_config_path(), cfg)
    if not cfg.client_id:
        raise _fail("first time: run `xclean login --client-id <your X app client ID>`")

    def open_browser(url: str) -> None:
        out.print("Opening your browser to log in to X. If it does not open, visit:")
        out.print(url, soft_wrap=True)
        webbrowser.open(url)

    def ask_url(_: str) -> str:
        return str(typer.prompt("Paste the full address your browser ended on"))

    try:
        auth.login(cfg.client_id, cfg.redirect_uri, _token_store(), open_browser, ask_url)
        me = _client(cfg).me()
    except (auth.LoginError, XError) as e:
        raise _fail(str(e)) from None
    out.print(f"Logged in as [bold]@{me.username}[/bold].")


@app.command()
def logout() -> None:
    """Log out and forget the login on this machine."""
    cfg = _config()
    auth.logout(_token_store(), cfg.client_id)
    out.print("Logged out.")


def main() -> None:
    app()
