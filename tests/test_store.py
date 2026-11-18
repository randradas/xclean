import multiprocessing
from datetime import UTC, datetime
from pathlib import Path

import pytest

from xclean.model import ContentType, Counts, Item, ItemStatus, PostKind, RunState
from xclean.store import LockedError, RunInProgress, SqliteStore, Store

ACCOUNT = "42"


def post(id: str, kind: PostKind = PostKind.ORIGINAL) -> Item:
    return Item(
        id=id,
        content_type=ContentType.POST,
        created_at=datetime(2019, 1, int(id) % 28 + 1, tzinfo=UTC),
        kind=kind,
        text=f"post {id}",
    )


@pytest.fixture
def store(tmp_path: Path) -> SqliteStore:
    return SqliteStore(tmp_path / "xclean.db")


# T7: runs, frozen selection, statuses, lock (AC18, AC20)


def test_start_run_freezes_selection_in_order(store: SqliteStore) -> None:
    run = store.start_run(ACCOUNT, [post("3"), post("1"), post("2")], rules="all posts")
    assert run.state is RunState.READY
    assert run.rules == "all posts"
    assert store.counts(run.id) == Counts(done=0, failed=0, pending=3)
    assert [i.id for i in store.pending(run.id)] == ["3", "1", "2"]


def test_items_round_trip(store: SqliteStore) -> None:
    item = post("7", PostKind.QUOTE)
    run = store.start_run(ACCOUNT, [item], rules="quotes")
    assert store.pending(run.id) == [item]


def test_mark_moves_items_out_of_pending(store: SqliteStore) -> None:
    run = store.start_run(ACCOUNT, [post("1"), post("2"), post("3")], rules="all posts")
    store.mark(run.id, "1", ItemStatus.DONE)
    store.mark(run.id, "2", ItemStatus.FAILED, reason="boom")
    assert [i.id for i in store.pending(run.id)] == ["3"]
    assert store.counts(run.id) == Counts(done=1, failed=1, pending=1)


def test_one_unfinished_run_per_account(store: SqliteStore) -> None:
    run = store.start_run(ACCOUNT, [post("1")], rules="all posts")
    with pytest.raises(RunInProgress) as e:
        store.start_run(ACCOUNT, [post("2")], rules="all posts")
    assert e.value.run.id == run.id
    # Other accounts are not blocked.
    store.start_run("99", [post("2")], rules="all posts")


def test_drop_run_allows_a_new_one(store: SqliteStore) -> None:
    run = store.start_run(ACCOUNT, [post("1")], rules="all posts")
    store.drop_run(run.id)
    assert store.current_run(ACCOUNT) is None
    store.start_run(ACCOUNT, [post("2")], rules="all posts")


def test_finished_run_allows_a_new_one(store: SqliteStore) -> None:
    run = store.start_run(ACCOUNT, [post("1")], rules="all posts")
    store.finish(run.id)
    assert store.current_run(ACCOUNT) is None
    assert store.latest_run(ACCOUNT) is not None
    store.start_run(ACCOUNT, [post("2")], rules="all posts")


def test_state_and_requests_are_saved(store: SqliteStore) -> None:
    run = store.start_run(ACCOUNT, [post("1")], rules="all posts")
    until = datetime(2026, 11, 17, 12, 15, tzinfo=UTC)
    store.set_state(run.id, RunState.WAITING, wait_until=until, message="rate limited")
    store.add_requests(run.id, 2)
    saved = store.current_run(ACCOUNT)
    assert saved is not None
    assert saved.state is RunState.WAITING
    assert saved.wait_until == until
    assert saved.message == "rate limited"
    assert saved.requests == 2


def test_progress_survives_reopening(tmp_path: Path) -> None:
    path = tmp_path / "xclean.db"
    first = SqliteStore(path)
    run = first.start_run(ACCOUNT, [post("1"), post("2")], rules="all posts")
    first.mark(run.id, "1", ItemStatus.DONE)
    first.close()
    second = SqliteStore(path)
    assert [i.id for i in second.pending(run.id)] == ["2"]


def test_requeue_failed(store: SqliteStore) -> None:
    run = store.start_run(ACCOUNT, [post("1"), post("2")], rules="all posts")
    store.mark(run.id, "1", ItemStatus.FAILED, reason="boom")
    assert store.requeue_failed(run.id) == 1
    assert store.counts(run.id) == Counts(done=0, failed=0, pending=2)


def _try_lock(path: str, queue: "multiprocessing.Queue[str]") -> None:
    try:
        with SqliteStore(Path(path)).lock(ACCOUNT):
            queue.put("got")
    except LockedError:
        queue.put("locked")


def test_lock_blocks_a_second_process(tmp_path: Path) -> None:
    path = tmp_path / "xclean.db"
    store = SqliteStore(path)
    queue: multiprocessing.Queue[str] = multiprocessing.Queue()
    with store.lock(ACCOUNT):
        proc = multiprocessing.Process(target=_try_lock, args=(str(path), queue))
        proc.start()
        proc.join()
        assert queue.get() == "locked"
    proc = multiprocessing.Process(target=_try_lock, args=(str(path), queue))
    proc.start()
    proc.join()
    assert queue.get() == "got"


# T8: final report (AC25)


def test_report_lists_failures_with_reasons(store: SqliteStore) -> None:
    run = store.start_run(ACCOUNT, [post("1"), post("2"), post("3")], rules="all posts")
    store.mark(run.id, "1", ItemStatus.DONE)
    store.mark(run.id, "2", ItemStatus.FAILED, reason="403 forbidden")
    store.mark(run.id, "3", ItemStatus.DONE)
    store.finish(run.id)
    report = store.report(run.id)
    assert report.run.state is RunState.FINISHED
    assert report.run.finished_at is not None
    assert report.counts == Counts(done=2, failed=1, pending=0)
    assert [(f.item.id, f.reason) for f in report.failures] == [("2", "403 forbidden")]


def test_report_is_readable_from_a_new_store(tmp_path: Path) -> None:
    path = tmp_path / "xclean.db"
    first = SqliteStore(path)
    run = first.start_run(ACCOUNT, [post("1")], rules="all posts")
    first.mark(run.id, "1", ItemStatus.FAILED, reason="boom")
    first.finish(run.id)
    first.close()
    latest = SqliteStore(path).latest_run(ACCOUNT)
    assert latest is not None
    assert SqliteStore(path).report(latest.id).failures[0].reason == "boom"


def test_sqlite_store_satisfies_the_store_protocol(store: SqliteStore) -> None:
    _: Store = store  # checked by mypy


def test_requeue_failed_reopens_a_finished_run(store: SqliteStore) -> None:
    run = store.start_run(ACCOUNT, [post("1")], rules="all posts")
    store.mark(run.id, "1", ItemStatus.FAILED, reason="boom")
    store.finish(run.id)
    assert store.requeue_failed(run.id) == 1
    reopened = store.current_run(ACCOUNT)
    assert reopened is not None
    assert reopened.state is RunState.READY


def test_requeue_with_no_failures_keeps_run_finished(store: SqliteStore) -> None:
    run = store.start_run(ACCOUNT, [post("1")], rules="all posts")
    store.mark(run.id, "1", ItemStatus.DONE)
    store.finish(run.id)
    assert store.requeue_failed(run.id) == 0
    assert store.current_run(ACCOUNT) is None


def test_store_files_are_private(tmp_path: Path) -> None:
    """The store holds post text: only the user may read it (R9)."""
    store = SqliteStore(tmp_path / "state" / "xclean.db")
    store.start_run("42", [], rules="all posts")
    with store.lock("42"):
        files = list(store.path.parent.iterdir())
        assert {f.name for f in files} >= {"xclean.db", "xclean.db-wal", "xclean.db.42.lock"}
        for f in files:
            assert f.stat().st_mode & 0o077 == 0, f.name
    assert store.path.parent.stat().st_mode & 0o777 == 0o700


def test_requeue_clears_the_old_stop_message(store: SqliteStore) -> None:
    run = store.start_run(ACCOUNT, [post("1")], rules="all posts")
    store.mark(run.id, "1", ItemStatus.FAILED, reason="boom")
    store.set_state(run.id, RunState.STOPPED, message="interrupted")
    store.requeue_failed(run.id)
    requeued = store.get_run(run.id)
    assert requeued.state is RunState.READY
    assert requeued.message == ""
