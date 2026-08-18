#!/usr/bin/env python3
"""Merge a repair parallel-batch into the original full batch by question_id."""

from __future__ import annotations

import argparse
import csv
import json
import shutil
from datetime import datetime, timezone
from pathlib import Path

from src.coord.baseline_analysis import batch_ex_accuracy_stats
from src.coord.interaction_metrics import batch_interaction_summary


def _recompute(payload: dict) -> dict:
    rows = payload["rows"]
    ex_stats = batch_ex_accuracy_stats(rows)
    interaction_stats = batch_interaction_summary(rows)
    payload.update(
        {
            "total_prompt_tokens": sum(r.get("total_prompt_tokens") or 0 for r in rows),
            "total_completion_tokens": sum(r.get("total_completion_tokens") or 0 for r in rows),
            "total_cached_prompt_tokens": sum(
                r.get("total_cached_prompt_tokens") or 0 for r in rows
            ),
            "batch_cached_prompt_pct": (
                round(
                    100.0
                    * sum(r.get("total_cached_prompt_tokens") or 0 for r in rows)
                    / sum(r.get("total_prompt_tokens") or 0 for r in rows),
                    2,
                )
                if sum(r.get("total_prompt_tokens") or 0 for r in rows) > 0
                else 0.0
            ),
            "task_count": len(rows),
            "ex_accuracy_pct": ex_stats["ex_accuracy_pct"],
            "api_failure_count": ex_stats["api_failure_count"],
            "completed_task_count": ex_stats["completed_task_count"],
            "ex_accuracy_excluding_api_errors_pct": ex_stats[
                "ex_accuracy_excluding_api_errors_pct"
            ],
            "avg_token_overhead_ratio": (
                round(
                    sum(
                        r["token_overhead_ratio"]
                        for r in rows
                        if r.get("token_overhead_ratio") is not None
                    )
                    / sum(1 for r in rows if r.get("token_overhead_ratio") is not None),
                    3,
                )
                if any(r.get("token_overhead_ratio") is not None for r in rows)
                else None
            ),
            "avg_explore_redundancy_pct": (
                round(sum(r.get("explore_redundancy_pct") or 0 for r in rows) / len(rows), 2)
                if rows
                else 0
            ),
            **interaction_stats,
            "repaired_at": datetime.now(timezone.utc).isoformat(),
        }
    )
    return payload


def merge(original: Path, repair: Path, backup_dir: Path) -> None:
    orig = json.loads(original.read_text(encoding="utf-8"))
    rep = json.loads(repair.read_text(encoding="utf-8"))
    if not isinstance(orig, dict) or "rows" not in orig:
        raise SystemExit(f"invalid original batch: {original}")
    if not isinstance(rep, dict) or "rows" not in rep:
        raise SystemExit(f"invalid repair batch: {repair}")

    before_fail = sum(1 for r in orig["rows"] if r.get("error"))
    order = [int(r["question_id"]) for r in orig["rows"]]
    by_qid = {int(r["question_id"]): r for r in orig["rows"]}
    replaced = []
    still_failed = []
    for r in rep["rows"]:
        qid = int(r["question_id"])
        if qid not in by_qid:
            raise SystemExit(f"repair qid={qid} not in original batch")
        by_qid[qid] = r
        replaced.append(qid)
        if r.get("error"):
            still_failed.append(qid)

    # Preserve original row order
    orig["rows"] = [by_qid[qid] for qid in order]
    _recompute(orig)

    backup_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    backup = backup_dir / f"{original.stem}.pre_repair_{stamp}.json"
    shutil.copy2(original, backup)

    original.write_text(json.dumps(orig, indent=2), encoding="utf-8")
    csv_path = original.with_suffix(".csv")
    if orig["rows"]:
        with csv_path.open("w", encoding="utf-8", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=list(orig["rows"][0].keys()))
            writer.writeheader()
            writer.writerows(orig["rows"])

    print(
        f"merged {len(replaced)} rows into {original.name}: "
        f"api_fail {before_fail} -> {orig['api_failure_count']}, "
        f"EX {orig['ex_accuracy_pct']}% "
        f"(excl {orig['ex_accuracy_excluding_api_errors_pct']}%), "
        f"still_failed={still_failed or 'none'}, backup={backup.name}"
    )


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--original", type=Path, required=True)
    ap.add_argument("--repair", type=Path, required=True)
    ap.add_argument("--backup-dir", type=Path, required=True)
    args = ap.parse_args()
    merge(args.original, args.repair, args.backup_dir)


if __name__ == "__main__":
    main()
