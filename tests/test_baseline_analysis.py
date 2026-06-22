"""Unit tests for baseline redundancy analysis (no API calls)."""

from __future__ import annotations

from pathlib import Path

import pytest

from src.coord.baseline_analysis import (
    analyze_coord_trace,
    batch_ex_accuracy_stats,
    extract_sql_fragments,
)
from src.db.sql_normalize import normalize_sql_ast, normalize_sql_string
from src.logging.trace import RunTrace


def test_normalize_sql_string_collapses_whitespace() -> None:
    assert normalize_sql_string("  SELECT  1  ") == "select 1"


def test_normalize_sql_ast_ignores_alias_differences() -> None:
    a = normalize_sql_ast("SELECT x AS foo FROM t")
    b = normalize_sql_ast("SELECT x foo FROM t")
    assert a is not None and b is not None
    assert a == b


def test_batch_ex_accuracy_stats_excludes_api_failures() -> None:
    rows = [
        {"ex_correct": 1, "error": None},
        {"ex_correct": 0, "error": None},
        {"ex_correct": 0, "error": "RateLimitError"},
    ]
    stats = batch_ex_accuracy_stats(rows)
    assert stats["ex_accuracy_pct"] == pytest.approx(33.33, abs=0.1)
    assert stats["api_failure_count"] == 1
    assert stats["completed_task_count"] == 2
    assert stats["ex_accuracy_excluding_api_errors_pct"] == 50.0


def test_extract_sql_fragments_finds_table_and_column() -> None:
    frags = extract_sql_fragments("SELECT a FROM users WHERE users.id = 1")
    assert "table:users" in frags
    assert any("id" in f for f in frags)


@pytest.fixture
def cfg():
    from src.config import load_config

    c = load_config()
    if not c.tasks_json.exists():
        pytest.skip("BIRD mini-dev not downloaded")
    return c


def test_analyze_coord_trace_from_parallel_run(tmp_path: Path, cfg) -> None:
    from src.bird.tasks import load_tasks, sqlite_path_for_task

    task = load_tasks(cfg)[0]
    db_path = sqlite_path_for_task(task, cfg)

    def make_replica(agent_id: str, explore: list[str], ex: int) -> Path:
        trace = RunTrace(
            cfg=cfg,
            question_id=task.question_id,
            db_id=task.db_id,
            policy="P0_parallel",
            agent_id=agent_id,
            runs_dir=tmp_path,
        )
        for sql in explore:
            trace.log_sql_execute(sql=sql, sql_role="explore", db_path=db_path)
        trace.log_sql_execute(
            sql="SELECT 1",
            sql_role="submit",
            db_path=db_path,
        )
        trace.finish(
            predicted_sql="SELECT 1",
            gold_sql=task.gold_sql,
            ex_correct=ex,
            match=ex == 1,
        )
        return trace.path

    t0 = make_replica("agent_0", ["SELECT 1 FROM t", "SELECT 2"], 1)
    t1 = make_replica("agent_1", ["SELECT 1 FROM t", "SELECT 3"], 0)

    coord_path = tmp_path / "coord_test.jsonl"
    events = [
        {
            "event": "parallel_start",
            "question_id": task.question_id,
            "db_id": task.db_id,
            "n_replicas": 2,
        },
        {
            "event": "replica_end",
            "agent_id": "agent_0",
            "finish_rank": 0,
            "trace_path": str(t0),
            "ex_correct": 1,
        },
        {
            "event": "replica_end",
            "agent_id": "agent_1",
            "finish_rank": 1,
            "trace_path": str(t1),
            "ex_correct": 0,
        },
        {
            "event": "coordination_end",
            "chosen_ex_correct": 1,
            "wall_clock_ms": 5000,
            "redundancy": {
                "total_prompt_tokens": 200,
                "total_completion_tokens": 20,
                "replicas_ex_correct": 1,
                "token_overhead_ratio": 2.0,
            },
        },
    ]
    import json

    with coord_path.open("w", encoding="utf-8") as f:
        for ev in events:
            f.write(json.dumps(ev) + "\n")

    metrics = analyze_coord_trace(
        coord_path,
        question_id=task.question_id,
        db_id=task.db_id,
        difficulty="simple",
    )
    assert metrics is not None
    assert metrics.n_replicas == 2
    assert metrics.total_explore_queries == 4
    assert metrics.unique_explore_string == 3
    assert metrics.duplicate_explore_sql == 1
    assert metrics.explore_redundancy_pct == 25.0
    assert metrics.subexpr_total > 0
    assert metrics.subexpr_shared >= 1
    assert metrics.wall_clock_ms == 5000
