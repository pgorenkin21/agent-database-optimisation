"""Tests for P1 shared SQL result cache."""

from __future__ import annotations

from pathlib import Path

import pytest

from src.bird.tasks import load_tasks, sqlite_path_for_task
from src.config import load_config
from src.db.shared_sql_cache import SharedSqlResultCache
from src.db.sql_normalize import cache_key_for_sql, normalize_sql_ast, normalize_sql_string
from src.logging.trace import RunTrace, read_trace_events


def test_normalize_sql_ast_ignores_alias_differences() -> None:
    a = normalize_sql_ast("SELECT x AS foo FROM t")
    b = normalize_sql_ast("SELECT x foo FROM t")
    assert a is not None and a == b


def test_cache_key_falls_back_to_string_normalization() -> None:
    key = cache_key_for_sql("  SELECT  1 ", db_path="/tmp/db.sqlite")
    assert key[1] == normalize_sql_string("  SELECT  1 ")


def test_shared_cache_hit_on_duplicate_explore(tmp_path: Path) -> None:
    cfg = load_config()
    if not cfg.tasks_json.exists():
        pytest.skip("BIRD mini-dev not downloaded")
    task = load_tasks(cfg)[0]
    db_path = sqlite_path_for_task(task, cfg)
    cache = SharedSqlResultCache(max_entries=16)

    sql = "SELECT 1"
    rows1, err1, hit1 = cache.execute_or_get(
        db_path=db_path, sql=sql, sql_role="explore", timeout_seconds=30
    )
    rows2, err2, hit2 = cache.execute_or_get(
        db_path=db_path, sql=sql, sql_role="explore", timeout_seconds=30
    )

    assert hit1 is False
    assert hit2 is True
    assert err1 is None and err2 is None
    assert rows1 == rows2
    assert cache.stats.hits == 1
    assert cache.stats.misses == 1


def test_shared_cache_ast_equivalent_queries_hit(tmp_path: Path) -> None:
    cfg = load_config()
    if not cfg.tasks_json.exists():
        pytest.skip("BIRD mini-dev not downloaded")
    task = load_tasks(cfg)[0]
    db_path = sqlite_path_for_task(task, cfg)
    cache = SharedSqlResultCache(max_entries=16)

    sql_a = "SELECT 1 AS x"
    sql_b = "SELECT 1 x"
    _, _, hit_a = cache.execute_or_get(
        db_path=db_path, sql=sql_a, sql_role="explore", timeout_seconds=30
    )
    _, _, hit_b = cache.execute_or_get(
        db_path=db_path, sql=sql_b, sql_role="explore", timeout_seconds=30
    )

    assert hit_a is False
    assert hit_b is True


def test_trace_logs_cache_hit(tmp_path: Path) -> None:
    cfg = load_config()
    if not cfg.tasks_json.exists():
        pytest.skip("BIRD mini-dev not downloaded")
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

    events = [e for e in read_trace_events(trace.path) if e["event"] == "sql_execute"]
    assert events[0]["cache_hit"] is False
    assert events[1]["cache_hit"] is True


def test_resolve_trace_policy() -> None:
    from src.coord.parallel import resolve_trace_policy

    assert resolve_trace_policy(shared_cache=False, early_stop=False) == "P0_parallel"
    assert resolve_trace_policy(shared_cache=False, early_stop=True) == "P0_early_stop"
    assert resolve_trace_policy(shared_cache=True, early_stop=False) == "P1_shared_cache"
    assert (
        resolve_trace_policy(shared_cache=True, early_stop=True)
        == "P1_shared_cache_early_stop"
    )
    assert resolve_trace_policy(shared_cache=False, early_stop=False, discovery_board=True) == (
        "P2_subexpr_propagation"
    )
