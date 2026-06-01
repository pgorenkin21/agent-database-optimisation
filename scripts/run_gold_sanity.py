#!/usr/bin/env python3
"""Verify gold SQL runs and self-matches (EX=1) on a sample of mini-dev tasks."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from src.bird.tasks import load_tasks, sqlite_path_for_task
from src.config import load_config
from src.eval.execution_accuracy import execution_accuracy


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--limit", type=int, default=20, help="Number of tasks to check")
    parser.add_argument("--config", type=Path, default=None)
    args = parser.parse_args()

    cfg = load_config(args.config)
    tasks = load_tasks(cfg)[: args.limit]
    timeout = float(cfg.query_timeout_seconds)

    passed = 0
    failed: list[str] = []

    for task in tasks:
        db_path = sqlite_path_for_task(task, cfg)
        ex = execution_accuracy(db_path, task.gold_sql, task.gold_sql, timeout_seconds=timeout)
        if ex == 1:
            passed += 1
        else:
            failed.append(f"question_id={task.question_id} db_id={task.db_id}")

    print(f"Gold self-match: {passed}/{len(tasks)} passed")
    for line in failed[:10]:
        print(f"  FAIL {line}")
    if len(failed) > 10:
        print(f"  ... and {len(failed) - 10} more")

    return 0 if not failed else 1


if __name__ == "__main__":
    raise SystemExit(main())
