#!/usr/bin/env python3
"""Compare P3 semantic store vs P0 and vs P2 full stack+schema prune."""

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
from src.coord.p3_analysis import load_comparisons_by_replica_counts


def _fmt_delta(value: float | None, *, suffix: str = "%") -> str:
    if value is None:
        return "—"
    sign = "+" if value > 0 else ""
    return f"{sign}{value:.1f}{suffix}"


def _rec_label(rec: str) -> str:
    return {
        "adopt": "**Adopt P3**",
        "mixed": "**Mixed**",
        "avoid": "**Avoid P3** (use P2 full stack+prune)",
        "investigate": "**Investigate**",
    }.get(rec, rec)


def format_comparison_markdown(data: dict[str, Any]) -> str:
    ts = datetime.now(timezone.utc).isoformat()
    lines = [
        "# P3 Semantic Store Comparison",
        "",
        f"Generated: {ts}",
        "",
        "**P3 stack:** P1 cache + P3 semantic fact store + early stop + hybrid schema prune "
        "(`--semantic-store --shared-cache --early-stop --schema-pruning --schema-pruning-mode hybrid`).",
        "",
        "**P2 baseline:** full stack + schema prune (P1 + P2 discovery board + early stop + schema prune).",
        "",
        "50-task BIRD mini-dev smoke subset; `best_of_n` at N=10 unless noted.",
        "",
    ]

    vs_p2 = data.get("vs_full_stack_prune", {})
    recs_by_n = data.get("recommendations", {})

    for n in sorted(vs_p2, key=int):
        rows = vs_p2[n]
        lines.extend([f"## N={n}: P3 vs P2 full stack+prune", ""])
        lines.extend(
            [
                "| Model | P2 EX % | P3 EX % | EX Δ | P2 tokens | P3 tokens | Token Δ | "
                "Semantic inj/task | Recommendation |",
                "|-------|--------:|--------:|-----:|----------:|----------:|--------:|"
                "----------------:|----------------|",
            ]
        )
        for entry in rows:
            p2 = entry["p2_full_stack_prune"]
            p3 = entry["p3"]
            d = entry["delta"]
            label = MODEL_LABELS.get(p3["model_key"], p3["model_key"])
            rec = d.get("recommendation", "mixed")
            lines.append(
                f"| {label} | {p2['ex_accuracy_pct']:.1f} | {p3['ex_accuracy_pct']:.1f} | "
                f"{d['ex_delta_pp']:+.1f}pp | {p2['total_tokens']:,} | {p3['total_tokens']:,} | "
                f"{_fmt_delta(d.get('token_delta_pct'))} | "
                f"{d.get('avg_semantic_injections_per_task', 0):.1f} | {_rec_label(rec)} |"
            )
        lines.append("")

        lines.extend(["### Recommendations", ""])
        for entry in rows:
            p3 = entry["p3"]
            d = entry["delta"]
            label = MODEL_LABELS.get(p3["model_key"], p3["model_key"])
            lines.append(f"- **{label}:** {_rec_label(d['recommendation'])} — {d['recommendation_reason']}")
        lines.append("")

        # Cross-model thesis summary
        recs = recs_by_n.get(n, {})
        adopt = [m for m, r in recs.items() if r["recommendation"] == "adopt"]
        avoid = [m for m, r in recs.items() if r["recommendation"] == "avoid"]
        mixed = [m for m, r in recs.items() if r["recommendation"] == "mixed"]
        lines.extend(
            [
                "### Thesis summary (N={})".format(n),
                "",
                f"- **Adopt P3 for:** {', '.join(MODEL_LABELS.get(m, m) for m in adopt) or 'none on this subset'}",
                f"- **Prefer P2 full stack+prune for:** {', '.join(MODEL_LABELS.get(m, m) for m in avoid) or 'none'}",
                f"- **Mixed / further work:** {', '.join(MODEL_LABELS.get(m, m) for m in mixed) or 'none'}",
                "",
            ]
        )
        if any(recs.get(m, {}).get("recommendation") == "mixed" for m in recs):
            p2p3_rows = data.get("p2p3_combined", {}).get(n, [])
            if not p2p3_rows:
                lines.extend(
                    [
                        "**Suggested follow-up:** run **P2+P3 combined** (`--discovery-board --semantic-store`) "
                        "on Gemini and DeepSeek to test whether discovery fragments recover EX while semantic facts "
                        "cap prompt growth.",
                        "",
                    ]
                )

        for entry in rows:
            p2 = entry["p2_full_stack_prune"]
            p3 = entry["p3"]
            label = MODEL_LABELS.get(p3["model_key"], p3["model_key"])
            lines.extend(
                [
                    f"### {label} (N={n})",
                    "",
                    f"- P2 batch: `{Path(p2['path']).name}`",
                    f"- P3 batch: `{Path(p3['path']).name}`",
                    f"- Cache hit (P3): {p3.get('avg_cache_hit_rate_pct') or 0:.1f}%",
                    f"- Semantic: {p3.get('avg_semantic_facts_per_task', 0):.1f} facts/task, "
                    f"{p3.get('avg_semantic_injections_per_task', 0):.1f} injections/task",
                    f"- Middleware interaction (P3): {p3.get('avg_middleware_interaction_pct', 0):.1f}%",
                    "",
                ]
            )

    p2p3 = data.get("p2p3_combined", {})
    if p2p3:
        lines.extend(["## P2+P3 combined (discovery + semantic store)", ""])
        for n in sorted(p2p3, key=int):
            lines.extend([f"### N={n}", ""])
            lines.append(
                "| Model | P2+prune EX | P3 only EX | P2+P3 EX | P2+P3 tokens | Δ vs P2 | Δ vs P3 |"
            )
            lines.append("|-------|----------:|-----------:|---------:|-------------:|--------:|--------:|")
            for entry in p2p3[n]:
                label = MODEL_LABELS.get(entry["model_key"], entry["model_key"])
                p2 = entry.get("p2_full_stack_prune", {})
                p3 = entry.get("p3_only", {})
                c = entry["p2p3"]
                d2 = entry.get("vs_p2", {})
                d3 = entry.get("vs_p3", {})
                lines.append(
                    f"| {label} | {p2.get('ex_accuracy_pct', '—')} | {p3.get('ex_accuracy_pct', '—')} | "
                    f"{c.get('ex_accuracy_pct', '—')} | {c.get('total_tokens', 0):,} | "
                    f"{_fmt_delta(d2.get('token_delta_pct'))} | {_fmt_delta(d3.get('token_delta_pct'))} |"
                )
            lines.append("")
            for entry in p2p3[n]:
                label = MODEL_LABELS.get(entry["model_key"], entry["model_key"])
                c = entry["p2p3"]
                d2 = entry.get("vs_p2", {})
                lines.append(
                    f"- **{label}:** P2+P3 EX **{c.get('ex_accuracy_pct')}%** "
                    f"({d2.get('ex_delta_pp', 0):+.0f} pp vs P2+prune); "
                    f"tokens {_fmt_delta(d2.get('token_delta_pct'))} vs P2+prune."
                )
            lines.append("")

    vs_p0 = data.get("vs_p0", {})
    if vs_p0:
        lines.extend(["## P3 vs P0 baseline", ""])
        for n in sorted(vs_p0, key=int):
            lines.extend([f"### N={n}", ""])
            lines.append(
                "| Model | P0 EX % | P3 EX % | P0 tokens | P3 tokens | Token Δ vs P0 |"
            )
            lines.append("|-------|--------:|--------:|----------:|----------:|--------------:|")
            for entry in vs_p0[n]:
                p0, p3, d = entry["p0"], entry["p3"], entry["delta"]
                label = MODEL_LABELS.get(p3["model_key"], p3["model_key"])
                lines.append(
                    f"| {label} | {p0['ex_accuracy_pct']:.1f} | {p3['ex_accuracy_pct']:.1f} | "
                    f"{p0['total_tokens']:,} | {p3['total_tokens']:,} | "
                    f"{_fmt_delta(d.get('token_delta_pct'))} |"
                )
            lines.append("")

    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--batch-dir", type=Path, default=REPO_ROOT / "runs" / "batches")
    parser.add_argument("--replicas", type=int, nargs="+", default=[10])
    parser.add_argument("--out-dir", type=Path, default=REPO_ROOT / "runs" / "reports")
    parser.add_argument("--report-id", type=str, default="p3_vs_p2")
    args = parser.parse_args()

    data = load_comparisons_by_replica_counts(
        args.batch_dir.resolve(),
        replica_counts=args.replicas,
    )
    if not data.get("vs_full_stack_prune") and not data.get("vs_p0"):
        print("No P3 comparison pairs found.", file=sys.stderr)
        return 1

    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        **data,
    }
    md = format_comparison_markdown(payload)
    args.out_dir.mkdir(parents=True, exist_ok=True)
    md_path = args.out_dir / f"{args.report_id}.md"
    json_path = args.out_dir / f"{args.report_id}.json"
    md_path.write_text(md, encoding="utf-8")
    json_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print(md)
    print(f"\nWrote {md_path}")
    print(f"Wrote {json_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
