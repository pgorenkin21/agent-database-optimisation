"""Tests for middleware stack analysis and Chapter 6 draft."""

from __future__ import annotations

from pathlib import Path

from src.coord.chapter6_draft import generate_chapter6_markdown
from src.coord.middleware_stack_analysis import (
    FULL_STACK_BATCH_IDS,
    find_full_stack_batch,
    find_p1p2_batch,
    load_stack_by_replica_count,
    p1p2_batch_summary,
)

REPO = Path(__file__).resolve().parents[1]


def test_p1p2_batch_summary() -> None:
    data = {
        "shared_cache": True,
        "discovery_board": True,
        "avg_cache_hit_rate_pct": 70.0,
        "avg_discovery_fragments": 10.0,
        "rows": [
            {"cache_hits": 5, "cache_misses": 2, "discovery_injections": 3, "discovery_fragments": 4},
        ],
    }
    s = p1p2_batch_summary(data)
    assert s["shared_cache"] is True
    assert s["discovery_board"] is True
    assert s["avg_discovery_fragments"] == 10.0


def test_find_p1p2_batch() -> None:
    batch_dir = REPO / "runs" / "batches"
    if not batch_dir.is_dir():
        return
    path = find_p1p2_batch(batch_dir, "gemini-2.5-flash", 10, batch_id="p1p2_r10_bo")
    assert path is not None
    assert "p1_cache_p2_discovery" in path.name


def test_load_stack_r10() -> None:
    batch_dir = REPO / "runs" / "batches"
    if not batch_dir.is_dir():
        return
    stack = load_stack_by_replica_count(batch_dir, n_replicas=10)
    if not stack:
        return
    assert "gemini-2.5-flash" in stack or "gpt-4o-mini" in stack
    gem = stack.get("gemini-2.5-flash", {})
    if gem:
        assert "P0" in gem
        assert "P1+P2" in gem


def test_find_full_stack_schema_prune_batch_pattern() -> None:
    batch_dir = REPO / "runs" / "batches"
    if not batch_dir.is_dir():
        return
    from src.coord.middleware_stack_analysis import (
        FULL_STACK_SCHEMA_PRUNE_BATCH_IDS,
        find_full_stack_schema_prune_batch,
    )

    path = find_full_stack_schema_prune_batch(
        batch_dir, "gemini-2.5-flash", 10, batch_id=FULL_STACK_SCHEMA_PRUNE_BATCH_IDS[10]
    )
    if path is not None:
        assert "schema_prune" in path.name


def test_load_stack_includes_full_stack_prune() -> None:
    batch_dir = REPO / "runs" / "batches"
    if not batch_dir.is_dir():
        return
    stack = load_stack_by_replica_count(batch_dir, n_replicas=10)
    gem = stack.get("gemini-2.5-flash", {})
    if "full_stack_prune" in gem:
        assert gem["full_stack_prune"].get("schema_pruning") is True


def test_find_full_stack_batch_pattern() -> None:
    batch_dir = REPO / "runs" / "batches"
    if not batch_dir.is_dir():
        return
    path = find_full_stack_batch(
        batch_dir, "gpt-4o-mini", 25, batch_id=FULL_STACK_BATCH_IDS[25]
    )
    # None until sweep completes
    if path is not None:
        assert "p1_cache_p2_discovery_early_stop" in path.name


def test_generate_chapter6_markdown() -> None:
    batch_dir = REPO / "runs" / "batches"
    if not batch_dir.is_dir():
        return
    from src.coord.middleware_stack_analysis import load_stack_by_replica_counts

    stacks = load_stack_by_replica_counts(batch_dir, replica_counts=[10, 25])
    if not stacks:
        return
    md = generate_chapter6_markdown(stacks)
    assert "# Chapter 6:" in md
    assert "P1+P2" in md
