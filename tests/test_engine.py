from collections.abc import Iterator
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from xclean.engine import Ending, Engine
from xclean.model import ContentType, Counts, Item, PostKind, RateLimit, RunState
from xclean.store import SqliteStore
from xclean.xclient import Outcome, Result

START = datetime(2026, 11, 17, 12, 0, tzinfo=UTC)


class FakeClock:
    def __init__(self) -> None:
        self.t = START
        self.sleeps: list[datetime] = []

    def now(self) -> datetime:
        return self.t

    def sleep_until(self, when: datetime) -> None:
        self.sleeps.append(when)
        self.t = max(self.t, when)


class FakeRemover:
    """Answers from a script per item id; default is DELETED. Records every call."""

    content_type = ContentType.POST
    rate_limit = RateLimit(requests=50, window=timedelta(minutes=15))
    price_key = "post.delete"

    def __init__(self, script: dict[str, list[Result]] | None = None) -> None:
        self.script = {k: iter(v) for k, v in (script or {}).items()}
        self.calls: list[str] = []

    def remove(self, item: Item) -> Result:
        self.calls.append(item.id)
        answers: Iterator[Result] | None = self.script.get(item.id)
        return next(answers, Result(Outcome.DELETED)) if answers else Result(Outcome.DELETED)


def post(id: str) -> Item:
    return Item(id, ContentType.POST, START - timedelta(days=400), kind=PostKind.ORIGINAL)


@pytest.fixture
def store(tmp_path: Path) -> SqliteStore:
    return SqliteStore(tmp_path / "x.db")


def start(store: SqliteStore, *ids: str) -> int:
    return store.start_run("42", [post(i) for i in ids], rules="all posts").id


# T14: loop, results saved, already gone, retries (AC18, AC21)


def test_removes_every_item_and_finishes(store: SqliteStore) -> None:
    run = start(store, "1", "2", "3")
    remover = FakeRemover()
    assert Engine(store, remover, FakeClock()).run(run) is Ending.FINISHED
    assert remover.calls == ["1", "2", "3"]
    assert store.counts(run) == Counts(done=3, failed=0, pending=0)
    assert store.get_run(run).state is RunState.FINISHED
    assert store.get_run(run).requests == 3


def test_already_gone_counts_as_done(store: SqliteStore) -> None:
    run = start(store, "1")
    remover = FakeRemover({"1": [Result(Outcome.ALREADY_GONE)]})
    Engine(store, remover, FakeClock()).run(run)
    assert store.counts(run).done == 1


def test_failed_item_keeps_reason_and_run_goes_on(store: SqliteStore) -> None:
    run = start(store, "1", "2")
    remover = FakeRemover({"1": [Result(Outcome.FAILED, "403: nope")]})
    Engine(store, remover, FakeClock()).run(run)
    report = store.report(run)
    assert [(f.item.id, f.reason) for f in report.failures] == [("1", "403: nope")]
    assert report.counts.done == 1


def test_temporary_errors_are_retried_with_backoff(store: SqliteStore) -> None:
    run = start(store, "1")
    remover = FakeRemover({"1": [Result(Outcome.TEMPORARY, "503"), Result(Outcome.DELETED)]})
    clock = FakeClock()
    Engine(store, remover, clock, backoff=(timedelta(seconds=5),)).run(run)
    assert remover.calls == ["1", "1"]
    assert clock.sleeps == [START + timedelta(seconds=5)]
    assert store.counts(run).done == 1


def test_temporary_errors_fail_after_retries(store: SqliteStore) -> None:
    run = start(store, "1", "2")
    remover = FakeRemover({"1": [Result(Outcome.TEMPORARY, "503")] * 3})
    Engine(store, remover, FakeClock(), backoff=(timedelta(0), timedelta(0))).run(run)
    assert remover.calls == ["1", "1", "1", "2"]
    assert [f.reason for f in store.report(run).failures] == ["503"]
    # Network errors and retries are not billed.
    assert store.get_run(run).requests == 1


def test_progress_callback_after_each_item(store: SqliteStore) -> None:
    run = start(store, "1", "2")
    seen: list[Counts] = []
    Engine(
        store, FakeRemover(), FakeClock(), on_progress=lambda: seen.append(store.counts(run))
    ).run(run)
    assert seen[:2] == [Counts(1, 0, 1), Counts(2, 0, 0)]


# T15: rate limit and spending limit (AC19, AC22)


def test_rate_limit_waits_until_reset_then_retries(store: SqliteStore) -> None:
    run = start(store, "1")
    reset = START + timedelta(minutes=12)
    remover = FakeRemover({"1": [Result(Outcome.RATE_LIMITED, reset_at=reset)]})
    clock = FakeClock()
    states: list[tuple[RunState, datetime | None]] = []

    def watch() -> None:
        r = store.get_run(run)
        states.append((r.state, r.wait_until))

    Engine(store, remover, clock, on_progress=watch).run(run)
    assert clock.sleeps == [reset]
    assert remover.calls == ["1", "1"]
    assert states[0] == (RunState.WAITING, reset)
    assert store.counts(run).done == 1
    assert store.get_run(run).requests == 1


def test_reset_in_the_past_still_waits_a_minimum(store: SqliteStore) -> None:
    """Local clock ahead of X: the reset looks past, but we must not hammer X (R5)."""
    run = start(store, "1")
    past = START - timedelta(minutes=5)
    remover = FakeRemover({"1": [Result(Outcome.RATE_LIMITED, reset_at=past)] * 3})
    clock = FakeClock()
    Engine(store, remover, clock).run(run)
    assert clock.sleeps[0] >= START + timedelta(minutes=1)
    assert clock.sleeps[1] - clock.sleeps[0] >= timedelta(minutes=15)
    assert len(remover.calls) == 4
    assert store.counts(run).done == 1


class StopDuringWait(FakeClock):
    def sleep_until(self, when: datetime) -> None:
        raise KeyboardInterrupt


def test_resume_honours_a_stored_wait(store: SqliteStore) -> None:
    """Stopped mid-wait: resume waits out the rest before sending anything (R6)."""
    run = start(store, "1")
    reset = START + timedelta(minutes=12)
    first = FakeRemover({"1": [Result(Outcome.RATE_LIMITED, reset_at=reset)]})
    with pytest.raises(KeyboardInterrupt):
        Engine(store, first, StopDuringWait()).run(run)
    assert store.get_run(run).wait_until == reset

    second = FakeRemover()
    clock = FakeClock()
    clock.t = START + timedelta(minutes=2)
    Engine(store, second, clock).run(run)
    assert clock.sleeps == [reset]
    assert second.calls == ["1"]


def test_one_refusal_fails_that_post_only(store: SqliteStore) -> None:
    run = start(store, "1", "2")
    remover = FakeRemover({"1": [Result(Outcome.REFUSED, "403: not allowed")]})
    assert Engine(store, remover, FakeClock()).run(run) is Ending.FINISHED
    assert store.counts(run).failed == 1
    assert store.counts(run).done == 1


def test_refusals_in_a_row_stop_the_run(store: SqliteStore) -> None:
    """X may answer 403 when credits run out: stop instead of failing every post (R10, AC22)."""
    ids = [str(i) for i in range(1, 7)]
    run = start(store, *ids)
    refused = [Result(Outcome.REFUSED, "403: client forbidden")]
    remover = FakeRemover({i: list(refused) for i in ids})
    assert Engine(store, remover, FakeClock()).run(run) is Ending.REFUSED
    assert remover.calls == ["1", "2", "3"]
    stopped = store.get_run(run)
    assert stopped.state is RunState.STOPPED
    assert "403: client forbidden" in stopped.message
    assert store.counts(run).pending == 3


def test_spending_limit_stops_cleanly_and_resumes(store: SqliteStore) -> None:
    run = start(store, "1", "2")
    remover = FakeRemover({"2": [Result(Outcome.SPENDING_LIMIT, "402: credits depleted")]})
    assert Engine(store, remover, FakeClock()).run(run) is Ending.SPENDING_LIMIT
    stopped = store.get_run(run)
    assert stopped.state is RunState.STOPPED
    assert "credits depleted" in stopped.message
    assert store.counts(run) == Counts(done=1, failed=0, pending=1)

    assert Engine(store, FakeRemover(), FakeClock()).run(run) is Ending.FINISHED
    assert store.counts(run) == Counts(done=2, failed=0, pending=0)


def test_not_logged_in_stops(store: SqliteStore) -> None:
    run = start(store, "1")
    remover = FakeRemover({"1": [Result(Outcome.NOT_LOGGED_IN, "run `xclean login`")]})
    assert Engine(store, remover, FakeClock()).run(run) is Ending.NOT_LOGGED_IN
    assert store.counts(run).pending == 1


# T16: stop and resume, retry failed (AC20, AC21)


class Interrupting(FakeRemover):
    def __init__(self, after: int) -> None:
        super().__init__()
        self.after = after

    def remove(self, item: Item) -> Result:
        if len(self.calls) == self.after:
            raise KeyboardInterrupt
        return super().remove(item)


def test_interrupt_then_resume_removes_each_item_exactly_once(tmp_path: Path) -> None:
    path = tmp_path / "x.db"
    store = SqliteStore(path)
    run = start(store, "1", "2", "3", "4")
    first = Interrupting(after=2)
    with pytest.raises(KeyboardInterrupt):
        Engine(store, first, FakeClock()).run(run)
    assert store.get_run(run).state is RunState.STOPPED
    store.close()

    reopened = SqliteStore(path)
    second = FakeRemover()
    Engine(reopened, second, FakeClock()).run(run)
    assert first.calls + second.calls == ["1", "2", "3", "4"]
    assert reopened.counts(run) == Counts(done=4, failed=0, pending=0)


def test_retry_failed_requeues_and_runs_again(store: SqliteStore) -> None:
    run = start(store, "1", "2")
    Engine(store, FakeRemover({"1": [Result(Outcome.FAILED, "oops")]}), FakeClock()).run(run)
    assert store.requeue_failed(run) == 1
    second = FakeRemover()
    Engine(store, second, FakeClock()).run(run)
    assert second.calls == ["1"]
    assert store.counts(run) == Counts(done=2, failed=0, pending=0)
