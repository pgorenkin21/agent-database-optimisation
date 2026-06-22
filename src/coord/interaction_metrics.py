"""DB vs middleware interaction metrics from replica traces."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from src.agent.loop import AgentRunResult
from src.logging.trace import read_trace_events


@dataclass(frozen=True)
class InteractionMetrics:
    """
    Classify agent interactions by whether they hit SQLite or middleware.

    - **DB**: ``sql_execute`` events that run against SQLite (cache miss, final
      submit, or any query without a shared cache).
    - **Middleware (cache)**: explore ``sql_execute`` events served from the
      shared LRU without a DB round-trip.
    - **Middleware (discovery)**: ``discovery_injection`` events from the P2
      discovery board (prompt augmentation, not SQL).
    """

    db_sql_executions: int
    middleware_cache_hits: int
    middleware_discovery_injections: int
    middleware_semantic_injections: int

    @property
    def middleware_interactions(self) -> int:
        return (
            self.middleware_cache_hits
            + self.middleware_discovery_injections
            + self.middleware_semantic_injections
        )

    @property
    def total_interactions(self) -> int:
        return self.db_sql_executions + self.middleware_interactions

    @property
    def middleware_interaction_pct(self) -> float:
        """Share of all interactions handled by middleware rather than SQLite."""
        total = self.total_interactions
        if total == 0:
            return 0.0
        return 100.0 * self.middleware_interactions / total

    @property
    def sql_cache_hit_pct(self) -> float:
        """Share of SQL interactions (explore + final) served from cache."""
        sql_total = self.db_sql_executions + self.middleware_cache_hits
        if sql_total == 0:
            return 0.0
        return 100.0 * self.middleware_cache_hits / sql_total

    def to_dict(self) -> dict[str, float | int]:
        return {
            "db_sql_executions": self.db_sql_executions,
            "middleware_cache_hits": self.middleware_cache_hits,
            "middleware_discovery_injections": self.middleware_discovery_injections,
            "middleware_semantic_injections": self.middleware_semantic_injections,
            "middleware_interactions": self.middleware_interactions,
            "total_interactions": self.total_interactions,
            "middleware_interaction_pct": round(self.middleware_interaction_pct, 2),
            "sql_cache_hit_pct": round(self.sql_cache_hit_pct, 2),
        }


def interaction_metrics_from_trace(trace_path: Path) -> InteractionMetrics:
    """Count DB vs middleware interactions in one replica trace."""
    db_sql = 0
    cache_hits = 0
    discovery = 0
    semantic = 0

    if not trace_path.exists():
        return InteractionMetrics(0, 0, 0, 0)

    for ev in read_trace_events(trace_path):
        event = ev.get("event")
        if event == "sql_execute":
            if ev.get("cache_hit") is True:
                cache_hits += 1
            else:
                db_sql += 1
        elif event == "discovery_injection":
            discovery += 1
        elif event == "semantic_injection":
            semantic += 1

    return InteractionMetrics(
        db_sql_executions=db_sql,
        middleware_cache_hits=cache_hits,
        middleware_discovery_injections=discovery,
        middleware_semantic_injections=semantic,
    )


def compute_interaction_metrics(replicas: list[AgentRunResult]) -> InteractionMetrics:
    """Aggregate DB vs middleware interactions across parallel replicas."""
    db_sql = 0
    cache_hits = 0
    discovery = 0
    semantic = 0
    for replica in replicas:
        m = interaction_metrics_from_trace(replica.trace_path)
        db_sql += m.db_sql_executions
        cache_hits += m.middleware_cache_hits
        discovery += m.middleware_discovery_injections
        semantic += m.middleware_semantic_injections
    return InteractionMetrics(
        db_sql_executions=db_sql,
        middleware_cache_hits=cache_hits,
        middleware_discovery_injections=discovery,
        middleware_semantic_injections=semantic,
    )


def interaction_metrics_from_coord_trace(coord_path: Path) -> InteractionMetrics | None:
    """Recompute interaction metrics from a coordination JSONL trace."""
    if not coord_path.exists():
        return None

    events = read_trace_events(coord_path)
    replica_ends = [e for e in events if e.get("event") == "replica_end"]
    if not replica_ends:
        end = next((e for e in events if e.get("event") == "coordination_end"), None)
        if end and "interaction_metrics" in end:
            raw = end["interaction_metrics"]
            return InteractionMetrics(
                db_sql_executions=int(raw.get("db_sql_executions", 0)),
                middleware_cache_hits=int(raw.get("middleware_cache_hits", 0)),
                middleware_discovery_injections=int(
                    raw.get("middleware_discovery_injections", 0)
                ),
                middleware_semantic_injections=int(
                    raw.get("middleware_semantic_injections", 0)
                ),
            )
        return None

    db_sql = 0
    cache_hits = 0
    discovery = 0
    semantic = 0
    for rep in replica_ends:
        m = interaction_metrics_from_trace(Path(str(rep.get("trace_path", ""))))
        db_sql += m.db_sql_executions
        cache_hits += m.middleware_cache_hits
        discovery += m.middleware_discovery_injections
        semantic += m.middleware_semantic_injections
    return InteractionMetrics(
        db_sql_executions=db_sql,
        middleware_cache_hits=cache_hits,
        middleware_discovery_injections=discovery,
        middleware_semantic_injections=semantic,
    )


def batch_interaction_summary(rows: list[dict]) -> dict[str, float | int]:
    """Aggregate per-task interaction rows into batch-level totals."""
    enriched = _enrich_rows_with_trace_metrics(rows)
    db_sql = sum(int(r.get("db_interactions", 0)) for r in enriched)
    cache_hits = sum(int(r.get("middleware_cache_hits", 0)) for r in enriched)
    discovery = sum(int(r.get("middleware_discovery_injections", 0)) for r in enriched)
    semantic = sum(int(r.get("middleware_semantic_injections", 0)) for r in enriched)
    middleware = cache_hits + discovery + semantic
    total = db_sql + middleware
    per_task_pcts = [
        float(r["middleware_interaction_pct"])
        for r in enriched
        if "middleware_interaction_pct" in r
    ]
    return {
        "total_db_interactions": db_sql,
        "total_middleware_cache_hits": cache_hits,
        "total_middleware_discovery_injections": discovery,
        "total_middleware_semantic_injections": semantic,
        "total_middleware_interactions": middleware,
        "total_interactions": total,
        "batch_middleware_interaction_pct": round(100.0 * middleware / total, 2) if total else 0.0,
        "avg_middleware_interaction_pct": round(
            sum(per_task_pcts) / len(per_task_pcts), 2
        )
        if per_task_pcts
        else 0.0,
    }


def _enrich_rows_with_trace_metrics(rows: list[dict]) -> list[dict]:
    """Backfill interaction fields from coord traces when batch rows lack them."""
    out: list[dict] = []
    for row in rows:
        if row.get("db_interactions") is not None:
            out.append(row)
            continue
        coord_path = row.get("coord_trace_path")
        if not coord_path:
            out.append(row)
            continue
        metrics = interaction_metrics_from_coord_trace(Path(str(coord_path)))
        if metrics is None:
            out.append(row)
            continue
        enriched = dict(row)
        enriched.update(
            {
                "db_interactions": metrics.db_sql_executions,
                "middleware_cache_hits": metrics.middleware_cache_hits,
                "middleware_discovery_injections": metrics.middleware_discovery_injections,
                "middleware_semantic_injections": metrics.middleware_semantic_injections,
                "middleware_interactions": metrics.middleware_interactions,
                "middleware_interaction_pct": round(metrics.middleware_interaction_pct, 2),
            }
        )
        out.append(enriched)
    return out
