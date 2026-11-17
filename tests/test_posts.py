from datetime import UTC, datetime

import pytest
import respx

from xclean.content_types import Remover
from xclean.content_types.posts import Posts
from xclean.model import ContentType, Item, PostKind
from xclean.prices import PRICES
from xclean.xclient import Outcome, XClient


class Tokens:
    def access_token(self) -> str:
        return "t"

    def refresh(self) -> str:
        return "t"


@pytest.fixture
def posts() -> Posts:
    return Posts(XClient(Tokens()))


@respx.mock
def test_remove_deletes_the_post_by_id(posts: Posts) -> None:
    route = respx.delete("https://api.x.com/2/tweets/99").respond(
        200, json={"data": {"deleted": True}}
    )
    item = Item("99", ContentType.POST, datetime.now(UTC), kind=PostKind.REPLY)
    assert posts.remove(item).outcome is Outcome.DELETED
    assert route.called


def test_refuses_other_content_types(posts: Posts) -> None:
    with pytest.raises(ValueError, match="not a post"):
        posts.remove(Item("1", ContentType.REPOST, datetime.now(UTC)))


def test_is_a_remover_with_known_price(posts: Posts) -> None:
    remover: Remover = posts
    assert remover.price_key in PRICES
    assert remover.rate_limit.requests == 50
