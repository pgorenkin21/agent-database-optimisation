#!/usr/bin/env python3
"""Run gold SQL for one BIRD task, check EX, and write a JSONL trace (Phase 1a/1b)."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from src.bird.tasks import get_task, load_tasks, sqlite_path_for_task
from src.config import load_config
from src.eval.execution_accuracy import compare_result_sets
from src.logging.trace import RunTrace


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--question-id", type=int, help="BIRD question_id")
    parser.add_argument("--index", type=int, help="0-based index into tasks JSON")
    parser.add_argument(
        "--predicted-sql",
        type=str,
        default=None,
        help="SQL to compare to gold (default: gold SQL itself)",
    )
    parser.add_argument("--config", type=Path, default=None)
    parser.add_argument(
        "--no-trace",
        action="store_true",
        help="Skip writing JSONL trace file",
    )
    args = parser.parse_args()

    cfg = load_config(args.config)
    tasks = load_tasks(cfg)

    if args.question_id is not None:
        task = get_task(args.question_id, cfg)
    elif args.index is not None:
        if args.index < 0 or args.index >= len(tasks):
            print(f"index out of range: {args.index} (0..{len(tasks) - 1})", file=sys.stderr)
            return 1
        task = tasks[args.index]
    else:
        task = tasks[0]
        print(f"No --question-id; using first task (index 0, question_id={task.question_id})")

    db_path = sqlite_path_for_task(task, cfg)
    predicted_sql = args.predicted_sql if args.predicted_sql is not None else task.gold_sql
    timeout = float(cfg.query_timeout_seconds)

    print(f"question_id:  {task.question_id}")
    print(f"db_id:        {task.db_id}")
    print(f"difficulty:   {task.difficulty}")
    print(f"sqlite:       {db_path}")
    print(f"question:     {task.question[:120]}{'...' if len(task.question) > 120 else ''}")
    print()

    trace: RunTrace | None = None
    if not args.no_trace:
        trace = RunTrace(cfg=cfg, question_id=task.question_id, db_id=task.db_id, policy="P0")
        print(f"trace:        {trace.path}")

    def run_sql(sql: str, role: str) -> list | None:
        if trace is not None:
            rows, err = trace.log_sql_execute(
                sql=sql,
                sql_role=role,
                db_path=db_path,
                timeout_seconds=timeout,
            )
            if err:
                print(f"{role} SQL failed: {err}")
                return None
            return rows
        from src.db.sqlite_exec import execute_sql

        try:
            return execute_sql(db_path, sql, timeout_seconds=timeout)
        except Exception as e:
            print(f"{role} SQL failed: {e}")
            return None

    gold_rows = run_sql(task.gold_sql, "gold")
    if gold_rows is None:
        if trace:
            trace.finish(
                predicted_sql=predicted_sql,
                gold_sql=task.gold_sql,
                ex_correct=0,
                match=False,
            )
        return 1

    print(f"Gold SQL executed: {len(gold_rows)} row(s)")
    if gold_rows:
        print(f"  sample: {gold_rows[0]}")

    pred_rows = run_sql(predicted_sql, "predicted")
    if pred_rows is None:
        match = False
        ex = 0
    else:
        match = compare_result_sets(pred_rows, gold_rows)
        ex = 1 if match else 0
        print(f"Predicted SQL: {len(pred_rows)} row(s)")

    print()
    print(f"Execution accuracy (EX): {ex} ({'match' if match else 'no match'})")

    if trace:
        trace.finish(
            predicted_sql=predicted_sql,
            gold_sql=task.gold_sql,
            ex_correct=ex,
            match=match,
            extra={"difficulty": task.difficulty},
        )
        print(f"Trace written:  {trace.path}")

    return 0 if ex == 1 else 1


if __name__ == "__main__":
    raise SystemExit(main())
