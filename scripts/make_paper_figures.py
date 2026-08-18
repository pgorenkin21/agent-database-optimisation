#!/usr/bin/env python3
"""Regenerate paper-ready figures for thesis/draft_paper_ieee.tex.

Restyles two chapter plots for print at IEEE column width (~3.5 in): no
in-image titles (the LaTeX captions carry them), a colourblind-safe palette,
and fonts sized for the final render size. Writes to thesis/figures/ and
leaves the chapter plots in runs/reports/plots/ untouched.
"""

from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

from src.coord.baseline_plots import MODEL_LABELS, comparison_dataframe  # noqa: E402

# Registry key predates the provider rename; the paper reports the served model.
MODEL_LABELS = {**MODEL_LABELS, "deepseek-v3.2": "DeepSeek v4-flash"}
from src.coord.prompt_cache_analysis import load_default_comparisons  # noqa: E402
from src.coord.prompt_cache_plots import (  # noqa: E402
    aggregate_by_turn,
    collect_llm_turns,
    trace_paths_from_batch,
)

DEFAULT_OUT_DIR = REPO_ROOT / "thesis" / "figures"
BASELINE_REPORTS = [
    REPO_ROOT / "runs" / "reports" / "baseline_gpt4o_baseline_full.json",
    REPO_ROOT / "runs" / "reports" / "baseline_gemini_baseline_full.json",
    REPO_ROOT / "runs" / "reports" / "baseline_deepseek_v4f_baseline_full.json",
]

# Colour follows the entity: one fixed hue per model across all paper figures.
# Palette validated (CVD-safe) against the light surface; the below-3:1 slots
# rely on the legend plus the paper's tables as the table view.
MODEL_COLORS = {
    "gpt-4o-mini": "#2a78d6",
    "gemini-2.5-flash": "#199e70",
    "deepseek-v3.2": "#c98500",
}
INK = "#0b0b0b"
INK_MUTED = "#52514e"
CACHED_FILL = "#5598e7"
BILLED_FILL = "#eb6834"

PAPER_RC = {
    "figure.figsize": (3.45, 2.35),
    "savefig.dpi": 300,
    "font.size": 8,
    "axes.labelsize": 8,
    "axes.titlesize": 8,
    "xtick.labelsize": 7.5,
    "ytick.labelsize": 7.5,
    "legend.fontsize": 7,
    "axes.spines.top": False,
    "axes.spines.right": False,
    "axes.grid": True,
    "grid.color": "#e2e1dd",
    "grid.linewidth": 0.5,
    "axes.axisbelow": True,
    "axes.edgecolor": INK_MUTED,
    "axes.linewidth": 0.6,
    "axes.labelcolor": INK,
    "xtick.color": INK_MUTED,
    "ytick.color": INK_MUTED,
    "xtick.major.width": 0.6,
    "ytick.major.width": 0.6,
    "legend.frameon": False,
}


def make_explore_redundancy_figure(out_path: Path) -> Path:
    """Fig. 2 — explore redundancy vs replica count, one line per model."""
    df = comparison_dataframe([p for p in BASELINE_REPORTS if p.exists()])
    fig, ax = plt.subplots()
    for model, color in MODEL_COLORS.items():
        sub = df[df["model_key"] == model].sort_values("n_replicas")
        if sub.empty:
            continue
        ax.plot(
            sub["n_replicas"],
            sub["avg_explore_redundancy_pct"],
            color=color,
            linewidth=1.6,
            marker="o",
            markersize=4.5,
            markeredgecolor="white",
            markeredgewidth=0.6,
            label=MODEL_LABELS.get(model, model),
        )
        for _, row in sub.iterrows():
            n_tasks = int(row.get("task_count", 0))
            if 0 < n_tasks < 50:
                ax.annotate(
                    f"n={n_tasks}",
                    (row["n_replicas"], row["avg_explore_redundancy_pct"]),
                    textcoords="offset points",
                    xytext=(0, 5),
                    fontsize=6,
                    ha="center",
                    color=INK_MUTED,
                )
    ax.set_xlabel("Parallel replicas")
    ax.set_ylabel("Explore redundancy (%)")
    ax.set_xticks(sorted(df["n_replicas"].unique()))
    ax.legend(loc="lower right", handlelength=1.6)
    fig.tight_layout(pad=0.4)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out_path, bbox_inches="tight")
    plt.close(fig)
    return out_path


def make_prompt_cache_figure(out_path: Path) -> Path:
    """Fig. 3 — cached vs billed input tokens per turn (GPT cached batch)."""
    comparisons = load_default_comparisons(REPO_ROOT / "runs" / "batches")
    gpt = next((c for c in comparisons if c.model_key == "gpt-4o-mini"), None)
    if gpt is None:
        raise ValueError("No gpt-4o-mini prompt-cache comparison batch found")
    agg = aggregate_by_turn(collect_llm_turns(trace_paths_from_batch(gpt.cached_path)))
    if agg.empty:
        raise ValueError(f"No llm_turn events in {gpt.cached_path}")

    fig, ax = plt.subplots()
    ax.stackplot(
        agg["turn_idx"],
        agg["mean_cached"],
        agg["mean_uncached"],
        labels=["Cached input (discounted)", "Billed input (uncached)"],
        colors=[CACHED_FILL, BILLED_FILL],
        linewidth=0,
    )
    # Surface gap between the stacked fills
    ax.plot(agg["turn_idx"], agg["mean_cached"], color="white", linewidth=1.0)
    ax.plot(
        agg["turn_idx"],
        agg["mean_prompt"],
        color=INK,
        linewidth=1.2,
        label="Total input tokens",
    )
    ax.set_xlabel("Turn index")
    ax.set_ylabel("Mean input tokens / replica-turn")
    ax.set_xlim(agg["turn_idx"].min(), agg["turn_idx"].max())
    ax.set_ylim(0, float(agg["mean_prompt"].max()) * 1.28)
    ax.legend(loc="upper left", handlelength=1.6)
    fig.tight_layout(pad=0.4)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out_path, bbox_inches="tight")
    plt.close(fig)
    return out_path


def make_cache_hit_rate_figure(out_path: Path) -> Path:
    """Fig. 4 — cached share of input tokens per turn (GPT cached batch)."""
    comparisons = load_default_comparisons(REPO_ROOT / "runs" / "batches")
    gpt = next((c for c in comparisons if c.model_key == "gpt-4o-mini"), None)
    if gpt is None:
        raise ValueError("No gpt-4o-mini prompt-cache comparison batch found")
    agg = aggregate_by_turn(collect_llm_turns(trace_paths_from_batch(gpt.cached_path)))
    if agg.empty:
        raise ValueError(f"No llm_turn events in {gpt.cached_path}")

    fig, ax = plt.subplots(figsize=(3.45, 1.9))
    ax.plot(
        agg["turn_idx"],
        agg["cached_pct"],
        color=MODEL_COLORS["gpt-4o-mini"],
        linewidth=1.6,
        marker="o",
        markersize=4,
        markeredgecolor="white",
        markeredgewidth=0.6,
    )
    ax.set_xlabel("Turn index")
    ax.set_ylabel("Cached share of input (%)")
    ax.set_ylim(0, 100)
    fig.tight_layout(pad=0.4)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out_path, bbox_inches="tight")
    plt.close(fig)
    return out_path


def main() -> int:
    plt.rcParams.update(PAPER_RC)
    saved = [
        make_explore_redundancy_figure(DEFAULT_OUT_DIR / "baseline_explore_redundancy.png"),
        make_prompt_cache_figure(DEFAULT_OUT_DIR / "prompt_cache_tokens_by_turn.png"),
        make_cache_hit_rate_figure(DEFAULT_OUT_DIR / "prompt_cache_hit_rate_by_turn.png"),
    ]
    for path in saved:
        print(f"Wrote {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
