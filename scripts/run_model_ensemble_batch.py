#!/usr/bin/env python3
"""P0 baseline with heterogeneous models: one replica per model, best_of_n on EX."""

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
    parser.add_argument(
        "--models",
        type=str,
        nargs="+",
        default=None,
        help="Model registry keys (default: llm.eval_models from config)",
    )
    parser.add_argument("--config", type=Path, default=None)
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--subset-file", type=Path, default=None)
    parser.add_argument(
        "--batch-id",
        type=str,
        default=None,
        help="Fixed batch id for output filenames (default: generated timestamp)",
    )
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--fail-fast", action="store_true")
    parser.add_argument("--inter-task-delay", type=float, default=None)
    args = parser.parse_args()

    load_dotenv(REPO_ROOT / ".env")
    cfg = load_config(args.config)
    model_keys = args.models or cfg.eval_model_keys
    if len(model_keys) < 2:
        print("ERROR: ensemble requires at least two models.", file=sys.stderr)
        return 1

    warnings = validate_paths(cfg)
    if warnings:
        for w in warnings:
            print(f"WARN: {w}", file=sys.stderr)
        return 1

    registry = load_model_registry(cfg.models_config_path)
    resolved: list[str] = []
    for raw_key in model_keys:
        spec = registry.get(raw_key)
        resolved.append(spec.key)
        ok, msg = api_key_status(spec)
        if not ok and not args.dry_run:
            print(f"API key missing for {spec.key}: {msg}", file=sys.stderr)
            return 1

    batch_id = args.batch_id or (
        datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S") + "_" + uuid.uuid4().hex[:6]
    )

    print(f"batch_id:  {batch_id}")
    print(f"models:    {', '.join(resolved)}")
    print(f"policy:    P0_parallel (heterogeneous replicas, best_of_n on EX)")

    parallel_script = REPO_ROOT / "scripts" / "run_parallel_batch.py"
    cmd = [
        sys.executable,
        "-u",
        str(parallel_script),
        "--models",
        *resolved,
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
    print(" ".join(cmd))
    rc = subprocess.call(cmd, cwd=REPO_ROOT)
    if rc != 0:
        print(f"Ensemble batch exited {rc}", file=sys.stderr)
        return rc

    if args.dry_run:
        print()
        print("Dry-run complete. Re-run without --dry-run to execute API calls.")
        return 0

    print()
    print("Ensemble batch complete.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
