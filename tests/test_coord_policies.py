"""Coordination policy and redundancy unit tests (no API calls)."""

from __future__ import annotations

from pathlib import Path

import pytest

from src.agent.loop import AgentRunResult
from src.coord.policies import CoordinationPolicy, ReplicaOutcome, select_replica
from src.coord.redundancy import compute_redundancy
from src.logging.trace import RunTrace


def _result(
    *,
    qid: int = 1,
    ex: int,
    turns: int,
    sql: str | None = "SELECT 1",
    prompt: int = 100,
    completion: int = 10,
    trace_path: Path | None = None,
) -> AgentRunResult:
    return AgentRunResult(
        question_id=qid,
        db_id="db",
        model_key="test",
        final_sql=sql,
        ex_correct=ex,
        turns=turns,
        trace_path=trace_path or Path("/tmp/trace.jsonl"),
        total_prompt_tokens=prompt,
        total_completion_tokens=completion,
        stop_reason="submit_sql",
    )


def test_best_of_n_prefers_correct_lowest_turns() -> None:
    outcomes = [
        ReplicaOutcome(_result(ex=0, turns=1, sql="SELECT 0")),
        ReplicaOutcome(_result(ex=1, turns=3, sql="SELECT ok slow")),
        ReplicaOutcome(_result(ex=1, turns=2, sql="SELECT ok fast")),
    ]
    chosen = select_replica(CoordinationPolicy.BEST_OF_N, outcomes)
    assert chosen.turns == 2
    assert chosen.ex_correct == 1


def test_first_success_uses_completion_order() -> None:
    outcomes = [
        ReplicaOutcome(_result(ex=0, turns=1)),
        ReplicaOutcome(_result(ex=1, turns=5)),
        ReplicaOutcome(_result(ex=1, turns=2)),
    ]
    chosen = select_replica(
        CoordinationPolicy.FIRST_SUCCESS,
        outcomes,
        completion_order=[2, 0, 1],
    )
    assert chosen.turns == 2


def test_majority_vote_picks_largest_result_bucket() -> None:
    outcomes = [
        ReplicaOutcome(_result(ex=0, turns=1), result_fingerprint="fp_a"),
        ReplicaOutcome(_result(ex=0, turns=1), result_fingerprint="fp_a"),
        ReplicaOutcome(_result(ex=1, turns=4), result_fingerprint="fp_b"),
    ]
    chosen = select_replica(CoordinationPolicy.MAJORITY_VOTE, outcomes)
    assert chosen.ex_correct == 0
    assert chosen.turns == 1


@pytest.fixture
def cfg():
    from src.config import load_config

    c = load_config()
    if not c.tasks_json.exists():
        pytest.skip("BIRD mini-dev not downloaded")
    return c


def test_redundancy_counts_duplicate_explore_sql(tmp_path: Path, cfg) -> None:
    from src.bird.tasks import load_tasks

    task = load_tasks(cfg)[0]

    def make_trace(agent_id: str, explore_sql: list[str]) -> Path:
        trace = RunTrace(
            cfg=cfg,
            question_id=task.question_id,
            db_id=task.db_id,
            policy="P0_parallel",
            agent_id=agent_id,
            runs_dir=tmp_path,
        )
        from src.bird.tasks import sqlite_path_for_task

        db_path = sqlite_path_for_task(task, cfg)
        for sql in explore_sql:
            trace.log_sql_execute(sql=sql, sql_role="explore", db_path=db_path)
        trace.finish(
            predicted_sql="SELECT 1",
            gold_sql=task.gold_sql,
            ex_correct=0,
            match=False,
        )
        return trace.path

    t1 = make_trace("agent_0", ["SELECT 1", "SELECT 2"])
    t2 = make_trace("agent_1", ["SELECT 1", "SELECT 3"])

    replicas = [
        _result(ex=0, turns=2, trace_path=t1, prompt=50, completion=5),
        _result(ex=0, turns=2, trace_path=t2, prompt=80, completion=8),
    ]
    metrics = compute_redundancy(replicas)
    assert metrics.total_explore_sql == 4
    assert metrics.duplicate_explore_sql == 1
    assert metrics.token_overhead_ratio is None
