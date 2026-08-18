"""Tests for heterogeneous ensemble analysis (no API calls)."""

from __future__ import annotations

import json
from pathlib import Path

from src.coord.model_ensemble_analysis import summarize_ensemble


def test_summarize_ensemble_counts_partial_and_solo(tmp_path: Path) -> None:
    rows = [
        {
            "question_id": 1,
            "db_id": "a",
            "difficulty": "simple",
            "ensemble_ex": 1,
            "chosen_model_key": "gemini-2.5-flash",
            "per_model_ex": {
                "gpt-4o-mini": 0,
                "gemini-2.5-flash": 1,
                "deepseek-v3.2": 0,
            },
            "n_correct": 1,
            "correct_models": ["gemini-2.5-flash"],
        },
        {
            "question_id": 2,
            "db_id": "a",
            "difficulty": "moderate",
            "ensemble_ex": 1,
            "chosen_model_key": "gpt-4o-mini",
            "per_model_ex": {
                "gpt-4o-mini": 1,
                "gemini-2.5-flash": 1,
                "deepseek-v3.2": 0,
            },
            "n_correct": 2,
            "correct_models": ["gpt-4o-mini", "gemini-2.5-flash"],
        },
        {
            "question_id": 3,
            "db_id": "b",
            "difficulty": "challenging",
            "ensemble_ex": 0,
            "chosen_model_key": "gpt-4o-mini",
            "per_model_ex": {
                "gpt-4o-mini": 0,
                "gemini-2.5-flash": 0,
                "deepseek-v3.2": 0,
            },
            "n_correct": 0,
            "correct_models": [],
        },
    ]
    batch = {
        "batch_id": "toy",
        "models": ["gpt-4o-mini", "gemini-2.5-flash", "deepseek-v3.2"],
        "rows": rows,
        "total_prompt_tokens": 10,
        "total_completion_tokens": 2,
        "avg_token_overhead_ratio": 3.0,
        "avg_explore_redundancy_pct": 0.0,
        "api_failure_count": 0,
    }
    s = summarize_ensemble(batch)
    assert s["ensemble_ex"] == 2
    assert s["partial_count"] == 2
    assert s["solo_wins"]["gemini-2.5-flash"] == 1
    assert s["pair_wins"]["gpt-4o-mini+gemini-2.5-flash"] == 1
    assert s["best_single_model"] == "gemini-2.5-flash"
    assert s["lift_vs_best_single_pp"] == round(100.0 * (2 - 2) / 3, 1)

    # also exercise JSON serialisation shape used by the report writer
    out = tmp_path / "r.json"
    out.write_text(json.dumps({"summary": s}), encoding="utf-8")
    assert out.exists()
