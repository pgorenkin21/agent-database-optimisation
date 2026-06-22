"""Tests for replica temperature and stagger scheduling."""

from __future__ import annotations

import threading
import time
from pathlib import Path
from unittest.mock import patch

import pytest

from src.coord.replica_schedule import (
    ReplicaScheduleConfig,
    resolve_replica_profile,
    resolve_replica_temperature,
    schedule_batch_tag_suffix,
    wait_turns_with_cancel,
    wait_with_cancel,
)


def test_resolve_replica_temperature_uniform() -> None:
    cfg = ReplicaScheduleConfig(base_temperature=0.3, temperature_mode="uniform")
    assert resolve_replica_temperature(cfg, agent_idx=0) == 0.3
    assert resolve_replica_temperature(cfg, agent_idx=5) == 0.3


def test_resolve_replica_temperature_ladder() -> None:
    cfg = ReplicaScheduleConfig(
        base_temperature=0.0,
        temperature_mode="ladder",
        temperature_step=0.2,
    )
    assert resolve_replica_temperature(cfg, agent_idx=0) == 0.0
    assert resolve_replica_temperature(cfg, agent_idx=2) == pytest.approx(0.4)
    assert resolve_replica_temperature(cfg, agent_idx=10) == 2.0


def test_resolve_replica_profile_linear_stagger() -> None:
    cfg = ReplicaScheduleConfig(
        stagger_mode="linear_seconds",
        stagger_seconds=2.5,
    )
    p0 = resolve_replica_profile(cfg, agent_idx=0)
    p2 = resolve_replica_profile(cfg, agent_idx=2)
    assert p0.start_delay_seconds == 0.0
    assert p2.start_delay_seconds == 5.0
    assert p2.start_turn_delay == 0

    cfg_turns = ReplicaScheduleConfig(stagger_mode="linear_turns", stagger_turns=2)
    p3 = resolve_replica_profile(cfg_turns, agent_idx=3)
    assert p3.start_turn_delay == 6
    assert p3.start_delay_seconds == 0.0


def test_schedule_batch_tag_suffix() -> None:
    uniform = ReplicaScheduleConfig(base_temperature=0.3)
    assert schedule_batch_tag_suffix(uniform) == "_t30"
    ladder = ReplicaScheduleConfig(
        base_temperature=0.0,
        temperature_mode="ladder",
        temperature_step=0.2,
    )
    assert schedule_batch_tag_suffix(ladder) == "_tl00s20"
    stagger = ReplicaScheduleConfig(
        stagger_mode="linear_seconds",
        stagger_seconds=2.0,
    )
    assert schedule_batch_tag_suffix(stagger) == "_stag2p0s"


def test_wait_with_cancel() -> None:
    cancel = threading.Event()
    start = time.perf_counter()
    assert wait_with_cancel(0.3, cancel, poll_seconds=0.05) is False
    assert time.perf_counter() - start >= 0.25

    cancel.set()
    assert wait_with_cancel(1.0, cancel, poll_seconds=0.05) is True


def test_wait_turns_with_cancel() -> None:
    cancel = threading.Event()
    start = time.perf_counter()
    assert wait_turns_with_cancel(2, cancel, poll_seconds=0.05) is False
    assert time.perf_counter() - start >= 0.08

    cancel.set()
    assert wait_turns_with_cancel(5, cancel, poll_seconds=0.05) is True


@pytest.fixture
def cfg():
    from src.config import load_config

    c = load_config()
    if not c.tasks_json.exists():
        pytest.skip("BIRD mini-dev not downloaded")
    return c


def test_run_agent_passes_temperature_to_backend(cfg, tmp_path: Path) -> None:
    from src.agent.loop import run_agent
    from src.bird.tasks import load_tasks
    from src.logging.trace import RunTrace

    task = load_tasks(cfg)[0]
    trace = RunTrace(
        cfg=cfg,
        question_id=task.question_id,
        db_id=task.db_id,
        policy="P0",
        agent_id="agent_0",
        runs_dir=tmp_path,
        temperature=0.7,
    )
    mock_create = patch("src.agent.loop.create_chat_backend").start()
    mock_backend = mock_create.return_value
    mock_backend.complete.return_value = type(
        "R",
        (),
        {
            "assistant_message": {"role": "assistant", "content": None, "tool_calls": []},
            "tool_calls": [],
            "prompt_tokens": 1,
            "completion_tokens": 1,
        },
    )()

    try:
        run_agent(
            task,
            "gpt-4o-mini",
            cfg,
            trace=trace,
            temperature=0.7,
        )
    finally:
        patch.stopall()

    mock_create.assert_called_once()
    assert mock_create.call_args.kwargs["temperature"] == 0.7


def test_stagger_delays_before_llm(cfg, tmp_path: Path) -> None:
    from src.agent.loop import run_agent
    from src.bird.tasks import load_tasks
    from src.logging.trace import RunTrace

    task = load_tasks(cfg)[0]
    trace = RunTrace(
        cfg=cfg,
        question_id=task.question_id,
        db_id=task.db_id,
        policy="P0",
        agent_id="agent_2",
        runs_dir=tmp_path,
        start_delay_seconds=0.15,
    )
    mock_create = patch("src.agent.loop.create_chat_backend").start()
    mock_backend = mock_create.return_value
    llm_called = threading.Event()

    def _complete(_messages):
        llm_called.set()
        return type(
            "R",
            (),
            {
                "assistant_message": {"role": "assistant", "content": "done"},
                "tool_calls": [],
                "prompt_tokens": 1,
                "completion_tokens": 1,
            },
        )()

    mock_backend.complete.side_effect = _complete

    start = time.perf_counter()
    try:
        run_agent(
            task,
            "gpt-4o-mini",
            cfg,
            trace=trace,
            start_delay_seconds=0.15,
            stagger_poll_seconds=0.05,
        )
    finally:
        patch.stopall()

    assert llm_called.is_set()
    assert time.perf_counter() - start >= 0.12
