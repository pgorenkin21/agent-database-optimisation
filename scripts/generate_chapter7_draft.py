#!/usr/bin/env python3
"""Generate thesis Chapter 7 P3 semantic store evaluation."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from src.coord.chapter7_draft import generate_chapter7_markdown
from src.coord.p3_analysis import load_comparisons_by_replica_counts

DEFAULT_OUT = REPO_ROOT / "thesis" / "chapter7_semantic_store.md"
DEFAULT_BATCH_DIR = REPO_ROOT / "runs" / "batches"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--batch-dir", type=Path, default=DEFAULT_BATCH_DIR)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--replicas", type=int, nargs="+", default=[10])
    args = parser.parse_args()

    data = load_comparisons_by_replica_counts(
        args.batch_dir.resolve(),
        replica_counts=args.replicas,
    )
    if not data.get("vs_full_stack_prune") and not data.get("vs_p0"):
        print("No P3 comparison batches found.", file=sys.stderr)
        return 1

    markdown = generate_chapter7_markdown(data)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(markdown, encoding="utf-8")
    print(f"Wrote {args.out.resolve()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
