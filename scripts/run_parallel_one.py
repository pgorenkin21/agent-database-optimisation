#!/usr/bin/env python3
"""Run N parallel agent replicas on one BIRD task (Phase 2)."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from dotenv import load_dotenv

from src.bird.tasks import get_task, load_tasks
from src.config import load_config
from src.coord.parallel import run_parallel_agents
from src.coord.replica_schedule import add_replica_schedule_arguments, schedule_from_args
from src.coord.policies import policy_from_str
from src.llm.client import api_key_status
from src.llm.models import load_model_registry


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--question-id", type=int, help="BIRD question_id")
    parser.add_argument("--index", type=int, help="0-based task index")
    parser.add_argument("--model", type=str, default=None)
    parser.add_argument("--config", type=Path, default=None)
    parser.add_argument("--replicas", type=int, default=3, help="Parallel replicas (default: 3)")
    parser.add_argument(
        "--policy",
        type=str,
        default="best_of_n",
        choices=["best_of_n", "first_success", "majority_vote"],
    )
    parser.add_argument(
        "--early-stop",
        action="store_true",
        help="Cancel remaining replicas when one achieves EX=1",
    )
    parser.add_argument(
        "--shared-cache",
        action="store_true",
        help="Enable P1 shared SQL result cache for explore queries",
    )
    parser.add_argument(
        "--discovery-board",
        action="store_true",
        help="Enable P2 shared sub-expression discovery board (prompt injection)",
    )
    parser.add_argument(
        "--semantic-store",
        action="store_true",
        help="Enable P3 shared semantic fact store (bounded prompt injection)",
    )
    parser.add_argument("--max-workers", type=int, default=None)
    add_replica_schedule_arguments(parser)
    args = parser.parse_args()

    load_dotenv(REPO_ROOT / ".env")
    cfg = load_config(args.config)
    model_key = args.model or cfg.default_model_key
    policy = policy_from_str(args.policy)
    schedule = schedule_from_args(args, cfg)

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
    print(f"replicas:     {args.replicas}")
    print(f"policy:       {policy.value}")
    print(f"early_stop:   {args.early_stop}")
    print(f"shared_cache: {args.shared_cache}")
    print(f"discovery:    {args.discovery_board}")
    print(f"semantic:     {args.semantic_store}")
    print(f"schedule:     {schedule.to_dict()}")
    print()

    result = run_parallel_agents(
        task,
        model_key,
        n_replicas=args.replicas,
        policy=policy,
        cfg=cfg,
        max_workers=args.max_workers,
        early_stop=args.early_stop,
        shared_cache=args.shared_cache,
        discovery_board=args.discovery_board,
        semantic_store=args.semantic_store,
        replica_schedule=schedule,
    )

    print(f"coord_trace:  {result.coord_trace_path}")
    print(f"EX (chosen):  {result.ex_correct}")
    if result.early_stop:
        print(f"early_stop:   triggered={result.early_stop_triggered} cancelled={result.replicas_cancelled}")
    if result.shared_cache and result.cache_stats:
        print(f"cache:        hits={result.cache_stats.hits} "
              f"misses={result.cache_stats.misses} "
              f"hit_rate={result.cache_stats.hit_rate_pct:.1f}%")
    if result.discovery_board and result.discovery_stats:
        ds = result.discovery_stats
        print(
            f"discovery:    fragments={ds.fragments_added} "
            f"publishes={ds.publishes} injections={ds.context_injections}"
        )
    if result.semantic_store and result.semantic_stats:
        ss = result.semantic_stats
        print(
            f"semantic:     facts={ss.facts_added} "
            f"publishes={ss.publishes} injections={ss.context_injections} "
            f"chars={ss.injected_chars}"
        )
    if result.chosen:
        print(f"chosen trace: {result.chosen.trace_path}")
        print(f"turns:        {result.chosen.turns}")
    print()
    for i, rep in enumerate(result.replicas):
        mark = " *" if result.chosen and rep.trace_path == result.chosen.trace_path else ""
        print(
            f"  agent_{i}: EX={rep.ex_correct} turns={rep.turns} "
            f"stop={rep.stop_reason} "
            f"tokens={rep.total_prompt_tokens}+{rep.total_completion_tokens} "
            f"trace={rep.trace_path.name}{mark}"
        )
    if result.redundancy:
        print()
        print("redundancy:", json.dumps(result.redundancy.to_dict(), indent=2))

    return 0 if result.ex_correct == 1 else 1


if __name__ == "__main__":
    raise SystemExit(main())
