"""X API prices and estimates. Prices change; the preview shows when they were checked.

Source: docs.x.com pay-per-use pricing. Which category post delete falls under is not
documented, so it assumes the higher known delete price ("Interaction: Delete") until checked
with a real delete (release checklist).
"""

import math
from datetime import date, timedelta
from decimal import Decimal

from xclean.model import RateLimit

CHECKED_ON = date(2026, 11, 17)

PRICES: dict[str, Decimal] = {
    "post.delete": Decimal("0.010"),
}


def estimate_cost(count: int, price_key: str) -> Decimal:
    return PRICES[price_key] * count


def estimate_duration(count: int, limit: RateLimit) -> timedelta:
    """Time to send `count` requests, the first window starting now."""
    if count == 0:
        return timedelta(0)
    duration = limit.window * (math.ceil(count / limit.requests) - 1)
    if limit.daily:
        duration = max(duration, timedelta(days=math.ceil(count / limit.daily) - 1))
    return duration
