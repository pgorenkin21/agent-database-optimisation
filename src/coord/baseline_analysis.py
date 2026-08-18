"""Baseline redundancy analysis for P0 parallel runs (thesis Chapter 2)."""

from __future__ import annotations

import json
import statistics
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from src.coord.redundancy import compute_redundancy, explore_sql_from_trace
from src.db.sql_fragments import extract_sql_fragments
from src.db.sql_normalize import normalize_sql_ast, normalize_sql_string
from src.llm.cost import batch_cost_usd
from src.logging.trace import read_trace_events


def batch_ex_accuracy_stats(rows: list[dict[str, Any]]) -> dict[str, Any]:
    """
    Compute EX accuracy from parallel batch rows.

    API failures (non-empty ``error``) count as EX=0 in the headline metric but
    can be excluded for a completed-tasks-only rate.
    """
    api_failed = [r for r in rows if r.get("error")]
    completed = [r for r in rows if not r.get("error")]
    n = len(rows)
    ex_all = 100.0 * sum(int(r.get("ex_correct", 0)) for r in rows) / n if n else 0.0
    ex_excl: float | None = None
    if completed:
        ex_excl = 100.0 * sum(int(r.get("ex_correct", 0)) for r in completed) / len(completed)
    return {
        "ex_accuracy_pct": round(ex_all, 2),
        "api_failure_count": len(api_failed),
        "completed_task_count": len(completed),
        "ex_accuracy_excluding_api_errors_pct": round(ex_excl, 2) if ex_excl is not None else None,
    }


def _sql_events_from_trace(trace_path: Path) -> list[dict[str, Any]]:
    events: list[dict[str, Any]] = []
    if not trace_path.exists():
        return events
    for ev in read_trace_events(trace_path):
        if ev.get("event") == "sql_execute":
            events.append(ev)
    return events


def _wall_clock_from_trace(trace_path: Path) -> int | None:
    if not trace_path.exists():
        return None
    for ev in read_trace_events(trace_path):
        if ev.get("event") == "run_end":
            ms = ev.get("wall_clock_ms")
            if ms is not None:
                return int(ms)
    return None


@dataclass(frozen=True)
class TaskBaselineMetrics:
    question_id: int
    db_id: str
    difficulty: str
    n_replicas: int
    total_sql_queries: int
    total_explore_queries: int
    unique_explore_string: int
    unique_explore_ast: int
    duplicate_explore_sql: int
    explore_redundancy_pct: float
    subexpr_total: int
    subexpr_shared: int
    subexpr_overlap_pct: float
    wall_clock_ms: int
    time_to_first_success_ms: int | None
    min_replica_wall_ms: int | None
    total_tokens: int
    token_overhead_ratio: float | None
    ex_correct: int
    replicas_ex_correct: int
    total_prompt_tokens: int = 0
    total_completion_tokens: int = 0
    total_cached_prompt_tokens: int = 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "question_id": self.question_id,
            "db_id": self.db_id,
            "difficulty": self.difficulty,
            "n_replicas": self.n_replicas,
            "total_sql_queries": self.total_sql_queries,
            "total_explore_queries": self.total_explore_queries,
            "unique_explore_string": self.unique_explore_string,
            "unique_explore_ast": self.unique_explore_ast,
            "duplicate_explore_sql": self.duplicate_explore_sql,
            "explore_redundancy_pct": round(self.explore_redundancy_pct, 2),
            "subexpr_total": self.subexpr_total,
            "subexpr_shared": self.subexpr_shared,
            "subexpr_overlap_pct": round(self.subexpr_overlap_pct, 2),
            "wall_clock_ms": self.wall_clock_ms,
            "time_to_first_success_ms": self.time_to_first_success_ms,
            "min_replica_wall_ms": self.min_replica_wall_ms,
            "total_tokens": self.total_tokens,
            "total_prompt_tokens": self.total_prompt_tokens,
            "total_completion_tokens": self.total_completion_tokens,
            "total_cached_prompt_tokens": self.total_cached_prompt_tokens,
            "token_overhead_ratio": round(self.token_overhead_ratio, 3)
            if self.token_overhead_ratio is not None
            else None,
            "ex_correct": self.ex_correct,
            "replicas_ex_correct": self.replicas_ex_correct,
        }


@dataclass
class BatchBaselineReport:
    batch_path: str
    batch_id: str
    model_key: str
    bird_split: str
    n_replicas: int
    task_count: int
    ex_accuracy_pct: float
    api_failure_count: int = 0
    completed_task_count: int = 0
    ex_accuracy_excluding_api_errors_pct: float | None = None
    tasks: list[TaskBaselineMetrics] = field(default_factory=list)

    def aggregate(self) -> dict[str, Any]:
        if not self.tasks:
            return {}

        def _mean(vals: list[float]) -> float:
            return statistics.mean(vals) if vals else 0.0

        def _median(vals: list[float]) -> float:
            return statistics.median(vals) if vals else 0.0

        explore_red = [t.explore_redundancy_pct for t in self.tasks]
        subexpr_overlap = [t.subexpr_overlap_pct for t in self.tasks]
        overhead = [t.token_overhead_ratio for t in self.tasks if t.token_overhead_ratio is not None]
        wall = [float(t.wall_clock_ms) for t in self.tasks]
        ttf = [float(t.time_to_first_success_ms) for t in self.tasks if t.time_to_first_success_ms is not None]

        total_sql = sum(t.total_sql_queries for t in self.tasks)
        total_explore = sum(t.total_explore_queries for t in self.tasks)
        unique_explore_str = sum(t.unique_explore_string for t in self.tasks)
        unique_explore_ast = sum(t.unique_explore_ast for t in self.tasks)

        return {
            "task_count": len(self.tasks),
            "ex_accuracy_pct": round(self.ex_accuracy_pct, 2),
            "api_failure_count": self.api_failure_count,
            "completed_task_count": self.completed_task_count,
            "ex_accuracy_excluding_api_errors_pct": self.ex_accuracy_excluding_api_errors_pct,
            "total_sql_queries": total_sql,
            "total_explore_queries": total_explore,
            "unique_explore_string": unique_explore_str,
            "unique_explore_ast": unique_explore_ast,
            "explore_query_uniqueness_pct": round(
                100.0 * unique_explore_str / total_explore if total_explore else 0.0, 2
            ),
            "avg_explore_redundancy_pct": round(_mean(explore_red), 2),
            "median_explore_redundancy_pct": round(_median(explore_red), 2),
            "avg_subexpr_overlap_pct": round(_mean(subexpr_overlap), 2),
            "median_subexpr_overlap_pct": round(_median(subexpr_overlap), 2),
            "avg_token_overhead_ratio": round(_mean(overhead), 3) if overhead else None,
            "avg_wall_clock_ms": round(_mean(wall), 1),
            "median_wall_clock_ms": round(_median(wall), 1),
            "avg_time_to_first_success_ms": round(_mean(ttf), 1) if ttf else None,
            "total_tokens": sum(t.total_tokens for t in self.tasks),
            "total_prompt_tokens": sum(t.total_prompt_tokens for t in self.tasks),
            "total_completion_tokens": sum(t.total_completion_tokens for t in self.tasks),
            "total_cached_prompt_tokens": sum(
                t.total_cached_prompt_tokens for t in self.tasks
            ),
            "total_cost_usd": batch_cost_usd(
                [t.to_dict() for t in self.tasks], self.model_key
            ),
        }

    def to_dict(self) -> dict[str, Any]:
        return {
            "batch_path": self.batch_path,
            "batch_id": self.batch_id,
            "model_key": self.model_key,
            "bird_split": self.bird_split,
            "n_replicas": self.n_replicas,
            "task_count": self.task_count,
            "ex_accuracy_pct": round(self.ex_accuracy_pct, 2),
            "api_failure_count": self.api_failure_count,
            "completed_task_count": self.completed_task_count,
            "ex_accuracy_excluding_api_errors_pct": self.ex_accuracy_excluding_api_errors_pct,
            "aggregate": self.aggregate(),
            "tasks": [t.to_dict() for t in self.tasks],
        }


def _subexpr_overlap_per_task(
    agent_explore_sql: dict[str, list[str]],
) -> tuple[int, int, float]:
    """Count fragments appearing in explore SQL from 2+ agents."""
    fragment_agents: dict[str, set[str]] = defaultdict(set)
    for agent_id, queries in agent_explore_sql.items():
        for sql in queries:
            for frag in extract_sql_fragments(sql):
                fragment_agents[frag].add(agent_id)

    total = len(fragment_agents)
    shared = sum(1 for agents in fragment_agents.values() if len(agents) >= 2)
    pct = 100.0 * shared / total if total else 0.0
    return total, shared, pct


def analyze_coord_trace(
    coord_path: Path,
    *,
    question_id: int | None = None,
    db_id: str = "",
    difficulty: str = "",
) -> TaskBaselineMetrics | None:
    """Derive per-task baseline metrics from a coordination JSONL trace."""
    if not coord_path.exists():
        return None

    events = read_trace_events(coord_path)
    if not events:
        return None

    start = next((e for e in events if e.get("event") == "parallel_start"), None)
    end = next((e for e in events if e.get("event") == "coordination_end"), None)
    replica_ends = [e for e in events if e.get("event") == "replica_end"]

    if start is None or end is None:
        return None

    qid = int(question_id if question_id is not None else start.get("question_id", 0))
    n_replicas = int(start.get("n_replicas", len(replica_ends)))
    wall_clock_ms = int(end.get("wall_clock_ms", 0))

    agent_explore: dict[str, list[str]] = {}
    all_sql_count = 0
    explore_count = 0
    explore_string_keys: list[str] = []
    explore_ast_keys: list[str] = []

    replica_walls: list[int] = []
    for rep in replica_ends:
        agent_id = str(rep.get("agent_id", "agent_0"))
        trace_path = Path(str(rep.get("trace_path", "")))
        explore_sql = explore_sql_from_trace(trace_path)
        agent_explore[agent_id] = explore_sql

        for ev in _sql_events_from_trace(trace_path):
            all_sql_count += 1
            role = ev.get("sql_role", "")
            raw = str(ev.get("sql_raw", ""))
            if role == "explore" and raw:
                explore_count += 1
                explore_string_keys.append(normalize_sql_string(raw))
                ast_key = normalize_sql_ast(raw)
                if ast_key:
                    explore_ast_keys.append(ast_key)

        w = _wall_clock_from_trace(trace_path)
        if w is not None:
            replica_walls.append(w)

    seen: set[str] = set()
    duplicates = 0
    for key in explore_string_keys:
        if key in seen:
            duplicates += 1
        else:
            seen.add(key)

    explore_pct = 100.0 * duplicates / explore_count if explore_count else 0.0
    subexpr_total, subexpr_shared, subexpr_pct = _subexpr_overlap_per_task(agent_explore)

    # Time to first successful replica (by finish_rank order in coord trace)
    time_to_first_success: int | None = None
    ordered = sorted(replica_ends, key=lambda e: int(e.get("finish_rank", 0)))
    if ordered and start.get("ts"):
        start_ts = str(start["ts"])
        for rep in ordered:
            if int(rep.get("ex_correct", 0)) == 1:
                # Approximate from per-replica wall clock if available
                trace_path = Path(str(rep.get("trace_path", "")))
                w = _wall_clock_from_trace(trace_path)
                if w is not None:
                    time_to_first_success = w
                break

    redundancy = end.get("redundancy", {})
    total_prompt_tokens = int(redundancy.get("total_prompt_tokens", 0))
    total_completion_tokens = int(redundancy.get("total_completion_tokens", 0))
    total_cached_prompt_tokens = int(redundancy.get("total_cached_prompt_tokens", 0))
    total_tokens = total_prompt_tokens + total_completion_tokens
    overhead = redundancy.get("token_overhead_ratio")
    token_overhead = float(overhead) if overhead is not None else None

    return TaskBaselineMetrics(
        question_id=qid,
        db_id=db_id or str(start.get("db_id", "")),
        difficulty=difficulty,
        n_replicas=n_replicas,
        total_sql_queries=all_sql_count,
        total_explore_queries=explore_count,
        unique_explore_string=len(set(explore_string_keys)),
        unique_explore_ast=len(set(explore_ast_keys)),
        duplicate_explore_sql=duplicates,
        explore_redundancy_pct=explore_pct,
        subexpr_total=subexpr_total,
        subexpr_shared=subexpr_shared,
        subexpr_overlap_pct=subexpr_pct,
        wall_clock_ms=wall_clock_ms,
        time_to_first_success_ms=time_to_first_success,
        min_replica_wall_ms=min(replica_walls) if replica_walls else None,
        total_tokens=total_tokens,
        token_overhead_ratio=token_overhead,
        ex_correct=int(end.get("chosen_ex_correct", 0)),
        replicas_ex_correct=int(redundancy.get("replicas_ex_correct", 0)),
        total_prompt_tokens=total_prompt_tokens,
        total_completion_tokens=total_completion_tokens,
        total_cached_prompt_tokens=total_cached_prompt_tokens,
    )


def analyze_parallel_batch(batch_path: Path) -> BatchBaselineReport:
    """Analyze one parallel batch JSON produced by run_parallel_batch.py."""
    data = json.loads(batch_path.read_text(encoding="utf-8"))
    rows = data.get("rows", [])
    tasks: list[TaskBaselineMetrics] = []

    for row in rows:
        if not isinstance(row, dict):
            continue
        coord = row.get("coord_trace_path")
        if not coord:
            continue
        metrics = analyze_coord_trace(
            Path(str(coord)),
            question_id=int(row.get("question_id", 0)),
            db_id=str(row.get("db_id", "")),
            difficulty=str(row.get("difficulty", "")),
        )
        if metrics is not None:
            tasks.append(metrics)

    ex_stats = batch_ex_accuracy_stats([r for r in rows if isinstance(r, dict)])
    ex_pct = float(data.get("ex_accuracy_pct", ex_stats["ex_accuracy_pct"]))
    api_failures = int(data.get("api_failure_count", ex_stats["api_failure_count"]))
    completed = int(data.get("completed_task_count", ex_stats["completed_task_count"]))
    ex_excl = data.get("ex_accuracy_excluding_api_errors_pct", ex_stats["ex_accuracy_excluding_api_errors_pct"])
    if ex_excl is not None:
        ex_excl = float(ex_excl)
    if not tasks and rows:
        ex_pct = ex_stats["ex_accuracy_pct"]

    return BatchBaselineReport(
        batch_path=str(batch_path.resolve()),
        batch_id=str(data.get("batch_id", batch_path.stem)),
        model_key=str(data.get("model_key", "")),
        bird_split=str(data.get("bird_split", "")),
        n_replicas=int(data.get("n_replicas", 0)),
        task_count=int(data.get("task_count", len(rows))),
        ex_accuracy_pct=ex_pct,
        api_failure_count=api_failures,
        completed_task_count=completed,
        ex_accuracy_excluding_api_errors_pct=ex_excl,
        tasks=tasks,
    )


def compare_replica_counts(reports: list[BatchBaselineReport]) -> list[dict[str, Any]]:
    """Summarise how redundancy scales with replica count (one batch per N)."""
    by_n = sorted(reports, key=lambda r: r.n_replicas)
    rows: list[dict[str, Any]] = []
    for report in by_n:
        agg = report.aggregate()
        rows.append(
            {
                "n_replicas": report.n_replicas,
                "model_key": report.model_key,
                "task_count": agg.get("task_count", 0),
                "ex_accuracy_pct": agg.get("ex_accuracy_pct"),
                "api_failure_count": report.api_failure_count,
                "completed_task_count": report.completed_task_count,
                "ex_accuracy_excluding_api_errors_pct": report.ex_accuracy_excluding_api_errors_pct,
                "total_sql_queries": agg.get("total_sql_queries"),
                "total_explore_queries": agg.get("total_explore_queries"),
                "unique_explore_string": agg.get("unique_explore_string"),
                "unique_explore_ast": agg.get("unique_explore_ast"),
                "explore_query_uniqueness_pct": agg.get("explore_query_uniqueness_pct"),
                "avg_explore_redundancy_pct": agg.get("avg_explore_redundancy_pct"),
                "median_explore_redundancy_pct": agg.get("median_explore_redundancy_pct"),
                "avg_subexpr_overlap_pct": agg.get("avg_subexpr_overlap_pct"),
                "median_subexpr_overlap_pct": agg.get("median_subexpr_overlap_pct"),
                "avg_token_overhead_ratio": agg.get("avg_token_overhead_ratio"),
                "avg_wall_clock_ms": agg.get("avg_wall_clock_ms"),
                "median_wall_clock_ms": agg.get("median_wall_clock_ms"),
                "avg_time_to_first_success_ms": agg.get("avg_time_to_first_success_ms"),
                "total_tokens": agg.get("total_tokens"),
                "total_prompt_tokens": agg.get("total_prompt_tokens"),
                "total_completion_tokens": agg.get("total_completion_tokens"),
                "total_cached_prompt_tokens": agg.get("total_cached_prompt_tokens"),
                "total_cost_usd": agg.get("total_cost_usd"),
            }
        )
    return rows


def format_markdown_report(
    reports: list[BatchBaselineReport],
    *,
    title: str = "Baseline Redundancy Report (P0)",
    generated_at: str | None = None,
) -> str:
    """Render a thesis-ready markdown summary."""
    ts = generated_at or datetime.now(timezone.utc).isoformat()
    lines: list[str] = [
        f"# {title}",
        "",
        f"Generated: {ts}",
        "",
        "Policy: **P0** — independent parallel replicas (`P0_parallel`), no shared middleware.",
        "",
    ]

    if not reports:
        lines.append("_No batch data provided._")
        return "\n".join(lines)

    model = reports[0].model_key
    split = reports[0].bird_split
    lines.extend(
        [
            f"- Model: `{model}`",
            f"- Dataset: `{split}`",
            f"- Batches analysed: {len(reports)}",
            "",
        ]
    )

    comparison = compare_replica_counts(reports)
    if comparison:
        lines.extend(
            [
                "## Redundancy vs agent count",
                "",
                "| Replicas | Tasks | EX % | EX % (no API fail) | API fails | Total SQL | Explore SQL | Unique explore | Avg explore redundancy % | Avg sub-expr overlap % | Token overhead | Avg wall (ms) | Total tokens |",
                "|---------:|------:|-----:|-------------------:|----------:|----------:|------------:|---------------:|-------------------------:|-----------------------:|---------------:|--------------:|-------------:|",
            ]
        )
        for row in comparison:
            overhead = row.get("avg_token_overhead_ratio")
            overhead_s = f"{overhead:.2f}x" if overhead is not None else "—"
            ex_excl = row.get("ex_accuracy_excluding_api_errors_pct")
            ex_excl_s = f"{ex_excl:.1f}" if ex_excl is not None else "—"
            api_fails = int(row.get("api_failure_count", 0))
            lines.append(
                f"| {row['n_replicas']} | {row['task_count']} | {row['ex_accuracy_pct']:.1f} | "
                f"{ex_excl_s} | {api_fails} | "
                f"{row['total_sql_queries']} | {row['total_explore_queries']} | "
                f"{row['unique_explore_string']} | {row['avg_explore_redundancy_pct']:.1f} | "
                f"{row['avg_subexpr_overlap_pct']:.1f} | {overhead_s} | "
                f"{row['avg_wall_clock_ms']:.0f} | {row['total_tokens']:,} |"
            )
        lines.append("")

    for report in sorted(reports, key=lambda r: r.n_replicas):
        agg = report.aggregate()
        ex_excl_line = (
            f"- Execution accuracy (excluding API failures): **{report.ex_accuracy_excluding_api_errors_pct:.1f}%**"
            if report.ex_accuracy_excluding_api_errors_pct is not None
            else "- Execution accuracy (excluding API failures): **n/a**"
        )
        lines.extend(
            [
                f"## {report.n_replicas} replicas — `{report.batch_id}`",
                "",
                f"- Execution accuracy: **{agg.get('ex_accuracy_pct', 0):.1f}%**",
                ex_excl_line,
                f"- API failures: **{report.api_failure_count}** "
                f"({report.completed_task_count}/{report.task_count} tasks completed)",
                f"- Explore query uniqueness: **{agg.get('explore_query_uniqueness_pct', 0):.1f}%** "
                f"({agg.get('unique_explore_string', 0)} unique / {agg.get('total_explore_queries', 0)} total explore queries)",
                f"- AST-unique explore queries: **{agg.get('unique_explore_ast', 0)}**",
                f"- Median explore redundancy: **{agg.get('median_explore_redundancy_pct', 0):.1f}%**",
                f"- Median sub-expression overlap: **{agg.get('median_subexpr_overlap_pct', 0):.1f}%**",
                f"- Median wall-clock (coord): **{agg.get('median_wall_clock_ms', 0):.0f} ms**",
                "",
            ]
        )

        by_diff: Counter[str] = Counter()
        red_by_diff: dict[str, list[float]] = defaultdict(list)
        for t in report.tasks:
            by_diff[t.difficulty] += 1
            red_by_diff[t.difficulty].append(t.explore_redundancy_pct)

        if by_diff:
            lines.append("### By difficulty")
            lines.append("")
            lines.append("| Difficulty | Tasks | Avg explore redundancy % |")
            lines.append("|------------|------:|---------------------------:|")
            for diff in sorted(by_diff.keys()):
                avg_red = statistics.mean(red_by_diff[diff]) if red_by_diff[diff] else 0.0
                lines.append(f"| {diff} | {by_diff[diff]} | {avg_red:.1f} |")
            lines.append("")

    lines.extend(
        [
            "## Metric definitions",
            "",
            "- **Explore redundancy %**: fraction of explore SQL statements that duplicate a prior statement "
            "(whitespace-normalised) within the same task's replica set.",
            "- **Sub-expression overlap %**: fraction of sqlglot-extracted fragments (tables, columns, predicates) "
            "that appear in explore queries from two or more replicas.",
            "- **Token overhead ratio**: total tokens across replicas divided by tokens of the cheapest correct replica.",
            "- **Wall-clock**: coordination session time (parallel_start → coordination_end).",
            "- **EX % (no API fail)**: execution accuracy counting only tasks that finished without a "
            "transport/API error (tasks where the whole parallel run raised after retries).",
            "- **API failures**: tasks where all replicas failed before producing a coordinated answer; "
            "recorded as EX=0 in the headline metric.",
            "",
        ]
    )

    return "\n".join(lines)
