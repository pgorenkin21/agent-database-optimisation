#!/usr/bin/env python3
"""Run a single LLM agent on one BIRD mini-dev task (Phase 1c)."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from dotenv import load_dotenv

from src.agent.loop import run_agent
from src.bird.tasks import get_task, load_tasks
from src.config import load_config
from src.llm.client import api_key_status
from src.llm.models import load_model_registry


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--question-id", type=int, help="BIRD question_id")
    parser.add_argument("--index", type=int, help="0-based task index")
    parser.add_argument(
        "--model",
        type=str,
        default=None,
        help="Model registry key (default: llm.default in config)",
    )
    parser.add_argument("--config", type=Path, default=None)
    parser.add_argument(
        "--temperature",
        type=float,
        default=None,
        help="LLM sampling temperature (default: config llm.temperature)",
    )
    args = parser.parse_args()

    load_dotenv(REPO_ROOT / ".env")
    cfg = load_config(args.config)
    model_key = args.model or cfg.default_model_key

    registry = load_model_registry(cfg.models_config_path)
    spec = registry.get(model_key)
    ok, msg = api_key_status(spec)
    if not ok:
        print(f"API key missing for {model_key}: {msg}", file=sys.stderr)
        return 1

    tasks = load_tasks(cfg)
    if args.question_id is not None:
        task = get_task(args.question_id, cfg)
    elif args.index is not None:
        task = tasks[args.index]
    else:
        task = tasks[0]
        print(f"Using first task (question_id={task.question_id})")

    print(f"question_id:  {task.question_id}")
    print(f"db_id:        {task.db_id}")
    print(f"model:        {model_key} ({spec.api_model})")
    temp = cfg.llm_temperature if args.temperature is None else args.temperature
    print(f"temperature:  {temp}")
    print(f"difficulty:   {task.difficulty}")
    print(f"question:     {task.question[:100]}...")
    print()

    result = run_agent(task, model_key, cfg, temperature=temp)

    print(f"trace:        {result.trace_path}")
    print(f"turns:        {result.turns}")
    print(f"stop_reason:  {result.stop_reason}")
    print(f"EX:           {result.ex_correct}")
    print(f"tokens:       prompt={result.total_prompt_tokens} completion={result.total_completion_tokens}")
    if result.final_sql:
        print(f"final_sql:    {result.final_sql[:200]}...")
    if result.error and result.ex_correct == 0:
        print(f"note:         {result.error}")

    return 0 if result.ex_correct == 1 else 1


if __name__ == "__main__":
    raise SystemExit(main())
