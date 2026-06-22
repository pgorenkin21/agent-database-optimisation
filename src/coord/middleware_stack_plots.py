"""Plot middleware stack comparisons."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import matplotlib.pyplot as plt

from src.coord.baseline_plots import MODEL_LABELS

POLICY_ORDER = ["P0", "P1", "P2", "P1+P2", "early_stop", "full_stack", "full_stack_prune"]
POLICY_COLORS = {
    "P0": "#4C72B0",
    "P1": "#55A868",
    "P2": "#8172B2",
    "P1+P2": "#CCB974",
    "early_stop": "#C44E52",
    "full_stack": "#DD8452",
    "full_stack_prune": "#64B5CD",
}
POLICY_DISPLAY = {
    "full_stack_prune": "full_stack+prune",
}


def _model_label(model_key: str) -> str:
    return MODEL_LABELS.get(model_key, model_key)


def plot_middleware_stack(
    stack_by_model: dict[str, dict[str, dict[str, Any]]],
    out_dir: Path,
    *,
    n_replicas: int,
    title_prefix: str = "Middleware stack",
) -> list[Path]:
    out_dir.mkdir(parents=True, exist_ok=True)
    models = [_model_label(m) for m in stack_by_model]
    model_keys = list(stack_by_model.keys())
    policies = [p for p in POLICY_ORDER if any(p in stack_by_model[m] for m in model_keys)]
    saved: list[Path] = []

    fig, axes = plt.subplots(2, 2, figsize=(14, 8))
    axes = axes.flatten()
    metrics = [
        ("avg_token_overhead_ratio", "Token overhead (×)", "overhead"),
        ("avg_explore_redundancy_pct", "Explore redundancy (%)", "redundancy"),
        ("total_tokens", "Total tokens", "tokens"),
        ("avg_middleware_interaction_pct", "Middleware interaction (%)", "middleware"),
    ]

    x = range(len(models))
    width = 0.8 / max(len(policies), 1)

    for ax, (field, ylabel, slug) in zip(axes, metrics, strict=True):
        for pi, policy in enumerate(policies):
            offsets = [i + (pi - len(policies) / 2 + 0.5) * width for i in x]
            ys: list[float] = []
            for mk in model_keys:
                row = stack_by_model[mk].get(policy)
                if row is None:
                    ys.append(float("nan"))
                elif field == "total_tokens":
                    ys.append(float(row.get("total_tokens", 0)))
                elif field == "avg_middleware_interaction_pct":
                    ys.append(float(row.get(field) or 0))
                else:
                    ys.append(float(row.get(field) or 0))
            ax.bar(
                offsets,
                ys,
                width=width,
                label=POLICY_DISPLAY.get(policy, policy),
                color=POLICY_COLORS.get(policy, "#888888"),
            )
        ax.set_xticks(list(x))
        ax.set_xticklabels(models, rotation=15, ha="right")
        ax.set_ylabel(ylabel)
        ax.grid(True, axis="y", alpha=0.3, linestyle="--")

    axes[0].legend(loc="best", fontsize=8)
    fig.suptitle(f"{title_prefix} at N={n_replicas}", fontsize=12)
    fig.tight_layout()
    out_path = out_dir / f"middleware_stack_r{n_replicas}.png"
    fig.savefig(out_path, dpi=150, bbox_inches="tight")
    plt.close(fig)
    saved.append(out_path)
    return saved
