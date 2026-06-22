#!/usr/bin/env python3
"""Generate thesis Chapter 3 draft from early-stop vs P0 batch comparisons."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from src.coord.chapter3_draft import generate_chapter3_markdown, load_comparisons_from_batches
from src.coord.early_stop_plots import plot_early_stop_comparison

DEFAULT_OUT = REPO_ROOT / "thesis" / "chapter3_early_stopping.md"
DEFAULT_BATCH_DIR = REPO_ROOT / "runs" / "batches"
DEFAULT_PLOTS_DIR = REPO_ROOT / "runs" / "reports" / "plots"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--batch-dir",
        type=Path,
        default=DEFAULT_BATCH_DIR,
        help="Directory containing parallel batch JSON files",
    )
    parser.add_argument(
        "--out",
        type=Path,
        default=DEFAULT_OUT,
        help=f"Output markdown path (default: {DEFAULT_OUT.relative_to(REPO_ROOT)})",
    )
    parser.add_argument(
        "--plots-dir",
        type=Path,
        default=DEFAULT_PLOTS_DIR,
        help="Directory for early-stop PNG figures",
    )
    parser.add_argument(
        "--replicas",
        type=int,
        nargs="+",
        default=[10, 25],
        help="Replica counts to include (default: 10 25)",
    )
    parser.add_argument(
        "--no-plots",
        action="store_true",
        help="Skip figure generation",
    )
    args = parser.parse_args()

    comparisons = load_comparisons_from_batches(
        args.batch_dir.resolve(),
        replica_counts=args.replicas,
    )
    if not comparisons:
        print("No early-stop comparison pairs found.", file=sys.stderr)
        print("Run early-stop batches with batch-id earlystop_r10_bo / earlystop_r25_bo.", file=sys.stderr)
        return 1

    if not args.no_plots:
        saved = plot_early_stop_comparison(comparisons, args.plots_dir.resolve())
        for path in saved:
            print(f"  {path.name}")

    markdown = generate_chapter3_markdown(
        comparisons,
        plots_dir=args.plots_dir.relative_to(REPO_ROOT),
    )
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(markdown, encoding="utf-8")
    print(f"Wrote {args.out.resolve()}")
    for n, pairs in sorted(comparisons.items()):
        print(f"  N={n}: {len(pairs)} model comparison(s)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
