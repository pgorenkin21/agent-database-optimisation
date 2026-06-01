"""Phase 1a: execution accuracy and gold SQL execution."""

from pathlib import Path

import pytest

from src.bird.tasks import get_task, load_tasks, resolve_sqlite_path, sqlite_path_for_task
from src.config import load_config
from src.db.sqlite_exec import execute_sql
from src.eval.execution_accuracy import compare_result_sets, execution_accuracy


@pytest.fixture(scope="module")
def cfg():
    c = load_config()
    if not c.tasks_json.exists():
        pytest.skip("BIRD mini-dev not downloaded")
    return c


@pytest.fixture(scope="module")
def first_task(cfg):
    return load_tasks(cfg)[0]


def test_compare_result_sets_order_independent() -> None:
    a = [(1, "x"), (2, "y")]
    b = [(2, "y"), (1, "x")]
    assert compare_result_sets(a, b)
    assert not compare_result_sets(a, [(1, "z")])


def test_resolve_sqlite_path(cfg) -> None:
    task = load_tasks(cfg)[0]
    path = resolve_sqlite_path(cfg.databases_dir, task.db_id)
    assert path.is_file()
    assert path.suffix == ".sqlite"


def test_gold_sql_executes(first_task, cfg) -> None:
    db_path = sqlite_path_for_task(first_task, cfg)
    rows = execute_sql(db_path, first_task.gold_sql, timeout_seconds=30.0)
    assert isinstance(rows, list)


def test_gold_self_match_ex(first_task, cfg) -> None:
    db_path = sqlite_path_for_task(first_task, cfg)
    ex = execution_accuracy(db_path, first_task.gold_sql, first_task.gold_sql, timeout_seconds=30.0)
    assert ex == 1


def test_wrong_sql_ex_zero(first_task, cfg) -> None:
    db_path = sqlite_path_for_task(first_task, cfg)
    ex = execution_accuracy(
        db_path,
        "SELECT 1 AS wrong_answer",
        first_task.gold_sql,
        timeout_seconds=30.0,
    )
    assert ex == 0


def test_get_task_by_question_id(first_task, cfg) -> None:
    t = get_task(first_task.question_id, cfg)
    assert t.question_id == first_task.question_id
