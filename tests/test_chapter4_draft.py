"""Tests for P1 analysis and Chapter 4 draft."""

from __future__ import annotations

from pathlib import Path

from src.coord.chapter4_draft import generate_chapter4_markdown
from src.coord.p1_analysis import build_p1_comparisons, load_comparisons_by_replica_counts, p1_batch_summary

REPO = Path(__file__).resolve().parents[1]


def test_p1_batch_summary_cache_fields() -> None:
    data = {
        "batch_id": "test",
        "model_key": "gpt-4o-mini",
        "ex_accuracy_pct": 60.0,
        "avg_explore_redundancy_pct": 50.0,
        "avg_token_overhead_ratio": 3.0,
        "avg_cache_hit_rate_pct": 75.0,
        "rows": [
            {"cache_hits": 8, "cache_misses": 2, "total_prompt_tokens": 100, "total_completion_tokens": 10},
            {"cache_hits": 6, "cache_misses": 4, "total_prompt_tokens": 200, "total_completion_tokens": 20},
        ],
    }
    summary = p1_batch_summary(data)
    assert summary["total_cache_hits"] == 14
    assert summary["total_cache_misses"] == 6
    assert summary["batch_cache_hit_rate_pct"] == 70.0


def test_load_p1_comparisons() -> None:
    batch_dir = REPO / "runs" / "batches"
    if not batch_dir.is_dir():
        return
    comparisons = load_comparisons_by_replica_counts(batch_dir, replica_counts=[25])
    if not comparisons:
        return
    assert 25 in comparisons
    assert len(comparisons[25]) >= 1


def test_generate_chapter4_markdown() -> None:
    batch_dir = REPO / "runs" / "batches"
    if not batch_dir.is_dir():
        return
    comparisons = load_comparisons_by_replica_counts(batch_dir, replica_counts=[10, 25])
    if not comparisons:
        return
    md = generate_chapter4_markdown(comparisons)
    assert "# Chapter 4:" in md
    assert "P1_shared_cache" in md
    assert "cache hit" in md.lower()


def test_build_p1_comparisons_pair() -> None:
    batch_dir = REPO / "runs" / "batches"
    if not batch_dir.is_dir():
        return
    pairs = build_p1_comparisons(
        batch_dir, models=["gpt-4o-mini"], n_replicas=25, p1_batch_id="p1_r25_bo"
    )
    if not pairs:
        return
    p0, p1 = pairs[0]
    assert p0["early_stop"] is False
    assert p1["shared_cache"] is True
