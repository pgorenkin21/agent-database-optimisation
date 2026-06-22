#!/usr/bin/env python3
"""Generate thesis Chapter 9 synthesis and deployment rules."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from src.coord.chapter9_draft import generate_chapter9_markdown
from src.coord.synthesis_analysis import build_synthesis

DEFAULT_OUT = REPO_ROOT / "thesis" / "chapter9_synthesis.md"
DEFAULT_BATCH_DIR = REPO_ROOT / "runs" / "batches"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--batch-dir", type=Path, default=DEFAULT_BATCH_DIR)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--sweep-id", type=str, default="sched_r10_bo")
    parser.add_argument("--replicas", type=int, default=10)
    args = parser.parse_args()

    data = build_synthesis(
        args.batch_dir.resolve(),
        n_replicas=args.replicas,
        sweep_id=args.sweep_id,
    )
    if not data.get("by_model"):
        print("No synthesis batches found.", file=sys.stderr)
        return 1

    markdown = generate_chapter9_markdown(data)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(markdown, encoding="utf-8")
    print(f"Wrote {args.out.resolve()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
