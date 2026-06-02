"""Single-agent text-to-SQL loop with tool calling and JSONL tracing."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from src.agent.prompt import build_initial_messages
from src.agent.schema import build_schema_context
from src.agent.sql_utils import format_sql_feedback, strip_sql_markdown, validate_read_only_sql
from src.bird.tasks import BirdTask, sqlite_path_for_task
from src.config import ProjectConfig, load_config
from src.db.sqlite_exec import execute_sql
from src.eval.execution_accuracy import compare_result_sets
from src.llm.chat import ChatResponse, create_chat_backend
from src.llm.models import ModelSpec, load_model_registry
from src.logging.trace import RunTrace


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


def run_agent(
    task: BirdTask,
    model_key: str,
    cfg: ProjectConfig | None = None,
    *,
    spec: ModelSpec | None = None,
    trace: RunTrace | None = None,
) -> AgentRunResult:
    cfg = cfg or load_config()
    registry = load_model_registry(cfg.models_config_path)
    spec = spec or registry.get(model_key)

    db_path = sqlite_path_for_task(task, cfg)
    schema = build_schema_context(db_path, cfg.databases_dir, task.db_id)
    messages = build_initial_messages(task, schema, use_evidence=cfg.use_evidence)

    if trace is None:
        trace = RunTrace(
            cfg=cfg,
            question_id=task.question_id,
            db_id=task.db_id,
            policy="P0",
            model=model_key,
            agent_id="agent_0",
        )

    backend = create_chat_backend(spec, retry=cfg.llm_retry_config())
    timeout = float(cfg.query_timeout_seconds)
    max_sample_rows = 10

    total_prompt = 0
    total_completion = 0
    final_sql: str | None = None
    stop_reason = "max_turns"
    last_error: str | None = None

    gold_rows_cache: list[tuple[Any, ...]] | None = None

    for turn in range(cfg.max_turns):
        response: ChatResponse = backend.complete(messages)
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
                    pred_rows, err = trace.log_sql_execute(
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
                    rows, err = trace.log_sql_execute(
                        sql=sql,
                        sql_role="explore",
                        db_path=db_path,
                        timeout_seconds=timeout,
                        turn_idx=turn,
                    )
                    feedback = format_sql_feedback(
                        rows,
                        str(err) if err else None,
                        max_rows=max_sample_rows,
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

    ex = 0
    match = False
    if final_sql:
        try:
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
            "turns": cfg.max_turns,
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
        turns=cfg.max_turns,
        trace_path=trace.path,
        total_prompt_tokens=total_prompt,
        total_completion_tokens=total_completion,
        stop_reason=stop_reason,
        error=last_error or "max_turns without submit_sql",
    )
