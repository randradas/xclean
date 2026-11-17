from pathlib import Path

import pytest

from xclean import paths


@pytest.fixture
def home(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.setenv("HOME", str(tmp_path))
    for var in ("XDG_CONFIG_HOME", "XDG_DATA_HOME", "XDG_STATE_HOME"):
        monkeypatch.delenv(var, raising=False)
    return tmp_path


def test_defaults_follow_xdg_under_home(home: Path) -> None:
    assert paths.config_dir() == home / ".config" / "xclean"
    assert paths.data_dir() == home / ".local" / "share" / "xclean"
    assert paths.state_dir() == home / ".local" / "state" / "xclean"


def test_xdg_variables_override_defaults(home: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("XDG_CONFIG_HOME", str(home / "cfg"))
    monkeypatch.setenv("XDG_DATA_HOME", str(home / "dat"))
    monkeypatch.setenv("XDG_STATE_HOME", str(home / "st"))
    assert paths.config_dir() == home / "cfg" / "xclean"
    assert paths.data_dir() == home / "dat" / "xclean"
    assert paths.state_dir() == home / "st" / "xclean"


@pytest.mark.parametrize("value", ["", "relative/dir"])
def test_empty_or_relative_xdg_values_are_ignored(
    home: Path, monkeypatch: pytest.MonkeyPatch, value: str
) -> None:
    monkeypatch.setenv("XDG_DATA_HOME", value)
    assert paths.data_dir() == home / ".local" / "share" / "xclean"


def test_dirs_are_not_created_on_lookup(home: Path) -> None:
    paths.data_dir()
    assert not (home / ".local").exists()


def test_ensure_creates_dir_private(home: Path) -> None:
    path = paths.ensure(paths.data_dir())
    assert path.is_dir()
    assert path.stat().st_mode & 0o777 == 0o700
