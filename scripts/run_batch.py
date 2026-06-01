#!/usr/bin/env python3
"""Run the text-to-SQL agent on a batch of BIRD tasks and write a summary CSV/JSON."""

from __future__ import annotations

import argparse
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from dotenv import load_dotenv

from src.agent.loop import run_agent
from src.batch.summary import BatchRow, BatchSummary, print_batch_summary, write_batch_csv, write_batch_json
from src.bird.subset import resolve_task_subset
from src.config import load_config, validate_paths
from src.llm.client import api_key_status
from src.llm.models import load_model_registry


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model", type=str, default=None, help="Model registry key")
    parser.add_argument("--config", type=Path, default=None)
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Max tasks (overrides config subset_limit when no subset file)",
    )
    parser.add_argument(
        "--subset-file",
        type=Path,
        default=None,
        help="File with question_id per line",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=None,
        help="Directory for batch summary files (default: runs/batches/)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="List tasks only, do not call the LLM",
    )
    parser.add_argument(
        "--fail-fast",
        action="store_true",
        help="Stop batch on first task exception (default: continue)",
    )
    args = parser.parse_args()

    load_dotenv(REPO_ROOT / ".env")
    cfg = load_config(args.config)
    model_key = args.model or cfg.default_model_key

    warnings = validate_paths(cfg)
    if warnings:
        for w in warnings:
            print(f"WARN: {w}", file=sys.stderr)
        return 1

    registry = load_model_registry(cfg.models_config_path)
    spec = registry.get(model_key)
    ok, msg = api_key_status(spec)
    if not ok and not args.dry_run:
        print(f"API key missing for {model_key}: {msg}", file=sys.stderr)
        return 1

    tasks = resolve_task_subset(cfg, limit=args.limit, subset_file=args.subset_file)
    if not tasks:
        print("No tasks selected.", file=sys.stderr)
        return 1

    batch_id = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S") + "_" + uuid.uuid4().hex[:6]
    out_dir = args.output_dir or (cfg.runs_dir / "batches")
    csv_path = out_dir / f"batch_{batch_id}_{model_key}.csv"
    json_path = out_dir / f"batch_{batch_id}_{model_key}.json"

    print(f"batch_id:     {batch_id}")
    print(f"model:        {model_key} ({spec.api_model})")
    print(f"bird_split:   {cfg.bird_split}")
    print(f"tasks:        {len(tasks)}")
    print(f"output:       {csv_path}")

    if args.dry_run:
        for i, t in enumerate(tasks):
            print(f"  [{i}] question_id={t.question_id} db={t.db_id} {t.difficulty}")
        return 0

    summary = BatchSummary(
        batch_id=batch_id,
        model_key=model_key,
        bird_split=cfg.bird_split,
        task_count=len(tasks),
    )

    failures = 0
    for i, task in enumerate(tasks):
        print(f"\n[{i + 1}/{len(tasks)}] question_id={task.question_id} ({task.difficulty}) ...", flush=True)
        try:
            result = run_agent(task, model_key, cfg)
            summary.add_from_agent_result(
                BatchRow(
                    question_id=result.question_id,
                    db_id=result.db_id,
                    difficulty=task.difficulty,
                    model_key=result.model_key,
                    ex_correct=result.ex_correct,
                    turns=result.turns,
                    stop_reason=result.stop_reason,
                    prompt_tokens=result.total_prompt_tokens,
                    completion_tokens=result.total_completion_tokens,
                    trace_path=str(result.trace_path),
                    error=result.error,
                )
            )
            status = "EX=1" if result.ex_correct else "EX=0"
            print(f"  -> {status} turns={result.turns} trace={result.trace_path.name}")
            if result.ex_correct == 0:
                failures += 1
        except Exception as e:
            failures += 1
            summary.add_from_agent_result(
                BatchRow(
                    question_id=task.question_id,
                    db_id=task.db_id,
                    difficulty=task.difficulty,
                    model_key=model_key,
                    ex_correct=0,
                    turns=0,
                    stop_reason="error",
                    prompt_tokens=0,
                    completion_tokens=0,
                    trace_path="",
                    error=str(e),
                )
            )
            print(f"  -> ERROR: {e}", file=sys.stderr)
            if args.fail_fast:
                break

    write_batch_csv(csv_path, summary)
    write_batch_json(json_path, summary)
    print_batch_summary(summary)
    print(f"\nWrote {csv_path}")
    print(f"Wrote {json_path}")

    return 0 if failures == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
