"""Plot schema-pruning offline and agent-run comparisons."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import matplotlib.pyplot as plt

from src.coord.baseline_plots import MODEL_LABELS
from src.coord.schema_pruning_analysis import comparison_deltas, offline_summary_by_database


def _model_label(model_key: str) -> str:
    return MODEL_LABELS.get(model_key, model_key)


def plot_offline_reduction_by_db(
    offline_reports: dict[str, dict[str, Any]],
    out_dir: Path,
    *,
    mode: str = "hybrid",
) -> Path | None:
    report = offline_reports.get(mode)
    if not report:
        return None
    by_db = offline_summary_by_database(report)
    if not by_db:
        return None

    out_dir.mkdir(parents=True, exist_ok=True)
    dbs = list(by_db)
    reductions = [by_db[db]["avg_reduction_pct"] for db in dbs]
    counts = [int(by_db[db]["task_count"]) for db in dbs]

    fig, ax = plt.subplots(figsize=(7, 4))
    bars = ax.bar(dbs, reductions, color=["#4C72B0", "#55A868"][: len(dbs)])
    ax.set_ylabel("Avg schema size reduction (%)")
    ax.set_title(f"Offline schema pruning by database ({mode} mode, n=50)")
    ax.set_ylim(0, max(reductions) * 1.15 if reductions else 100)
    for bar, n in zip(bars, counts):
        ax.text(
            bar.get_x() + bar.get_width() / 2,
            bar.get_height() + 1,
            f"n={n}",
            ha="center",
            va="bottom",
            fontsize=9,
        )
    ax.grid(True, axis="y", alpha=0.3, linestyle="--")
    fig.tight_layout()
    out_path = out_dir / "schema_prune_offline_by_db.png"
    fig.savefig(out_path, dpi=150, bbox_inches="tight")
    plt.close(fig)
    return out_path


def plot_offline_mode_comparison(
    offline_reports: dict[str, dict[str, Any]],
    out_dir: Path,
) -> Path | None:
    if not offline_reports:
        return None
    out_dir.mkdir(parents=True, exist_ok=True)
    modes = list(offline_reports)
    recalls = [offline_reports[m]["full_gold_recall_pct"] for m in modes]
    reductions = [offline_reports[m]["avg_reduction_pct"] for m in modes]
    tables = [offline_reports[m]["avg_selected_tables"] for m in modes]

    fig, axes = plt.subplots(1, 3, figsize=(10, 3.8))
    x = range(len(modes))
    for ax, vals, ylab, title in zip(
        axes,
        [recalls, reductions, tables],
        ["Gold-table recall (%)", "Avg reduction (%)", "Avg tables kept"],
        ["Recall", "Schema reduction", "Table count"],
    ):
        ax.bar(x, vals, color="#4C72B0")
        ax.set_xticks(list(x))
        ax.set_xticklabels(modes)
        ax.set_ylabel(ylab)
        ax.set_title(title)
        ax.grid(True, axis="y", alpha=0.3, linestyle="--")
    fig.suptitle("Schema pruning modes (offline, 50-task smoke subset)", fontsize=11)
    fig.tight_layout()
    out_path = out_dir / "schema_prune_mode_comparison.png"
    fig.savefig(out_path, dpi=150, bbox_inches="tight")
    plt.close(fig)
    return out_path


def plot_agent_token_impact(
    p0_vs_prune: list[tuple[dict[str, Any], dict[str, Any]]],
    out_dir: Path,
    *,
    n_replicas: int,
    title_suffix: str = "full stack + schema prune vs P0",
) -> Path | None:
    if not p0_vs_prune:
        return None
    out_dir.mkdir(parents=True, exist_ok=True)
    models = [_model_label(p0["model_key"]) for p0, _ in p0_vs_prune]
    p0_tokens = [p0["total_tokens"] / 1e6 for p0, _ in p0_vs_prune]
    prune_tokens = [sp["total_tokens"] / 1e6 for _, sp in p0_vs_prune]
    ex_deltas = [comparison_deltas(p0, sp)["ex_pp"] or 0 for p0, sp in p0_vs_prune]

    fig, axes = plt.subplots(1, 2, figsize=(10, 4))
    x = range(len(models))
    width = 0.35
    ax = axes[0]
    ax.bar([i - width / 2 for i in x], p0_tokens, width, label="P0", color="#4C72B0")
    ax.bar([i + width / 2 for i in x], prune_tokens, width, label="Pruned", color="#55A868")
    ax.set_ylabel("Total tokens (millions)")
    ax.set_title(f"Token spend (N={n_replicas})")
    ax.set_xticks(list(x))
    ax.set_xticklabels(models, rotation=15, ha="right")
    ax.legend()
    ax.grid(True, axis="y", alpha=0.3, linestyle="--")

    ax = axes[1]
    colors = ["#55A868" if d >= 0 else "#C44E52" for d in ex_deltas]
    ax.bar(x, ex_deltas, color=colors)
    ax.axhline(0, color="black", linewidth=0.8)
    ax.set_ylabel("EX change (pp)")
    ax.set_title(f"Execution accuracy delta vs P0 (N={n_replicas})")
    ax.set_xticks(list(x))
    ax.set_xticklabels(models, rotation=15, ha="right")
    ax.grid(True, axis="y", alpha=0.3, linestyle="--")

    fig.suptitle(title_suffix, fontsize=11)
    fig.tight_layout()
    out_path = out_dir / f"schema_prune_agent_r{n_replicas}.png"
    fig.savefig(out_path, dpi=150, bbox_inches="tight")
    plt.close(fig)
    return out_path


def plot_isolated_all_models(
    isolated_by_model: dict[str, tuple[dict[str, Any], dict[str, Any]]],
    out_dir: Path,
    *,
    n_replicas: int = 10,
) -> Path | None:
    if not isolated_by_model:
        return None
    out_dir.mkdir(parents=True, exist_ok=True)
    models = [_model_label(m) for m in sorted(isolated_by_model)]
    p0_tokens = [isolated_by_model[m][0]["total_tokens"] / 1e6 for m in sorted(isolated_by_model)]
    sp_tokens = [isolated_by_model[m][1]["total_tokens"] / 1e6 for m in sorted(isolated_by_model)]
    ex_deltas = [
        comparison_deltas(isolated_by_model[m][0], isolated_by_model[m][1])["ex_pp"] or 0
        for m in sorted(isolated_by_model)
    ]

    fig, axes = plt.subplots(1, 2, figsize=(10, 4))
    x = range(len(models))
    width = 0.35
    ax = axes[0]
    ax.bar([i - width / 2 for i in x], p0_tokens, width, label="P0", color="#4C72B0")
    ax.bar([i + width / 2 for i in x], sp_tokens, width, label="Hybrid prune", color="#55A868")
    ax.set_ylabel("Total tokens (millions)")
    ax.set_title(f"Isolated schema prune (N={n_replicas})")
    ax.set_xticks(list(x))
    ax.set_xticklabels(models, rotation=15, ha="right")
    ax.legend()
    ax.grid(True, axis="y", alpha=0.3, linestyle="--")

    ax = axes[1]
    colors = ["#55A868" if d >= 0 else "#C44E52" for d in ex_deltas]
    ax.bar(x, ex_deltas, color=colors)
    ax.axhline(0, color="black", linewidth=0.8)
    ax.set_ylabel("EX change (pp)")
    ax.set_title("EX delta vs P0")
    ax.set_xticks(list(x))
    ax.set_xticklabels(models, rotation=15, ha="right")
    ax.grid(True, axis="y", alpha=0.3, linestyle="--")

    fig.tight_layout()
    out_path = out_dir / f"schema_prune_isolated_all_models_r{n_replicas}.png"
    fig.savefig(out_path, dpi=150, bbox_inches="tight")
    plt.close(fig)
    return out_path


def plot_isolated_prune_evolution(
    isolated: list[tuple[str, dict[str, Any], dict[str, Any]]],
    out_dir: Path,
) -> Path | None:
    if not isolated:
        return None
    out_dir.mkdir(parents=True, exist_ok=True)
    p0 = isolated[0][1]
    labels = ["P0"] + [f"prune {v}" for v, _, _ in isolated]
    tokens = [p0["total_tokens"] / 1e6]
    ex_vals = [p0["ex_accuracy_pct"] or 0]
    for _, _, sp in isolated:
        tokens.append(sp["total_tokens"] / 1e6)
        ex_vals.append(sp["ex_accuracy_pct"] or 0)

    fig, axes = plt.subplots(1, 2, figsize=(8, 3.8))
    x = range(len(labels))
    axes[0].bar(x, tokens, color=["#4C72B0", "#C44E52", "#55A868"][: len(labels)])
    axes[0].set_ylabel("Total tokens (millions)")
    axes[0].set_title(f"Isolated schema prune ({_model_label(p0['model_key'])}, N=10)")
    axes[0].set_xticks(list(x))
    axes[0].set_xticklabels(labels)
    axes[0].grid(True, axis="y", alpha=0.3, linestyle="--")

    axes[1].bar(x, ex_vals, color=["#4C72B0", "#C44E52", "#55A868"][: len(labels)])
    axes[1].set_ylabel("EX (%)")
    axes[1].set_ylim(0, 100)
    axes[1].set_title("Execution accuracy")
    axes[1].set_xticks(list(x))
    axes[1].set_xticklabels(labels)
    axes[1].grid(True, axis="y", alpha=0.3, linestyle="--")

    fig.tight_layout()
    out_path = out_dir / "schema_prune_v1_v2_gemini.png"
    fig.savefig(out_path, dpi=150, bbox_inches="tight")
    plt.close(fig)
    return out_path


def plot_schema_pruning_figures(
    *,
    offline_reports: dict[str, dict[str, Any]],
    p0_vs_full_stack_prune: dict[int, list[tuple[dict[str, Any], dict[str, Any]]]],
    isolated_by_n: dict[int, dict[str, tuple[dict[str, Any], dict[str, Any]]]],
    legacy_isolated: list[tuple[str, dict[str, Any], dict[str, Any]]] | None = None,
    out_dir: Path,
) -> list[Path]:
    saved: list[Path] = []
    for fn, kwargs in (
        (plot_offline_reduction_by_db, {"mode": "hybrid"}),
        (plot_offline_mode_comparison, {}),
    ):
        path = fn(offline_reports, out_dir, **kwargs)
        if path:
            saved.append(path)
    for n, isolated_by_model in sorted(isolated_by_n.items()):
        path = plot_isolated_all_models(isolated_by_model, out_dir, n_replicas=n)
        if path:
            saved.append(path)
    if legacy_isolated:
        path = plot_isolated_prune_evolution(legacy_isolated, out_dir)
        if path:
            saved.append(path)
    for n, pairs in sorted(p0_vs_full_stack_prune.items()):
        path = plot_agent_token_impact(
            pairs,
            out_dir,
            n_replicas=n,
            title_suffix=f"Full stack + hybrid schema prune vs P0 (N={n})",
        )
        if path:
            saved.append(path)
    return saved
