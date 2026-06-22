"""Load and summarise P1 shared-cache vs P0 batch comparisons."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from src.coord.early_stop_analysis import (
    DEFAULT_MODELS,
    batch_summary as _base_batch_summary,
    find_p0_batch,
    load_batch,
    pct_delta,
)

P1_BATCH_IDS: dict[int, str] = {
    10: "p1_r10_bo",
    25: "p1_r25_bo",
}


def p1_batch_summary(data: dict[str, Any], *, path: Path | None = None) -> dict[str, Any]:
    summary = _base_batch_summary(data, path=path)
    rows = data.get("rows", [])
    total_hits = sum(int(r.get("cache_hits", 0)) for r in rows)
    total_misses = sum(int(r.get("cache_misses", 0)) for r in rows)
    lookups = total_hits + total_misses
    summary.update(
        {
            "shared_cache": bool(data.get("shared_cache", True)),
            "avg_cache_hit_rate_pct": data.get("avg_cache_hit_rate_pct"),
            "total_cache_hits": total_hits,
            "total_cache_misses": total_misses,
            "total_cache_lookups": lookups,
            "batch_cache_hit_rate_pct": round(100.0 * total_hits / lookups, 2) if lookups else 0.0,
        }
    )
    return summary


def find_p1_batch(
    batch_dir: Path, model: str, n_replicas: int, *, batch_id: str
) -> Path | None:
    pattern = f"parallel_{batch_id}_{model}_r{n_replicas}_best_of_n_p1_cache.json"
    matches = sorted(batch_dir.glob(pattern))
    return matches[-1] if matches else None


def build_p1_comparisons(
    batch_dir: Path,
    *,
    models: list[str],
    n_replicas: int,
    p1_batch_id: str,
) -> list[tuple[dict[str, Any], dict[str, Any]]]:
    pairs: list[tuple[dict[str, Any], dict[str, Any]]] = []
    for model in models:
        p0_path = find_p0_batch(batch_dir, model, n_replicas)
        p1_path = find_p1_batch(batch_dir, model, n_replicas, batch_id=p1_batch_id)
        if not p0_path or not p1_path:
            continue
        p0_data = load_batch(p0_path)
        p1_data = load_batch(p1_path)
        pairs.append(
            (
                _base_batch_summary(p0_data, path=p0_path),
                p1_batch_summary(p1_data, path=p1_path),
            )
        )
    return pairs


def load_comparisons_by_replica_counts(
    batch_dir: Path,
    *,
    models: list[str] | None = None,
    replica_counts: list[int] | None = None,
) -> dict[int, list[tuple[dict[str, Any], dict[str, Any]]]]:
    model_list = list(models or DEFAULT_MODELS)
    counts = replica_counts or sorted(P1_BATCH_IDS)
    out: dict[int, list[tuple[dict[str, Any], dict[str, Any]]]] = {}
    for n in counts:
        batch_id = P1_BATCH_IDS.get(n, f"p1_r{n}_bo")
        pairs = build_p1_comparisons(batch_dir, models=model_list, n_replicas=n, p1_batch_id=batch_id)
        if pairs:
            out[n] = pairs
    return out
