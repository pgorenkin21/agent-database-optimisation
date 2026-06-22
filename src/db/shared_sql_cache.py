"""Thread-safe LRU cache for shared SQL explore results (P1 middleware)."""

from __future__ import annotations

import threading
from collections import OrderedDict
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from src.db.sqlite_exec import SqlExecutionError, execute_sql
from src.db.sql_normalize import cache_key_for_sql


@dataclass(frozen=True)
class CachedSqlResult:
    rows: tuple[tuple[Any, ...], ...] | None
    error: str | None

    @classmethod
    def from_execution(
        cls,
        rows: list[tuple[Any, ...]] | None,
        error: SqlExecutionError | None,
    ) -> CachedSqlResult:
        frozen_rows = tuple(tuple(r) for r in rows) if rows is not None else None
        return cls(rows=frozen_rows, error=str(error) if error else None)

    def to_rows(self) -> list[tuple[Any, ...]] | None:
        if self.rows is None:
            return None
        return [tuple(r) for r in self.rows]

    def to_error(self) -> SqlExecutionError | None:
        if self.error is None:
            return None
        return SqlExecutionError(self.error, sql="")


@dataclass
class SqlCacheStats:
    hits: int = 0
    misses: int = 0
    stores: int = 0
    explore_hits: int = 0
    explore_misses: int = 0

    @property
    def total_lookups(self) -> int:
        return self.hits + self.misses

    @property
    def hit_rate_pct(self) -> float:
        if not self.total_lookups:
            return 0.0
        return 100.0 * self.hits / self.total_lookups

    def to_dict(self) -> dict[str, Any]:
        return {
            "hits": self.hits,
            "misses": self.misses,
            "stores": self.stores,
            "explore_hits": self.explore_hits,
            "explore_misses": self.explore_misses,
            "hit_rate_pct": round(self.hit_rate_pct, 2),
        }


class SharedSqlResultCache:
    """
    LRU cache keyed by (database path, AST-normalised SQL).

    Intended for explore-phase ``execute_sql`` calls across parallel replicas.
    """

    def __init__(self, *, max_entries: int = 4096) -> None:
        if max_entries < 1:
            raise ValueError("max_entries must be >= 1")
        self._max_entries = max_entries
        self._data: OrderedDict[tuple[str, str], CachedSqlResult] = OrderedDict()
        self._lock = threading.Lock()
        self.stats = SqlCacheStats()

    def get(
        self,
        *,
        db_path: Path,
        sql: str,
        sql_role: str,
    ) -> CachedSqlResult | None:
        if sql_role != "explore":
            return None
        key = cache_key_for_sql(sql, db_path=str(db_path.resolve()))
        with self._lock:
            entry = self._data.get(key)
            if entry is None:
                self.stats.misses += 1
                self.stats.explore_misses += 1
                return None
            self._data.move_to_end(key)
            self.stats.hits += 1
            self.stats.explore_hits += 1
            return entry

    def put(
        self,
        *,
        db_path: Path,
        sql: str,
        sql_role: str,
        rows: list[tuple[Any, ...]] | None,
        error: SqlExecutionError | None,
    ) -> None:
        if sql_role != "explore":
            return
        key = cache_key_for_sql(sql, db_path=str(db_path.resolve()))
        entry = CachedSqlResult.from_execution(rows, error)
        with self._lock:
            if key in self._data:
                self._data.move_to_end(key)
            self._data[key] = entry
            self.stats.stores += 1
            while len(self._data) > self._max_entries:
                self._data.popitem(last=False)

    def execute_or_get(
        self,
        *,
        db_path: Path,
        sql: str,
        sql_role: str,
        timeout_seconds: float | None,
    ) -> tuple[list[tuple[Any, ...]] | None, SqlExecutionError | None, bool]:
        """
        Return (rows, error, cache_hit).

        On miss, executes SQL and stores explore results in the cache.
        """
        cached = self.get(db_path=db_path, sql=sql, sql_role=sql_role)
        if cached is not None:
            return cached.to_rows(), cached.to_error(), True

        error: SqlExecutionError | None = None
        rows: list[tuple[Any, ...]] | None = None
        try:
            rows = execute_sql(db_path, sql, timeout_seconds=timeout_seconds)
        except SqlExecutionError as e:
            error = e

        self.put(
            db_path=db_path,
            sql=sql,
            sql_role=sql_role,
            rows=rows,
            error=error,
        )
        return rows, error, False
