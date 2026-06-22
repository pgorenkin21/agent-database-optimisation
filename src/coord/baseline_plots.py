"""Plot baseline redundancy reports (P0) across models and replica counts."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import matplotlib.pyplot as plt
import pandas as pd

# Short display labels for thesis figures
MODEL_LABELS: dict[str, str] = {
    "gpt-4o-mini": "GPT-4o mini",
    "gemini-2.5-flash": "Gemini 2.5 Flash",
    "deepseek-v3.2": "DeepSeek V3.2",
}

METRIC_SPECS: tuple[tuple[str, str, str], ...] = (
    ("avg_explore_redundancy_pct", "Explore redundancy (%)", "explore_redundancy"),
    ("avg_subexpr_overlap_pct", "Sub-expression overlap (%)", "subexpr_overlap"),
    ("avg_token_overhead_ratio", "Token overhead (×)", "token_overhead"),
    ("avg_wall_clock_ms", "Avg wall-clock (s)", "wall_clock_s"),
)


def load_report_comparison(path: Path) -> list[dict[str, Any]]:
    """Load the ``comparison`` table from a baseline report JSON."""
    data = json.loads(path.read_text(encoding="utf-8"))
    rows = data.get("comparison", [])
    if not isinstance(rows, list) or not rows:
        raise ValueError(f"No comparison rows in {path}")
    return rows


def comparison_dataframe(report_paths: list[Path]) -> pd.DataFrame:
    """Merge comparison rows from one or more baseline report JSON files."""
    frames: list[pd.DataFrame] = []
    for path in report_paths:
        rows = load_report_comparison(path)
        df = pd.DataFrame(rows)
        df["report_path"] = str(path.resolve())
        frames.append(df)
    if not frames:
        raise ValueError("No report data loaded")
    out = pd.concat(frames, ignore_index=True)
    out["model_label"] = out["model_key"].map(lambda k: MODEL_LABELS.get(k, k))
    if "avg_wall_clock_ms" in out.columns:
        out["avg_wall_clock_s"] = out["avg_wall_clock_ms"] / 1000.0
    return out.sort_values(["model_key", "n_replicas"]).reset_index(drop=True)


def _plot_metric(
    df: pd.DataFrame,
    *,
    y_col: str,
    y_label: str,
    out_path: Path,
    title: str,
) -> None:
    fig, ax = plt.subplots(figsize=(7, 4.5))
    models = df["model_key"].unique()
    colors = plt.cm.tab10(range(len(models)))

    for color, model in zip(colors, sorted(models), strict=False):
        sub = df[df["model_key"] == model].sort_values("n_replicas")
        label = MODEL_LABELS.get(model, model)
        ax.plot(
            sub["n_replicas"],
            sub[y_col],
            marker="o",
            linewidth=2,
            markersize=8,
            label=label,
            color=color,
        )
        for _, row in sub.iterrows():
            n_tasks = int(row.get("task_count", 0))
            if n_tasks < 50:
                ax.annotate(
                    f"n={n_tasks}",
                    (row["n_replicas"], row[y_col]),
                    textcoords="offset points",
                    xytext=(0, 8),
                    fontsize=7,
                    ha="center",
                    color=color,
                )

    ax.set_xlabel("Parallel replicas")
    ax.set_ylabel(y_label)
    ax.set_title(title)
    ax.set_xticks(sorted(df["n_replicas"].unique()))
    ax.grid(True, alpha=0.3, linestyle="--")
    ax.legend(loc="best", framealpha=0.9)
    fig.tight_layout()
    out_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out_path, dpi=150, bbox_inches="tight")
    plt.close(fig)


def _plot_ex_accuracy(df: pd.DataFrame, out_path: Path, *, title: str) -> None:
    """Execution accuracy with optional dashed line excluding API failures."""
    fig, ax = plt.subplots(figsize=(7, 4.5))
    models = sorted(df["model_key"].unique())
    colors = plt.cm.tab10(range(len(models)))
    has_excl = "ex_accuracy_excluding_api_errors_pct" in df.columns

    for color, model in zip(colors, models, strict=False):
        sub = df[df["model_key"] == model].sort_values("n_replicas")
        label = MODEL_LABELS.get(model, model)
        ax.plot(
            sub["n_replicas"],
            sub["ex_accuracy_pct"],
            marker="o",
            linewidth=2,
            markersize=8,
            label=label,
            color=color,
        )
        if has_excl and sub["ex_accuracy_excluding_api_errors_pct"].notna().any():
            ax.plot(
                sub["n_replicas"],
                sub["ex_accuracy_excluding_api_errors_pct"],
                marker="o",
                linewidth=2,
                markersize=6,
                linestyle="--",
                alpha=0.85,
                label=f"{label} (excl. API fail)",
                color=color,
            )
        for _, row in sub.iterrows():
            api_fails = int(row.get("api_failure_count", 0))
            if api_fails > 0:
                ax.annotate(
                    f"{api_fails} API fail",
                    (row["n_replicas"], row["ex_accuracy_pct"]),
                    textcoords="offset points",
                    xytext=(0, -14),
                    fontsize=7,
                    ha="center",
                    color=color,
                )

    ax.set_xlabel("Parallel replicas")
    ax.set_ylabel("Execution accuracy (%)")
    ax.set_title(title)
    ax.set_xticks(sorted(df["n_replicas"].unique()))
    ax.grid(True, alpha=0.3, linestyle="--")
    ax.legend(loc="best", framealpha=0.9, fontsize=8)
    fig.tight_layout()
    out_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out_path, dpi=150, bbox_inches="tight")
    plt.close(fig)


def plot_baseline_comparison(
    report_paths: list[Path],
    out_dir: Path,
    *,
    title_prefix: str = "P0 baseline",
) -> tuple[pd.DataFrame, list[Path]]:
    """
    Plot key redundancy metrics vs replica count for each model.

    Returns the merged dataframe and paths to saved PNG figures.
    """
    df = comparison_dataframe(report_paths)
    saved: list[Path] = []

    for y_col, y_label, stem in METRIC_SPECS:
        col = "avg_wall_clock_s" if stem == "wall_clock_s" else y_col
        if col not in df.columns:
            continue
        out_path = out_dir / f"baseline_{stem}.png"
        _plot_metric(
            df,
            y_col=col,
            y_label=y_label,
            out_path=out_path,
            title=f"{title_prefix}: {y_label} vs replica count",
        )
        saved.append(out_path)

    ex_path = out_dir / "baseline_ex_accuracy.png"
    _plot_ex_accuracy(
        df,
        ex_path,
        title=f"{title_prefix}: execution accuracy vs replica count",
    )
    saved.append(ex_path)

    # Combined 2×2 overview
    overview_path = out_dir / "baseline_overview.png"
    _plot_overview(df, overview_path, title_prefix=title_prefix)
    saved.append(overview_path)

    return df, saved


def _plot_overview(df: pd.DataFrame, out_path: Path, *, title_prefix: str) -> None:
    fig, axes = plt.subplots(2, 2, figsize=(10, 8), sharex=True)
    models = sorted(df["model_key"].unique())
    colors = plt.cm.tab10(range(len(models)))

    metric_panels = [
        (axes[0, 0], "avg_explore_redundancy_pct", "Explore redundancy (%)"),
        (axes[0, 1], "avg_token_overhead_ratio", "Token overhead (×)"),
        (axes[1, 0], "avg_subexpr_overlap_pct", "Sub-expression overlap (%)"),
    ]
    for ax, y_col, y_label in metric_panels:
        for color, model in zip(colors, models, strict=False):
            sub = df[df["model_key"] == model].sort_values("n_replicas")
            ax.plot(
                sub["n_replicas"],
                sub[y_col],
                marker="o",
                linewidth=2,
                markersize=6,
                label=MODEL_LABELS.get(model, model),
                color=color,
            )
        ax.set_ylabel(y_label)
        ax.set_xticks(sorted(df["n_replicas"].unique()))
        ax.grid(True, alpha=0.3, linestyle="--")

    ex_ax = axes[1, 1]
    for color, model in zip(colors, models, strict=False):
        sub = df[df["model_key"] == model].sort_values("n_replicas")
        ex_ax.plot(
            sub["n_replicas"],
            sub["ex_accuracy_pct"],
            marker="o",
            linewidth=2,
            markersize=6,
            label=MODEL_LABELS.get(model, model),
            color=color,
        )
        if "ex_accuracy_excluding_api_errors_pct" in sub.columns:
            ex_ax.plot(
                sub["n_replicas"],
                sub["ex_accuracy_excluding_api_errors_pct"],
                marker="o",
                linewidth=1.5,
                markersize=4,
                linestyle="--",
                alpha=0.85,
                color=color,
            )
    ex_ax.set_ylabel("Execution accuracy (%)")
    ex_ax.set_xticks(sorted(df["n_replicas"].unique()))
    ex_ax.grid(True, alpha=0.3, linestyle="--")

    for ax in axes[1, :]:
        ax.set_xlabel("Parallel replicas")
    fig.suptitle(f"{title_prefix}: redundancy scaling across models", fontsize=12)
    handles, labels = axes[0, 0].get_legend_handles_labels()
    fig.legend(handles, labels, loc="lower center", ncol=len(models), bbox_to_anchor=(0.5, 0.02))
    fig.tight_layout(rect=[0, 0.06, 1, 0.96])
    out_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out_path, dpi=150, bbox_inches="tight")
    plt.close(fig)
