"""Plot P1 shared-cache vs P0 comparison figures."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import matplotlib.pyplot as plt

from src.coord.baseline_plots import MODEL_LABELS
from src.coord.early_stop_analysis import pct_delta


def _model_label(model_key: str) -> str:
    return MODEL_LABELS.get(model_key, model_key)


def plot_p1_comparison(
    comparisons_by_n: dict[int, list[tuple[dict[str, Any], dict[str, Any]]]],
    out_dir: Path,
    *,
    title_prefix: str = "P1 shared cache vs P0",
) -> list[Path]:
    out_dir.mkdir(parents=True, exist_ok=True)
    saved: list[Path] = []

    for n_replicas, comparisons in sorted(comparisons_by_n.items()):
        if not comparisons:
            continue
        models = [_model_label(p0["model_key"]) for p0, _ in comparisons]
        p0_red = [p0["avg_explore_redundancy_pct"] for p0, _ in comparisons]
        p1_red = [p1["avg_explore_redundancy_pct"] for _, p1 in comparisons]
        cache_hit = [p1.get("avg_cache_hit_rate_pct") or p1.get("batch_cache_hit_rate_pct", 0) for _, p1 in comparisons]

        fig, axes = plt.subplots(1, 2, figsize=(10, 4.5))
        x = range(len(models))
        width = 0.35

        ax = axes[0]
        ax.bar([i - width / 2 for i in x], p0_red, width, label="P0", color="#4C72B0")
        ax.bar([i + width / 2 for i in x], p1_red, width, label="P1", color="#55A868")
        ax.set_ylabel("Explore redundancy (%)")
        ax.set_title(f"Explore redundancy (N={n_replicas})")
        ax.set_xticks(list(x))
        ax.set_xticklabels(models, rotation=15, ha="right")
        ax.legend()
        ax.grid(True, axis="y", alpha=0.3, linestyle="--")

        ax = axes[1]
        ax.bar(x, cache_hit, color="#C44E52")
        ax.set_ylabel("Cache hit rate (%)")
        ax.set_title(f"P1 explore SQL cache hits (N={n_replicas})")
        ax.set_xticks(list(x))
        ax.set_xticklabels(models, rotation=15, ha="right")
        ax.set_ylim(0, 100)
        ax.grid(True, axis="y", alpha=0.3, linestyle="--")

        fig.suptitle(f"{title_prefix} at N={n_replicas}", fontsize=12)
        fig.tight_layout()
        out_path = out_dir / f"p1_comparison_r{n_replicas}.png"
        fig.savefig(out_path, dpi=150, bbox_inches="tight")
        plt.close(fig)
        saved.append(out_path)

    if len(comparisons_by_n) >= 2:
        overview = out_dir / "p1_cache_hit_scaling.png"
        _plot_cache_hit_scaling(comparisons_by_n, overview, title_prefix=title_prefix)
        saved.append(overview)

    return saved


def _plot_cache_hit_scaling(
    comparisons_by_n: dict[int, list[tuple[dict[str, Any], dict[str, Any]]]],
    out_path: Path,
    *,
    title_prefix: str,
) -> None:
    models = sorted({p0["model_key"] for pairs in comparisons_by_n.values() for p0, _ in pairs})
    replica_counts = sorted(comparisons_by_n)
    colors = plt.cm.tab10(range(len(models)))

    fig, ax = plt.subplots(figsize=(7, 4.5))
    for color, model in zip(colors, models, strict=False):
        ys: list[float] = []
        for n in replica_counts:
            pair = next(
                ((p0, p1) for p0, p1 in comparisons_by_n[n] if p0["model_key"] == model),
                None,
            )
            if pair is None:
                ys.append(float("nan"))
            else:
                _, p1 = pair
                ys.append(float(p1.get("avg_cache_hit_rate_pct") or 0))
        ax.plot(replica_counts, ys, marker="o", linewidth=2, markersize=8, label=_model_label(model), color=color)

    ax.set_xlabel("Parallel replicas")
    ax.set_ylabel("Mean cache hit rate (%)")
    ax.set_title(f"{title_prefix}: cache hit rate vs N")
    ax.set_xticks(replica_counts)
    ax.set_ylim(0, 100)
    ax.grid(True, alpha=0.3, linestyle="--")
    ax.legend(loc="best")
    fig.tight_layout()
    out_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out_path, dpi=150, bbox_inches="tight")
    plt.close(fig)
