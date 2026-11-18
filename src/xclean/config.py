"""User settings in the config folder. No secrets here: it is often a dotfiles repo."""

import json
import tomllib
from dataclasses import dataclass
from pathlib import Path

DEFAULT_REDIRECT_URI = "http://127.0.0.1:8765/callback"


class ConfigError(Exception):
    """The config file cannot be read. The message is shown as is."""


@dataclass(frozen=True)
class Config:
    client_id: str = ""
    redirect_uri: str = DEFAULT_REDIRECT_URI


def load(path: Path) -> Config:
    try:
        data = tomllib.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return Config()
    except (tomllib.TOMLDecodeError, UnicodeDecodeError) as e:
        raise ConfigError(f"cannot read {path}: {e}; fix or delete it") from None
    return Config(
        client_id=str(data.get("client_id", "")),
        redirect_uri=str(data.get("redirect_uri", DEFAULT_REDIRECT_URI)),
    )


def save(path: Path, config: Config) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = [f"{key} = {_toml_string(value)}" for key, value in vars(config).items()]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _toml_string(value: str) -> str:
    """A JSON string is a TOML basic string, except TOML also forbids a raw DEL."""
    return json.dumps(value, ensure_ascii=False).replace("\x7f", "\\u007f")
