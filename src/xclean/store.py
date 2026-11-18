"""Progress store: runs, their frozen selection, and each item's result.

The core only uses the `Store` protocol, so the cloud runner can swap in another store.
Every write is committed at once: a result is saved before the next request is sent.
"""

import fcntl
import os
import sqlite3
from collections.abc import Iterator, Sequence
from contextlib import AbstractContextManager, contextmanager
from datetime import UTC, datetime
from pathlib import Path
from typing import Protocol

from xclean import paths
from xclean.model import (
    ContentType,
    Counts,
    Failure,
    Item,
    ItemStatus,
    PostKind,
    Report,
    Run,
    RunState,
)


class RunInProgress(Exception):
    """The account already has an unfinished run: resume it or drop it first."""

    def __init__(self, run: Run) -> None:
        super().__init__(f"run {run.id} is not finished")
        self.run = run


class LockedError(Exception):
    """Another process is running a removal for this account."""


class Store(Protocol):
    def start_run(self, account_id: str, items: Sequence[Item], rules: str) -> Run: ...
    def current_run(self, account_id: str) -> Run | None: ...
    def latest_run(self, account_id: str) -> Run | None: ...
    def get_run(self, run_id: int) -> Run: ...
    def drop_run(self, run_id: int) -> None: ...
    def pending(self, run_id: int) -> list[Item]: ...
    def mark(self, run_id: int, item_id: str, status: ItemStatus, reason: str = "") -> None: ...
    def counts(self, run_id: int) -> Counts: ...
    def requeue_failed(self, run_id: int) -> int: ...
    def set_state(
        self,
        run_id: int,
        state: RunState,
        wait_until: datetime | None = None,
        message: str = "",
    ) -> None: ...
    def add_requests(self, run_id: int, n: int = 1) -> None: ...
    def finish(self, run_id: int) -> None: ...
    def report(self, run_id: int) -> Report: ...
    def lock(self, account_id: str) -> AbstractContextManager[None]: ...


_SCHEMA = """
CREATE TABLE IF NOT EXISTS runs (
    id INTEGER PRIMARY KEY,
    account_id TEXT NOT NULL,
    created_at TEXT NOT NULL,
    rules TEXT NOT NULL,
    state TEXT NOT NULL,
    requests INTEGER NOT NULL DEFAULT 0,
    wait_until TEXT,
    message TEXT NOT NULL DEFAULT '',
    finished_at TEXT
);
CREATE TABLE IF NOT EXISTS items (
    run_id INTEGER NOT NULL REFERENCES runs(id) ON DELETE CASCADE,
    seq INTEGER NOT NULL,
    item_id TEXT NOT NULL,
    content_type TEXT NOT NULL,
    kind TEXT,
    created_at TEXT NOT NULL,
    text TEXT NOT NULL,
    status TEXT NOT NULL,
    reason TEXT NOT NULL DEFAULT '',
    PRIMARY KEY (run_id, item_id)
);
CREATE INDEX IF NOT EXISTS items_by_status ON items (run_id, status, seq);
"""


def _ts(value: str | None) -> datetime | None:
    return datetime.fromisoformat(value) if value else None


def _unique(items: Sequence[Item]) -> list[Item]:
    """An ID listed twice is removed once; first one wins, order kept."""
    seen: dict[str, Item] = {}
    for item in items:
        seen.setdefault(item.id, item)
    return list(seen.values())


class SqliteStore:
    def __init__(self, path: Path) -> None:
        self.path = path
        # Post text lives here: folder and files readable only by the user. SQLite gives the
        # -wal and -shm files the same mode as the database file.
        paths.ensure(path.parent)
        os.close(os.open(path, os.O_RDWR | os.O_CREAT, 0o600))
        path.chmod(0o600)
        self._db = sqlite3.connect(path, isolation_level=None)  # autocommit
        self._db.row_factory = sqlite3.Row
        self._db.execute("PRAGMA journal_mode=WAL")  # status can read while a run writes
        self._db.execute("PRAGMA foreign_keys=ON")
        self._db.executescript(_SCHEMA)

    def close(self) -> None:
        self._db.close()

    def _run(self, row: sqlite3.Row) -> Run:
        return Run(
            id=row["id"],
            account_id=row["account_id"],
            created_at=datetime.fromisoformat(row["created_at"]),
            rules=row["rules"],
            state=RunState(row["state"]),
            requests=row["requests"],
            wait_until=_ts(row["wait_until"]),
            message=row["message"],
            finished_at=_ts(row["finished_at"]),
        )

    def _item(self, row: sqlite3.Row) -> Item:
        return Item(
            id=row["item_id"],
            content_type=ContentType(row["content_type"]),
            created_at=datetime.fromisoformat(row["created_at"]),
            kind=PostKind(row["kind"]) if row["kind"] else None,
            text=row["text"],
        )

    def start_run(self, account_id: str, items: Sequence[Item], rules: str) -> Run:
        if (current := self.current_run(account_id)) is not None:
            raise RunInProgress(current)
        with self._transaction():
            cur = self._db.execute(
                "INSERT INTO runs (account_id, created_at, rules, state) VALUES (?, ?, ?, ?)",
                (account_id, datetime.now(UTC).isoformat(), rules, RunState.READY),
            )
            run_id = cur.lastrowid
            assert run_id is not None
            self._db.executemany(
                "INSERT INTO items (run_id, seq, item_id, content_type, kind, created_at, text,"
                " status) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                [
                    (
                        run_id,
                        seq,
                        i.id,
                        i.content_type,
                        i.kind,
                        i.created_at.isoformat(),
                        i.text,
                        ItemStatus.PENDING,
                    )
                    for seq, i in enumerate(_unique(items))
                ],
            )
        return self.get_run(run_id)

    @contextmanager
    def _transaction(self) -> Iterator[None]:
        self._db.execute("BEGIN")
        try:
            yield
        except BaseException:
            self._db.execute("ROLLBACK")
            raise
        self._db.execute("COMMIT")

    def get_run(self, run_id: int) -> Run:
        row = self._db.execute("SELECT * FROM runs WHERE id = ?", (run_id,)).fetchone()
        if row is None:
            raise KeyError(f"no run {run_id}")
        return self._run(row)

    def current_run(self, account_id: str) -> Run | None:
        row = self._db.execute(
            "SELECT * FROM runs WHERE account_id = ? AND finished_at IS NULL"
            " ORDER BY id DESC LIMIT 1",
            (account_id,),
        ).fetchone()
        return self._run(row) if row else None

    def latest_run(self, account_id: str) -> Run | None:
        row = self._db.execute(
            "SELECT * FROM runs WHERE account_id = ? ORDER BY id DESC LIMIT 1", (account_id,)
        ).fetchone()
        return self._run(row) if row else None

    def drop_run(self, run_id: int) -> None:
        self._db.execute("DELETE FROM runs WHERE id = ?", (run_id,))

    def pending(self, run_id: int) -> list[Item]:
        rows = self._db.execute(
            "SELECT * FROM items WHERE run_id = ? AND status = ? ORDER BY seq",
            (run_id, ItemStatus.PENDING),
        )
        return [self._item(r) for r in rows]

    def _update(self, sql: str, params: tuple[object, ...], missing: str) -> None:
        """Run an UPDATE; a wrong id is a bug, so touching no row raises."""
        if self._db.execute(sql, params).rowcount == 0:
            raise KeyError(missing)

    def mark(self, run_id: int, item_id: str, status: ItemStatus, reason: str = "") -> None:
        self._update(
            "UPDATE items SET status = ?, reason = ? WHERE run_id = ? AND item_id = ?",
            (status, reason, run_id, item_id),
            f"no item {item_id} in run {run_id}",
        )

    def counts(self, run_id: int) -> Counts:
        rows = self._db.execute(
            "SELECT status, COUNT(*) AS n FROM items WHERE run_id = ? GROUP BY status", (run_id,)
        )
        by_status = {r["status"]: r["n"] for r in rows}
        return Counts(
            done=by_status.get(ItemStatus.DONE, 0),
            failed=by_status.get(ItemStatus.FAILED, 0),
            pending=by_status.get(ItemStatus.PENDING, 0),
        )

    def requeue_failed(self, run_id: int) -> int:
        """Put failed items back to pending. Reopens the run if it had finished."""
        with self._transaction():
            cur = self._db.execute(
                "UPDATE items SET status = ?, reason = '' WHERE run_id = ? AND status = ?",
                (ItemStatus.PENDING, run_id, ItemStatus.FAILED),
            )
            if cur.rowcount:
                self._db.execute(
                    "UPDATE runs SET state = ?, finished_at = NULL, wait_until = NULL,"
                    " message = '' WHERE id = ?",
                    (RunState.READY, run_id),
                )
        return cur.rowcount

    def set_state(
        self,
        run_id: int,
        state: RunState,
        wait_until: datetime | None = None,
        message: str = "",
    ) -> None:
        self._update(
            "UPDATE runs SET state = ?, wait_until = ?, message = ? WHERE id = ?",
            (state, wait_until.isoformat() if wait_until else None, message, run_id),
            f"no run {run_id}",
        )

    def add_requests(self, run_id: int, n: int = 1) -> None:
        self._update(
            "UPDATE runs SET requests = requests + ? WHERE id = ?", (n, run_id), f"no run {run_id}"
        )

    def finish(self, run_id: int) -> None:
        self._update(
            "UPDATE runs SET state = ?, wait_until = NULL, message = '', finished_at = ?"
            " WHERE id = ?",
            (RunState.FINISHED, datetime.now(UTC).isoformat(), run_id),
            f"no run {run_id}",
        )

    def report(self, run_id: int) -> Report:
        rows = self._db.execute(
            "SELECT * FROM items WHERE run_id = ? AND status = ? ORDER BY seq",
            (run_id, ItemStatus.FAILED),
        )
        return Report(
            run=self.get_run(run_id),
            counts=self.counts(run_id),
            failures=[Failure(item=self._item(r), reason=r["reason"]) for r in rows],
        )

    @contextmanager
    def lock(self, account_id: str) -> Iterator[None]:
        """Hold while removing. The OS frees it if the process dies."""
        path = self.path.with_name(f"{self.path.name}.{account_id}.lock")
        with os.fdopen(os.open(path, os.O_WRONLY | os.O_CREAT, 0o600), "w") as f:
            try:
                fcntl.flock(f, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError:
                raise LockedError("another xclean run is active for this account") from None
            try:
                yield
            finally:
                fcntl.flock(f, fcntl.LOCK_UN)
