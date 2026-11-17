from datetime import UTC, datetime

import pytest

from xclean.model import ContentType, Item, ItemStatus, PostKind, RunState


def test_post_item_needs_a_kind() -> None:
    with pytest.raises(ValueError, match="kind"):
        Item(id="1", content_type=ContentType.POST, created_at=datetime.now(UTC))


def test_repost_item_has_no_kind() -> None:
    with pytest.raises(ValueError, match="kind"):
        Item(
            id="1",
            content_type=ContentType.REPOST,
            created_at=datetime.now(UTC),
            kind=PostKind.REPLY,
        )


def test_created_at_must_be_timezone_aware() -> None:
    with pytest.raises(ValueError, match="time zone"):
        Item(
            id="1",
            content_type=ContentType.POST,
            created_at=datetime(2020, 1, 1),
            kind=PostKind.ORIGINAL,
        )


def test_values_are_stable_strings() -> None:
    # Stored in the progress store, so they must never change.
    assert [k.value for k in PostKind] == ["original", "reply", "quote"]
    assert [c.value for c in ContentType] == ["post", "repost"]
    assert [s.value for s in ItemStatus] == ["pending", "done", "failed"]
    assert [s.value for s in RunState] == ["ready", "working", "waiting", "stopped", "finished"]
