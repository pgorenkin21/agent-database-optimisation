"""Thread-safe shared discovery board for P2 sub-expression propagation."""

from __future__ import annotations

import threading
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Any

from src.db.sql_fragments import extract_sql_fragments


@dataclass
class FragmentRecord:
    fragment: str
    discovered_by: str
    row_count: int = 0
    had_error: bool = False


@dataclass
class DiscoveryStats:
    publishes: int = 0
    fragments_added: int = 0
    context_injections: int = 0

    @property
    def unique_fragments(self) -> int:
        return self.fragments_added

    def to_dict(self) -> dict[str, Any]:
        return {
            "publishes": self.publishes,
            "fragments_added": self.fragments_added,
            "context_injections": self.context_injections,
        }


class SharedDiscoveryBoard:
    """
    Collect sqlglot fragments from explore SQL across parallel replicas.

    Peers read aggregated discoveries via ``peer_fragments`` for prompt injection.
    """

    def __init__(self, *, max_fragments: int = 256) -> None:
        if max_fragments < 1:
            raise ValueError("max_fragments must be >= 1")
        self._max_fragments = max_fragments
        self._lock = threading.Lock()
        self._records: dict[str, FragmentRecord] = {}
        self._agents_per_fragment: dict[str, set[str]] = defaultdict(set)
        self.stats = DiscoveryStats()

    def publish(
        self,
        *,
        agent_id: str,
        sql: str,
        row_count: int = 0,
        error: str | None = None,
    ) -> int:
        """Record fragments from an explore query; return count of newly added keys."""
        fragments = extract_sql_fragments(sql)
        added = 0
        with self._lock:
            for frag in fragments:
                self._agents_per_fragment[frag].add(agent_id)
                if frag in self._records:
                    continue
                if len(self._records) >= self._max_fragments:
                    continue
                self._records[frag] = FragmentRecord(
                    fragment=frag,
                    discovered_by=agent_id,
                    row_count=row_count,
                    had_error=error is not None,
                )
                added += 1
            self.stats.publishes += 1
            self.stats.fragments_added += added
        return added

    def peer_fragments(self, agent_id: str) -> list[str]:
        """Fragments published by at least one replica other than ``agent_id``."""
        with self._lock:
            return sorted(
                frag
                for frag, agents in self._agents_per_fragment.items()
                if agents - {agent_id}
            )

    def unique_fragment_count(self) -> int:
        with self._lock:
            return len(self._records)

    def record_context_injection(self, *, fragment_count: int) -> None:
        if fragment_count <= 0:
            return
        with self._lock:
            self.stats.context_injections += 1
