import base64
import hashlib
import os
import socket
import sys
import threading
from pathlib import Path
from urllib.parse import parse_qs, urlparse

import httpx
import pytest
import respx

from xclean import config
from xclean.auth import (
    LoginError,
    code_from_callback,
    login,
    logout,
    start_login,
    wait_for_callback,
)
from xclean.tokens import FileTokenStore, MemoryTokenStore, TokenSet
from xclean.xclient import REVOKE_URL, TOKEN_URL

REDIRECT = "http://127.0.0.1:8765/callback"


def test_authorize_url_uses_pkce_s256() -> None:
    req = start_login("cid", REDIRECT)
    params = {k: v[0] for k, v in parse_qs(urlparse(req.url).query).items()}
    assert req.url.startswith("https://x.com/i/oauth2/authorize?")
    assert params["client_id"] == "cid"
    assert params["redirect_uri"] == REDIRECT
    assert params["scope"] == "tweet.read tweet.write users.read offline.access"
    assert params["state"] == req.state
    assert params["code_challenge_method"] == "S256"
    expected = base64.urlsafe_b64encode(hashlib.sha256(req.verifier.encode()).digest())
    assert params["code_challenge"] == expected.rstrip(b"=").decode()


def test_each_login_gets_new_secrets() -> None:
    a, b = start_login("cid", REDIRECT), start_login("cid", REDIRECT)
    assert a.state != b.state
    assert a.verifier != b.verifier


def test_code_from_callback() -> None:
    assert code_from_callback(f"{REDIRECT}?state=s&code=c", "s") == "c"


@pytest.mark.parametrize(
    ("url", "message"),
    [
        (f"{REDIRECT}?state=other&code=c", "does not match"),
        (f"{REDIRECT}?error=access_denied&state=s", "access_denied"),
        (f"{REDIRECT}?state=s", "no login code"),
    ],
)
def test_bad_callbacks(url: str, message: str) -> None:
    with pytest.raises(LoginError, match=message):
        code_from_callback(url, "s")


@respx.mock
def test_login_exchanges_code_and_saves_tokens() -> None:
    route = respx.post(TOKEN_URL).respond(
        200, json={"access_token": "a", "refresh_token": "r", "expires_in": 7200}
    )
    store = MemoryTokenStore()
    opened: list[str] = []

    def callback(_: str) -> str:
        state = parse_qs(urlparse(opened[0]).query)["state"][0]
        return f"{REDIRECT}?state={state}&code=thecode"

    tokens = login("cid", REDIRECT, store, opened.append, ask_url=lambda _: "", wait=callback)
    assert store.load() == tokens
    sent = parse_qs(route.calls.last.request.content.decode())
    assert sent["grant_type"] == ["authorization_code"]
    assert sent["code"] == ["thecode"]
    assert sent["client_id"] == ["cid"]
    assert len(sent["code_verifier"][0]) >= 43


@respx.mock
def test_login_falls_back_to_pasted_url() -> None:
    respx.post(TOKEN_URL).respond(200, json={"access_token": "a", "refresh_token": "r"})
    opened: list[str] = []

    def paste(_: str) -> str:
        state = parse_qs(urlparse(opened[0]).query)["state"][0]
        return f"{REDIRECT}?state={state}&code=c"

    login("cid", REDIRECT, MemoryTokenStore(), opened.append, ask_url=paste, wait=lambda _: None)


@respx.mock
def test_rejected_code_is_a_login_error() -> None:
    respx.post(TOKEN_URL).respond(400)
    opened: list[str] = []

    def callback(_: str) -> str:
        state = parse_qs(urlparse(opened[0]).query)["state"][0]
        return f"{REDIRECT}?state={state}&code=c"

    with pytest.raises(LoginError, match="did not accept"):
        login("cid", REDIRECT, MemoryTokenStore(), opened.append, lambda _: "", wait=callback)


@respx.mock
def test_logout_revokes_and_forgets() -> None:
    route = respx.post(REVOKE_URL).respond(200)
    from datetime import UTC, datetime

    store = MemoryTokenStore(TokenSet("a", "r", datetime.now(UTC)))
    logout(store, "cid")
    assert store.load() is None
    assert route.call_count == 2


@respx.mock
def test_logout_forgets_even_if_x_unreachable() -> None:
    respx.post(REVOKE_URL).mock(side_effect=httpx.ConnectError("down"))
    from datetime import UTC, datetime

    store = MemoryTokenStore(TokenSet("a", "r", datetime.now(UTC)))
    logout(store, "cid")
    assert store.load() is None


def _free_port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        port: int = sock.getsockname()[1]
        return port


@pytest.mark.skipif(
    sys.platform == "darwin" and os.environ.get("GITHUB_ACTIONS") == "true",
    reason="GitHub macOS runners drop local connections to the test server (connect timeout); "
    "covered locally on macOS and by the release checklist",
)
def test_local_callback_server_returns_the_url() -> None:
    uri = f"http://127.0.0.1:{_free_port()}/callback"
    result: list[str | None] = []
    thread = threading.Thread(target=lambda: result.append(wait_for_callback(uri, timeout=10)))
    thread.start()
    response: httpx.Response | None = None
    errors: list[str] = []
    # Until the server is bound, connecting fails. On macOS with stealth mode the attempt
    # times out instead of being refused, so retry on any transport error.
    for _ in range(50):
        try:
            response = httpx.get(f"{uri}?state=s&code=c", timeout=0.5, trust_env=False)
            break
        except httpx.TransportError as e:
            errors.append(repr(e))
            threading.Event().wait(0.05)
    thread.join()
    assert response is not None, errors[-3:]
    assert response.status_code == 200
    assert result == [f"{uri}?state=s&code=c"]


def test_local_callback_server_times_out() -> None:
    assert wait_for_callback(f"http://127.0.0.1:{_free_port()}/callback", timeout=0.2) is None


def test_busy_port_gives_none_so_user_can_paste() -> None:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        sock.listen()
        port = sock.getsockname()[1]
        assert wait_for_callback(f"http://127.0.0.1:{port}/callback", timeout=0.2) is None


def test_config_round_trip(tmp_path: Path) -> None:
    path = tmp_path / "config.toml"
    assert config.load(path) == config.Config()
    config.save(path, config.Config(client_id="cid"))
    assert config.load(path) == config.Config(client_id="cid", redirect_uri=REDIRECT)


def test_logout_survives_broken_token_file(tmp_path: Path) -> None:
    store = FileTokenStore(tmp_path / "tokens.json")
    store.path.write_text("not json")
    logout(store, "cid")
    assert not store.path.exists()


@pytest.mark.parametrize("client_id", ['a"b', "a\\b", "a\nb"])
def test_config_round_trip_with_odd_characters(tmp_path: Path, client_id: str) -> None:
    path = tmp_path / "config.toml"
    config.save(path, config.Config(client_id=client_id))
    assert config.load(path).client_id == client_id


def test_broken_config_is_a_clear_error(tmp_path: Path) -> None:
    path = tmp_path / "config.toml"
    path.write_text('client_id = "unclosed\n')
    with pytest.raises(config.ConfigError, match=str(path)):
        config.load(path)
