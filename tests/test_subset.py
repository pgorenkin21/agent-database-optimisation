"""Task subset resolution tests."""

from pathlib import Path

import pytest

from src.bird.subset import resolve_task_subset
from src.bird.tasks import load_tasks
from src.config import load_config


@pytest.fixture
def cfg():
    c = load_config()
    if not c.tasks_json.exists():
        pytest.skip("BIRD not downloaded")
    return c


def test_resolve_by_limit(cfg) -> None:
    tasks = resolve_task_subset(cfg, limit=3)
    assert len(tasks) == 3
    all_ids = [t.question_id for t in load_tasks(cfg)]
    assert [t.question_id for t in tasks] == all_ids[:3]


def test_resolve_by_subset_file(cfg, tmp_path: Path) -> None:
    all_tasks = load_tasks(cfg)
    ids = [all_tasks[0].question_id, all_tasks[2].question_id]
    path = tmp_path / "subset.txt"
    path.write_text("\n".join(str(i) for i in ids), encoding="utf-8")
    tasks = resolve_task_subset(cfg, subset_file=path, limit=0)
    assert len(tasks) == 2
    assert tasks[0].question_id == ids[0]
    assert tasks[1].question_id == ids[1]
