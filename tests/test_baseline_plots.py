"""Tests for baseline plot data loading (no figure display)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from src.coord.baseline_plots import comparison_dataframe, load_report_comparison


@pytest.fixture
def sample_report(tmp_path: Path) -> Path:
    payload = {
        "comparison": [
            {
                "n_replicas": 3,
                "model_key": "gpt-4o-mini",
                "task_count": 50,
                "ex_accuracy_pct": 58.0,
                "avg_explore_redundancy_pct": 50.9,
                "avg_subexpr_overlap_pct": 89.2,
                "avg_token_overhead_ratio": 3.07,
                "avg_wall_clock_ms": 6064.0,
            },
            {
                "n_replicas": 10,
                "model_key": "gpt-4o-mini",
                "task_count": 50,
                "ex_accuracy_pct": 58.0,
                "api_failure_count": 0,
                "ex_accuracy_excluding_api_errors_pct": 58.0,
                "avg_explore_redundancy_pct": 78.5,
                "avg_subexpr_overlap_pct": 93.7,
                "avg_token_overhead_ratio": 10.53,
                "avg_wall_clock_ms": 12635.0,
            },
        ]
    }
    path = tmp_path / "baseline_test.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


def test_load_report_comparison(sample_report: Path) -> None:
    rows = load_report_comparison(sample_report)
    assert len(rows) == 2
    assert rows[0]["n_replicas"] == 3


def test_comparison_dataframe(sample_report: Path) -> None:
    df = comparison_dataframe([sample_report])
    assert len(df) == 2
    assert "model_label" in df.columns
    assert df.iloc[0]["avg_wall_clock_s"] == pytest.approx(6.064)
