#!/usr/bin/env python3
"""Compare P0 parallel batches vs early-stop batches (apples-to-apples)."""

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


def _load_batch(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _batch_summary(data: dict[str, Any]) -> dict[str, Any]:
    rows = data.get("rows", [])
    triggered = [r for r in rows if r.get("early_stop_triggered")]
    not_triggered = [r for r in rows if not r.get("early_stop_triggered")]
    total_tokens = sum(
        r.get("total_prompt_tokens", 0) + r.get("total_completion_tokens", 0) for r in rows
    )
    avg_cancel = (
        sum(r.get("replicas_cancelled", 0) for r in rows) / len(rows) if rows else 0.0
    )
    tok_triggered = (
        sum(r.get("total_prompt_tokens", 0) + r.get("total_completion_tokens", 0) for r in triggered)
        / len(triggered)
        if triggered
        else None
    )
    tok_not = (
        sum(r.get("total_prompt_tokens", 0) + r.get("total_completion_tokens", 0) for r in not_triggered)
        / len(not_triggered)
        if not_triggered
        else None
    )
    return {
        "path": data.get("_path", ""),
        "batch_id": data.get("batch_id", ""),
        "model_key": data.get("model_key", ""),
        "policy": data.get("policy", ""),
        "n_replicas": data.get("n_replicas"),
        "early_stop": bool(data.get("early_stop", False)),
        "task_count": len(rows),
        "ex_accuracy_pct": data.get("ex_accuracy_pct"),
        "avg_explore_redundancy_pct": data.get("avg_explore_redundancy_pct"),
        "avg_token_overhead_ratio": data.get("avg_token_overhead_ratio"),
        "total_tokens": total_tokens,
        "early_stop_triggered_count": len(triggered),
        "avg_replicas_cancelled": round(avg_cancel, 2),
        "avg_tokens_per_task_triggered": round(tok_triggered) if tok_triggered is not None else None,
        "avg_tokens_per_task_not_triggered": round(tok_not) if tok_not is not None else None,
    }


def _pct_delta(baseline: float | None, variant: float | None) -> str:
    if baseline is None or variant is None or baseline == 0:
        return "—"
    delta = variant - baseline
    pct = 100.0 * delta / baseline
    sign = "+" if pct > 0 else ""
    return f"{sign}{pct:.1f}%"


def _find_p0_batch(batch_dir: Path, model: str, n_replicas: int) -> Path | None:
    pattern = f"*baseline_r{n_replicas}_{model}_r{n_replicas}_best_of_n.json"
    matches = sorted(batch_dir.glob(f"parallel_{pattern}"))
    return matches[-1] if matches else None


def _find_early_stop_batch(
    batch_dir: Path, model: str, n_replicas: int, *, batch_id: str | None
) -> Path | None:
    if batch_id:
        pattern = f"parallel_{batch_id}_{model}_r{n_replicas}_best_of_n_early_stop.json"
        matches = sorted(batch_dir.glob(pattern))
        if matches:
            return matches[-1]
    matches = sorted(
        batch_dir.glob(
            f"parallel_*_{model}_r{n_replicas}_best_of_n_early_stop.json"
        )
    )
    return matches[-1] if matches else None


def format_comparison_markdown(
    comparisons: list[tuple[dict[str, Any], dict[str, Any]]],
    *,
    title: str = "Early Stop vs P0 Comparison",
) -> str:
    ts = datetime.now(timezone.utc).isoformat()
    lines = [
        f"# {title}",
        "",
        f"Generated: {ts}",
        "",
        "Apples-to-apples: same model, replica count, and `best_of_n` policy. "
        "Only difference is `--early-stop` (P0_parallel vs P0_early_stop traces).",
        "",
    ]

    lines.extend(
        [
            "## Summary",
            "",
            "| Model | P0 EX % | ES EX % | P0 redundancy % | ES redundancy % | "
            "P0 tokens | ES tokens | Token Δ | P0 overhead | ES overhead | ES triggered |",
            "|-------|--------:|--------:|----------------:|----------------:|"
            "----------:|----------:|--------:|------------:|------------:|-------------:|",
        ]
    )

    for p0, es in comparisons:
        label = MODEL_LABELS.get(p0["model_key"], p0["model_key"])
        lines.append(
            f"| {label} | {p0['ex_accuracy_pct']:.1f} | {es['ex_accuracy_pct']:.1f} | "
            f"{p0['avg_explore_redundancy_pct']:.1f} | {es['avg_explore_redundancy_pct']:.1f} | "
            f"{p0['total_tokens']:,} | {es['total_tokens']:,} | "
            f"{_pct_delta(p0['total_tokens'], es['total_tokens'])} | "
            f"{p0['avg_token_overhead_ratio']:.2f}× | {es['avg_token_overhead_ratio']:.2f}× | "
            f"{es['early_stop_triggered_count']}/{es['task_count']} |"
        )

    lines.append("")

    for p0, es in comparisons:
        label = MODEL_LABELS.get(p0["model_key"], p0["model_key"])
        lines.extend(
            [
                f"## {label}",
                "",
                f"- P0 batch: `{Path(p0['path']).name}`",
                f"- Early stop batch: `{Path(es['path']).name}`",
                f"- Early stop triggered: **{es['early_stop_triggered_count']}/{es['task_count']}** tasks",
                f"- Avg replicas cancelled: **{es['avg_replicas_cancelled']}** per task",
                "",
            ]
        )
        if es["avg_tokens_per_task_triggered"] is not None:
            lines.append(
                f"- Avg tokens/task when triggered: **{es['avg_tokens_per_task_triggered']:,}** "
                f"(vs **{es['avg_tokens_per_task_not_triggered']:,}** when not triggered)"
            )
            lines.append("")

    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--p0",
        type=Path,
        action="append",
        default=[],
        help="P0 batch JSON (repeatable; default: auto-discover baseline_rN)",
    )
    parser.add_argument(
        "--early-stop",
        type=Path,
        action="append",
        default=[],
        dest="early_stop_paths",
        help="Early-stop batch JSON (repeatable)",
    )
    parser.add_argument("--batch-dir", type=Path, default=REPO_ROOT / "runs" / "batches")
    parser.add_argument(
        "--models",
        nargs="*",
        default=["gpt-4o-mini", "gemini-2.5-flash", "deepseek-v3.2"],
    )
    parser.add_argument("--replicas", type=int, default=10)
    parser.add_argument(
        "--early-stop-batch-id",
        type=str,
        default="earlystop_r10_bo",
        help="Batch id prefix for early-stop runs to compare",
    )
    parser.add_argument(
        "--out-dir",
        type=Path,
        default=REPO_ROOT / "runs" / "reports",
    )
    parser.add_argument("--report-id", type=str, default="early_stop_vs_p0")
    args = parser.parse_args()

    comparisons: list[tuple[dict[str, Any], dict[str, Any]]] = []

    if args.p0 and args.early_stop_paths:
        if len(args.p0) != len(args.early_stop_paths):
            print("Must provide equal --p0 and --early-stop paths", file=sys.stderr)
            return 1
        for p0_path, es_path in zip(args.p0, args.early_stop_paths, strict=True):
            p0_data = _load_batch(p0_path.resolve())
            es_data = _load_batch(es_path.resolve())
            p0_data["_path"] = str(p0_path.resolve())
            es_data["_path"] = str(es_path.resolve())
            comparisons.append((_batch_summary(p0_data), _batch_summary(es_data)))
    else:
        for model in args.models:
            p0_path = _find_p0_batch(args.batch_dir, model, args.replicas)
            es_path = _find_early_stop_batch(
                args.batch_dir, model, args.replicas, batch_id=args.early_stop_batch_id
            )
            if not p0_path:
                print(f"Missing P0 batch for {model} r={args.replicas}", file=sys.stderr)
                continue
            if not es_path:
                print(
                    f"Missing early-stop batch for {model} "
                    f"(batch-id={args.early_stop_batch_id})",
                    file=sys.stderr,
                )
                continue
            p0_data = _load_batch(p0_path)
            es_data = _load_batch(es_path)
            p0_data["_path"] = str(p0_path.resolve())
            es_data["_path"] = str(es_path.resolve())
            comparisons.append((_batch_summary(p0_data), _batch_summary(es_data)))

    if not comparisons:
        print("No comparison pairs found.", file=sys.stderr)
        return 1

    md = format_comparison_markdown(comparisons)
    args.out_dir.mkdir(parents=True, exist_ok=True)
    md_path = args.out_dir / f"{args.report_id}.md"
    json_path = args.out_dir / f"{args.report_id}.json"
    md_path.write_text(md, encoding="utf-8")
    json_path.write_text(
        json.dumps({"comparisons": [{"p0": p0, "early_stop": es} for p0, es in comparisons]}, indent=2),
        encoding="utf-8",
    )
    print(md)
    print(f"\nWrote {md_path}")
    print(f"Wrote {json_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
