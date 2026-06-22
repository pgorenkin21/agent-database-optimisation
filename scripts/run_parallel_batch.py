#!/usr/bin/env python3
"""Batch parallel-agent runs: N replicas per task with coordination policy."""

from __future__ import annotations

import argparse
import csv
import json
import sys
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from dotenv import load_dotenv
from src.bird.subset import resolve_task_subset
from src.config import load_config, validate_paths
from src.coord.baseline_analysis import batch_ex_accuracy_stats
from src.coord.interaction_metrics import batch_interaction_summary
from src.coord.parallel import run_parallel_agents
from src.coord.replica_schedule import (
    add_replica_schedule_arguments,
    schedule_batch_tag_suffix,
    schedule_from_args,
)
from src.coord.policies import policy_from_str
from src.llm.client import api_key_status
from src.llm.models import load_model_registry


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model", type=str, default=None)
    parser.add_argument("--config", type=Path, default=None)
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--subset-file", type=Path, default=None)
    parser.add_argument("--output-dir", type=Path, default=None)
    parser.add_argument("--replicas", type=int, default=3)
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
    parser.add_argument(
        "--schema-pruning",
        action="store_true",
        help="Prune schema context to question/evidence-matched tables (+ FK neighbors)",
    )
    parser.add_argument(
        "--schema-pruning-mode",
        type=str,
        default=None,
        choices=["keyword", "semantic", "hybrid"],
        help="Table selection for schema pruning (default: config schema_pruning_mode)",
    )
    parser.add_argument("--max-workers", type=int, default=None)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--fail-fast", action="store_true")
    parser.add_argument("--inter-task-delay", type=float, default=None)
    parser.add_argument(
        "--batch-id",
        type=str,
        default=None,
        help="Fixed batch id for output filenames (default: generated timestamp)",
    )
    add_replica_schedule_arguments(parser)
    args = parser.parse_args()

    load_dotenv(REPO_ROOT / ".env")
    cfg = load_config(args.config)
    if args.schema_pruning:
        cfg.raw["schema_pruning"] = True
    if args.schema_pruning_mode:
        cfg.raw["schema_pruning_mode"] = args.schema_pruning_mode
    model_key = args.model or cfg.default_model_key
    policy = policy_from_str(args.policy)
    schedule = schedule_from_args(args, cfg)

    warnings = validate_paths(cfg)
    if warnings:
        for w in warnings:
            print(f"WARN: {w}", file=sys.stderr)
        return 1

    registry = load_model_registry(cfg.models_config_path)
    spec = registry.get(model_key)
    model_key = spec.key
    ok, msg = api_key_status(spec)
    if not ok and not args.dry_run:
        print(f"API key missing for {model_key}: {msg}", file=sys.stderr)
        return 1

    tasks = resolve_task_subset(cfg, limit=args.limit, subset_file=args.subset_file)
    if not tasks:
        print("No tasks selected.", file=sys.stderr)
        return 1

    inter_task_delay = (
        args.inter_task_delay
        if args.inter_task_delay is not None
        else cfg.batch_inter_task_delay_seconds
    )

    batch_id = args.batch_id or (
        datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S") + "_" + uuid.uuid4().hex[:6]
    )
    tag = f"{model_key}_r{args.replicas}_{policy.value}"
    if args.shared_cache:
        tag += "_p1_cache"
    if args.discovery_board:
        tag += "_p2_discovery"
    if args.semantic_store:
        tag += "_p3_semantic"
    if args.early_stop:
        tag += "_early_stop"
    if args.schema_pruning or cfg.schema_pruning:
        tag += "_schema_prune"
    tag += schedule_batch_tag_suffix(schedule)
    out_dir = args.output_dir or (cfg.runs_dir / "batches")
    csv_path = out_dir / f"parallel_{batch_id}_{tag}.csv"
    json_path = out_dir / f"parallel_{batch_id}_{tag}.json"

    print(f"batch_id:     {batch_id}")
    print(f"model:        {model_key}")
    print(f"replicas:     {args.replicas}")
    print(f"policy:       {policy.value}")
    print(f"early_stop:   {args.early_stop}")
    print(f"shared_cache: {args.shared_cache}")
    print(f"discovery:    {args.discovery_board}")
    print(f"semantic:     {args.semantic_store}")
    print(f"schema_prune: {args.schema_pruning or cfg.schema_pruning} ({cfg.schema_pruning_mode})")
    print(f"schedule:     {schedule.to_dict()}")
    print(f"tasks:        {len(tasks)}")
    print(f"output:       {json_path}")

    if args.dry_run:
        for i, t in enumerate(tasks):
            print(f"  [{i}] question_id={t.question_id} db={t.db_id}")
        return 0

    rows: list[dict] = []
    failures = 0

    for i, task in enumerate(tasks):
        if i > 0 and inter_task_delay > 0:
            time.sleep(inter_task_delay)
        print(
            f"\n[{i + 1}/{len(tasks)}] question_id={task.question_id} "
            f"({task.difficulty}) x{args.replicas} ...",
            flush=True,
        )
        try:
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
            chosen = result.chosen
            red = result.redundancy
            cache = result.cache_stats
            discovery = result.discovery_stats
            semantic = result.semantic_stats
            interactions = result.interaction_metrics
            rows.append(
                {
                    "question_id": task.question_id,
                    "db_id": task.db_id,
                    "difficulty": task.difficulty,
                    "model_key": model_key,
                    "policy": policy.value,
                    "n_replicas": args.replicas,
                    "ex_correct": result.ex_correct,
                    "replicas_ex_correct": red.replicas_ex_correct if red else 0,
                    "chosen_turns": chosen.turns if chosen else 0,
                    "total_prompt_tokens": red.total_prompt_tokens if red else 0,
                    "total_completion_tokens": red.total_completion_tokens if red else 0,
                    "token_overhead_ratio": red.token_overhead_ratio if red else None,
                    "explore_redundancy_pct": red.explore_redundancy_pct if red else 0,
                    "early_stop": args.early_stop,
                    "early_stop_triggered": result.early_stop_triggered,
                    "replicas_cancelled": result.replicas_cancelled,
                    "shared_cache": args.shared_cache,
                    "cache_hits": cache.hits if cache else 0,
                    "cache_misses": cache.misses if cache else 0,
                    "cache_hit_rate_pct": round(cache.hit_rate_pct, 2) if cache else None,
                    "discovery_board": args.discovery_board,
                    "discovery_publishes": discovery.publishes if discovery else 0,
                    "discovery_fragments": discovery.fragments_added if discovery else 0,
                    "discovery_injections": discovery.context_injections if discovery else 0,
                    "semantic_store": args.semantic_store,
                    "semantic_publishes": semantic.publishes if semantic else 0,
                    "semantic_facts_added": semantic.facts_added if semantic else 0,
                    "semantic_injections": semantic.context_injections if semantic else 0,
                    "semantic_injected_chars": semantic.injected_chars if semantic else 0,
                    "db_interactions": interactions.db_sql_executions if interactions else 0,
                    "middleware_cache_hits": interactions.middleware_cache_hits if interactions else 0,
                    "middleware_discovery_injections": (
                        interactions.middleware_discovery_injections if interactions else 0
                    ),
                    "middleware_semantic_injections": (
                        interactions.middleware_semantic_injections if interactions else 0
                    ),
                    "middleware_interactions": interactions.middleware_interactions if interactions else 0,
                    "middleware_interaction_pct": (
                        round(interactions.middleware_interaction_pct, 2) if interactions else 0.0
                    ),
                    "coord_trace_path": str(result.coord_trace_path or ""),
                    "chosen_trace_path": str(chosen.trace_path) if chosen else "",
                    "error": None,
                }
            )
            status = "EX=1" if result.ex_correct else "EX=0"
            rep_ok = red.replicas_ex_correct if red else 0
            print(f"  -> {status} ({rep_ok}/{args.replicas} replicas correct)")
            if result.ex_correct == 0:
                failures += 1
        except Exception as e:
            failures += 1
            rows.append(
                {
                    "question_id": task.question_id,
                    "db_id": task.db_id,
                    "difficulty": task.difficulty,
                    "model_key": model_key,
                    "policy": policy.value,
                    "n_replicas": args.replicas,
                    "ex_correct": 0,
                    "replicas_ex_correct": 0,
                    "chosen_turns": 0,
                    "total_prompt_tokens": 0,
                    "total_completion_tokens": 0,
                    "token_overhead_ratio": 0,
                    "explore_redundancy_pct": 0,
                    "early_stop": args.early_stop,
                    "early_stop_triggered": False,
                    "replicas_cancelled": 0,
                    "shared_cache": args.shared_cache,
                    "cache_hits": 0,
                    "cache_misses": 0,
                    "cache_hit_rate_pct": None,
                    "discovery_board": args.discovery_board,
                    "discovery_publishes": 0,
                    "discovery_fragments": 0,
                    "discovery_injections": 0,
                    "semantic_store": args.semantic_store,
                    "semantic_publishes": 0,
                    "semantic_facts_added": 0,
                    "semantic_injections": 0,
                    "semantic_injected_chars": 0,
                    "db_interactions": 0,
                    "middleware_cache_hits": 0,
                    "middleware_discovery_injections": 0,
                    "middleware_semantic_injections": 0,
                    "middleware_interactions": 0,
                    "middleware_interaction_pct": 0.0,
                    "coord_trace_path": "",
                    "chosen_trace_path": "",
                    "error": str(e),
                }
            )
            print(f"  -> ERROR: {e}", file=sys.stderr)
            if args.fail_fast:
                break

    ex_stats = batch_ex_accuracy_stats(rows)
    ex_pct = ex_stats["ex_accuracy_pct"]
    interaction_stats = batch_interaction_summary(rows)
    payload = {
        "batch_id": batch_id,
        "model_key": model_key,
        "bird_split": cfg.bird_split,
        "policy": policy.value,
        "n_replicas": args.replicas,
        "early_stop": args.early_stop,
        "shared_cache": args.shared_cache,
        "discovery_board": args.discovery_board,
        "semantic_store": args.semantic_store,
        "schema_pruning": bool(args.schema_pruning or cfg.schema_pruning),
        "schema_pruning_mode": cfg.schema_pruning_mode,
        "replica_schedule": schedule.to_dict(),
        "task_count": len(tasks),
        "ex_accuracy_pct": ex_pct,
        "api_failure_count": ex_stats["api_failure_count"],
        "completed_task_count": ex_stats["completed_task_count"],
        "ex_accuracy_excluding_api_errors_pct": ex_stats["ex_accuracy_excluding_api_errors_pct"],
        "avg_token_overhead_ratio": round(
            sum(r["token_overhead_ratio"] for r in rows if r["token_overhead_ratio"] is not None)
            / sum(1 for r in rows if r["token_overhead_ratio"] is not None),
            3,
        )
        if any(r["token_overhead_ratio"] is not None for r in rows)
        else None,
        "avg_explore_redundancy_pct": round(
            sum(r["explore_redundancy_pct"] for r in rows) / len(rows), 2
        )
        if rows
        else 0,
        "avg_cache_hit_rate_pct": round(
            sum(r["cache_hit_rate_pct"] or 0 for r in rows if r.get("shared_cache"))
            / sum(1 for r in rows if r.get("shared_cache")),
            2,
        )
        if any(r.get("shared_cache") for r in rows)
        else None,
        "avg_discovery_fragments": round(
            sum(r["discovery_fragments"] for r in rows if r.get("discovery_board"))
            / sum(1 for r in rows if r.get("discovery_board")),
            2,
        )
        if any(r.get("discovery_board") for r in rows)
        else None,
        **interaction_stats,
        "rows": rows,
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }

    out_dir.mkdir(parents=True, exist_ok=True)
    json_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    if rows:
        with csv_path.open("w", encoding="utf-8", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
            writer.writeheader()
            writer.writerows(rows)

    print()
    print(f"Parallel batch {batch_id}")
    print(f"  Tasks:      {len(rows)} / {len(tasks)}")
    print(f"  EX:         {ex_pct:.1f}%")
    if ex_stats["api_failure_count"]:
        ex_excl = ex_stats["ex_accuracy_excluding_api_errors_pct"]
        print(f"  EX (no API fail): {ex_excl:.1f}%  ({ex_stats['api_failure_count']} API failures)")
    print(f"  Avg overhead ratio: {payload['avg_token_overhead_ratio']}")
    print(f"  Avg explore redundancy: {payload['avg_explore_redundancy_pct']}%")
    print(f"\nWrote {json_path}")
    print(f"Wrote {csv_path}")

    return 0 if failures == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
