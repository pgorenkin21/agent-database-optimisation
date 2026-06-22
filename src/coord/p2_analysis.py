"""Load and summarise P2 discovery-board vs P0 batch comparisons."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from src.coord.early_stop_analysis import (
    DEFAULT_MODELS,
    batch_summary as _base_batch_summary,
    find_p0_batch,
    load_batch,
)

P2_BATCH_IDS: dict[int, str] = {
    10: "p2_r10_bo",
    25: "p2_r25_bo",
}


def p2_batch_summary(data: dict[str, Any], *, path: Path | None = None) -> dict[str, Any]:
    summary = _base_batch_summary(data, path=path)
    rows = data.get("rows", [])
    total_publishes = sum(int(r.get("discovery_publishes", 0)) for r in rows)
    total_fragments = sum(int(r.get("discovery_fragments", 0)) for r in rows)
    total_injections = sum(int(r.get("discovery_injections", 0)) for r in rows)
    summary.update(
        {
            "discovery_board": bool(data.get("discovery_board", True)),
            "avg_discovery_fragments": data.get("avg_discovery_fragments"),
            "total_discovery_publishes": total_publishes,
            "total_discovery_fragments": total_fragments,
            "total_discovery_injections": total_injections,
            "avg_discovery_injections_per_task": round(total_injections / len(rows), 2) if rows else 0.0,
        }
    )
    return summary


def find_p2_batch(
    batch_dir: Path, model: str, n_replicas: int, *, batch_id: str
) -> Path | None:
    pattern = f"parallel_{batch_id}_{model}_r{n_replicas}_best_of_n_p2_discovery*.json"
    matches = [
        p
        for p in sorted(batch_dir.glob(pattern))
        if "early_stop" not in p.stem and p.is_file()
    ]
    return matches[-1] if matches else None


def build_p2_comparisons(
    batch_dir: Path,
    *,
    models: list[str],
    n_replicas: int,
    p2_batch_id: str,
) -> list[tuple[dict[str, Any], dict[str, Any]]]:
    pairs: list[tuple[dict[str, Any], dict[str, Any]]] = []
    for model in models:
        p0_path = find_p0_batch(batch_dir, model, n_replicas)
        p2_path = find_p2_batch(batch_dir, model, n_replicas, batch_id=p2_batch_id)
        if not p0_path or not p2_path:
            continue
        p0_data = load_batch(p0_path)
        p2_data = load_batch(p2_path)
        pairs.append(
            (
                _base_batch_summary(p0_data, path=p0_path),
                p2_batch_summary(p2_data, path=p2_path),
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
    counts = replica_counts or sorted(P2_BATCH_IDS)
    out: dict[int, list[tuple[dict[str, Any], dict[str, Any]]]] = {}
    for n in counts:
        batch_id = P2_BATCH_IDS.get(n, f"p2_r{n}_bo")
        pairs = build_p2_comparisons(batch_dir, models=model_list, n_replicas=n, p2_batch_id=batch_id)
        if pairs:
            out[n] = pairs
    return out
