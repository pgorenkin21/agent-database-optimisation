#!/usr/bin/env python3
"""Analyze P0 parallel batch runs and produce a baseline redundancy report."""

from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from src.coord.baseline_analysis import (
    analyze_parallel_batch,
    compare_replica_counts,
    format_markdown_report,
)


def _discover_batches(
    batch_dir: Path,
    *,
    sweep_id: str | None,
    model: str | None,
    replicas: list[int] | None,
) -> list[Path]:
    paths = sorted(batch_dir.glob("parallel_*.json"))
    if sweep_id:
        paths = [p for p in paths if sweep_id in p.name]
    if model:
        paths = [p for p in paths if f"_{model}_" in p.name or p.name.endswith(f"_{model}_r")]
    if replicas:
        rep_pat = re.compile(r"_r(\d+)_")
        paths = [p for p in paths if (m := rep_pat.search(p.name)) and int(m.group(1)) in replicas]
    return paths


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "batches",
        nargs="*",
        type=Path,
        help="Parallel batch JSON files (default: discover from --batch-dir)",
    )
    parser.add_argument("--batch-dir", type=Path, default=REPO_ROOT / "runs" / "batches")
    parser.add_argument(
        "--sweep-id",
        type=str,
        default=None,
        help="Filter batches whose filename contains this id (e.g. 20260610_124547_2f8250)",
    )
    parser.add_argument("--model", type=str, default=None, help="Filter by model key")
    parser.add_argument(
        "--replicas",
        type=int,
        nargs="*",
        default=None,
        help="Filter by replica counts (e.g. 3 10 25)",
    )
    parser.add_argument(
        "--out-dir",
        type=Path,
        default=REPO_ROOT / "runs" / "reports",
        help="Directory for report outputs",
    )
    parser.add_argument(
        "--report-id",
        type=str,
        default=None,
        help="Filename stem for outputs (default: baseline_<sweep-id or timestamp>)",
    )
    parser.add_argument("--title", type=str, default="Baseline Redundancy Report (P0)")
    args = parser.parse_args()

    batch_paths: list[Path]
    if args.batches:
        batch_paths = [p.resolve() for p in args.batches]
    else:
        batch_paths = _discover_batches(
            args.batch_dir.resolve(),
            sweep_id=args.sweep_id,
            model=args.model,
            replicas=args.replicas,
        )

    if not batch_paths:
        print("No parallel batch JSON files found.", file=sys.stderr)
        return 1

    reports = []
    for path in batch_paths:
        if not path.exists():
            print(f"Missing: {path}", file=sys.stderr)
            return 1
        report = analyze_parallel_batch(path)
        if not report.tasks:
            print(f"WARN: no coord traces in {path.name}", file=sys.stderr)
        reports.append(report)
        print(f"Analysed {path.name}: {len(report.tasks)} tasks, r={report.n_replicas}")

    # Deduplicate: if multiple batches for same replica count, keep latest file
    by_replicas: dict[int, object] = {}
    for report in sorted(reports, key=lambda r: r.batch_path):
        by_replicas[report.n_replicas] = report
    reports = list(by_replicas.values())

    generated_at = datetime.now(timezone.utc).isoformat()
    report_id = args.report_id or args.sweep_id or datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    args.out_dir.mkdir(parents=True, exist_ok=True)

    stem = report_id if report_id.startswith("baseline_") else f"baseline_{report_id}"
    json_path = args.out_dir / f"{stem}.json"
    md_path = args.out_dir / f"{stem}.md"

    payload = {
        "report_id": report_id,
        "generated_at": generated_at,
        "comparison": compare_replica_counts(reports),
        "batches": [r.to_dict() for r in reports],
    }
    json_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    md_path.write_text(
        format_markdown_report(reports, title=args.title, generated_at=generated_at),
        encoding="utf-8",
    )

    print()
    print(f"Wrote {json_path}")
    print(f"Wrote {md_path}")
    print()
    print("Replica comparison:")
    for row in payload["comparison"]:
        ex_excl = row.get("ex_accuracy_excluding_api_errors_pct")
        ex_excl_s = f"{ex_excl:.1f}%" if ex_excl is not None else "—"
        api_fails = int(row.get("api_failure_count", 0))
        print(
            f"  r={row['n_replicas']:2d}  tasks={row['task_count']:3d}  "
            f"EX={row['ex_accuracy_pct']:5.1f}%  EX_no_api={ex_excl_s}  api_fail={api_fails}  "
            f"explore_red={row['avg_explore_redundancy_pct']:5.1f}%  "
            f"overhead={row.get('avg_token_overhead_ratio')}"
        )

    missing = {3, 10, 25} - {r.n_replicas for r in reports}
    if missing:
        print()
        print(f"Note: replica counts not yet covered: {sorted(missing)}")
        print("Run: uv run python scripts/run_baseline_sweep.py --replicas " + " ".join(map(str, sorted(missing))))

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
