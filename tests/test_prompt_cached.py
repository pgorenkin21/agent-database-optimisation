"""Tests for append-only shared-context injection (prompt_cached)."""

from __future__ import annotations

import copy

from src.agent.prompt_cached import append_discovery_delta, append_semantic_delta


def _zone1() -> list[dict[str, str]]:
    return [
        {"role": "system", "content": "SYSTEM PROMPT"},
        {"role": "user", "content": "TASK + full schema text"},
    ]


def test_semantic_delta_appends_only_new_facts():
    messages = _zone1()
    shown: set[str] = set()

    new, block = append_semantic_delta(messages, shown, ["customers has 5 rows", "join works"])
    assert len(new) == 2
    assert block
    assert len(messages) == 3  # one trailing block appended

    # Re-publishing the same facts appends nothing.
    new2, block2 = append_semantic_delta(messages, shown, ["customers has 5 rows", "join works"])
    assert new2 == []
    assert block2 == ""
    assert len(messages) == 3

    # Only the genuinely new fact is appended.
    new3, _ = append_semantic_delta(messages, shown, ["join works", "orders empty"])
    assert new3 == ["orders empty"]
    assert len(messages) == 4


def test_discovery_delta_appends_only_new_fragments():
    messages = _zone1()
    shown: set[str] = set()

    new, block = append_discovery_delta(messages, shown, ["table:customers", "col:customers.id"])
    assert len(new) == 2
    assert block
    assert len(messages) == 3

    new2, _ = append_discovery_delta(messages, shown, ["table:customers", "join_on:a.id=b.id"])
    assert new2 == ["join_on:a.id=b.id"]
    assert len(messages) == 4


def test_zone1_prefix_is_byte_stable_across_injections():
    """The static prefix (system + task) must never change — that is what keeps
    provider prefix-caching valid. This guards against the interior-mutation bug
    that the original apply_*_context helpers had."""
    messages = _zone1()
    frozen = copy.deepcopy(messages[:2])

    sem_shown: set[str] = set()
    disc_shown: set[str] = set()
    for turn in range(5):
        append_semantic_delta(messages, sem_shown, [f"fact {turn}", "shared fact"])
        append_discovery_delta(messages, disc_shown, [f"table:t{turn}", "col:x.y"])
        # Simulate the loop appending assistant + tool messages at the tail.
        messages.append({"role": "assistant", "content": None})
        messages.append({"role": "tool", "name": "execute_sql", "content": "rows..."})

    assert messages[:2] == frozen  # byte-identical prefix throughout


def test_empty_inputs_are_noops():
    messages = _zone1()
    assert append_semantic_delta(messages, set(), []) == ([], "")
    assert append_discovery_delta(messages, set(), []) == ([], "")
    assert len(messages) == 2
