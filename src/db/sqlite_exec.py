"""Execute SQL against BIRD SQLite databases (matches official BIRD evaluation)."""

from __future__ import annotations

import sqlite3
import threading
from pathlib import Path
from typing import Any


class SqlExecutionError(Exception):
    """Raised when SQL cannot be executed."""

    def __init__(self, message: str, *, sql: str | None = None) -> None:
        super().__init__(message)
        self.sql = sql


def _execute_sync(
    db_path: Path, sql: str, timeout_seconds: float | None
) -> list[tuple[Any, ...]]:
    conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    # Watchdog: SQLite query execution is a single C call that ignores Python
    # thread cancellation, so a runaway query (e.g. a cartesian join) would spin
    # a core forever. conn.interrupt() is thread-safe and aborts the in-flight
    # statement, making the timeout actually enforceable.
    timed_out = threading.Event()
    timer: threading.Timer | None = None
    if timeout_seconds is not None:

        def _interrupt() -> None:
            timed_out.set()
            conn.interrupt()

        timer = threading.Timer(timeout_seconds, _interrupt)
        timer.start()
    try:
        conn.row_factory = None
        cursor = conn.cursor()
        cursor.execute(sql)
        rows = cursor.fetchall()
        return [tuple(row) for row in rows]
    except sqlite3.OperationalError as e:
        if timed_out.is_set():
            raise SqlExecutionError(
                f"Query timed out after {timeout_seconds}s",
                sql=sql,
            ) from e
        raise
    finally:
        if timer is not None:
            timer.cancel()
        conn.close()


def execute_sql(
    db_path: Path,
    sql: str,
    *,
    timeout_seconds: float | None = 30.0,
) -> list[tuple[Any, ...]]:
    """
  Run read-only SQL and return result rows.

  Uses SQLite directly so BIRD gold SQL (IIF, etc.) matches official EX evaluation.
  A runaway query is aborted in-place via conn.interrupt() once timeout_seconds
  elapses (see _execute_sync).
  """
    sql = sql.strip()
    if not sql:
        raise SqlExecutionError("Empty SQL", sql=sql)

    try:
        return _execute_sync(db_path, sql, timeout_seconds)
    except sqlite3.Error as e:
        raise SqlExecutionError(str(e), sql=sql) from e
