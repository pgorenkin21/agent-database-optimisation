"""Single-agent text-to-SQL loop with tool calling and JSONL tracing."""

from __future__ import annotations

import threading
import time
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any

from src.agent.prompt import (
    apply_discovery_context,
    apply_semantic_context,
    build_initial_messages,
    build_task_user_message,
    format_discovery_context,
    format_semantic_context,
)
from src.agent.schema import build_schema_context, list_user_tables
from src.agent.sql_utils import (
    format_sql_feedback,
    is_sqlite_missing_table_error,
    strip_sql_markdown,
    validate_read_only_sql,
)
from src.bird.tasks import BirdTask, sqlite_path_for_task
from src.config import ProjectConfig, load_config
from src.coord.replica_schedule import wait_turns_with_cancel, wait_with_cancel
from src.db.sqlite_exec import execute_sql
from src.db.shared_sql_cache import SharedSqlResultCache
from src.eval.execution_accuracy import compare_result_sets
from src.llm.chat import ChatResponse, create_chat_backend
from src.llm.models import ModelSpec, load_model_registry
from src.logging.trace import RunTrace

if TYPE_CHECKING:
    from src.coord.shared_discovery import SharedDiscoveryBoard
    from src.coord.semantic_store import SharedSemanticStore


@dataclass
class AgentRunResult:
    question_id: int
    db_id: str
    model_key: str
    final_sql: str | None
    ex_correct: int
    turns: int
    trace_path: Path
    total_prompt_tokens: int
    total_completion_tokens: int
    stop_reason: str
    error: str | None = None


def _tool_result_message(tool_call_id: str | None, name: str, content: str) -> dict[str, Any]:
    return {
        "role": "tool",
        "tool_call_id": tool_call_id or name,
        "name": name,
        "content": content,
    }


def _finish_agent_run(
    *,
    task: BirdTask,
    model_key: str,
    trace: RunTrace,
    cfg: ProjectConfig,
    db_path: Path,
    final_sql: str | None,
    stop_reason: str,
    turns: int,
    total_prompt: int,
    total_completion: int,
    last_error: str | None,
    gold_rows_cache: list[tuple[Any, ...]] | None,
) -> AgentRunResult:
    ex = 0
    match = False
    if final_sql:
        try:
            timeout = float(cfg.query_timeout_seconds)
            pred_rows = execute_sql(db_path, final_sql, timeout_seconds=timeout)
            gold_rows_cache = gold_rows_cache or execute_sql(
                db_path, task.gold_sql, timeout_seconds=timeout
            )
            match = compare_result_sets(pred_rows, gold_rows_cache)
            ex = 1 if match else 0
        except Exception as e:
            last_error = str(e)

    trace.finish(
        predicted_sql=final_sql or "",
        gold_sql=task.gold_sql,
        ex_correct=ex,
        match=match,
        extra={
            "turns": turns,
            "stop_reason": stop_reason,
            "total_prompt_tokens": total_prompt,
            "total_completion_tokens": total_completion,
        },
    )
    return AgentRunResult(
        question_id=task.question_id,
        db_id=task.db_id,
        model_key=model_key,
        final_sql=final_sql,
        ex_correct=ex,
        turns=turns,
        trace_path=trace.path,
        total_prompt_tokens=total_prompt,
        total_completion_tokens=total_completion,
        stop_reason=stop_reason,
        error=last_error,
    )


def run_agent(
    task: BirdTask,
    model_key: str,
    cfg: ProjectConfig | None = None,
    *,
    spec: ModelSpec | None = None,
    trace: RunTrace | None = None,
    policy: str = "P0",
    agent_id: str = "agent_0",
    cancel_event: threading.Event | None = None,
    sql_cache: SharedSqlResultCache | None = None,
    discovery_board: SharedDiscoveryBoard | None = None,
    semantic_store: SharedSemanticStore | None = None,
    temperature: float | None = None,
    start_delay_seconds: float = 0.0,
    start_turn_delay: int = 0,
    stagger_poll_seconds: float = 1.0,
) -> AgentRunResult:
    cfg = cfg or load_config()
    registry = load_model_registry(cfg.models_config_path)
    spec = spec or registry.get(model_key)
    llm_temperature = cfg.llm_temperature if temperature is None else float(temperature)

    db_path = sqlite_path_for_task(task, cfg)
    schema_pruning_meta: dict[str, object] | None = None
    schema_context = build_schema_context(db_path, cfg.databases_dir, task.db_id)
    schema_pruning_active = False
    schema_runtime_fallback = False
    if cfg.schema_pruning:
        from src.agent.schema_pruning import build_pruned_schema_context

        pruned = build_pruned_schema_context(
            task,
            db_path,
            cfg.databases_dir,
            mode=cfg.schema_pruning_mode,
            semantic_min_score=cfg.schema_pruning_semantic_min_score,
        )
        schema_context = pruned.schema_context
        schema_pruning_active = pruned.pruning_applied
        schema_pruning_meta = {
            "selected_tables": list(pruned.selected_tables),
            "full_chars": pruned.full_chars,
            "pruned_chars": pruned.pruned_chars,
            "reduction_pct": round(pruned.reduction_pct, 2),
            "pruning_applied": pruned.pruning_applied,
            "fallback_reason": pruned.fallback_reason,
            "pruning_mode": pruned.pruning_mode,
        }
    messages = build_initial_messages(
        task, schema_context, use_evidence=cfg.use_evidence
    )

    if trace is None:
        trace = RunTrace(
            cfg=cfg,
            question_id=task.question_id,
            db_id=task.db_id,
            policy=policy,
            model=model_key,
            agent_id=agent_id,
            sql_cache=sql_cache,
            temperature=llm_temperature,
            start_delay_seconds=start_delay_seconds,
            start_turn_delay=start_turn_delay,
        )

    if schema_pruning_meta is not None:
        trace.log_schema_pruning(
            selected_tables=list(schema_pruning_meta["selected_tables"]),  # type: ignore[arg-type]
            full_chars=int(schema_pruning_meta["full_chars"]),  # type: ignore[arg-type]
            pruned_chars=int(schema_pruning_meta["pruned_chars"]),  # type: ignore[arg-type]
            reduction_pct=float(schema_pruning_meta["reduction_pct"]),  # type: ignore[arg-type]
            pruning_applied=bool(schema_pruning_meta["pruning_applied"]),
            fallback_reason=schema_pruning_meta.get("fallback_reason"),  # type: ignore[arg-type]
            pruning_mode=str(schema_pruning_meta.get("pruning_mode", "keyword")),
        )

    backend = create_chat_backend(
        spec,
        retry=cfg.llm_retry_config(),
        request_timeout_seconds=cfg.llm_request_timeout_seconds,
        temperature=llm_temperature,
    )
    timeout = float(cfg.query_timeout_seconds)
    max_sample_rows = 10

    stagger_started = time.perf_counter()
    if start_delay_seconds > 0 and wait_with_cancel(
        start_delay_seconds,
        cancel_event,
        poll_seconds=min(0.25, stagger_poll_seconds),
    ):
        return _finish_agent_run(
            task=task,
            model_key=model_key,
            trace=trace,
            cfg=cfg,
            db_path=db_path,
            final_sql=None,
            stop_reason="cancelled_early",
            turns=0,
            total_prompt=0,
            total_completion=0,
            last_error=None,
            gold_rows_cache=None,
        )
    if start_turn_delay > 0 and wait_turns_with_cancel(
        start_turn_delay,
        cancel_event,
        poll_seconds=stagger_poll_seconds,
    ):
        return _finish_agent_run(
            task=task,
            model_key=model_key,
            trace=trace,
            cfg=cfg,
            db_path=db_path,
            final_sql=None,
            stop_reason="cancelled_early",
            turns=0,
            total_prompt=0,
            total_completion=0,
            last_error=None,
            gold_rows_cache=None,
        )
    if start_delay_seconds > 0 or start_turn_delay > 0:
        trace.log_stagger_complete(
            waited_seconds=round(time.perf_counter() - stagger_started, 3),
        )

    total_prompt = 0
    total_completion = 0
    final_sql: str | None = None
    stop_reason = "max_turns"
    last_error: str | None = None

    gold_rows_cache: list[tuple[Any, ...]] | None = None

    for turn in range(cfg.max_turns):
        if cancel_event is not None and cancel_event.is_set():
            return _finish_agent_run(
                task=task,
                model_key=model_key,
                trace=trace,
                cfg=cfg,
                db_path=db_path,
                final_sql=final_sql,
                stop_reason="cancelled_early",
                turns=turn,
                total_prompt=total_prompt,
                total_completion=total_completion,
                last_error=last_error,
                gold_rows_cache=gold_rows_cache,
            )

        if discovery_board is not None:
            peer_frags = discovery_board.peer_fragments(agent_id)
            discovery_ctx = format_discovery_context(peer_frags)
            apply_discovery_context(messages, discovery_ctx)
            if discovery_ctx:
                discovery_board.record_context_injection(fragment_count=len(peer_frags))
                trace.log_discovery_injection(turn_idx=turn, fragment_count=len(peer_frags))

        if semantic_store is not None:
            peer_facts = semantic_store.peer_facts(agent_id)
            semantic_ctx = format_semantic_context(peer_facts)
            apply_semantic_context(messages, semantic_ctx)
            if semantic_ctx:
                semantic_store.record_context_injection(
                    fact_count=len(peer_facts),
                    char_count=len(semantic_ctx),
                )
                trace.log_semantic_injection(
                    turn_idx=turn,
                    fact_count=len(peer_facts),
                    char_count=len(semantic_ctx),
                )

        response: ChatResponse = backend.complete(messages)
        if cancel_event is not None and cancel_event.is_set():
            if response.prompt_tokens:
                total_prompt += response.prompt_tokens
            if response.completion_tokens:
                total_completion += response.completion_tokens
            return _finish_agent_run(
                task=task,
                model_key=model_key,
                trace=trace,
                cfg=cfg,
                db_path=db_path,
                final_sql=final_sql,
                stop_reason="cancelled_early",
                turns=turn + 1,
                total_prompt=total_prompt,
                total_completion=total_completion,
                last_error=last_error,
                gold_rows_cache=gold_rows_cache,
            )
        if response.prompt_tokens:
            total_prompt += response.prompt_tokens
        if response.completion_tokens:
            total_completion += response.completion_tokens

        if cfg.raw["logging"].get("log_llm_messages", False):
            trace.log_llm_turn(
                turn_idx=turn,
                prompt_tokens=response.prompt_tokens,
                completion_tokens=response.completion_tokens,
                tool_calls=[tc.name for tc in response.tool_calls],
            )

        messages.append(response.assistant_message)

        if not response.tool_calls:
            messages.append(
                {
                    "role": "user",
                    "content": "Use execute_sql to explore or submit_sql with your final answer.",
                }
            )
            continue

        submitted = False
        for tc in response.tool_calls:
            sql_raw = str(tc.arguments.get("sql", ""))
            tool_id = tc.id

            if tc.name == "submit_sql":
                try:
                    sql = strip_sql_markdown(sql_raw)
                    if cfg.read_only_sql:
                        validate_read_only_sql(sql)
                    final_sql = sql
                    pred_rows, err, _ = trace.log_sql_execute(
                        sql=sql,
                        sql_role="final",
                        db_path=db_path,
                        timeout_seconds=timeout,
                        turn_idx=turn,
                    )
                    if gold_rows_cache is None:
                        gold_rows_cache = execute_sql(
                            db_path, task.gold_sql, timeout_seconds=timeout
                        )
                    if err:
                        last_error = str(err)
                        ex = 0
                        match = False
                    else:
                        match = compare_result_sets(pred_rows or [], gold_rows_cache or [])
                        ex = 1 if match else 0

                    trace.finish(
                        predicted_sql=sql,
                        gold_sql=task.gold_sql,
                        ex_correct=ex,
                        match=match,
                        extra={
                            "turns": turn + 1,
                            "stop_reason": "submit_sql",
                            "total_prompt_tokens": total_prompt,
                            "total_completion_tokens": total_completion,
                        },
                    )
                    return AgentRunResult(
                        question_id=task.question_id,
                        db_id=task.db_id,
                        model_key=model_key,
                        final_sql=final_sql,
                        ex_correct=ex,
                        turns=turn + 1,
                        trace_path=trace.path,
                        total_prompt_tokens=total_prompt,
                        total_completion_tokens=total_completion,
                        stop_reason="submit_sql",
                        error=last_error,
                    )
                except ValueError as e:
                    feedback = str(e)
                    messages.append(_tool_result_message(tool_id, tc.name, feedback))
                submitted = True
                break

            if tc.name == "execute_sql":
                try:
                    sql = strip_sql_markdown(sql_raw)
                    if cfg.read_only_sql:
                        validate_read_only_sql(sql)
                    rows, err, cache_hit = trace.log_sql_execute(
                        sql=sql,
                        sql_role="explore",
                        db_path=db_path,
                        timeout_seconds=timeout,
                        turn_idx=turn,
                    )
                    err_text = str(err) if err else None
                    if (
                        schema_pruning_active
                        and not schema_runtime_fallback
                        and is_sqlite_missing_table_error(err_text)
                    ):
                        schema_context = build_schema_context(
                            db_path, cfg.databases_dir, task.db_id
                        )
                        messages[1] = {
                            "role": "user",
                            "content": build_task_user_message(
                                task,
                                schema_context,
                                use_evidence=cfg.use_evidence,
                            ),
                        }
                        schema_runtime_fallback = True
                        schema_pruning_active = False
                        trace.log_schema_pruning(
                            selected_tables=list_user_tables(db_path),
                            full_chars=len(schema_context),
                            pruned_chars=len(schema_context),
                            reduction_pct=0.0,
                            pruning_applied=False,
                            fallback_reason="runtime_missing_table",
                        )
                    feedback = format_sql_feedback(
                        rows,
                        err_text,
                        max_rows=max_sample_rows,
                        cache_hit=cache_hit,
                    )
                    if schema_runtime_fallback and err_text:
                        feedback = (
                            f"{feedback}\n\n"
                            "[System: Full database schema restored after a missing-table "
                            "SQL error. Re-run your query with the complete schema above.]"
                        )
                    if discovery_board is not None:
                        discovery_board.publish(
                            agent_id=agent_id,
                            sql=sql,
                            row_count=len(rows) if rows is not None else 0,
                            error=str(err) if err else None,
                        )
                    if semantic_store is not None:
                        semantic_store.publish(
                            agent_id=agent_id,
                            sql=sql,
                            rows=rows,
                            error=str(err) if err else None,
                        )
                except ValueError as e:
                    feedback = str(e)
                    rows, err = None, None

                messages.append(_tool_result_message(tool_id, tc.name, feedback))
            else:
                messages.append(
                    _tool_result_message(tool_id, tc.name, f"Unknown tool: {tc.name}")
                )

        if submitted:
            break

    return _finish_agent_run(
        task=task,
        model_key=model_key,
        trace=trace,
        cfg=cfg,
        db_path=db_path,
        final_sql=final_sql,
        stop_reason=stop_reason,
        turns=cfg.max_turns,
        total_prompt=total_prompt,
        total_completion=total_completion,
        last_error=last_error or "max_turns without submit_sql",
        gold_rows_cache=gold_rows_cache,
    )
