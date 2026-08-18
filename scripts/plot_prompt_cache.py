#!/usr/bin/env python3
"""Plot turn-by-turn prompt-cache figures from a --prompt-cache batch.

Requires the batch to have been run with ``logging.log_llm_messages: true`` so
per-turn ``llm_turn`` events (with ``cached_prompt_tokens``) are present.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from src.coord.prompt_cache_plots import plot_prompt_cache_figures

DEFAULT_PLOTS_DIR = REPO_ROOT / "runs" / "reports" / "plots"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "batch_json",
        type=Path,
        help="Path to a parallel batch JSON run with --prompt-cache",
    )
    parser.add_argument("--out-dir", type=Path, default=DEFAULT_PLOTS_DIR)
    parser.add_argument(
        "--label", type=str, default=None, help="Title label (default: batch filename)"
    )
    args = parser.parse_args()

    if not args.batch_json.exists():
        print(f"Batch JSON not found: {args.batch_json}", file=sys.stderr)
        return 1

    try:
        saved = plot_prompt_cache_figures(
            args.batch_json, args.out_dir.resolve(), label=args.label
        )
    except ValueError as e:
        print(str(e), file=sys.stderr)
        return 1

    print(f"Output: {args.out_dir.resolve()}")
    for path in saved:
        print(f"  {path.name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
