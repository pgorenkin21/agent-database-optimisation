"""Tests for early-stop vs P0 comparison script."""

from __future__ import annotations

import json
from pathlib import Path

from scripts.compare_early_stop import _batch_summary, format_comparison_markdown


def test_batch_summary_includes_early_stop_fields(tmp_path: Path) -> None:
    data = {
        "batch_id": "test",
        "model_key": "gpt-4o-mini",
        "policy": "best_of_n",
        "n_replicas": 10,
        "early_stop": True,
        "ex_accuracy_pct": 60.0,
        "avg_explore_redundancy_pct": 70.0,
        "avg_token_overhead_ratio": 5.0,
        "rows": [
            {
                "total_prompt_tokens": 100,
                "total_completion_tokens": 10,
                "early_stop_triggered": True,
                "replicas_cancelled": 8,
                "explore_redundancy_pct": 50,
            },
            {
                "total_prompt_tokens": 200,
                "total_completion_tokens": 20,
                "early_stop_triggered": False,
                "replicas_cancelled": 0,
                "explore_redundancy_pct": 80,
            },
        ],
    }
    summary = _batch_summary(data)
    assert summary["early_stop_triggered_count"] == 1
    assert summary["total_tokens"] == 330
    assert summary["avg_replicas_cancelled"] == 4.0


def test_format_comparison_markdown() -> None:
    p0 = {
        "path": "/p0.json",
        "model_key": "gpt-4o-mini",
        "ex_accuracy_pct": 58.0,
        "avg_explore_redundancy_pct": 78.0,
        "avg_token_overhead_ratio": 10.0,
        "total_tokens": 1000,
        "task_count": 50,
    }
    es = {
        "path": "/es.json",
        "model_key": "gpt-4o-mini",
        "ex_accuracy_pct": 58.0,
        "avg_explore_redundancy_pct": 75.0,
        "avg_token_overhead_ratio": 9.0,
        "total_tokens": 900,
        "task_count": 50,
        "early_stop_triggered_count": 30,
        "avg_replicas_cancelled": 7.5,
        "avg_tokens_per_task_triggered": 100,
        "avg_tokens_per_task_not_triggered": 200,
    }
    md = format_comparison_markdown([(p0, es)])
    assert "GPT-4o mini" in md
    assert "-10.0%" in md
