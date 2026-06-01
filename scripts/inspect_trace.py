#!/usr/bin/env python3
"""Pretty-print a JSONL run trace."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from src.logging.trace import read_trace_events


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("trace_file", type=Path, help="Path to runs/<run_id>.jsonl")
    args = parser.parse_args()

    if not args.trace_file.exists():
        print(f"Not found: {args.trace_file}", file=sys.stderr)
        return 1

    for event in read_trace_events(args.trace_file):
        print(json.dumps(event, indent=2, ensure_ascii=False))
        print("---")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
