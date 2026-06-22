#!/usr/bin/env python3
"""Plot baseline redundancy reports for one or more models."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from src.coord.baseline_plots import plot_baseline_comparison

DEFAULT_REPORTS = [
    REPO_ROOT / "runs/reports/baseline_gpt4o_baseline_full.json",
    REPO_ROOT / "runs/reports/baseline_gemini_baseline_full.json",
    REPO_ROOT / "runs/reports/baseline_deepseek_baseline_full.json",
]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "reports",
        nargs="*",
        type=Path,
        help="Baseline report JSON files (default: all three model reports)",
    )
    parser.add_argument(
        "--out-dir",
        type=Path,
        default=REPO_ROOT / "runs" / "reports" / "plots",
        help="Directory for PNG outputs",
    )
    parser.add_argument(
        "--title-prefix",
        type=str,
        default="P0 baseline (mini-dev)",
    )
    args = parser.parse_args()

    paths = [p.resolve() for p in args.reports] if args.reports else DEFAULT_REPORTS
    missing = [p for p in paths if not p.is_file()]
    if missing:
        for p in missing:
            print(f"Missing report: {p}", file=sys.stderr)
        print(
            "Run analyze_baseline_redundancy.py for each model first.",
            file=sys.stderr,
        )
        return 1

    df, saved = plot_baseline_comparison(
        paths,
        args.out_dir.resolve(),
        title_prefix=args.title_prefix,
    )

    print(f"Models:  {', '.join(sorted(df['model_key'].unique()))}")
    print(f"Replicas: {sorted(df['n_replicas'].unique())}")
    print(f"Output:  {args.out_dir.resolve()}")
    print()
    for path in saved:
        print(f"  {path.name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
