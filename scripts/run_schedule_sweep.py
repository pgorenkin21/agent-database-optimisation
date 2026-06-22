#!/usr/bin/env python3
"""Sweep temperature and stagger settings for parallel batches (smoke experiments)."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

DEFAULT_MODELS = ["gemini-2.5-flash", "gpt-4o-mini", "deepseek-v3.2"]

SCENARIOS: list[dict] = [
    {"label": "t0", "temperature": 0.0},
    {"label": "t03", "temperature": 0.3},
    {"label": "t07", "temperature": 0.7},
    {"label": "ladder", "temperature": 0.0, "temperature_mode": "ladder"},
    {"label": "stag2s", "stagger_mode": "linear_seconds", "stagger_seconds": 2.0},
    {"label": "stag1t", "stagger_mode": "linear_turns", "stagger_turns": 1},
    {"label": "t03_stag2s", "temperature": 0.3, "stagger_mode": "linear_seconds", "stagger_seconds": 2.0},
]


def _run_one(
    *,
    python: str,
    model: str,
    batch_id: str,
    limit: int,
    replicas: int,
    temperature: float | None,
    temperature_mode: str | None,
    stagger_mode: str | None,
    stagger_seconds: float | None,
    stagger_turns: int | None,
    middleware: list[str],
    dry_run: bool,
    skip_existing: bool,
    out_dir: Path,
) -> tuple[int, str | None]:
    json_matches = sorted(out_dir.glob(f"parallel_{batch_id}_*.json"))
    if skip_existing and json_matches:
        print(f"[{model}] SKIP existing {json_matches[-1].name}", flush=True)
        return 0, str(json_matches[-1])

    cmd = [
        python,
        "-u",
        str(REPO_ROOT / "scripts" / "run_parallel_batch.py"),
        "--model",
        model,
        "--limit",
        str(limit),
        "--replicas",
        str(replicas),
        "--batch-id",
        batch_id,
        "--policy",
        "best_of_n",
    ]
    for flag in middleware:
        cmd.append(flag)
    if temperature is not None:
        cmd += ["--temperature", str(temperature)]
    if temperature_mode:
        cmd += ["--temperature-mode", temperature_mode]
    if stagger_mode:
        cmd += ["--stagger-mode", stagger_mode]
    if stagger_seconds is not None:
        cmd += ["--stagger-seconds", str(stagger_seconds)]
    if stagger_turns is not None:
        cmd += ["--stagger-turns", str(stagger_turns)]

    print(f"[{model}] {' '.join(cmd)}", flush=True)
    if dry_run:
        return 0, None
    code = subprocess.call(cmd, cwd=REPO_ROOT)
    json_matches = sorted(out_dir.glob(f"parallel_{batch_id}_*.json"))
    return code, str(json_matches[-1]) if json_matches else None


def _run_model_sweep(
    model: str,
    *,
    sweep_id: str,
    python: str,
    limit: int,
    replicas: int,
    middleware: list[str],
    dry_run: bool,
    skip_existing: bool,
    out_dir: Path,
) -> tuple[int, list[dict]]:
    """Run all scenarios sequentially for one model."""
    safe = model.replace(".", "-")
    rc = 0
    entries: list[dict] = []
    print(f"[{model}] Starting model sweep ({len(SCENARIOS)} scenarios)", flush=True)
    for sc in SCENARIOS:
        batch_id = f"{sweep_id}_{sc['label']}_{safe}"
        code, path = _run_one(
            python=python,
            model=model,
            batch_id=batch_id,
            limit=limit,
            replicas=replicas,
            temperature=sc.get("temperature"),
            temperature_mode=sc.get("temperature_mode"),
            stagger_mode=sc.get("stagger_mode"),
            stagger_seconds=sc.get("stagger_seconds"),
            stagger_turns=sc.get("stagger_turns"),
            middleware=middleware,
            dry_run=dry_run,
            skip_existing=skip_existing,
            out_dir=out_dir,
        )
        rc = rc or code
        entries.append(
            {
                "batch_id": batch_id,
                "model": model,
                "scenario": sc["label"],
                "exit_code": code,
                "json_path": path,
                **{k: v for k, v in sc.items() if k != "label"},
            }
        )
    print(f"[{model}] Model sweep finished (exit={rc})", flush=True)
    return rc, entries


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--models", nargs="+", default=DEFAULT_MODELS)
    parser.add_argument("--limit", type=int, default=50)
    parser.add_argument("--replicas", type=int, default=10)
    parser.add_argument("--sweep-id", type=str, default="sched_r10")
    parser.add_argument(
        "--middleware",
        nargs="+",
        default=["--shared-cache", "--early-stop", "--schema-pruning", "--schema-pruning-mode", "hybrid"],
        help="Flags passed to run_parallel_batch (default: P1+early stop+hybrid prune)",
    )
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument(
        "--skip-existing",
        action="store_true",
        help="Skip scenarios whose batch JSON already exists in runs/batches",
    )
    parser.add_argument(
        "--parallel-models",
        action="store_true",
        help="Run one model sweep per thread; scenarios stay sequential within each model",
    )
    parser.add_argument(
        "--parallel-scenarios",
        action="store_true",
        help="Run every model×scenario batch job concurrently (high API load)",
    )
    parser.add_argument(
        "--max-parallel",
        type=int,
        default=7,
        help="Max concurrent jobs when --parallel-scenarios (default: 7)",
    )
    parser.add_argument("--out-dir", type=Path, default=REPO_ROOT / "runs" / "batches")
    parser.add_argument("--python", type=str, default=sys.executable)
    args = parser.parse_args()
    args.out_dir.mkdir(parents=True, exist_ok=True)

    if args.parallel_models and args.parallel_scenarios:
        print("Use only one of --parallel-models or --parallel-scenarios.", file=sys.stderr)
        return 2

    rc = 0
    manifest: list[dict] = []

    if args.parallel_models:
        workers = max(1, len(args.models))
        print(f"Running {len(args.models)} model sweeps in parallel (scenarios sequential)", flush=True)
        with ThreadPoolExecutor(max_workers=workers) as pool:
            futures = {
                pool.submit(
                    _run_model_sweep,
                    model,
                    sweep_id=args.sweep_id,
                    python=args.python,
                    limit=args.limit,
                    replicas=args.replicas,
                    middleware=args.middleware,
                    dry_run=args.dry_run,
                    skip_existing=args.skip_existing,
                    out_dir=args.out_dir.resolve(),
                ): model
                for model in args.models
            }
            for fut in as_completed(futures):
                model_rc, entries = fut.result()
                rc = rc or model_rc
                manifest.extend(entries)
        manifest.sort(key=lambda e: (e["model"], e["scenario"]))
    elif args.parallel_scenarios:
        jobs: list[tuple[str, dict]] = []
        for model in args.models:
            safe = model.replace(".", "-")
            for sc in SCENARIOS:
                jobs.append((model, {**sc, "batch_id": f"{args.sweep_id}_{sc['label']}_{safe}"}))

        def _execute(job: tuple[str, dict]) -> dict:
            model, sc = job
            code, path = _run_one(
                python=args.python,
                model=model,
                batch_id=sc["batch_id"],
                limit=args.limit,
                replicas=args.replicas,
                temperature=sc.get("temperature"),
                temperature_mode=sc.get("temperature_mode"),
                stagger_mode=sc.get("stagger_mode"),
                stagger_seconds=sc.get("stagger_seconds"),
                stagger_turns=sc.get("stagger_turns"),
                middleware=args.middleware,
                dry_run=args.dry_run,
                skip_existing=args.skip_existing,
                out_dir=args.out_dir.resolve(),
            )
            return {
                "batch_id": sc["batch_id"],
                "model": model,
                "scenario": sc["label"],
                "exit_code": code,
                "json_path": path,
                **{k: v for k, v in sc.items() if k not in ("label", "batch_id")},
            }

        workers = max(1, min(args.max_parallel, len(jobs)))
        print(f"Running {len(jobs)} scenario jobs with max_parallel={workers}", flush=True)
        with ThreadPoolExecutor(max_workers=workers) as pool:
            futures = {pool.submit(_execute, job): job for job in jobs}
            for fut in as_completed(futures):
                entry = fut.result()
                manifest.append(entry)
                rc = rc or int(entry["exit_code"])
        manifest.sort(key=lambda e: (e["model"], e["scenario"]))
    else:
        for model in args.models:
            model_rc, entries = _run_model_sweep(
                model,
                sweep_id=args.sweep_id,
                python=args.python,
                limit=args.limit,
                replicas=args.replicas,
                middleware=args.middleware,
                dry_run=args.dry_run,
                skip_existing=args.skip_existing,
                out_dir=args.out_dir.resolve(),
            )
            rc = rc or model_rc
            manifest.extend(entries)

    mode = (
        "parallel_models"
        if args.parallel_models
        else ("parallel_scenarios" if args.parallel_scenarios else "sequential")
    )
    manifest_path = args.out_dir / f"sweep_{args.sweep_id}.json"
    manifest_path.write_text(
        json.dumps(
            {
                "sweep_id": args.sweep_id,
                "generated_at": datetime.now(timezone.utc).isoformat(),
                "execution_mode": mode,
                "max_parallel": args.max_parallel if args.parallel_scenarios else len(args.models)
                if args.parallel_models
                else 1,
                "models": args.models,
                "limit": args.limit,
                "replicas": args.replicas,
                "middleware": args.middleware,
                "scenarios": [s["label"] for s in SCENARIOS],
                "runs": manifest,
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    print(f"\nWrote manifest {manifest_path}", flush=True)
    return rc


if __name__ == "__main__":
    raise SystemExit(main())
