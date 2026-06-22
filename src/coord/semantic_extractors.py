"""Rule-based fact extraction from explore SQL and result sets."""

from __future__ import annotations

import re
from typing import Any

from src.db.sql_fragments import extract_sql_fragments
from src.db.sql_normalize import normalize_sql_ast

_NUMERIC_RE = re.compile(r"^-?\d+(\.\d+)?$")
_MAX_DISTINCT_SAMPLES = 5
_MAX_STRING_LEN = 40


def _stringify(value: Any) -> str:
    text = repr(value) if not isinstance(value, str) else value
    text = text.strip()
    if len(text) > _MAX_STRING_LEN:
        return text[: _MAX_STRING_LEN - 1] + "…"
    return text


def _tables_from_sql(sql: str) -> list[str]:
    return sorted(
        frag.removeprefix("table:")
        for frag in extract_sql_fragments(sql)
        if frag.startswith("table:")
    )


def _join_hints_from_sql(sql: str) -> list[str]:
    return sorted(
        frag.removeprefix("join_on:")
        for frag in extract_sql_fragments(sql)
        if frag.startswith("join_on:")
    )


def _numeric_stats(rows: list[tuple[Any, ...]]) -> list[str]:
    if not rows:
        return []
    ncol = len(rows[0])
    facts: list[str] = []
    for col_idx in range(ncol):
        values: list[float] = []
        for row in rows:
            if col_idx >= len(row):
                continue
            val = row[col_idx]
            if isinstance(val, (int, float)) and not isinstance(val, bool):
                values.append(float(val))
            elif isinstance(val, str) and _NUMERIC_RE.match(val.strip()):
                values.append(float(val.strip()))
        if not values:
            continue
        if len(values) == 1:
            facts.append(f"column[{col_idx}]={values[0]:g}")
        else:
            facts.append(
                f"column[{col_idx}] min={min(values):g} max={max(values):g} "
                f"avg={sum(values) / len(values):g}"
            )
    return facts[:3]


def _distinct_samples(rows: list[tuple[Any, ...]], *, max_values: int = _MAX_DISTINCT_SAMPLES) -> list[str]:
    if not rows or len(rows) > 50:
        return []
    ncol = len(rows[0])
    facts: list[str] = []
    for col_idx in range(min(ncol, 4)):
        seen: list[str] = []
        for row in rows:
            if col_idx >= len(row):
                continue
            text = _stringify(row[col_idx])
            if text not in seen:
                seen.append(text)
            if len(seen) >= max_values:
                break
        if 1 < len(seen) <= max_values:
            facts.append(f"column[{col_idx}] samples: {', '.join(seen)}")
    return facts


def extract_semantic_facts(
    *,
    sql: str,
    rows: list[tuple[Any, ...]] | None,
    error: str | None,
) -> list[str]:
    """
    Distil explore SQL + results into compact, reusable facts for prompt injection.

    No LLM calls — purely structural / statistical rules.
    """
    facts: list[str] = []
    tables = _tables_from_sql(sql)
    ast = normalize_sql_ast(sql)
    if ast:
        facts.append(f"explored: {ast[:120]}{'…' if len(ast) > 120 else ''}")

    for join in _join_hints_from_sql(sql)[:2]:
        facts.append(f"join works: {join[:80]}{'…' if len(join) > 80 else ''}")

    if error:
        err = error.strip()
        if len(err) > 100:
            err = err[:99] + "…"
        if tables:
            facts.append(f"{'/'.join(tables)} error: {err}")
        else:
            facts.append(f"SQL error: {err}")
        return facts

    if rows is None:
        return facts

    n = len(rows)
    if tables:
        facts.append(f"{'/'.join(tables)} returned {n} row(s)")
    else:
        facts.append(f"query returned {n} row(s)")

    if n == 0:
        return facts

    facts.extend(_numeric_stats(rows))
    facts.extend(_distinct_samples(rows))
    return facts
