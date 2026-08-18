"""Turn-by-turn prompt-cache figures.

Reads per-turn ``llm_turn`` events (written when ``logging.log_llm_messages`` is
on; ``cached_prompt_tokens`` is populated by ``CachedRunTrace``) and plots how
input tokens split into cached vs billed as the conversation grows.
"""

from __future__ import annotations

import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import pandas as pd  # noqa: E402

from src.logging.trace import read_trace_events  # noqa: E402


def collect_llm_turns(trace_paths: list[Path]) -> pd.DataFrame:
    """Gather (turn_idx, prompt_tokens, cached_prompt_tokens) from replica traces."""
    records: list[dict[str, int]] = []
    for path in trace_paths:
        path = Path(path)
        if not path.exists():
            continue
        for ev in read_trace_events(path):
            if ev.get("event") != "llm_turn":
                continue
            prompt = int(ev.get("prompt_tokens") or 0)
            cached = int(ev.get("cached_prompt_tokens") or 0)
            records.append(
                {
                    "turn_idx": int(ev.get("turn_idx", 0)),
                    "prompt_tokens": prompt,
                    "cached_prompt_tokens": cached,
                }
            )
    return pd.DataFrame.from_records(
        records, columns=["turn_idx", "prompt_tokens", "cached_prompt_tokens"]
    )


def aggregate_by_turn(df: pd.DataFrame) -> pd.DataFrame:
    """Mean cached / uncached / total input tokens per turn index across replicas."""
    if df.empty:
        return df
    df = df.copy()
    df["uncached_prompt_tokens"] = df["prompt_tokens"] - df["cached_prompt_tokens"]
    agg = (
        df.groupby("turn_idx")
        .agg(
            mean_prompt=("prompt_tokens", "mean"),
            mean_cached=("cached_prompt_tokens", "mean"),
            mean_uncached=("uncached_prompt_tokens", "mean"),
            samples=("prompt_tokens", "size"),
        )
        .reset_index()
        .sort_values("turn_idx")
    )
    agg["cached_pct"] = [
        (100.0 * c / p) if p > 0 else 0.0
        for c, p in zip(agg["mean_cached"], agg["mean_prompt"])
    ]
    return agg


def trace_paths_from_batch(batch_path: Path) -> list[Path]:
    """Collect per-replica trace paths from a parallel batch JSON.

    Prefers every replica trace referenced by each task's coord trace; falls back
    to the chosen replica trace when no coord trace is available.
    """
    data = json.loads(Path(batch_path).read_text(encoding="utf-8"))
    paths: list[Path] = []
    seen: set[str] = set()
    for row in data.get("rows", []):
        added = False
        coord = str(row.get("coord_trace_path") or "")
        if coord and Path(coord).exists():
            for ev in read_trace_events(Path(coord)):
                if ev.get("event") == "replica_end":
                    tp = str(ev.get("trace_path") or "")
                    if tp and tp not in seen:
                        seen.add(tp)
                        paths.append(Path(tp))
                        added = True
        if not added:
            chosen = str(row.get("chosen_trace_path") or "")
            if chosen and chosen not in seen:
                seen.add(chosen)
                paths.append(Path(chosen))
    return paths


def plot_cache_tokens_by_turn(agg: pd.DataFrame, out_path: Path, *, title: str) -> Path:
    """Stacked area of mean cached vs billed input tokens per turn index."""
    fig, ax = plt.subplots(figsize=(8, 5))
    ax.stackplot(
        agg["turn_idx"],
        agg["mean_cached"],
        agg["mean_uncached"],
        labels=["Cached input (discounted)", "Billed input (uncached)"],
        colors=["#4c9f70", "#d65f5f"],
        alpha=0.85,
    )
    ax.plot(
        agg["turn_idx"],
        agg["mean_prompt"],
        color="black",
        lw=1.5,
        label="Total input tokens",
    )
    ax.set_xlabel("Turn index")
    ax.set_ylabel("Mean input tokens per replica-turn")
    ax.set_title(title)
    ax.legend(loc="upper left")
    ax.grid(True, alpha=0.3)
    fig.tight_layout()
    out_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out_path, dpi=150)
    plt.close(fig)
    return out_path


def plot_cache_hit_rate_by_turn(agg: pd.DataFrame, out_path: Path, *, title: str) -> Path:
    """Mean cached share of input tokens per turn index."""
    fig, ax = plt.subplots(figsize=(8, 5))
    ax.plot(agg["turn_idx"], agg["cached_pct"], marker="o", color="#4c9f70", lw=1.8)
    ax.set_xlabel("Turn index")
    ax.set_ylabel("Cached share of input tokens (%)")
    ax.set_ylim(0, 100)
    ax.set_title(title)
    ax.grid(True, alpha=0.3)
    fig.tight_layout()
    out_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out_path, dpi=150)
    plt.close(fig)
    return out_path


def plot_prompt_cache_figures(
    batch_path: Path, out_dir: Path, *, label: str | None = None
) -> list[Path]:
    """End-to-end: batch JSON -> two turn-by-turn cache figures."""
    name = label or Path(batch_path).stem
    df = collect_llm_turns(trace_paths_from_batch(batch_path))
    agg = aggregate_by_turn(df)
    if agg.empty:
        raise ValueError(
            f"No llm_turn events found for {batch_path}. "
            "Set logging.log_llm_messages: true and re-run with --prompt-cache."
        )
    saved = [
        plot_cache_tokens_by_turn(
            agg,
            out_dir / "prompt_cache_tokens_by_turn.png",
            title=f"Input tokens by turn — {name}",
        ),
        plot_cache_hit_rate_by_turn(
            agg,
            out_dir / "prompt_cache_hit_rate_by_turn.png",
            title=f"Cached input share by turn — {name}",
        ),
    ]
    return saved
