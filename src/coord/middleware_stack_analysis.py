"""Load middleware stack summaries (P0, P1, P2, P1+P2, early stop) from batch JSON."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from src.coord.early_stop_analysis import (
    DEFAULT_MODELS,
    batch_summary as _base_batch_summary,
    find_early_stop_batch,
    find_p0_batch,
    load_batch,
)
from src.coord.p1_analysis import P1_BATCH_IDS, find_p1_batch, p1_batch_summary
from src.coord.p2_analysis import P2_BATCH_IDS, find_p2_batch, p2_batch_summary

P1P2_BATCH_IDS: dict[int, str] = {
    10: "p1p2_r10_bo",
}

FULL_STACK_BATCH_IDS: dict[int, str] = {
    25: "fullstack_r25_bo",
}

FULL_STACK_SCHEMA_PRUNE_BATCH_IDS: dict[int, str] = {
    10: "fullstack_prune_r10_bo",
    25: "fullstack_prune_r25_bo",
}

FULL500_STACK_PRUNE_BATCH_ID = "fullstack_prune_full500_r3"
FULL500_STACK_REPLICAS = 3

EARLY_STOP_BATCH_IDS: dict[int, str] = {
    10: "earlystop_r10_bo",
    25: "earlystop_r25_bo",
}


def find_p1p2_batch(
    batch_dir: Path, model: str, n_replicas: int, *, batch_id: str
) -> Path | None:
    pattern = f"parallel_{batch_id}_{model}_r{n_replicas}_best_of_n_p1_cache_p2_discovery.json"
    matches = sorted(batch_dir.glob(pattern))
    return matches[-1] if matches else None


def find_full_stack_batch(
    batch_dir: Path, model: str, n_replicas: int, *, batch_id: str
) -> Path | None:
    pattern = (
        f"parallel_{batch_id}_{model}_r{n_replicas}_best_of_n"
        f"_p1_cache_p2_discovery_early_stop.json"
    )
    matches = sorted(batch_dir.glob(pattern))
    return matches[-1] if matches else None


def find_full_stack_schema_prune_batch(
    batch_dir: Path, model: str, n_replicas: int, *, batch_id: str
) -> Path | None:
    pattern = (
        f"parallel_{batch_id}_{model}_r{n_replicas}_best_of_n"
        f"_p1_cache_p2_discovery_early_stop_schema_prune.json"
    )
    matches = sorted(batch_dir.glob(pattern))
    return matches[-1] if matches else None


def p1p2_batch_summary(data: dict[str, Any], *, path: Path | None = None) -> dict[str, Any]:
    summary = p1_batch_summary(data, path=path)
    p2_extra = p2_batch_summary(data, path=path)
    summary.update(
        {
            "shared_cache": True,
            "discovery_board": True,
            "policy_label": "P1_P2_combined",
            "avg_discovery_fragments": p2_extra.get("avg_discovery_fragments"),
            "avg_discovery_injections_per_task": p2_extra.get("avg_discovery_injections_per_task"),
            "total_discovery_publishes": p2_extra.get("total_discovery_publishes"),
            "total_discovery_injections": p2_extra.get("total_discovery_injections"),
        }
    )
    return summary


def full_stack_batch_summary(data: dict[str, Any], *, path: Path | None = None) -> dict[str, Any]:
    summary = p1p2_batch_summary(data, path=path)
    summary.update(
        {
            "early_stop": True,
            "policy_label": "full_stack",
            "early_stop_triggered_count": sum(
                1 for r in data.get("rows", []) if r.get("early_stop_triggered")
            ),
            "avg_replicas_cancelled": round(
                sum(r.get("replicas_cancelled", 0) for r in data.get("rows", []))
                / len(data.get("rows", [])),
                2,
            )
            if data.get("rows")
            else 0.0,
        }
    )
    return summary


def full_stack_schema_prune_batch_summary(
    data: dict[str, Any], *, path: Path | None = None
) -> dict[str, Any]:
    summary = full_stack_batch_summary(data, path=path)
    summary.update(
        {
            "schema_pruning": True,
            "policy_label": "full_stack_prune",
        }
    )
    return summary


def _p0_summary(data: dict[str, Any], *, path: Path | None = None) -> dict[str, Any]:
    s = _base_batch_summary(data, path=path)
    s["policy_label"] = "P0"
    s["shared_cache"] = False
    s["discovery_board"] = False
    return s


def _early_stop_summary(data: dict[str, Any], *, path: Path | None = None) -> dict[str, Any]:
    s = _base_batch_summary(data, path=path)
    s["policy_label"] = "early_stop"
    s["early_stop"] = True
    return s


def load_policy_stack(
    batch_dir: Path,
    *,
    model: str,
    n_replicas: int,
) -> dict[str, dict[str, Any]]:
    """Return available policy summaries for one model and replica count."""
    stack: dict[str, dict[str, Any]] = {}

    p0_path = find_p0_batch(batch_dir, model, n_replicas)
    if p0_path:
        stack["P0"] = _p0_summary(load_batch(p0_path), path=p0_path)

    p1_id = P1_BATCH_IDS.get(n_replicas)
    if p1_id:
        p1_path = find_p1_batch(batch_dir, model, n_replicas, batch_id=p1_id)
        if p1_path:
            stack["P1"] = p1_batch_summary(load_batch(p1_path), path=p1_path)
            stack["P1"]["policy_label"] = "P1"

    p2_id = P2_BATCH_IDS.get(n_replicas)
    if p2_id:
        p2_path = find_p2_batch(batch_dir, model, n_replicas, batch_id=p2_id)
        if p2_path:
            stack["P2"] = p2_batch_summary(load_batch(p2_path), path=p2_path)
            stack["P2"]["policy_label"] = "P2"

    p12_id = P1P2_BATCH_IDS.get(n_replicas)
    if p12_id:
        p12_path = find_p1p2_batch(batch_dir, model, n_replicas, batch_id=p12_id)
        if p12_path:
            stack["P1+P2"] = p1p2_batch_summary(load_batch(p12_path), path=p12_path)

    fs_id = FULL_STACK_BATCH_IDS.get(n_replicas)
    if fs_id:
        fs_path = find_full_stack_batch(batch_dir, model, n_replicas, batch_id=fs_id)
        if fs_path:
            stack["full_stack"] = full_stack_batch_summary(load_batch(fs_path), path=fs_path)

    fsp_id = FULL_STACK_SCHEMA_PRUNE_BATCH_IDS.get(n_replicas)
    if fsp_id:
        fsp_path = find_full_stack_schema_prune_batch(
            batch_dir, model, n_replicas, batch_id=fsp_id
        )
        if fsp_path:
            stack["full_stack_prune"] = full_stack_schema_prune_batch_summary(
                load_batch(fsp_path), path=fsp_path
            )

    from src.coord.p3_analysis import P3_BATCH_IDS, find_p3_batch, p3_batch_summary

    p3_id = P3_BATCH_IDS.get(n_replicas)
    if p3_id:
        p3_path = find_p3_batch(batch_dir, model, n_replicas, batch_id=p3_id)
        if p3_path:
            stack["P3_semantic"] = p3_batch_summary(load_batch(p3_path), path=p3_path)

    es_id = EARLY_STOP_BATCH_IDS.get(n_replicas)
    if es_id:
        es_path = find_early_stop_batch(batch_dir, model, n_replicas, batch_id=es_id)
        if es_path:
            stack["early_stop"] = _early_stop_summary(load_batch(es_path), path=es_path)

    return stack


def load_stack_by_replica_count(
    batch_dir: Path,
    *,
    models: list[str] | None = None,
    n_replicas: int,
) -> dict[str, dict[str, dict[str, Any]]]:
    """Return {model_key: {policy: summary}} for all models."""
    out: dict[str, dict[str, dict[str, Any]]] = {}
    for model in models or DEFAULT_MODELS:
        stack = load_policy_stack(batch_dir, model=model, n_replicas=n_replicas)
        if stack:
            out[model] = stack
    return out


def load_stack_by_replica_counts(
    batch_dir: Path,
    *,
    models: list[str] | None = None,
    replica_counts: list[int],
) -> dict[int, dict[str, dict[str, dict[str, Any]]]]:
    return {
        n: load_stack_by_replica_count(batch_dir, models=models, n_replicas=n)
        for n in replica_counts
    }


def find_full500_stack_prune_batch(batch_dir: Path, model: str) -> Path | None:
    """Locate full mini-dev full-stack+prune batch (*N*=3)."""
    return find_full_stack_schema_prune_batch(
        batch_dir,
        model,
        FULL500_STACK_REPLICAS,
        batch_id=FULL500_STACK_PRUNE_BATCH_ID,
    )


def build_full500_stack_comparisons(
    batch_dir: Path,
    *,
    models: list[str] | None = None,
) -> dict[str, dict[str, dict[str, Any]]]:
    """Return {model: {P0, Ch11_prune?, full_stack_prune}} for full mini-dev *N*=3.

    Uses Chapter 2 ``baseline_full500_r3`` as P0 and Chapter 11
    ``schema_prune_iso_full500_r3`` as the isolated-prune reference when present.
    """
    from src.coord.schema_pruning_analysis import (
        find_full500_isolated_prune_batch,
        find_full500_p0_batch,
        schema_prune_batch_summary,
    )

    out: dict[str, dict[str, dict[str, Any]]] = {}
    for model in models or DEFAULT_MODELS:
        p0_path = find_full500_p0_batch(batch_dir, model)
        fsp_path = find_full500_stack_prune_batch(batch_dir, model)
        if not p0_path or not fsp_path:
            continue
        entry: dict[str, dict[str, Any]] = {
            "P0": _p0_summary(load_batch(p0_path), path=p0_path),
            "full_stack_prune": full_stack_schema_prune_batch_summary(
                load_batch(fsp_path), path=fsp_path
            ),
        }
        prune_path = find_full500_isolated_prune_batch(batch_dir, model)
        if prune_path:
            entry["Ch11_prune"] = schema_prune_batch_summary(
                load_batch(prune_path), path=prune_path
            )
        out[model] = entry
    return out
