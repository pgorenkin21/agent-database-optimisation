#!/usr/bin/env python3
"""Offline analysis of heuristic schema pruning on the task subset."""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from src.agent.schema import list_user_tables
from src.agent.schema_pruning import (
    build_pruned_schema_context,
    tables_mentioned_in_sql,
)
from src.bird.subset import resolve_task_subset
from src.bird.tasks import sqlite_path_for_task
from src.config import load_config


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=None)
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--subset-file", type=Path, default=None)
    parser.add_argument("--out-dir", type=Path, default=REPO_ROOT / "runs" / "reports")
    parser.add_argument("--report-id", type=str, default="schema_pruning")
    parser.add_argument(
        "--mode",
        type=str,
        default="keyword",
        choices=["keyword", "semantic", "hybrid"],
        help="Table selection mode for pruning analysis",
    )
    args = parser.parse_args()

    cfg = load_config(args.config)
    tasks = resolve_task_subset(cfg, limit=args.limit, subset_file=args.subset_file)
    if not tasks:
        print("No tasks.", file=sys.stderr)
        return 1

    rows: list[dict] = []
    for task in tasks:
        db_path = sqlite_path_for_task(task, cfg)
        all_tables = list_user_tables(db_path)
        gold_tables = tables_mentioned_in_sql(task.gold_sql, all_tables)
        pruned = build_pruned_schema_context(
            task,
            db_path,
            cfg.databases_dir,
            mode=args.mode,
            semantic_min_score=cfg.schema_pruning_semantic_min_score,
        )
        selected = set(pruned.selected_tables)
        recall = len(gold_tables & selected) / len(gold_tables) if gold_tables else 1.0
        rows.append(
            {
                "question_id": task.question_id,
                "db_id": task.db_id,
                "difficulty": task.difficulty,
                "total_tables": len(all_tables),
                "selected_tables": list(pruned.selected_tables),
                "gold_tables": sorted(gold_tables),
                "gold_table_recall": round(recall, 3),
                "full_chars": pruned.full_chars,
                "pruned_chars": pruned.pruned_chars,
                "reduction_pct": round(pruned.reduction_pct, 2),
                "pruning_applied": pruned.pruning_applied,
                "fallback_reason": pruned.fallback_reason,
                "pruning_mode": pruned.pruning_mode,
                "semantic_scores": pruned.semantic_scores,
            }
        )

    full_recall = sum(1 for r in rows if r["gold_table_recall"] == 1.0)
    payload = {
        "report_id": args.report_id,
        "pruning_mode": args.mode,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "task_count": len(rows),
        "full_gold_recall_count": full_recall,
        "full_gold_recall_pct": round(100.0 * full_recall / len(rows), 2),
        "avg_reduction_pct": round(sum(r["reduction_pct"] for r in rows) / len(rows), 2),
        "avg_selected_tables": round(
            sum(len(r["selected_tables"]) for r in rows) / len(rows), 2
        ),
        "full_schema_fallback_count": sum(
            1 for r in rows if not r.get("pruning_applied", True)
        ),
        "rows": rows,
    }

    args.out_dir.mkdir(parents=True, exist_ok=True)
    json_path = args.out_dir / f"{args.report_id}.json"
    md_path = args.out_dir / f"{args.report_id}.md"
    json_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    misses = [r for r in rows if r["gold_table_recall"] < 1.0]
    lines = [
        "# Schema pruning analysis",
        "",
        f"Generated: {payload['generated_at']}",
        "",
        "Heuristic: score tables from question+evidence keywords, expand FK neighbors, "
        "include matched column descriptions only.",
        "",
        f"- Tasks: **{len(rows)}**",
        f"- Full gold-table recall: **{payload['full_gold_recall_pct']:.1f}%** "
        f"({full_recall}/{len(rows)})",
        f"- Avg schema size reduction: **{payload['avg_reduction_pct']:.1f}%**",
        f"- Avg tables kept: **{payload['avg_selected_tables']:.1f}**",
        f"- Full-schema fallbacks: **{payload['full_schema_fallback_count']}**",
        "",
        "## Misses (gold table not in pruned schema)",
        "",
    ]
    if not misses:
        lines.append("_None on this subset._")
    else:
        lines.append("| question_id | db_id | recall | gold | selected |")
        lines.append("|------------:|-------|-------:|------|----------|")
        for r in sorted(misses, key=lambda x: x["gold_table_recall"]):
            lines.append(
                f"| {r['question_id']} | {r['db_id']} | {r['gold_table_recall']:.2f} | "
                f"{', '.join(r['gold_tables'])} | {', '.join(r['selected_tables'])} |"
            )

    md_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("\n".join(lines))
    print(f"\nWrote {json_path}")
    print(f"Wrote {md_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
