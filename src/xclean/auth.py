"""Browser login: OAuth 2.0 authorization code with PKCE, for an X "Native App".

The browser returns to a local address. If that cannot work, the user pastes the address the
browser ended on.
"""

import base64
import contextlib
import hashlib
import secrets
import time
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import parse_qs, urlencode, urlparse

import httpx

from xclean.tokens import TOKEN_URL, TokenSet, TokenStore, token_set_from_response

AUTHORIZE_URL = "https://x.com/i/oauth2/authorize"
REVOKE_URL = "https://api.x.com/2/oauth2/revoke"
SCOPES = ("tweet.read", "tweet.write", "users.read", "offline.access")


class LoginError(Exception):
    """Login failed. The message is shown as is."""


@dataclass(frozen=True)
class LoginRequest:
    url: str
    state: str
    verifier: str


def _challenge(verifier: str) -> str:
    digest = hashlib.sha256(verifier.encode()).digest()
    return base64.urlsafe_b64encode(digest).rstrip(b"=").decode()


def start_login(client_id: str, redirect_uri: str) -> LoginRequest:
    verifier = secrets.token_urlsafe(64)
    state = secrets.token_urlsafe(16)
    query = urlencode(
        {
            "response_type": "code",
            "client_id": client_id,
            "redirect_uri": redirect_uri,
            "scope": " ".join(SCOPES),
            "state": state,
            "code_challenge": _challenge(verifier),
            "code_challenge_method": "S256",
        }
    )
    return LoginRequest(url=f"{AUTHORIZE_URL}?{query}", state=state, verifier=verifier)


def code_from_callback(url: str, state: str) -> str:
    """Take the code from the address X sent the browser back to."""
    params = parse_qs(urlparse(url.strip()).query)
    if "error" in params:
        raise LoginError(f"X refused the login: {params['error'][0]}")
    if params.get("state", [""])[0] != state:
        raise LoginError("login answer does not match this login attempt; try again")
    if not params.get("code"):
        raise LoginError("no login code in that address")
    return params["code"][0]


def finish_login(
    request: LoginRequest,
    code: str,
    client_id: str,
    redirect_uri: str,
    store: TokenStore,
    http: httpx.Client | None = None,
) -> TokenSet:
    http = http or httpx.Client(timeout=30)
    response = http.post(
        TOKEN_URL,
        data={
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": redirect_uri,
            "code_verifier": request.verifier,
            "client_id": client_id,
        },
    )
    if response.status_code != 200:
        raise LoginError(f"X did not accept the login code ({response.status_code})")
    tokens = token_set_from_response(response.json(), datetime.now(UTC))
    store.save(tokens)
    return tokens


def logout(store: TokenStore, client_id: str, http: httpx.Client | None = None) -> None:
    """Revoke at X (best effort) and forget the tokens locally."""
    tokens = store.load()
    if tokens:
        http = http or httpx.Client(timeout=30)
        for token in (tokens.refresh_token, tokens.access_token):
            with contextlib.suppress(httpx.TransportError):
                http.post(REVOKE_URL, data={"token": token, "client_id": client_id})
    store.clear()


def wait_for_callback(redirect_uri: str, timeout: float = 300) -> str | None:
    """Serve one request on the local redirect address and return its full URL.

    None when the address cannot be served or nothing arrives in time.
    """
    target = urlparse(redirect_uri)
    received: list[str] = []

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:
            if urlparse(self.path).path != target.path:
                self.send_error(404)
                return
            received.append(f"{target.scheme}://{target.netloc}{self.path}")
            self.send_response(200)
            self.send_header("Content-Type", "text/plain; charset=utf-8")
            self.end_headers()
            self.wfile.write(b"xclean: login received. You can close this tab.")

        def log_message(self, format: str, *args: object) -> None:
            pass

    try:
        server = HTTPServer((target.hostname or "127.0.0.1", target.port or 80), Handler)
    except OSError:
        return None
    deadline = time.monotonic() + timeout
    with server:
        while not received and (left := deadline - time.monotonic()) > 0:
            server.timeout = left
            server.handle_request()
    return received[0] if received else None


def login(
    client_id: str,
    redirect_uri: str,
    store: TokenStore,
    open_browser: Callable[[str], object],
    ask_url: Callable[[str], str],
    wait: Callable[[str], str | None] = wait_for_callback,
    http: httpx.Client | None = None,
) -> TokenSet:
    """Full login. `ask_url` is the paste fallback when the local address gets nothing."""
    request = start_login(client_id, redirect_uri)
    open_browser(request.url)
    url = wait(redirect_uri) or ask_url(request.url)
    code = code_from_callback(url, request.state)
    return finish_login(request, code, client_id, redirect_uri, store, http)
