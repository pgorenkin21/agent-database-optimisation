"""Per-replica temperature and stagger scheduling for parallel coordination."""

from __future__ import annotations

import argparse
import time
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from src.config import ProjectConfig


@dataclass(frozen=True)
class ReplicaScheduleConfig:
    """Task-level schedule applied to all replicas in a parallel run."""

    base_temperature: float = 0.0
    temperature_mode: str = "uniform"  # uniform | ladder
    temperature_step: float = 0.2
    stagger_mode: str = "none"  # none | linear_seconds | linear_turns
    stagger_seconds: float = 0.0
    stagger_turns: int = 0
    stagger_poll_seconds: float = 1.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "base_temperature": self.base_temperature,
            "temperature_mode": self.temperature_mode,
            "temperature_step": self.temperature_step,
            "stagger_mode": self.stagger_mode,
            "stagger_seconds": self.stagger_seconds,
            "stagger_turns": self.stagger_turns,
            "stagger_poll_seconds": self.stagger_poll_seconds,
        }


@dataclass(frozen=True)
class ReplicaProfile:
    agent_idx: int
    temperature: float
    start_delay_seconds: float
    start_turn_delay: int

    def to_dict(self) -> dict[str, Any]:
        return {
            "agent_idx": self.agent_idx,
            "temperature": self.temperature,
            "start_delay_seconds": self.start_delay_seconds,
            "start_turn_delay": self.start_turn_delay,
        }


def _clamp_temperature(value: float) -> float:
    return max(0.0, min(2.0, float(value)))


def resolve_replica_temperature(
    config: ReplicaScheduleConfig,
    *,
    agent_idx: int,
) -> float:
    base = _clamp_temperature(config.base_temperature)
    if config.temperature_mode == "ladder":
        return _clamp_temperature(base + agent_idx * config.temperature_step)
    return base


def resolve_replica_profile(
    config: ReplicaScheduleConfig,
    *,
    agent_idx: int,
) -> ReplicaProfile:
    temperature = resolve_replica_temperature(config, agent_idx=agent_idx)
    start_delay_seconds = 0.0
    start_turn_delay = 0
    if config.stagger_mode == "linear_seconds":
        start_delay_seconds = max(0.0, agent_idx * config.stagger_seconds)
    elif config.stagger_mode == "linear_turns":
        start_turn_delay = max(0, agent_idx * config.stagger_turns)
    return ReplicaProfile(
        agent_idx=agent_idx,
        temperature=temperature,
        start_delay_seconds=start_delay_seconds,
        start_turn_delay=start_turn_delay,
    )


def schedule_from_config(
    cfg: ProjectConfig,
    *,
    base_temperature: float | None = None,
    temperature_mode: str | None = None,
    temperature_step: float | None = None,
    stagger_mode: str | None = None,
    stagger_seconds: float | None = None,
    stagger_turns: int | None = None,
    stagger_poll_seconds: float | None = None,
) -> ReplicaScheduleConfig:
    coord = cfg.raw.get("coordination", {})
    return ReplicaScheduleConfig(
        base_temperature=(
            cfg.llm_temperature if base_temperature is None else float(base_temperature)
        ),
        temperature_mode=str(temperature_mode or coord.get("temperature_mode", "uniform")),
        temperature_step=float(
            temperature_step if temperature_step is not None else coord.get("temperature_step", 0.2)
        ),
        stagger_mode=str(stagger_mode or coord.get("stagger_mode", "none")),
        stagger_seconds=float(
            stagger_seconds if stagger_seconds is not None else coord.get("stagger_seconds", 0.0)
        ),
        stagger_turns=int(
            stagger_turns if stagger_turns is not None else coord.get("stagger_turns", 0)
        ),
        stagger_poll_seconds=float(
            stagger_poll_seconds
            if stagger_poll_seconds is not None
            else coord.get("stagger_poll_seconds", 1.0)
        ),
    )


def wait_with_cancel(
    seconds: float,
    cancel_event: Any | None,
    *,
    poll_seconds: float = 0.1,
) -> bool:
    """Sleep up to *seconds*; return True if cancelled."""
    if seconds <= 0:
        return cancel_event is not None and cancel_event.is_set()
    deadline = time.perf_counter() + seconds
    while time.perf_counter() < deadline:
        if cancel_event is not None and cancel_event.is_set():
            return True
        time.sleep(min(poll_seconds, max(0.0, deadline - time.perf_counter())))
    return cancel_event is not None and cancel_event.is_set()


def wait_turns_with_cancel(
    turns: int,
    cancel_event: Any | None,
    *,
    poll_seconds: float = 1.0,
) -> bool:
    """Wait *turns* polling intervals; return True if cancelled."""
    for _ in range(max(0, turns)):
        if cancel_event is not None and cancel_event.is_set():
            return True
        time.sleep(max(0.01, poll_seconds))
    return cancel_event is not None and cancel_event.is_set()


def schedule_batch_tag_suffix(config: ReplicaScheduleConfig) -> str:
    """Compact suffix for parallel batch filenames."""
    parts: list[str] = []
    if config.temperature_mode == "ladder":
        parts.append(
            f"tl{int(config.base_temperature * 100):02d}s{int(config.temperature_step * 100):02d}"
        )
    elif config.base_temperature != 0.0:
        parts.append(f"t{int(config.base_temperature * 100):02d}")
    if config.stagger_mode == "linear_seconds" and config.stagger_seconds > 0:
        parts.append(f"stag{config.stagger_seconds:.1f}s".replace(".", "p"))
    elif config.stagger_mode == "linear_turns" and config.stagger_turns > 0:
        parts.append(f"stag{config.stagger_turns}t")
    return ("_" + "_".join(parts)) if parts else ""


def add_replica_schedule_arguments(parser: argparse.ArgumentParser) -> None:
    group = parser.add_argument_group("replica schedule (temperature & stagger)")
    group.add_argument(
        "--temperature",
        type=float,
        default=None,
        help="LLM sampling temperature for all replicas (default: config llm.temperature)",
    )
    group.add_argument(
        "--temperature-mode",
        type=str,
        default=None,
        choices=["uniform", "ladder"],
        help="uniform: same T for all replicas; ladder: T + i*step per agent_i",
    )
    group.add_argument(
        "--temperature-step",
        type=float,
        default=None,
        help="Per-replica increment when --temperature-mode ladder (default: 0.2)",
    )
    group.add_argument(
        "--stagger-mode",
        type=str,
        default=None,
        choices=["none", "linear_seconds", "linear_turns"],
        help="Delay replica starts so earlier agents populate middleware first",
    )
    group.add_argument(
        "--stagger-seconds",
        type=float,
        default=None,
        help="Agent i waits i * N seconds before first LLM call (linear_seconds)",
    )
    group.add_argument(
        "--stagger-turns",
        type=int,
        default=None,
        help="Agent i waits i * N turn-polls before first LLM call (linear_turns)",
    )
    group.add_argument(
        "--stagger-poll-seconds",
        type=float,
        default=None,
        help="Sleep interval per stagger turn while waiting (default: 1.0)",
    )


def schedule_from_args(args: argparse.Namespace, cfg: ProjectConfig) -> ReplicaScheduleConfig:
    return schedule_from_config(
        cfg,
        base_temperature=args.temperature,
        temperature_mode=args.temperature_mode,
        temperature_step=args.temperature_step,
        stagger_mode=args.stagger_mode,
        stagger_seconds=args.stagger_seconds,
        stagger_turns=args.stagger_turns,
        stagger_poll_seconds=args.stagger_poll_seconds,
    )
