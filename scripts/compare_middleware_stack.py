#!/usr/bin/env python3
"""Compare P0, P1, P2, P1+P2, and early-stop batches (middleware stack)."""

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
from src.coord.middleware_stack_analysis import load_stack_by_replica_counts

POLICY_ORDER = [
    "P0",
    "P1",
    "P2",
    "P1+P2",
    "early_stop",
    "full_stack",
    "full_stack_prune",
    "P3_semantic",
]
POLICY_LABELS = {
    "full_stack_prune": "full_stack+prune",
    "P3_semantic": "P3 semantic+prune",
}


def format_stack_markdown(
    stacks_by_n: dict[int, dict[str, dict[str, dict[str, Any]]]],
    *,
    title: str = "Middleware Stack Comparison",
) -> str:
    ts = datetime.now(timezone.utc).isoformat()
    lines = [
        f"# {title}",
        "",
        f"Generated: {ts}",
        "",
        "Policies: **P0** (baseline), **P1** (shared SQL cache), **P2** (discovery board), "
        "**P1+P2** (both), **early_stop** (Chapter 3; same `best_of_n` selection), "
        "**full_stack** (P1+P2+early stop), "
        "**full_stack+prune** (P1+P2+early stop+schema pruning), "
        "**P3 semantic+prune** (P1+P3 semantic store+early stop+hybrid schema prune). "
        "50-task smoke subset unless noted.",
        "",
    ]

    for n in sorted(stacks_by_n):
        stack_by_model = stacks_by_n[n]
        lines.extend([f"## N={n}", ""])
        policies = [p for p in POLICY_ORDER if any(p in stack_by_model[m] for m in stack_by_model)]
        policy_headers = [POLICY_LABELS.get(p, p) for p in policies]

        # Per-metric tables
        for metric_key, metric_label, fmt in [
            ("ex_accuracy_pct", "Execution accuracy (%)", "{:.1f}"),
            ("avg_explore_redundancy_pct", "Explore redundancy (%)", "{:.1f}"),
            ("avg_token_overhead_ratio", "Token overhead (×)", "{:.2f}"),
            ("avg_middleware_interaction_pct", "Middleware interaction (%)", "{:.1f}"),
        ]:
            lines.extend([f"### {metric_label}", ""])
            lines.append("| Model | " + " | ".join(policy_headers) + " |")
            lines.append("|-------|" + "|".join(["--------:" for _ in policies]) + "|")
            for model, policies_map in stack_by_model.items():
                label = MODEL_LABELS.get(model, model)
                cells = []
                for p in policies:
                    row = policies_map.get(p)
                    if row is None:
                        cells.append("—")
                    else:
                        val = row.get(metric_key)
                        if metric_key == "total_tokens":
                            cells.append(f"{int(val):,}" if val is not None else "—")
                        elif val is not None:
                            cells.append(fmt.format(val))
                        else:
                            cells.append("—")
                lines.append(f"| {label} | " + " | ".join(cells) + " |")
            lines.append("")

        # Token delta vs P0
        lines.extend(["### Token Δ vs P0", ""])
        lines.append("| Model | " + " | ".join(p for p in policies if p != "P0") + " |")
        lines.append("|-------|" + "|".join(["--------:" for _ in policies if _ != "P0"]) + "|")
        for model, policies_map in stack_by_model.items():
            label = MODEL_LABELS.get(model, model)
            p0 = policies_map.get("P0")
            if not p0:
                continue
            cells = []
            for p in policies:
                if p == "P0":
                    continue
                row = policies_map.get(p)
                if row is None:
                    cells.append("—")
                else:
                    d = pct_delta(p0.get("total_tokens"), row.get("total_tokens"))
                    cells.append(f"{d:+.1f}%" if d is not None else "—")
            lines.append(f"| {label} | " + " | ".join(cells) + " |")
        lines.append("")

        # P1+P2 detail
        lines.extend(["### P1+P2 combined (cache + discovery)", ""])
        for model, policies_map in stack_by_model.items():
            row = policies_map.get("P1+P2")
            if not row:
                continue
            label = MODEL_LABELS.get(model, model)
            p0 = policies_map.get("P0", {})
            lines.extend(
                [
                    f"**{label}** — batch `{Path(row.get('path', '')).name}`",
                    f"- EX: {p0.get('ex_accuracy_pct', '—')} → {row.get('ex_accuracy_pct')}%",
                    f"- Redundancy: {p0.get('avg_explore_redundancy_pct', '—')} → "
                    f"{row.get('avg_explore_redundancy_pct')}%",
                    f"- Cache hit: {row.get('avg_cache_hit_rate_pct') or row.get('batch_cache_hit_rate_pct', 0):.1f}%",
                    f"- Middleware interaction: {row.get('avg_middleware_interaction_pct', 0):.1f}% "
                    f"(DB: {row.get('total_db_interactions', 0):,}, "
                    f"middleware: {row.get('total_middleware_interactions', 0):,})",
                    f"- Discovery fragments/task: {row.get('avg_discovery_fragments', 0)}",
                    "",
                ]
            )

    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--batch-dir", type=Path, default=REPO_ROOT / "runs" / "batches")
    parser.add_argument("--replicas", type=int, nargs="+", default=[10, 25])
    parser.add_argument("--out-dir", type=Path, default=REPO_ROOT / "runs" / "reports")
    parser.add_argument("--report-id", type=str, default="middleware_stack")
    args = parser.parse_args()

    stacks = load_stack_by_replica_counts(
        args.batch_dir.resolve(),
        replica_counts=args.replicas,
    )
    if not stacks:
        print("No middleware stack batches found.", file=sys.stderr)
        return 1

    md = format_stack_markdown(stacks)
    args.out_dir.mkdir(parents=True, exist_ok=True)
    md_path = args.out_dir / f"{args.report_id}.md"
    json_path = args.out_dir / f"{args.report_id}.json"
    json_path.write_text(json.dumps(stacks, indent=2, default=str), encoding="utf-8")
    md_path.write_text(md, encoding="utf-8")
    print(md)
    print(f"\nWrote {md_path}")
    print(f"Wrote {json_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
