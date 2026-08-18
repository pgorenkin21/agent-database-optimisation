"""Analyse heterogeneous multi-model parallel batches (one model per replica)."""

from __future__ import annotations

import json
from collections import Counter
from pathlib import Path
from typing import Any


MODEL_LABELS: dict[str, str] = {
    "gpt-4o-mini": "GPT-4o mini",
    "gemini-2.5-flash": "Gemini 2.5 Flash",
    "deepseek-v3.2": "DeepSeek V3.2",
}


def _replica_ex_from_coord_trace(trace_path: Path, models: list[str]) -> dict[str, int]:
    per = {m: 0 for m in models}
    if not trace_path.exists():
        return per
    for line in trace_path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        event = json.loads(line)
        if event.get("event") != "replica_end":
            continue
        model = event.get("model")
        if model in per:
            per[model] = int(event.get("ex_correct") or 0)
    return per


def load_ensemble_batch(batch_json: Path) -> dict[str, Any]:
    payload = json.loads(batch_json.read_text(encoding="utf-8"))
    models = list(payload.get("replica_model_keys") or [])
    if not models and payload.get("model_key"):
        models = [payload["model_key"]]

    task_rows: list[dict[str, Any]] = []
    for row in payload.get("rows", []):
        per = _replica_ex_from_coord_trace(Path(row["coord_trace_path"]), models)
        correct_models = [m for m in models if per.get(m) == 1]
        task_rows.append(
            {
                "question_id": row["question_id"],
                "db_id": row["db_id"],
                "difficulty": row["difficulty"],
                "ensemble_ex": int(row.get("ex_correct") or 0),
                "chosen_model_key": row.get("chosen_model_key") or "",
                "per_model_ex": per,
                "n_correct": sum(per.values()),
                "correct_models": correct_models,
            }
        )

    return {
        "batch_id": payload.get("batch_id"),
        "models": models,
        "task_count": len(task_rows),
        "ex_accuracy_pct": payload.get("ex_accuracy_pct"),
        "total_prompt_tokens": payload.get("total_prompt_tokens", 0),
        "total_completion_tokens": payload.get("total_completion_tokens", 0),
        "avg_token_overhead_ratio": payload.get("avg_token_overhead_ratio"),
        "avg_explore_redundancy_pct": payload.get("avg_explore_redundancy_pct"),
        "api_failure_count": payload.get("api_failure_count", 0),
        "rows": task_rows,
    }


def summarize_ensemble(batch: dict[str, Any]) -> dict[str, Any]:
    models: list[str] = batch["models"]
    rows: list[dict[str, Any]] = batch["rows"]
    n = len(rows)
    if n == 0:
        raise ValueError("No rows in ensemble batch")

    model_ex = {m: sum(r["per_model_ex"].get(m, 0) for r in rows) for m in models}
    ensemble_ex = sum(r["ensemble_ex"] for r in rows)
    n_correct_dist = Counter(r["n_correct"] for r in rows)

    solo = Counter()
    pairs = Counter()
    for r in rows:
        cms = tuple(r["correct_models"])
        if len(cms) == 1:
            solo[cms[0]] += 1
        elif len(cms) == 2:
            pairs["+".join(cms)] += 1

    by_diff: dict[str, dict[str, Any]] = {}
    for r in rows:
        d = r["difficulty"]
        bucket = by_diff.setdefault(
            d,
            {"n": 0, "ensemble": 0, "model_ex": {m: 0 for m in models}},
        )
        bucket["n"] += 1
        bucket["ensemble"] += r["ensemble_ex"]
        for m in models:
            bucket["model_ex"][m] += r["per_model_ex"].get(m, 0)

    chosen_when_ex1 = Counter(r["chosen_model_key"] for r in rows if r["ensemble_ex"] == 1)
    best_single_model = max(models, key=lambda m: model_ex[m])
    best_single_ex = model_ex[best_single_model]

    return {
        "task_count": n,
        "ensemble_ex": ensemble_ex,
        "ensemble_ex_pct": round(100.0 * ensemble_ex / n, 1),
        "model_ex": model_ex,
        "model_ex_pct": {m: round(100.0 * model_ex[m] / n, 1) for m in models},
        "lift_vs_best_single_pp": round(
            100.0 * (ensemble_ex - best_single_ex) / n, 1
        ),
        "best_single_model": best_single_model,
        "best_single_ex": best_single_ex,
        "best_single_ex_pct": round(100.0 * best_single_ex / n, 1),
        "n_correct_dist": {int(k): int(v) for k, v in sorted(n_correct_dist.items())},
        "partial_count": int(n_correct_dist.get(1, 0) + n_correct_dist.get(2, 0)),
        "solo_wins": dict(solo),
        "pair_wins": dict(pairs),
        "by_difficulty": {
            d: {
                "n": v["n"],
                "ensemble_pct": round(100.0 * v["ensemble"] / v["n"], 1),
                "model_ex_pct": {
                    m: round(100.0 * v["model_ex"][m] / v["n"], 1) for m in models
                },
            }
            for d, v in by_diff.items()
        },
        "chosen_when_ex1": dict(chosen_when_ex1),
        "total_prompt_tokens": batch.get("total_prompt_tokens", 0),
        "total_completion_tokens": batch.get("total_completion_tokens", 0),
        "avg_token_overhead_ratio": batch.get("avg_token_overhead_ratio"),
        "avg_explore_redundancy_pct": batch.get("avg_explore_redundancy_pct"),
        "api_failure_count": batch.get("api_failure_count", 0),
        "batch_id": batch.get("batch_id"),
        "models": models,
    }


def build_ensemble_report(batch_json: Path) -> dict[str, Any]:
    batch = load_ensemble_batch(batch_json)
    summary = summarize_ensemble(batch)
    return {"summary": summary, "rows": batch["rows"]}
