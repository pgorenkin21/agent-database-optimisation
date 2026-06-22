"""Prompt construction for the text-to-SQL agent."""

from __future__ import annotations

from typing import Any

from src.bird.tasks import BirdTask

DISCOVERY_CONTEXT_PREFIX = "Shared discoveries from parallel replicas on this task"
SEMANTIC_CONTEXT_PREFIX = "Shared semantic facts from parallel replicas on this task"


SYSTEM_TEMPLATE = """You are a data analyst that answers questions by writing SQLite SQL.

You have tools:
- execute_sql: run a read-only SELECT (or WITH ... SELECT) to explore the database.
- submit_sql: submit your final SELECT query that answers the question.

Rules:
- Use execute_sql to inspect tables and validate logic before submitting.
- Only read-only SQL (SELECT / WITH). No INSERT, UPDATE, DELETE, or DDL.
- When ready, call submit_sql exactly once with the final answer query.
- The database is SQLite. Use valid SQLite syntax.
- When peer discoveries are listed below, prefer building on them instead of re-probing the same tables, columns, or predicates.
"""


def format_discovery_context(peer_fragments: list[str]) -> str:
    """Format peer fragment keys as a compact user-message block."""
    if not peer_fragments:
        return ""

    tables: list[str] = []
    columns: list[str] = []
    predicates: list[str] = []
    joins: list[str] = []

    for frag in peer_fragments:
        if frag.startswith("table:"):
            tables.append(frag.removeprefix("table:"))
        elif frag.startswith("col:"):
            columns.append(frag.removeprefix("col:"))
        elif frag.startswith("pred:"):
            predicates.append(frag.removeprefix("pred:"))
        elif frag.startswith("join_on:"):
            joins.append(frag.removeprefix("join_on:"))

    lines = [
        f"{DISCOVERY_CONTEXT_PREFIX} (avoid redundant explore queries when possible):",
    ]
    if tables:
        lines.append(f"- Tables: {', '.join(sorted(set(tables)))}")
    if columns:
        lines.append(f"- Columns: {', '.join(sorted(set(columns)))}")
    if predicates:
        shown = sorted(set(predicates))[:12]
        suffix = " …" if len(predicates) > len(shown) else ""
        lines.append(f"- Predicates: {', '.join(shown)}{suffix}")
    if joins:
        shown = sorted(set(joins))[:6]
        suffix = " …" if len(joins) > len(shown) else ""
        lines.append(f"- Join conditions: {', '.join(shown)}{suffix}")

    return "\n".join(lines)


def format_semantic_context(facts: list[str]) -> str:
    """Format distilled peer facts as a compact, bounded user-message block."""
    if not facts:
        return ""
    lines = [
        f"{SEMANTIC_CONTEXT_PREFIX} (reuse these instead of re-probing):",
    ]
    for fact in facts:
        lines.append(f"- {fact}")
    return "\n".join(lines)


def apply_semantic_context(messages: list[dict[str, Any]], context: str) -> None:
    """Replace any prior semantic user message with the latest context."""
    messages[:] = [
        m
        for m in messages
        if not (
            m.get("role") == "user"
            and str(m.get("content", "")).startswith(SEMANTIC_CONTEXT_PREFIX)
        )
    ]
    if context.strip():
        messages.append({"role": "user", "content": context})


def apply_discovery_context(messages: list[dict[str, Any]], context: str) -> None:
    """Replace any prior discovery user message with the latest context."""
    messages[:] = [
        m
        for m in messages
        if not (
            m.get("role") == "user"
            and str(m.get("content", "")).startswith(DISCOVERY_CONTEXT_PREFIX)
        )
    ]
    if context.strip():
        messages.append({"role": "user", "content": context})


def build_task_user_message(
    task: BirdTask,
    schema_context: str,
    *,
    use_evidence: bool,
) -> str:
    user_parts = [
        f"Database id: {task.db_id}",
        "",
        schema_context,
        "",
        f"Question: {task.question}",
    ]
    if use_evidence and task.evidence.strip():
        user_parts.extend(["", f"Evidence (hints): {task.evidence}"])
    return "\n".join(user_parts)


def build_initial_messages(
    task: BirdTask,
    schema_context: str,
    *,
    use_evidence: bool,
) -> list[dict]:
    return [
        {"role": "system", "content": SYSTEM_TEMPLATE},
        {
            "role": "user",
            "content": build_task_user_message(
                task, schema_context, use_evidence=use_evidence
            ),
        },
    ]
