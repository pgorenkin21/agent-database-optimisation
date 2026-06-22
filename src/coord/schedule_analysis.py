"""Load and summarise temperature / stagger schedule sweep batches."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Literal

from src.coord.early_stop_analysis import (
    DEFAULT_MODELS,
    batch_summary,
    load_batch,
    pct_delta,
)
from src.coord.middleware_stack_analysis import (
    FULL_STACK_SCHEMA_PRUNE_BATCH_IDS,
    find_full_stack_schema_prune_batch,
    full_stack_schema_prune_batch_summary,
)

SCHEDULE_SWEEP_IDS: dict[int, str] = {
    10: "sched_r10_bo",
}

# Longest labels first for batch_id parsing.
SCHEDULE_SCENARIOS: list[str] = [
    "t03_stag2s",
    "stag2s",
    "stag1t",
    "ladder",
    "t07",
    "t03",
    "t0",
]

Recommendation = Literal["adopt", "mixed", "avoid", "investigate"]


def sweep_id_from_batch_id(batch_id: str) -> str | None:
    for sid in SCHEDULE_SWEEP_IDS.values():
        if batch_id.startswith(f"{sid}_"):
            return sid
    return None


def scenario_from_batch_id(batch_id: str, *, sweep_id: str | None = None) -> str | None:
    sid = sweep_id or sweep_id_from_batch_id(batch_id)
    if not sid:
        return None
    prefix = f"{sid}_"
    if not batch_id.startswith(prefix):
        return None
    rest = batch_id[len(prefix) :]
    for label in SCHEDULE_SCENARIOS:
        if rest.startswith(f"{label}_") or rest == label:
            return label
    return None


def find_schedule_batch(
    batch_dir: Path,
    model: str,
    scenario: str,
    *,
    sweep_id: str,
) -> Path | None:
    safe = model.replace(".", "-")
    pattern = f"parallel_{sweep_id}_{scenario}_{safe}_*.json"
    matches = sorted(batch_dir.glob(pattern))
    for path in reversed(matches):
        data = load_batch(path)
        rows = data.get("rows", [])
        if rows and all(r.get("error") for r in rows):
            continue
        return path
    return matches[-1] if matches else None


def schedule_batch_summary(data: dict[str, Any], *, path: Path | None = None) -> dict[str, Any]:
    summary = batch_summary(data, path=path)
    batch_id = summary.get("batch_id", "")
    sweep_id = sweep_id_from_batch_id(batch_id) or data.get("sweep_id", "")
    scenario = scenario_from_batch_id(batch_id, sweep_id=sweep_id)
    summary.update(
        {
            "scenario": scenario,
            "sweep_id": sweep_id,
            "replica_schedule": data.get("replica_schedule"),
            "schema_pruning_mode": data.get("schema_pruning_mode"),
            "policy_label": f"schedule_{scenario}" if scenario else "schedule",
        }
    )
    return summary


def load_schedule_sweep(
    batch_dir: Path,
    *,
    models: list[str] | None = None,
    sweep_id: str | None = None,
    n_replicas: int = 10,
) -> dict[str, list[dict[str, Any]]]:
    """Return {model_key: [scenario summaries sorted by SCHEDULE_SCENARIOS]}."""
    sid = sweep_id or SCHEDULE_SWEEP_IDS.get(n_replicas, "sched_r10_bo")
    model_list = list(models or DEFAULT_MODELS)
    out: dict[str, list[dict[str, Any]]] = {}
    for model in model_list:
        rows: list[dict[str, Any]] = []
        for scenario in SCHEDULE_SCENARIOS:
            path = find_schedule_batch(batch_dir, model, scenario, sweep_id=sid)
            if not path:
                continue
            rows.append(schedule_batch_summary(load_batch(path), path=path))
        if rows:
            out[model] = rows
    return out


def compare_row(
    baseline: dict[str, Any],
    variant: dict[str, Any],
) -> dict[str, Any]:
    ex_delta = (variant.get("ex_accuracy_pct") or 0) - (baseline.get("ex_accuracy_pct") or 0)
    red_delta = (variant.get("avg_explore_redundancy_pct") or 0) - (
        baseline.get("avg_explore_redundancy_pct") or 0
    )
    tok_delta = pct_delta(baseline.get("total_tokens"), variant.get("total_tokens"))
    return {
        "model_key": variant.get("model_key"),
        "baseline_scenario": baseline.get("scenario", "t0"),
        "variant_scenario": variant.get("scenario"),
        "baseline_ex_pct": baseline.get("ex_accuracy_pct"),
        "variant_ex_pct": variant.get("ex_accuracy_pct"),
        "ex_delta_pp": round(ex_delta, 1),
        "baseline_tokens": baseline.get("total_tokens"),
        "variant_tokens": variant.get("total_tokens"),
        "token_delta_pct": round(tok_delta, 2) if tok_delta is not None else None,
        "redundancy_delta_pp": round(red_delta, 1),
        "baseline_path": baseline.get("path"),
        "variant_path": variant.get("path"),
    }


def recommend_schedule(
    t0: dict[str, Any],
    candidate: dict[str, Any],
) -> tuple[Recommendation, str]:
    ex_d = (candidate.get("ex_accuracy_pct") or 0) - (t0.get("ex_accuracy_pct") or 0)
    tok_d = pct_delta(t0.get("total_tokens"), candidate.get("total_tokens"))
    red_d = (candidate.get("avg_explore_redundancy_pct") or 0) - (
        t0.get("avg_explore_redundancy_pct") or 0
    )
    label = candidate.get("scenario", "?")

    if tok_d is None:
        return "investigate", "Missing token totals."

    if ex_d >= 0 and tok_d <= -5:
        return "adopt", f"EX {ex_d:+.0f} pp and tokens {tok_d:+.1f}% vs t0."
    if ex_d >= -2 and tok_d <= -10 and red_d <= -10:
        return "adopt", f"Tokens {tok_d:+.1f}% and redundancy {red_d:+.0f} pp vs t0; EX {ex_d:+.0f} pp."
    if ex_d >= 2 and tok_d <= 5:
        return "adopt", f"EX +{ex_d:.0f} pp with modest token cost ({tok_d:+.1f}%)."
    if ex_d < -4:
        return "avoid", f"EX {ex_d:+.0f} pp vs t0."
    if tok_d > 15 and ex_d <= 0:
        return "avoid", f"Tokens +{tok_d:.1f}% without EX gain."
    return "mixed", f"EX {ex_d:+.0f} pp, tokens {tok_d:+.1f}%, redundancy {red_d:+.0f} pp vs t0."


def pick_best_schedule(scenarios: list[dict[str, Any]]) -> dict[str, Any]:
    """Heuristic: maximise EX, then minimise tokens among top EX."""
    if not scenarios:
        return {}
    max_ex = max(s.get("ex_accuracy_pct") or 0 for s in scenarios)
    tied = [s for s in scenarios if (s.get("ex_accuracy_pct") or 0) >= max_ex - 0.5]
    return min(tied, key=lambda s: s.get("total_tokens") or 0)


def build_schedule_comparisons(
    batch_dir: Path,
    *,
    models: list[str] | None = None,
    sweep_id: str | None = None,
    n_replicas: int = 10,
    include_p2_prune: bool = True,
) -> dict[str, Any]:
    sweep = load_schedule_sweep(
        batch_dir,
        models=models,
        sweep_id=sweep_id,
        n_replicas=n_replicas,
    )
    sid = sweep_id or SCHEDULE_SWEEP_IDS.get(n_replicas, "sched_r10_bo")
    p2_id = FULL_STACK_SCHEMA_PRUNE_BATCH_IDS.get(n_replicas, "")

    by_model: dict[str, Any] = {}
    recommendations: dict[str, dict[str, Any]] = {}

    for model, scenarios in sweep.items():
        t0 = next((s for s in scenarios if s.get("scenario") == "t0"), scenarios[0])
        vs_t0 = []
        recs: dict[str, Any] = {}
        for s in scenarios:
            if s.get("scenario") == "t0":
                continue
            delta = compare_row(t0, s)
            rec, reason = recommend_schedule(t0, s)
            delta["recommendation"] = rec
            delta["recommendation_reason"] = reason
            vs_t0.append({"baseline": t0, "variant": s, "delta": delta})
            recs[s["scenario"]] = {"recommendation": rec, "reason": reason, **delta}

        best = pick_best_schedule(scenarios)
        entry: dict[str, Any] = {
            "scenarios": scenarios,
            "t0": t0,
            "best": best,
            "vs_t0": vs_t0,
            "recommendations": recs,
        }

        if include_p2_prune and p2_id:
            p2_path = find_full_stack_schema_prune_batch(
                batch_dir, model, n_replicas, batch_id=p2_id
            )
            if p2_path and best:
                p2 = full_stack_schema_prune_batch_summary(load_batch(p2_path), path=p2_path)
                entry["p2_full_stack_prune"] = p2
                entry["best_vs_p2_prune"] = compare_row(p2, best)

        recommendations[model] = {
            "best_scenario": best.get("scenario"),
            "best_ex_pct": best.get("ex_accuracy_pct"),
            "best_tokens": best.get("total_tokens"),
            "t0_ex_pct": t0.get("ex_accuracy_pct"),
            "scenario_recs": recs,
        }
        by_model[model] = entry

    return {
        "sweep_id": sid,
        "n_replicas": n_replicas,
        "by_model": by_model,
        "recommendations": recommendations,
    }
