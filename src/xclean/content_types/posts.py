"""Posts: originals, replies, and quote posts."""

from datetime import timedelta

from xclean.model import ContentType, Item, RateLimit
from xclean.xclient import Result, XClient


class Posts:
    content_type = ContentType.POST
    rate_limit = RateLimit(requests=50, window=timedelta(minutes=15))  # DELETE /2/tweets/:id
    price_key = "post.delete"

    def __init__(self, client: XClient) -> None:
        self._client = client

    def remove(self, item: Item) -> Result:
        if item.content_type is not ContentType.POST:
            raise ValueError(f"not a post: {item.content_type}")
        return self._client.delete_post(item.id)
