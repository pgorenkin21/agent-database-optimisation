"""SQL parsing helpers for the agent."""

from __future__ import annotations

import re


def strip_sql_markdown(sql: str) -> str:
    """Remove markdown code fences if the model wrapped SQL."""
    text = sql.strip()
    match = re.search(r"```(?:sql)?\s*([\s\S]*?)```", text, re.IGNORECASE)
    if match:
        return match.group(1).strip()
    return text


def validate_read_only_sql(sql: str) -> None:
    """Raise ValueError if SQL is not a read-only SELECT/WITH."""
    cleaned = strip_sql_markdown(sql).strip()
    if not cleaned:
        raise ValueError("Empty SQL")

    upper = cleaned.upper()
    # Allow only statements starting with SELECT or WITH (CTE)
    if not (upper.startswith("SELECT") or upper.startswith("WITH")):
        raise ValueError("Only SELECT or WITH queries are allowed")

    forbidden = (
        "INSERT ",
        "UPDATE ",
        "DELETE ",
        "DROP ",
        "ALTER ",
        "CREATE ",
        "ATTACH ",
        "DETACH ",
        "REPLACE ",
        "TRUNCATE ",
    )
    for token in forbidden:
        if token in upper:
            raise ValueError(f"Forbidden statement type in SQL: {token.strip()}")


def format_sql_feedback(
    rows: list[tuple] | None,
    error: str | None,
    *,
    max_rows: int = 10,
) -> str:
    if error:
        return f"SQL error: {error}"
    if rows is None:
        return "SQL error: unknown failure"
    if len(rows) == 0:
        return "Success: 0 rows returned."
    lines = [f"Success: {len(rows)} row(s). First rows:"]
    for row in rows[:max_rows]:
        lines.append(repr(row))
    if len(rows) > max_rows:
        lines.append(f"... ({len(rows) - max_rows} more rows not shown)")
    return "\n".join(lines)
