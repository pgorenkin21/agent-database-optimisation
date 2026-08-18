"""P4 — structural explore suppression (Chapter 13).

Task-scoped, thread-safe layer that intercepts a redundant *explore* query before
it hits SQLite and returns the already-distilled facts from an equivalent prior
probe, instead of re-running the round-trip. It is the enforcing sibling of P2/P3:
where those *inject advice* the agent may ignore, this *skips the probe*.

Correctness is everything here — a wrongly suppressed probe withholds data the
agent needed and can drop EX. So suppression is deliberately conservative:

* It fires only on a **structural match**: two probes with the *same* probe
  signature (tables, columns, predicates, joins **and aggregate kinds**) that are
  **not** byte-identical after AST normalisation (exact repeats are P1's job and
  return real rows). Aggregate kind is part of the signature so ``AVG(x)`` and
  ``MAX(x)`` over the same column never collide.
* It only ever returns a **fact string**, never result rows.
* It only stores facts from probes that ran clean and returned rows.
* A per-task cap bounds how many suppressions can happen, so a bad match cannot
  starve an agent of real data.
* ``submit_sql`` is never routed here — the loop only consults it for explores.
"""

from __future__ import annotations

import threading
from dataclasses import dataclass, field
from typing import Any

import sqlglot
from sqlglot import exp

from src.coord.semantic_extractors import extract_semantic_facts
from src.db.sql_fragments import extract_sql_fragments
from src.db.sql_normalize import normalize_sql_ast

_AGG_NODES = (exp.Avg, exp.Max, exp.Min, exp.Sum, exp.Count)


def probe_signature(sql: str) -> frozenset[str] | None:
    """Structural signature: fragments + aggregate kinds. ``None`` if unparseable.

    Two explores with the same signature ask the same question of the same columns
    with the same filters — differing only in surface form (whitespace, clause
    order, ``DISTINCT`` vs ``GROUP BY``). Aggregate kind is included so that
    ``AVG``/``MAX``/``MIN``/``SUM``/``COUNT`` over identical columns do **not** match.

    Conservative on aliasing: a qualified column ref (``o.status``) and its
    unqualified form (``status``) yield different fragments and so do **not** match.
    That under-suppresses (a missed catch) rather than risking a wrong one — flatly
    unqualifying would let ``a.id`` and ``b.id`` collide in a join. Catch rate is
    measured in Chapter 13; alias-heavy misses are a candidate for the embedding stage.
    """
    frags = extract_sql_fragments(sql)
    if not frags:
        return None
    try:
        tree = sqlglot.parse_one(sql.strip(), read="sqlite")
    except Exception:
        return None
    if tree is None:
        return None
    aggs = {
        f"agg:{type(node).__name__.lower()}"
        for node in tree.walk()
        if isinstance(node, _AGG_NODES)
    }
    return frozenset(frags | aggs)


@dataclass(frozen=True)
class _Probe:
    ast: str
    signature: frozenset[str]
    facts: tuple[str, ...]
    sql: str


@dataclass(frozen=True)
class SuppressionHit:
    facts: tuple[str, ...]
    matched_sql: str


@dataclass
class SuppressorStats:
    probes_recorded: int = 0
    suppressions: int = 0
    cap_rejections: int = 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "probes_recorded": self.probes_recorded,
            "suppressions": self.suppressions,
            "cap_rejections": self.cap_rejections,
        }


class StructuralExploreSuppressor:
    """Task-scoped structural suppressor shared across a task's parallel replicas."""

    def __init__(self, *, max_suppressions: int = 64) -> None:
        if max_suppressions < 0:
            raise ValueError("max_suppressions must be >= 0")
        self._max_suppressions = max_suppressions
        self._lock = threading.Lock()
        self._by_ast: set[str] = set()
        self._probes: list[_Probe] = []
        self.stats = SuppressorStats()

    def consult(self, sql: str) -> SuppressionHit | None:
        """Return a hit iff ``sql`` structurally matches a prior, non-identical probe.

        Exact (AST-identical) repeats return ``None`` so they fall through to the
        normal execute path (P1 serves real rows there). The per-task cap is charged
        only on an actual suppression.
        """
        sig = probe_signature(sql)
        if sig is None:
            return None
        ast = normalize_sql_ast(sql)
        with self._lock:
            if ast in self._by_ast:
                return None  # exact known probe -> defer to P1 / re-execution
            for probe in self._probes:
                if probe.signature == sig:
                    if self.stats.suppressions >= self._max_suppressions:
                        self.stats.cap_rejections += 1
                        return None
                    self.stats.suppressions += 1
                    return SuppressionHit(facts=probe.facts, matched_sql=probe.sql)
        return None

    def record(
        self,
        *,
        sql: str,
        rows: list[tuple[Any, ...]] | None,
        error: str | None,
    ) -> bool:
        """Store a clean, non-empty probe's signature + distilled facts.

        Returns ``True`` if newly recorded. Errored or empty probes are ignored —
        the suppressor only ever hands back facts that were actually observed.
        """
        if error or not rows:
            return False
        sig = probe_signature(sql)
        if sig is None:
            return False
        ast = normalize_sql_ast(sql)
        facts = extract_semantic_facts(sql=sql, rows=rows, error=None)
        if not facts:
            return False
        with self._lock:
            if ast in self._by_ast:
                return False
            self._by_ast.add(ast)
            self._probes.append(
                _Probe(ast=ast, signature=sig, facts=tuple(facts), sql=sql)
            )
            self.stats.probes_recorded += 1
        return True

    @staticmethod
    def format_suppressed_feedback(hit: SuppressionHit) -> str:
        """Tool-result text for a suppressed probe — facts only, clearly marked."""
        lines = [
            "[suppressed] This probe matches one already run on this task; "
            "reuse the known result instead of re-querying:",
        ]
        lines.extend(f"- {f}" for f in hit.facts)
        return "\n".join(lines)
