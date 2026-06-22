#!/usr/bin/env python3
"""Run P1+P2+early-stop (full middleware stack) parallel batches."""

from __future__ import annotations

import argparse
import subprocess
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from dotenv import load_dotenv

from src.config import load_config, validate_paths
from src.coord.early_stop_analysis import DEFAULT_MODELS
from src.coord.middleware_stack_analysis import (
    FULL_STACK_BATCH_IDS,
    FULL_STACK_SCHEMA_PRUNE_BATCH_IDS,
)
from src.llm.client import api_key_status
from src.llm.models import load_model_registry


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=None)
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--subset-file", type=Path, default=None)
    parser.add_argument("--replicas", type=int, default=25)
    parser.add_argument(
        "--models",
        nargs="+",
        default=list(DEFAULT_MODELS),
        help="Model keys to run (default: all eval models)",
    )
    parser.add_argument(
        "--batch-id",
        type=str,
        default=None,
        help="Fixed batch id prefix (default: fullstack_r{replicas}_bo or fullstack_prune_r{replicas}_bo)",
    )
    parser.add_argument(
        "--schema-pruning",
        action="store_true",
        help="Also enable schema pruning (prompt-layer table selection)",
    )
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--fail-fast", action="store_true")
    parser.add_argument("--inter-task-delay", type=float, default=None)
    args = parser.parse_args()

    load_dotenv(REPO_ROOT / ".env")
    cfg = load_config(args.config)

    warnings = validate_paths(cfg)
    if warnings:
        for w in warnings:
            print(f"WARN: {w}", file=sys.stderr)
        return 1

    registry = load_model_registry(cfg.models_config_path)
    default_ids = (
        FULL_STACK_SCHEMA_PRUNE_BATCH_IDS if args.schema_pruning else FULL_STACK_BATCH_IDS
    )
    batch_id = args.batch_id or default_ids.get(
        args.replicas,
        f"fullstack_prune_r{args.replicas}_bo"
        if args.schema_pruning
        else f"fullstack_r{args.replicas}_bo",
    )

    stack_label = "P1_shared_cache + P2_discovery + early_stop"
    if args.schema_pruning:
        stack_label += " + schema_prune"

    print(f"batch_id:  {batch_id}")
    print(f"replicas:  {args.replicas}")
    print(f"policy:    {stack_label}")
    print(f"models:    {', '.join(args.models)}")

    parallel_script = REPO_ROOT / "scripts" / "run_parallel_batch.py"
    failures = 0

    for model_key in args.models:
        spec = registry.get(model_key)
        model_key = spec.key
        ok, msg = api_key_status(spec)
        if not ok and not args.dry_run:
            print(f"SKIP {model_key}: {msg}", file=sys.stderr)
            failures += 1
            continue

        cmd = [
            sys.executable,
            "-u",
            str(parallel_script),
            "--model",
            model_key,
            "--replicas",
            str(args.replicas),
            "--policy",
            "best_of_n",
            "--shared-cache",
            "--discovery-board",
            "--early-stop",
            "--batch-id",
            batch_id,
        ]
        if args.schema_pruning:
            cmd.append("--schema-pruning")
        if args.config:
            cmd.extend(["--config", str(args.config)])
        if args.limit is not None:
            cmd.extend(["--limit", str(args.limit)])
        if args.subset_file:
            cmd.extend(["--subset-file", str(args.subset_file)])
        if args.inter_task_delay is not None:
            cmd.extend(["--inter-task-delay", str(args.inter_task_delay)])
        if args.fail_fast:
            cmd.append("--fail-fast")
        if args.dry_run:
            cmd.append("--dry-run")

        print()
        print(f"=== {model_key} ===")
        print(" ".join(cmd))
        rc = subprocess.call(cmd, cwd=REPO_ROOT)
        if rc != 0:
            failures += 1
            print(f"Batch for {model_key} exited {rc}", file=sys.stderr)
            if args.fail_fast:
                break

    if args.dry_run:
        print()
        print("Dry-run complete. Re-run without --dry-run to execute API calls.")
        return 0

    print()
    if failures:
        print(f"Full-stack sweep finished with {failures} failed batch(es).", file=sys.stderr)
        return 1

    print("Full-stack sweep complete.")
    print(
        "Compare: uv run python scripts/compare_middleware_stack.py "
        f"--replicas {args.replicas} --report-id fullstack_r{args.replicas}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
