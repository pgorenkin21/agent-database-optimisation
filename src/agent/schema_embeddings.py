"""TF-IDF table–query similarity for semantic schema pruning."""

from __future__ import annotations

import csv
import io
import math
import re
from collections import Counter
from pathlib import Path

from src.agent.schema import read_text_with_encoding_fallback

_TOKEN_RE = re.compile(r"[a-z_][a-z0-9_]*", re.IGNORECASE)


def tokenize(text: str) -> list[str]:
    return [t.lower() for t in _TOKEN_RE.findall(text.lower())]


def table_profile_text(
    db_id: str,
    databases_dir: Path,
    table: str,
    *,
    columns: list[str] | None = None,
) -> str:
    """Build a searchable document for one table (name, columns, BIRD descriptions)."""
    parts = [table.replace("_", " "), table]
    if columns:
        parts.extend(columns)
        parts.extend(c.replace("_", " ") for c in columns)

    desc_dir = databases_dir / db_id / "database_description"
    csv_path = desc_dir / f"{table}.csv"
    if csv_path.is_file():
        text = read_text_with_encoding_fallback(csv_path)
        reader = csv.DictReader(io.StringIO(text, newline=""))
        for row in reader:
            col = row.get("column_name") or row.get("original_column_name") or ""
            desc = (row.get("column_description") or "").strip()
            fmt = (row.get("data_format") or "").strip()
            if col:
                parts.append(str(col))
                parts.append(str(col).replace("_", " "))
            if desc:
                parts.append(desc)
            if fmt:
                parts.append(fmt)
    return " ".join(parts)


def _tfidf_vectors(documents: list[list[str]]) -> list[dict[str, float]]:
    if not documents:
        return []
    df: Counter[str] = Counter()
    doc_freqs: list[Counter[str]] = []
    for tokens in documents:
        counts = Counter(tokens)
        doc_freqs.append(counts)
        for term in counts:
            df[term] += 1
    n_docs = len(documents)
    vectors: list[dict[str, float]] = []
    for counts in doc_freqs:
        vec: dict[str, float] = {}
        norm_sq = 0.0
        for term, tf in counts.items():
            idf = math.log((1 + n_docs) / (1 + df[term])) + 1.0
            weight = (1.0 + math.log(tf)) * idf
            vec[term] = weight
            norm_sq += weight * weight
        norm = math.sqrt(norm_sq) if norm_sq else 1.0
        vectors.append({term: w / norm for term, w in vec.items()})
    return vectors


def _cosine_sparse(a: dict[str, float], b: dict[str, float]) -> float:
    if not a or not b:
        return 0.0
    if len(a) > len(b):
        a, b = b, a
    return sum(weight * b.get(term, 0.0) for term, weight in a.items())


def score_tables_semantic(
    query_text: str,
    table_documents: dict[str, str],
) -> dict[str, float]:
    """
    Cosine similarity between query TF-IDF vector and each table profile.

    Returns scores in [0, 1] (higher = more relevant).
    """
    if not table_documents:
        return {}
    tables = sorted(table_documents)
    query_tokens = tokenize(query_text)
    docs = [query_tokens] + [tokenize(table_documents[t]) for t in tables]
    vectors = _tfidf_vectors(docs)
    query_vec = vectors[0]
    scores: dict[str, float] = {}
    for table, table_vec in zip(tables, vectors[1:], strict=True):
        scores[table] = _cosine_sparse(query_vec, table_vec)
    return scores


def normalize_scores(scores: dict[str, float]) -> dict[str, float]:
    if not scores:
        return {}
    max_score = max(scores.values())
    if max_score <= 0:
        return {k: 0.0 for k in scores}
    return {k: v / max_score for k, v in scores.items()}
