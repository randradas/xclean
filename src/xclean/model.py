"""Core data types. Enum values are stored, so never change them."""

from dataclasses import dataclass
from datetime import datetime, timedelta
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


class RunState(StrEnum):
    READY = "ready"  # created, not started yet
    WORKING = "working"
    WAITING = "waiting"  # rate limited, see Run.wait_until
    STOPPED = "stopped"  # interrupted or blocked; resumable
    FINISHED = "finished"


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


@dataclass(frozen=True)
class RateLimit:
    """X's per-user limit for one removal endpoint."""

    requests: int
    window: timedelta
    daily: int | None = None


@dataclass(frozen=True)
class Run:
    """One confirmed removal job. Its selection is frozen when it starts."""

    id: int
    account_id: str
    created_at: datetime
    rules: str  # rules in plain words, as shown in the preview
    state: RunState
    requests: int  # removal requests sent to X, for the spend estimate
    wait_until: datetime | None = None
    message: str = ""  # why the run is waiting or stopped
    finished_at: datetime | None = None


@dataclass(frozen=True)
class Counts:
    done: int
    failed: int
    pending: int

    @property
    def total(self) -> int:
        return self.done + self.failed + self.pending


@dataclass(frozen=True)
class Failure:
    item: Item
    reason: str


@dataclass(frozen=True)
class Report:
    run: Run
    counts: Counts
    failures: list[Failure]
