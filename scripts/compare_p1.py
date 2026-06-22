#!/usr/bin/env python3
"""Compare P0 parallel batches vs P1 shared-cache batches."""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from src.coord.baseline_plots import MODEL_LABELS
from src.coord.early_stop_analysis import pct_delta


def _fmt_delta(value: float | None) -> str:
    if value is None:
        return "—"
    sign = "+" if value > 0 else ""
    return f"{sign}{value:.1f}%"


def format_comparison_markdown(
    comparisons_by_n: dict[int, list[tuple[dict[str, Any], dict[str, Any]]]],
    *,
    title: str = "P1 Shared Cache vs P0 Comparison",
) -> str:
    ts = datetime.now(timezone.utc).isoformat()
    lines = [
        f"# {title}",
        "",
        f"Generated: {ts}",
        "",
        "Apples-to-apples: same model, replica count, and `best_of_n` policy. "
        "P1 adds `--shared-cache` (AST-keyed LRU for explore-phase `execute_sql`).",
        "",
    ]

    for n in sorted(comparisons_by_n):
        comparisons = comparisons_by_n[n]
        lines.extend([f"## N={n}", ""])
        lines.extend(
            [
                "| Model | P0 EX % | P1 EX % | P0 red % | P1 red % | Red Δ | "
                "P1 cache hit % | P0 tokens | P1 tokens | Token Δ |",
                "|-------|--------:|--------:|---------:|---------:|------:|"
                "---------------:|----------:|----------:|--------:|",
            ]
        )
        footnotes: list[str] = []
        for p0, p1 in comparisons:
            label = MODEL_LABELS.get(p0["model_key"], p0["model_key"])
            p1_ex = f"{p1['ex_accuracy_pct']:.1f}"
            api_fails = int(p1.get("api_failure_count", 0))
            if api_fails:
                p1_ex = f"{p1_ex}†"
                ex_excl = p1.get("ex_accuracy_excluding_api_errors_pct")
                footnotes.append(
                    f"† {label} P1 run: {api_fails} API failure(s); "
                    f"EX on completed tasks = {ex_excl:.1f}%."
                )
            red_delta = (p1["avg_explore_redundancy_pct"] or 0) - (p0["avg_explore_redundancy_pct"] or 0)
            tok_delta = pct_delta(p0["total_tokens"], p1["total_tokens"])
            cache_hit = p1.get("avg_cache_hit_rate_pct") or p1.get("batch_cache_hit_rate_pct", 0)
            lines.append(
                f"| {label} | {p0['ex_accuracy_pct']:.1f} | {p1_ex} | "
                f"{p0['avg_explore_redundancy_pct']:.1f} | {p1['avg_explore_redundancy_pct']:.1f} | "
                f"{red_delta:+.1f}pp | {cache_hit:.1f} | "
                f"{p0['total_tokens']:,} | {p1['total_tokens']:,} | {_fmt_delta(tok_delta)} |"
            )
        if footnotes:
            lines.append("")
            lines.extend(footnotes)
        lines.append("")

        for p0, p1 in comparisons:
            label = MODEL_LABELS.get(p0["model_key"], p0["model_key"])
            lines.extend(
                [
                    f"### {label} (N={n})",
                    "",
                    f"- P0 batch: `{Path(p0['path']).name}`",
                    f"- P1 batch: `{Path(p1['path']).name}`",
                    f"- Cache: **{p1.get('total_cache_hits', 0):,}** hits / "
                    f"**{p1.get('total_cache_lookups', 0):,}** explore lookups "
                    f"({p1.get('avg_cache_hit_rate_pct', 0):.1f}% per-task mean)",
                    f"- Explore redundancy: {p0['avg_explore_redundancy_pct']:.1f}% → "
                    f"{p1['avg_explore_redundancy_pct']:.1f}%",
                    "",
                ]
            )

    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--batch-dir", type=Path, default=REPO_ROOT / "runs" / "batches")
    parser.add_argument("--replicas", type=int, nargs="+", default=[10, 25])
    parser.add_argument(
        "--out-dir",
        type=Path,
        default=REPO_ROOT / "runs" / "reports",
    )
    parser.add_argument("--report-id", type=str, default="p1_vs_p0")
    args = parser.parse_args()

    from src.coord.p1_analysis import load_comparisons_by_replica_counts

    comparisons = load_comparisons_by_replica_counts(
        args.batch_dir.resolve(),
        replica_counts=args.replicas,
    )
    if not comparisons:
        print("No P0 vs P1 comparison pairs found.", file=sys.stderr)
        return 1

    md = format_comparison_markdown(comparisons)
    args.out_dir.mkdir(parents=True, exist_ok=True)
    md_path = args.out_dir / f"{args.report_id}.md"
    json_path = args.out_dir / f"{args.report_id}.json"

    serialisable = {
        str(n): [{"p0": p0, "p1": p1} for p0, p1 in pairs]
        for n, pairs in comparisons.items()
    }
    md_path.write_text(md, encoding="utf-8")
    json_path.write_text(json.dumps(serialisable, indent=2), encoding="utf-8")
    print(md)
    print(f"\nWrote {md_path}")
    print(f"Wrote {json_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
