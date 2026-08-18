"""Heterogeneous multi-model parallel runs (no live API calls)."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest

from src.agent.loop import AgentRunResult
from src.coord.parallel import (
    ensemble_model_label,
    resolve_replica_model_keys,
    run_parallel_agents,
)
from src.coord.policies import CoordinationPolicy, ReplicaOutcome, select_replica


def _result(
    *,
    model_key: str,
    ex: int,
    turns: int,
    sql: str | None = "SELECT 1",
) -> AgentRunResult:
    return AgentRunResult(
        question_id=1,
        db_id="db",
        model_key=model_key,
        final_sql=sql,
        ex_correct=ex,
        turns=turns,
        trace_path=Path(f"/tmp/{model_key}.jsonl"),
        total_prompt_tokens=100,
        total_completion_tokens=10,
        stop_reason="submit_sql",
    )


def test_resolve_replica_model_keys_homogeneous() -> None:
    keys = resolve_replica_model_keys(model_key="gpt-4o-mini", n_replicas=3)
    assert keys == ["gpt-4o-mini", "gpt-4o-mini", "gpt-4o-mini"]


def test_resolve_replica_model_keys_heterogeneous() -> None:
    keys = resolve_replica_model_keys(
        model_keys=["gpt-4o-mini", "gemini-2.5-flash", "deepseek-v3.2"]
    )
    assert len(keys) == 3
    assert keys[0] == "gpt-4o-mini"


def test_ensemble_model_label() -> None:
    label = ensemble_model_label(["gpt-4o-mini", "gemini-2.5-flash"])
    assert label == "gpt-4o-mini+gemini-2.5-flash"


def test_best_of_n_picks_correct_model_with_fewest_turns() -> None:
    outcomes = [
        ReplicaOutcome(_result(model_key="gpt-4o-mini", ex=0, turns=2)),
        ReplicaOutcome(_result(model_key="gemini-2.5-flash", ex=1, turns=4)),
        ReplicaOutcome(_result(model_key="deepseek-v3.2", ex=1, turns=3)),
    ]
    chosen = select_replica(CoordinationPolicy.BEST_OF_N, outcomes)
    assert chosen.model_key == "deepseek-v3.2"
    assert chosen.ex_correct == 1
    assert chosen.turns == 3


@pytest.fixture
def cfg():
    from src.config import load_config

    c = load_config()
    if not c.tasks_json.exists():
        pytest.skip("BIRD mini-dev not downloaded")
    return c


def test_run_parallel_agents_uses_per_replica_models(cfg) -> None:
    from src.bird.tasks import load_tasks

    task = load_tasks(cfg)[0]
    model_keys = ["gpt-4o-mini", "gemini-2.5-flash", "deepseek-v3.2"]
    seen_models: list[str] = []

    def side_effect(task_arg, model_key, cfg_arg, *, agent_id, **kwargs):
        seen_models.append(model_key)
        idx = int(agent_id.split("_")[1])
        return _result(
            model_key=model_key,
            ex=1 if idx == 2 else 0,
            turns=idx + 1,
            sql=f"SELECT {idx}",
        )

    with patch("src.coord.parallel.run_agent", side_effect=side_effect):
        result = run_parallel_agents(
            task,
            model_keys=model_keys,
            policy=CoordinationPolicy.BEST_OF_N,
            cfg=cfg,
            write_coord_trace=False,
        )

    assert seen_models == model_keys
    assert result.model_key == ensemble_model_label(model_keys)
    assert result.replica_model_keys == model_keys
    assert result.ex_correct == 1
    assert result.chosen is not None
    assert result.chosen.model_key == "deepseek-v3.2"
    assert result.chosen.turns == 3
