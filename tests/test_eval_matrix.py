"""Eval matrix orchestrator unit tests (no API calls)."""

from __future__ import annotations

from pathlib import Path

from scripts.run_eval_matrix import VARIATIONS, _build_jobs

REPO_ROOT = Path(__file__).resolve().parents[1]


def test_build_jobs_single_and_parallel() -> None:
    out = Path("/tmp/matrix_test")
    jobs = _build_jobs(
        matrix_id="matrix123",
        models=["gpt-4o-mini", "gemini-2.5-flash"],
        variations=["single", "parallel"],
        out_dir=out,
        replicas=3,
        policy="best_of_n",
        config=None,
        limit=10,
        subset_file=None,
        inter_task_delay=None,
        python="/usr/bin/python3",
    )
    assert len(jobs) == 4
    variations = {j.variation for j in jobs}
    assert variations == set(VARIATIONS)
    single = [j for j in jobs if j.variation == "single"]
    assert single[0].json_path.name.startswith("batch_matrix123_single_")
    parallel = [j for j in jobs if j.variation == "parallel"]
    assert parallel[0].json_path.name.startswith("parallel_matrix123_parallel_")
    script_idx = parallel[0].cmd.index(str(REPO_ROOT / "scripts" / "run_parallel_batch.py"))
    script_tail = parallel[0].cmd[script_idx:]
    assert "--limit" in script_tail
    assert "--replicas" in script_tail
    assert "3" in script_tail
