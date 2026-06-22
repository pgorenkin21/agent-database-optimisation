"""Tests for parallel early stopping (no live API calls)."""

from __future__ import annotations

import threading
import time
from pathlib import Path
from unittest.mock import patch

import pytest

from src.agent.loop import AgentRunResult
from src.coord.parallel import run_parallel_agents
from src.coord.policies import CoordinationPolicy


def _fake_result(
    *,
    idx: int,
    ex: int = 0,
    stop_reason: str = "submit_sql",
    turns: int = 1,
    delay: float = 0.0,
) -> AgentRunResult:
    if delay:
        time.sleep(delay)
    return AgentRunResult(
        question_id=1,
        db_id="db",
        model_key="test",
        final_sql="SELECT 1" if ex else None,
        ex_correct=ex,
        turns=turns,
        trace_path=Path(f"/tmp/agent_{idx}.jsonl"),
        total_prompt_tokens=100 * (turns + 1),
        total_completion_tokens=10 * (turns + 1),
        stop_reason=stop_reason,
    )


@pytest.fixture
def cfg():
    from src.config import load_config

    c = load_config()
    if not c.tasks_json.exists():
        pytest.skip("BIRD mini-dev not downloaded")
    return c


def test_run_agent_exits_immediately_when_cancel_pre_set(cfg, tmp_path: Path) -> None:
    from src.bird.tasks import load_tasks
    from src.agent.loop import run_agent
    from src.logging.trace import RunTrace

    task = load_tasks(cfg)[0]
    cancel = threading.Event()
    cancel.set()
    trace = RunTrace(
        cfg=cfg,
        question_id=task.question_id,
        db_id=task.db_id,
        policy="P0_early_stop",
        agent_id="agent_0",
        runs_dir=tmp_path,
    )

    mock_backend = patch("src.agent.loop.create_chat_backend").start()
    mock_backend.return_value.complete.side_effect = AssertionError("LLM should not be called")

    try:
        result = run_agent(
            task,
            "gpt-4o-mini",
            cfg,
            trace=trace,
            policy="P0_early_stop",
            cancel_event=cancel,
        )
    finally:
        patch.stopall()

    assert result.stop_reason == "cancelled_early"
    assert result.turns == 0
    assert result.ex_correct == 0


def test_early_stop_cancels_slow_replicas(cfg) -> None:
    from src.bird.tasks import load_tasks

    task = load_tasks(cfg)[0]

    def side_effect(
        task_arg,
        model_key,
        cfg_arg,
        *,
        policy,
        agent_id,
        cancel_event=None,
        sql_cache=None,
        discovery_board=None,
        semantic_store=None,
        **kwargs,
    ):
        idx = int(agent_id.split("_")[1])
        if idx == 0:
            return _fake_result(idx=0, ex=1, delay=0.05)
        for _ in range(50):
            if cancel_event is not None and cancel_event.is_set():
                return _fake_result(idx=idx, ex=0, stop_reason="cancelled_early", turns=0)
            time.sleep(0.02)
        return _fake_result(idx=idx, ex=0, turns=5)

    with patch("src.coord.parallel.run_agent", side_effect=side_effect):
        result = run_parallel_agents(
            task,
            "gpt-4o-mini",
            n_replicas=3,
            policy=CoordinationPolicy.FIRST_SUCCESS,
            cfg=cfg,
            write_coord_trace=False,
            early_stop=True,
        )

    assert result.ex_correct == 1
    assert result.early_stop_triggered is True
    assert result.replicas_cancelled >= 1
    cancelled = [r for r in result.replicas if r.stop_reason == "cancelled_early"]
    assert len(cancelled) >= 1


def test_no_early_stop_when_no_correct_replica(cfg) -> None:
    from src.bird.tasks import load_tasks

    task = load_tasks(cfg)[0]

    with patch(
        "src.coord.parallel.run_agent",
        side_effect=lambda *a, **k: _fake_result(
            idx=int(k["agent_id"].split("_")[1]), ex=0
        ),
    ):
        result = run_parallel_agents(
            task,
            "gpt-4o-mini",
            n_replicas=3,
            cfg=cfg,
            write_coord_trace=False,
            early_stop=True,
        )

    assert result.ex_correct == 0
    assert result.early_stop_triggered is False
    assert result.replicas_cancelled == 0
