"""Aggregate and persist batch run results."""

from __future__ import annotations

import csv
import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path


@dataclass
class BatchRow:
    question_id: int
    db_id: str
    difficulty: str
    model_key: str
    ex_correct: int
    turns: int
    stop_reason: str
    prompt_tokens: int
    completion_tokens: int
    trace_path: str
    error: str | None = None


@dataclass
class BatchSummary:
    batch_id: str
    model_key: str
    bird_split: str
    task_count: int
    rows: list[BatchRow] = field(default_factory=list)

    @property
    def ex_accuracy_pct(self) -> float:
        if not self.rows:
            return 0.0
        return 100.0 * sum(r.ex_correct for r in self.rows) / len(self.rows)

    @property
    def avg_turns(self) -> float:
        if not self.rows:
            return 0.0
        return sum(r.turns for r in self.rows) / len(self.rows)

    @property
    def total_prompt_tokens(self) -> int:
        return sum(r.prompt_tokens for r in self.rows)

    @property
    def total_completion_tokens(self) -> int:
        return sum(r.completion_tokens for r in self.rows)

    def add_from_agent_result(self, row: BatchRow) -> None:
        self.rows.append(row)


def write_batch_csv(path: Path, summary: BatchSummary) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = [
        "question_id",
        "db_id",
        "difficulty",
        "model_key",
        "ex_correct",
        "turns",
        "stop_reason",
        "prompt_tokens",
        "completion_tokens",
        "trace_path",
        "error",
    ]
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for row in summary.rows:
            writer.writerow(
                {
                    "question_id": row.question_id,
                    "db_id": row.db_id,
                    "difficulty": row.difficulty,
                    "model_key": row.model_key,
                    "ex_correct": row.ex_correct,
                    "turns": row.turns,
                    "stop_reason": row.stop_reason,
                    "prompt_tokens": row.prompt_tokens,
                    "completion_tokens": row.completion_tokens,
                    "trace_path": row.trace_path,
                    "error": row.error or "",
                }
            )


def write_batch_json(path: Path, summary: BatchSummary) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "batch_id": summary.batch_id,
        "model_key": summary.model_key,
        "bird_split": summary.bird_split,
        "task_count": summary.task_count,
        "ex_accuracy_pct": round(summary.ex_accuracy_pct, 2),
        "avg_turns": round(summary.avg_turns, 2),
        "total_prompt_tokens": summary.total_prompt_tokens,
        "total_completion_tokens": summary.total_completion_tokens,
        "rows": [
            {
                "question_id": r.question_id,
                "db_id": r.db_id,
                "difficulty": r.difficulty,
                "ex_correct": r.ex_correct,
                "turns": r.turns,
                "stop_reason": r.stop_reason,
                "prompt_tokens": r.prompt_tokens,
                "completion_tokens": r.completion_tokens,
                "trace_path": r.trace_path,
                "error": r.error,
            }
            for r in summary.rows
        ],
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def load_batch_json(path: Path) -> dict:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict) or "rows" not in data:
        raise ValueError(f"Invalid batch JSON: {path}")
    return data


def failed_question_ids_from_batch(path: Path) -> list[int]:
    """Question IDs of tasks that raised an exception in a prior batch (for --retry-from).

    run_batch records ``stop_reason="error"`` only when a task raises (API/transport
    errors, timeouts); the agent loop handles SQL errors internally as turns. So an
    error row is exactly a task worth re-running.
    """
    data = load_batch_json(path)
    ids: list[int] = []
    for row in data["rows"]:
        if not isinstance(row, dict):
            continue
        if str(row.get("stop_reason", "")) == "error":
            ids.append(int(row["question_id"]))
    return ids


def print_batch_summary(summary: BatchSummary) -> None:
    print()
    print(f"Batch {summary.batch_id} ({summary.model_key})")
    print(f"  Tasks:      {len(summary.rows)} / {summary.task_count}")
    print(f"  EX:         {summary.ex_accuracy_pct:.1f}%")
    print(f"  Avg turns:  {summary.avg_turns:.2f}")
    print(f"  Tokens:     prompt={summary.total_prompt_tokens} completion={summary.total_completion_tokens}")
