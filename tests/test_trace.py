"""JSONL trace logging tests."""

import json
from pathlib import Path

import pytest

from src.bird.tasks import load_tasks, sqlite_path_for_task
from src.config import load_config
from src.eval.execution_accuracy import compare_result_sets
from src.logging.trace import RunTrace, read_trace_events


@pytest.fixture
def cfg():
    c = load_config()
    if not c.tasks_json.exists():
        pytest.skip("BIRD mini-dev not downloaded")
    return c


def test_trace_writes_start_sql_end(tmp_path: Path, cfg) -> None:
    task = load_tasks(cfg)[0]
    db_path = sqlite_path_for_task(task, cfg)

    trace = RunTrace(
        cfg=cfg,
        question_id=task.question_id,
        db_id=task.db_id,
        runs_dir=tmp_path,
    )
    gold_rows, err, _ = trace.log_sql_execute(
        sql=task.gold_sql, sql_role="gold", db_path=db_path
    )
    assert err is None
    pred_rows, err2, _ = trace.log_sql_execute(
        sql=task.gold_sql, sql_role="predicted", db_path=db_path
    )
    assert err2 is None
    match = compare_result_sets(pred_rows or [], gold_rows or [])
    trace.finish(
        predicted_sql=task.gold_sql,
        gold_sql=task.gold_sql,
        ex_correct=1 if match else 0,
        match=match,
    )

    events = read_trace_events(trace.path)
    types = [e["event"] for e in events]
    assert types == ["run_start", "sql_execute", "sql_execute", "run_end"]

    sql_events = [e for e in events if e["event"] == "sql_execute"]
    assert sql_events[0]["sql_role"] == "gold"
    assert sql_events[0]["exec_status"] == "ok"
    assert sql_events[0]["row_count"] >= 0
    assert "latency_ms" in sql_events[0]

    end = events[-1]
    assert end["ex_correct"] == 1
    assert end["match"] is True

    # valid JSONL: one object per line
    lines = trace.path.read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) == 4
    for line in lines:
        json.loads(line)


def test_trace_logs_sql_error(tmp_path: Path, cfg) -> None:
    task = load_tasks(cfg)[0]
    db_path = sqlite_path_for_task(task, cfg)

    trace = RunTrace(
        cfg=cfg,
        question_id=task.question_id,
        db_id=task.db_id,
        runs_dir=tmp_path,
    )
    rows, err, _ = trace.log_sql_execute(
        sql="SELECT * FROM not_a_real_table_xyz",
        sql_role="predicted",
        db_path=db_path,
    )
    assert rows is None
    assert err is not None

    events = read_trace_events(trace.path)
    sql_ev = [e for e in events if e["event"] == "sql_execute"][0]
    assert sql_ev["exec_status"] == "error"
    assert sql_ev["error"]
