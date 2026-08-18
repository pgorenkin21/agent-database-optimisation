#!/usr/bin/env python3
"""Regenerate the v8 figures at IEEE column width (~3.45 in), or for slides.

All from clean `v8_*` batches, so the set stays single-era. Only fig4 is in the
paper; the rest exist because the 8-page limit cut them, and a 10-minute video
has no page limit.

  fig4_two_ledger.png   raw-token delta vs billed delta, one point per measured
                        cell. The paper's central claim: the two ledgers move
                        independently.  [Fig. 3 in the paper]
  fig5_additivity.png   composed saving vs the multiplicative prediction from
                        the isolated arms. 11 of 15 beat their parts.
  fig2_cached_by_turn.png
                        cached share of input per turn, three models, under the
                        cache-stable loop. Evidence the prefix invariant holds.
  fig6_scaling.png      the problem itself: cost tracks N, accuracy does not.
  fig7_redundancy.png   duplicated exploratory SQL against replica count.
                        Supersedes baseline_explore_redundancy.png, which was
                        drawn from a different task set and disagrees with §3.3.
  fig8_recall_split.png pruning's saving where gold recall holds against its
                        cost where it does not, with paired bootstrap intervals.
  fig9_billed_by_model.png
                        every prompt-cache cell grouped by model, labelled with
                        the provider's cached rate. The staircase between groups
                        is the price schedule, not the mechanism.

Numbers are parsed from runs/reports/v8_numbers.txt or recomputed from the same
batches the analyser uses, never hardcoded, so the figures track the evidence.
Run `scripts/analyze_v8_results.py` first (strict — no --allow-legacy) if any
wave has landed since these were last generated.

    uv run python scripts/make_v8_figures.py             # thesis/figures/
    uv run python scripts/make_v8_figures.py --slides    # thesis/figures/slides/

Colour follows the entity: one fixed hue per model, shared with
make_paper_figures.py. Method is carried by marker shape, so identity never
rests on colour alone. Palette validated CVD-safe on all pairs (worst OKLab
dE 8.4 protan/deutan, 19.8 unsimulated); the amber slot sits at 2.99:1 against
the light surface, so every figure carries a legend and the paper's tables
serve as the table view.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

NUMBERS = REPO_ROOT / "runs" / "reports" / "v8_numbers.txt"
BATCH_DIR = REPO_ROOT / "runs" / "batches"
OUT_DIR = REPO_ROOT / "thesis" / "figures"

MODEL_COLORS = {
    "GPT": "#2a78d6",
    "Gemini": "#199e70",
    "DeepSeek": "#c98500",
}
MODEL_LABELS = {
    "GPT": "GPT-4o mini",
    "Gemini": "Gemini 2.5 Flash",
    "DeepSeek": "DeepSeek v4-flash",
}
MODEL_BATCH_KEY = {
    "GPT": "gpt-4o-mini",
    "Gemini": "gemini-2.5-flash",
    "DeepSeek": "deepseek-v3.2",
}
# Marker carries the method so identity survives greyscale and CVD.
METHOD_MARKERS = {
    "pruning": "o",
    "P3 facts": "^",
    "prompt cache": "s",
    "composed": "D",
}
METHOD_LABELS = {
    "pruning": "Schema pruning",
    "P3 facts": "Fact store",
    "prompt cache": "Prompt cache",
    "composed": "Composed",
}

INK = "#0b0b0b"
INK_MUTED = "#52514e"
GRID = "#e2e1dd"

PAPER_RC = {
    "figure.figsize": (3.45, 2.35),
    "savefig.dpi": 300,
    "font.size": 8,
    "axes.labelsize": 8,
    "axes.titlesize": 8,
    "xtick.labelsize": 7.5,
    "ytick.labelsize": 7.5,
    "legend.fontsize": 6.5,
    "axes.spines.top": False,
    "axes.spines.right": False,
    "axes.grid": True,
    "grid.color": GRID,
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

# A figure sized for a 3.45in journal column is unreadable projected in a
# 10-minute video, and scaling the PNG up scales the type with it. --slides
# re-renders at presentation size so the type is set large rather than blown up.
SLIDE_RC = {**PAPER_RC, "font.size": 15, "axes.labelsize": 15,
            "axes.titlesize": 15, "xtick.labelsize": 14, "ytick.labelsize": 14,
            "legend.fontsize": 12.5, "grid.linewidth": 0.9,
            "axes.linewidth": 1.0}
SLIDE_SCALE = 2.6
_scale = 1.0


def fs(w: float, h: float) -> tuple[float, float]:
    """Figure size in inches, scaled for the current output mode."""
    return (w * _scale, h * _scale)


def save(fig, out_path: Path) -> Path:
    """Write a figure, thickening its marks first when rendering for slides.

    Every mark in this file is sized in points for a 3.45in column. Growing the
    canvas 2.6x without touching them leaves lines and markers proportionally
    thinner than the paper version, which is the opposite of what a projected
    figure needs. Scaling them here keeps the per-figure code free of mode
    checks and applies the same correction to every chart.
    """
    if _scale != 1.0:
        factor = 1.0 + (_scale - 1.0) * 0.62

        def grow(line) -> None:
            line.set_linewidth(line.get_linewidth() * factor)
            line.set_markersize(line.get_markersize() * factor)
            line.set_markeredgewidth(line.get_markeredgewidth() * factor)

        for ax in fig.axes:
            for line in ax.get_lines():
                grow(line)
            # Legend handles are separate artists, so scaling the plotted lines
            # alone leaves a legend of large text beside pinhead swatches.
            legend = ax.get_legend()
            for handle in getattr(legend, "legend_handles", []) if legend else []:
                if hasattr(handle, "set_markersize"):
                    grow(handle)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out_path, bbox_inches="tight")
    plt.close(fig)
    return out_path


# "  N=3  GPT      n=50   EX 58.0v 56.0 +2.0pp [...]  tok -25.8% [...]  billed -24.3% [...]"
ROW_RE = re.compile(
    r"^\s*N=(?P<n>\d+)\s+(?P<model>GPT|Gemini|DeepSeek)\s+n=(?P<obs>\d+)\s+"
    r"EX\s+[\d.]+v\s*[\d.]+\s+(?P<ex>[-+][\d.]+)pp\s+\[[^\]]*\](?P<exdag>.?)\s+"
    r"tok\s+(?P<tok>[-+][\d.]+)%\s+\[[^\]]*\](?P<tokdag>.?)\s+"
    r"billed\s+(?P<billed>[-+][\d.]+)%\s+\[[^\]]*\](?P<billeddag>.?)"
    # Only the fact-store rows carry an injection count, so this stays optional.
    r"(?:\s+inj/task=(?P<inj>[\d.]+))?"
)
DAGGER = "†"


def pct(v: float) -> str:
    """Signed percent using the same U+2212 minus matplotlib puts on the ticks."""
    return f"{v:+.1f}%".replace("-", "−")


def parse_numbers(path: Path) -> list[dict]:
    """Parse v8_numbers.txt into one record per measured cell."""
    rows: list[dict] = []
    scale, method = None, None
    for line in path.read_text().splitlines():
        if line.startswith("##########"):
            scale = "50" if "50-task" in line else "500"
            continue
        if line.startswith("---") and line.rstrip().endswith("---"):
            method = line.strip().strip("- ").strip()
            continue
        m = ROW_RE.match(line)
        if not m or scale is None or method is None:
            continue
        rows.append(
            {
                "scale": scale,
                "method": method,
                "n": int(m["n"]),
                "model": m["model"],
                "obs": int(m["obs"]),
                "ex": float(m["ex"]),
                "ex_sig": m["exdag"] != DAGGER,
                "tok": float(m["tok"]),
                "tok_sig": m["tokdag"] != DAGGER,
                "billed": float(m["billed"]),
                "billed_sig": m["billeddag"] != DAGGER,
                "inj": float(m["inj"]) if m["inj"] else None,
            }
        )
    return rows


def make_two_ledger_figure(rows: list[dict], out_path: Path) -> Path:
    """Raw-token delta vs billed delta, one point per measured cell.

    Both scales are plotted -- filled markers for the 50-task subset, open for
    the 500-task split, matching the additivity figure's convention. Restricting
    this to 50 tasks showed only 9 of the 15 prompt-cache configurations §6.3
    actually claims, so the figure under-represented its own section; the
    full-scale cells also carry the deepest billed savings (-86% on DeepSeek).
    """
    cells = [r for r in rows if r["scale"] == "50"]
    cells_full = [r for r in rows if r["scale"] == "500"]
    if not cells:
        raise ValueError("no 50-task rows parsed from v8_numbers.txt")

    fig, ax = plt.subplots(figsize=fs(3.45, 2.75))

    # Axes are scaled to their own data rather than forced square: the reference
    # line is still the y=x locus, and a square box would spend ~40% of a
    # column-width figure on an empty quadrant.
    allc = cells + cells_full
    x_lo = min(r["tok"] for r in allc) - 8
    # Extra right-hand padding is deliberate: it opens an empty wedge for the
    # method legend. At +10 the legend sat close enough to the DeepSeek
    # prompt-cache markers on the -82% floor to graze them, and masking a data
    # point behind a legend frame is not an acceptable fix.
    x_hi = max(r["tok"] for r in allc) + 17
    y_lo = min(r["billed"] for r in allc) - 9
    y_hi = max(r["billed"] for r in allc) + 10
    d_lo, d_hi = min(x_lo, y_lo), max(x_hi, y_hi)

    # y = x: both ledgers moving together. Distance below it is repricing.
    ax.plot([d_lo, d_hi], [d_lo, d_hi], color=INK_MUTED,
            linewidth=0.7, linestyle=(0, (4, 3)), zorder=1)
    ax.axhline(0, color=GRID, linewidth=0.8, zorder=0)
    ax.axvline(0, color=GRID, linewidth=0.8, zorder=0)
    # Sits above-left of the reference line, where the upper triangle is empty;
    # anchoring it on the right would put the dashes through the text.
    label_at = min(x_hi, y_hi) - 7
    ax.annotate("raw = billed", (label_at, label_at), textcoords="offset points",
                xytext=(-4, 4), fontsize=6, color=INK_MUTED, ha="right",
                va="bottom", style="italic")

    for r in cells:                          # filled marker = 50-task subset
        ax.plot(
            r["tok"], r["billed"],
            marker=METHOD_MARKERS[r["method"]],
            color=MODEL_COLORS[r["model"]],
            markersize=4.6,
            markeredgecolor="white",
            markeredgewidth=0.55,   # 2px-equivalent surface ring on overlap
            linestyle="none",
            zorder=3,
        )
    for r in cells_full:                     # open marker = full 500-task split
        ax.plot(
            r["tok"], r["billed"],
            marker=METHOD_MARKERS[r["method"]],
            markerfacecolor="white",
            markeredgecolor=MODEL_COLORS[r["model"]],
            markeredgewidth=1.1,
            markersize=4.9,
            linestyle="none",
            zorder=4,
        )

    # Direct-label only the punchline cell: raw up, billed down, both significant.
    punch = next((r for r in cells
                  if r["method"] == "prompt cache" and r["tok_sig"] and r["tok"] > 0), None)
    if punch:
        ax.annotate(
            f"{MODEL_LABELS[punch['model']]}, N={punch['n']}:\n"
            f"raw +{punch['tok']:.1f}%, billed {pct(punch['billed'])}",
            (punch["tok"], punch["billed"]),
            textcoords="offset points", xytext=(4, -34), fontsize=6,
            ha="right", va="top", color=INK, linespacing=1.3,
            arrowprops=dict(arrowstyle="-", color=INK_MUTED, linewidth=0.6,
                            shrinkA=2, shrinkB=3),
        )

    ax.set_xlabel("Raw token change vs baseline (%)")
    ax.set_ylabel("Billed token change vs baseline (%)")
    ax.set_xlim(x_lo, x_hi)
    ax.set_ylim(y_lo, y_hi)

    model_handles = [
        plt.Line2D([], [], marker="o", linestyle="none", color=c,
                   markersize=4.6, markeredgecolor="white", markeredgewidth=0.55,
                   label=MODEL_LABELS[m])
        for m, c in MODEL_COLORS.items()
    ]
    method_handles = [
        plt.Line2D([], [], marker=mk, linestyle="none", color=INK_MUTED,
                   markersize=4.6, markeredgecolor="white", markeredgewidth=0.55,
                   label=METHOD_LABELS[k])
        for k, mk in METHOD_MARKERS.items()
    ]
    model_handles.append(
        plt.Line2D([], [], marker="o", linestyle="none", markerfacecolor="white",
                   markeredgecolor=INK_MUTED, markeredgewidth=1.1, markersize=4.9,
                   label="500 tasks"))
    # Legend placement, checked against the rendered point cloud rather than
    # assumed: upper-left is free above the diagonal, and the lower-RIGHT wedge
    # is empty because no cell combines a large raw increase with a large billed
    # saving. Lower-left is NOT free -- once the 500-task cells were added, the
    # DeepSeek composed markers sit on the -85% floor and the method legend
    # printed straight through them.
    first = ax.legend(handles=model_handles, loc="upper left",
                      handlelength=1.0, labelspacing=0.25, borderpad=0.2)
    ax.add_artist(first)
    ax.legend(handles=method_handles, loc="lower right",
              handlelength=1.0, labelspacing=0.25, borderpad=0.2)

    fig.tight_layout(pad=0.4)
    return save(fig, out_path)


def additivity_table(rows: list[dict], scale: str = "50") -> list[dict]:
    """Multiplicative prediction from the isolated arms vs the composed measurement."""
    by_key = {(r["method"], r["n"], r["model"]): r
              for r in rows if r["scale"] == scale}
    out = []
    for (method, n, model), comp in sorted(by_key.items()):
        if method != "composed":
            continue
        parts = [by_key.get((m, n, model)) for m in ("pruning", "P3 facts", "prompt cache")]
        if any(p is None for p in parts):
            continue
        pred = 1.0
        for p in parts:
            pred *= 1 + p["tok"] / 100
        pred = (pred - 1) * 100
        out.append({"scale": scale, "n": n, "model": model, "pred": pred,
                    "meas": comp["tok"], "gap": comp["tok"] - pred})
    return out


def make_additivity_figure(rows: list[dict], out_path: Path) -> Path:
    """Composed saving vs the prediction from its parts."""
    # Both scales on one axis: the 50-task sweep covers the replica axis, the
    # full-scale column tests whether the pattern survives ten times the tasks.
    # Scale is carried by marker fill so colour stays bound to the model.
    data = additivity_table(rows, "50")
    data_full = additivity_table(rows, "500")
    if not data:
        raise ValueError("could not build the additivity table — missing isolated arms")

    fig, ax = plt.subplots(figsize=fs(3.45, 2.9))

    allpts = data + data_full
    lo = min(min(d["pred"] for d in allpts), min(d["meas"] for d in allpts)) - 8
    hi = max(max(d["pred"] for d in allpts), max(d["meas"] for d in allpts)) + 8

    # Both axes are "% change", so more negative = more saving. A stack that
    # beats its parts lands BELOW the y=x line, not above it.
    ax.fill_between([lo, hi], lo, [lo, hi], color=GRID, alpha=0.45, zorder=0,
                    linewidth=0)
    ax.plot([lo, hi], [lo, hi], color=INK_MUTED, linewidth=0.7,
            linestyle=(0, (4, 3)), zorder=1)
    ax.axhline(0, color=GRID, linewidth=0.8, zorder=0)
    ax.axvline(0, color=GRID, linewidth=0.8, zorder=0)

    n_marker = {3: "o", 10: "^", 25: "s"}
    for d in data:
        ax.plot(d["pred"], d["meas"], marker=n_marker.get(d["n"], "o"),
                color=MODEL_COLORS[d["model"]], markersize=5.0,
                markeredgecolor="white", markeredgewidth=0.55,
                linestyle="none", zorder=3)
    for d in data_full:                      # open marker = full 500-task split
        ax.plot(d["pred"], d["meas"], marker=n_marker.get(d["n"], "o"),
                markerfacecolor="white", markeredgecolor=MODEL_COLORS[d["model"]],
                markeredgewidth=1.3, markersize=6.4, linestyle="none", zorder=4)

    # One label, parked in the empty lower-right quadrant. Two labels collided
    # with the full-scale markers once they were added, and the caption can
    # carry the second case in words.
    star = max((d for d in data + data_full if d["pred"] > 0 and d["meas"] < 0),
               key=lambda d: d["pred"] - d["meas"], default=None)
    if star:
        ax.annotate(
            f"{MODEL_LABELS[star['model']]}, N={star['n']}:\n"
            f"parts predict {pct(star['pred'])},\nstack saves {pct(star['meas'])}",
            (star["pred"], star["meas"]),
            xytext=(0.62, 0.14), textcoords="axes fraction", fontsize=6,
            ha="left", va="bottom", color=INK, linespacing=1.3,
            arrowprops=dict(arrowstyle="-", color=INK_MUTED, linewidth=0.6,
                            shrinkA=2, shrinkB=4),
        )

    ax.text(0.975, 0.035, "stack beats its parts", transform=ax.transAxes,
            fontsize=6.5, color=INK_MUTED, ha="right", va="bottom", style="italic")

    ax.set_xlabel("Predicted change from isolated arms (%)")
    ax.set_ylabel("Measured composed change (%)")
    ax.set_xlim(lo, hi)
    ax.set_ylim(lo, hi)
    ax.set_aspect("equal", adjustable="box")

    handles = [
        plt.Line2D([], [], marker="o", linestyle="none", color=c, markersize=4.6,
                   markeredgecolor="white", markeredgewidth=0.55, label=MODEL_LABELS[m])
        for m, c in MODEL_COLORS.items()
    ] + [
        plt.Line2D([], [], linestyle="none", marker="none", label=" "),
    ] + [
        plt.Line2D([], [], marker=mk, linestyle="none", color=INK_MUTED,
                   markersize=4.6, markeredgecolor="white", markeredgewidth=0.55,
                   label=f"N={n}")
        for n, mk in n_marker.items()
    ] + [
        plt.Line2D([], [], marker="o", linestyle="none", markerfacecolor="white",
                   markeredgecolor=INK_MUTED, markeredgewidth=1.3, markersize=5.6,
                   label="500 tasks"),
    ]
    # Upper-left is the "under its parts" triangle and is nearly empty.
    ax.legend(handles=handles, loc="upper left", handlelength=1.0,
              labelspacing=0.25, borderpad=0.2, ncol=2, columnspacing=0.8)

    fig.tight_layout(pad=0.4)
    return save(fig, out_path)


MIN_TURN_SAMPLES = 20


def make_cached_by_turn_figure(out_path: Path, *, n_replicas: int = 25) -> Path:
    """Cached share of input per turn under the cache-stable loop, three models.

    Only the cache-stable arm is plotted. The P0 baseline reports zero cached
    tokens because its backend never reads the provider field, not because the
    cache demonstrably failed -- plotting it as a comparison line would assert
    something the instrumentation cannot support.

    Each series is truncated where fewer than MIN_TURN_SAMPLES replica-turns
    reach that depth. Without this, Gemini shows a dramatic dip to 17% at turn 7
    computed from three observations, which reads as a cache collapse and is
    noise. The truncation must be stated in the figure caption.
    """
    from src.coord.prompt_cache_plots import (
        aggregate_by_turn,
        collect_llm_turns,
        trace_paths_from_batch,
    )

    fig, ax = plt.subplots(figsize=fs(3.45, 2.2))
    plotted = 0
    for model, color in MODEL_COLORS.items():
        key = MODEL_BATCH_KEY[model]
        matches = sorted(BATCH_DIR.glob(
            f"parallel_v8_pc_50t_r{n_replicas}_{key}_r{n_replicas}_*.json"))
        if not matches:
            print(f"  [skip] no v8_pc_50t_r{n_replicas} batch for {key}")
            continue
        agg = aggregate_by_turn(collect_llm_turns(trace_paths_from_batch(matches[0])))
        if agg.empty:
            print(f"  [skip] no llm_turn events in {matches[0].name}")
            continue
        kept = agg[agg["samples"] >= MIN_TURN_SAMPLES]
        dropped = len(agg) - len(kept)
        if dropped:
            print(f"  [{model}] truncated {dropped} turn(s) below n={MIN_TURN_SAMPLES}"
                  f" (deepest kept: turn {int(kept['turn_idx'].max())},"
                  f" n={int(kept['samples'].min())})")
        ax.plot(kept["turn_idx"], kept["cached_pct"], color=color, linewidth=1.6,
                marker="o", markersize=3.8, markeredgecolor="white",
                markeredgewidth=0.55, label=MODEL_LABELS[model])
        plotted += 1

    if not plotted:
        raise ValueError("no v8 prompt-cache batches found")

    ax.set_xlabel("Turn index")
    ax.set_ylabel("Cached share of input (%)")
    ax.set_ylim(0, 100)
    ax.legend(loc="lower right", handlelength=1.6, labelspacing=0.25)
    fig.tight_layout(pad=0.4)
    return save(fig, out_path)


def baseline_scaling() -> list[dict]:
    """P0 scaling on the 50-task subset, straight from the batch summaries.

    ``avg_token_overhead_ratio`` and ``avg_explore_redundancy_pct`` are written
    by run_parallel_batch.py, so nothing is recomputed here and the figures
    cannot drift from §3.3 of the paper. Cells resolve through
    ``baseline_for``, which prefers a fresh ``v8_p0_*`` batch, so these are the
    same baselines every delta in the matrix is measured against.
    """
    from analyze_v8_results import MODELS, baseline_for  # noqa: PLC0415

    out: list[dict] = []
    for n in (3, 10, 25):
        for key, short in MODELS:
            path = baseline_for("50", n, key)
            if path is None:
                print(f"  [skip] no 50-task P0 baseline for {key} at N={n}")
                continue
            d = json.loads(path.read_text())
            out.append({
                "n": n,
                "model": short,
                "overhead": float(d.get("avg_token_overhead_ratio") or 0.0),
                "redundancy": float(d.get("avg_explore_redundancy_pct") or 0.0),
                "ex": float(d.get("ex_accuracy_pct") or 0.0),
            })
    return out


def _categorical_x(ns: list[int]) -> dict[int, int]:
    """3, 10 and 25 are unevenly spaced, and a linear axis buries the first two
    points against the left spine. Three categories read better than a log axis
    at this size."""
    return {n: i for i, n in enumerate(sorted(set(ns)))}


def make_scaling_figure(out_path: Path) -> Path:
    """The problem, in one figure: cost tracks N, accuracy does not.

    Two stacked panels on a shared x rather than one panel with twin y axes.
    A dual-axis chart lets the author choose where the two series appear to
    cross, which is exactly the impression this figure must not manufacture.
    """
    data = baseline_scaling()
    if not data:
        raise ValueError("no 50-task P0 baselines found")
    xs = _categorical_x([d["n"] for d in data])

    fig, (top, bot) = plt.subplots(
        2, 1, sharex=True, figsize=fs(3.45, 3.4),
        gridspec_kw={"height_ratios": [1.35, 1.0], "hspace": 0.16})

    # Cost would grow exactly like this if every replica paid full price and
    # nothing amortised. The measured lines sitting on it IS the finding.
    # Labelled in the legend rather than annotated in place. Every free region
    # of this panel is crossed by a series at one N or another, so a floating
    # label with a leader line collides at some figure size or other.
    ref = sorted(xs)
    top.plot([xs[n] for n in ref], ref, color=INK_MUTED, linewidth=0.9,
             linestyle=(0, (4, 3)), zorder=1,
             label="cost $=N\\times$ one replica")

    for model, color in MODEL_COLORS.items():
        pts = sorted((d for d in data if d["model"] == model), key=lambda d: d["n"])
        if not pts:
            continue
        common = {"color": color, "linewidth": 1.6, "marker": "o",
                  "markersize": 4.2, "markeredgecolor": "white",
                  "markeredgewidth": 0.55, "zorder": 3}
        top.plot([xs[p["n"]] for p in pts], [p["overhead"] for p in pts],
                 label=MODEL_LABELS[model], **common)
        bot.plot([xs[p["n"]] for p in pts], [p["ex"] for p in pts], **common)

    # Kept to one line. Stacked panels put the two y labels close together, and
    # a two-line label on the upper one runs into the lower one's.
    top.set_ylabel("Cost ($\\times$ one replica)")
    top.set_ylim(0, max(d["overhead"] for d in data) * 1.18)
    # Upper left is the one reliably empty corner: every series rises to the right.
    top.legend(loc="upper left", handlelength=1.5, labelspacing=0.25,
               borderpad=0.2)

    # A fixed 0-100 accuracy axis would flatten the lines by construction and
    # beg the question. Pad the observed range instead and state the span.
    ex = [d["ex"] for d in data]
    span = max(ex) - min(ex)
    bot.set_ylim(min(ex) - 0.55 * span, max(ex) + 0.75 * span)
    bot.set_ylabel("Execution accuracy (%)")
    bot.set_xlabel("Parallel replicas $N$")
    bot.set_xticks([xs[n] for n in sorted(xs)])
    bot.set_xticklabels([str(n) for n in sorted(xs)])
    bot.set_xlim(-0.18, len(xs) - 0.82)

    worst = max(
        max(d["ex"] for d in data if d["model"] == m)
        - min(d["ex"] for d in data if d["model"] == m)
        for m in {d["model"] for d in data}
    )
    bot.annotate(f"no model moves more than {worst:.0f} points",
                 xy=(0.5, 0.06), xycoords="axes fraction", ha="center",
                 fontsize=plt.rcParams["legend.fontsize"], color=INK_MUTED,
                 style="italic")

    return save(fig, out_path)


def make_redundancy_figure(out_path: Path) -> Path:
    """Duplicated exploratory SQL against replica count.

    Replaces thesis/figures/baseline_explore_redundancy.png, which was drawn
    from a different task set (n=47) and reports 46--51% at N=3 where the
    current baselines give 39--49%. Numbers on a slide must match the paper.
    """
    data = baseline_scaling()
    if not data:
        raise ValueError("no 50-task P0 baselines found")
    xs = _categorical_x([d["n"] for d in data])

    fig, ax = plt.subplots(figsize=fs(3.45, 2.2))
    for model, color in MODEL_COLORS.items():
        pts = sorted((d for d in data if d["model"] == model), key=lambda d: d["n"])
        if not pts:
            continue
        ax.plot([xs[p["n"]] for p in pts], [p["redundancy"] for p in pts],
                color=color, linewidth=1.6, marker="o", markersize=4.2,
                markeredgecolor="white", markeredgewidth=0.55,
                label=MODEL_LABELS[model])

    ax.set_xlabel("Parallel replicas $N$")
    ax.set_ylabel("Duplicated exploratory SQL (%)")
    ax.set_xticks([xs[n] for n in sorted(xs)])
    ax.set_xticklabels([str(n) for n in sorted(xs)])
    ax.set_xlim(-0.18, len(xs) - 0.82)
    ax.set_ylim(0, 100)
    ax.legend(loc="lower right", handlelength=1.6, labelspacing=0.25)
    fig.tight_layout(pad=0.4)
    return save(fig, out_path)


def recall_split() -> list[dict]:
    """Pruning's raw-token effect at full scale, split on offline gold recall.

    Recomputed rather than read back from the paper, on the same batches and
    the same paired bootstrap the matrix uses, so the figure and Table II share
    a source. Point estimates reproduce the table exactly. Two interval bounds
    differ in the first decimal because they sit within a point of zero, and
    GPT at N=3 recall-incomplete flips its significance mark with the bootstrap
    seed. The paper marks it dagger, which is the conservative reading and the
    majority verdict across seeds. The error bars here say the same thing
    without depending on a threshold.
    """
    from analyze_v8_results import MODELS, baseline_for, find  # noqa: PLC0415
    from generate_robustness_pack import (  # noqa: PLC0415
        _bootstrap_mean_pct,
        _metric_map,
    )

    report = REPO_ROOT / "runs" / "reports" / "schema_pruning_full500_hybrid.json"
    if not report.exists():
        raise ValueError(f"missing {report}")
    rows = json.loads(report.read_text())["rows"]
    complete = {int(r["question_id"]): float(r["gold_table_recall"]) >= 1.0 for r in rows}

    out: list[dict] = []
    for n in (3, 10):
        for key, short in MODELS:
            tp, cp = find(f"v8_prune_500t_r{n}", key), baseline_for("500", n, key)
            if tp is None or cp is None:
                print(f"  [skip] recall split {short} N={n}: missing arm or baseline")
                continue
            treat, ctrl = _metric_map(tp, "tokens"), _metric_map(cp, "tokens")
            for kept in (True, False):
                t = {q: v for q, v in treat.items() if complete.get(q) is kept}
                c = {q: v for q, v in ctrl.items() if complete.get(q) is kept}
                nq, _, _, delta, lo, hi = _bootstrap_mean_pct(t, c)
                out.append({"n": n, "model": short, "complete": kept, "obs": nq,
                            "delta": delta, "lo": lo, "hi": hi})
    return out


def make_recall_split_figure(out_path: Path) -> Path:
    """Pruning saves where recall holds and costs several times more where it
    does not. The two regimes have opposite signs, so a zero line does the
    separating and the bars need no colour to be told apart."""
    data = recall_split()
    if not data:
        raise ValueError("could not build the recall split")

    cells = sorted({(d["n"], d["model"]) for d in data},
                   key=lambda c: (c[0], list(MODEL_COLORS).index(c[1])))
    fig, ax = plt.subplots(figsize=fs(4.0, 2.6))
    width = 0.42
    # Cells are spread wider than unit spacing and the two replica-count blocks
    # are separated further. At unit spacing the tick labels ran together, and
    # "Gemini" abutting "DeepSeek" reads as one word.
    ns = sorted({c[0] for c in cells})
    pitch, gap = 1.3, 0.8
    xpos = {c: i * pitch + gap * ns.index(c[0]) for i, c in enumerate(cells)}

    for cell in cells:
        for kept in (True, False):
            rec = next((d for d in data
                        if (d["n"], d["model"]) == cell and d["complete"] is kept), None)
            if rec is None:
                continue
            x = xpos[cell] + (-width / 2 if kept else width / 2)
            color = MODEL_COLORS[cell[1]]
            ax.bar(x, rec["delta"], width=width * 0.92, color=color,
                   edgecolor="white", linewidth=0.6,
                   # Hatch, not a second hue: regime is a property of the task,
                   # not a fourth entity, and colour stays bound to the model.
                   hatch="" if kept else "////", alpha=1.0 if kept else 0.55,
                   zorder=2)
            ax.errorbar(x, rec["delta"], yerr=[[rec["delta"] - rec["lo"]],
                                               [rec["hi"] - rec["delta"]]],
                        fmt="none", ecolor=INK, elinewidth=0.8, capsize=2,
                        capthick=0.8, zorder=3)

    ax.axhline(0, color=INK, linewidth=0.9, zorder=4)
    ax.set_xticks([xpos[c] for c in cells])
    ax.set_xticklabels([f"{m}\n$N$={n}" for n, m in cells])
    ax.set_ylabel("Raw-token change (%)")
    ax.set_xlim(-0.6, max(xpos.values()) + 0.6)
    # Headroom for the legend above the tallest whisker, which reaches +231.
    hi = max(d["hi"] for d in data)
    lo = min(d["lo"] for d in data)
    ax.set_ylim(lo - 0.06 * (hi - lo), hi * 1.28)

    # Recall is a property of the task, so the share is the same in every
    # group. Read it off one cell rather than restating it six times.
    n_kept = next(d["obs"] for d in data if d["complete"])
    n_miss = next(d["obs"] for d in data if not d["complete"])
    total = n_kept + n_miss
    handles = [
        plt.Rectangle((0, 0), 1, 1, facecolor=INK_MUTED, edgecolor="white",
                      label=f"all gold tables kept ({100 * n_kept / total:.0f}% of tasks)"),
        plt.Rectangle((0, 0), 1, 1, facecolor=INK_MUTED, edgecolor="white",
                      alpha=0.55, hatch="////",
                      label=f"one or more missing ({100 * n_miss / total:.0f}%)"),
    ]
    ax.legend(handles=handles, loc="upper left", handlelength=1.4,
              labelspacing=0.25, borderpad=0.2)
    fig.tight_layout(pad=0.4)
    return save(fig, out_path)


def make_billed_by_model_figure(rows: list[dict], out_path: Path) -> Path:
    """Every prompt-cache cell's billed saving, grouped by model.

    The honest reading of the paper's largest number is on this chart. The
    mechanism is identical across the three groups, so the spread between them
    is the provider's cached discount, not the method working harder on one
    model. The discount is read from the registry rather than typed in.
    """
    from src.llm.models import load_model_registry  # noqa: PLC0415

    reg = load_model_registry()
    cells = [r for r in rows if r["method"] == "prompt cache"]
    if not cells:
        raise ValueError("no prompt-cache cells in v8_numbers.txt")

    fig, ax = plt.subplots(figsize=fs(4.2, 2.5))
    pos, ticks, labels = 0.0, [], []
    for model, color in MODEL_COLORS.items():
        group = sorted((c for c in cells if c["model"] == model),
                       key=lambda c: (c["scale"], c["n"]))
        if not group:
            continue
        start = pos
        for c in group:
            ax.bar(pos, c["billed"], width=0.78, color=color, edgecolor="white",
                   linewidth=0.6,
                   # Open bars are the 500-task cells, matching fig4 and fig5.
                   alpha=1.0 if c["scale"] == "50" else 0.5, zorder=2)
            pos += 1
        ticks.append((start + pos - 1) / 2)

        spec = reg.get(MODEL_BATCH_KEY[model])
        p_in = float(getattr(spec, "price_per_1m_input", 0) or 0)
        p_cache = getattr(spec, "price_per_1m_cached_input", None)
        rate = f"{100 * float(p_cache) / p_in:.0f}%" if p_cache and p_in else "?"
        # Short second line. "cached input at 50% of standard" is three times
        # the width of the group it labels and runs into its neighbours.
        labels.append(f"{MODEL_LABELS[model]}\ncached at {rate}")
        pos += 1.1

    ax.axhline(0, color=INK, linewidth=0.9, zorder=4)
    ax.set_xticks(ticks)
    ax.set_xticklabels(labels)
    ax.set_ylabel("Billed input change (%)")
    ax.set_xlim(-0.8, pos - 1.4)
    # Every bar hangs from zero, so a header band above it is the one region
    # guaranteed to stay empty whatever the data does.
    deepest = min(c["billed"] for c in cells)
    ax.set_ylim(deepest * 1.06, abs(deepest) * 0.16)
    ax.annotate("one bar per measured cell, lighter bars are the 500-task split",
                xy=(0.5, 0.955), xycoords="axes fraction", ha="center",
                va="top", fontsize=plt.rcParams["legend.fontsize"],
                color=INK_MUTED, style="italic")
    fig.tight_layout(pad=0.4)
    return save(fig, out_path)


def make_factstore_figure(rows: list[dict], out_path: Path) -> Path:
    """The fact store's two problems, on one axis each.

    Top: the token effect has no stable sign, and it does not even keep its sign
    between scales. Each configuration is drawn as a pair joined by a line, the
    50-task subset against the full split, so a reversal reads as a line
    crossing zero rather than as two numbers a reader has to difference.

    Bottom: the injection tax, which is the obvious explanation and is not the
    explanation. The load barely moves between scales while the sign flips, so
    it bounds the achievable saving without predicting it.
    """
    cells = [r for r in rows if r["method"] == "P3 facts" and r["n"] in (3, 10)]
    if not cells:
        raise ValueError("no fact-store cells at N in {3,10}")

    configs = [(n, m) for n in (3, 10) for m in MODEL_COLORS]
    xs = {c: i for i, c in enumerate(configs)}

    fig, (top, bot) = plt.subplots(
        2, 1, sharex=True, figsize=fs(4.0, 3.2),
        gridspec_kw={"height_ratios": [1.55, 1.0], "hspace": 0.16})

    for (n, model) in configs:
        x = xs[(n, model)]
        color = MODEL_COLORS[model]
        sub = {r["scale"]: r for r in cells if r["n"] == n and r["model"] == model}
        if "50" not in sub or "500" not in sub:
            continue
        a, b = sub["50"], sub["500"]
        top.plot([x, x], [a["tok"], b["tok"]], color=color, linewidth=1.4,
                 alpha=0.55, zorder=2, solid_capstyle="round")
        top.plot([x], [a["tok"]], marker="o", color=color, markersize=5.2,
                 markeredgecolor="white", markeredgewidth=0.6, zorder=3)
        # Open marker for the full split, matching fig4 and fig5.
        top.plot([x], [b["tok"]], marker="o", markerfacecolor="white",
                 markeredgecolor=color, markeredgewidth=1.6, markersize=5.6,
                 zorder=3)
        bot.plot([x, x], [a["inj"], b["inj"]], color=color, linewidth=1.4,
                 alpha=0.55, zorder=2, solid_capstyle="round")
        bot.plot([x], [a["inj"]], marker="o", color=color, markersize=5.2,
                 markeredgecolor="white", markeredgewidth=0.6, zorder=3)
        bot.plot([x], [b["inj"]], marker="o", markerfacecolor="white",
                 markeredgecolor=color, markeredgewidth=1.6, markersize=5.6,
                 zorder=3)

    top.axhline(0, color=INK, linewidth=0.9, zorder=4)
    top.set_ylabel("Raw-token change (%)")
    ys = [r["tok"] for r in cells]
    top.set_ylim(min(ys) - 6, max(ys) + 12)
    top.annotate("costs tokens", xy=(0.012, 0.955), xycoords="axes fraction",
                 fontsize=plt.rcParams["legend.fontsize"], color=INK_MUTED,
                 style="italic", va="top")
    top.annotate("saves tokens", xy=(0.012, 0.045), xycoords="axes fraction",
                 fontsize=plt.rcParams["legend.fontsize"], color=INK_MUTED,
                 style="italic", va="bottom")

    bot.set_ylabel("Facts injected\nper task")
    bot.set_ylim(0, max(r["inj"] for r in cells) * 1.22)
    bot.set_xticks(range(len(configs)))
    bot.set_xticklabels([f"{m}\n$N$={n}" for n, m in configs])
    bot.set_xlim(-0.55, len(configs) - 0.45)

    handles = [
        plt.Line2D([], [], marker="o", linestyle="none", color=INK_MUTED,
                   markersize=5.2, markeredgecolor="white", label="50 tasks"),
        plt.Line2D([], [], marker="o", linestyle="none", markerfacecolor="white",
                   markeredgecolor=INK_MUTED, markeredgewidth=1.6,
                   markersize=5.6, label="500 tasks"),
    ]
    top.legend(handles=handles, loc="upper right", handlelength=1.2,
               labelspacing=0.25, borderpad=0.2)
    return save(fig, out_path)


def make_factstore_figure_wrapper(rows: list[dict]):
    return lambda p: make_factstore_figure(rows, p)


def make_billed_by_model_figure_wrapper(rows: list[dict]):
    return lambda p: make_billed_by_model_figure(rows, p)


def main() -> int:
    global _scale

    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--slides", action="store_true",
                    help="re-render at presentation size into thesis/figures/slides/")
    args = ap.parse_args()

    if not NUMBERS.exists():
        print(f"missing {NUMBERS}; run scripts/analyze_v8_results.py first")
        return 1

    out_dir = OUT_DIR / "slides" if args.slides else OUT_DIR
    plt.rcParams.update(SLIDE_RC if args.slides else PAPER_RC)
    _scale = SLIDE_SCALE if args.slides else 1.0
    print(f"rendering at {'presentation' if args.slides else 'column'} size "
          f"into {out_dir.relative_to(REPO_ROOT)}")

    rows = parse_numbers(NUMBERS)
    print(f"parsed {len(rows)} measured cells "
          f"({sum(r['scale'] == '50' for r in rows)} at 50-task)")

    # Each figure is attempted independently. The scaling and recall-split
    # figures read batch files rather than v8_numbers.txt, so a missing batch
    # should cost one figure, not the whole run.
    jobs = [
        ("fig4_two_ledger.png", lambda p: make_two_ledger_figure(rows, p)),
        ("fig5_additivity.png", lambda p: make_additivity_figure(rows, p)),
        ("fig2_cached_by_turn.png", make_cached_by_turn_figure),
        ("fig6_scaling.png", make_scaling_figure),
        ("fig7_redundancy.png", make_redundancy_figure),
        ("fig8_recall_split.png", make_recall_split_figure),
        ("fig9_billed_by_model.png", make_billed_by_model_figure_wrapper(rows)),
        ("fig10_factstore.png", make_factstore_figure_wrapper(rows)),
    ]
    for name, fn in jobs:
        try:
            path = fn(out_dir / name)
        except Exception as exc:  # noqa: BLE001 - one bad input must not kill the rest
            print(f"  [warn] {name} skipped: {exc}")
            continue
        print(f"wrote {path.relative_to(REPO_ROOT)}")

    print("\nadditivity check:")
    for d in additivity_table(rows, "50") + additivity_table(rows, "500"):
        verdict = "beats parts" if d["gap"] < 0 else "under parts"
        print(f"  {d['scale']:>3}t N={d['n']:<3} {d['model']:9} pred {d['pred']:+6.1f}  "
              f"meas {d['meas']:+6.1f}  gap {d['gap']:+6.1f}  {verdict}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
