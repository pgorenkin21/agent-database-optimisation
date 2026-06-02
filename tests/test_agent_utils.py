"""Agent helper unit tests (no API calls)."""

import pytest

from src.agent.sql_utils import strip_sql_markdown, validate_read_only_sql
from src.config import load_config


def test_strip_sql_markdown() -> None:
    assert strip_sql_markdown("```sql\nSELECT 1\n```") == "SELECT 1"
    assert strip_sql_markdown("SELECT 2") == "SELECT 2"


def test_validate_read_only_accepts_select() -> None:
    validate_read_only_sql("SELECT * FROM t")
    validate_read_only_sql("WITH cte AS (SELECT 1) SELECT * FROM cte")


def test_validate_read_only_rejects_write() -> None:
    with pytest.raises(ValueError):
        validate_read_only_sql("DELETE FROM t")
    with pytest.raises(ValueError):
        validate_read_only_sql("INSERT INTO t VALUES (1)")


def test_build_schema_context() -> None:
    cfg = load_config()
    if not cfg.tasks_json.exists():
        pytest.skip("BIRD not downloaded")
    from src.bird.tasks import load_tasks, sqlite_path_for_task
    from src.agent.schema import build_schema_context

    task = load_tasks(cfg)[0]
    db_path = sqlite_path_for_task(task, cfg)
    text = build_schema_context(db_path, cfg.databases_dir, task.db_id)
    assert "CREATE TABLE" in text or "Table `" in text
    assert task.db_id in text or "customers" in text.lower()


def test_gemini_function_declarations_use_schema_parameters() -> None:
    """google-genai FunctionDeclaration rejects parameters_json_schema dicts."""
    from google.genai import types

    from src.llm.chat import build_gemini_function_declarations

    decls = build_gemini_function_declarations(types)
    assert len(decls) == 2
    assert decls[0].name == "execute_sql"
    assert decls[0].parameters is not None
    assert decls[0].parameters.type == types.Type.OBJECT
    assert "sql" in (decls[0].parameters.properties or {})


def test_student_club_budget_csv_encoding() -> None:
    """student_club/Budget.csv uses cp1252; must not raise on schema load."""
    cfg = load_config()
    if not cfg.tasks_json.exists():
        pytest.skip("BIRD not downloaded")

    budget_csv = (
        cfg.databases_dir / "student_club" / "database_description" / "Budget.csv"
    )
    if not budget_csv.is_file():
        pytest.skip("student_club not in mini-dev")

    from src.agent.schema import read_text_with_encoding_fallback, build_schema_context
    from src.bird.tasks import get_task, sqlite_path_for_task

    text = read_text_with_encoding_fallback(budget_csv)
    assert len(text) > 800
    assert "original_column_name" in text

    task = get_task(1312, cfg)
    db_path = sqlite_path_for_task(task, cfg)
    schema = build_schema_context(db_path, cfg.databases_dir, "student_club")
    assert "Table `Budget`" in schema
    assert "CREATE TABLE" in schema
