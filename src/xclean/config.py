"""User settings in the config folder. No secrets here: it is often a dotfiles repo."""

import tomllib
from dataclasses import dataclass
from pathlib import Path

DEFAULT_REDIRECT_URI = "http://127.0.0.1:8765/callback"


@dataclass(frozen=True)
class Config:
    client_id: str = ""
    redirect_uri: str = DEFAULT_REDIRECT_URI


def load(path: Path) -> Config:
    try:
        data = tomllib.loads(path.read_text())
    except FileNotFoundError:
        return Config()
    return Config(
        client_id=str(data.get("client_id", "")),
        redirect_uri=str(data.get("redirect_uri", DEFAULT_REDIRECT_URI)),
    )


def save(path: Path, config: Config) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(f'client_id = "{config.client_id}"\nredirect_uri = "{config.redirect_uri}"\n')
