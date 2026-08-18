"""Measure the persistent per-database profile (DB Profile Card, Chapter 12).

The headline metric is **mean explore ``sql_execute`` events per task** with the
profile card on vs off: the card pre-answers database-level questions, so the agent
should issue fewer exploratory queries. Existing interaction metrics
(``interaction_metrics.py``) lump explore + final executions into one count; this
module reads replica traces and isolates **explore** events (``sql_role ==
"explore"``), then attributes the reduction to the profile section it plausibly
replaces — value-domain probes vs join-graph probes — per §12.6.

Baseline is ``P0_cached`` (prompt cache on, profile off); the variant adds
``--db-profile``. Comparisons reuse the batch loaders in ``early_stop_analysis``.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import sqlglot
from sqlglot import exp

from src.coord.early_stop_analysis import (
    DEFAULT_MODELS,
    batch_summary,
    load_batch,
    pct_delta,
)
from src.logging.trace import read_trace_events

# Batch ids for the Chapter 12 ablation (see §12.5). Baseline = prompt-cache only;
# variant = prompt-cache + db-profile. Both run under best_of_n.
DBPROFILE_ISOLATED_BATCH_IDS: dict[int, str] = {
    10: "dbprofile_iso_r10_bo",
    25: "dbprofile_iso_r25_bo",
}
DBPROFILE_BASELINE_BATCH_IDS: dict[int, str] = {
    10: "dbprofile_base_r10_bo",
    25: "dbprofile_base_r25_bo",
}

# sql_execute event classes for section attribution.
EXPLORE_JOIN = "join"
EXPLORE_VALUE_DOMAIN = "value_domain"
EXPLORE_OTHER = "other"


@dataclass(frozen=True)
class ExploreMetrics:
    """Explore ``sql_execute`` counts for one trace / task / batch, by class."""

    explore_total: int = 0
    join_explores: int = 0
    value_domain_explores: int = 0
    other_explores: int = 0

    def __add__(self, other: "ExploreMetrics") -> "ExploreMetrics":
        return ExploreMetrics(
            explore_total=self.explore_total + other.explore_total,
            join_explores=self.join_explores + other.join_explores,
            value_domain_explores=self.value_domain_explores + other.value_domain_explores,
            other_explores=self.other_explores + other.other_explores,
        )


# --------------------------------------------------------------------------- #
# Explore-query classification (section attribution)
# --------------------------------------------------------------------------- #


def classify_explore_sql(sql: str) -> str:
    """Attribute an explore query to the profile section it plausibly replaces.

    - ``join``: contains a JOIN — the profile's join graph could have answered it.
    - ``value_domain``: single-table DISTINCT / GROUP BY / COUNT(DISTINCT) — the
      profile's value-domain samples could have answered it.
    - ``other``: anything else (row inspection, aggregates without grouping, …).

    A parse failure degrades to ``other`` (never raises).
    """
    try:
        tree = sqlglot.parse_one(sql.strip(), read="sqlite")
    except Exception:
        return EXPLORE_OTHER
    if tree is None:
        return EXPLORE_OTHER

    if tree.find(exp.Join) is not None:
        return EXPLORE_JOIN

    has_group = bool(tree.find(exp.Group))
    has_distinct = tree.find(exp.Distinct) is not None
    if has_group or has_distinct:
        return EXPLORE_VALUE_DOMAIN
    return EXPLORE_OTHER


# --------------------------------------------------------------------------- #
# Trace-level explore counting
# --------------------------------------------------------------------------- #


def explore_metrics_from_trace(trace_path: Path) -> ExploreMetrics:
    """Count explore ``sql_execute`` events in one replica trace, by class."""
    if not trace_path.exists():
        return ExploreMetrics()
    join = value_domain = other = 0
    for ev in read_trace_events(trace_path):
        if ev.get("event") != "sql_execute" or ev.get("sql_role") != "explore":
            continue
        cls = classify_explore_sql(str(ev.get("sql_raw", "")))
        if cls == EXPLORE_JOIN:
            join += 1
        elif cls == EXPLORE_VALUE_DOMAIN:
            value_domain += 1
        else:
            other += 1
    return ExploreMetrics(
        explore_total=join + value_domain + other,
        join_explores=join,
        value_domain_explores=value_domain,
        other_explores=other,
    )


def explore_metrics_from_coord_trace(coord_path: Path) -> ExploreMetrics:
    """Aggregate explore metrics across a task's replica traces.

    Follows ``replica_end`` pointers in the coordination trace to each replica's
    per-run trace (same pattern as ``interaction_metrics_from_coord_trace``).
    """
    if not coord_path.exists():
        return ExploreMetrics()
    total = ExploreMetrics()
    for ev in read_trace_events(coord_path):
        if ev.get("event") == "replica_end":
            total = total + explore_metrics_from_trace(
                Path(str(ev.get("trace_path", "")))
            )
    return total


# --------------------------------------------------------------------------- #
# Batch-level explore summary
# --------------------------------------------------------------------------- #


def _row_explore_metrics(row: dict[str, Any]) -> ExploreMetrics | None:
    coord = row.get("coord_trace_path")
    if not coord:
        return None
    path = Path(str(coord))
    if not path.exists():
        return None
    return explore_metrics_from_coord_trace(path)


def batch_explore_summary(data: dict[str, Any]) -> dict[str, Any]:
    """Mean explore ``sql_execute`` events per task for a batch, with attribution.

    Reads per-task coordination traces. ``traces_found`` reports coverage so a
    partial run does not silently understate the mean.
    """
    rows = data.get("rows", [])
    per_task: list[ExploreMetrics] = []
    by_db: dict[str, list[ExploreMetrics]] = defaultdict(list)
    for row in rows:
        m = _row_explore_metrics(row)
        if m is None:
            continue
        per_task.append(m)
        by_db[str(row.get("db_id", "?"))].append(m)

    n = len(per_task)

    def _mean(values: list[int]) -> float | None:
        return round(sum(values) / len(values), 3) if values else None

    return {
        "traces_found": n,
        "task_count": len(rows),
        "mean_explore_per_task": _mean([m.explore_total for m in per_task]),
        "mean_join_explores_per_task": _mean([m.join_explores for m in per_task]),
        "mean_value_domain_explores_per_task": _mean(
            [m.value_domain_explores for m in per_task]
        ),
        "mean_other_explores_per_task": _mean([m.other_explores for m in per_task]),
        "explore_by_db": {
            db: {
                "task_count": len(ms),
                "mean_explore_per_task": _mean([m.explore_total for m in ms]),
                "mean_value_domain_per_task": _mean(
                    [m.value_domain_explores for m in ms]
                ),
                "mean_join_per_task": _mean([m.join_explores for m in ms]),
            }
            for db, ms in sorted(by_db.items())
        },
    }


def dbprofile_batch_summary(
    data: dict[str, Any], *, path: Path | None = None
) -> dict[str, Any]:
    """``batch_summary`` extended with explore attribution and the db_profile flag."""
    summary = batch_summary(data, path=path)
    summary.update(batch_explore_summary(data))
    summary.update(
        {
            "db_profile": bool(data.get("db_profile", False)),
            "policy_label": "dbprofile" if data.get("db_profile") else "P0_cached",
        }
    )
    return summary


# --------------------------------------------------------------------------- #
# Batch discovery + comparisons
# --------------------------------------------------------------------------- #


def _find_batch(batch_dir: Path, batch_id: str, model: str, n_replicas: int, suffix: str) -> Path | None:
    pattern = f"parallel_{batch_id}_{model}_r{n_replicas}_best_of_n_{suffix}.json"
    matches = sorted(batch_dir.glob(pattern))
    return matches[-1] if matches else None


def find_cached_baseline_batch(
    batch_dir: Path, model: str, n_replicas: int, *, batch_id: str
) -> Path | None:
    """Prompt-cache-on, profile-off baseline (tag ``_promptcache``)."""
    return _find_batch(batch_dir, batch_id, model, n_replicas, "promptcache")


def find_dbprofile_batch(
    batch_dir: Path, model: str, n_replicas: int, *, batch_id: str
) -> Path | None:
    """Prompt-cache-on, profile-on variant (tag ``_promptcache_dbprofile``)."""
    return _find_batch(batch_dir, batch_id, model, n_replicas, "promptcache_dbprofile")


def build_isolated_comparisons_by_model(
    batch_dir: Path,
    *,
    models: list[str] | None = None,
    n_replicas: int = 10,
    baseline_batch_id: str | None = None,
    variant_batch_id: str | None = None,
) -> dict[str, tuple[dict[str, Any], dict[str, Any]]]:
    """Return ``{model: (baseline_summary, dbprofile_summary)}`` for isolated runs.

    Baseline = ``P0_cached`` (prompt cache, no profile); variant adds the card.
    """
    base_id = baseline_batch_id or DBPROFILE_BASELINE_BATCH_IDS.get(
        n_replicas, f"dbprofile_base_r{n_replicas}_bo"
    )
    var_id = variant_batch_id or DBPROFILE_ISOLATED_BATCH_IDS.get(
        n_replicas, f"dbprofile_iso_r{n_replicas}_bo"
    )
    out: dict[str, tuple[dict[str, Any], dict[str, Any]]] = {}
    for m in models or DEFAULT_MODELS:
        base_path = find_cached_baseline_batch(batch_dir, m, n_replicas, batch_id=base_id)
        var_path = find_dbprofile_batch(batch_dir, m, n_replicas, batch_id=var_id)
        if not base_path or not var_path:
            continue
        out[m] = (
            dbprofile_batch_summary(load_batch(base_path), path=base_path),
            dbprofile_batch_summary(load_batch(var_path), path=var_path),
        )
    return out


def comparison_deltas(
    baseline: dict[str, Any], variant: dict[str, Any]
) -> dict[str, float | None]:
    """Explore-count and token/EX deltas, baseline (profile off) → variant (on)."""

    def _delta(key: str) -> float | None:
        b, v = baseline.get(key), variant.get(key)
        if b is None or v is None:
            return None
        return round(v - b, 3)

    return {
        # The golden rule: EX delta sits next to every saving.
        "ex_pp": (variant.get("ex_accuracy_pct") or 0) - (baseline.get("ex_accuracy_pct") or 0),
        "token_pct": pct_delta(baseline.get("total_tokens", 0), variant.get("total_tokens", 0)),
        "cost_usd_pct": pct_delta(baseline.get("total_cost_usd"), variant.get("total_cost_usd")),
        "explore_per_task_delta": _delta("mean_explore_per_task"),
        "explore_per_task_pct": pct_delta(
            baseline.get("mean_explore_per_task"), variant.get("mean_explore_per_task")
        ),
        "value_domain_explores_delta": _delta("mean_value_domain_explores_per_task"),
        "join_explores_delta": _delta("mean_join_explores_per_task"),
    }
