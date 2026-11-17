"""Core data types. Enum values are stored, so never change them."""

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum


class ContentType(StrEnum):
    POST = "post"
    REPOST = "repost"


class PostKind(StrEnum):
    ORIGINAL = "original"
    REPLY = "reply"
    QUOTE = "quote"


class ItemStatus(StrEnum):
    PENDING = "pending"
    DONE = "done"
    FAILED = "failed"


@dataclass(frozen=True)
class Item:
    """One piece of user content found by a source."""

    id: str
    content_type: ContentType
    created_at: datetime
    kind: PostKind | None = None
    text: str = ""

    def __post_init__(self) -> None:
        if self.created_at.tzinfo is None:
            raise ValueError("created_at needs a time zone")
        if (self.content_type is ContentType.POST) != (self.kind is not None):
            raise ValueError("posts need a kind; other content types must not have one")
