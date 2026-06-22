#!/usr/bin/env python3
"""Generate thesis Chapter 5 draft from P2 vs P0 batch comparisons."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from src.coord.chapter5_draft import generate_chapter5_markdown
from src.coord.p2_analysis import load_comparisons_by_replica_counts
from src.coord.p2_plots import plot_p2_comparison

DEFAULT_OUT = REPO_ROOT / "thesis" / "chapter5_subexpr_propagation.md"
DEFAULT_BATCH_DIR = REPO_ROOT / "runs" / "batches"
DEFAULT_PLOTS_DIR = REPO_ROOT / "runs" / "reports" / "plots"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--batch-dir", type=Path, default=DEFAULT_BATCH_DIR)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--plots-dir", type=Path, default=DEFAULT_PLOTS_DIR)
    parser.add_argument("--replicas", type=int, nargs="+", default=[10, 25])
    parser.add_argument("--no-plots", action="store_true")
    args = parser.parse_args()

    comparisons = load_comparisons_by_replica_counts(
        args.batch_dir.resolve(),
        replica_counts=args.replicas,
    )
    if not comparisons:
        print("No P0 vs P2 comparison pairs found.", file=sys.stderr)
        print("Run P2 batches with --discovery-board --batch-id p2_r10_bo / p2_r25_bo.", file=sys.stderr)
        return 1

    if not args.no_plots:
        saved = plot_p2_comparison(comparisons, args.plots_dir.resolve())
        for path in saved:
            print(f"  {path.name}")

    markdown = generate_chapter5_markdown(
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
