#!/usr/bin/env python3
"""Run P1+P2+P3+early-stop+hybrid schema prune batches across eval models concurrently."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from dotenv import load_dotenv

from src.config import load_config, validate_paths
from src.coord.early_stop_analysis import DEFAULT_MODELS
from src.llm.client import api_key_status
from src.llm.models import load_model_registry


@dataclass(frozen=True)
class SweepJob:
    model_key: str
    batch_id: str
    json_path: Path
    cmd: list[str]


def _expected_json_path(out_dir: Path, batch_id: str, model_key: str, replicas: int) -> Path:
    tag = (
        f"{model_key}_r{replicas}_best_of_n"
        "_p1_cache_p2_discovery_p3_semantic_early_stop_schema_prune"
    )
    return out_dir / f"parallel_{batch_id}_{tag}.json"


def _build_job(
    *,
    model_key: str,
    batch_id: str,
    replicas: int,
    out_dir: Path,
    config: Path | None,
    limit: int | None,
    subset_file: Path | None,
    inter_task_delay: float | None,
    schema_pruning_mode: str,
    python: str,
) -> SweepJob:
    cmd = [
        python,
        "-u",
        str(REPO_ROOT / "scripts" / "run_parallel_batch.py"),
        "--model",
        model_key,
        "--replicas",
        str(replicas),
        "--policy",
        "best_of_n",
        "--shared-cache",
        "--discovery-board",
        "--semantic-store",
        "--early-stop",
        "--schema-pruning",
        "--schema-pruning-mode",
        schema_pruning_mode,
        "--batch-id",
        batch_id,
        "--output-dir",
        str(out_dir),
    ]
    if config:
        cmd.extend(["--config", str(config)])
    if limit is not None:
        cmd.extend(["--limit", str(limit)])
    if subset_file:
        cmd.extend(["--subset-file", str(subset_file)])
    if inter_task_delay is not None:
        cmd.extend(["--inter-task-delay", str(inter_task_delay)])

    return SweepJob(
        model_key=model_key,
        batch_id=batch_id,
        json_path=_expected_json_path(out_dir, batch_id, model_key, replicas),
        cmd=cmd,
    )


def _run_job(job: SweepJob, *, dry_run: bool, skip_existing: bool) -> dict[str, Any]:
    header = f"[{job.model_key}]"
    if skip_existing and job.json_path.is_file():
        print(f"{header} SKIP (exists): {job.json_path.name}", flush=True)
        payload = json.loads(job.json_path.read_text(encoding="utf-8"))
        return {
            "model_key": job.model_key,
            "batch_id": job.batch_id,
            "json_path": str(job.json_path),
            "exit_code": 0,
            "skipped": True,
            "ex_accuracy_pct": payload.get("ex_accuracy_pct"),
            "avg_token_overhead_ratio": payload.get("avg_token_overhead_ratio"),
        }

    if dry_run:
        print(f"{header} would run: {' '.join(job.cmd)}")
        return {
            "model_key": job.model_key,
            "batch_id": job.batch_id,
            "json_path": str(job.json_path),
            "exit_code": 0,
            "dry_run": True,
        }

    print(f"{header} starting ...", flush=True)
    proc = subprocess.run(job.cmd, cwd=REPO_ROOT, text=True)
    result: dict[str, Any] = {
        "model_key": job.model_key,
        "batch_id": job.batch_id,
        "json_path": str(job.json_path),
        "exit_code": proc.returncode,
        "skipped": False,
    }
    if job.json_path.is_file():
        payload = json.loads(job.json_path.read_text(encoding="utf-8"))
        result["ex_accuracy_pct"] = payload.get("ex_accuracy_pct")
        result["avg_token_overhead_ratio"] = payload.get("avg_token_overhead_ratio")
        result["avg_explore_redundancy_pct"] = payload.get("avg_explore_redundancy_pct")
    status = "OK" if proc.returncode == 0 else "DONE" if job.json_path.is_file() else "FAIL"
    print(f"{header} {status} (exit={proc.returncode})", flush=True)
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=None)
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--subset-file", type=Path, default=None)
    parser.add_argument("--replicas", type=int, default=10)
    parser.add_argument(
        "--models",
        nargs="+",
        default=["gemini-2.5-flash", "deepseek-v3.2"],
        help="Model keys (default: gemini + deepseek)",
    )
    parser.add_argument(
        "--batch-id",
        type=str,
        default=None,
        help="Shared batch id prefix (default: p2p3_hybrid_r{replicas}_bo)",
    )
    parser.add_argument(
        "--schema-pruning-mode",
        type=str,
        default="hybrid",
        choices=["keyword", "semantic", "hybrid"],
    )
    parser.add_argument("--output-dir", type=Path, default=None)
    parser.add_argument("--max-workers", type=int, default=2)
    parser.add_argument("--skip-existing", action="store_true")
    parser.add_argument("--skip-missing-keys", action="store_true")
    parser.add_argument("--inter-task-delay", type=float, default=None)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    load_dotenv(REPO_ROOT / ".env")
    cfg = load_config(args.config)
    warnings = validate_paths(cfg)
    if warnings:
        for w in warnings:
            print(f"WARN: {w}", file=sys.stderr)
        return 1

    registry = load_model_registry(cfg.models_config_path)
    batch_id = args.batch_id or f"p2p3_hybrid_r{args.replicas}_bo"
    out_dir = args.output_dir or (cfg.runs_dir / "batches")
    out_dir.mkdir(parents=True, exist_ok=True)

    jobs: list[SweepJob] = []
    for model_key in args.models:
        spec = registry.get(model_key)
        model_key = spec.key
        ok, msg = api_key_status(spec)
        if not ok and not args.dry_run:
            if args.skip_missing_keys:
                print(f"SKIP {model_key}: {msg}", file=sys.stderr)
                continue
            print(f"API key missing for {model_key}: {msg}", file=sys.stderr)
            return 1
        jobs.append(
            _build_job(
                model_key=model_key,
                batch_id=batch_id,
                replicas=args.replicas,
                out_dir=out_dir,
                config=args.config,
                limit=args.limit,
                subset_file=args.subset_file,
                inter_task_delay=args.inter_task_delay,
                schema_pruning_mode=args.schema_pruning_mode,
                python=sys.executable,
            )
        )

    print(f"batch_id:  {batch_id}")
    print(f"replicas:  {args.replicas}")
    print(
        "stack:     P1 cache + P2 discovery + P3 semantic store + early stop "
        f"+ schema prune ({args.schema_pruning_mode})"
    )
    print(f"models:    {', '.join(j.model_key for j in jobs)}")
    print(f"workers:   {args.max_workers}")

    if not jobs:
        return 1

    results: list[dict[str, Any]] = []
    if args.dry_run or args.max_workers <= 1 or len(jobs) == 1:
        for job in jobs:
            results.append(_run_job(job, dry_run=args.dry_run, skip_existing=args.skip_existing))
    else:
        with ThreadPoolExecutor(max_workers=min(args.max_workers, len(jobs))) as pool:
            futures = {
                pool.submit(
                    _run_job, job, dry_run=args.dry_run, skip_existing=args.skip_existing
                ): job
                for job in jobs
            }
            for fut in as_completed(futures):
                results.append(fut.result())

    results.sort(key=lambda r: r["model_key"])
    manifest = {
        "sweep_id": batch_id,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "replicas": args.replicas,
        "schema_pruning_mode": args.schema_pruning_mode,
        "stack": "P1+P2+P3+early_stop+schema_prune",
        "job_count": len(results),
        "results": results,
    }
    manifest_path = out_dir / f"sweep_{batch_id}.json"
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")

    print("\nSweep summary")
    for row in results:
        ex = row.get("ex_accuracy_pct")
        ex_s = f"{ex:.1f}%" if isinstance(ex, (int, float)) else "—"
        skip = " (skipped)" if row.get("skipped") else ""
        print(f"  {row['model_key']}: EX={ex_s} exit={row['exit_code']}{skip}")
    print(f"\nWrote {manifest_path}")

    hard_failures = [
        r
        for r in results
        if not r.get("skipped") and not r.get("dry_run") and not Path(r["json_path"]).is_file()
    ]
    return 1 if hard_failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
