"""Tests for thesis Chapter 2 draft generation."""

from __future__ import annotations

import json
from pathlib import Path

from src.coord.chapter2_draft import generate_chapter2_markdown

REPO = Path(__file__).resolve().parents[1]


def test_generate_chapter2_from_report() -> None:
    report_path = REPO / "runs/reports/baseline_gpt4o_baseline_full.json"
    if not report_path.is_file():
        return
    md = generate_chapter2_markdown([report_path])
    assert "# Chapter 2:" in md
    assert "P0" in md
    assert "gpt-4o-mini" in md
    assert "Explore redundancy" in md


def test_generate_chapter2_requires_comparison_rows(tmp_path: Path) -> None:
    empty = tmp_path / "empty.json"
    empty.write_text(json.dumps({"comparison": []}), encoding="utf-8")
    try:
        generate_chapter2_markdown([empty])
        raised = False
    except ValueError:
        raised = True
    assert raised
