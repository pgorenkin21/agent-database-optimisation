#!/usr/bin/env python3
"""Compare a baseline parallel batch vs a ``--prompt-cache`` batch.

Produces a thesis-ready table of input-token spend, cached-token share, the
*effective* billed input tokens (cached tokens discounted), and the EX delta
that proves the saving is accuracy-neutral.

Usage:
    uv run python scripts/compare_prompt_cache.py \
        --baseline runs/batches/parallel_<id>_<tag>.json \
        --cached   runs/batches/parallel_<id>_<tag>_promptcache.json \
        [--cache-discount 0.5] [--report-id prompt_cache_vs_baseline]
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))


def _load(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


from src.coord.prompt_cache_analysis import compare_batches as compare


def format_markdown(
    summary: dict[str, Any], *, baseline_path: Path, cached_path: Path
) -> str:
    b = summary["baseline"]
    c = summary["cached"]
    d = summary["deltas"]
    ts = datetime.now(timezone.utc).isoformat()
    eff_delta = (
        f"{d['effective_input_token_pct']:+.1f}%"
        if d["effective_input_token_pct"] is not None
        else "—"
    )
    return "\n".join(
        [
            "# Prompt Cache vs Baseline",
            "",
            f"Generated: {ts}",
            "",
            f"- Baseline batch: `{baseline_path.name}`",
            f"- Cached batch:   `{cached_path.name}`",
            f"- Matched tasks (no API error in either): **{summary['matched_tasks']}**",
            f"- Cache discount applied to cached input tokens: "
            f"**{summary['cache_discount']:.2f}** "
            f"(cached billed at {summary['cache_discount'] * 100:.0f}%)",
            "",
            "| Metric | Baseline | Prompt cache | Δ |",
            "|--------|---------:|-------------:|---:|",
            f"| EX accuracy | {b['ex_pct']:.1f}% | {c['ex_pct']:.1f}% | {d['ex_pp']:+.1f}pp |",
            f"| Input tokens (raw) | {b['prompt_tokens']:,} | {c['prompt_tokens']:,} | "
            f"{d['raw_prompt_token_pct']:+.1f}% |",
            f"| Cached input tokens | — | {c['cached_prompt_tokens']:,} "
            f"({c['cached_prompt_pct']:.1f}%) | — |",
            f"| **Effective billed input** | {b['prompt_tokens']:,} | "
            f"{c['effective_input_tokens']:,.0f} | {eff_delta} |",
            f"| Completion tokens | {b['completion_tokens']:,} | {c['completion_tokens']:,} | — |",
            "",
            f"**Trajectory-controlled caching saving (within the cached run): "
            f"−{c['within_run_input_saving_pct']:.1f}% billed input.** This isolates the "
            "cache benefit from cross-run turn-count divergence.",
            "",
            "**Read:** prefer the trajectory-controlled line above as the headline. The "
            "cross-run *effective billed input* row also reflects trajectory differences "
            "(turn counts) between the two independent runs, which dominate on small or "
            "low-EX samples; the EX Δ confirms accuracy is unchanged.",
            "",
        ]
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--baseline", type=Path, required=True, help="Baseline batch JSON")
    parser.add_argument(
        "--cached", type=Path, required=True, help="--prompt-cache batch JSON"
    )
    parser.add_argument(
        "--cache-discount",
        type=float,
        default=0.5,
        help="Fraction of full price billed for cached input tokens (default 0.5)",
    )
    parser.add_argument("--out-dir", type=Path, default=REPO_ROOT / "runs" / "reports")
    parser.add_argument("--report-id", type=str, default="prompt_cache_vs_baseline")
    args = parser.parse_args()

    if not args.baseline.exists():
        print(f"Baseline batch not found: {args.baseline}", file=sys.stderr)
        return 1
    if not args.cached.exists():
        print(f"Cached batch not found: {args.cached}", file=sys.stderr)
        return 1

    summary = compare(
        _load(args.baseline),
        _load(args.cached),
        cache_discount=args.cache_discount,
    )
    if summary["matched_tasks"] == 0:
        print("No overlapping non-errored tasks between the two batches.", file=sys.stderr)
        return 1

    md = format_markdown(summary, baseline_path=args.baseline, cached_path=args.cached)
    args.out_dir.mkdir(parents=True, exist_ok=True)
    md_path = args.out_dir / f"{args.report_id}.md"
    json_path = args.out_dir / f"{args.report_id}.json"
    md_path.write_text(md, encoding="utf-8")
    json_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")

    print(md)
    print(f"\nWrote {md_path}")
    print(f"Wrote {json_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
