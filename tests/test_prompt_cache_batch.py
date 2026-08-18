"""Tests for prompt-cache batch wiring: cached-token aggregation + comparison."""

from __future__ import annotations

import importlib.util
from dataclasses import dataclass
from pathlib import Path

from src.coord.redundancy import compute_redundancy

REPO_ROOT = Path(__file__).resolve().parents[1]


@dataclass
class _FakeReplica:
    total_prompt_tokens: int
    total_completion_tokens: int
    ex_correct: int
    trace_path: Path
    total_cached_prompt_tokens: int = 0


def _load_compare_module():
    spec = importlib.util.spec_from_file_location(
        "compare_prompt_cache", REPO_ROOT / "scripts" / "compare_prompt_cache.py"
    )
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


def test_redundancy_aggregates_cached_tokens():
    missing = REPO_ROOT / "runs" / "_does_not_exist.jsonl"
    replicas = [
        _FakeReplica(1000, 200, 1, missing, total_cached_prompt_tokens=600),
        _FakeReplica(800, 150, 0, missing, total_cached_prompt_tokens=400),
    ]
    red = compute_redundancy(replicas)
    assert red.total_prompt_tokens == 1800
    assert red.total_cached_prompt_tokens == 1000
    assert round(red.cached_prompt_pct, 2) == round(100.0 * 1000 / 1800, 2)
    d = red.to_dict()
    assert d["total_cached_prompt_tokens"] == 1000
    assert "cached_prompt_pct" in d


def test_redundancy_defaults_cached_to_zero_for_baseline_replicas():
    """Replicas without a cached split (baseline AgentRunResult) report 0."""

    @dataclass
    class _Baseline:
        total_prompt_tokens: int
        total_completion_tokens: int
        ex_correct: int
        trace_path: Path

    missing = REPO_ROOT / "runs" / "_does_not_exist.jsonl"
    red = compute_redundancy([_Baseline(500, 100, 1, missing)])
    assert red.total_cached_prompt_tokens == 0
    assert red.cached_prompt_pct == 0.0


def test_compare_effective_input_and_ex_delta():
    compare_mod = _load_compare_module()
    baseline = {
        "rows": [
            {"question_id": 1, "ex_correct": 1, "total_prompt_tokens": 1000, "total_completion_tokens": 100},
            {"question_id": 2, "ex_correct": 0, "total_prompt_tokens": 1000, "total_completion_tokens": 100},
        ]
    }
    cached = {
        "rows": [
            {"question_id": 1, "ex_correct": 1, "total_prompt_tokens": 1000,
             "total_completion_tokens": 100, "total_cached_prompt_tokens": 800},
            {"question_id": 2, "ex_correct": 0, "total_prompt_tokens": 1000,
             "total_completion_tokens": 100, "total_cached_prompt_tokens": 800},
        ]
    }
    summary = compare_mod.compare(baseline, cached, cache_discount=0.5)
    assert summary["matched_tasks"] == 2
    # Effective input = (2000 - 1600) + 1600*0.5 = 400 + 800 = 1200 vs baseline 2000.
    assert summary["cached"]["effective_input_tokens"] == 1200
    assert summary["deltas"]["effective_input_token_pct"] == -40.0
    assert summary["deltas"]["ex_pp"] == 0.0  # accuracy-neutral
    assert summary["cached"]["cached_prompt_pct"] == 80.0
    # Trajectory-controlled: (2000 - 1200) / 2000 = 40% within-run saving.
    assert summary["cached"]["within_run_input_saving_pct"] == 40.0


def test_compare_skips_errored_tasks():
    compare_mod = _load_compare_module()
    baseline = {"rows": [{"question_id": 1, "ex_correct": 1, "total_prompt_tokens": 500, "total_completion_tokens": 50}]}
    cached = {"rows": [{"question_id": 1, "ex_correct": 0, "total_prompt_tokens": 0,
                        "total_completion_tokens": 0, "total_cached_prompt_tokens": 0, "error": "API timeout"}]}
    summary = compare_mod.compare(baseline, cached, cache_discount=0.5)
    assert summary["matched_tasks"] == 0
