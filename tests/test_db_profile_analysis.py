"""Tests for db-profile explore-attribution analysis (Chapter 12)."""

from __future__ import annotations

import json
from pathlib import Path

from src.coord.db_profile_analysis import (
    EXPLORE_JOIN,
    EXPLORE_OTHER,
    EXPLORE_VALUE_DOMAIN,
    batch_explore_summary,
    classify_explore_sql,
    comparison_deltas,
    explore_metrics_from_coord_trace,
    explore_metrics_from_trace,
)


# --------------------------------------------------------------------------- #
# classify_explore_sql
# --------------------------------------------------------------------------- #


def test_classify_join() -> None:
    assert (
        classify_explore_sql(
            "SELECT * FROM orders o JOIN customers c ON o.cid = c.id"
        )
        == EXPLORE_JOIN
    )


def test_classify_value_domain() -> None:
    assert classify_explore_sql("SELECT DISTINCT status FROM orders") == EXPLORE_VALUE_DOMAIN
    assert (
        classify_explore_sql("SELECT segment, COUNT(*) FROM customers GROUP BY segment")
        == EXPLORE_VALUE_DOMAIN
    )


def test_classify_other() -> None:
    assert classify_explore_sql("SELECT * FROM orders LIMIT 5") == EXPLORE_OTHER
    assert classify_explore_sql("SELECT COUNT(*) FROM orders") == EXPLORE_OTHER


def test_classify_unparseable_is_other() -> None:
    assert classify_explore_sql("this is not sql ;;;") == EXPLORE_OTHER
    assert classify_explore_sql("") == EXPLORE_OTHER


# --------------------------------------------------------------------------- #
# trace-level counting
# --------------------------------------------------------------------------- #


def _write_trace(path: Path, events: list[dict]) -> None:
    path.write_text(
        "\n".join(json.dumps(e) for e in events) + "\n", encoding="utf-8"
    )


def test_explore_metrics_from_trace_counts_and_classifies(tmp_path: Path) -> None:
    trace = tmp_path / "replica.jsonl"
    _write_trace(
        trace,
        [
            {"event": "sql_execute", "sql_role": "explore", "sql_raw": "SELECT DISTINCT s FROM t"},
            {"event": "sql_execute", "sql_role": "explore", "sql_raw": "SELECT * FROM a JOIN b ON a.x=b.x"},
            {"event": "sql_execute", "sql_role": "explore", "sql_raw": "SELECT * FROM t LIMIT 3"},
            # final submit must NOT count as an explore
            {"event": "sql_execute", "sql_role": "final", "sql_raw": "SELECT DISTINCT s FROM t"},
            {"event": "llm_turn", "sql_role": "explore"},  # wrong event type
        ],
    )
    m = explore_metrics_from_trace(trace)
    assert m.explore_total == 3
    assert m.value_domain_explores == 1
    assert m.join_explores == 1
    assert m.other_explores == 1


def test_explore_metrics_missing_trace_is_zero(tmp_path: Path) -> None:
    m = explore_metrics_from_trace(tmp_path / "nope.jsonl")
    assert m.explore_total == 0


def test_explore_metrics_from_coord_aggregates_replicas(tmp_path: Path) -> None:
    r1 = tmp_path / "r1.jsonl"
    r2 = tmp_path / "r2.jsonl"
    _write_trace(r1, [{"event": "sql_execute", "sql_role": "explore", "sql_raw": "SELECT DISTINCT s FROM t"}])
    _write_trace(r2, [{"event": "sql_execute", "sql_role": "explore", "sql_raw": "SELECT * FROM a JOIN b ON a.x=b.x"}])
    coord = tmp_path / "coord.jsonl"
    _write_trace(
        coord,
        [
            {"event": "replica_end", "trace_path": str(r1)},
            {"event": "replica_end", "trace_path": str(r2)},
        ],
    )
    m = explore_metrics_from_coord_trace(coord)
    assert m.explore_total == 2
    assert m.value_domain_explores == 1
    assert m.join_explores == 1


# --------------------------------------------------------------------------- #
# batch summary + deltas
# --------------------------------------------------------------------------- #


def _batch_with_two_tasks(tmp_path: Path, per_task_explores: list[str]) -> dict:
    rows = []
    for i, sql in enumerate(per_task_explores):
        r = tmp_path / f"r{i}.jsonl"
        _write_trace(r, [{"event": "sql_execute", "sql_role": "explore", "sql_raw": sql}])
        coord = tmp_path / f"coord{i}.jsonl"
        _write_trace(coord, [{"event": "replica_end", "trace_path": str(r)}])
        rows.append({"db_id": "shop", "coord_trace_path": str(coord)})
    return {"rows": rows}


def test_batch_explore_summary_means_and_by_db(tmp_path: Path) -> None:
    data = _batch_with_two_tasks(
        tmp_path, ["SELECT DISTINCT s FROM t", "SELECT * FROM a JOIN b ON a.x=b.x"]
    )
    s = batch_explore_summary(data)
    assert s["traces_found"] == 2
    assert s["mean_explore_per_task"] == 1.0
    assert s["mean_value_domain_explores_per_task"] == 0.5
    assert s["mean_join_explores_per_task"] == 0.5
    assert s["explore_by_db"]["shop"]["task_count"] == 2


def test_batch_explore_summary_handles_missing_traces(tmp_path: Path) -> None:
    data = {"rows": [{"db_id": "shop"}, {"db_id": "shop", "coord_trace_path": "/nonexistent"}]}
    s = batch_explore_summary(data)
    assert s["traces_found"] == 0
    assert s["task_count"] == 2
    assert s["mean_explore_per_task"] is None  # no coverage -> no false zero


def test_comparison_deltas_signs() -> None:
    baseline = {"ex_accuracy_pct": 60.0, "total_tokens": 1000, "mean_explore_per_task": 4.0,
                "mean_value_domain_explores_per_task": 2.0, "mean_join_explores_per_task": 1.0}
    variant = {"ex_accuracy_pct": 60.0, "total_tokens": 900, "mean_explore_per_task": 3.0,
               "mean_value_domain_explores_per_task": 1.0, "mean_join_explores_per_task": 1.0}
    d = comparison_deltas(baseline, variant)
    assert d["ex_pp"] == 0.0
    assert d["explore_per_task_delta"] == -1.0
    assert d["explore_per_task_pct"] == -25.0
    assert d["value_domain_explores_delta"] == -1.0
    assert d["join_explores_delta"] == 0.0
