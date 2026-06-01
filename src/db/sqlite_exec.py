"""Execute SQL against BIRD SQLite databases (matches official BIRD evaluation)."""

from __future__ import annotations

import sqlite3
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FuturesTimeoutError
from pathlib import Path
from typing import Any


class SqlExecutionError(Exception):
    """Raised when SQL cannot be executed."""

    def __init__(self, message: str, *, sql: str | None = None) -> None:
        super().__init__(message)
        self.sql = sql


def _execute_sync(db_path: Path, sql: str) -> list[tuple[Any, ...]]:
    conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    try:
        conn.row_factory = None
        cursor = conn.cursor()
        cursor.execute(sql)
        rows = cursor.fetchall()
        return [tuple(row) for row in rows]
    finally:
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
  """
    sql = sql.strip()
    if not sql:
        raise SqlExecutionError("Empty SQL", sql=sql)

    try:
        if timeout_seconds is None:
            return _execute_sync(db_path, sql)
        with ThreadPoolExecutor(max_workers=1) as pool:
            future = pool.submit(_execute_sync, db_path, sql)
            return future.result(timeout=timeout_seconds)
    except FuturesTimeoutError as e:
        raise SqlExecutionError(
            f"Query timed out after {timeout_seconds}s",
            sql=sql,
        ) from e
    except sqlite3.Error as e:
        raise SqlExecutionError(str(e), sql=sql) from e
