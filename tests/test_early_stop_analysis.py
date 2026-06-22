"""Tests for early-stop analysis helpers."""

from __future__ import annotations

import json
from pathlib import Path

from src.coord.early_stop_analysis import batch_summary, build_comparisons, pct_delta

REPO = Path(__file__).resolve().parents[1]


def test_batch_summary_early_stop_fields() -> None:
    data = {
        "batch_id": "test",
        "model_key": "gpt-4o-mini",
        "policy": "best_of_n",
        "n_replicas": 10,
        "early_stop": True,
        "ex_accuracy_pct": 60.0,
        "avg_explore_redundancy_pct": 77.0,
        "avg_token_overhead_ratio": 9.5,
        "rows": [
            {
                "early_stop_triggered": True,
                "replicas_cancelled": 8,
                "total_prompt_tokens": 1000,
                "total_completion_tokens": 100,
                "ex_correct": 1,
            },
            {
                "early_stop_triggered": False,
                "replicas_cancelled": 0,
                "total_prompt_tokens": 2000,
                "total_completion_tokens": 200,
                "ex_correct": 0,
            },
        ],
    }
    summary = batch_summary(data)
    assert summary["early_stop_triggered_count"] == 1
    assert summary["avg_replicas_cancelled"] == 4.0
    assert summary["total_tokens"] == 3300


def test_pct_delta() -> None:
    assert pct_delta(100, 80) == -20.0
    assert pct_delta(0, 50) is None


def test_build_comparisons_r25() -> None:
    batch_dir = REPO / "runs" / "batches"
    if not batch_dir.is_dir():
        return
    pairs = build_comparisons(
        batch_dir,
        models=["gpt-4o-mini"],
        n_replicas=25,
        early_stop_batch_id="earlystop_r25_bo",
    )
    if not pairs:
        return
    p0, es = pairs[0]
    assert p0["early_stop"] is False
    assert es["early_stop"] is True
