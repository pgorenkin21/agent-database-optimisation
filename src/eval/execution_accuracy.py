"""Execution accuracy (EX) — same logic as BIRD llm/src/evaluation.py."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from src.db.sqlite_exec import SqlExecutionError, execute_sql


def compare_result_sets(
    predicted: list[tuple[Any, ...]],
    gold: list[tuple[Any, ...]],
) -> bool:
    """True if result sets are identical (order-independent)."""
    return set(predicted) == set(gold)


def results_match(
    db_path: Path,
    predicted_sql: str,
    gold_sql: str,
    *,
    timeout_seconds: float | None = 30.0,
) -> tuple[bool, list[tuple[Any, ...]] | None, list[tuple[Any, ...]] | None, str | None]:
    """
  Execute both SQL statements and compare results.

  Returns (match, predicted_rows, gold_rows, error_message).
  """
    try:
        gold_rows = execute_sql(db_path, gold_sql, timeout_seconds=timeout_seconds)
        predicted_rows = execute_sql(db_path, predicted_sql, timeout_seconds=timeout_seconds)
        return compare_result_sets(predicted_rows, gold_rows), predicted_rows, gold_rows, None
    except SqlExecutionError as e:
        return False, None, None, str(e)


def execution_accuracy(
    db_path: Path,
    predicted_sql: str,
    gold_sql: str,
    *,
    timeout_seconds: float | None = 30.0,
) -> int:
    """Return 1 if EX match, 0 otherwise (BIRD convention)."""
    match, _, _, _ = results_match(
        db_path,
        predicted_sql,
        gold_sql,
        timeout_seconds=timeout_seconds,
    )
    return 1 if match else 0
