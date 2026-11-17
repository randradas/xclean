"""The only code that talks HTTP to X. Everything else sees simple results."""

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from enum import Enum
from typing import Any, Protocol

import httpx

API = "https://api.x.com"
_NOT_FOUND = "https://api.x.com/2/problems/resource-not-found"
_CREDITS = "https://api.x.com/2/problems/credits-depleted"
_DEFAULT_WAIT = timedelta(minutes=15)


class NotLoggedIn(Exception):
    """No usable tokens: the user must run `xclean login`."""


class TemporaryError(Exception):
    """X or the network failed in a way worth retrying later."""


class Tokens(Protocol):
    """Both raise NotLoggedIn when there is no usable token."""

    def access_token(self) -> str: ...
    def refresh(self) -> str: ...


class Outcome(Enum):
    DELETED = "deleted"
    ALREADY_GONE = "already gone"
    RATE_LIMITED = "rate limited"
    SPENDING_LIMIT = "spending limit reached"
    TEMPORARY = "temporary error"
    NOT_LOGGED_IN = "not logged in"
    FAILED = "failed"


@dataclass(frozen=True)
class Result:
    outcome: Outcome
    reason: str = ""
    reset_at: datetime | None = None  # set when rate limited


@dataclass(frozen=True)
class Me:
    id: str
    username: str
    pinned_post_id: str | None


class XError(Exception):
    """A read from X failed. The message is shown as is."""


def _body(response: httpx.Response) -> dict[str, Any]:
    try:
        body = response.json()
    except ValueError:
        return {}
    return body if isinstance(body, dict) else {}


def _detail(response: httpx.Response) -> str:
    body = _body(response)
    errors = body.get("errors") or [{}]
    text = body.get("detail") or errors[0].get("detail") or errors[0].get("message")
    return f"{response.status_code}: {text or response.reason_phrase}"


def _problem_types(response: httpx.Response) -> set[str]:
    body = _body(response)
    types = {e.get("type", "") for e in body.get("errors") or []}
    types.add(body.get("type", ""))
    return types


class XClient:
    def __init__(self, tokens: Tokens, http: httpx.Client | None = None) -> None:
        self._tokens = tokens
        self._http = http or httpx.Client(base_url=API, timeout=30)

    def _send(self, method: str, path: str, **kwargs: Any) -> httpx.Response:
        """Send with the user's token; on 401 refresh once and retry."""

        def send(token: str) -> httpx.Response:
            headers = {"Authorization": f"Bearer {token}"}
            return self._http.request(method, path, headers=headers, **kwargs)

        response = send(self._tokens.access_token())
        if response.status_code == 401:
            response = send(self._tokens.refresh())
        return response

    def delete_post(self, post_id: str) -> Result:
        try:
            response = self._send("DELETE", f"/2/tweets/{post_id}")
        except (httpx.TransportError, TemporaryError) as e:
            return Result(Outcome.TEMPORARY, f"network: {e}")
        except NotLoggedIn as e:
            return Result(Outcome.NOT_LOGGED_IN, str(e))
        return self._removal_result(response, "data", "deleted")

    def _removal_result(self, response: httpx.Response, *done_path: str) -> Result:
        status = response.status_code
        problems = _problem_types(response)
        if status == 404 or _NOT_FOUND in problems:
            return Result(Outcome.ALREADY_GONE)
        if status == 429:
            return Result(Outcome.RATE_LIMITED, reset_at=_reset_at(response))
        if status == 402 or _CREDITS in problems:
            return Result(Outcome.SPENDING_LIMIT, _detail(response))
        if status == 401:
            return Result(Outcome.NOT_LOGGED_IN, "access token rejected; run `xclean login`")
        if status >= 500:
            return Result(Outcome.TEMPORARY, _detail(response))
        if status != 200:
            return Result(Outcome.FAILED, _detail(response))
        value: Any = _body(response)
        for key in done_path:
            value = value.get(key, {}) if isinstance(value, dict) else {}
        if value is True:
            return Result(Outcome.DELETED)
        return Result(Outcome.FAILED, "X answered but the item was not deleted")

    def me(self) -> Me:
        try:
            response = self._send("GET", "/2/users/me", params={"user.fields": "pinned_tweet_id"})
        except (httpx.TransportError, TemporaryError) as e:
            raise XError(f"could not reach X: {e}") from None
        except NotLoggedIn as e:
            raise XError(str(e)) from None
        if response.status_code == 401:
            raise XError("not logged in; run `xclean login`")
        if response.status_code != 200:
            raise XError(f"could not read your X account: {_detail(response)}")
        data = _body(response).get("data", {})
        return Me(
            id=data["id"], username=data["username"], pinned_post_id=data.get("pinned_tweet_id")
        )


def _reset_at(response: httpx.Response) -> datetime:
    reset = response.headers.get("x-rate-limit-reset")
    if reset and reset.isdigit():
        return datetime.fromtimestamp(int(reset), UTC)
    return datetime.now(UTC) + _DEFAULT_WAIT
