#!/usr/bin/env python3
"""Plot early-stop vs P0 comparison figures."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from src.coord.chapter3_draft import load_comparisons_from_batches
from src.coord.early_stop_plots import plot_early_stop_comparison

DEFAULT_BATCH_DIR = REPO_ROOT / "runs" / "batches"
DEFAULT_PLOTS_DIR = REPO_ROOT / "runs" / "reports" / "plots"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--batch-dir", type=Path, default=DEFAULT_BATCH_DIR)
    parser.add_argument("--out-dir", type=Path, default=DEFAULT_PLOTS_DIR)
    parser.add_argument("--replicas", type=int, nargs="+", default=[10, 25])
    args = parser.parse_args()

    comparisons = load_comparisons_from_batches(
        args.batch_dir.resolve(),
        replica_counts=args.replicas,
    )
    if not comparisons:
        print("No comparison data found.", file=sys.stderr)
        return 1

    saved = plot_early_stop_comparison(comparisons, args.out_dir.resolve())
    print(f"Output: {args.out_dir.resolve()}")
    for path in saved:
        print(f"  {path.name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
