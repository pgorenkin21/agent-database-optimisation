"""Tests for TF-IDF semantic schema table scoring."""

from __future__ import annotations

from src.agent.schema_embeddings import score_tables_semantic, tokenize


def test_tokenize_splits_identifiers() -> None:
    tokens = tokenize("How many customers spent EUR in 2012?")
    assert "customers" in tokens
    assert "eur" in tokens


def test_semantic_scores_rank_relevant_table() -> None:
    docs = {
        "customers": "customers CustomerID Segment Currency customer profile",
        "products": "products ProductID Description product catalog item",
    }
    scores = score_tables_semantic(
        "Which customers use EUR currency?",
        docs,
    )
    assert scores["customers"] > scores["products"]
