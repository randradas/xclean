from datetime import UTC, datetime
from pathlib import Path

import pytest

from xclean.keep import KeepError, parse_keep, read_keep
from xclean.model import ContentType, Item, PostKind
from xclean.rules import Rules, select


@pytest.mark.parametrize(
    "line",
    [
        "1234567890",
        "  1234567890  ",
        "https://x.com/someone/status/1234567890",
        "https://twitter.com/someone/status/1234567890",
        "https://mobile.twitter.com/someone/status/1234567890?s=20",
        "x.com/someone/status/1234567890/photo/1",
        "https://x.com/i/web/status/1234567890",
    ],
)
def test_ids_and_links_give_the_post_id(line: str) -> None:
    assert parse_keep([line]) == {"1234567890"}


def test_blank_lines_and_comments_are_ignored() -> None:
    assert parse_keep(["", "# my best post", "42", "   "]) == {"42"}


@pytest.mark.parametrize(
    "line", ["hello", "https://x.com/someone", "12ab", "https://example.com/status/1"]
)
def test_bad_line_names_its_line_number(line: str) -> None:
    with pytest.raises(KeepError, match=r"line 2: .*post ID or post link"):
        parse_keep(["1", line])


def test_read_keep_from_file(tmp_path: Path) -> None:
    path = tmp_path / "keep.txt"
    path.write_text("1\nhttps://x.com/a/status/2\n")
    assert read_keep(path) == {"1", "2"}


def test_missing_keep_file_is_a_clear_error(tmp_path: Path) -> None:
    with pytest.raises(KeepError, match="keep file not found"):
        read_keep(tmp_path / "nope.txt")


def test_kept_posts_are_never_selected() -> None:
    items = [
        Item(
            id=str(n),
            content_type=ContentType.POST,
            created_at=datetime(2019, 1, 1, tzinfo=UTC),
            kind=PostKind.ORIGINAL,
        )
        for n in (1, 2, 3)
    ]
    rules = Rules(kinds=frozenset(), before=None, after=None, tz=UTC)
    assert [i.id for i in select(items, rules, keep=parse_keep(["2"]))] == ["1", "3"]
