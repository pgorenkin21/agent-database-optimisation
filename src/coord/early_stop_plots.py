"""Plot early-stop vs P0 comparison figures."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import matplotlib.pyplot as plt

from src.coord.baseline_plots import MODEL_LABELS
from src.coord.early_stop_analysis import pct_delta


def _model_label(model_key: str) -> str:
    return MODEL_LABELS.get(model_key, model_key)


def plot_early_stop_comparison(
    comparisons_by_n: dict[int, list[tuple[dict[str, Any], dict[str, Any]]]],
    out_dir: Path,
    *,
    title_prefix: str = "Early stop vs P0",
) -> list[Path]:
    """Bar charts: token savings and overhead by model at each replica count."""
    out_dir.mkdir(parents=True, exist_ok=True)
    saved: list[Path] = []

    for n_replicas, comparisons in sorted(comparisons_by_n.items()):
        if not comparisons:
            continue
        models = [_model_label(p0["model_key"]) for p0, _ in comparisons]
        p0_tokens = [p0["total_tokens"] for p0, _ in comparisons]
        es_tokens = [es["total_tokens"] for _, es in comparisons]
        p0_overhead = [p0["avg_token_overhead_ratio"] for p0, _ in comparisons]
        es_overhead = [es["avg_token_overhead_ratio"] for _, es in comparisons]

        fig, axes = plt.subplots(1, 2, figsize=(10, 4.5))
        x = range(len(models))
        width = 0.35

        ax = axes[0]
        ax.bar([i - width / 2 for i in x], p0_tokens, width, label="P0", color="#4C72B0")
        ax.bar([i + width / 2 for i in x], es_tokens, width, label="Early stop", color="#55A868")
        ax.set_ylabel("Total tokens")
        ax.set_title(f"Token spend (N={n_replicas})")
        ax.set_xticks(list(x))
        ax.set_xticklabels(models, rotation=15, ha="right")
        ax.legend()
        ax.grid(True, axis="y", alpha=0.3, linestyle="--")

        ax = axes[1]
        ax.bar([i - width / 2 for i in x], p0_overhead, width, label="P0", color="#4C72B0")
        ax.bar([i + width / 2 for i in x], es_overhead, width, label="Early stop", color="#55A868")
        ax.set_ylabel("Token overhead (×)")
        ax.set_title(f"Overhead ratio (N={n_replicas})")
        ax.set_xticks(list(x))
        ax.set_xticklabels(models, rotation=15, ha="right")
        ax.legend()
        ax.grid(True, axis="y", alpha=0.3, linestyle="--")

        fig.suptitle(f"{title_prefix} at N={n_replicas}", fontsize=12)
        fig.tight_layout()
        out_path = out_dir / f"early_stop_comparison_r{n_replicas}.png"
        fig.savefig(out_path, dpi=150, bbox_inches="tight")
        plt.close(fig)
        saved.append(out_path)

    if len(comparisons_by_n) >= 2:
        overview_path = out_dir / "early_stop_token_savings.png"
        _plot_token_savings_overview(comparisons_by_n, overview_path, title_prefix=title_prefix)
        saved.append(overview_path)

    return saved


def _plot_token_savings_overview(
    comparisons_by_n: dict[int, list[tuple[dict[str, Any], dict[str, Any]]]],
    out_path: Path,
    *,
    title_prefix: str,
) -> None:
    models = sorted(
        {p0["model_key"] for pairs in comparisons_by_n.values() for p0, _ in pairs}
    )
    replica_counts = sorted(comparisons_by_n)
    colors = plt.cm.tab10(range(len(models)))

    fig, ax = plt.subplots(figsize=(7, 4.5))
    for color, model in zip(colors, models, strict=False):
        deltas: list[float | None] = []
        for n in replica_counts:
            pair = next(
                ((p0, es) for p0, es in comparisons_by_n[n] if p0["model_key"] == model),
                None,
            )
            if pair is None:
                deltas.append(None)
            else:
                p0, es = pair
                deltas.append(pct_delta(p0["total_tokens"], es["total_tokens"]))
        ys = [d if d is not None else float("nan") for d in deltas]
        ax.plot(
            replica_counts,
            ys,
            marker="o",
            linewidth=2,
            markersize=8,
            label=_model_label(model),
            color=color,
        )

    ax.axhline(0, color="gray", linewidth=0.8, linestyle="--")
    ax.set_xlabel("Parallel replicas")
    ax.set_ylabel("Token change vs P0 (%)")
    ax.set_title(f"{title_prefix}: token savings")
    ax.set_xticks(replica_counts)
    ax.grid(True, alpha=0.3, linestyle="--")
    ax.legend(loc="best")
    fig.tight_layout()
    out_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out_path, dpi=150, bbox_inches="tight")
    plt.close(fig)
