"""Load BIRD / mini-dev text-to-SQL tasks from JSON."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Iterator

from src.config import ProjectConfig, load_config


@dataclass(frozen=True)
class BirdTask:
    question_id: int
    db_id: str
    question: str
    evidence: str
    gold_sql: str
    difficulty: str

    @classmethod
    def from_row(cls, row: dict) -> BirdTask:
        return cls(
            question_id=int(row["question_id"]),
            db_id=str(row["db_id"]),
            question=str(row["question"]),
            evidence=str(row.get("evidence") or ""),
            gold_sql=str(row["SQL"]),
            difficulty=str(row.get("difficulty") or ""),
        )


def load_tasks(cfg: ProjectConfig | None = None) -> list[BirdTask]:
    cfg = cfg or load_config()
    if not cfg.tasks_json.exists():
        raise FileNotFoundError(f"Tasks file not found: {cfg.tasks_json}")
    with cfg.tasks_json.open(encoding="utf-8") as f:
        rows = json.load(f)
    return [BirdTask.from_row(row) for row in rows]


def iter_tasks(cfg: ProjectConfig | None = None) -> Iterator[BirdTask]:
    yield from load_tasks(cfg)


def get_task(
    question_id: int,
    cfg: ProjectConfig | None = None,
) -> BirdTask:
    for task in iter_tasks(cfg):
        if task.question_id == question_id:
            return task
    raise KeyError(f"question_id {question_id} not found in {cfg.tasks_json if cfg else 'tasks'}")


def resolve_sqlite_path(databases_dir: Path, db_id: str) -> Path:
    """Return path to the SQLite file for a BIRD db_id."""
    base = databases_dir / db_id
    candidates = [
        base / f"{db_id}.sqlite",
        base / "sqlite" / f"{db_id}.sqlite",
    ]
    for path in candidates:
        if path.is_file():
            return path
    raise FileNotFoundError(
        f"No SQLite database for db_id={db_id!r} under {base} (tried {[str(p) for p in candidates]})"
    )


def sqlite_path_for_task(task: BirdTask, cfg: ProjectConfig | None = None) -> Path:
    cfg = cfg or load_config()
    return resolve_sqlite_path(cfg.databases_dir, task.db_id)
