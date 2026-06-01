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


def _ddl_from_sqlite(db_path: Path) -> str:
    conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    try:
        rows = conn.execute(
            "SELECT sql FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name"
        ).fetchall()
        parts = [r[0] for r in rows if r[0]]
        return "\n\n".join(parts) if parts else "(no tables found)"
    finally:
        conn.close()


def _descriptions_from_csv(db_id: str, databases_dir: Path) -> str:
    desc_dir = databases_dir / db_id / "database_description"
    if not desc_dir.is_dir():
        return ""

    sections: list[str] = []
    for csv_path in sorted(desc_dir.glob("*.csv")):
        table = csv_path.stem
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


def build_schema_context(db_path: Path, databases_dir: Path, db_id: str) -> str:
    """Schema text for the agent system prompt."""
    ddl = _ddl_from_sqlite(db_path)
    descriptions = _descriptions_from_csv(db_id, databases_dir)
    parts = ["## SQLite schema (CREATE TABLE)", ddl]
    if descriptions:
        parts.extend(["## Column descriptions", descriptions])
    return "\n\n".join(parts)
