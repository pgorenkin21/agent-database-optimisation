"""Tests for SQL helper utilities."""

from __future__ import annotations

from src.agent.sql_utils import format_sql_feedback, is_sqlite_missing_table_error


def test_format_sql_feedback_cache_hit() -> None:
    text = format_sql_feedback([(1, 2)], None, cache_hit=True)
    assert "cache hit" in text.lower()
    assert "Alice" not in text


def test_is_sqlite_missing_table_error() -> None:
    assert is_sqlite_missing_table_error("no such table: attendance")
    assert is_sqlite_missing_table_error('no such table: "Budget"')
    assert not is_sqlite_missing_table_error("syntax error near SELECT")
    assert not is_sqlite_missing_table_error(None)
