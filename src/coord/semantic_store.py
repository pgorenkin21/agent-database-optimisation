"""Thread-safe semantic fact store for P3 token-efficient coordination."""

from __future__ import annotations

import threading
from dataclasses import dataclass
from typing import Any

from src.coord.semantic_extractors import extract_semantic_facts


@dataclass(frozen=True)
class SemanticEntry:
    fact: str
    discovered_by: str
    entry_key: str


@dataclass
class SemanticStoreStats:
    publishes: int = 0
    facts_added: int = 0
    context_injections: int = 0
    injected_chars: int = 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "publishes": self.publishes,
            "facts_added": self.facts_added,
            "context_injections": self.context_injections,
            "injected_chars": self.injected_chars,
        }


class SharedSemanticStore:
    """
    Task-scoped store of distilled explore facts shared across parallel replicas.

    Unlike P2 (syntactic fragments), entries are short natural-language facts
    with a hard cap on injected prompt size.
    """

    def __init__(
        self,
        *,
        max_entries: int = 128,
        max_inject_chars: int = 500,
        max_inject_bullets: int = 8,
    ) -> None:
        if max_entries < 1:
            raise ValueError("max_entries must be >= 1")
        self._max_entries = max_entries
        self._max_inject_chars = max_inject_chars
        self._max_inject_bullets = max_inject_bullets
        self._lock = threading.Lock()
        self._entries: dict[str, SemanticEntry] = {}
        self._agents_per_key: dict[str, set[str]] = {}
        self.stats = SemanticStoreStats()

    def publish(
        self,
        *,
        agent_id: str,
        sql: str,
        rows: list[tuple[Any, ...]] | None,
        error: str | None,
    ) -> int:
        """Record facts from an explore query; return count of newly added keys."""
        raw_facts = extract_semantic_facts(sql=sql, rows=rows, error=error)
        added = 0
        with self._lock:
            for fact in raw_facts:
                key = fact.lower().strip()
                self._agents_per_key.setdefault(key, set()).add(agent_id)
                if key in self._entries:
                    continue
                if len(self._entries) >= self._max_entries:
                    continue
                self._entries[key] = SemanticEntry(
                    fact=fact,
                    discovered_by=agent_id,
                    entry_key=key,
                )
                added += 1
            self.stats.publishes += 1
            self.stats.facts_added += added
        return added

    def peer_facts(self, agent_id: str) -> list[str]:
        """Facts from other replicas, prioritising cross-agent discoveries."""
        with self._lock:
            peer: list[tuple[int, str]] = []
            own: list[str] = []
            for key, entry in self._entries.items():
                agents = self._agents_per_key.get(key, set())
                if agents - {agent_id}:
                    peer.append((len(agents), entry.fact))
                elif agent_id in agents:
                    own.append(entry.fact)
            peer.sort(key=lambda x: (-x[0], x[1]))
            ordered = [fact for _, fact in peer] + own
            return self._truncate(ordered)

    def _truncate(self, facts: list[str]) -> list[str]:
        selected: list[str] = []
        total_chars = 0
        for fact in facts:
            if len(selected) >= self._max_inject_bullets:
                break
            line_len = len(fact) + 2
            if total_chars + line_len > self._max_inject_chars and selected:
                break
            selected.append(fact)
            total_chars += line_len
        return selected

    def unique_fact_count(self) -> int:
        with self._lock:
            return len(self._entries)

    def record_context_injection(self, *, fact_count: int, char_count: int) -> None:
        if fact_count <= 0:
            return
        with self._lock:
            self.stats.context_injections += 1
            self.stats.injected_chars += char_count
