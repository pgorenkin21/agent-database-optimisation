"""Redundancy metrics from parallel replica traces."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from src.agent.loop import AgentRunResult
from src.logging.trace import read_trace_events


def _normalize_sql(sql: str) -> str:
    return " ".join(sql.split()).lower()


@dataclass(frozen=True)
class RedundancyMetrics:
    n_replicas: int
    replicas_ex_correct: int
    total_prompt_tokens: int
    total_completion_tokens: int
    min_replica_prompt_tokens: int
    min_replica_completion_tokens: int
    duplicate_explore_sql: int
    total_explore_sql: int
    explore_redundancy_pct: float
    token_overhead_ratio: float | None
    # Cached input tokens served from the provider prompt cache. 0 for
    # baseline (non-cached) replicas that do not report a cached split.
    total_cached_prompt_tokens: int = 0

    @property
    def cached_prompt_pct(self) -> float:
        if self.total_prompt_tokens <= 0:
            return 0.0
        return 100.0 * self.total_cached_prompt_tokens / self.total_prompt_tokens

    def to_dict(self) -> dict[str, float | int | None]:
        return {
            "n_replicas": self.n_replicas,
            "replicas_ex_correct": self.replicas_ex_correct,
            "total_prompt_tokens": self.total_prompt_tokens,
            "total_completion_tokens": self.total_completion_tokens,
            "total_cached_prompt_tokens": self.total_cached_prompt_tokens,
            "cached_prompt_pct": round(self.cached_prompt_pct, 2),
            "min_replica_prompt_tokens": self.min_replica_prompt_tokens,
            "min_replica_completion_tokens": self.min_replica_completion_tokens,
            "duplicate_explore_sql": self.duplicate_explore_sql,
            "total_explore_sql": self.total_explore_sql,
            "explore_redundancy_pct": round(self.explore_redundancy_pct, 2),
            "token_overhead_ratio": round(self.token_overhead_ratio, 3) if self.token_overhead_ratio is not None else None,
        }


def compute_redundancy(replicas: list[AgentRunResult]) -> RedundancyMetrics:
    """Aggregate redundancy across replica traces."""
    n = len(replicas)
    prompt_tokens = [r.total_prompt_tokens for r in replicas]
    completion_tokens = [r.total_completion_tokens for r in replicas]
    total_prompt = sum(prompt_tokens)
    total_completion = sum(completion_tokens)
    actual_total = total_prompt + total_completion

    successful = [r for r in replicas if r.ex_correct]
    if successful:
        min_prompt = min(r.total_prompt_tokens for r in successful)
        min_completion = min(r.total_completion_tokens for r in successful)
        min_total = min_prompt + min_completion
        overhead: float | None = actual_total / min_total if min_total > 0 else float(n)
    else:
        min_prompt = 0
        min_completion = 0
        overhead = None

    explore_sql: list[str] = []
    for r in replicas:
        if not r.trace_path.exists():
            continue
        for ev in read_trace_events(r.trace_path):
            if ev.get("event") == "sql_execute" and ev.get("sql_role") == "explore":
                sql = ev.get("sql_raw", "")
                if sql:
                    explore_sql.append(_normalize_sql(str(sql)))

    seen: set[str] = set()
    duplicates = 0
    for sql in explore_sql:
        if sql in seen:
            duplicates += 1
        else:
            seen.add(sql)

    total_explore = len(explore_sql)
    explore_pct = 100.0 * duplicates / total_explore if total_explore else 0.0
    # getattr keeps this compatible with both AgentRunResult (no cached split)
    # and CachedAgentRunResult (prompt cache).
    total_cached = sum(getattr(r, "total_cached_prompt_tokens", 0) for r in replicas)
    return RedundancyMetrics(
        n_replicas=n,
        replicas_ex_correct=sum(r.ex_correct for r in replicas),
        total_prompt_tokens=total_prompt,
        total_completion_tokens=total_completion,
        min_replica_prompt_tokens=min_prompt if successful else 0,
        min_replica_completion_tokens=min_completion if successful else 0,
        duplicate_explore_sql=duplicates,
        total_explore_sql=total_explore,
        explore_redundancy_pct=explore_pct,
        token_overhead_ratio=overhead,
        total_cached_prompt_tokens=total_cached,
    )


def explore_sql_from_trace(trace_path: Path) -> list[str]:
    """Return normalized explore SQL statements from one trace."""
    out: list[str] = []
    for ev in read_trace_events(trace_path):
        if ev.get("event") == "sql_execute" and ev.get("sql_role") == "explore":
            sql = ev.get("sql_raw", "")
            if sql:
                out.append(_normalize_sql(str(sql)))
    return out
