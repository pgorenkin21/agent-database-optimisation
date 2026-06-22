"""Tests for schedule sweep analysis."""

from __future__ import annotations

from src.coord.schedule_analysis import (
    SCHEDULE_SCENARIOS,
    compare_row,
    pick_best_schedule,
    recommend_schedule,
    scenario_from_batch_id,
    sweep_id_from_batch_id,
)


def test_scenario_from_batch_id() -> None:
    assert scenario_from_batch_id("sched_r10_bo_t0_gemini-2-5-flash") == "t0"
    assert scenario_from_batch_id("sched_r10_bo_t03_gemini-2-5-flash") == "t03"
    assert scenario_from_batch_id("sched_r10_bo_t03_stag2s_gpt-4o-mini") == "t03_stag2s"
    assert scenario_from_batch_id("sched_r10_bo_ladder_deepseek-v3-2") == "ladder"


def test_sweep_id_from_batch_id() -> None:
    assert sweep_id_from_batch_id("sched_r10_bo_t0_gpt-4o-mini") == "sched_r10_bo"


def test_pick_best_schedule_prefers_ex_then_tokens() -> None:
    scenarios = [
        {"scenario": "t0", "ex_accuracy_pct": 60.0, "total_tokens": 1000},
        {"scenario": "t03", "ex_accuracy_pct": 64.0, "total_tokens": 900},
        {"scenario": "t07", "ex_accuracy_pct": 64.0, "total_tokens": 800},
    ]
    best = pick_best_schedule(scenarios)
    assert best["scenario"] == "t07"


def test_recommend_schedule_adopt_on_token_win() -> None:
    t0 = {"ex_accuracy_pct": 60.0, "total_tokens": 1000, "avg_explore_redundancy_pct": 80.0}
    cand = {"scenario": "t03", "ex_accuracy_pct": 62.0, "total_tokens": 850, "avg_explore_redundancy_pct": 50.0}
    rec, _ = recommend_schedule(t0, cand)
    assert rec == "adopt"


def test_compare_row_deltas() -> None:
    t0 = {"model_key": "gpt", "scenario": "t0", "ex_accuracy_pct": 60.0, "total_tokens": 1000,
          "avg_explore_redundancy_pct": 80.0}
    t03 = {"model_key": "gpt", "scenario": "t03", "ex_accuracy_pct": 62.0, "total_tokens": 900,
           "avg_explore_redundancy_pct": 70.0}
    row = compare_row(t0, t03)
    assert row["ex_delta_pp"] == 2.0
    assert row["token_delta_pct"] == -10.0
    assert row["redundancy_delta_pp"] == -10.0


def test_schedule_scenarios_order() -> None:
    assert SCHEDULE_SCENARIOS.index("t03_stag2s") < SCHEDULE_SCENARIOS.index("t03")
    assert SCHEDULE_SCENARIOS.index("t03") < SCHEDULE_SCENARIOS.index("t0")
