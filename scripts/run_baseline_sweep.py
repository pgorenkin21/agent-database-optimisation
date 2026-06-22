#!/usr/bin/env python3
"""Run P0 baseline parallel batches across replica counts (3, 10, 25)."""

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
from src.llm.client import api_key_status
from src.llm.models import load_model_registry


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model", type=str, default=None)
    parser.add_argument("--config", type=Path, default=None)
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--subset-file", type=Path, default=None)
    parser.add_argument(
        "--replicas",
        type=int,
        nargs="+",
        default=[3, 10, 25],
        help="Replica counts to sweep (default: 3 10 25)",
    )
    parser.add_argument(
        "--sweep-id",
        type=str,
        default=None,
        help="Shared id prefix for all batches in this sweep",
    )
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--fail-fast", action="store_true")
    parser.add_argument("--inter-task-delay", type=float, default=None)
    parser.add_argument(
        "--analyze",
        action="store_true",
        help="Run analyze_baseline_redundancy.py after all batches complete",
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
    model_key = spec.key
    ok, msg = api_key_status(spec)
    if not ok and not args.dry_run:
        print(f"API key missing for {model_key}: {msg}", file=sys.stderr)
        return 1

    sweep_id = args.sweep_id or (
        datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S") + "_" + uuid.uuid4().hex[:6]
    )

    print(f"sweep_id:  {sweep_id}")
    print(f"model:     {model_key}")
    print(f"replicas:  {args.replicas}")
    print(f"policy:    P0_parallel (independent replicas, best_of_n coordination)")

    parallel_script = REPO_ROOT / "scripts" / "run_parallel_batch.py"
    failures = 0

    for n in args.replicas:
        batch_id = f"{sweep_id}_baseline_r{n}"
        cmd = [
            sys.executable,
            "-u",
            str(parallel_script),
            "--model",
            model_key,
            "--replicas",
            str(n),
            "--policy",
            "best_of_n",
            "--batch-id",
            batch_id,
        ]
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
        print(f"=== {n} replicas ===")
        print(" ".join(cmd))
        if args.dry_run:
            rc = subprocess.call(cmd, cwd=REPO_ROOT)
        else:
            rc = subprocess.call(cmd, cwd=REPO_ROOT)
        if rc != 0:
            failures += 1
            print(f"Batch r={n} exited {rc}", file=sys.stderr)
            if args.fail_fast:
                break

    if args.analyze and not args.dry_run and failures == 0:
        analyze_script = REPO_ROOT / "scripts" / "analyze_baseline_redundancy.py"
        analyze_cmd = [
            sys.executable,
            str(analyze_script),
            "--sweep-id",
            sweep_id,
            "--model",
            model_key,
            "--report-id",
            sweep_id,
        ]
        print()
        print("=== Analysing sweep ===")
        subprocess.call(analyze_cmd, cwd=REPO_ROOT)

    if args.dry_run:
        print()
        print("Dry-run complete. Re-run without --dry-run to execute API calls.")
        return 0

    print()
    if failures:
        print(f"Sweep finished with {failures} failed batch(es).", file=sys.stderr)
        return 1

    print("Sweep complete.")
    print(f"Analyse: uv run python scripts/analyze_baseline_redundancy.py --sweep-id {sweep_id} --model {model_key}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
