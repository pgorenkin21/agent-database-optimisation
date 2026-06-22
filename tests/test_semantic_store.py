"""Tests for P3 shared semantic store."""

from __future__ import annotations

from src.coord.semantic_store import SharedSemanticStore


def test_publish_and_peer_facts() -> None:
    store = SharedSemanticStore(max_entries=16, max_inject_chars=200, max_inject_bullets=4)
    store.publish(
        agent_id="agent_0",
        sql="SELECT * FROM customers",
        rows=[(1,)],
        error=None,
    )
    peer = store.peer_facts("agent_1")
    assert peer
    own = store.peer_facts("agent_0")
    assert own
    assert peer != own or len(peer) == 1


def test_injection_cap() -> None:
    store = SharedSemanticStore(max_entries=32, max_inject_chars=80, max_inject_bullets=3)
    for i in range(10):
        store.publish(
            agent_id=f"agent_{i % 2}",
            sql=f"SELECT {i} FROM t{i}",
            rows=[(i,)],
            error=None,
        )
    facts = store.peer_facts("agent_99")
    text = "\n".join(facts)
    assert len(facts) <= 3
    assert len(text) <= 80 or len(facts) == 1
