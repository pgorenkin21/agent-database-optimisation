"""Unit tests for DB vs middleware interaction metrics."""

from __future__ import annotations

from pathlib import Path

import pytest

from src.coord.interaction_metrics import (
    InteractionMetrics,
    batch_interaction_summary,
    compute_interaction_metrics,
    interaction_metrics_from_trace,
)
from src.logging.trace import RunTrace


@pytest.fixture
def cfg():
    from src.config import load_config

    c = load_config()
    if not c.tasks_json.exists():
        pytest.skip("BIRD mini-dev not downloaded")
    return c


def test_interaction_metrics_p0_all_db(tmp_path: Path, cfg) -> None:
    from src.bird.tasks import load_tasks, sqlite_path_for_task

    task = load_tasks(cfg)[0]
    db_path = sqlite_path_for_task(task, cfg)
    trace = RunTrace(
        cfg=cfg,
        question_id=task.question_id,
        db_id=task.db_id,
        runs_dir=tmp_path,
    )
    trace.log_sql_execute(sql="SELECT 1", sql_role="explore", db_path=db_path)
    trace.log_sql_execute(sql="SELECT 2", sql_role="explore", db_path=db_path)
    trace.log_sql_execute(sql="SELECT 1", sql_role="final", db_path=db_path)

    m = interaction_metrics_from_trace(trace.path)
    assert m.db_sql_executions == 3
    assert m.middleware_cache_hits == 0
    assert m.middleware_discovery_injections == 0
    assert m.middleware_semantic_injections == 0
    assert m.middleware_interaction_pct == 0.0


def test_interaction_metrics_cache_and_discovery(tmp_path: Path, cfg) -> None:
    from src.bird.tasks import load_tasks, sqlite_path_for_task
    from src.db.shared_sql_cache import SharedSqlResultCache

    task = load_tasks(cfg)[0]
    db_path = sqlite_path_for_task(task, cfg)
    cache = SharedSqlResultCache(max_entries=16)
    trace = RunTrace(
        cfg=cfg,
        question_id=task.question_id,
        db_id=task.db_id,
        runs_dir=tmp_path,
        sql_cache=cache,
    )
    sql = "SELECT 1"
    trace.log_sql_execute(sql=sql, sql_role="explore", db_path=db_path)
    trace.log_sql_execute(sql=sql, sql_role="explore", db_path=db_path)
    trace.log_discovery_injection(turn_idx=1, fragment_count=3)
    trace.log_semantic_injection(turn_idx=2, fact_count=2, char_count=120)
    trace.log_sql_execute(sql="SELECT 1", sql_role="final", db_path=db_path)

    m = interaction_metrics_from_trace(trace.path)
    assert m.db_sql_executions == 2  # first explore + final
    assert m.middleware_cache_hits == 1
    assert m.middleware_discovery_injections == 1
    assert m.middleware_semantic_injections == 1
    assert m.middleware_interactions == 3
    assert m.total_interactions == 5
    assert m.middleware_interaction_pct == pytest.approx(60.0)
    assert m.sql_cache_hit_pct == pytest.approx(100.0 / 3.0)


def test_batch_interaction_summary() -> None:
    rows = [
        {
            "db_interactions": 10,
            "middleware_cache_hits": 5,
            "middleware_discovery_injections": 2,
            "middleware_interaction_pct": 41.18,
        },
        {
            "db_interactions": 8,
            "middleware_cache_hits": 4,
            "middleware_discovery_injections": 0,
            "middleware_interaction_pct": 33.33,
        },
    ]
    summary = batch_interaction_summary(rows)
    assert summary["total_db_interactions"] == 18
    assert summary["total_middleware_cache_hits"] == 9
    assert summary["total_middleware_discovery_injections"] == 2
    assert summary["total_middleware_interactions"] == 11
    assert summary["total_interactions"] == 29
    assert summary["batch_middleware_interaction_pct"] == pytest.approx(37.93, abs=0.1)
    assert summary["avg_middleware_interaction_pct"] == pytest.approx(37.26, abs=0.1)


def test_interaction_metrics_to_dict() -> None:
    m = InteractionMetrics(
        db_sql_executions=4,
        middleware_cache_hits=6,
        middleware_discovery_injections=2,
        middleware_semantic_injections=0,
    )
    d = m.to_dict()
    assert d["middleware_interactions"] == 8
    assert d["total_interactions"] == 12
    assert d["middleware_interaction_pct"] == pytest.approx(66.67, abs=0.1)
