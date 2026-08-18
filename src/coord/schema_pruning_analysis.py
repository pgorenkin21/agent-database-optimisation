"""Load offline schema-pruning reports and agent batch comparisons."""

from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path
from typing import Any

from src.coord.early_stop_analysis import (
    DEFAULT_MODELS,
    batch_summary,
    find_p0_batch,
    load_batch,
    pct_delta,
)
from src.coord.middleware_stack_analysis import (
    FULL_STACK_SCHEMA_PRUNE_BATCH_IDS,
    find_full_stack_batch,
    find_full_stack_schema_prune_batch,
    full_stack_batch_summary,
    full_stack_schema_prune_batch_summary,
)

SCHEMA_PRUNE_BATCH_IDS: dict[str, str] = {
    "v1": "schema_prune_r10_bo",
    "v2": "schema_prune_r10_bo_v2",
}

ISOLATED_BATCH_IDS: dict[int, str] = {
    10: "schema_prune_iso_r10_bo",
    25: "schema_prune_iso_r25_bo",
}

DEFAULT_ISOLATED_BATCH_VERSION = "iso"

OFFLINE_REPORT_FILES: dict[str, str] = {
    "keyword": "schema_pruning.json",
    "semantic": "schema_pruning_semantic.json",
    "hybrid": "schema_pruning_hybrid.json",
}

OFFLINE_FULL500_REPORT_FILES: dict[str, str] = {
    "keyword": "schema_pruning_full500.json",
    "semantic": "schema_pruning_full500_semantic.json",
    "hybrid": "schema_pruning_full500_hybrid.json",
}

FULL500_P0_BATCH_ID = "baseline_full500_r3"
FULL500_ISOLATED_BATCH_ID = "schema_prune_iso_full500_r3"
FULL500_ISOLATED_REPLICAS = 3


def load_offline_report(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def load_offline_reports(
    reports_dir: Path,
    *,
    modes: tuple[str, ...] = ("keyword", "semantic", "hybrid"),
    file_map: dict[str, str] | None = None,
) -> dict[str, dict[str, Any]]:
    mapping = file_map or OFFLINE_REPORT_FILES
    out: dict[str, dict[str, Any]] = {}
    for mode in modes:
        fname = mapping.get(mode, f"schema_pruning_{mode}.json")
        path = reports_dir / fname
        if path.exists():
            out[mode] = load_offline_report(path)
    return out


def load_offline_full500_reports(
    reports_dir: Path,
    *,
    modes: tuple[str, ...] = ("keyword", "semantic", "hybrid"),
) -> dict[str, dict[str, Any]]:
    """Load offline prune reports for the full 500-task mini-dev split."""
    return load_offline_reports(
        reports_dir, modes=modes, file_map=OFFLINE_FULL500_REPORT_FILES
    )


def offline_summary_by_database(report: dict[str, Any]) -> dict[str, dict[str, float]]:
    """Per-database averages from an offline pruning report."""
    buckets: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in report.get("rows", []):
        buckets[str(row["db_id"])].append(row)

    out: dict[str, dict[str, float]] = {}
    for db_id, rows in sorted(buckets.items()):
        recalls = [float(r["gold_table_recall"]) for r in rows]
        reductions = [float(r["reduction_pct"]) for r in rows]
        selected = [len(r.get("selected_tables", [])) for r in rows]
        out[db_id] = {
            "task_count": float(len(rows)),
            "avg_gold_recall_pct": round(100.0 * sum(recalls) / len(recalls), 2),
            "avg_reduction_pct": round(sum(reductions) / len(reductions), 2),
            "avg_selected_tables": round(sum(selected) / len(selected), 2),
        }
    return out


def isolated_batch_id(n_replicas: int, *, version: str = DEFAULT_ISOLATED_BATCH_VERSION) -> str:
    if version == DEFAULT_ISOLATED_BATCH_VERSION:
        return ISOLATED_BATCH_IDS.get(n_replicas, f"schema_prune_iso_r{n_replicas}_bo")
    return SCHEMA_PRUNE_BATCH_IDS.get(version, version)


def find_isolated_schema_prune_batch(
    batch_dir: Path,
    model: str,
    n_replicas: int,
    *,
    version: str = DEFAULT_ISOLATED_BATCH_VERSION,
    batch_id: str | None = None,
) -> Path | None:
    resolved_id = batch_id or isolated_batch_id(n_replicas, version=version)
    patterns = (
        f"parallel_{resolved_id}_{model}_r{n_replicas}_best_of_n_schema_prune.json",
        f"parallel_{resolved_id}_{model}_r{n_replicas}_best_of_n.json",
    )
    for pattern in patterns:
        matches = sorted(batch_dir.glob(pattern))
        if matches:
            return matches[-1]
    return None


def find_full500_p0_batch(batch_dir: Path, model: str) -> Path | None:
    """Locate the homogeneous P0 full mini-dev N=3 baseline for ``model``."""
    pattern = (
        f"parallel_{FULL500_P0_BATCH_ID}_{model}_"
        f"r{FULL500_ISOLATED_REPLICAS}_best_of_n.json"
    )
    matches = sorted(batch_dir.glob(pattern))
    return matches[-1] if matches else None


def find_full500_isolated_prune_batch(batch_dir: Path, model: str) -> Path | None:
    return find_isolated_schema_prune_batch(
        batch_dir,
        model,
        FULL500_ISOLATED_REPLICAS,
        batch_id=FULL500_ISOLATED_BATCH_ID,
    )


def build_full500_isolated_comparisons(
    batch_dir: Path,
    *,
    models: list[str] | None = None,
) -> dict[str, tuple[dict[str, Any], dict[str, Any]]]:
    """Return {model: (p0_summary, prune_summary)} for full-500 isolated prune @ N=3."""
    out: dict[str, tuple[dict[str, Any], dict[str, Any]]] = {}
    for m in models or DEFAULT_MODELS:
        p0_path = find_full500_p0_batch(batch_dir, m)
        sp_path = find_full500_isolated_prune_batch(batch_dir, m)
        if not p0_path or not sp_path:
            continue
        out[m] = (
            batch_summary(load_batch(p0_path), path=p0_path),
            schema_prune_batch_summary(load_batch(sp_path), path=sp_path),
        )
    return out


def task_flip_counts(
    p0_batch: dict[str, Any],
    prune_batch: dict[str, Any],
    *,
    miss_question_ids: set[int] | None = None,
) -> dict[str, int]:
    """Count per-task EX gains/losses between P0 and isolated prune."""
    p0_ex = {
        int(r["question_id"]): int(r["ex_correct"]) for r in p0_batch.get("rows", [])
    }
    pr_ex = {
        int(r["question_id"]): int(r["ex_correct"]) for r in prune_batch.get("rows", [])
    }
    miss = miss_question_ids or set()
    gained = lost = lost_on_miss = 0
    for qid, was_correct in p0_ex.items():
        now = pr_ex.get(qid)
        if now is None:
            continue
        if was_correct == 0 and now == 1:
            gained += 1
        elif was_correct == 1 and now == 0:
            lost += 1
            if qid in miss:
                lost_on_miss += 1
    return {
        "gained": gained,
        "lost": lost,
        "lost_on_miss": lost_on_miss,
        "net": gained - lost,
    }


def gold_recall_miss_ids(offline_report: dict[str, Any]) -> set[int]:
    return {
        int(r["question_id"])
        for r in offline_report.get("rows", [])
        if float(r.get("gold_table_recall", 1.0)) < 1.0
    }


def build_full500_flip_summaries(
    batch_dir: Path,
    offline_hybrid: dict[str, Any],
    *,
    models: list[str] | None = None,
) -> dict[str, dict[str, int]]:
    """Per-model task flips for full-500 isolated prune vs P0, keyed by model."""
    miss_ids = gold_recall_miss_ids(offline_hybrid)
    out: dict[str, dict[str, int]] = {}
    for m in models or DEFAULT_MODELS:
        p0_path = find_full500_p0_batch(batch_dir, m)
        sp_path = find_full500_isolated_prune_batch(batch_dir, m)
        if not p0_path or not sp_path:
            continue
        out[m] = task_flip_counts(
            load_batch(p0_path),
            load_batch(sp_path),
            miss_question_ids=miss_ids,
        )
    return out


def schema_prune_batch_summary(data: dict[str, Any], *, path: Path | None = None) -> dict[str, Any]:
    summary = batch_summary(data, path=path)
    summary.update(
        {
            "schema_pruning": True,
            "schema_pruning_mode": data.get("schema_pruning_mode", "keyword"),
            "policy_label": "schema_prune",
        }
    )
    return summary


def build_isolated_comparisons(
    batch_dir: Path,
    *,
    model: str | None = None,
    models: list[str] | None = None,
    n_replicas: int = 10,
    versions: tuple[str, ...] = (DEFAULT_ISOLATED_BATCH_VERSION,),
) -> list[tuple[str, dict[str, Any], dict[str, Any]]]:
    """Return [(version, p0_summary, prune_summary), ...] for isolated schema-prune runs.

    Pass ``models`` to load one comparison per model (same batch version).
    Pass ``model`` for a single model (legacy). If both are set, ``models`` wins.
    """
    model_list = list(models or ([model] if model else []))
    if not model_list:
        return []

    pairs: list[tuple[str, dict[str, Any], dict[str, Any]]] = []
    for m in model_list:
        p0_path = find_p0_batch(batch_dir, m, n_replicas)
        if not p0_path:
            continue
        p0 = batch_summary(load_batch(p0_path), path=p0_path)
        for version in versions:
            sp_path = find_isolated_schema_prune_batch(
                batch_dir, m, n_replicas, version=version
            )
            if not sp_path:
                continue
            sp = schema_prune_batch_summary(load_batch(sp_path), path=sp_path)
            pairs.append((f"{version}:{m}", p0, sp))
    return pairs


def build_isolated_comparisons_by_model(
    batch_dir: Path,
    *,
    models: list[str] | None = None,
    n_replicas: int = 10,
    version: str = DEFAULT_ISOLATED_BATCH_VERSION,
) -> dict[str, tuple[dict[str, Any], dict[str, Any]]]:
    """Return {model_key: (p0_summary, prune_summary)} for isolated prune runs."""
    from src.coord.early_stop_analysis import DEFAULT_MODELS

    out: dict[str, tuple[dict[str, Any], dict[str, Any]]] = {}
    for m in models or DEFAULT_MODELS:
        p0_path = find_p0_batch(batch_dir, m, n_replicas)
        sp_path = find_isolated_schema_prune_batch(batch_dir, m, n_replicas, version=version)
        if not p0_path or not sp_path:
            continue
        out[m] = (
            batch_summary(load_batch(p0_path), path=p0_path),
            schema_prune_batch_summary(load_batch(sp_path), path=sp_path),
        )
    return out


def build_p0_vs_full_stack_prune(
    batch_dir: Path,
    *,
    models: list[str] | None = None,
    n_replicas: int,
) -> list[tuple[dict[str, Any], dict[str, Any]]]:
    model_list = list(models or DEFAULT_MODELS)
    batch_id = FULL_STACK_SCHEMA_PRUNE_BATCH_IDS.get(n_replicas, f"fullstack_prune_r{n_replicas}_bo")
    pairs: list[tuple[dict[str, Any], dict[str, Any]]] = []
    for model in model_list:
        p0_path = find_p0_batch(batch_dir, model, n_replicas)
        fsp_path = find_full_stack_schema_prune_batch(
            batch_dir, model, n_replicas, batch_id=batch_id
        )
        if not p0_path or not fsp_path:
            continue
        pairs.append(
            (
                batch_summary(load_batch(p0_path), path=p0_path),
                full_stack_schema_prune_batch_summary(
                    load_batch(fsp_path), path=fsp_path
                ),
            )
        )
    return pairs


def build_full_stack_vs_prune(
    batch_dir: Path,
    *,
    models: list[str] | None = None,
    n_replicas: int,
) -> list[tuple[dict[str, Any], dict[str, Any]]]:
    """Compare full stack (P1+P2+early stop) against the same stack + schema prune."""
    from src.coord.middleware_stack_analysis import FULL_STACK_BATCH_IDS

    model_list = list(models or DEFAULT_MODELS)
    fs_id = FULL_STACK_BATCH_IDS.get(n_replicas)
    fsp_id = FULL_STACK_SCHEMA_PRUNE_BATCH_IDS.get(n_replicas)
    if not fs_id or not fsp_id:
        return []

    pairs: list[tuple[dict[str, Any], dict[str, Any]]] = []
    for model in model_list:
        fs_path = find_full_stack_batch(batch_dir, model, n_replicas, batch_id=fs_id)
        fsp_path = find_full_stack_schema_prune_batch(
            batch_dir, model, n_replicas, batch_id=fsp_id
        )
        if not fs_path or not fsp_path:
            continue
        pairs.append(
            (
                full_stack_batch_summary(load_batch(fs_path), path=fs_path),
                full_stack_schema_prune_batch_summary(
                    load_batch(fsp_path), path=fsp_path
                ),
            )
        )
    return pairs


def comparison_deltas(
    baseline: dict[str, Any], variant: dict[str, Any]
) -> dict[str, float | None]:
    return {
        "ex_pp": (variant.get("ex_accuracy_pct") or 0) - (baseline.get("ex_accuracy_pct") or 0),
        "token_pct": pct_delta(baseline.get("total_tokens", 0), variant.get("total_tokens", 0)),
        "redundancy_pp": (variant.get("avg_explore_redundancy_pct") or 0)
        - (baseline.get("avg_explore_redundancy_pct") or 0),
        "overhead_delta": (variant.get("avg_token_overhead_ratio") or 0)
        - (baseline.get("avg_token_overhead_ratio") or 0),
    }
