"""Removal loop: the core of a run. Knows nothing about terminals or the cloud.

One request at a time. Each result is saved before the next request, so a stop at any moment
loses nothing and a resume never removes an item twice.
"""

import time
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from enum import Enum
from typing import Protocol

from xclean.content_types import Remover
from xclean.model import Item, ItemStatus, RunState
from xclean.store import Store
from xclean.xclient import RATE_WINDOW, Outcome

BACKOFF = (timedelta(seconds=5), timedelta(seconds=30), timedelta(minutes=2))
# X bills requests it answers; rate-limited and network failures are not counted.
_BILLED = {Outcome.DELETED, Outcome.ALREADY_GONE, Outcome.FAILED}
# X's reset time is X's clock. If ours runs ahead, the reset looks past: wait at least this,
# and a full window when X still says no right after a wait.
MIN_RATE_WAIT = timedelta(minutes=1)
# One 403 fails that item. This many in a row means X refuses the app (often out of credits).
REFUSALS_TO_STOP = 3


class Clock(Protocol):
    def now(self) -> datetime: ...
    def sleep_until(self, when: datetime) -> None: ...


class RealClock:
    def now(self) -> datetime:
        return datetime.now(UTC)

    def sleep_until(self, when: datetime) -> None:
        # One extra second so X's window has surely reset.
        time.sleep(max(0.0, (when - self.now()).total_seconds()) + 1)


class Ending(Enum):
    FINISHED = "finished"
    SPENDING_LIMIT = "spending limit reached"
    NOT_LOGGED_IN = "not logged in"
    REFUSED = "refused by X"


class Engine:
    def __init__(
        self,
        store: Store,
        remover: Remover,
        clock: Clock | None = None,
        backoff: tuple[timedelta, ...] = BACKOFF,
        on_progress: Callable[[], None] = lambda: None,
    ) -> None:
        self._store = store
        self._remover = remover
        self._clock = clock or RealClock()
        self._backoff = backoff
        self._on_progress = on_progress

    def run(self, run_id: int) -> Ending:
        """Work through pending items. Ctrl-C leaves the run stopped and resumable."""
        store = self._store
        self._refusals = 0
        try:
            # A run stopped mid-wait waits out the rest before sending anything.
            until = store.get_run(run_id).wait_until
            if until is not None and until > self._clock.now():
                store.set_state(run_id, RunState.WAITING, wait_until=until, message="rate limit")
                self._on_progress()
                self._clock.sleep_until(until)
            store.set_state(run_id, RunState.WORKING)
            for item in store.pending(run_id):
                if (ending := self._remove_one(run_id, item)) is not None:
                    return ending
                self._on_progress()
        except BaseException:
            until = store.get_run(run_id).wait_until
            store.set_state(run_id, RunState.STOPPED, wait_until=until, message="interrupted")
            raise
        store.finish(run_id)
        self._on_progress()
        return Ending.FINISHED

    def _remove_one(self, run_id: int, item: Item) -> Ending | None:
        store = self._store
        retries = 0
        rate_limited = 0
        while True:
            result = self._remover.remove(item)
            if result.outcome in _BILLED:
                store.add_requests(run_id)
            match result.outcome:
                case Outcome.DELETED | Outcome.ALREADY_GONE:
                    store.mark(run_id, item.id, ItemStatus.DONE)
                    self._refusals = 0
                    return None
                case Outcome.REFUSED:
                    store.mark(run_id, item.id, ItemStatus.FAILED, result.reason)
                    self._refusals += 1
                    if self._refusals < REFUSALS_TO_STOP:
                        return None
                    message = f"X refused {REFUSALS_TO_STOP} in a row ({result.reason})"
                    store.set_state(run_id, RunState.STOPPED, message=message)
                    return Ending.REFUSED
                case Outcome.FAILED:
                    store.mark(run_id, item.id, ItemStatus.FAILED, result.reason)
                    self._refusals = 0
                    return None
                case Outcome.RATE_LIMITED:
                    floor = RATE_WINDOW if rate_limited else MIN_RATE_WAIT
                    rate_limited += 1
                    until = max(result.reset_at or self._clock.now(), self._clock.now() + floor)
                    store.set_state(
                        run_id, RunState.WAITING, wait_until=until, message="rate limit"
                    )
                    self._on_progress()
                    self._clock.sleep_until(until)
                    store.set_state(run_id, RunState.WORKING)
                case Outcome.TEMPORARY:
                    if retries >= len(self._backoff):
                        store.mark(run_id, item.id, ItemStatus.FAILED, result.reason)
                        self._refusals = 0
                        return None
                    self._clock.sleep_until(self._clock.now() + self._backoff[retries])
                    retries += 1
                case Outcome.SPENDING_LIMIT:
                    store.set_state(run_id, RunState.STOPPED, message=result.reason)
                    return Ending.SPENDING_LIMIT
                case Outcome.NOT_LOGGED_IN:
                    store.set_state(run_id, RunState.STOPPED, message=result.reason)
                    return Ending.NOT_LOGGED_IN
