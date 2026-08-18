"""Tests for turn-by-turn prompt-cache plotting."""

from __future__ import annotations

import json
from pathlib import Path

from src.coord.prompt_cache_plots import (
    aggregate_by_turn,
    collect_llm_turns,
    plot_prompt_cache_figures,
    trace_paths_from_batch,
)


def _write_trace(path: Path, turns: list[tuple[int, int, int]]) -> None:
    """turns = [(turn_idx, prompt_tokens, cached_prompt_tokens), ...]"""
    lines = []
    for turn_idx, prompt, cached in turns:
        lines.append(
            json.dumps(
                {
                    "event": "llm_turn",
                    "turn_idx": turn_idx,
                    "prompt_tokens": prompt,
                    "completion_tokens": 50,
                    "cached_prompt_tokens": cached,
                    "tool_calls": ["execute_sql"],
                }
            )
        )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def test_collect_and_aggregate(tmp_path: Path):
    _write_trace(tmp_path / "a.jsonl", [(0, 1000, 0), (1, 1300, 1000)])
    _write_trace(tmp_path / "b.jsonl", [(0, 1000, 0), (1, 1300, 800)])

    df = collect_llm_turns([tmp_path / "a.jsonl", tmp_path / "b.jsonl"])
    assert len(df) == 4

    agg = aggregate_by_turn(df)
    turn0 = agg[agg["turn_idx"] == 0].iloc[0]
    turn1 = agg[agg["turn_idx"] == 1].iloc[0]
    assert turn0["mean_cached"] == 0
    assert turn0["cached_pct"] == 0.0
    assert turn1["mean_cached"] == 900  # (1000 + 800) / 2
    assert turn1["mean_uncached"] == 400  # 1300 - 900
    assert round(turn1["cached_pct"], 1) == round(100.0 * 900 / 1300, 1)


def test_trace_paths_from_batch_uses_coord_replicas(tmp_path: Path):
    rep0 = tmp_path / "agent0.jsonl"
    rep1 = tmp_path / "agent1.jsonl"
    _write_trace(rep0, [(0, 100, 0)])
    _write_trace(rep1, [(0, 100, 0)])
    coord = tmp_path / "coord_x.jsonl"
    coord.write_text(
        "\n".join(
            [
                json.dumps({"event": "parallel_start", "prompt_cache": True}),
                json.dumps({"event": "replica_end", "trace_path": str(rep0)}),
                json.dumps({"event": "replica_end", "trace_path": str(rep1)}),
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    batch = tmp_path / "batch.json"
    batch.write_text(
        json.dumps(
            {"rows": [{"coord_trace_path": str(coord), "chosen_trace_path": str(rep0)}]}
        ),
        encoding="utf-8",
    )
    paths = trace_paths_from_batch(batch)
    assert set(paths) == {rep0, rep1}


def test_trace_paths_falls_back_to_chosen(tmp_path: Path):
    chosen = tmp_path / "chosen.jsonl"
    _write_trace(chosen, [(0, 100, 0)])
    batch = tmp_path / "batch.json"
    batch.write_text(
        json.dumps(
            {"rows": [{"coord_trace_path": "", "chosen_trace_path": str(chosen)}]}
        ),
        encoding="utf-8",
    )
    assert trace_paths_from_batch(batch) == [chosen]


def test_plot_figures_written(tmp_path: Path):
    rep = tmp_path / "agent0.jsonl"
    _write_trace(rep, [(0, 1000, 0), (1, 1300, 1000)])
    batch = tmp_path / "batch.json"
    batch.write_text(
        json.dumps({"rows": [{"coord_trace_path": "", "chosen_trace_path": str(rep)}]}),
        encoding="utf-8",
    )
    out_dir = tmp_path / "plots"
    saved = plot_prompt_cache_figures(batch, out_dir, label="test")
    assert len(saved) == 2
    for p in saved:
        assert p.exists() and p.stat().st_size > 0
