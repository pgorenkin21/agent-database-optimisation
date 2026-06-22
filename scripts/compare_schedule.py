#!/usr/bin/env python3
"""Compare temperature / stagger schedule sweep vs t0 and vs P2 full stack+prune."""

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
from src.coord.schedule_analysis import (
    SCHEDULE_SCENARIOS,
    build_schedule_comparisons,
)


def _fmt_delta(value: float | None, *, suffix: str = "%") -> str:
    if value is None:
        return "—"
    sign = "+" if value > 0 else ""
    return f"{sign}{value:.1f}{suffix}"


def _rec_label(rec: str) -> str:
    return {
        "adopt": "**Adopt**",
        "mixed": "**Mixed**",
        "avoid": "**Avoid**",
        "investigate": "**Investigate**",
    }.get(rec, rec)


def format_comparison_markdown(data: dict[str, Any]) -> str:
    ts = datetime.now(timezone.utc).isoformat()
    lines = [
        "# Schedule Sweep Comparison (Temperature & Stagger)",
        "",
        f"Generated: {ts}",
        "",
        f"**Sweep ID:** `{data.get('sweep_id')}` at N={data.get('n_replicas')}.",
        "",
        "**Stack:** P1 cache + early stop + hybrid schema prune (no P2 discovery, no P3 semantic store).",
        "",
        "**Scenarios:** uniform/ladder temperature; linear stagger (seconds or turn polls).",
        "",
        "50-task BIRD mini-dev smoke subset; `best_of_n` coordination.",
        "",
    ]

    by_model = data.get("by_model", {})
    recs = data.get("recommendations", {})

    for model in sorted(by_model):
        entry = by_model[model]
        label = MODEL_LABELS.get(model, model)
        scenarios = entry.get("scenarios", [])
        best = entry.get("best", {})
        t0 = entry.get("t0", {})

        lines.extend([f"## {label}", ""])
        lines.extend(
            [
                "| Scenario | EX % | Redundancy % | Overhead × | Tokens | Δ tok vs t0 | Δ EX vs t0 |",
                "|----------|-------:|-------------:|-----------:|-------:|------------:|-----------:|",
            ]
        )
        for s in scenarios:
            sc = s.get("scenario", "—")
            d = compare_row_local(t0, s) if sc != "t0" else {}
            tok_d = _fmt_delta(d.get("token_delta_pct")) if sc != "t0" else "—"
            ex_d = f"{d.get('ex_delta_pp', 0):+.0f}pp" if sc != "t0" else "—"
            overhead = s.get("avg_token_overhead_ratio")
            oh = f"{overhead:.2f}" if overhead is not None else "—"
            lines.append(
                f"| {sc} | {s.get('ex_accuracy_pct', 0):.1f} | "
                f"{s.get('avg_explore_redundancy_pct', 0):.1f} | {oh} | "
                f"{s.get('total_tokens', 0):,} | {tok_d} | {ex_d} |"
            )
        lines.append("")

        best_sc = best.get("scenario", "—")
        lines.append(
            f"**Best on subset:** `{best_sc}` — EX **{best.get('ex_accuracy_pct')}%**, "
            f"{best.get('total_tokens', 0):,} tokens, "
            f"redundancy {best.get('avg_explore_redundancy_pct')}%."
        )
        lines.append("")

        p2 = entry.get("p2_full_stack_prune")
        vs_p2 = entry.get("best_vs_p2_prune")
        if p2 and vs_p2:
            lines.extend(
                [
                    f"**Best schedule vs P2 full stack+prune:** EX {vs_p2.get('ex_delta_pp', 0):+.0f} pp, "
                    f"tokens {_fmt_delta(vs_p2.get('token_delta_pct'))}.",
                    "",
                    f"| | P2+prune | Best schedule (`{best_sc}`) |",
                    f"|---|--:|--:|",
                    f"| EX % | {p2.get('ex_accuracy_pct')} | {best.get('ex_accuracy_pct')} |",
                    f"| Tokens | {p2.get('total_tokens', 0):,} | {best.get('total_tokens', 0):,} |",
                    f"| Redundancy % | {p2.get('avg_explore_redundancy_pct')} | "
                    f"{best.get('avg_explore_redundancy_pct')} |",
                    "",
                ]
            )

        model_recs = recs.get(model, {})
        lines.append("### Recommendations vs t0")
        lines.append("")
        for sc in SCHEDULE_SCENARIOS:
            r = entry.get("recommendations", {}).get(sc)
            if not r:
                continue
            lines.append(
                f"- **{sc}:** {_rec_label(r.get('recommendation', 'mixed'))} — {r.get('reason', '')}"
            )
        lines.append("")

    lines.extend(["## Cross-model summary", ""])
    lines.append("| Model | Best scenario | EX % | Tokens | vs t0 EX | vs t0 tokens |")
    lines.append("|-------|---------------|-----:|-------:|---------:|-------------:|")
    for model in sorted(by_model):
        entry = by_model[model]
        best = entry.get("best", {})
        t0 = entry.get("t0", {})
        d = compare_row_local(t0, best)
        label = MODEL_LABELS.get(model, model)
        lines.append(
            f"| {label} | {best.get('scenario', '—')} | {best.get('ex_accuracy_pct', '—')} | "
            f"{best.get('total_tokens', 0):,} | {d.get('ex_delta_pp', 0):+.0f}pp | "
            f"{_fmt_delta(d.get('token_delta_pct'))} |"
        )
    lines.append("")

    return "\n".join(lines)


def compare_row_local(baseline: dict[str, Any], variant: dict[str, Any]) -> dict[str, Any]:
    from src.coord.schedule_analysis import compare_row

    return compare_row(baseline, variant)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--batch-dir", type=Path, default=REPO_ROOT / "runs" / "batches")
    parser.add_argument("--sweep-id", type=str, default=None)
    parser.add_argument("--replicas", type=int, default=10)
    parser.add_argument("--out-dir", type=Path, default=REPO_ROOT / "runs" / "reports")
    parser.add_argument("--report-id", type=str, default="schedule_sweep")
    args = parser.parse_args()

    data = build_schedule_comparisons(
        args.batch_dir.resolve(),
        sweep_id=args.sweep_id,
        n_replicas=args.replicas,
    )
    if not data.get("by_model"):
        print("No schedule sweep batches found.", file=sys.stderr)
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
