"""Tests for P4 suppression analysis (Chapter 13)."""

from __future__ import annotations

import json
from pathlib import Path

from src.coord.explore_suppressor_analysis import (
    batch_suppression_summary,
    comparison_deltas,
    counts_from_coord_trace,
    counts_from_trace,
)


def _write(path: Path, events: list[dict]) -> None:
    path.write_text("\n".join(json.dumps(e) for e in events) + "\n", encoding="utf-8")


def test_counts_executed_and_suppressed(tmp_path: Path) -> None:
    t = tmp_path / "r.jsonl"
    _write(
        t,
        [
            {"event": "sql_execute", "sql_role": "explore", "sql_raw": "SELECT a FROM t"},
            {"event": "explore_suppressed", "sql_raw": "SELECT a FROM t GROUP BY a"},
            {"event": "sql_execute", "sql_role": "final", "sql_raw": "SELECT a FROM t"},  # ignored
        ],
    )
    c = counts_from_trace(t)
    assert c.executed_explores == 1
    assert c.suppressed == 1


def test_coord_aggregates_replicas(tmp_path: Path) -> None:
    r1, r2 = tmp_path / "r1.jsonl", tmp_path / "r2.jsonl"
    _write(r1, [{"event": "explore_suppressed", "sql_raw": "x"}])
    _write(r2, [{"event": "sql_execute", "sql_role": "explore", "sql_raw": "x"}])
    coord = tmp_path / "c.jsonl"
    _write(coord, [{"event": "replica_end", "trace_path": str(r1)},
                   {"event": "replica_end", "trace_path": str(r2)}])
    c = counts_from_coord_trace(coord)
    assert c.executed_explores == 1 and c.suppressed == 1


def test_batch_summary_rate_and_coverage(tmp_path: Path) -> None:
    # one task: 3 executed + 1 suppressed -> rate 25%
    r = tmp_path / "r.jsonl"
    _write(r, [
        {"event": "sql_execute", "sql_role": "explore", "sql_raw": "a"},
        {"event": "sql_execute", "sql_role": "explore", "sql_raw": "b"},
        {"event": "sql_execute", "sql_role": "explore", "sql_raw": "c"},
        {"event": "explore_suppressed", "sql_raw": "d"},
    ])
    coord = tmp_path / "c.jsonl"
    _write(coord, [{"event": "replica_end", "trace_path": str(r)}])
    data = {"rows": [{"coord_trace_path": str(coord)}]}
    s = batch_suppression_summary(data)
    assert s["traces_found"] == 1
    assert s["mean_executed_explores_per_task"] == 3.0
    assert s["mean_suppressed_per_task"] == 1.0
    assert s["suppression_rate_pct"] == 25.0


def test_batch_summary_no_traces_is_none(tmp_path: Path) -> None:
    s = batch_suppression_summary({"rows": [{"db_id": "x"}]})
    assert s["traces_found"] == 0
    assert s["mean_executed_explores_per_task"] is None


def test_comparison_deltas() -> None:
    base = {"ex_accuracy_pct": 60.0, "total_tokens": 1000,
            "mean_executed_explores_per_task": 4.0}
    var = {"ex_accuracy_pct": 60.0, "total_tokens": 950,
           "mean_executed_explores_per_task": 3.0,
           "mean_suppressed_per_task": 0.5, "suppression_rate_pct": 11.1}
    d = comparison_deltas(base, var)
    assert d["ex_pp"] == 0.0
    assert d["executed_explores_delta"] == -1.0
    assert d["executed_explores_pct"] == -25.0
    assert d["suppressed_per_task"] == 0.5
