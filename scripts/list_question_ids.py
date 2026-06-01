#!/usr/bin/env python3
"""Print BIRD question_id values for building subset files."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from src.config import load_config  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--limit", type=int, default=50, help="Max IDs to print (0 = all)")
    parser.add_argument(
        "--config",
        type=Path,
        default=None,
        help="Path to YAML config (default: configs/default.yaml)",
    )
    args = parser.parse_args()

    cfg = load_config(args.config)
    if not cfg.tasks_json.exists():
        print(f"tasks JSON not found: {cfg.tasks_json}", file=sys.stderr)
        return 1

    with cfg.tasks_json.open(encoding="utf-8") as f:
        tasks = json.load(f)

    rows = tasks if args.limit == 0 else tasks[: args.limit]
    for row in rows:
        qid = row.get("question_id", row.get("id"))
        print(qid)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
