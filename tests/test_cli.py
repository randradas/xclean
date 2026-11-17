import pytest
from typer.testing import CliRunner

from xclean import __version__, auth, config, paths
from xclean.cli import app
from xclean.xclient import Me, XClient

runner = CliRunner()


def test_version_flag_prints_version() -> None:
    result = runner.invoke(app, ["--version"])
    assert result.exit_code == 0
    assert __version__ in result.output


def test_login_needs_client_id_the_first_time() -> None:
    result = runner.invoke(app, ["login"])
    assert result.exit_code == 1
    assert "--client-id" in result.output


def test_login_saves_client_id_and_greets(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[str] = []
    monkeypatch.setattr(auth, "login", lambda client_id, *a, **k: calls.append(client_id))
    monkeypatch.setattr(
        XClient, "me", lambda self: Me(id="1", username="someone", pinned_post_id=None)
    )
    result = runner.invoke(app, ["login", "--client-id", "cid"])
    assert result.exit_code == 0, result.output
    assert calls == ["cid"]
    assert "@someone" in result.output
    assert config.load(paths.config_dir() / "config.toml").client_id == "cid"


def test_logout() -> None:
    result = runner.invoke(app, ["logout"])
    assert result.exit_code == 0
    assert "Logged out" in result.output
