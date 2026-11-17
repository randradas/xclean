"""Rules pick which items to remove. All rules must match (AND).

Dates are whole days in the user's local time zone, and strict: "before 2020-01-01" excludes
1 Jan, "after 2020-01-01" excludes 1 Jan too.
"""

from collections.abc import Iterable
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta, tzinfo

from xclean.model import ContentType, Item, PostKind


class RuleError(ValueError):
    """A rule the user gave is invalid. The message is shown as is."""


@dataclass(frozen=True)
class Rules:
    kinds: frozenset[PostKind]  # empty means every kind
    before: date | None
    after: date | None
    tz: tzinfo | None  # None means the system's local time zone


def _parse_kind(value: str) -> PostKind:
    try:
        return PostKind(value.lower())
    except ValueError:
        allowed = ", ".join(k.value for k in PostKind)
        raise RuleError(f"unknown type '{value}'; use one of: {allowed}") from None


def _parse_date(value: str | None) -> date | None:
    if value is None:
        return None
    try:
        return date.fromisoformat(value)
    except ValueError:
        raise RuleError(f"bad date '{value}'; use YYYY-MM-DD, e.g. 2020-01-31") from None


def parse_rules(
    types: Iterable[str], before: str | None, after: str | None, tz: tzinfo | None = None
) -> Rules:
    rules = Rules(
        kinds=frozenset(_parse_kind(t) for t in types),
        before=_parse_date(before),
        after=_parse_date(after),
        tz=tz,
    )
    if rules.before and rules.after and rules.after + timedelta(days=1) >= rules.before:
        raise RuleError(
            f"after {rules.after} and before {rules.before} matches nothing; "
            "the after date must be at least two days earlier"
        )
    return rules


def _start_of_day(day: date, tz: tzinfo | None) -> datetime:
    naive = datetime.combine(day, time())
    # astimezone() on a naive datetime uses the system zone, with the right DST offset.
    return naive.replace(tzinfo=tz) if tz else naive.astimezone()


def matches(item: Item, rules: Rules) -> bool:
    # Only posts are handled in this version; reposts and other types never match.
    if item.content_type is not ContentType.POST or item.kind is None:
        return False
    if rules.kinds and item.kind not in rules.kinds:
        return False
    if rules.before and item.created_at >= _start_of_day(rules.before, rules.tz):
        return False
    return not (
        rules.after and item.created_at < _start_of_day(rules.after + timedelta(days=1), rules.tz)
    )


def select(items: Iterable[Item], rules: Rules, keep: frozenset[str] = frozenset()) -> list[Item]:
    return [i for i in items if i.id not in keep and matches(i, rules)]


_KIND_WORDS = {
    PostKind.ORIGINAL: "original posts",
    PostKind.REPLY: "replies",
    PostKind.QUOTE: "quotes",
}


def _day(d: date) -> str:
    return f"{d.day} {d:%b %Y}"


def describe(rules: Rules, keep_count: int) -> str:
    """Rules in plain words, e.g. "replies and quotes before 1 Jan 2020, keeping 3 posts"."""
    words = [_KIND_WORDS[k] for k in PostKind if k in rules.kinds]
    if not words:
        text = "all posts"
    elif len(words) == 1:
        text = words[0]
    else:
        text = f"{', '.join(words[:-1])} and {words[-1]}"
    if rules.after and rules.before:
        text += f" after {_day(rules.after)} and before {_day(rules.before)}"
    elif rules.after:
        text += f" after {_day(rules.after)}"
    elif rules.before:
        text += f" before {_day(rules.before)}"
    if keep_count:
        text += f", keeping {keep_count} post{'s' if keep_count != 1 else ''}"
    return text
