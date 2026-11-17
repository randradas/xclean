"""Content types: one module each. Each knows how to remove one item, its rate limit, and its
price. Adding one must not change the core."""

from typing import Protocol

from xclean.model import ContentType, Item, RateLimit
from xclean.xclient import Result


class Remover(Protocol):
    content_type: ContentType
    rate_limit: RateLimit
    price_key: str

    def remove(self, item: Item) -> Result: ...
