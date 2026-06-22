"""Tests for P2 analysis and Chapter 5 draft."""

from __future__ import annotations

from pathlib import Path

from src.coord.chapter5_draft import generate_chapter5_markdown
from src.coord.p2_analysis import build_p2_comparisons, load_comparisons_by_replica_counts, p2_batch_summary


REPO = Path(__file__).resolve().parents[1]


def test_p2_batch_summary_discovery_fields() -> None:
    data = {
        "batch_id": "test",
        "model_key": "gpt-4o-mini",
        "ex_accuracy_pct": 60.0,
        "avg_explore_redundancy_pct": 50.0,
        "avg_token_overhead_ratio": 3.0,
        "avg_discovery_fragments": 12.0,
        "rows": [
            {"discovery_publishes": 5, "discovery_fragments": 3, "discovery_injections": 2},
            {"discovery_publishes": 7, "discovery_fragments": 4, "discovery_injections": 3},
        ],
    }
    summary = p2_batch_summary(data)
    assert summary["total_discovery_publishes"] == 12
    assert summary["total_discovery_fragments"] == 7
    assert summary["avg_discovery_injections_per_task"] == 2.5


def test_load_p2_comparisons() -> None:
    batch_dir = REPO / "runs" / "batches"
    if not batch_dir.is_dir():
        return
    comparisons = load_comparisons_by_replica_counts(batch_dir, replica_counts=[25])
    if not comparisons:
        return
    assert 25 in comparisons
    assert len(comparisons[25]) >= 1


def test_generate_chapter5_markdown() -> None:
    batch_dir = REPO / "runs" / "batches"
    if not batch_dir.is_dir():
        return
    comparisons = load_comparisons_by_replica_counts(batch_dir, replica_counts=[10, 25])
    if not comparisons:
        return
    md = generate_chapter5_markdown(comparisons)
    assert "# Chapter 5:" in md
    assert "P2_subexpr_propagation" in md
    assert "discovery board" in md.lower()


def test_find_p2_excludes_early_stop() -> None:
    batch_dir = REPO / "runs" / "batches"
    if not batch_dir.is_dir():
        return
    from src.coord.p2_analysis import find_p2_batch

    path = find_p2_batch(batch_dir, "gpt-4o-mini", 10, batch_id="p2_r10_bo")
    if path is None:
        return
    assert "early_stop" not in path.name


def test_build_p2_comparisons_pair() -> None:
    batch_dir = REPO / "runs" / "batches"
    if not batch_dir.is_dir():
        return
    pairs = build_p2_comparisons(
        batch_dir, models=["gpt-4o-mini"], n_replicas=25, p2_batch_id="p2_r25_bo"
    )
    if not pairs:
        return
    p0, p2 = pairs[0]
    assert p2["discovery_board"] is True
