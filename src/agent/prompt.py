"""Prompt construction for the text-to-SQL agent."""

from __future__ import annotations

from src.bird.tasks import BirdTask

SYSTEM_TEMPLATE = """You are a data analyst that answers questions by writing SQLite SQL.

You have tools:
- execute_sql: run a read-only SELECT (or WITH ... SELECT) to explore the database.
- submit_sql: submit your final SELECT query that answers the question.

Rules:
- Use execute_sql to inspect tables and validate logic before submitting.
- Only read-only SQL (SELECT / WITH). No INSERT, UPDATE, DELETE, or DDL.
- When ready, call submit_sql exactly once with the final answer query.
- The database is SQLite. Use valid SQLite syntax.
"""


def build_initial_messages(
    task: BirdTask,
    schema_context: str,
    *,
    use_evidence: bool,
) -> list[dict]:
    user_parts = [
        f"Database id: {task.db_id}",
        "",
        schema_context,
        "",
        f"Question: {task.question}",
    ]
    if use_evidence and task.evidence.strip():
        user_parts.extend(["", f"Evidence (hints): {task.evidence}"])

    return [
        {"role": "system", "content": SYSTEM_TEMPLATE},
        {"role": "user", "content": "\n".join(user_parts)},
    ]
