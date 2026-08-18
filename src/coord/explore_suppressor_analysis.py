"""Measure P4 structural explore suppression (Chapter 13).

Baseline is ``P0_cached`` (prompt cache, no suppressor); the variant adds
``--explore-suppressor``. The headline is the **net DB round-trip reduction**:
executed explore ``sql_execute`` events per task, on vs off, with the count of
``explore_suppressed`` events showing where the round-trips went — reported next
to the EX delta (a suppression that drops EX is not a win).
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from src.coord.early_stop_analysis import (
    DEFAULT_MODELS,
    batch_summary,
    load_batch,
    pct_delta,
)
from src.logging.trace import read_trace_events

SUPPRESSOR_BASELINE_BATCH_IDS: dict[int, str] = {
    10: "suppress_base_r10_bo",
    25: "suppress_base_r25_bo",
}
SUPPRESSOR_ISOLATED_BATCH_IDS: dict[int, str] = {
    10: "suppress_iso_r10_bo",
    25: "suppress_iso_r25_bo",
}


@dataclass(frozen=True)
class SuppressionCounts:
    executed_explores: int = 0
    suppressed: int = 0

    def __add__(self, other: "SuppressionCounts") -> "SuppressionCounts":
        return SuppressionCounts(
            executed_explores=self.executed_explores + other.executed_explores,
            suppressed=self.suppressed + other.suppressed,
        )


def counts_from_trace(trace_path: Path) -> SuppressionCounts:
    if not trace_path.exists():
        return SuppressionCounts()
    executed = suppressed = 0
    for ev in read_trace_events(trace_path):
        event = ev.get("event")
        if event == "sql_execute" and ev.get("sql_role") == "explore":
            executed += 1
        elif event == "explore_suppressed":
            suppressed += 1
    return SuppressionCounts(executed_explores=executed, suppressed=suppressed)


def counts_from_coord_trace(coord_path: Path) -> SuppressionCounts:
    if not coord_path.exists():
        return SuppressionCounts()
    total = SuppressionCounts()
    for ev in read_trace_events(coord_path):
        if ev.get("event") == "replica_end":
            total = total + counts_from_trace(Path(str(ev.get("trace_path", ""))))
    return total


def batch_suppression_summary(data: dict[str, Any]) -> dict[str, Any]:
    """Mean executed-explore and suppressed counts per task, with coverage."""
    rows = data.get("rows", [])
    per_task: list[SuppressionCounts] = []
    for row in rows:
        coord = row.get("coord_trace_path")
        if not coord or not Path(str(coord)).exists():
            continue
        per_task.append(counts_from_coord_trace(Path(str(coord))))

    n = len(per_task)

    def _mean(vals: list[int]) -> float | None:
        return round(sum(vals) / len(vals), 3) if vals else None

    total_exec = sum(c.executed_explores for c in per_task)
    total_supp = sum(c.suppressed for c in per_task)
    denom = total_exec + total_supp
    return {
        "traces_found": n,
        "task_count": len(rows),
        "mean_executed_explores_per_task": _mean([c.executed_explores for c in per_task]),
        "mean_suppressed_per_task": _mean([c.suppressed for c in per_task]),
        # share of would-be explore probes the suppressor intercepted
        "suppression_rate_pct": round(100.0 * total_supp / denom, 2) if denom else 0.0,
    }


def suppressor_batch_summary(
    data: dict[str, Any], *, path: Path | None = None
) -> dict[str, Any]:
    summary = batch_summary(data, path=path)
    summary.update(batch_suppression_summary(data))
    summary.update(
        {
            "explore_suppressor": bool(data.get("explore_suppressor", False)),
            "policy_label": "p4suppress" if data.get("explore_suppressor") else "P0_cached",
        }
    )
    return summary


def _find(batch_dir: Path, batch_id: str, model: str, n: int, suffix: str) -> Path | None:
    matches = sorted(
        batch_dir.glob(f"parallel_{batch_id}_{model}_r{n}_best_of_n_{suffix}.json")
    )
    return matches[-1] if matches else None


def find_baseline_batch(batch_dir: Path, model: str, n: int, *, batch_id: str) -> Path | None:
    return _find(batch_dir, batch_id, model, n, "promptcache")


def find_suppressor_batch(batch_dir: Path, model: str, n: int, *, batch_id: str) -> Path | None:
    return _find(batch_dir, batch_id, model, n, "promptcache_p4suppress")


def build_comparisons_by_model(
    batch_dir: Path,
    *,
    models: list[str] | None = None,
    n_replicas: int = 10,
    baseline_batch_id: str | None = None,
    variant_batch_id: str | None = None,
) -> dict[str, tuple[dict[str, Any], dict[str, Any]]]:
    base_id = baseline_batch_id or SUPPRESSOR_BASELINE_BATCH_IDS.get(
        n_replicas, f"suppress_base_r{n_replicas}_bo"
    )
    var_id = variant_batch_id or SUPPRESSOR_ISOLATED_BATCH_IDS.get(
        n_replicas, f"suppress_iso_r{n_replicas}_bo"
    )
    out: dict[str, tuple[dict[str, Any], dict[str, Any]]] = {}
    for m in models or DEFAULT_MODELS:
        base = find_baseline_batch(batch_dir, m, n_replicas, batch_id=base_id)
        var = find_suppressor_batch(batch_dir, m, n_replicas, batch_id=var_id)
        if not base or not var:
            continue
        out[m] = (
            suppressor_batch_summary(load_batch(base), path=base),
            suppressor_batch_summary(load_batch(var), path=var),
        )
    return out


def comparison_deltas(
    baseline: dict[str, Any], variant: dict[str, Any]
) -> dict[str, float | None]:
    def _d(key: str) -> float | None:
        b, v = baseline.get(key), variant.get(key)
        return None if b is None or v is None else round(v - b, 3)

    return {
        "ex_pp": (variant.get("ex_accuracy_pct") or 0) - (baseline.get("ex_accuracy_pct") or 0),
        "executed_explores_delta": _d("mean_executed_explores_per_task"),
        "executed_explores_pct": pct_delta(
            baseline.get("mean_executed_explores_per_task"),
            variant.get("mean_executed_explores_per_task"),
        ),
        "suppressed_per_task": variant.get("mean_suppressed_per_task"),
        "suppression_rate_pct": variant.get("suppression_rate_pct"),
        "token_pct": pct_delta(baseline.get("total_tokens", 0), variant.get("total_tokens", 0)),
        "cost_usd_pct": pct_delta(baseline.get("total_cost_usd"), variant.get("total_cost_usd")),
    }
