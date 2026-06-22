#!/usr/bin/env python3
"""Generate thesis Chapter 2 draft from P0 baseline report JSON files."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from src.coord.chapter2_draft import DEFAULT_REPORT_PATHS, generate_chapter2_markdown

DEFAULT_OUT = REPO_ROOT / "thesis" / "chapter2_baseline_redundancy.md"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "reports",
        nargs="*",
        type=Path,
        help="Baseline report JSON files (default: all three model reports)",
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
        default=REPO_ROOT / "runs" / "reports" / "plots",
        help="Directory containing baseline PNG figures",
    )
    args = parser.parse_args()

    if args.reports:
        report_paths = [p.resolve() for p in args.reports]
    else:
        report_paths = [(REPO_ROOT / rel).resolve() for rel in DEFAULT_REPORT_PATHS]

    missing = [p for p in report_paths if not p.is_file()]
    if missing:
        for p in missing:
            print(f"Missing report: {p}", file=sys.stderr)
        print("Run analyze_baseline_redundancy.py for each model first.", file=sys.stderr)
        return 1

    markdown = generate_chapter2_markdown(
        report_paths,
        plots_dir=args.plots_dir.relative_to(REPO_ROOT),
    )
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(markdown, encoding="utf-8")
    print(f"Wrote {args.out.resolve()}")
    print(f"  Sources: {len(report_paths)} report(s)")
    print(f"  Figures: {args.plots_dir.resolve()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
