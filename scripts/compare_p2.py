#!/usr/bin/env python3
"""Compare P0 parallel batches vs P2 discovery-board batches."""

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
    title: str = "P2 Discovery Board vs P0 Comparison",
) -> str:
    ts = datetime.now(timezone.utc).isoformat()
    lines = [
        f"# {title}",
        "",
        f"Generated: {ts}",
        "",
        "Apples-to-apples: same model, replica count, and `best_of_n` policy. "
        "P2 adds `--discovery-board` (shared sub-expression propagation via prompt injection). "
        "Early-stop variants are excluded.",
        "",
    ]

    for n in sorted(comparisons_by_n):
        comparisons = comparisons_by_n[n]
        lines.extend([f"## N={n}", ""])
        lines.extend(
            [
                "| Model | P0 EX % | P2 EX % | P0 red % | P2 red % | Red Δ | "
                "P2 frags/task | P0 tokens | P2 tokens | Token Δ |",
                "|-------|--------:|--------:|---------:|---------:|------:|"
                "-------------:|----------:|----------:|--------:|",
            ]
        )
        footnotes: list[str] = []
        for p0, p2 in comparisons:
            label = MODEL_LABELS.get(p0["model_key"], p0["model_key"])
            p2_ex = f"{p2['ex_accuracy_pct']:.1f}"
            api_fails = int(p2.get("api_failure_count", 0))
            if api_fails:
                p2_ex = f"{p2_ex}†"
                ex_excl = p2.get("ex_accuracy_excluding_api_errors_pct")
                footnotes.append(
                    f"† {label} P2 run: {api_fails} API failure(s); "
                    f"EX on completed tasks = {ex_excl:.1f}%."
                )
            red_delta = (p2["avg_explore_redundancy_pct"] or 0) - (p0["avg_explore_redundancy_pct"] or 0)
            tok_delta = pct_delta(p0["total_tokens"], p2["total_tokens"])
            frags = p2.get("avg_discovery_fragments") or 0
            lines.append(
                f"| {label} | {p0['ex_accuracy_pct']:.1f} | {p2_ex} | "
                f"{p0['avg_explore_redundancy_pct']:.1f} | {p2['avg_explore_redundancy_pct']:.1f} | "
                f"{red_delta:+.1f}pp | {frags:.1f} | "
                f"{p0['total_tokens']:,} | {p2['total_tokens']:,} | {_fmt_delta(tok_delta)} |"
            )
        if footnotes:
            lines.append("")
            lines.extend(footnotes)
        lines.append("")

        for p0, p2 in comparisons:
            label = MODEL_LABELS.get(p0["model_key"], p0["model_key"])
            lines.extend(
                [
                    f"### {label} (N={n})",
                    "",
                    f"- P0 batch: `{Path(p0['path']).name}`",
                    f"- P2 batch: `{Path(p2['path']).name}`",
                    f"- Discovery: **{p2.get('avg_discovery_fragments', 0):.1f}** fragments/task mean, "
                    f"**{p2.get('avg_discovery_injections_per_task', 0):.1f}** context injections/task",
                    f"- Explore redundancy: {p0['avg_explore_redundancy_pct']:.1f}% → "
                    f"{p2['avg_explore_redundancy_pct']:.1f}%",
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
    parser.add_argument("--report-id", type=str, default="p2_vs_p0")
    args = parser.parse_args()

    from src.coord.p2_analysis import load_comparisons_by_replica_counts

    comparisons = load_comparisons_by_replica_counts(
        args.batch_dir.resolve(),
        replica_counts=args.replicas,
    )
    if not comparisons:
        print("No P0 vs P2 comparison pairs found.", file=sys.stderr)
        return 1

    md = format_comparison_markdown(comparisons)
    args.out_dir.mkdir(parents=True, exist_ok=True)
    md_path = args.out_dir / f"{args.report_id}.md"
    json_path = args.out_dir / f"{args.report_id}.json"

    serialisable = {
        str(n): [{"p0": p0, "p2": p2} for p0, p2 in pairs]
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
