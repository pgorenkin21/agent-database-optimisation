"""Tests for heuristic schema pruning."""

from __future__ import annotations

import pytest

from src.agent.schema import build_schema_context, list_user_tables
from src.agent.schema_pruning import (
    build_pruned_schema_context,
    select_tables_for_task,
    tables_mentioned_in_sql,
)
from src.config import load_config

DEBIT_CARD_MISSES = (1472, 1479, 1490, 1501, 1506, 1507, 1509, 1514, 1515, 1524, 1525, 1526, 1529)


@pytest.fixture
def cfg():
    c = load_config()
    if not c.tasks_json.exists():
        pytest.skip("BIRD mini-dev not downloaded")
    return c


def test_pruned_schema_smaller_when_pruning_applied(cfg) -> None:
    from src.bird.tasks import load_tasks, sqlite_path_for_task

    task = load_tasks(cfg)[0]
    db_path = sqlite_path_for_task(task, cfg)
    full = build_schema_context(db_path, cfg.databases_dir, task.db_id)
    pruned = build_pruned_schema_context(task, db_path, cfg.databases_dir)
    assert pruned.full_chars == len(full)
    if pruned.pruning_applied:
        assert pruned.pruned_chars < pruned.full_chars


def test_select_tables_mentions_customers_for_currency_question(cfg) -> None:
    from src.bird.tasks import get_task, sqlite_path_for_task

    task = get_task(1471, cfg)
    db_path = sqlite_path_for_task(task, cfg)
    selected, _ = select_tables_for_task(task, db_path)
    assert "customers" in selected
    assert "transactions_1k" in selected


def test_debit_card_miss_tasks_now_cover_gold_tables(cfg) -> None:
    from src.bird.tasks import get_task, sqlite_path_for_task

    for qid in DEBIT_CARD_MISSES:
        task = get_task(qid, cfg)
        db_path = sqlite_path_for_task(task, cfg)
        tables = list_user_tables(db_path)
        gold = tables_mentioned_in_sql(task.gold_sql, tables)
        selected, _ = select_tables_for_task(task, db_path)
        assert gold <= set(selected), f"qid={qid} gold={gold} selected={selected}"


def test_no_keyword_match_uses_full_schema(cfg) -> None:
    from src.bird.tasks import BirdTask, sqlite_path_for_task

    task = BirdTask(
        question_id=99999,
        db_id="debit_card_specializing",
        question="What is the answer?",
        evidence="",
        gold_sql="SELECT 1",
        difficulty="simple",
    )
    db_path = sqlite_path_for_task(
        __import__("src.bird.tasks", fromlist=["get_task"]).get_task(1471, cfg),
        cfg,
    )
    selected, reason = select_tables_for_task(task, db_path)
    assert reason == "no_match_full_schema"
    assert len(selected) == len(list_user_tables(db_path))

    result = build_pruned_schema_context(task, db_path, cfg.databases_dir)
    assert result.pruning_applied is False
    assert result.fallback_reason == "no_match_full_schema"


def test_student_club_event_queries_include_attendance(cfg) -> None:
    from src.bird.tasks import get_task, sqlite_path_for_task

    for qid in (1317, 1322):
        task = get_task(qid, cfg)
        db_path = sqlite_path_for_task(task, cfg)
        tables = list_user_tables(db_path)
        gold = tables_mentioned_in_sql(task.gold_sql, tables)
        selected, _ = select_tables_for_task(task, db_path)
        assert gold <= set(selected), f"qid={qid} gold={gold} selected={selected}"


def test_student_club_expense_queries_include_budget(cfg) -> None:
    from src.bird.tasks import get_task, sqlite_path_for_task

    task = get_task(1338, cfg)
    db_path = sqlite_path_for_task(task, cfg)
    tables = list_user_tables(db_path)
    gold = tables_mentioned_in_sql(task.gold_sql, tables)
    selected, _ = select_tables_for_task(task, db_path)
    assert gold <= set(selected)


def test_smoke_subset_gold_recall_threshold(cfg) -> None:
    from src.bird.tasks import load_tasks, sqlite_path_for_task

    tasks = load_tasks(cfg)[:50]
    recalls = []
    for task in tasks:
        db_path = sqlite_path_for_task(task, cfg)
        tables = list_user_tables(db_path)
        gold = tables_mentioned_in_sql(task.gold_sql, tables)
        selected, _ = select_tables_for_task(task, db_path)
        recall = len(gold & set(selected)) / len(gold) if gold else 1.0
        recalls.append(recall)
    assert min(recalls) == 1.0
    assert sum(recalls) / len(recalls) >= 0.98
