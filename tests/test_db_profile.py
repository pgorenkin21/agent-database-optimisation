"""Tests for persistent per-database profiles (Chapter 12).

Covers both the consumer module (``src/agent/db_profile.py``: dataclasses, loader,
card formatter) and the offline builder logic (``scripts/build_db_profile.py``).
The builder is exercised against a small self-contained SQLite fixture — no BIRD
data required — mirroring how ``test_eval_matrix`` imports pure helpers from a script.
"""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path

import pytest

from scripts.build_db_profile import (
    _is_domain_column,
    _observed_joins,
    build_profile,
)
from src.agent.db_profile import (
    ColumnProfile,
    DbProfile,
    JoinEdge,
    TableProfile,
    format_profile_card,
    load_db_profile,
)


@pytest.fixture
def fixture_db(tmp_path: Path) -> Path:
    """A 2-table SQLite DB exercising every sampling rule and a foreign key."""
    db_path = tmp_path / "shop.sqlite"
    conn = sqlite3.connect(db_path)
    conn.executescript(
        """
        CREATE TABLE customers (
            CustomerID INTEGER PRIMARY KEY,
            Segment TEXT,
            Currency TEXT,
            Balance REAL
        );
        CREATE TABLE orders (
            OrderID INTEGER PRIMARY KEY,
            CustomerID INTEGER,
            Status TEXT NOT NULL,
            link_to_customer TEXT,
            FOREIGN KEY (CustomerID) REFERENCES customers(CustomerID)
        );
        """
    )
    conn.executemany(
        "INSERT INTO customers VALUES (?,?,?,?)",
        [
            (1, "SME", "EUR", 10.5),
            (2, "LAM", "CZK", 20.25),
            (3, "KAM", "EUR", 30.0),
            (4, "SME", "CZK", 40.75),
        ],
    )
    conn.executemany(
        "INSERT INTO orders VALUES (?,?,?,?)",
        [
            (1, 1, "open", "cust-1"),
            (2, 2, "closed", "cust-2"),
            (3, 1, "open", "cust-1"),
        ],
    )
    conn.commit()
    conn.close()
    return db_path


# --------------------------------------------------------------------------- #
# Module: dataclasses, loader
# --------------------------------------------------------------------------- #


def test_dataclass_roundtrip() -> None:
    profile = DbProfile(
        db_id="shop",
        tables=(
            TableProfile(
                name="customers",
                row_count=4,
                primary_key=("CustomerID",),
                columns=(
                    ColumnProfile("Segment", "TEXT", True, 3, ("SME", "LAM", "KAM")),
                    ColumnProfile("Balance", "REAL", True, 4),
                ),
            ),
        ),
        joins=(JoinEdge("orders.CustomerID = customers.CustomerID", "fk"),),
    )
    restored = DbProfile.from_dict(profile.to_dict())
    assert restored == profile


def test_load_missing_returns_none(tmp_path: Path) -> None:
    assert load_db_profile("does_not_exist", tmp_path) is None


def test_load_malformed_returns_none(tmp_path: Path) -> None:
    (tmp_path / "broken.json").write_text("{not valid json", encoding="utf-8")
    assert load_db_profile("broken", tmp_path) is None


# --------------------------------------------------------------------------- #
# Module: card formatter
# --------------------------------------------------------------------------- #


def test_format_card_none_is_empty() -> None:
    assert format_profile_card(None) == ""


def _wide_profile() -> DbProfile:
    """One wide table (mostly distinct-only cols) + two small tables."""
    wide_cols = [ColumnProfile("Label", "TEXT", True, 3, ("a", "b", "c"))]
    wide_cols += [
        ColumnProfile(f"c{i}", "TEXT", True, 900) for i in range(30)  # no samples
    ]
    return DbProfile(
        db_id="wide",
        tables=(
            TableProfile("big", 1000, ("id",), tuple(wide_cols)),
            TableProfile("small_b", 5, ("id",), (ColumnProfile("k", "TEXT", True, 2, ("x", "y")),)),
            TableProfile("small_c", 7, ("id",), (ColumnProfile("m", "TEXT", True, 2, ("p", "q")),)),
        ),
        joins=(JoinEdge("small_b.big_id = big.id", "fk"),),
    )


def test_format_card_full_render_keeps_all_columns_when_it_fits() -> None:
    card = format_profile_card(_wide_profile(), char_budget=100_000)
    # Grouped render shows every column, including distinct-only ones.
    assert "c17: TEXT, 900 distinct" in card
    assert "small_c" in card


def test_format_card_degrades_breadth_first_over_budget() -> None:
    """Regression guard: a wide first table must not starve later tables.

    Under budget pressure the card drops distinct-only columns but must still show
    every table header + its value-domain (sampled) columns."""
    card = format_profile_card(_wide_profile(), char_budget=400)
    assert len(card) <= 400
    assert "big:" in card and "small_b:" in card and "small_c:" in card  # breadth kept
    assert "Label: TEXT, values {a, b, c}" in card  # value domain kept
    assert "900 distinct" not in card  # distinct-only columns dropped under pressure


def test_format_card_filters_to_kept_tables() -> None:
    profile = _wide_profile()
    card = format_profile_card(profile, tables=["small_b"], char_budget=100_000)
    assert "small_b:" in card
    assert "big:" not in card and "small_c:" not in card


def test_format_card_join_needs_both_endpoints_kept() -> None:
    profile = DbProfile(
        db_id="j",
        tables=(
            TableProfile("a", 1, (), (ColumnProfile("x", "TEXT", True, 2, ("p", "q")),)),
            TableProfile("b", 1, (), (ColumnProfile("y", "TEXT", True, 2, ("p", "q")),)),
        ),
        joins=(JoinEdge("a.id = b.id", "fk"),),
    )
    # Both kept -> join shown.
    assert "Joins: a.id = b.id" in format_profile_card(profile, tables=["a", "b"])
    # Only one endpoint kept -> join suppressed (b's DDL isn't in the pruned prompt).
    assert "Joins" not in format_profile_card(profile, tables=["a"])


# --------------------------------------------------------------------------- #
# Builder: sampling rules
# --------------------------------------------------------------------------- #


def test_is_domain_column_predicate() -> None:
    assert _is_domain_column("Segment", "TEXT", is_pk=False, is_fk=False)
    assert not _is_domain_column("CustomerID", "INTEGER", is_pk=False, is_fk=False)  # *id
    assert not _is_domain_column("link_to_customer", "TEXT", is_pk=False, is_fk=False)
    assert not _is_domain_column("Balance", "REAL", is_pk=False, is_fk=False)  # float
    assert not _is_domain_column("Segment", "TEXT", is_pk=True, is_fk=False)  # pk
    assert not _is_domain_column("Segment", "TEXT", is_pk=False, is_fk=True)  # fk


def _table(profile: DbProfile, name: str) -> TableProfile:
    return next(t for t in profile.tables if t.name == name)


def _col(table: TableProfile, name: str) -> ColumnProfile:
    return next(c for c in table.columns if c.name == name)


def test_build_profile_samples_categorical_only(fixture_db: Path) -> None:
    profile = build_profile("shop", fixture_db, gold_sqls=[], include_observed_joins=False)
    customers = _table(profile, "customers")

    # Low-cardinality categorical labels get value domains.
    assert set(_col(customers, "Segment").samples) == {"SME", "LAM", "KAM"}
    assert set(_col(customers, "Currency").samples) == {"EUR", "CZK"}
    # Distinct counts are correct.
    assert _col(customers, "Segment").distinct == 3
    assert _col(customers, "Currency").distinct == 2

    # Identifiers, floats, foreign keys, and link_to_* columns are NOT sampled.
    assert _col(customers, "CustomerID").samples == ()  # pk
    assert _col(customers, "Balance").samples == ()  # REAL
    orders = _table(profile, "orders")
    assert _col(orders, "CustomerID").samples == ()  # fk column
    assert _col(orders, "link_to_customer").samples == ()  # link_to_ prefix


def test_build_profile_row_count_pk_and_nullability(fixture_db: Path) -> None:
    profile = build_profile("shop", fixture_db, gold_sqls=[], include_observed_joins=False)
    customers = _table(profile, "customers")
    orders = _table(profile, "orders")
    assert customers.row_count == 4
    assert orders.row_count == 3
    assert customers.primary_key == ("CustomerID",)
    assert _col(orders, "Status").nullable is False  # NOT NULL
    assert _col(customers, "Segment").nullable is True


def test_build_profile_fk_join(fixture_db: Path) -> None:
    profile = build_profile("shop", fixture_db, gold_sqls=[], include_observed_joins=False)
    fk = [j for j in profile.joins if j.source == "fk"]
    assert any(
        "orders.CustomerID" in j.display and "customers.CustomerID" in j.display
        for j in fk
    )


# --------------------------------------------------------------------------- #
# Builder: observed joins (separate ablation)
# --------------------------------------------------------------------------- #


def test_observed_joins_extracted_and_deduped() -> None:
    gold = ["SELECT * FROM orders o JOIN customers c ON o.CustomerID = c.CustomerID"]
    edges = _observed_joins(gold, fk_displays=set())
    assert edges, "expected an observed join from the gold SQL"
    assert all(e.source == "observed" for e in edges)
    # An observed edge already present as a declared FK is not duplicated.
    display = edges[0].display
    assert _observed_joins(gold, fk_displays={display}) == []


def test_build_profile_include_observed_joins_flag(fixture_db: Path) -> None:
    gold = ["SELECT * FROM orders o JOIN customers c ON o.CustomerID = c.CustomerID"]
    off = build_profile("shop", fixture_db, gold_sqls=gold, include_observed_joins=False)
    on = build_profile("shop", fixture_db, gold_sqls=gold, include_observed_joins=True)
    assert not any(j.source == "observed" for j in off.joins)
    assert any(j.source == "observed" for j in on.joins)


# --------------------------------------------------------------------------- #
# End-to-end: build -> persist -> load -> render
# --------------------------------------------------------------------------- #


def test_build_persist_load_render(fixture_db: Path, tmp_path: Path) -> None:
    profile = build_profile("shop", fixture_db, gold_sqls=[], include_observed_joins=False)
    out = tmp_path / "shop.json"
    out.write_text(json.dumps(profile.to_dict(), indent=2), encoding="utf-8")

    loaded = load_db_profile("shop", tmp_path)
    assert loaded is not None
    card = format_profile_card(loaded, char_budget=1500)
    assert card.startswith("## Database profile (precomputed)")
    assert "Segment: TEXT, values {" in card
    assert "customers: 4 rows, pk=CustomerID" in card
