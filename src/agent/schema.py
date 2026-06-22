"""Build schema context for BIRD prompts from SQLite DDL and description CSVs."""

from __future__ import annotations

import csv
import io
import sqlite3
from pathlib import Path

# BIRD database_description CSVs are mostly UTF-8; some use Windows-1252 (e.g. student_club/Budget.csv).
_DESCRIPTION_ENCODINGS = ("utf-8-sig", "utf-8", "cp1252", "latin-1")


def read_text_with_encoding_fallback(path: Path) -> str:
    """Decode a text file, trying common encodings used in BIRD dumps."""
    data = path.read_bytes()
    for encoding in _DESCRIPTION_ENCODINGS:
        try:
            return data.decode(encoding)
        except UnicodeDecodeError:
            continue
    return data.decode("utf-8", errors="replace")


def list_user_tables(db_path: Path) -> list[str]:
    conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    try:
        rows = conn.execute(
            "SELECT name FROM sqlite_master "
            "WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name"
        ).fetchall()
        return [str(r[0]) for r in rows]
    finally:
        conn.close()


def ddl_for_tables(db_path: Path, tables: list[str] | tuple[str, ...]) -> str:
    if not tables:
        return "(no tables found)"
    conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    try:
        parts: list[str] = []
        for table in tables:
            row = conn.execute(
                "SELECT sql FROM sqlite_master WHERE type='table' AND name = ?",
                (table,),
            ).fetchone()
            if row and row[0]:
                parts.append(str(row[0]))
        return "\n\n".join(parts) if parts else "(no tables found)"
    finally:
        conn.close()


def descriptions_for_tables(
    db_id: str,
    databases_dir: Path,
    tables: list[str] | tuple[str, ...],
) -> str:
    if not tables:
        return ""
    desc_dir = databases_dir / db_id / "database_description"
    if not desc_dir.is_dir():
        return ""

    allowed = {str(t).lower() for t in tables}
    sections: list[str] = []
    for csv_path in sorted(desc_dir.glob("*.csv")):
        table = csv_path.stem
        if table.lower() not in allowed:
            continue
        lines = [f"Table `{table}` (column reference):"]
        text = read_text_with_encoding_fallback(csv_path)
        reader = csv.DictReader(io.StringIO(text, newline=""))
        for row in reader:
            col = row.get("column_name") or row.get("original_column_name") or "?"
            orig = row.get("original_column_name", "")
            desc = (row.get("column_description") or "").strip()
            fmt = (row.get("data_format") or "").strip()
            line = f"  - {col}"
            if orig and orig != col:
                line += f" (original: {orig})"
            if fmt:
                line += f" [{fmt}]"
            if desc:
                line += f": {desc}"
            lines.append(line)
        sections.append("\n".join(lines))
    return "\n\n".join(sections)


def build_schema_context(
    db_path: Path,
    databases_dir: Path,
    db_id: str,
    *,
    tables: list[str] | tuple[str, ...] | None = None,
) -> str:
    """Schema text for the agent system prompt."""
    selected = list(tables) if tables is not None else list_user_tables(db_path)
    ddl = ddl_for_tables(db_path, selected)
    descriptions = descriptions_for_tables(db_id, databases_dir, selected)
    parts = ["## SQLite schema (CREATE TABLE)", ddl]
    if descriptions:
        parts.extend(["## Column descriptions", descriptions])
    return "\n\n".join(parts)
