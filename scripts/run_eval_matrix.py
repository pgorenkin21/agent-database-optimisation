#!/usr/bin/env python3
"""Run the full eval matrix: all models × variations (single + parallel) concurrently."""

from __future__ import annotations

import argparse
import json
import signal
import subprocess
import sys
import uuid
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from dotenv import load_dotenv

from src.config import load_config, validate_paths
from src.llm.client import api_key_status
from src.llm.models import load_model_registry

VARIATIONS = ("single", "parallel")

_ACTIVE_CHILD: subprocess.Popen[str] | None = None


def _terminate_active_child() -> None:
    global _ACTIVE_CHILD
    if _ACTIVE_CHILD is None:
        return
    if _ACTIVE_CHILD.poll() is None:
        _ACTIVE_CHILD.terminate()
        try:
            _ACTIVE_CHILD.wait(timeout=5)
        except subprocess.TimeoutExpired:
            _ACTIVE_CHILD.kill()
    _ACTIVE_CHILD = None


def _handle_interrupt(_signum: int, _frame: object) -> None:
    print("\nInterrupted — stopping active batch job ...", file=sys.stderr, flush=True)
    _terminate_active_child()
    raise SystemExit(130)


@dataclass(frozen=True)
class MatrixJob:
    variation: str
    model_key: str
    batch_id: str
    json_path: Path
    csv_path: Path
    cmd: list[str]


def _sanitize_batch_id(value: str) -> str:
    return value.replace("/", "_").replace(" ", "_")


def _build_jobs(
    *,
    matrix_id: str,
    models: list[str],
    variations: list[str],
    out_dir: Path,
    replicas: int,
    policy: str,
    config: Path | None,
    limit: int | None,
    subset_file: Path | None,
    inter_task_delay: float | None,
    python: str,
) -> list[MatrixJob]:
    jobs: list[MatrixJob] = []
    interpreter: list[str] = [python, "-u"]
    script_args: list[str] = []
    if config:
        script_args += ["--config", str(config)]
    if limit is not None:
        script_args += ["--limit", str(limit)]
    if subset_file:
        script_args += ["--subset-file", str(subset_file)]
    if inter_task_delay is not None:
        script_args += ["--inter-task-delay", str(inter_task_delay)]

    for variation in variations:
        for model_key in models:
            safe_model = _sanitize_batch_id(model_key)
            batch_id = f"{matrix_id}_{variation}_{safe_model}"
            if variation == "single":
                script = REPO_ROOT / "scripts" / "run_batch.py"
                json_path = out_dir / f"batch_{batch_id}_{model_key}.json"
                csv_path = out_dir / f"batch_{batch_id}_{model_key}.csv"
                cmd = [
                    *interpreter,
                    str(script),
                    *script_args,
                    "--model",
                    model_key,
                    "--batch-id",
                    batch_id,
                    "--output-dir",
                    str(out_dir),
                ]
            elif variation == "parallel":
                script = REPO_ROOT / "scripts" / "run_parallel_batch.py"
                tag = f"{model_key}_r{replicas}_{policy}"
                json_path = out_dir / f"parallel_{batch_id}_{tag}.json"
                csv_path = out_dir / f"parallel_{batch_id}_{tag}.csv"
                cmd = [
                    *interpreter,
                    str(script),
                    *script_args,
                    "--model",
                    model_key,
                    "--batch-id",
                    batch_id,
                    "--replicas",
                    str(replicas),
                    "--policy",
                    policy,
                    "--output-dir",
                    str(out_dir),
                ]
            else:
                raise ValueError(f"Unknown variation: {variation}")

            jobs.append(
                MatrixJob(
                    variation=variation,
                    model_key=model_key,
                    batch_id=batch_id,
                    json_path=json_path,
                    csv_path=csv_path,
                    cmd=cmd,
                )
            )
    return jobs


def _result_from_existing(job: MatrixJob, *, skipped: bool = False) -> dict[str, Any]:
    result: dict[str, Any] = {
        "variation": job.variation,
        "model_key": job.model_key,
        "batch_id": job.batch_id,
        "json_path": str(job.json_path),
        "csv_path": str(job.csv_path),
        "exit_code": 0,
        "dry_run": False,
        "skipped": skipped,
    }
    if job.json_path.is_file():
        payload = json.loads(job.json_path.read_text(encoding="utf-8"))
        result["ex_accuracy_pct"] = payload.get("ex_accuracy_pct")
        if job.variation == "single":
            result["avg_turns"] = payload.get("avg_turns")
            result["total_tokens"] = (
                (payload.get("total_prompt_tokens") or 0)
                + (payload.get("total_completion_tokens") or 0)
            )
        else:
            result["avg_token_overhead_ratio"] = payload.get("avg_token_overhead_ratio")
            result["avg_explore_redundancy_pct"] = payload.get("avg_explore_redundancy_pct")
            result["n_replicas"] = payload.get("n_replicas")
            result["policy"] = payload.get("policy")
    return result


def _run_job(job: MatrixJob, *, dry_run: bool, skip_existing: bool) -> dict[str, Any]:
    header = f"[{job.variation} | {job.model_key}]"
    if skip_existing and job.json_path.is_file():
        print(f"{header} SKIP (exists): {job.json_path.name}", flush=True)
        return _result_from_existing(job, skipped=True)

    if dry_run:
        print(f"{header} would run: {' '.join(job.cmd)}")
        print(f"{header} output: {job.json_path}")
        return {
            "variation": job.variation,
            "model_key": job.model_key,
            "batch_id": job.batch_id,
            "json_path": str(job.json_path),
            "csv_path": str(job.csv_path),
            "exit_code": 0,
            "dry_run": True,
        }

    global _ACTIVE_CHILD
    print(f"{header} starting ...", flush=True)
    proc = subprocess.Popen(job.cmd, cwd=REPO_ROOT, text=True)
    _ACTIVE_CHILD = proc
    exit_code = proc.wait()
    _ACTIVE_CHILD = None

    result: dict[str, Any] = {
        "variation": job.variation,
        "model_key": job.model_key,
        "batch_id": job.batch_id,
        "json_path": str(job.json_path),
        "csv_path": str(job.csv_path),
        "exit_code": exit_code,
        "dry_run": False,
        "skipped": False,
    }

    if job.json_path.is_file():
        payload = json.loads(job.json_path.read_text(encoding="utf-8"))
        result["ex_accuracy_pct"] = payload.get("ex_accuracy_pct")
        if job.variation == "single":
            result["avg_turns"] = payload.get("avg_turns")
            result["total_tokens"] = (
                (payload.get("total_prompt_tokens") or 0)
                + (payload.get("total_completion_tokens") or 0)
            )
        else:
            result["avg_token_overhead_ratio"] = payload.get("avg_token_overhead_ratio")
            result["avg_explore_redundancy_pct"] = payload.get("avg_explore_redundancy_pct")
            result["n_replicas"] = payload.get("n_replicas")
            result["policy"] = payload.get("policy")
    elif exit_code != 0:
        result["interrupted"] = exit_code in (130, -2, 2)

    status = "OK" if exit_code == 0 else "FAIL"
    print(f"{header} {status} (exit={exit_code})", flush=True)
    return result


def main() -> int:
    parser = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # All 3 models × single + parallel, models run concurrently per variation
  uv run python scripts/run_eval_matrix.py --limit 50

  # Dry-run the job plan
  uv run python scripts/run_eval_matrix.py --dry-run --limit 5

  # Single-agent only, sequential model runs
  uv run python scripts/run_eval_matrix.py --variations single --sequential
        """,
    )
    parser.add_argument("--config", type=Path, default=None)
    parser.add_argument(
        "--model",
        action="append",
        dest="models",
        help="Model registry key (repeatable). Default: llm.eval_models",
    )
    parser.add_argument(
        "--variations",
        type=str,
        default="single,parallel",
        help="Comma-separated: single, parallel (default: both)",
    )
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
        "--max-workers",
        type=int,
        default=3,
        help="Max concurrent model runs (default: 3 = all eval models at once)",
    )
    parser.add_argument(
        "--sequential",
        action="store_true",
        help="Run model jobs one at a time instead of concurrently",
    )
    parser.add_argument(
        "--skip-missing-keys",
        action="store_true",
        help="Skip models without API keys instead of aborting",
    )
    parser.add_argument("--inter-task-delay", type=float, default=None)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument(
        "--matrix-id",
        type=str,
        default=None,
        help="Fixed matrix id for output manifest (default: generated timestamp)",
    )
    parser.add_argument(
        "--skip-existing",
        action="store_true",
        help="Skip jobs whose batch JSON output already exists",
    )
    parser.add_argument(
        "--resume-from",
        type=Path,
        default=None,
        metavar="MATRIX.json",
        help="Resume a prior matrix run (reuses matrix_id; implies --skip-existing)",
    )
    args = parser.parse_args()

    signal.signal(signal.SIGINT, _handle_interrupt)
    signal.signal(signal.SIGTERM, _handle_interrupt)

    load_dotenv(REPO_ROOT / ".env")
    cfg = load_config(args.config)

    warnings = validate_paths(cfg)
    if warnings and not args.dry_run:
        for w in warnings:
            print(f"WARN: {w}", file=sys.stderr)
        return 1

    variations = [v.strip() for v in args.variations.split(",") if v.strip()]
    unknown = [v for v in variations if v not in VARIATIONS]
    if unknown:
        print(f"Unknown variations: {unknown}. Expected: {', '.join(VARIATIONS)}", file=sys.stderr)
        return 1

    registry = load_model_registry(cfg.models_config_path)
    model_keys: list[str] = []
    for key in args.models or cfg.eval_model_keys:
        spec = registry.get(key)
        model_keys.append(spec.key)

    if args.skip_missing_keys and not args.dry_run:
        available: list[str] = []
        for key in model_keys:
            spec = registry.get(key)
            ok, msg = api_key_status(spec)
            if ok:
                available.append(key)
            else:
                print(f"SKIP {key}: {msg}", file=sys.stderr)
        model_keys = available
        if not model_keys:
            print("No models with API keys available.", file=sys.stderr)
            return 1
    elif not args.dry_run:
        for key in model_keys:
            spec = registry.get(key)
            ok, msg = api_key_status(spec)
            if not ok:
                print(f"API key missing for {key}: {msg}", file=sys.stderr)
                return 1

    skip_existing = args.skip_existing or args.resume_from is not None
    if args.resume_from:
        if not args.resume_from.is_file():
            print(f"Matrix manifest not found: {args.resume_from}", file=sys.stderr)
            return 1
        prior = json.loads(args.resume_from.read_text(encoding="utf-8"))
        matrix_id = str(prior["matrix_id"])
        if args.limit is None and prior.get("task_count"):
            pass  # child scripts use config default unless --limit passed
        print(f"Resuming matrix {matrix_id} from {args.resume_from.name}")
    else:
        matrix_id = args.matrix_id or (
            datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S") + "_" + uuid.uuid4().hex[:6]
        )
    out_dir = args.output_dir or (cfg.runs_dir / "batches")
    out_dir.mkdir(parents=True, exist_ok=True)

    jobs = _build_jobs(
        matrix_id=matrix_id,
        models=model_keys,
        variations=variations,
        out_dir=out_dir,
        replicas=args.replicas,
        policy=args.policy,
        config=args.config,
        limit=args.limit,
        subset_file=args.subset_file,
        inter_task_delay=args.inter_task_delay,
        python=sys.executable,
    )

    print("Eval matrix")
    print(f"  matrix_id:   {matrix_id}")
    print(f"  models:      {', '.join(model_keys)}")
    print(f"  variations:  {', '.join(variations)}")
    print(f"  replicas:    {args.replicas} (parallel only)")
    print(f"  policy:      {args.policy} (parallel only)")
    pending = sum(1 for j in jobs if not (skip_existing and j.json_path.is_file()))
    print(f"  jobs:        {len(jobs)} ({pending} to run, {len(jobs) - pending} skipped)")
    print(f"  concurrency: {1 if args.sequential else min(args.max_workers, len(jobs))}")
    print(f"  output dir:  {out_dir}")
    if not args.dry_run and pending:
        est_tasks = (args.limit if args.limit is not None else cfg.subset_limit) or 50
        print(
            f"  note:        {pending} batch job(s) to run; up to {est_tasks} tasks each; "
            f"parallel variation uses {args.replicas} replicas per task",
            flush=True,
        )
    print()

    results: list[dict[str, Any]] = []
    workers = 1 if args.sequential else args.max_workers

    jobs_by_variation: dict[str, list[MatrixJob]] = {v: [] for v in variations}
    for job in jobs:
        jobs_by_variation[job.variation].append(job)

    for variation in variations:
        group = jobs_by_variation[variation]
        if not group:
            continue
        print(f"=== variation: {variation} ({len(group)} model job(s)) ===", flush=True)
        pool_workers = 1 if args.sequential else min(workers, len(group))
        if pool_workers == 1:
            for job in group:
                results.append(
                    _run_job(job, dry_run=args.dry_run, skip_existing=skip_existing)
                )
        else:
            with ThreadPoolExecutor(max_workers=pool_workers) as pool:
                futures = [
                    pool.submit(_run_job, job, dry_run=args.dry_run, skip_existing=skip_existing)
                    for job in group
                ]
                for fut in as_completed(futures):
                    results.append(fut.result())

    results.sort(key=lambda r: (r["variation"], r["model_key"]))
    manifest = {
        "matrix_id": matrix_id,
        "bird_split": cfg.bird_split,
        "variations": variations,
        "models": model_keys,
        "replicas": args.replicas,
        "policy": args.policy,
        "job_count": len(jobs),
        "results": results,
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }
    manifest_path = out_dir / f"matrix_{matrix_id}.json"
    if not args.dry_run:
        manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")

    print()
    print("Matrix summary")
    for row in results:
        ex = row.get("ex_accuracy_pct")
        ex_s = f"EX={ex}%" if ex is not None else "EX=?"
        extra = ""
        if row["variation"] == "parallel" and row.get("avg_token_overhead_ratio") is not None:
            extra = f" overhead={row['avg_token_overhead_ratio']}"
        if row.get("dry_run"):
            status = "dry-run"
        elif row.get("skipped"):
            status = "skipped"
        else:
            status = "ok" if row["exit_code"] == 0 else "FAIL"
        print(f"  {row['variation']:8} {row['model_key']:20} {ex_s}{extra} [{status}]")

    if not args.dry_run:
        print(f"\nWrote manifest: {manifest_path}")

    failed = sum(1 for r in results if r["exit_code"] != 0)
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
