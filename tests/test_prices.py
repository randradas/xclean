from datetime import date, timedelta
from decimal import Decimal

from xclean.model import RateLimit
from xclean.prices import CHECKED_ON, PRICES, estimate_cost, estimate_duration

POSTS = RateLimit(requests=50, window=timedelta(minutes=15))


def test_price_table_has_checked_on_date() -> None:
    assert isinstance(CHECKED_ON, date)
    assert PRICES["post.delete"] > 0


def test_cost_is_count_times_price() -> None:
    assert estimate_cost(1000, "post.delete") == PRICES["post.delete"] * 1000
    assert estimate_cost(0, "post.delete") == Decimal(0)


def test_duration_from_rate_limit() -> None:
    assert estimate_duration(0, POSTS) == timedelta(0)
    assert estimate_duration(50, POSTS) == timedelta(0)  # fits in the first window
    assert estimate_duration(51, POSTS) == timedelta(minutes=15)
    assert estimate_duration(10_000, POSTS) == timedelta(minutes=15) * 199


def test_daily_cap_dominates_when_tighter() -> None:
    likes = RateLimit(requests=50, window=timedelta(minutes=15), daily=1000)
    assert estimate_duration(20_000, likes) == timedelta(days=19)
