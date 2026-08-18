"""Load and format persistent per-database profiles (DB Profile Card / DPC).

A profile is a precomputed, per-database JSON artifact
(``data/profiles/<db_id>.json``) built offline by ``scripts/build_db_profile.py``.
Unlike the task-scoped P1/P3 caches, it persists across every task on a database
and pre-answers database-level questions (value domains, join keys, row counts,
constraints) so the agent does not re-probe them each task.

This module is consumer-side only: it loads a profile and renders a compact
**DB Profile Card** appended to the static schema prefix (Zone 1), so it rides
the prompt cache and can be filtered to the tables that survive schema pruning.
See ``thesis/chapter12_database_profiles.md`` for the design.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Sequence

PROFILE_CARD_HEADER = "## Database profile (precomputed)"
BUILDER_VERSION = 1


@dataclass(frozen=True)
class ColumnProfile:
    name: str
    type: str
    nullable: bool
    distinct: int | None  # None => not counted (table too large / error)
    samples: tuple[str, ...] = ()

    @classmethod
    def from_dict(cls, name: str, d: dict[str, Any]) -> "ColumnProfile":
        return cls(
            name=name,
            type=str(d.get("type", "")),
            nullable=bool(d.get("nullable", True)),
            distinct=d.get("distinct"),
            samples=tuple(str(s) for s in d.get("samples", ())),
        )

    def to_dict(self) -> dict[str, Any]:
        out: dict[str, Any] = {"type": self.type, "nullable": self.nullable}
        if self.distinct is not None:
            out["distinct"] = self.distinct
        if self.samples:
            out["samples"] = list(self.samples)
        return out


@dataclass(frozen=True)
class TableProfile:
    name: str
    row_count: int | None
    primary_key: tuple[str, ...]
    columns: tuple[ColumnProfile, ...]

    @classmethod
    def from_dict(cls, name: str, d: dict[str, Any]) -> "TableProfile":
        cols = tuple(
            ColumnProfile.from_dict(cname, cd)
            for cname, cd in d.get("columns", {}).items()
        )
        return cls(
            name=name,
            row_count=d.get("row_count"),
            primary_key=tuple(str(p) for p in d.get("primary_key", ())),
            columns=cols,
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "row_count": self.row_count,
            "primary_key": list(self.primary_key),
            "columns": {c.name: c.to_dict() for c in self.columns},
        }


@dataclass(frozen=True)
class JoinEdge:
    display: str  # e.g. "transactions_1k.CardID = customers.CustomerID"
    source: str  # "fk" | "observed"

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "JoinEdge":
        return cls(display=str(d["display"]), source=str(d.get("source", "fk")))

    def to_dict(self) -> dict[str, Any]:
        return {"display": self.display, "source": self.source}


@dataclass(frozen=True)
class DbProfile:
    db_id: str
    tables: tuple[TableProfile, ...] = ()
    joins: tuple[JoinEdge, ...] = ()
    built_at: str = ""
    builder_version: int = BUILDER_VERSION
    meta: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "DbProfile":
        tables = tuple(
            TableProfile.from_dict(tname, td)
            for tname, td in d.get("tables", {}).items()
        )
        joins = tuple(JoinEdge.from_dict(j) for j in d.get("joins", ()))
        return cls(
            db_id=str(d["db_id"]),
            tables=tables,
            joins=joins,
            built_at=str(d.get("built_at", "")),
            builder_version=int(d.get("builder_version", BUILDER_VERSION)),
            meta=dict(d.get("meta", {})),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "db_id": self.db_id,
            "built_at": self.built_at,
            "builder_version": self.builder_version,
            "meta": self.meta,
            "tables": {t.name: t.to_dict() for t in self.tables},
            "joins": [j.to_dict() for j in self.joins],
        }


def profile_path(db_id: str, profiles_dir: Path) -> Path:
    return profiles_dir / f"{db_id}.json"


def load_db_profile(db_id: str, profiles_dir: Path) -> DbProfile | None:
    """Return the profile for ``db_id`` or ``None`` if no artifact exists."""
    path = profile_path(db_id, profiles_dir)
    if not path.is_file():
        return None
    try:
        return DbProfile.from_dict(json.loads(path.read_text(encoding="utf-8")))
    except (json.JSONDecodeError, KeyError, ValueError):
        return None


def _format_column_line(col: ColumnProfile) -> str:
    parts = [col.type or "?"]
    if col.samples:
        parts.append("values {" + ", ".join(col.samples) + "}")
    elif col.distinct is not None:
        parts.append(f"{col.distinct} distinct")
    if not col.nullable:
        parts.append("not null")
    return f"  - {col.name}: {', '.join(parts)}"


def _table_header_line(table: TableProfile) -> str:
    tags: list[str] = []
    if table.row_count is not None:
        tags.append(f"{table.row_count} rows")
    if table.primary_key:
        tags.append(f"pk={','.join(table.primary_key)}")
    return f"{table.name}: {', '.join(tags)}" if tags else table.name


def format_profile_card(
    profile: DbProfile | None,
    *,
    tables: Sequence[str] | None = None,
    char_budget: int = 1500,
) -> str:
    """Render a compact DB Profile Card, or ``""`` when there is nothing to show.

    ``tables`` restricts output to the given tables (e.g. the survivors of schema
    pruning). ``char_budget`` bounds the card. Content is emitted **breadth-first by
    value** so one wide table cannot starve the rest: every table's header plus its
    value-domain (sampled) columns come first, then the join graph, then remaining
    plain columns backfill any leftover budget. A table too wide to list in full is
    truncated, not dropped.
    """
    if profile is None:
        return ""

    keep = {t.lower() for t in tables} if tables is not None else None
    selected = [t for t in profile.tables if keep is None or t.name.lower() in keep]

    join_line = ""
    if profile.joins:
        shown = [
            j.display
            for j in profile.joins
            if keep is None or _join_within(j.display, keep)
        ]
        if shown:
            join_line = f"Joins: {'; '.join(shown)}"

    # Preferred rendering: every table grouped, all columns in schema order, joins
    # last. If it fits the budget we use it verbatim (clean, grouped, common case).
    full: list[str] = [PROFILE_CARD_HEADER]
    for table in selected:
        full.append(_table_header_line(table))
        full.extend(_format_column_line(c) for c in table.columns)
    if join_line:
        full.append(join_line)
    if len(full) == 1:
        return ""
    if len("\n".join(full)) <= char_budget:
        return "\n".join(full)

    # Over budget: degrade breadth-first by value so one wide table can't starve
    # the rest — every table header + its value-domain (sampled) columns, then the
    # join graph. Plain distinct-count columns are dropped rather than detached.
    lines = [PROFILE_CARD_HEADER]
    used = len(PROFILE_CARD_HEADER)

    def _try_add(line: str) -> bool:
        nonlocal used
        cost = len(line) + 1  # newline join
        if used + cost > char_budget:
            return False
        lines.append(line)
        used += cost
        return True

    for table in selected:
        if not _try_add(_table_header_line(table)):
            continue  # header didn't fit; a later, cheaper table still might
        for col in table.columns:
            if col.samples:
                _try_add(_format_column_line(col))
    if join_line:
        _try_add(join_line)

    if len(lines) == 1:  # header only, nothing fit
        return ""
    return "\n".join(lines)


def _join_within(display: str, keep: set[str]) -> bool:
    """True if *every* table a join references is in ``keep``.

    Under schema pruning we only advertise joins whose endpoints are both present
    in the pruned schema; a join to a table whose DDL isn't shown is just noise.
    """
    tables = [
        tok.split(".", 1)[0].strip()
        for tok in display.lower().replace("=", " ").split()
        if "." in tok
    ]
    return bool(tables) and all(t in keep for t in tables)
