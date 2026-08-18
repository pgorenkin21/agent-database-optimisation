"""Tests for P4 structural explore suppression (Chapter 13).

The equivalence relation is the EX-critical piece, so the paraphrase-catch and the
false-positive guards (aggregates, differing predicates, exact repeats) are tested
explicitly.
"""

from __future__ import annotations

from src.coord.explore_suppressor import (
    StructuralExploreSuppressor,
    probe_signature,
)


# --------------------------------------------------------------------------- #
# probe_signature
# --------------------------------------------------------------------------- #


def test_signature_equates_distinct_and_group_by() -> None:
    a = probe_signature("SELECT DISTINCT status FROM orders")
    b = probe_signature("SELECT status FROM orders GROUP BY status")
    assert a is not None and a == b


def test_signature_ignores_whitespace_and_case() -> None:
    a = probe_signature("SELECT status FROM orders")
    b = probe_signature("select   status   from   ORDERS")
    assert a == b


def test_signature_conservative_on_alias() -> None:
    """Qualified vs unqualified columns do NOT match (safe under-suppression)."""
    a = probe_signature("SELECT status FROM orders")
    b = probe_signature("SELECT o.status FROM orders o")
    assert a != b


def test_signature_distinguishes_aggregate_kind() -> None:
    """The EX-critical guard: AVG and MAX over the same column must NOT match."""
    avg = probe_signature("SELECT AVG(score) FROM t")
    mx = probe_signature("SELECT MAX(score) FROM t")
    assert avg is not None and mx is not None and avg != mx


def test_signature_distinguishes_predicate() -> None:
    a = probe_signature("SELECT id FROM orders WHERE status = 'open'")
    b = probe_signature("SELECT id FROM orders WHERE status = 'closed'")
    assert a != b


def test_signature_none_when_no_fragments() -> None:
    assert probe_signature("") is None
    assert probe_signature("   ") is None


# --------------------------------------------------------------------------- #
# consult / record
# --------------------------------------------------------------------------- #


def _record(sup: StructuralExploreSuppressor, sql: str, rows: list) -> bool:
    return sup.record(sql=sql, rows=rows, error=None)


def test_paraphrase_is_suppressed_with_facts() -> None:
    sup = StructuralExploreSuppressor()
    assert _record(sup, "SELECT status FROM orders", [("open",), ("closed",)])
    hit = sup.consult("SELECT status FROM orders GROUP BY status")
    assert hit is not None
    assert hit.facts  # returns the prior probe's distilled facts, not rows
    assert sup.stats.suppressions == 1


def test_exact_repeat_defers_to_p1() -> None:
    sup = StructuralExploreSuppressor()
    _record(sup, "SELECT status FROM orders", [("open",)])
    # identical (and whitespace variant) normalise to the same AST -> not suppressed
    assert sup.consult("SELECT status FROM orders") is None
    assert sup.consult("SELECT   status   FROM orders") is None
    assert sup.stats.suppressions == 0


def test_aggregate_collision_is_not_suppressed() -> None:
    sup = StructuralExploreSuppressor()
    _record(sup, "SELECT AVG(score) FROM t", [(5.0,)])
    assert sup.consult("SELECT MAX(score) FROM t") is None  # different number!
    assert sup.stats.suppressions == 0


def test_different_predicate_is_not_suppressed() -> None:
    sup = StructuralExploreSuppressor()
    _record(sup, "SELECT id FROM orders WHERE status = 'open'", [(1,)])
    assert sup.consult("SELECT id FROM orders WHERE status = 'closed'") is None


def test_errored_or_empty_probes_are_not_recorded() -> None:
    sup = StructuralExploreSuppressor()
    assert not sup.record(sql="SELECT x FROM t", rows=None, error="no such column")
    assert not sup.record(sql="SELECT x FROM t", rows=[], error=None)
    assert sup.consult("SELECT x FROM t GROUP BY x") is None
    assert sup.stats.probes_recorded == 0


def test_per_task_cap_limits_suppressions() -> None:
    sup = StructuralExploreSuppressor(max_suppressions=1)
    _record(sup, "SELECT status FROM orders", [("open",), ("closed",)])
    assert sup.consult("SELECT status FROM orders GROUP BY status") is not None
    # cap reached: further structural matches fall through to real execution
    assert sup.consult("SELECT DISTINCT status FROM orders") is None
    assert sup.stats.suppressions == 1
    assert sup.stats.cap_rejections == 1


def test_suppressed_feedback_is_facts_only() -> None:
    sup = StructuralExploreSuppressor()
    _record(sup, "SELECT status FROM orders", [("open",), ("closed",)])
    hit = sup.consult("SELECT status FROM orders GROUP BY status")
    assert hit is not None
    text = StructuralExploreSuppressor.format_suppressed_feedback(hit)
    assert text.startswith("[suppressed]")
    assert "reuse the known result" in text
