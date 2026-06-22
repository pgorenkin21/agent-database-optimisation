"""Tests for P3 semantic store analysis."""

from __future__ import annotations

from pathlib import Path

from src.coord.p3_analysis import (
    P3_BATCH_IDS,
    build_p3_vs_full_stack_prune,
    find_p3_batch,
    p3_batch_summary,
    recommend_p3_vs_p2,
)

REPO = Path(__file__).resolve().parents[1]


def test_p3_batch_summary() -> None:
    data = {
        "semantic_store": True,
        "schema_pruning": True,
        "schema_pruning_mode": "hybrid",
        "shared_cache": True,
        "early_stop": True,
        "avg_cache_hit_rate_pct": 60.0,
        "ex_accuracy_pct": 70.0,
        "rows": [
            {
                "semantic_publishes": 2,
                "semantic_facts_added": 5,
                "semantic_injections": 3,
                "semantic_injected_chars": 400,
            }
        ],
    }
    s = p3_batch_summary(data)
    assert s["policy_label"] == "P3_semantic"
    assert s["avg_semantic_injections_per_task"] == 3.0


def test_find_p3_batch() -> None:
    batch_dir = REPO / "runs" / "batches"
    if not batch_dir.is_dir():
        return
    path = find_p3_batch(
        batch_dir, "gemini-2.5-flash", 10, batch_id=P3_BATCH_IDS[10]
    )
    assert path is not None
    assert "p3_semantic" in path.name


def test_build_p3_vs_full_stack_prune_smoke() -> None:
    batch_dir = REPO / "runs" / "batches"
    if not batch_dir.is_dir():
        return
    pairs = build_p3_vs_full_stack_prune(
        batch_dir,
        models=["gemini-2.5-flash", "gpt-4o-mini", "deepseek-v3.2"],
        n_replicas=10,
        p3_batch_id=P3_BATCH_IDS[10],
    )
    assert len(pairs) == 3


def test_recommend_p3_gpt_adopt() -> None:
    rec, _ = recommend_p3_vs_p2(
        {"ex_delta_pp": 4.0, "token_delta_pct": -6.5}
    )
    assert rec == "adopt"


def test_recommend_p3_deepseek_avoid() -> None:
    rec, _ = recommend_p3_vs_p2(
        {"ex_delta_pp": -4.0, "token_delta_pct": 42.5}
    )
    assert rec == "avoid"
