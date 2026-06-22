"""Load and summarise early-stop vs P0 batch comparisons."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from src.coord.interaction_metrics import batch_interaction_summary


def load_batch(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def batch_summary(data: dict[str, Any], *, path: Path | None = None) -> dict[str, Any]:
    rows = data.get("rows", [])
    triggered = [r for r in rows if r.get("early_stop_triggered")]
    not_triggered = [r for r in rows if not r.get("early_stop_triggered")]
    total_tokens = sum(
        r.get("total_prompt_tokens", 0) + r.get("total_completion_tokens", 0) for r in rows
    )
    avg_cancel = (
        sum(r.get("replicas_cancelled", 0) for r in rows) / len(rows) if rows else 0.0
    )
    tok_triggered = (
        sum(r.get("total_prompt_tokens", 0) + r.get("total_completion_tokens", 0) for r in triggered)
        / len(triggered)
        if triggered
        else None
    )
    tok_not = (
        sum(r.get("total_prompt_tokens", 0) + r.get("total_completion_tokens", 0) for r in not_triggered)
        / len(not_triggered)
        if not_triggered
        else None
    )
    api_failures = sum(1 for r in rows if r.get("error"))
    completed = [r for r in rows if not r.get("error")]
    ex_excl = (
        100.0 * sum(r.get("ex_correct", 0) for r in completed) / len(completed)
        if completed
        else None
    )
    return {
        "path": str(path.resolve()) if path else data.get("_path", ""),
        "batch_id": data.get("batch_id", ""),
        "model_key": data.get("model_key", ""),
        "policy": data.get("policy", ""),
        "n_replicas": data.get("n_replicas"),
        "early_stop": bool(data.get("early_stop", False)),
        "task_count": len(rows),
        "ex_accuracy_pct": data.get("ex_accuracy_pct"),
        "api_failure_count": data.get("api_failure_count", api_failures),
        "ex_accuracy_excluding_api_errors_pct": data.get(
            "ex_accuracy_excluding_api_errors_pct", ex_excl
        ),
        "avg_explore_redundancy_pct": data.get("avg_explore_redundancy_pct"),
        "avg_token_overhead_ratio": data.get("avg_token_overhead_ratio"),
        "total_tokens": total_tokens,
        "early_stop_triggered_count": len(triggered),
        "avg_replicas_cancelled": round(avg_cancel, 2),
        "avg_tokens_per_task_triggered": round(tok_triggered) if tok_triggered is not None else None,
        "avg_tokens_per_task_not_triggered": round(tok_not) if tok_not is not None else None,
        **batch_interaction_summary(rows),
    }


def find_p0_batch(batch_dir: Path, model: str, n_replicas: int) -> Path | None:
    pattern = f"*baseline_r{n_replicas}_{model}_r{n_replicas}_best_of_n.json"
    matches = sorted(batch_dir.glob(f"parallel_{pattern}"))
    return matches[-1] if matches else None


def find_early_stop_batch(
    batch_dir: Path, model: str, n_replicas: int, *, batch_id: str
) -> Path | None:
    pattern = f"parallel_{batch_id}_{model}_r{n_replicas}_best_of_n_early_stop.json"
    matches = sorted(batch_dir.glob(pattern))
    return matches[-1] if matches else None


def pct_delta(baseline: float | int | None, variant: float | int | None) -> float | None:
    if baseline is None or variant is None or baseline == 0:
        return None
    return 100.0 * (float(variant) - float(baseline)) / float(baseline)


def build_comparisons(
    batch_dir: Path,
    *,
    models: list[str],
    n_replicas: int,
    early_stop_batch_id: str,
) -> list[tuple[dict[str, Any], dict[str, Any]]]:
    pairs: list[tuple[dict[str, Any], dict[str, Any]]] = []
    for model in models:
        p0_path = find_p0_batch(batch_dir, model, n_replicas)
        es_path = find_early_stop_batch(
            batch_dir, model, n_replicas, batch_id=early_stop_batch_id
        )
        if not p0_path or not es_path:
            continue
        p0_data = load_batch(p0_path)
        es_data = load_batch(es_path)
        pairs.append(
            (
                batch_summary(p0_data, path=p0_path),
                batch_summary(es_data, path=es_path),
            )
        )
    return pairs


EARLY_STOP_BATCH_IDS: dict[int, str] = {
    10: "earlystop_r10_bo",
    25: "earlystop_r25_bo",
}

DEFAULT_MODELS: tuple[str, ...] = (
    "gpt-4o-mini",
    "gemini-2.5-flash",
    "deepseek-v3.2",
)
