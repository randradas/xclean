from datetime import UTC, date, datetime
from zoneinfo import ZoneInfo

import pytest

from xclean.model import ContentType, Item, PostKind
from xclean.rules import RuleError, Rules, describe, parse_rules, select

MADRID = ZoneInfo("Europe/Madrid")


def post(id: str, kind: PostKind, when: datetime) -> Item:
    return Item(id=id, content_type=ContentType.POST, created_at=when, kind=kind)


def repost(id: str, when: datetime) -> Item:
    return Item(id=id, content_type=ContentType.REPOST, created_at=when)


# T3: parse and validate (AC5, AC6, AC27)


def test_no_options_means_no_rules() -> None:
    rules = parse_rules(types=[], before=None, after=None, tz=MADRID)
    assert rules == Rules(kinds=frozenset(), before=None, after=None, tz=MADRID)


def test_types_parse_case_insensitive() -> None:
    rules = parse_rules(types=["Reply", "quote"], before=None, after=None, tz=MADRID)
    assert rules.kinds == {PostKind.REPLY, PostKind.QUOTE}


def test_dates_parse_iso() -> None:
    rules = parse_rules(types=[], before="2020-01-01", after="2018-12-31", tz=MADRID)
    assert rules.before == date(2020, 1, 1)
    assert rules.after == date(2018, 12, 31)


def test_unknown_type_is_a_clear_error() -> None:
    with pytest.raises(RuleError, match=r"unknown type 'tweet'.*original, reply, quote"):
        parse_rules(types=["tweet"], before=None, after=None, tz=MADRID)


@pytest.mark.parametrize("bad", ["2020-13-01", "01/01/2020", "yesterday", ""])
def test_bad_date_is_a_clear_error(bad: str) -> None:
    with pytest.raises(RuleError, match=rf"bad date '{bad}'.*YYYY-MM-DD"):
        parse_rules(types=[], before=bad, after=None, tz=MADRID)


def test_empty_date_range_is_an_error() -> None:
    with pytest.raises(RuleError, match="matches nothing"):
        parse_rules(types=[], before="2020-01-02", after="2020-01-01", tz=MADRID)


# T4: select (AC4, AC6, AC7, AC9)

JAN1 = date(2020, 1, 1)
ITEMS = [
    post("o", PostKind.ORIGINAL, datetime(2019, 6, 1, tzinfo=UTC)),
    post("r", PostKind.REPLY, datetime(2019, 6, 1, tzinfo=UTC)),
    post("q", PostKind.QUOTE, datetime(2021, 6, 1, tzinfo=UTC)),
    repost("rp", datetime(2019, 6, 1, tzinfo=UTC)),
]


def ids(items: list[Item]) -> list[str]:
    return [i.id for i in items]


def test_no_rules_selects_every_post_but_not_reposts() -> None:
    rules = Rules(kinds=frozenset(), before=None, after=None, tz=MADRID)
    assert ids(select(ITEMS, rules)) == ["o", "r", "q"]


def test_type_rule() -> None:
    rules = Rules(kinds=frozenset({PostKind.REPLY}), before=None, after=None, tz=MADRID)
    assert ids(select(ITEMS, rules)) == ["r"]


def test_rules_combine_with_and() -> None:
    rules = Rules(
        kinds=frozenset({PostKind.REPLY, PostKind.QUOTE}), before=JAN1, after=None, tz=MADRID
    )
    assert ids(select(ITEMS, rules)) == ["r"]


def test_reposts_never_selected_whatever_the_rules() -> None:
    rules = Rules(kinds=frozenset(PostKind), before=JAN1, after=None, tz=MADRID)
    assert "rp" not in ids(select(ITEMS, rules))


def test_before_is_strict_in_local_time() -> None:
    # 23:30 UTC on 31 Dec 2019 is 00:30 on 1 Jan 2020 in Madrid: not before 1 Jan.
    late = post("late", PostKind.ORIGINAL, datetime(2019, 12, 31, 23, 30, tzinfo=UTC))
    early = post("early", PostKind.ORIGINAL, datetime(2019, 12, 31, 22, 30, tzinfo=UTC))
    rules = Rules(kinds=frozenset(), before=JAN1, after=None, tz=MADRID)
    assert ids(select([late, early], rules)) == ["early"]


def test_after_is_strict_in_local_time() -> None:
    # Madrid summer time is UTC+2. The whole of 1 Jul is excluded, 2 Jul 00:00 is in.
    last = post("last", PostKind.ORIGINAL, datetime(2020, 7, 1, 21, 59, tzinfo=UTC))
    first = post("first", PostKind.ORIGINAL, datetime(2020, 7, 1, 22, 0, tzinfo=UTC))
    rules = Rules(kinds=frozenset(), before=None, after=date(2020, 7, 1), tz=MADRID)
    assert ids(select([last, first], rules)) == ["first"]


# T5: describe (AC28)


@pytest.mark.parametrize(
    ("types", "before", "after", "keep", "expected"),
    [
        ([], None, None, 0, "all posts"),
        (
            ["reply", "quote"],
            "2020-01-01",
            None,
            3,
            "replies and quotes before 1 Jan 2020, keeping 3 posts",
        ),
        (["original"], None, "2018-12-31", 1, "original posts after 31 Dec 2018, keeping 1 post"),
        (["quote", "original", "reply"], None, None, 0, "original posts, replies and quotes"),
        ([], "2020-01-01", "2018-12-31", 0, "all posts after 31 Dec 2018 and before 1 Jan 2020"),
    ],
)
def test_describe_in_plain_words(
    types: list[str], before: str | None, after: str | None, keep: int, expected: str
) -> None:
    rules = parse_rules(types=types, before=before, after=after, tz=MADRID)
    assert describe(rules, keep_count=keep) == expected
