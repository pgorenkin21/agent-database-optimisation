"""SQL normalisation helpers (string + AST) for dedup and P1 cache keys."""

from __future__ import annotations

import sqlglot


def normalize_sql_string(sql: str) -> str:
    return " ".join(sql.split()).lower()


def normalize_sql_ast(sql: str) -> str | None:
    """AST-normalised SQL via sqlglot (P1 cache key)."""
    try:
        parsed = sqlglot.parse_one(sql.strip(), read="sqlite")
        return parsed.sql(dialect="sqlite", normalize=True).lower()
    except Exception:
        return None


def cache_key_for_sql(sql: str, *, db_path: str) -> tuple[str, str]:
    """Return (db_path, normalised_sql_key) for shared result cache lookup."""
    ast_key = normalize_sql_ast(sql)
    sql_key = ast_key if ast_key is not None else normalize_sql_string(sql)
    return db_path, sql_key
