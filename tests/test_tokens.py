import json
from datetime import UTC, datetime, timedelta
from pathlib import Path
from urllib.parse import parse_qs

import httpx
import pytest
import respx

from xclean.tokens import (
    FileTokenStore,
    MemoryTokenStore,
    TokenSet,
    UserTokens,
    default_token_store,
)
from xclean.xclient import NotLoggedIn, Outcome, TemporaryError, XClient

TOKEN_URL = "https://api.x.com/2/oauth2/token"
NOW = datetime(2026, 11, 17, 12, 0, tzinfo=UTC)


def tokens(expires_in: timedelta = timedelta(hours=2)) -> TokenSet:
    return TokenSet(access_token="a1", refresh_token="r1", expires_at=NOW + expires_in)


# Token stores


def test_file_store_round_trip_and_private(tmp_path: Path) -> None:
    store = FileTokenStore(tmp_path / "data" / "tokens.json")
    assert store.load() is None
    store.save(tokens())
    assert store.load() == tokens()
    assert store.path.stat().st_mode & 0o777 == 0o600
    store.clear()
    assert store.load() is None


def test_default_store_uses_keyring_when_available(tmp_path: Path) -> None:
    warnings: list[str] = []
    store = default_token_store(tmp_path, warn=warnings.append, keyring_usable=lambda: True)
    assert type(store).__name__ == "KeyringTokenStore"
    assert warnings == []


def test_default_store_falls_back_to_file_and_warns_once(tmp_path: Path) -> None:
    warnings: list[str] = []
    for _ in range(2):
        store = default_token_store(tmp_path, warn=warnings.append, keyring_usable=lambda: False)
        assert isinstance(store, FileTokenStore)
        assert store.path.parent == tmp_path
    assert len(warnings) == 1
    assert "keyring" in warnings[0]


# UserTokens: expiry and refresh (AC1)


def test_no_tokens_means_not_logged_in() -> None:
    user = UserTokens(MemoryTokenStore(), client_id="cid", now=lambda: NOW)
    with pytest.raises(NotLoggedIn):
        user.access_token()


def test_fresh_token_is_used_as_is() -> None:
    store = MemoryTokenStore(tokens())
    assert UserTokens(store, client_id="cid", now=lambda: NOW).access_token() == "a1"


@respx.mock
def test_expiring_token_is_refreshed_and_saved() -> None:
    route = respx.post(TOKEN_URL).respond(
        200, json={"access_token": "a2", "refresh_token": "r2", "expires_in": 7200}
    )
    store = MemoryTokenStore(tokens(expires_in=timedelta(seconds=30)))
    user = UserTokens(store, client_id="cid", now=lambda: NOW)
    assert user.access_token() == "a2"
    sent = parse_qs(route.calls.last.request.content.decode())
    assert sent == {"grant_type": ["refresh_token"], "refresh_token": ["r1"], "client_id": ["cid"]}
    assert store.load() == TokenSet("a2", "r2", NOW + timedelta(seconds=7200))


@respx.mock
def test_refresh_keeps_old_refresh_token_if_none_returned() -> None:
    respx.post(TOKEN_URL).respond(200, json={"access_token": "a2", "expires_in": 7200})
    store = MemoryTokenStore(tokens())
    UserTokens(store, client_id="cid", now=lambda: NOW).refresh()
    saved = store.load()
    assert saved is not None
    assert saved.refresh_token == "r1"


@respx.mock
def test_rejected_refresh_means_not_logged_in() -> None:
    respx.post(TOKEN_URL).respond(400, json={"error": "invalid_request"})
    user = UserTokens(MemoryTokenStore(tokens()), client_id="cid", now=lambda: NOW)
    with pytest.raises(NotLoggedIn, match="xclean login"):
        user.refresh()


@respx.mock
def test_client_reports_not_logged_in_without_tokens() -> None:
    client = XClient(UserTokens(MemoryTokenStore(), client_id="cid"))
    assert client.delete_post("1").outcome is Outcome.NOT_LOGGED_IN


def test_token_set_json_round_trip() -> None:
    assert TokenSet.from_json(tokens().to_json()) == tokens()
    assert json.loads(tokens().to_json())["refresh_token"] == "r1"


def test_token_service_5xx_is_temporary() -> None:
    http = httpx.Client(transport=httpx.MockTransport(lambda r: httpx.Response(503)))
    user = UserTokens(MemoryTokenStore(tokens()), client_id="cid", http=http, now=lambda: NOW)
    with pytest.raises(TemporaryError):
        user.refresh()


@respx.mock
def test_network_error_during_refresh_is_temporary_not_logged_out() -> None:
    respx.post(TOKEN_URL).mock(side_effect=httpx.ConnectError("down"))
    store = MemoryTokenStore(tokens(expires_in=timedelta(0)))
    client = XClient(UserTokens(store, client_id="cid", now=lambda: NOW))
    assert client.delete_post("1").outcome is Outcome.TEMPORARY


@respx.mock
@pytest.mark.parametrize(
    "answer",
    [
        httpx.Response(200, text="<html>busy</html>"),
        httpx.Response(200, text=""),
        httpx.Response(200, json=["a"]),
        httpx.Response(200, json={"token_type": "bearer"}),
    ],
)
def test_unreadable_refresh_answer_is_temporary(answer: httpx.Response) -> None:
    respx.post(TOKEN_URL).mock(return_value=answer)
    store = MemoryTokenStore(tokens(expires_in=timedelta(0)))
    client = XClient(UserTokens(store, client_id="cid", now=lambda: NOW))
    assert client.delete_post("1").outcome is Outcome.TEMPORARY
    assert store.load() == tokens(expires_in=timedelta(0))


@respx.mock
def test_rate_limited_refresh_is_temporary_not_logged_out() -> None:
    respx.post(TOKEN_URL).respond(429)
    store = MemoryTokenStore(tokens(expires_in=timedelta(0)))
    client = XClient(UserTokens(store, client_id="cid", now=lambda: NOW))
    assert client.delete_post("1").outcome is Outcome.TEMPORARY


# Saving tokens must never lose the rotated refresh token (R4)


def test_file_store_keeps_old_tokens_if_write_fails(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    store = FileTokenStore(tmp_path / "data" / "tokens.json")
    store.save(tokens())

    def broken_replace(*_: object) -> None:
        raise OSError("disk full")

    monkeypatch.setattr("os.replace", broken_replace)
    with pytest.raises(OSError):
        store.save(tokens(expires_in=timedelta(hours=5)))
    assert store.load() == tokens()
    assert list(store.path.parent.iterdir()) == [store.path]


def test_broken_token_file_reads_as_logged_out(tmp_path: Path) -> None:
    store = FileTokenStore(tmp_path / "tokens.json")
    store.path.write_text('{"access_token": "a1", "refr')
    assert store.load() is None


class FailingSaveStore(MemoryTokenStore):
    def __init__(self, tokens: TokenSet) -> None:
        super().__init__(tokens)
        self.fail = True

    def save(self, tokens: TokenSet) -> None:
        if self.fail:
            raise OSError("keychain locked")
        super().save(tokens)


@respx.mock
def test_failed_save_keeps_new_tokens_in_memory_and_saves_later() -> None:
    route = respx.post(TOKEN_URL).respond(
        200, json={"access_token": "a2", "refresh_token": "r2", "expires_in": 7200}
    )
    store = FailingSaveStore(tokens(expires_in=timedelta(0)))
    user = UserTokens(store, client_id="cid", now=lambda: NOW)
    assert user.access_token() == "a2"
    assert user.access_token() == "a2"
    assert route.call_count == 1
    store.fail = False
    user.access_token()
    saved = store.load()
    assert saved is not None and saved.refresh_token == "r2"
