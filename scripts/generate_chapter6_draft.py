#!/usr/bin/env python3
"""Generate thesis Chapter 6 middleware stack synthesis."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from src.coord.chapter6_draft import generate_chapter6_markdown
from src.coord.middleware_stack_analysis import load_stack_by_replica_counts
from src.coord.middleware_stack_plots import plot_middleware_stack

DEFAULT_OUT = REPO_ROOT / "thesis" / "chapter6_middleware_stack.md"
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

    stacks = load_stack_by_replica_counts(
        args.batch_dir.resolve(),
        replica_counts=args.replicas,
    )
    if not stacks:
        print("No middleware stack batches found.", file=sys.stderr)
        return 1

    if not args.no_plots:
        for n, stack_by_model in sorted(stacks.items()):
            saved = plot_middleware_stack(stack_by_model, args.plots_dir.resolve(), n_replicas=n)
            for path in saved:
                print(f"  {path.name}")

    markdown = generate_chapter6_markdown(
        stacks,
        plots_dir=args.plots_dir.relative_to(REPO_ROOT),
    )
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(markdown, encoding="utf-8")
    print(f"Wrote {args.out.resolve()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
