"""Tests for thesis synthesis analysis."""

from __future__ import annotations

from src.coord.synthesis_analysis import (
    BEST_SCHEDULE_SCENARIO,
    SCHED_P2_GEMINI_BATCH_ID,
    build_synthesis,
    recommend_stack,
)


def test_best_schedule_scenarios_defined() -> None:
    assert BEST_SCHEDULE_SCENARIO["gemini-2.5-flash"] == "t03_stag2s"
    assert BEST_SCHEDULE_SCENARIO["deepseek-v3.2"] == "ladder"


def test_recommend_gemini_prefers_schedule() -> None:
    stacks = {
        "p2_prune": {"ex_accuracy_pct": 76.0, "total_tokens": 1_124_009},
        "best_schedule": {
            "ex_accuracy_pct": 82.0,
            "total_tokens": 483_807,
            "scenario": "t03_stag2s",
        },
        "sched_p2_gemini": {"ex_accuracy_pct": 80.0, "total_tokens": 489_040},
    }
    rec = recommend_stack("gemini-2.5-flash", stacks)
    assert rec["recommended_role"] == "best_schedule"
    assert "omit P2" in rec["rationale"] or "drops EX" in rec["rationale"]


def test_recommend_gpt_prefers_p3() -> None:
    stacks = {
        "p2_prune": {"ex_accuracy_pct": 56.0, "total_tokens": 1_847_079},
        "p3_only": {"ex_accuracy_pct": 60.0, "total_tokens": 1_726_234},
        "best_schedule": {"ex_accuracy_pct": 64.0, "total_tokens": 2_262_297, "scenario": "t03_stag2s"},
    }
    rec = recommend_stack("gpt-4o-mini", stacks)
    assert rec["recommended_role"] == "p3_only"


def test_recommend_deepseek_prefers_p2_prune() -> None:
    stacks = {
        "p2_prune": {"ex_accuracy_pct": 64.0, "total_tokens": 5_251_285},
        "p3_only": {"ex_accuracy_pct": 60.0, "total_tokens": 7_482_194},
        "best_schedule": {
            "ex_accuracy_pct": 68.0,
            "total_tokens": 6_941_153,
            "scenario": "ladder",
        },
    }
    rec = recommend_stack("deepseek-v3.2", stacks)
    assert rec["recommended_role"] == "p2_prune"


def test_build_synthesis_from_batches() -> None:
    from pathlib import Path

    root = Path(__file__).resolve().parents[1]
    batch_dir = root / "runs" / "batches"
    if not batch_dir.is_dir():
        return
    data = build_synthesis(batch_dir)
    assert data.get("by_model")
    gem = data["by_model"].get("gemini-2.5-flash", {})
    assert gem.get("stacks")
    followup = data.get("sched_p2_gemini_followup")
    if followup:
        assert followup["ex_delta_pp"] == -2.0
    assert SCHED_P2_GEMINI_BATCH_ID.startswith("sched_p2")
