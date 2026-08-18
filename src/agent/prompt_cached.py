"""Append-only shared-context injection for prompt caching.

New-file version of the prompt mutators in ``src/agent/prompt.py``. The
originals (`apply_discovery_context` / `apply_semantic_context`) filter the
previous shared-context block out of the *middle* of the message list and
re-append a fresh one every turn. That shifts every message after the schema
and prevents provider prefix-caching from covering the conversation history.

These helpers instead **append only the new items** (a delta) at the tail and
never touch the interior, so the cached prefix stays byte-stable and grows
monotonically. The Zone-1 builders are re-exported unchanged from ``prompt``.
"""

from __future__ import annotations

from typing import Any

# Re-export the unchanged Zone-1 (static prefix) builders so callers have a
# single import surface.
from src.agent.prompt import (  # noqa: F401
    DISCOVERY_CONTEXT_PREFIX,
    SEMANTIC_CONTEXT_PREFIX,
    SYSTEM_TEMPLATE,
    build_initial_messages,
    build_task_user_message,
    format_discovery_context,
    format_semantic_context,
)


def _semantic_key(fact: str) -> str:
    """Identity used to dedupe facts across turns (matches the store's key)."""
    return fact.lower().strip()


def append_semantic_delta(
    messages: list[dict[str, Any]],
    shown_keys: set[str],
    facts: list[str],
) -> tuple[list[str], str]:
    """
    Append only facts not shown before, as a single trailing user message.

    Returns ``(new_facts, block_text)``; both empty when there is nothing new.
    Never edits or removes existing messages (append-only ⇒ prefix-stable).
    """
    new = [f for f in facts if _semantic_key(f) not in shown_keys]
    if not new:
        return [], ""
    block = format_semantic_context(new)
    if not block.strip():
        return [], ""
    for f in new:
        shown_keys.add(_semantic_key(f))
    messages.append({"role": "user", "content": block})
    return new, block


def append_discovery_delta(
    messages: list[dict[str, Any]],
    shown_fragments: set[str],
    fragments: list[str],
) -> tuple[list[str], str]:
    """
    Append only peer fragments not shown before, as one trailing user message.

    Returns ``(new_fragments, block_text)``; both empty when nothing is new.
    Append-only, so the cacheable prefix is never disturbed.
    """
    new = [fr for fr in fragments if fr not in shown_fragments]
    if not new:
        return [], ""
    block = format_discovery_context(new)
    if not block.strip():
        return [], ""
    shown_fragments.update(new)
    messages.append({"role": "user", "content": block})
    return new, block
