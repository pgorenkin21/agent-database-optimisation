"""Tests for P2 shared discovery board."""

from __future__ import annotations

from src.agent.prompt import (
    DISCOVERY_CONTEXT_PREFIX,
    apply_discovery_context,
    format_discovery_context,
)
from src.coord.shared_discovery import SharedDiscoveryBoard
from src.db.sql_fragments import extract_sql_fragments


def test_extract_sql_fragments_table_and_column() -> None:
    frags = extract_sql_fragments("SELECT a FROM users WHERE users.id = 1")
    assert "table:users" in frags
    assert any("id" in f for f in frags)


def test_shared_discovery_board_peer_fragments() -> None:
    board = SharedDiscoveryBoard(max_fragments=64)
    board.publish(agent_id="agent_0", sql="SELECT id FROM orders")
    board.publish(agent_id="agent_1", sql="SELECT customer_id FROM customers")

    peer_0 = board.peer_fragments("agent_0")
    peer_1 = board.peer_fragments("agent_1")

    assert any(f.startswith("table:customers") for f in peer_0)
    assert any(f.startswith("table:orders") for f in peer_1)
    assert board.stats.publishes == 2


def test_format_discovery_context_groups_fragments() -> None:
    text = format_discovery_context(
        ["table:orders", "col:orders.id", "pred:orders.status = 'shipped'"]
    )
    assert DISCOVERY_CONTEXT_PREFIX in text
    assert "orders" in text
    assert "orders.id" in text


def test_apply_discovery_context_replaces_prior_message() -> None:
    messages = [{"role": "user", "content": "Question"}]
    apply_discovery_context(messages, format_discovery_context(["table:t"]))
    assert len(messages) == 2
    apply_discovery_context(messages, "")
    assert len(messages) == 1


def test_resolve_trace_policy_p2() -> None:
    from src.coord.parallel import resolve_trace_policy

    assert resolve_trace_policy(shared_cache=False, early_stop=False, discovery_board=True) == (
        "P2_subexpr_propagation"
    )
    assert resolve_trace_policy(shared_cache=False, early_stop=True, discovery_board=True) == (
        "P2_subexpr_propagation_early_stop"
    )
    assert resolve_trace_policy(shared_cache=True, early_stop=False, discovery_board=True) == (
        "P1_P2_combined"
    )
    assert resolve_trace_policy(shared_cache=False, early_stop=False, semantic_store=True) == (
        "P3_semantic_store"
    )
    assert resolve_trace_policy(shared_cache=True, early_stop=True, semantic_store=True) == (
        "P1_P3_combined_early_stop"
    )
