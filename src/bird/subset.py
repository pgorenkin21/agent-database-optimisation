"""Resolve which BIRD tasks to run in a batch."""

from __future__ import annotations

from pathlib import Path

from src.bird.tasks import BirdTask, load_tasks
from src.config import ProjectConfig


def _read_question_ids(path: Path) -> list[int]:
    ids: list[int] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        ids.append(int(line.split()[0]))
    return ids


def resolve_task_subset(
    cfg: ProjectConfig,
    *,
    limit: int | None = None,
    subset_file: Path | None = None,
    question_ids: list[int] | None = None,
) -> list[BirdTask]:
    """
    Choose tasks for a batch run.

    Priority: explicit question_ids > subset_file > cfg.subset_file > limit on full list.
    """
    all_tasks = load_tasks(cfg)
    by_id = {t.question_id: t for t in all_tasks}

    if question_ids:
        return [by_id[qid] for qid in question_ids if qid in by_id]

    file_path = subset_file or cfg.subset_file
    if file_path is not None:
        ids = _read_question_ids(file_path)
        return [by_id[qid] for qid in ids if qid in by_id]

    cap = cfg.subset_limit if limit is None else limit
    if cap and cap > 0:
        return all_tasks[:cap]

    return all_tasks
