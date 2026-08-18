#!/usr/bin/env python3
"""Compare P0_cached vs P0_cached + --db-profile batches (Chapter 12).

Apples-to-apples: same model, replica count, and best_of_n policy, both under
--prompt-cache; the only difference is the persistent DB Profile Card. Reports the
headline metric — mean explore ``sql_execute`` events per task — with value-domain
vs join-graph attribution, alongside the EX delta (the thesis golden rule).
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from src.coord.baseline_plots import MODEL_LABELS
from src.coord.db_profile_analysis import (
    DBPROFILE_BASELINE_BATCH_IDS,
    DBPROFILE_ISOLATED_BATCH_IDS,
    build_isolated_comparisons_by_model,
    comparison_deltas,
    dbprofile_batch_summary,
)
from src.coord.early_stop_analysis import load_batch


def _fmt(v: Any, spec: str = "", dash: str = "—") -> str:
    if v is None:
        return dash
    return format(v, spec) if spec else str(v)


def _pct(v: float | None) -> str:
    if v is None:
        return "—"
    sign = "+" if v > 0 else ""
    return f"{sign}{v:.1f}%"


def _signed(v: float | None, spec: str = ".2f") -> str:
    if v is None:
        return "—"
    sign = "+" if v > 0 else ""
    return f"{sign}{format(v, spec)}"


def format_comparison_markdown(
    comparisons: list[tuple[dict[str, Any], dict[str, Any]]],
    *,
    title: str = "DB Profile (Chapter 12): P0_cached vs +db-profile",
) -> str:
    ts = datetime.now(timezone.utc).isoformat()
    lines = [
        f"# {title}",
        "",
        f"Generated: {ts}",
        "",
        "Apples-to-apples: same model, replica count, `best_of_n`, both under "
        "`--prompt-cache`. Only difference is `--db-profile` (the DB Profile Card).",
        "",
        "## Summary",
        "",
        "| Model | EX base % | EX +DPC % | EX Δ | Explore/task base | Explore/task +DPC | "
        "Explore Δ | Explore Δ% | Value-dom Δ | Join Δ | Token Δ | Traces |",
        "|-------|----------:|----------:|-----:|------------------:|------------------:|"
        "----------:|-----------:|------------:|-------:|--------:|-------:|",
    ]

    for base, var in comparisons:
        d = comparison_deltas(base, var)
        label = MODEL_LABELS.get(base["model_key"], base["model_key"])
        cov = f"{var.get('traces_found', 0)}/{var.get('task_count', 0)}"
        lines.append(
            f"| {label} "
            f"| {_fmt(base.get('ex_accuracy_pct'), '.1f')} "
            f"| {_fmt(var.get('ex_accuracy_pct'), '.1f')} "
            f"| {_signed(d['ex_pp'], '.1f')}pp "
            f"| {_fmt(base.get('mean_explore_per_task'), '.2f')} "
            f"| {_fmt(var.get('mean_explore_per_task'), '.2f')} "
            f"| {_signed(d['explore_per_task_delta'])} "
            f"| {_pct(d['explore_per_task_pct'])} "
            f"| {_signed(d['value_domain_explores_delta'])} "
            f"| {_signed(d['join_explores_delta'])} "
            f"| {_pct(d['token_pct'])} "
            f"| {cov} |"
        )

    lines.append("")
    for base, var in comparisons:
        label = MODEL_LABELS.get(base["model_key"], base["model_key"])
        lines.extend(
            [
                f"## {label}",
                "",
                f"- Baseline batch: `{Path(base.get('path', '')).name}`",
                f"- +db-profile batch: `{Path(var.get('path', '')).name}`",
                f"- Explore-trace coverage (+DPC): "
                f"**{var.get('traces_found', 0)}/{var.get('task_count', 0)}** tasks",
                "",
            ]
        )
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--baseline", type=Path, action="append", default=[],
        help="P0_cached batch JSON (repeatable; pair 1:1 with --dbprofile)",
    )
    parser.add_argument(
        "--dbprofile", type=Path, action="append", default=[], dest="dbprofile_paths",
        help="+db-profile batch JSON (repeatable)",
    )
    parser.add_argument("--batch-dir", type=Path, default=REPO_ROOT / "runs" / "batches")
    parser.add_argument(
        "--models", nargs="*",
        default=["gpt-4o-mini", "gemini-2.5-flash", "deepseek-v3.2"],
    )
    parser.add_argument("--replicas", type=int, default=10)
    parser.add_argument("--baseline-batch-id", type=str, default=None,
                        help=f"default: {DBPROFILE_BASELINE_BATCH_IDS}")
    parser.add_argument("--variant-batch-id", type=str, default=None,
                        help=f"default: {DBPROFILE_ISOLATED_BATCH_IDS}")
    parser.add_argument("--out-dir", type=Path, default=REPO_ROOT / "runs" / "reports")
    parser.add_argument("--report-id", type=str, default="db_profile_vs_p0cached")
    args = parser.parse_args()

    comparisons: list[tuple[dict[str, Any], dict[str, Any]]] = []

    if args.baseline and args.dbprofile_paths:
        if len(args.baseline) != len(args.dbprofile_paths):
            print("Must provide equal --baseline and --dbprofile paths", file=sys.stderr)
            return 1
        for base_path, var_path in zip(args.baseline, args.dbprofile_paths, strict=True):
            base = dbprofile_batch_summary(load_batch(base_path.resolve()), path=base_path.resolve())
            var = dbprofile_batch_summary(load_batch(var_path.resolve()), path=var_path.resolve())
            comparisons.append((base, var))
    else:
        by_model = build_isolated_comparisons_by_model(
            args.batch_dir.resolve(),
            models=args.models,
            n_replicas=args.replicas,
            baseline_batch_id=args.baseline_batch_id,
            variant_batch_id=args.variant_batch_id,
        )
        for model in args.models:
            if model in by_model:
                comparisons.append(by_model[model])
            else:
                print(
                    f"Missing baseline/db-profile batch pair for {model} "
                    f"r={args.replicas}",
                    file=sys.stderr,
                )

    if not comparisons:
        print("No comparison pairs found. Run the batches first (see Chapter 12 §12.5).",
              file=sys.stderr)
        return 1

    md = format_comparison_markdown(comparisons)
    args.out_dir.mkdir(parents=True, exist_ok=True)
    md_path = args.out_dir / f"{args.report_id}.md"
    json_path = args.out_dir / f"{args.report_id}.json"
    md_path.write_text(md, encoding="utf-8")
    json_path.write_text(
        json.dumps(
            {"comparisons": [{"baseline": b, "db_profile": v} for b, v in comparisons]},
            indent=2,
        ),
        encoding="utf-8",
    )
    print(md)
    print(f"\nWrote {md_path}")
    print(f"Wrote {json_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
