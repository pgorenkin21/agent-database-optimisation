"""Tests for schema pruning analysis loaders."""

from __future__ import annotations

from pathlib import Path

import pytest

from src.coord.schema_pruning_analysis import (
    build_full500_flip_summaries,
    build_full500_isolated_comparisons,
    find_full500_isolated_prune_batch,
    find_full500_p0_batch,
    gold_recall_miss_ids,
    load_offline_full500_reports,
    load_offline_reports,
    offline_summary_by_database,
    task_flip_counts,
)

REPO_ROOT = Path(__file__).resolve().parents[1]
REPORTS_DIR = REPO_ROOT / "runs" / "reports"
BATCH_DIR = REPO_ROOT / "runs" / "batches"


@pytest.fixture
def reports_dir() -> Path:
    if not (REPORTS_DIR / "schema_pruning.json").exists():
        pytest.skip("Offline schema pruning report not generated")
    return REPORTS_DIR


def test_load_offline_reports(reports_dir: Path) -> None:
    reports = load_offline_reports(reports_dir)
    assert "keyword" in reports
    assert reports["keyword"]["full_gold_recall_pct"] == 100.0


def test_offline_summary_by_database(reports_dir: Path) -> None:
    reports = load_offline_reports(reports_dir)
    hybrid = reports.get("hybrid") or reports["keyword"]
    by_db = offline_summary_by_database(hybrid)
    assert "debit_card_specializing" in by_db
    assert "student_club" in by_db
    assert by_db["student_club"]["avg_reduction_pct"] > by_db["debit_card_specializing"]["avg_reduction_pct"]


def test_load_offline_full500_reports() -> None:
    if not (REPORTS_DIR / "schema_pruning_full500_hybrid.json").exists():
        pytest.skip("Full-500 offline prune report not generated")
    reports = load_offline_full500_reports(REPORTS_DIR)
    assert "hybrid" in reports
    assert reports["hybrid"]["task_count"] == 500
    assert reports["hybrid"]["full_gold_recall_pct"] < 100.0


def test_find_full500_batches() -> None:
    model = "gpt-4o-mini"
    p0 = find_full500_p0_batch(BATCH_DIR, model)
    prune = find_full500_isolated_prune_batch(BATCH_DIR, model)
    if p0 is None or prune is None:
        pytest.skip("Full-500 P0 or prune batch missing")
    assert p0.name.startswith("parallel_baseline_full500_r3_")
    assert "schema_prune_iso_full500_r3" in prune.name


def test_build_full500_isolated_comparisons() -> None:
    comps = build_full500_isolated_comparisons(BATCH_DIR)
    if not comps:
        pytest.skip("Full-500 isolated comparisons unavailable")
    assert len(comps) == 3
    for model, (p0, sp) in comps.items():
        assert p0["task_count"] == 500
        assert sp["task_count"] == 500
        assert sp["schema_pruning"] is True
        assert p0["model_key"] == model


def test_task_flip_counts_and_full500_flips() -> None:
    if not (REPORTS_DIR / "schema_pruning_full500_hybrid.json").exists():
        pytest.skip("Full-500 offline prune report not generated")
    offline = load_offline_full500_reports(REPORTS_DIR)["hybrid"]
    miss = gold_recall_miss_ids(offline)
    assert len(miss) > 0

    toy_p0 = {
        "rows": [
            {"question_id": 1, "ex_correct": 1},
            {"question_id": 2, "ex_correct": 0},
            {"question_id": 3, "ex_correct": 1},
        ]
    }
    toy_pr = {
        "rows": [
            {"question_id": 1, "ex_correct": 0},
            {"question_id": 2, "ex_correct": 1},
            {"question_id": 3, "ex_correct": 1},
        ]
    }
    flips = task_flip_counts(toy_p0, toy_pr, miss_question_ids={1})
    assert flips == {"gained": 1, "lost": 1, "lost_on_miss": 1, "net": 0}

    real = build_full500_flip_summaries(BATCH_DIR, offline)
    if not real:
        pytest.skip("Full-500 flip summaries unavailable")
    assert "gpt-4o-mini" in real
    assert real["gpt-4o-mini"]["gained"] + real["gpt-4o-mini"]["lost"] > 0
