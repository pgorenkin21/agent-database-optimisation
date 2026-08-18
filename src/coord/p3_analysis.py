"""Load and summarise P3 semantic-store batch comparisons."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Literal

from src.coord.early_stop_analysis import (
    DEFAULT_MODELS,
    batch_summary as _base_batch_summary,
    find_p0_batch,
    load_batch,
    pct_delta,
)

P3_BATCH_IDS: dict[int, str] = {
    10: "semantic_hybrid_r10_bo",
    25: "semantic_hybrid_r25_bo",
}

P2P3_BATCH_IDS: dict[int, str] = {
    10: "p2p3_hybrid_r10_bo",
}

FULL_STACK_SCHEMA_PRUNE_BATCH_IDS: dict[int, str] = {
    10: "fullstack_prune_r10_bo",
    25: "fullstack_prune_r25_bo",
}

Recommendation = Literal["adopt", "mixed", "avoid", "investigate"]


def find_p2p3_batch(
    batch_dir: Path, model: str, n_replicas: int, *, batch_id: str
) -> Path | None:
    pattern = (
        f"parallel_{batch_id}_{model}_r{n_replicas}_best_of_n"
        f"_p1_cache_p2_discovery_p3_semantic_early_stop_schema_prune.json"
    )
    matches = sorted(batch_dir.glob(pattern))
    return matches[-1] if matches else None


def p2p3_batch_summary(data: dict[str, Any], *, path: Path | None = None) -> dict[str, Any]:
    from src.coord.p2_analysis import p2_batch_summary

    summary = p3_batch_summary(data, path=path)
    p2_extra = p2_batch_summary(data, path=path)
    summary.update(
        {
            "discovery_board": True,
            "semantic_store": True,
            "policy_label": "P2+P3_combined",
            "avg_discovery_fragments": p2_extra.get("avg_discovery_fragments"),
            "avg_discovery_injections_per_task": p2_extra.get("avg_discovery_injections_per_task"),
        }
    )
    return summary


def build_p2p3_combined_rows(
    batch_dir: Path,
    *,
    models: list[str],
    n_replicas: int,
    p2p3_batch_id: str,
    p2_batch_id: str | None = None,
    p3_batch_id: str | None = None,
) -> list[dict[str, Any]]:
    """Summarise P2+P3 vs P2 full stack+prune and P3-only for thesis table."""
    p2_id = p2_batch_id or FULL_STACK_SCHEMA_PRUNE_BATCH_IDS.get(n_replicas, "")
    p3_id = p3_batch_id or P3_BATCH_IDS.get(n_replicas, "")
    rows: list[dict[str, Any]] = []
    for model in models:
        p2p3_path = find_p2p3_batch(batch_dir, model, n_replicas, batch_id=p2p3_batch_id)
        if not p2p3_path:
            continue
        combined = p2p3_batch_summary(load_batch(p2p3_path), path=p2p3_path)
        row: dict[str, Any] = {"model_key": model, "p2p3": combined}
        p2_path = find_full_stack_schema_prune_batch(batch_dir, model, n_replicas, batch_id=p2_id)
        p3_path = find_p3_batch(batch_dir, model, n_replicas, batch_id=p3_id)
        if p2_path:
            from src.coord.middleware_stack_analysis import full_stack_schema_prune_batch_summary

            row["p2_full_stack_prune"] = full_stack_schema_prune_batch_summary(
                load_batch(p2_path), path=p2_path
            )
            row["vs_p2"] = compare_row(row["p2_full_stack_prune"], combined)
        if p3_path:
            row["p3_only"] = p3_batch_summary(load_batch(p3_path), path=p3_path)
            row["vs_p3"] = compare_row(row["p3_only"], combined)
        rows.append(row)
    return rows


def find_p3_batch(
    batch_dir: Path, model: str, n_replicas: int, *, batch_id: str
) -> Path | None:
    pattern = (
        f"parallel_{batch_id}_{model}_r{n_replicas}_best_of_n"
        f"_p1_cache_p3_semantic_early_stop_schema_prune.json"
    )
    matches = sorted(batch_dir.glob(pattern))
    return matches[-1] if matches else None


def p3_batch_summary(data: dict[str, Any], *, path: Path | None = None) -> dict[str, Any]:
    summary = _base_batch_summary(data, path=path)
    rows = data.get("rows", [])
    total_publishes = sum(int(r.get("semantic_publishes", 0)) for r in rows)
    total_facts = sum(int(r.get("semantic_facts_added", 0)) for r in rows)
    total_injections = sum(int(r.get("semantic_injections", 0)) for r in rows)
    total_chars = sum(int(r.get("semantic_injected_chars", 0)) for r in rows)
    summary.update(
        {
            "semantic_store": bool(data.get("semantic_store", True)),
            "schema_pruning": bool(data.get("schema_pruning", False)),
            "schema_pruning_mode": data.get("schema_pruning_mode", "hybrid"),
            "policy_label": "P3_semantic",
            "shared_cache": bool(data.get("shared_cache", True)),
            "early_stop": bool(data.get("early_stop", True)),
            "discovery_board": False,
            "avg_cache_hit_rate_pct": data.get("avg_cache_hit_rate_pct"),
            "total_semantic_publishes": total_publishes,
            "total_semantic_facts_added": total_facts,
            "total_semantic_injections": total_injections,
            "total_semantic_injected_chars": total_chars,
            "avg_semantic_injections_per_task": round(total_injections / len(rows), 2)
            if rows
            else 0.0,
            "avg_semantic_facts_per_task": round(total_facts / len(rows), 2) if rows else 0.0,
            "early_stop_triggered_count": sum(
                1 for r in rows if r.get("early_stop_triggered")
            ),
        }
    )
    return summary


def build_p3_vs_p0(
    batch_dir: Path,
    *,
    models: list[str],
    n_replicas: int,
    p3_batch_id: str,
) -> list[tuple[dict[str, Any], dict[str, Any]]]:
    pairs: list[tuple[dict[str, Any], dict[str, Any]]] = []
    for model in models:
        p0_path = find_p0_batch(batch_dir, model, n_replicas)
        p3_path = find_p3_batch(batch_dir, model, n_replicas, batch_id=p3_batch_id)
        if not p0_path or not p3_path:
            continue
        pairs.append(
            (
                _base_batch_summary(load_batch(p0_path), path=p0_path),
                p3_batch_summary(load_batch(p3_path), path=p3_path),
            )
        )
    return pairs


def find_full_stack_schema_prune_batch(
    batch_dir: Path, model: str, n_replicas: int, *, batch_id: str
) -> Path | None:
    pattern = (
        f"parallel_{batch_id}_{model}_r{n_replicas}_best_of_n"
        f"_p1_cache_p2_discovery_early_stop_schema_prune.json"
    )
    matches = sorted(batch_dir.glob(pattern))
    return matches[-1] if matches else None


def build_p3_vs_full_stack_prune(
    batch_dir: Path,
    *,
    models: list[str],
    n_replicas: int,
    p3_batch_id: str,
    p2_batch_id: str | None = None,
) -> list[tuple[dict[str, Any], dict[str, Any]]]:
    """Compare P3 semantic stack vs P2 full stack + schema prune (apples-to-apples layers)."""
    from src.coord.middleware_stack_analysis import full_stack_schema_prune_batch_summary

    pairs: list[tuple[dict[str, Any], dict[str, Any]]] = []
    p2_id = p2_batch_id or FULL_STACK_SCHEMA_PRUNE_BATCH_IDS.get(n_replicas, "")
    if not p2_id:
        return pairs
    for model in models:
        p2_path = find_full_stack_schema_prune_batch(
            batch_dir, model, n_replicas, batch_id=p2_id
        )
        p3_path = find_p3_batch(batch_dir, model, n_replicas, batch_id=p3_batch_id)
        if not p2_path or not p3_path:
            continue
        pairs.append(
            (
                full_stack_schema_prune_batch_summary(load_batch(p2_path), path=p2_path),
                p3_batch_summary(load_batch(p3_path), path=p3_path),
            )
        )
    return pairs


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
        "baseline_label": baseline.get("policy_label", "baseline"),
        "variant_label": variant.get("policy_label", "P3"),
        "baseline_ex_pct": baseline.get("ex_accuracy_pct"),
        "variant_ex_pct": variant.get("ex_accuracy_pct"),
        "ex_delta_pp": round(ex_delta, 1),
        "baseline_tokens": baseline.get("total_tokens"),
        "variant_tokens": variant.get("total_tokens"),
        "token_delta_pct": round(tok_delta, 2) if tok_delta is not None else None,
        "redundancy_delta_pp": round(red_delta, 1),
        "baseline_path": baseline.get("path"),
        "variant_path": variant.get("path"),
        "avg_semantic_injections_per_task": variant.get("avg_semantic_injections_per_task"),
        "avg_cache_hit_rate_pct": variant.get("avg_cache_hit_rate_pct"),
    }


def recommend_p3_vs_p2(row: dict[str, Any]) -> tuple[Recommendation, str]:
    """Heuristic thesis recommendation for P3 vs P2 full stack+prune."""
    ex_d = row.get("ex_delta_pp", 0) or 0
    tok_d = row.get("token_delta_pct")
    if tok_d is None:
        return "investigate", "Missing token totals."

    if ex_d >= 0 and tok_d <= -3:
        return "adopt", f"EX {ex_d:+.0f} pp and tokens {tok_d:+.1f}% vs P2 full stack+prune."
    if ex_d >= -2 and abs(tok_d) <= 3:
        return "mixed", f"Token-neutral ({tok_d:+.1f}%) with modest EX change ({ex_d:+.0f} pp)."
    if ex_d < -2 and tok_d > 5:
        return "avoid", f"EX {ex_d:+.0f} pp and tokens {tok_d:+.1f}% — prefer P2 full stack+prune."
    if ex_d < -2:
        return "mixed", f"EX {ex_d:+.0f} pp; consider P2+P3 combined or P2 alone."
    if tok_d > 10:
        return "investigate", f"Token spend rose {tok_d:+.1f}% — check timeouts/retries."
    return "mixed", f"EX {ex_d:+.0f} pp, tokens {tok_d:+.1f}%."


def load_comparisons_by_replica_counts(
    batch_dir: Path,
    *,
    models: list[str] | None = None,
    replica_counts: list[int] | None = None,
) -> dict[str, Any]:
    model_list = list(models or DEFAULT_MODELS)
    counts = replica_counts or sorted(P3_BATCH_IDS)
    out: dict[str, Any] = {"vs_p0": {}, "vs_full_stack_prune": {}, "recommendations": {}, "p2p3_combined": {}}
    for n in counts:
        p3_id = P3_BATCH_IDS.get(n, f"semantic_hybrid_r{n}_bo")
        p0_pairs = build_p3_vs_p0(batch_dir, models=model_list, n_replicas=n, p3_batch_id=p3_id)
        p2_pairs = build_p3_vs_full_stack_prune(
            batch_dir, models=model_list, n_replicas=n, p3_batch_id=p3_id
        )
        if p0_pairs:
            out["vs_p0"][n] = [
                {"p0": p0, "p3": p3, "delta": compare_row(p0, p3)} for p0, p3 in p0_pairs
            ]
        if p2_pairs:
            rows = []
            recs = {}
            for p2, p3 in p2_pairs:
                delta = compare_row(p2, p3)
                rec, reason = recommend_p3_vs_p2(delta)
                delta["recommendation"] = rec
                delta["recommendation_reason"] = reason
                rows.append({"p2_full_stack_prune": p2, "p3": p3, "delta": delta})
                recs[p3["model_key"]] = {"recommendation": rec, "reason": reason, **delta}
            out["vs_full_stack_prune"][n] = rows
            out["recommendations"][n] = recs
        p2p3_id = P2P3_BATCH_IDS.get(n)
        if p2p3_id:
            out["p2p3_combined"][n] = build_p2p3_combined_rows(
                batch_dir,
                models=model_list,
                n_replicas=n,
                p2p3_batch_id=p2p3_id,
                p2_batch_id=FULL_STACK_SCHEMA_PRUNE_BATCH_IDS.get(n),
                p3_batch_id=p3_id,
            )
    return out
