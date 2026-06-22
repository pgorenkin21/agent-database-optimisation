"""Heuristic and semantic schema pruning for text-to-SQL prompts."""

from __future__ import annotations

import re
import sqlite3
from dataclasses import dataclass
from pathlib import Path

from src.agent.schema import (
    build_schema_context,
    descriptions_for_tables,
    ddl_for_tables,
    list_user_tables,
)
from src.agent.schema_embeddings import (
    normalize_scores,
    score_tables_semantic,
    table_profile_text,
)
from src.bird.tasks import BirdTask

_TOKEN_RE = re.compile(r"[a-z_][a-z0-9_]*", re.IGNORECASE)

# Boost fact/dimension tables when the question reads transactional (debit_card DB).
_TRANSACTIONAL_KEYWORDS = frozenset(
    {
        "amount",
        "consume",
        "consumption",
        "customer",
        "eur",
        "czk",
        "fuel",
        "gas",
        "paid",
        "payment",
        "price",
        "product",
        "purchase",
        "sale",
        "spent",
        "station",
        "transaction",
    }
)

_DEBIT_CARD_FACT = "transactions_1k"
SCHEMA_PRUNING_MODES = frozenset({"keyword", "semantic", "hybrid"})


@dataclass(frozen=True)
class SchemaPruningResult:
    selected_tables: tuple[str, ...]
    schema_context: str
    full_chars: int
    pruned_chars: int
    table_scores: dict[str, int]
    pruning_applied: bool
    fallback_reason: str | None = None
    pruning_mode: str = "keyword"
    semantic_scores: dict[str, float] | None = None

    @property
    def reduction_pct(self) -> float:
        if self.full_chars == 0:
            return 0.0
        return 100.0 * (1.0 - self.pruned_chars / self.full_chars)


def table_columns(db_path: Path, table: str) -> list[str]:
    conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    try:
        rows = conn.execute(f'PRAGMA table_info("{table}")').fetchall()
        return [str(r[1]) for r in rows]
    finally:
        conn.close()


def fk_neighbor_map(db_path: Path) -> dict[str, set[str]]:
    tables = list_user_tables(db_path)
    graph: dict[str, set[str]] = {t: set() for t in tables}
    conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    try:
        for table in tables:
            for row in conn.execute(f'PRAGMA foreign_key_list("{table}")').fetchall():
                ref = str(row[2])
                graph[table].add(ref)
                graph.setdefault(ref, set()).add(table)
    finally:
        conn.close()
    return graph


def tables_mentioned_in_sql(sql: str, tables: list[str]) -> set[str]:
    low = sql.lower()
    return {t for t in tables if re.search(rf"\b{re.escape(t.lower())}\b", low)}


def _task_text(task: BirdTask) -> str:
    return f"{task.question} {task.evidence}".lower()


def _transactional_context(text: str) -> bool:
    tokens = {t.lower() for t in _TOKEN_RE.findall(text)}
    return bool(tokens & _TRANSACTIONAL_KEYWORDS) or any(k in text for k in _TRANSACTIONAL_KEYWORDS)


def score_tables_for_task(
    task: BirdTask,
    db_path: Path,
    *,
    tables: list[str] | None = None,
) -> dict[str, int]:
    """Score tables by overlap between names/columns and question+evidence text."""
    table_list = tables or list_user_tables(db_path)
    text = _task_text(task)
    tokens = {t.lower() for t in _TOKEN_RE.findall(text)}
    scores: dict[str, int] = {}

    for table in table_list:
        score = 0
        table_l = table.lower()
        if table_l in tokens:
            score += 5
        if table_l in text:
            score += 3
        for col in table_columns(db_path, table):
            col_l = col.lower()
            if col_l in tokens:
                score += 2
            if col_l in text:
                score += 1
        scores[table] = score

    if task.db_id == "debit_card_specializing" and _transactional_context(text):
        if _DEBIT_CARD_FACT in scores:
            scores[_DEBIT_CARD_FACT] += 4

    return scores


def score_tables_semantic_for_task(
    task: BirdTask,
    db_path: Path,
    databases_dir: Path,
    *,
    tables: list[str] | None = None,
) -> dict[str, float]:
    """TF-IDF cosine scores between question+evidence and table/column descriptions."""
    table_list = tables or list_user_tables(db_path)
    query = _task_text(task)
    documents = {
        table: table_profile_text(
            task.db_id,
            databases_dir,
            table,
            columns=table_columns(db_path, table),
        )
        for table in table_list
    }
    return score_tables_semantic(query, documents)


def combined_table_scores(
    task: BirdTask,
    db_path: Path,
    databases_dir: Path,
    *,
    mode: str = "keyword",
    tables: list[str] | None = None,
) -> tuple[dict[str, float], dict[str, int], dict[str, float] | None]:
    """
    Return unified float scores for table selection.

    ``mode``: ``keyword`` | ``semantic`` | ``hybrid`` (50/50 normalized blend).
    """
    if mode not in SCHEMA_PRUNING_MODES:
        raise ValueError(f"Unknown schema pruning mode: {mode}")

    table_list = tables or list_user_tables(db_path)
    keyword = score_tables_for_task(task, db_path, tables=table_list)
    semantic_raw: dict[str, float] | None = None

    if mode == "keyword":
        return {t: float(keyword.get(t, 0)) for t in table_list}, keyword, None

    semantic_raw = score_tables_semantic_for_task(
        task, db_path, databases_dir, tables=table_list
    )
    semantic_norm = normalize_scores(semantic_raw)
    keyword_max = max(keyword.values()) if keyword else 0
    keyword_norm = {
        t: (keyword[t] / keyword_max if keyword_max else 0.0) for t in table_list
    }

    if mode == "semantic":
        return semantic_norm, keyword, semantic_raw

    blended = {
        t: 0.5 * keyword_norm.get(t, 0.0) + 0.5 * semantic_norm.get(t, 0.0)
        for t in table_list
    }
    return blended, keyword, semantic_raw


def _seed_tables_from_scores(
    ranked: list[str],
    scores: dict[str, float],
    *,
    min_score: float,
) -> list[str]:
    if not ranked:
        return []
    positive = [t for t in ranked if scores.get(t, 0.0) > 0]
    if positive:
        return positive
    if scores.get(ranked[0], 0.0) >= min_score:
        return [ranked[0]]
    return []


def _expand_fk_neighbors(selected: set[str], db_path: Path) -> None:
    graph = fk_neighbor_map(db_path)
    frontier = list(selected)
    while frontier:
        table = frontier.pop()
        for neighbor in graph.get(table, set()):
            if neighbor not in selected:
                selected.add(neighbor)
                frontier.append(neighbor)


def _apply_debit_card_rules(selected: set[str], tables: list[str], text: str) -> None:
    """debit_card_specializing: always include fact table; gasstations for customer/time joins."""
    if not selected:
        return
    if _DEBIT_CARD_FACT in tables:
        selected.add(_DEBIT_CARD_FACT)
    if "gasstations" in tables and (
        selected & {"customers", "yearmonth"} or _DEBIT_CARD_FACT in selected
    ):
        selected.add("gasstations")
    if "products" in tables and ("product" in text or "products" in selected):
        selected.add("products")


def _apply_student_club_rules(selected: set[str], tables: list[str]) -> None:
    """Sparse join hints without full FK expansion (student_club graph is fully connected)."""
    if "event" in selected and "attendance" in tables:
        selected.add("attendance")
    if "expense" in selected and "budget" in tables:
        selected.add("budget")


def _apply_domain_recall_rules(
    task: BirdTask,
    selected: set[str],
    tables: list[str],
) -> None:
    if task.db_id == "debit_card_specializing":
        _apply_debit_card_rules(selected, tables, _task_text(task))
    elif task.db_id == "student_club":
        _apply_student_club_rules(selected, tables)


def _apply_min_tables_floor(
    selected: set[str],
    tables: list[str],
    scores: dict[str, int],
    *,
    min_tables: int,
) -> None:
    """Only pad selection on larger schemas; skip when the DB is tiny."""
    if len(tables) <= min_tables + 1:
        return
    ranked = sorted(tables, key=lambda t: (-scores.get(t, 0), t))
    for table in ranked:
        if len(selected) >= min_tables:
            break
        selected.add(table)


def select_tables_for_task(
    task: BirdTask,
    db_path: Path,
    *,
    databases_dir: Path | None = None,
    expand_fk: bool = True,
    min_tables: int = 2,
    mode: str = "keyword",
    semantic_min_score: float = 0.05,
) -> tuple[tuple[str, ...], str | None]:
    """
    Pick tables for schema pruning.

    ``mode``: ``keyword`` | ``semantic`` | ``hybrid``.
    """
    tables = list_user_tables(db_path)
    if not tables:
        return (), None

    db_dir = databases_dir or db_path.parent.parent
    float_scores, int_scores, _ = combined_table_scores(
        task, db_path, db_dir, mode=mode, tables=tables
    )
    ranked = sorted(tables, key=lambda t: (-float_scores.get(t, 0.0), t))
    seeds = [t for t in ranked if int_scores.get(t, 0) > 0]
    if not seeds and mode != "keyword":
        seeds = _seed_tables_from_scores(
            ranked, float_scores, min_score=semantic_min_score
        )

    if not seeds:
        reason = "no_match_full_schema"
        return tuple(sorted(tables)), reason

    selected: set[str] = set(seeds)
    if expand_fk and task.db_id == "debit_card_specializing":
        _expand_fk_neighbors(selected, db_path)
    _apply_min_tables_floor(selected, tables, int_scores, min_tables=min_tables)
    _apply_domain_recall_rules(task, selected, tables)

    if len(selected) >= len(tables):
        return tuple(sorted(tables)), None

    return tuple(sorted(selected, key=lambda t: (-float_scores.get(t, 0.0), t))), None


def build_pruned_schema_context(
    task: BirdTask,
    db_path: Path,
    databases_dir: Path,
    *,
    expand_fk: bool = True,
    min_tables: int = 2,
    mode: str = "keyword",
    semantic_min_score: float = 0.05,
) -> SchemaPruningResult:
    """Build schema context limited to selected tables; report size vs full schema."""
    full_context = build_schema_context(db_path, databases_dir, task.db_id)
    all_tables = list_user_tables(db_path)
    _, int_scores, semantic_raw = combined_table_scores(
        task, db_path, databases_dir, mode=mode, tables=all_tables
    )
    selected, fallback_reason = select_tables_for_task(
        task,
        db_path,
        databases_dir=databases_dir,
        expand_fk=expand_fk,
        min_tables=min_tables,
        mode=mode,
        semantic_min_score=semantic_min_score,
    )

    if not selected or len(selected) >= len(all_tables):
        return SchemaPruningResult(
            selected_tables=tuple(all_tables),
            schema_context=full_context,
            full_chars=len(full_context),
            pruned_chars=len(full_context),
            table_scores=int_scores,
            pruning_applied=False,
            fallback_reason=fallback_reason,
            pruning_mode=mode,
            semantic_scores=semantic_raw,
        )

    ddl = ddl_for_tables(db_path, selected)
    descriptions = descriptions_for_tables(task.db_id, databases_dir, selected)
    parts = ["## SQLite schema (CREATE TABLE)", ddl]
    if descriptions:
        parts.extend(["## Column descriptions", descriptions])
    pruned = "\n\n".join(parts)

    return SchemaPruningResult(
        selected_tables=selected,
        schema_context=pruned,
        full_chars=len(full_context),
        pruned_chars=len(pruned),
        table_scores=int_scores,
        pruning_applied=True,
        fallback_reason=None,
        pruning_mode=mode,
        semantic_scores=semantic_raw,
    )
