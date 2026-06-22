"""Tests for thesis Chapter 3 draft generation."""

from __future__ import annotations

import json
from pathlib import Path

from src.coord.chapter3_draft import generate_chapter3_markdown, load_comparisons_from_batches

REPO = Path(__file__).resolve().parents[1]


def test_load_comparisons_from_batches() -> None:
    batch_dir = REPO / "runs" / "batches"
    if not batch_dir.is_dir():
        return
    comparisons = load_comparisons_from_batches(batch_dir, replica_counts=[25])
    if not comparisons:
        return
    assert 25 in comparisons
    assert len(comparisons[25]) >= 1


def test_generate_chapter3_markdown() -> None:
    batch_dir = REPO / "runs" / "batches"
    if not batch_dir.is_dir():
        return
    comparisons = load_comparisons_from_batches(batch_dir, replica_counts=[10, 25])
    if not comparisons:
        return
    md = generate_chapter3_markdown(comparisons)
    assert "# Chapter 3:" in md
    assert "P0_early_stop" in md
    assert "early stop" in md.lower()


def test_generate_chapter3_requires_data() -> None:
    try:
        generate_chapter3_markdown({})
        raised = False
    except ValueError:
        raised = True
    assert raised
