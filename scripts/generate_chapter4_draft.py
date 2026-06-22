#!/usr/bin/env python3
"""Generate thesis Chapter 4 draft from P1 vs P0 batch comparisons."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from src.coord.chapter4_draft import generate_chapter4_markdown
from src.coord.p1_analysis import load_comparisons_by_replica_counts
from src.coord.p1_plots import plot_p1_comparison

DEFAULT_OUT = REPO_ROOT / "thesis" / "chapter4_shared_cache.md"
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
        print("No P0 vs P1 comparison pairs found.", file=sys.stderr)
        print("Run P1 batches with --shared-cache --batch-id p1_r10_bo / p1_r25_bo.", file=sys.stderr)
        return 1

    if not args.no_plots:
        saved = plot_p1_comparison(comparisons, args.plots_dir.resolve())
        for path in saved:
            print(f"  {path.name}")

    markdown = generate_chapter4_markdown(
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
