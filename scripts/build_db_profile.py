#!/usr/bin/env python3
"""Build persistent per-database profiles (DB Profile Cards) — offline, no API cost.

For each BIRD ``db_id`` this makes one read-only pass over the SQLite file and
writes ``data/profiles/<db_id>.json``: column types/nullability/distinct counts,
low-cardinality value domains, row counts, primary keys, and a join graph seeded
from declared foreign keys (and, optionally, join conditions observed in prior-task
gold SQL). See ``thesis/chapter12_database_profiles.md`` §12.2.

Everything here is derivable with extractors already in the repo; no LLM calls.

Examples::

    uv run python scripts/build_db_profile.py                    # all 11 databases
    uv run python scripts/build_db_profile.py --db-id financial  # one database
    uv run python scripts/build_db_profile.py --include-observed-joins
"""

from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from src.agent.db_profile import (  # noqa: E402
    BUILDER_VERSION,
    ColumnProfile,
    DbProfile,
    JoinEdge,
    TableProfile,
    profile_path,
)
from src.agent.schema import list_user_tables  # noqa: E402
from src.bird.tasks import load_tasks, resolve_sqlite_path  # noqa: E402
from src.config import load_config  # noqa: E402
from src.coord.semantic_extractors import _join_hints_from_sql, _stringify  # noqa: E402

# Bounds reuse the P3 conventions (semantic_extractors): keep the card small.
_MAX_DISTINCT_FOR_SAMPLES = 25  # only sample value domains for low-cardinality columns
_MAX_SAMPLES = 10  # sampled distinct values per column
_MAX_ROWS_FOR_DISTINCT = 500_000  # skip COUNT(DISTINCT) on very large tables

# Value domains are useful for categorical *labels*, not identifiers or real-valued
# measures. Sampling opaque keys (BIRD's `link_to_*`, `*_id`) or floats wastes the
# card's character budget on values the agent can't act on.
_IDENTIFIER_TYPES = frozenset({"real", "float", "double", "numeric", "decimal"})


def _is_domain_column(name: str, ctype: str, *, is_pk: bool, is_fk: bool) -> bool:
    low = name.lower()
    if is_pk or is_fk:
        return False
    if low.endswith("id") or low.startswith("link_to"):
        return False
    if ctype.strip().lower() in _IDENTIFIER_TYPES:
        return False
    return True


def _quote(identifier: str) -> str:
    return '"' + identifier.replace('"', '""') + '"'


def _row_count(conn: sqlite3.Connection, table: str) -> int | None:
    try:
        row = conn.execute(f"SELECT COUNT(*) FROM {_quote(table)}").fetchone()
        return int(row[0]) if row else None
    except sqlite3.Error:
        return None


def _distinct_count(conn: sqlite3.Connection, table: str, col: str) -> int | None:
    try:
        row = conn.execute(
            f"SELECT COUNT(DISTINCT {_quote(col)}) FROM {_quote(table)}"
        ).fetchone()
        return int(row[0]) if row else None
    except sqlite3.Error:
        return None


def _sample_values(conn: sqlite3.Connection, table: str, col: str) -> tuple[str, ...]:
    try:
        rows = conn.execute(
            f"SELECT DISTINCT {_quote(col)} FROM {_quote(table)} "
            f"WHERE {_quote(col)} IS NOT NULL LIMIT {_MAX_SAMPLES}"
        ).fetchall()
    except sqlite3.Error:
        return ()
    return tuple(_stringify(r[0]) for r in rows)


def _build_table_profile(conn: sqlite3.Connection, table: str) -> TableProfile:
    info = conn.execute(f"PRAGMA table_info({_quote(table)})").fetchall()
    # PRAGMA table_info columns: (cid, name, type, notnull, dflt_value, pk)
    row_count = _row_count(conn, table)
    count_distinct = row_count is None or row_count <= _MAX_ROWS_FOR_DISTINCT

    try:
        fk_cols = {
            str(r[3]).lower()
            for r in conn.execute(f"PRAGMA foreign_key_list({_quote(table)})").fetchall()
        }
    except sqlite3.Error:
        fk_cols = set()

    pk = [str(r[1]) for r in sorted(info, key=lambda r: r[5]) if r[5]]
    pk_set = {p.lower() for p in pk}
    columns: list[ColumnProfile] = []
    for _cid, name, ctype, notnull, _dflt, _pk in info:
        name = str(name)
        ctype = str(ctype or "")
        distinct = _distinct_count(conn, table, name) if count_distinct else None
        samples: tuple[str, ...] = ()
        if (
            distinct is not None
            and 1 < distinct <= _MAX_DISTINCT_FOR_SAMPLES
            and _is_domain_column(
                name,
                ctype,
                is_pk=name.lower() in pk_set,
                is_fk=name.lower() in fk_cols,
            )
        ):
            samples = _sample_values(conn, table, name)
        columns.append(
            ColumnProfile(
                name=name,
                type=ctype,
                nullable=not bool(notnull),
                distinct=distinct,
                samples=samples,
            )
        )
    return TableProfile(
        name=table,
        row_count=row_count,
        primary_key=tuple(pk),
        columns=tuple(columns),
    )


def _fk_joins(conn: sqlite3.Connection, tables: list[str]) -> list[JoinEdge]:
    edges: list[JoinEdge] = []
    seen: set[str] = set()
    for table in tables:
        try:
            fks = conn.execute(
                f"PRAGMA foreign_key_list({_quote(table)})"
            ).fetchall()
        except sqlite3.Error:
            continue
        # PRAGMA foreign_key_list columns: (id, seq, table, from, to, ...)
        for row in fks:
            ref_table, from_col, to_col = str(row[2]), str(row[3]), row[4]
            to_col = str(to_col) if to_col is not None else ""
            rhs = f"{ref_table}.{to_col}" if to_col else ref_table
            display = f"{table}.{from_col} = {rhs}"
            if display not in seen:
                seen.add(display)
                edges.append(JoinEdge(display=display, source="fk"))
    return edges


def _observed_joins(
    gold_sqls: list[str], fk_displays: set[str]
) -> list[JoinEdge]:
    edges: list[JoinEdge] = []
    seen: set[str] = set()
    for sql in gold_sqls:
        for hint in _join_hints_from_sql(sql):
            display = hint.strip()
            key = display.lower()
            if not display or key in seen or display in fk_displays:
                continue
            seen.add(key)
            edges.append(JoinEdge(display=display, source="observed"))
    return edges


def build_profile(
    db_id: str,
    db_path: Path,
    *,
    gold_sqls: list[str],
    include_observed_joins: bool,
) -> DbProfile:
    conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    try:
        tables = list_user_tables(db_path)
        table_profiles = tuple(_build_table_profile(conn, t) for t in tables)
        joins = _fk_joins(conn, tables)
        n_observed = 0
        if include_observed_joins:
            fk_displays = {e.display for e in joins}
            observed = _observed_joins(gold_sqls, fk_displays)
            n_observed = len(observed)
            joins = joins + observed
    finally:
        conn.close()

    return DbProfile(
        db_id=db_id,
        tables=table_profiles,
        joins=tuple(joins),
        built_at=datetime.now(timezone.utc).isoformat(timespec="seconds"),
        builder_version=BUILDER_VERSION,
        meta={
            "tables": len(table_profiles),
            "columns": sum(len(t.columns) for t in table_profiles),
            "sampled_columns": sum(
                1 for t in table_profiles for c in t.columns if c.samples
            ),
            "fk_joins": sum(1 for j in joins if j.source == "fk"),
            "observed_joins": n_observed,
        },
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=None)
    parser.add_argument("--db-id", type=str, default=None, help="Build one database only")
    parser.add_argument(
        "--include-observed-joins",
        action="store_true",
        help="Seed the join graph from join conditions in prior-task gold SQL "
        "(separate ablation; touches gold metadata).",
    )
    parser.add_argument(
        "--out-dir",
        type=Path,
        default=None,
        help="Override output dir (default: cfg.profiles_dir or data/profiles).",
    )
    parser.add_argument("--force", action="store_true", help="Overwrite existing profiles")
    args = parser.parse_args()

    cfg = load_config(args.config)
    out_dir = args.out_dir or (
        cfg.repo_root / cfg.raw.get("profiles_dir", "data/profiles")
    )
    out_dir.mkdir(parents=True, exist_ok=True)

    def _rel(path: Path) -> str:
        try:
            return str(path.relative_to(cfg.repo_root))
        except ValueError:
            return str(path)

    tasks = load_tasks(cfg)
    gold_by_db: dict[str, list[str]] = {}
    for t in tasks:
        gold_by_db.setdefault(t.db_id, []).append(t.gold_sql)

    db_ids = [args.db_id] if args.db_id else sorted(gold_by_db)
    written = 0
    for db_id in db_ids:
        out_path = profile_path(db_id, out_dir)
        if out_path.exists() and not args.force:
            print(f"skip   {db_id}: exists (use --force)")
            continue
        try:
            db_path = resolve_sqlite_path(cfg.databases_dir, db_id)
        except FileNotFoundError as e:
            print(f"ERROR  {db_id}: {e}", file=sys.stderr)
            continue
        profile = build_profile(
            db_id,
            db_path,
            gold_sqls=gold_by_db.get(db_id, []),
            include_observed_joins=args.include_observed_joins,
        )
        out_path.write_text(
            json.dumps(profile.to_dict(), indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
        m = profile.meta
        print(
            f"wrote  {db_id}: {m['tables']} tables, {m['columns']} cols, "
            f"{m['sampled_columns']} sampled, "
            f"{m['fk_joins']} fk + {m['observed_joins']} observed joins "
            f"-> {_rel(out_path)}"
        )
        written += 1

    print(f"\nDone: {written} profile(s) written to {_rel(out_dir)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
