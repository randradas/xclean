from datetime import UTC, datetime

import httpx
import pytest
import respx

from xclean.xclient import Me, Outcome, XClient

API = "https://api.x.com"
DELETE = f"{API}/2/tweets/123"


class FakeTokens:
    def __init__(self) -> None:
        self.token = "old"
        self.refreshed = 0

    def access_token(self) -> str:
        return self.token

    def refresh(self) -> str:
        self.refreshed += 1
        self.token = "new"
        return self.token


@pytest.fixture
def tokens() -> FakeTokens:
    return FakeTokens()


@pytest.fixture
def client(tokens: FakeTokens) -> XClient:
    return XClient(tokens)


@respx.mock
def test_deleted(client: XClient) -> None:
    route = respx.delete(DELETE).respond(200, json={"data": {"deleted": True}})
    result = client.delete_post("123")
    assert result.outcome is Outcome.DELETED
    assert route.calls.last.request.headers["Authorization"] == "Bearer old"


@respx.mock
def test_not_deleted_is_failed(client: XClient) -> None:
    respx.delete(DELETE).respond(200, json={"data": {"deleted": False}})
    result = client.delete_post("123")
    assert result.outcome is Outcome.FAILED
    assert "not deleted" in result.reason


@respx.mock
def test_404_is_already_gone(client: XClient) -> None:
    respx.delete(DELETE).respond(404, json={"title": "Not Found Error"})
    assert client.delete_post("123").outcome is Outcome.ALREADY_GONE


@respx.mock
def test_not_found_problem_is_already_gone(client: XClient) -> None:
    respx.delete(DELETE).respond(
        200,
        json={
            "errors": [{"type": "https://api.x.com/2/problems/resource-not-found"}],
        },
    )
    assert client.delete_post("123").outcome is Outcome.ALREADY_GONE


@respx.mock
def test_429_gives_reset_time(client: XClient) -> None:
    respx.delete(DELETE).respond(429, headers={"x-rate-limit-reset": "1763380800"})
    result = client.delete_post("123")
    assert result.outcome is Outcome.RATE_LIMITED
    assert result.reset_at == datetime.fromtimestamp(1763380800, UTC)


@respx.mock
def test_429_without_header_waits_a_window(client: XClient) -> None:
    respx.delete(DELETE).respond(429)
    result = client.delete_post("123")
    assert result.outcome is Outcome.RATE_LIMITED
    assert result.reset_at is not None
    assert (result.reset_at - datetime.now(UTC)).total_seconds() > 14 * 60


@respx.mock
def test_402_is_spending_limit(client: XClient) -> None:
    respx.delete(DELETE).respond(
        402,
        json={
            "type": "https://api.x.com/2/problems/credits-depleted",
            "detail": "credits depleted",
        },
    )
    result = client.delete_post("123")
    assert result.outcome is Outcome.SPENDING_LIMIT
    assert "credits depleted" in result.reason


@pytest.mark.parametrize("status", [500, 502, 503, 504])
@respx.mock
def test_5xx_is_temporary(client: XClient, status: int) -> None:
    respx.delete(DELETE).respond(status)
    assert client.delete_post("123").outcome is Outcome.TEMPORARY


@respx.mock
def test_network_error_is_temporary(client: XClient) -> None:
    respx.delete(DELETE).mock(side_effect=httpx.ConnectTimeout("slow"))
    result = client.delete_post("123")
    assert result.outcome is Outcome.TEMPORARY
    assert "slow" in result.reason


@respx.mock
def test_403_is_failed_with_reason(client: XClient) -> None:
    respx.delete(DELETE).respond(
        403, json={"title": "Forbidden", "detail": "You are not allowed to delete this Post."}
    )
    result = client.delete_post("123")
    assert result.outcome is Outcome.FAILED
    assert result.reason == "403: You are not allowed to delete this Post."


@respx.mock
def test_401_refreshes_token_once_and_retries(client: XClient, tokens: FakeTokens) -> None:
    route = respx.delete(DELETE)
    route.side_effect = [
        httpx.Response(401),
        httpx.Response(200, json={"data": {"deleted": True}}),
    ]
    assert client.delete_post("123").outcome is Outcome.DELETED
    assert tokens.refreshed == 1
    assert route.calls.last.request.headers["Authorization"] == "Bearer new"


@respx.mock
def test_401_after_refresh_is_not_logged_in(client: XClient) -> None:
    respx.delete(DELETE).respond(401)
    result = client.delete_post("123")
    assert result.outcome is Outcome.NOT_LOGGED_IN


@respx.mock
def test_me(client: XClient) -> None:
    respx.get(f"{API}/2/users/me").respond(
        200, json={"data": {"id": "42", "username": "someone", "pinned_tweet_id": "7"}}
    )
    assert client.me() == Me(id="42", username="someone", pinned_post_id="7")
