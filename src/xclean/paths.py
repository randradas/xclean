"""XDG folders, on macOS and Linux alike.

Config holds settings and the client ID. Data holds the progress store, reports, and the
fallback token file. State holds logs. Tokens never go in config: it is often a dotfiles repo.
"""

import os
from pathlib import Path

APP = "xclean"


def _base(var: str, default: str) -> Path:
    value = os.environ.get(var, "")
    # XDG says relative paths are invalid and must be ignored.
    if value and Path(value).is_absolute():
        return Path(value)
    return Path.home() / default


def config_dir() -> Path:
    return _base("XDG_CONFIG_HOME", ".config") / APP


def data_dir() -> Path:
    return _base("XDG_DATA_HOME", ".local/share") / APP


def state_dir() -> Path:
    return _base("XDG_STATE_HOME", ".local/state") / APP


def ensure(path: Path) -> Path:
    """Create the folder if missing, readable only by the user."""
    path.mkdir(mode=0o700, parents=True, exist_ok=True)
    path.chmod(0o700)
    return path
