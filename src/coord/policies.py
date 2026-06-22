"""Replica selection policies for parallel agent runs."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any

from src.agent.loop import AgentRunResult
from src.bird.tasks import BirdTask, sqlite_path_for_task
from src.config import ProjectConfig
from src.db.sqlite_exec import SqlExecutionError, execute_sql


class CoordinationPolicy(str, Enum):
    """How to pick the final answer from N replica runs."""

    BEST_OF_N = "best_of_n"
    FIRST_SUCCESS = "first_success"
    MAJORITY_VOTE = "majority_vote"


@dataclass(frozen=True)
class ReplicaOutcome:
    """Replica result plus optional result-set fingerprint for voting."""

    result: AgentRunResult
    result_fingerprint: str | None = None


def _normalize_sql(sql: str | None) -> str:
    if not sql:
        return ""
    return " ".join(sql.split()).lower()


def result_fingerprint(
    task: BirdTask,
    sql: str | None,
    cfg: ProjectConfig,
) -> str | None:
    """Hashable key from executed result set (order-independent)."""
    if not sql:
        return None
    db_path = sqlite_path_for_task(task, cfg)
    try:
        rows = execute_sql(db_path, sql, timeout_seconds=float(cfg.query_timeout_seconds))
    except SqlExecutionError:
        return None
    return str(frozenset(rows))


def enrich_outcomes(
    task: BirdTask,
    replicas: list[AgentRunResult],
    cfg: ProjectConfig,
) -> list[ReplicaOutcome]:
    return [
        ReplicaOutcome(
            result=r,
            result_fingerprint=result_fingerprint(task, r.final_sql, cfg),
        )
        for r in replicas
    ]


def select_replica(
    policy: CoordinationPolicy,
    outcomes: list[ReplicaOutcome],
    *,
    completion_order: list[int] | None = None,
) -> AgentRunResult:
    """
    Pick the coordinating replica's result.

    completion_order: replica indices in finish order (for first_success).
    """
    if not outcomes:
        raise ValueError("No replica outcomes to select from")

    if policy == CoordinationPolicy.BEST_OF_N:
        correct = [o for o in outcomes if o.result.ex_correct == 1]
        if correct:
            return min(correct, key=lambda o: o.result.turns).result
        with_sql = [o for o in outcomes if o.result.final_sql]
        if with_sql:
            return min(with_sql, key=lambda o: o.result.turns).result
        return outcomes[0].result

    if policy == CoordinationPolicy.FIRST_SUCCESS:
        order = completion_order or list(range(len(outcomes)))
        for idx in order:
            if 0 <= idx < len(outcomes) and outcomes[idx].result.ex_correct == 1:
                return outcomes[idx].result
        return select_replica(CoordinationPolicy.BEST_OF_N, outcomes)

    if policy == CoordinationPolicy.MAJORITY_VOTE:
        buckets: dict[str, list[ReplicaOutcome]] = {}
        for o in outcomes:
            key = o.result_fingerprint or f"sql:{_normalize_sql(o.result.final_sql)}"
            buckets.setdefault(key, []).append(o)
        winner = max(buckets.values(), key=len)
        correct_in_winner = [o for o in winner if o.result.ex_correct == 1]
        if correct_in_winner:
            return min(correct_in_winner, key=lambda o: o.result.turns).result
        return min(winner, key=lambda o: o.result.turns).result

    raise ValueError(f"Unknown policy: {policy}")


def policy_from_str(name: str) -> CoordinationPolicy:
    try:
        return CoordinationPolicy(name)
    except ValueError as e:
        valid = ", ".join(p.value for p in CoordinationPolicy)
        raise ValueError(f"Unknown policy {name!r}; expected one of: {valid}") from e
