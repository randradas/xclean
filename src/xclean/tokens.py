"""Login tokens: where they are kept, and refreshing them before they expire.

Kept in the OS keyring (macOS Keychain, Linux Secret Service). With no keyring, they go in a
file in the data folder readable only by the user. Never in the config folder.
"""

import contextlib
import json
import os
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Protocol

import httpx
import keyring
import keyring.backends.fail
import keyring.backends.null
from keyring.errors import KeyringError

from xclean.xclient import NotLoggedIn, request_tokens

_SERVICE = "xclean"
_KEY = "tokens"
_MARGIN = timedelta(minutes=1)  # refresh a bit before expiry


@dataclass(frozen=True)
class TokenSet:
    access_token: str
    refresh_token: str
    expires_at: datetime

    def to_json(self) -> str:
        return json.dumps(
            {
                "access_token": self.access_token,
                "refresh_token": self.refresh_token,
                "expires_at": self.expires_at.isoformat(),
            }
        )

    @classmethod
    def from_json(cls, text: str) -> "TokenSet":
        data = json.loads(text)
        return cls(
            access_token=data["access_token"],
            refresh_token=data["refresh_token"],
            expires_at=datetime.fromisoformat(data["expires_at"]),
        )


def _parse(text: str) -> TokenSet | None:
    """None for a broken saved value: the user just logs in again."""
    try:
        return TokenSet.from_json(text)
    except (ValueError, KeyError, TypeError):
        return None


class TokenStore(Protocol):
    def load(self) -> TokenSet | None: ...
    def save(self, tokens: TokenSet) -> None: ...
    def clear(self) -> None: ...


class KeyringTokenStore:
    def load(self) -> TokenSet | None:
        text = keyring.get_password(_SERVICE, _KEY)
        return _parse(text) if text else None

    def save(self, tokens: TokenSet) -> None:
        keyring.set_password(_SERVICE, _KEY, tokens.to_json())

    def clear(self) -> None:
        with contextlib.suppress(keyring.errors.PasswordDeleteError):
            keyring.delete_password(_SERVICE, _KEY)


class FileTokenStore:
    def __init__(self, path: Path) -> None:
        self.path = path

    def load(self) -> TokenSet | None:
        try:
            return _parse(self.path.read_text())
        except FileNotFoundError:
            return None
        except UnicodeDecodeError:
            return None

    def save(self, tokens: TokenSet) -> None:
        """Write a new file, then swap it in, so a failure never leaves a half-written file."""
        self.path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
        new = self.path.with_name(f".{self.path.name}.new")
        fd = os.open(new, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        try:
            with os.fdopen(fd, "w") as f:
                f.write(tokens.to_json())
                f.flush()
                os.fsync(f.fileno())
            new.chmod(0o600)
            os.replace(new, self.path)
        finally:
            new.unlink(missing_ok=True)

    def clear(self) -> None:
        self.path.unlink(missing_ok=True)


def _keyring_usable() -> bool:
    try:
        backend = keyring.get_keyring()
    except KeyringError:
        return False
    return not isinstance(backend, keyring.backends.fail.Keyring | keyring.backends.null.Keyring)


def default_token_store(
    data_dir: Path,
    warn: Callable[[str], None],
    keyring_usable: Callable[[], bool] = _keyring_usable,
) -> TokenStore:
    if keyring_usable():
        return KeyringTokenStore()
    marker = data_dir / ".token-file-warned"
    if not marker.exists():
        warn(
            f"No OS keyring found. Login tokens are saved in {data_dir / 'tokens.json'}, "
            "readable only by you."
        )
        data_dir.mkdir(mode=0o700, parents=True, exist_ok=True)
        marker.touch()
    return FileTokenStore(data_dir / "tokens.json")


def token_set_from_response(
    body: dict[str, object], now: datetime, old_refresh: str = ""
) -> TokenSet:
    expires_in = body.get("expires_in", 7200)
    return TokenSet(
        access_token=str(body["access_token"]),
        refresh_token=str(body.get("refresh_token") or old_refresh),
        expires_at=now + timedelta(seconds=int(str(expires_in))),
    )


class UserTokens:
    """Gives a valid access token, refreshing it when needed. Satisfies `xclient.Tokens`."""

    def __init__(
        self,
        store: TokenStore,
        client_id: str,
        http: httpx.Client | None = None,
        now: Callable[[], datetime] = lambda: datetime.now(UTC),
    ) -> None:
        self._store = store
        self._client_id = client_id
        self._http = http
        self._now = now
        self._unsaved: TokenSet | None = None  # refreshed tokens the store has not taken yet

    def _save(self, tokens: TokenSet) -> None:
        """X rotates refresh tokens, so after a refresh only the new set works.

        If the store fails, keep the new set in memory and try again on the next use.
        """
        try:
            self._store.save(tokens)
        except Exception:
            self._unsaved = tokens
        else:
            self._unsaved = None

    def _load(self) -> TokenSet:
        if (unsaved := self._unsaved) is not None:
            self._save(unsaved)
            return unsaved
        tokens = self._store.load()
        if tokens is None:
            raise NotLoggedIn("not logged in; run `xclean login`")
        return tokens

    def access_token(self) -> str:
        tokens = self._load()
        if tokens.expires_at - _MARGIN <= self._now():
            return self.refresh()
        return tokens.access_token

    def refresh(self) -> str:
        old = self._load()
        # Network and temporary errors propagate: the X client retries them later.
        data = {
            "grant_type": "refresh_token",
            "refresh_token": old.refresh_token,
            "client_id": self._client_id,
        }
        try:
            body = request_tokens(data, self._http)
        except NotLoggedIn:
            raise NotLoggedIn("login expired or was revoked; run `xclean login`") from None
        tokens = token_set_from_response(body, self._now(), old.refresh_token)
        self._save(tokens)
        return tokens.access_token
