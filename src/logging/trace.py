"""Append-only JSONL traces for SQL runs and (later) agent turns."""

from __future__ import annotations

import json
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator

from src.config import ProjectConfig
from src.db.sqlite_exec import SqlExecutionError, execute_sql


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _json_safe(value: Any) -> Any:
    if value is None or isinstance(value, (bool, int, float, str)):
        return value
    if isinstance(value, (list, tuple)):
        return [_json_safe(v) for v in value]
    if isinstance(value, dict):
        return {str(k): _json_safe(v) for k, v in value.items()}
    return str(value)


def _sample_rows(rows: list[tuple[Any, ...]], limit: int) -> list[list[Any]]:
    out: list[list[Any]] = []
    for row in rows[:limit]:
        out.append([_json_safe(v) for v in row])
    return out


@dataclass
class RunTrace:
    """
    Write a single run trace to runs/<run_id>.jsonl.

    Events: run_start, sql_execute (repeatable), run_end.
    """

    cfg: ProjectConfig
    question_id: int
    db_id: str
    policy: str = "P0"
    model: str | None = None
    agent_id: str | None = None
    runs_dir: Path | None = None
    run_id: str = field(default_factory=lambda: uuid.uuid4().hex[:12])
    _seq: int = field(default=0, init=False, repr=False)
    _path: Path | None = field(default=None, init=False, repr=False)
    _started_at: float = field(default_factory=time.perf_counter, init=False, repr=False)

    def __post_init__(self) -> None:
        base = self.runs_dir or self.cfg.runs_dir
        base.mkdir(parents=True, exist_ok=True)
        self._path = base / f"{self.run_id}.jsonl"
        self._append(
            {
                "event": "run_start",
                "run_id": self.run_id,
                "ts": _utc_now_iso(),
                "question_id": self.question_id,
                "db_id": self.db_id,
                "policy": self.policy,
                "model": self.model,
                "agent_id": self.agent_id,
                "seed": self.cfg.seed,
                "bird_split": self.cfg.bird_split,
            }
        )

    @property
    def path(self) -> Path:
        assert self._path is not None
        return self._path

    def _append(self, event: dict[str, Any]) -> None:
        assert self._path is not None
        line = json.dumps(_json_safe(event), ensure_ascii=False)
        with self._path.open("a", encoding="utf-8") as f:
            f.write(line + "\n")

    def log_sql_execute(
        self,
        *,
        sql: str,
        sql_role: str,
        db_path: Path,
        timeout_seconds: float | None = None,
        turn_idx: int = 0,
    ) -> tuple[list[tuple[Any, ...]] | None, SqlExecutionError | None]:
        """Execute SQL, append sql_execute event, return rows or error."""
        timeout = (
            float(timeout_seconds)
            if timeout_seconds is not None
            else float(self.cfg.query_timeout_seconds)
        )
        max_sample = int(self.cfg.raw["database"].get("max_result_rows", 100))

        self._seq += 1
        t0 = time.perf_counter()
        error: SqlExecutionError | None = None
        rows: list[tuple[Any, ...]] | None = None
        status = "ok"

        try:
            rows = execute_sql(db_path, sql, timeout_seconds=timeout)
        except SqlExecutionError as e:
            error = e
            status = "error"

        latency_ms = int((time.perf_counter() - t0) * 1000)
        self._append(
            {
                "event": "sql_execute",
                "run_id": self.run_id,
                "seq": self._seq,
                "ts": _utc_now_iso(),
                "turn_idx": turn_idx,
                "sql_role": sql_role,
                "sql_raw": sql,
                "db_path": str(db_path),
                "exec_status": status,
                "latency_ms": latency_ms,
                "row_count": len(rows) if rows is not None else 0,
                "error": str(error) if error else None,
                "result_sample": _sample_rows(rows, max_sample) if rows is not None else [],
            }
        )
        return rows, error

    def log_llm_turn(
        self,
        *,
        turn_idx: int,
        prompt_tokens: int | None,
        completion_tokens: int | None,
        tool_calls: list[str],
    ) -> None:
        self._append(
            {
                "event": "llm_turn",
                "run_id": self.run_id,
                "ts": _utc_now_iso(),
                "turn_idx": turn_idx,
                "prompt_tokens": prompt_tokens,
                "completion_tokens": completion_tokens,
                "tool_calls": tool_calls,
            }
        )

    def finish(
        self,
        *,
        predicted_sql: str,
        gold_sql: str,
        ex_correct: int,
        match: bool,
        extra: dict[str, Any] | None = None,
    ) -> None:
        wall_ms = int((time.perf_counter() - self._started_at) * 1000)
        event: dict[str, Any] = {
            "event": "run_end",
            "run_id": self.run_id,
            "ts": _utc_now_iso(),
            "question_id": self.question_id,
            "predicted_sql": predicted_sql,
            "gold_sql": gold_sql,
            "ex_correct": ex_correct,
            "match": match,
            "wall_clock_ms": wall_ms,
        }
        if extra:
            event.update(extra)
        self._append(event)


def read_trace_events(path: Path) -> list[dict[str, Any]]:
    events: list[dict[str, Any]] = []
    with path.open(encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                events.append(json.loads(line))
    return events
