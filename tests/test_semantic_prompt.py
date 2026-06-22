"""Tests for semantic prompt injection helpers."""

from __future__ import annotations

from src.agent.prompt import (
    SEMANTIC_CONTEXT_PREFIX,
    apply_semantic_context,
    format_semantic_context,
)


def test_format_semantic_context_empty() -> None:
    assert format_semantic_context([]) == ""


def test_format_semantic_context_bullets() -> None:
    text = format_semantic_context(["customers returned 5 row(s)", "column[0]=EUR"])
    assert text.startswith(SEMANTIC_CONTEXT_PREFIX)
    assert "customers returned" in text


def test_apply_semantic_context_replaces_prior() -> None:
    messages = [{"role": "user", "content": "task"}]
    apply_semantic_context(messages, format_semantic_context(["fact a"]))
    apply_semantic_context(messages, format_semantic_context(["fact b"]))
    semantic_msgs = [
        m for m in messages if str(m.get("content", "")).startswith(SEMANTIC_CONTEXT_PREFIX)
    ]
    assert len(semantic_msgs) == 1
    assert "fact b" in str(semantic_msgs[0]["content"])
