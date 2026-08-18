"""Run N parallel agent replicas on one BIRD task and coordinate the final answer."""

from __future__ import annotations

import json
import threading
import time
import uuid
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from src.agent.loop import AgentRunResult, run_agent
from src.bird.tasks import BirdTask
from src.config import ProjectConfig, load_config
from src.coord.policies import (
    CoordinationPolicy,
    enrich_outcomes,
    select_replica,
)
from src.coord.interaction_metrics import InteractionMetrics, compute_interaction_metrics
from src.coord.redundancy import RedundancyMetrics, compute_redundancy
from src.coord.replica_schedule import (
    ReplicaScheduleConfig,
    ReplicaProfile,
    resolve_replica_profile,
    schedule_from_config,
)
from src.coord.shared_discovery import DiscoveryStats, SharedDiscoveryBoard
from src.coord.semantic_store import SemanticStoreStats, SharedSemanticStore
from src.db.shared_sql_cache import SharedSqlResultCache, SqlCacheStats
from src.logging.trace import _json_safe, _utc_now_iso

TRACE_POLICY_PARALLEL = "P0_parallel"
TRACE_POLICY_EARLY_STOP = "P0_early_stop"
TRACE_POLICY_P1 = "P1_shared_cache"
TRACE_POLICY_P2 = "P2_subexpr_propagation"
TRACE_POLICY_P3 = "P3_semantic_store"
TRACE_POLICY_P1_P2 = "P1_P2_combined"
TRACE_POLICY_P1_P3 = "P1_P3_combined"


def resolve_trace_policy(
    *,
    shared_cache: bool,
    early_stop: bool,
    discovery_board: bool = False,
    semantic_store: bool = False,
) -> str:
    if shared_cache and discovery_board:
        base = TRACE_POLICY_P1_P2
    elif shared_cache and semantic_store:
        base = TRACE_POLICY_P1_P3
    elif shared_cache:
        base = TRACE_POLICY_P1
    elif discovery_board:
        base = TRACE_POLICY_P2
    elif semantic_store:
        base = TRACE_POLICY_P3
    elif early_stop:
        return TRACE_POLICY_EARLY_STOP
    else:
        return TRACE_POLICY_PARALLEL

    if early_stop:
        return f"{base}_early_stop"
    return base


def resolve_replica_model_keys(
    *,
    model_key: str | None = None,
    model_keys: list[str] | None = None,
    n_replicas: int = 3,
) -> list[str]:
    """Return one model key per replica (homogeneous or heterogeneous)."""
    if model_keys is not None:
        if not model_keys:
            raise ValueError("model_keys must be non-empty")
        return list(model_keys)
    if model_key is None:
        raise ValueError("model_key or model_keys is required")
    if n_replicas < 1:
        raise ValueError("n_replicas must be >= 1")
    return [model_key] * n_replicas


def ensemble_model_label(model_keys: list[str]) -> str:
    """Stable batch tag / display label for a heterogeneous replica set."""
    return "+".join(model_keys)


@dataclass
class ParallelRunResult:
    question_id: int
    db_id: str
    model_key: str
    policy: CoordinationPolicy
    n_replicas: int
    replica_model_keys: list[str] = field(default_factory=list)
    replicas: list[AgentRunResult] = field(default_factory=list)
    chosen: AgentRunResult | None = None
    redundancy: RedundancyMetrics | None = None
    interaction_metrics: InteractionMetrics | None = None
    coord_trace_path: Path | None = None
    completion_order: list[int] = field(default_factory=list)
    early_stop: bool = False
    early_stop_triggered: bool = False
    replicas_cancelled: int = 0
    shared_cache: bool = False
    cache_stats: SqlCacheStats | None = None
    discovery_board: bool = False
    discovery_stats: DiscoveryStats | None = None
    semantic_store: bool = False
    semantic_stats: SemanticStoreStats | None = None
    prompt_cache: bool = False
    replica_schedule: ReplicaScheduleConfig | None = None

    @property
    def total_cached_prompt_tokens(self) -> int:
        return self.redundancy.total_cached_prompt_tokens if self.redundancy else 0

    @property
    def ex_correct(self) -> int:
        return self.chosen.ex_correct if self.chosen else 0

    @property
    def final_sql(self) -> str | None:
        return self.chosen.final_sql if self.chosen else None


class CoordinationTrace:
    """JSONL trace for a parallel coordination session (runs/<coord_id>.jsonl)."""

    def __init__(
        self,
        *,
        cfg: ProjectConfig,
        task: BirdTask,
        policy: str,
        model_key: str,
        n_replicas: int,
        replica_model_keys: list[str] | None = None,
        runs_dir: Path | None = None,
        coord_id: str | None = None,
        early_stop: bool = False,
        shared_cache: bool = False,
        discovery_board: bool = False,
        semantic_store: bool = False,
        prompt_cache: bool = False,
        trace_policy: str = TRACE_POLICY_PARALLEL,
        replica_schedule: ReplicaScheduleConfig | None = None,
    ) -> None:
        self.cfg = cfg
        self.coord_id = coord_id or uuid.uuid4().hex[:12]
        base = runs_dir or cfg.runs_dir
        base.mkdir(parents=True, exist_ok=True)
        self.path = base / f"coord_{self.coord_id}.jsonl"
        self._started_at = time.perf_counter()
        self._append(
            {
                "event": "parallel_start",
                "coord_id": self.coord_id,
                "ts": _utc_now_iso(),
                "question_id": task.question_id,
                "db_id": task.db_id,
                "policy": policy,
                "trace_policy": trace_policy,
                "early_stop": early_stop,
                "shared_cache": shared_cache,
                "discovery_board": discovery_board,
                "semantic_store": semantic_store,
                "prompt_cache": prompt_cache,
                "replica_schedule": replica_schedule.to_dict() if replica_schedule else None,
                "model": model_key,
                "replica_model_keys": replica_model_keys or [model_key] * n_replicas,
                "n_replicas": n_replicas,
                "bird_split": cfg.bird_split,
                "seed": cfg.seed,
            }
        )

    def _append(self, event: dict[str, Any]) -> None:
        line = json.dumps(_json_safe(event), ensure_ascii=False)
        with self.path.open("a", encoding="utf-8") as f:
            f.write(line + "\n")

    def log_replica_start(self, profile: ReplicaProfile, *, model_key: str) -> None:
        self._append(
            {
                "event": "replica_start",
                "coord_id": self.coord_id,
                "ts": _utc_now_iso(),
                "agent_id": f"agent_{profile.agent_idx}",
                "model": model_key,
                **profile.to_dict(),
            }
        )

    def log_replica_complete(
        self,
        replica: AgentRunResult,
        *,
        agent_idx: int,
        finish_rank: int,
        model_key: str,
    ) -> None:
        self._append(
            {
                "event": "replica_end",
                "coord_id": self.coord_id,
                "ts": _utc_now_iso(),
                "agent_id": f"agent_{agent_idx}",
                "model": model_key,
                "finish_rank": finish_rank,
                "trace_path": str(replica.trace_path),
                "ex_correct": replica.ex_correct,
                "turns": replica.turns,
                "stop_reason": replica.stop_reason,
                "prompt_tokens": replica.total_prompt_tokens,
                "completion_tokens": replica.total_completion_tokens,
                "cached_prompt_tokens": getattr(replica, "total_cached_prompt_tokens", 0),
                "error": replica.error,
            }
        )

    def log_early_stop(self, *, winner_agent_idx: int) -> None:
        self._append(
            {
                "event": "early_stop",
                "coord_id": self.coord_id,
                "ts": _utc_now_iso(),
                "winner_agent_id": f"agent_{winner_agent_idx}",
            }
        )

    def finish(
        self,
        *,
        chosen: AgentRunResult,
        redundancy: RedundancyMetrics,
        completion_order: list[int],
        early_stop_triggered: bool = False,
        replicas_cancelled: int = 0,
        cache_stats: dict[str, Any] | None = None,
        discovery_stats: dict[str, Any] | None = None,
        semantic_stats: dict[str, Any] | None = None,
        interaction_metrics: dict[str, Any] | None = None,
    ) -> None:
        wall_ms = int((time.perf_counter() - self._started_at) * 1000)
        event: dict[str, Any] = {
            "event": "coordination_end",
            "coord_id": self.coord_id,
            "ts": _utc_now_iso(),
            "chosen_trace_path": str(chosen.trace_path),
            "chosen_ex_correct": chosen.ex_correct,
            "chosen_final_sql": chosen.final_sql,
            "completion_order": completion_order,
            "early_stop_triggered": early_stop_triggered,
            "replicas_cancelled": replicas_cancelled,
            "wall_clock_ms": wall_ms,
            "redundancy": redundancy.to_dict(),
        }
        if cache_stats is not None:
            event["cache_stats"] = cache_stats
        if discovery_stats is not None:
            event["discovery_stats"] = discovery_stats
        if semantic_stats is not None:
            event["semantic_stats"] = semantic_stats
        if interaction_metrics is not None:
            event["interaction_metrics"] = interaction_metrics
        self._append(event)


def run_parallel_agents(
    task: BirdTask,
    model_key: str | None = None,
    *,
    model_keys: list[str] | None = None,
    n_replicas: int = 3,
    policy: CoordinationPolicy = CoordinationPolicy.BEST_OF_N,
    cfg: ProjectConfig | None = None,
    max_workers: int | None = None,
    write_coord_trace: bool = True,
    early_stop: bool = False,
    shared_cache: bool = False,
    discovery_board: bool = False,
    semantic_store: bool = False,
    prompt_cache: bool = False,
    explore_suppressor: bool = False,
    sql_cache_max_entries: int | None = None,
    discovery_max_fragments: int | None = None,
    semantic_store_max_entries: int | None = None,
    replica_schedule: ReplicaScheduleConfig | None = None,
) -> ParallelRunResult:
    """
    Run N replicas in parallel on the same task, then apply a coordination policy.

    Per-replica trace policy (``resolve_trace_policy``):
    - ``P0_parallel`` — independent replicas
    - ``P0_early_stop`` — siblings cancelled after first EX=1
    - ``P1_shared_cache`` — shared LRU SQL result cache for explore queries
    - ``P2_subexpr_propagation`` — shared discovery board (prompt injection)
    - ``P1_P2_combined`` — both P1 cache and P2 discovery board

    With ``early_stop=True``, remaining replicas stop at the next turn boundary once
    any replica submits a final SQL answer with execution accuracy EX=1.

    With ``shared_cache=True``, explore-phase SQL is deduplicated via an AST-keyed
    LRU cache shared across replicas on this task.

    With ``semantic_store=True``, explore results are distilled into bounded
    natural-language facts injected before each LLM turn (P3).
    """
    replica_model_keys = resolve_replica_model_keys(
        model_key=model_key,
        model_keys=model_keys,
        n_replicas=n_replicas,
    )
    n_replicas = len(replica_model_keys)
    display_model_key = (
        ensemble_model_label(replica_model_keys)
        if len(set(replica_model_keys)) > 1
        else replica_model_keys[0]
    )

    cfg = cfg or load_config()
    workers = max_workers or n_replicas
    schedule = replica_schedule or schedule_from_config(cfg)
    # Prompt cache: opt into the Zone-1-frozen, cache-aware loop. Default-off keeps the
    # baseline replica path (src.agent.loop.run_agent) byte-for-byte unchanged.
    if prompt_cache:
        from src.agent.loop_cached import run_agent as run_replica_agent
    else:
        run_replica_agent = run_agent
    trace_policy = resolve_trace_policy(
        shared_cache=shared_cache,
        early_stop=early_stop,
        discovery_board=discovery_board,
        semantic_store=semantic_store,
    )
    coord_cfg = cfg.raw.get("coordination", {})
    store_cfg = cfg.semantic_store_config
    max_entries = sql_cache_max_entries or int(coord_cfg.get("sql_cache_max_entries", 4096))
    max_fragments = discovery_max_fragments or int(coord_cfg.get("discovery_max_fragments", 256))
    max_semantic = semantic_store_max_entries or int(store_cfg.get("max_entries", 128))
    sql_cache = SharedSqlResultCache(max_entries=max_entries) if shared_cache else None
    board = SharedDiscoveryBoard(max_fragments=max_fragments) if discovery_board else None
    # P4 explore suppression rides the cache-aware loop (its hook lives there), so it
    # only activates with prompt_cache. When off, replica kwargs are unchanged.
    suppressor = None
    if explore_suppressor and prompt_cache:
        from src.coord.explore_suppressor import StructuralExploreSuppressor

        suppressor = StructuralExploreSuppressor(
            max_suppressions=cfg.explore_suppressor_max_suppressions
        )
    supp_kwargs = {"explore_suppressor": suppressor} if suppressor is not None else {}
    store = (
        SharedSemanticStore(
            max_entries=max_semantic,
            max_inject_chars=int(store_cfg.get("max_inject_chars", 500)),
            max_inject_bullets=int(store_cfg.get("max_inject_bullets", 8)),
        )
        if semantic_store
        else None
    )

    if n_replicas == 1:
        single_profile = resolve_replica_profile(schedule, agent_idx=0)
        single = run_replica_agent(
            task,
            replica_model_keys[0],
            cfg,
            policy=trace_policy,
            agent_id="agent_0",
            sql_cache=sql_cache,
            discovery_board=board,
            semantic_store=store,
            temperature=single_profile.temperature,
            start_delay_seconds=single_profile.start_delay_seconds,
            start_turn_delay=single_profile.start_turn_delay,
            stagger_poll_seconds=schedule.stagger_poll_seconds,
            **supp_kwargs,
        )
        redundancy = compute_redundancy([single])
        interactions = compute_interaction_metrics([single])
        return ParallelRunResult(
            question_id=task.question_id,
            db_id=task.db_id,
            model_key=display_model_key,
            policy=policy,
            n_replicas=1,
            replica_model_keys=replica_model_keys,
            replicas=[single],
            chosen=single,
            redundancy=redundancy,
            interaction_metrics=interactions,
            completion_order=[0],
            early_stop=early_stop,
            shared_cache=shared_cache,
            cache_stats=sql_cache.stats if sql_cache else None,
            discovery_board=discovery_board,
            discovery_stats=board.stats if board else None,
            semantic_store=semantic_store,
            semantic_stats=store.stats if store else None,
            prompt_cache=prompt_cache,
            replica_schedule=schedule,
        )

    cancel_event = threading.Event() if early_stop else None
    early_stop_triggered = False

    coord_trace: CoordinationTrace | None = None
    if write_coord_trace:
        coord_trace = CoordinationTrace(
            cfg=cfg,
            task=task,
            policy=policy.value,
            model_key=display_model_key,
            n_replicas=n_replicas,
            replica_model_keys=replica_model_keys,
            early_stop=early_stop,
            shared_cache=shared_cache,
            discovery_board=discovery_board,
            semantic_store=semantic_store,
            prompt_cache=prompt_cache,
            trace_policy=trace_policy,
            replica_schedule=schedule,
        )

    def _run_replica(idx: int) -> tuple[int, AgentRunResult]:
        replica_key = replica_model_keys[idx]
        profile = resolve_replica_profile(schedule, agent_idx=idx)
        if coord_trace is not None:
            coord_trace.log_replica_start(profile, model_key=replica_key)
        result = run_replica_agent(
            task,
            replica_key,
            cfg,
            policy=trace_policy,
            agent_id=f"agent_{idx}",
            cancel_event=cancel_event,
            sql_cache=sql_cache,
            discovery_board=board,
            semantic_store=store,
            temperature=profile.temperature,
            start_delay_seconds=profile.start_delay_seconds,
            start_turn_delay=profile.start_turn_delay,
            stagger_poll_seconds=schedule.stagger_poll_seconds,
            **supp_kwargs,
        )
        return idx, result

    replicas: list[AgentRunResult | None] = [None] * n_replicas
    completion_order: list[int] = []
    finish_rank = 0

    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures = {pool.submit(_run_replica, i): i for i in range(n_replicas)}
        for fut in as_completed(futures):
            idx, result = fut.result()
            replicas[idx] = result
            completion_order.append(idx)
            if coord_trace is not None:
                coord_trace.log_replica_complete(
                    result,
                    agent_idx=idx,
                    finish_rank=finish_rank,
                    model_key=replica_model_keys[idx],
                )
            finish_rank += 1

            if (
                early_stop
                and cancel_event is not None
                and result.ex_correct == 1
                and not cancel_event.is_set()
            ):
                cancel_event.set()
                early_stop_triggered = True
                if coord_trace is not None:
                    coord_trace.log_early_stop(winner_agent_idx=idx)

    filled = [r for r in replicas if r is not None]
    replicas_cancelled = sum(1 for r in filled if r.stop_reason == "cancelled_early")
    outcomes = enrich_outcomes(task, filled, cfg)
    chosen = select_replica(policy, outcomes, completion_order=completion_order)
    redundancy = compute_redundancy(filled)
    interactions = compute_interaction_metrics(filled)

    if coord_trace is not None:
        coord_trace.finish(
            chosen=chosen,
            redundancy=redundancy,
            completion_order=completion_order,
            early_stop_triggered=early_stop_triggered,
            replicas_cancelled=replicas_cancelled,
            cache_stats=sql_cache.stats.to_dict() if sql_cache else None,
            discovery_stats=board.stats.to_dict() if board else None,
            semantic_stats=store.stats.to_dict() if store else None,
            interaction_metrics=interactions.to_dict(),
        )

    return ParallelRunResult(
        question_id=task.question_id,
        db_id=task.db_id,
        model_key=display_model_key,
        policy=policy,
        n_replicas=n_replicas,
        replica_model_keys=replica_model_keys,
        replicas=filled,
        chosen=chosen,
        redundancy=redundancy,
        interaction_metrics=interactions,
        coord_trace_path=coord_trace.path if coord_trace else None,
        completion_order=completion_order,
        early_stop=early_stop,
        early_stop_triggered=early_stop_triggered,
        replicas_cancelled=replicas_cancelled,
        shared_cache=shared_cache,
        cache_stats=sql_cache.stats if sql_cache else None,
        discovery_board=discovery_board,
        discovery_stats=board.stats if board else None,
        semantic_store=semantic_store,
        semantic_stats=store.stats if store else None,
        prompt_cache=prompt_cache,
        replica_schedule=schedule,
    )
