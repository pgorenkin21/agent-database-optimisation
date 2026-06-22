"""Load cross-chapter stack summaries for thesis synthesis (Chapter 9)."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Literal

from src.coord.early_stop_analysis import DEFAULT_MODELS, batch_summary, load_batch, pct_delta
from src.coord.middleware_stack_analysis import (
    FULL_STACK_SCHEMA_PRUNE_BATCH_IDS,
    find_full_stack_schema_prune_batch,
    full_stack_schema_prune_batch_summary,
)
from src.coord.p3_analysis import P3_BATCH_IDS, find_p3_batch, p3_batch_summary
from src.coord.schedule_analysis import (
    SCHEDULE_SCENARIOS,
    find_schedule_batch,
    pick_best_schedule,
    schedule_batch_summary,
    load_schedule_sweep,
)

SCHED_P2_GEMINI_BATCH_ID = "sched_p2_t03_stag2s_r10_bo"

# Per-model best schedule scenario from Chapter 8 (N=10 smoke subset).
BEST_SCHEDULE_SCENARIO: dict[str, str] = {
    "gemini-2.5-flash": "t03_stag2s",
    "gpt-4o-mini": "t03_stag2s",
    "deepseek-v3.2": "ladder",
}

StackRole = Literal[
    "p2_prune",
    "p3_only",
    "best_schedule",
    "sched_p2_gemini",
    "recommended",
]


def find_sched_p2_gemini_batch(batch_dir: Path, *, batch_id: str = SCHED_P2_GEMINI_BATCH_ID) -> Path | None:
    pattern = f"parallel_{batch_id}_gemini-2.5-flash_*.json"
    matches = sorted(batch_dir.glob(pattern))
    for path in reversed(matches):
        data = load_batch(path)
        rows = data.get("rows", [])
        if rows and all(r.get("error") for r in rows):
            continue
        return path
    return matches[-1] if matches else None


def stack_summary(data: dict[str, Any], *, path: Path | None = None, role: str) -> dict[str, Any]:
    if role == "p3_only":
        summary = p3_batch_summary(data, path=path)
    elif role in ("best_schedule", "sched_p2_gemini"):
        summary = schedule_batch_summary(data, path=path)
    elif role == "p2_prune":
        summary = full_stack_schema_prune_batch_summary(data, path=path)
    else:
        summary = batch_summary(data, path=path)
    summary["stack_role"] = role
    return summary


def load_model_stacks(
    batch_dir: Path,
    model: str,
    *,
    n_replicas: int = 10,
    sweep_id: str = "sched_r10_bo",
) -> dict[str, dict[str, Any]]:
    """Return labelled stack summaries available for one model."""
    out: dict[str, dict[str, Any]] = {}

    p2_id = FULL_STACK_SCHEMA_PRUNE_BATCH_IDS.get(n_replicas, "fullstack_prune_r10_bo")
    p2_path = find_full_stack_schema_prune_batch(batch_dir, model, n_replicas, batch_id=p2_id)
    if p2_path:
        out["p2_prune"] = stack_summary(load_batch(p2_path), path=p2_path, role="p2_prune")

    p3_id = P3_BATCH_IDS.get(n_replicas, "semantic_hybrid_r10_bo")
    p3_path = find_p3_batch(batch_dir, model, n_replicas, batch_id=p3_id)
    if p3_path:
        out["p3_only"] = stack_summary(load_batch(p3_path), path=p3_path, role="p3_only")

    scenario = BEST_SCHEDULE_SCENARIO.get(model, "t03_stag2s")
    sched_path = find_schedule_batch(batch_dir, model, scenario, sweep_id=sweep_id)
    if sched_path:
        out["best_schedule"] = stack_summary(load_batch(sched_path), path=sched_path, role="best_schedule")

    if model == "gemini-2.5-flash":
        p2_sched_path = find_sched_p2_gemini_batch(batch_dir)
        if p2_sched_path:
            out["sched_p2_gemini"] = stack_summary(
                load_batch(p2_sched_path), path=p2_sched_path, role="sched_p2_gemini"
            )

    return out


def recommend_stack(model: str, stacks: dict[str, dict[str, Any]]) -> dict[str, Any]:
    """Pick recommended deployment stack and rationale for one model."""
    sched = stacks.get("best_schedule")
    p2 = stacks.get("p2_prune")
    p3 = stacks.get("p3_only")
    sched_p2 = stacks.get("sched_p2_gemini")

    if model == "gemini-2.5-flash" and sched:
        # Schedule+P2 follow-up: P2 on top of t03_stag2s drops EX without token win.
        if sched_p2:
            ex_delta = (sched_p2.get("ex_accuracy_pct") or 0) - (sched.get("ex_accuracy_pct") or 0)
            tok_delta = pct_delta(sched.get("total_tokens"), sched_p2.get("total_tokens"))
            p2_hurts = ex_delta < -1 or (tok_delta is not None and tok_delta > 2)
        else:
            p2_hurts = True
        return {
            "model_key": model,
            "recommended_role": "best_schedule",
            "recommended": sched,
            "stack_label": _schedule_label(sched),
            "rationale": (
                f"`t03_stag2s` + P1 + early stop + hybrid prune — "
                f"{sched.get('ex_accuracy_pct')}% EX, "
                f"{sched.get('total_tokens', 0):,} tokens. "
                + (
                    "P2 discovery on top drops EX −2 pp with flat tokens (§9.4); omit P2."
                    if sched_p2 and p2_hurts
                    else "Beats P2+prune on EX and tokens."
                )
            ),
            "alternatives": _alternatives(stacks, exclude={"best_schedule"}),
            "sched_p2_followup": sched_p2,
        }

    if model == "gpt-4o-mini" and p3:
        return {
            "model_key": model,
            "recommended_role": "p3_only",
            "recommended": p3,
            "stack_label": "P3 semantic store + P1 + early stop + hybrid prune",
            "rationale": (
                f"P3 replaces P2 fragment injection — {p3.get('ex_accuracy_pct')}% EX, "
                f"{p3.get('total_tokens', 0):,} tokens vs P2+prune "
                f"{(p2.get('ex_accuracy_pct') if p2 else '?')}% / "
                f"{(p2.get('total_tokens', 0) if p2 else 0):,} tokens."
            ),
            "alternatives": _alternatives(stacks, exclude={"p3_only"}),
            "sched_p2_followup": None,
        }

    if model == "deepseek-v3.2" and p2:
        alt_note = ""
        if sched:
            ex_d = (sched.get("ex_accuracy_pct") or 0) - (p2.get("ex_accuracy_pct") or 0)
            tok_d = pct_delta(p2.get("total_tokens"), sched.get("total_tokens"))
            if ex_d > 0 and tok_d is not None and tok_d > 10:
                alt_note = (
                    f" Schedule `{sched.get('scenario')}` raises EX +{ex_d:.0f} pp "
                    f"but tokens +{tok_d:.1f}% — not cost-effective."
                )
        return {
            "model_key": model,
            "recommended_role": "p2_prune",
            "recommended": p2,
            "stack_label": "P2 discovery + P1 + early stop + hybrid prune",
            "rationale": (
                f"Lowest token budget at acceptable EX — {p2.get('ex_accuracy_pct')}% EX, "
                f"{p2.get('total_tokens', 0):,} tokens."
                + alt_note
            ),
            "alternatives": _alternatives(stacks, exclude={"p2_prune"}),
            "sched_p2_followup": None,
        }

    # Fallback: highest EX then lowest tokens among available stacks.
    candidates = list(stacks.values())
    if not candidates:
        return {"model_key": model, "recommended": {}, "rationale": "No batches found."}
    best = pick_best_schedule(candidates)
    return {
        "model_key": model,
        "recommended_role": best.get("stack_role", "unknown"),
        "recommended": best,
        "stack_label": best.get("policy_label", "unknown"),
        "rationale": "Best available on subset.",
        "alternatives": [],
        "sched_p2_followup": None,
    }


def _schedule_label(summary: dict[str, Any]) -> str:
    scenario = summary.get("scenario") or "schedule"
    return f"`{scenario}` + P1 + early stop + hybrid prune (no P2)"


def _alternatives(
    stacks: dict[str, dict[str, Any]], *, exclude: set[str]
) -> list[dict[str, Any]]:
    alts: list[dict[str, Any]] = []
    for role, summary in stacks.items():
        if role in exclude:
            continue
        alts.append({"role": role, **summary})
    return alts


def build_synthesis(
    batch_dir: Path,
    *,
    models: list[str] | None = None,
    n_replicas: int = 10,
    sweep_id: str = "sched_r10_bo",
) -> dict[str, Any]:
    model_list = list(models or DEFAULT_MODELS)
    by_model: dict[str, Any] = {}
    recommendations: dict[str, Any] = {}

    for model in model_list:
        stacks = load_model_stacks(batch_dir, model, n_replicas=n_replicas, sweep_id=sweep_id)
        rec = recommend_stack(model, stacks)
        by_model[model] = {"stacks": stacks, "recommendation": rec}
        recommendations[model] = rec

    gemini = by_model.get("gemini-2.5-flash", {})
    sched_p2 = gemini.get("stacks", {}).get("sched_p2_gemini")
    sched_only = gemini.get("stacks", {}).get("best_schedule")
    sched_p2_comparison = None
    if sched_p2 and sched_only:
        sched_p2_comparison = {
            "baseline": sched_only,
            "variant": sched_p2,
            "ex_delta_pp": round(
                (sched_p2.get("ex_accuracy_pct") or 0) - (sched_only.get("ex_accuracy_pct") or 0),
                1,
            ),
            "token_delta_pct": pct_delta(sched_only.get("total_tokens"), sched_p2.get("total_tokens")),
            "redundancy_delta_pp": round(
                (sched_p2.get("avg_explore_redundancy_pct") or 0)
                - (sched_only.get("avg_explore_redundancy_pct") or 0),
                1,
            ),
        }

    return {
        "n_replicas": n_replicas,
        "sweep_id": sweep_id,
        "by_model": by_model,
        "recommendations": recommendations,
        "sched_p2_gemini_followup": sched_p2_comparison,
        "schedule_scenarios": SCHEDULE_SCENARIOS,
    }
