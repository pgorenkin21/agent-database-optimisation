"""Tests for rule-based semantic fact extraction."""

from __future__ import annotations

from src.coord.semantic_extractors import extract_semantic_facts


def test_extract_row_count_fact() -> None:
    facts = extract_semantic_facts(
        sql="SELECT * FROM customers LIMIT 5",
        rows=[(1, "Alice"), (2, "Bob")],
        error=None,
    )
    assert any("customers returned 2 row" in f for f in facts)


def test_extract_error_fact() -> None:
    facts = extract_semantic_facts(
        sql="SELECT * FROM missing_table",
        rows=None,
        error="no such table: missing_table",
    )
    assert any("error" in f.lower() for f in facts)


def test_extract_numeric_stats() -> None:
    facts = extract_semantic_facts(
        sql="SELECT amount FROM transactions_1k",
        rows=[(10.0,), (20.0,)],
        error=None,
    )
    assert any("min=10" in f and "max=20" in f for f in facts)
