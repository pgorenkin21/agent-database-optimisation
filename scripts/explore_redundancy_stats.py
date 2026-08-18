#!/usr/bin/env python3
"""Duplicated exploratory SQL in the P0 baselines, in absolute terms.

The redundancy figure plots a percentage. A percentage does not tell you whether
the agents are repeating two statements or two hundred, so this counts the
underlying statements: how many explore queries the replicas issue, how many
distinct statements those reduce to, and how hard the most-repeated one is hit.

Two notions of "the same query" are reported, because they disagree and the gap
is itself informative:

  string  the statement after whitespace and case normalisation, which is what
          `explore_redundancy_pct` in the batch summaries uses and therefore
          what §3.3 of the paper quotes.
  AST     the statement after parsing and re-serialising, which additionally
          collapses formatting and alias differences. Always at least as
          aggressive as the string measure.

Reads the same 50-task P0 baselines every delta in the matrix is measured
against, resolved through `analyze_v8_results.baseline_for`, so the numbers here
and the numbers in the paper come from one source.

    uv run python scripts/explore_redundancy_stats.py
    uv run python scripts/explore_redundancy_stats.py --scale 500
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(REPO / "scripts"))

from src.coord.redundancy import explore_sql_from_trace  # noqa: E402
from src.logging.trace import read_trace_events  # noqa: E402


def replica_traces(coord_path: Path) -> list[Path]:
    """Every replica trace referenced by one task's coordination trace."""
    if not coord_path.exists():
        return []
    out = []
    for ev in read_trace_events(coord_path):
        if ev.get("event") == "replica_end":
            p = Path(str(ev.get("trace_path", "")))
            if p.exists():
                out.append(p)
    return out


def ast_key(sql: str) -> str:
    """Normalise past formatting, or fall back to the string form.

    sqlglot fails on a small number of malformed probes. Falling back keeps
    those statements in the denominator rather than silently dropping the
    messiest queries, which would flatter the AST measure.
    """
    try:
        import sqlglot
        return sqlglot.parse_one(sql, read="sqlite").sql(normalize=True, comments=False).lower()
    except Exception:  # noqa: BLE001 - any parse failure means "use the string"
        return sql


def stats_for(batch: Path) -> dict:
    """Three different percentages, because they are genuinely different numbers.

    `mean_all` averages the per-task rate over every task with a trace,
    including tasks whose replicas never issued an explore query at all and so
    contribute a 0%. That is what run_parallel_batch.py writes as
    `avg_explore_redundancy_pct`, what the redundancy figure plots, and what
    §3.3 of the paper quotes, so it is the only one of the three that may be
    stated as "the paper's number".

    `mean_explorers` averages over tasks that actually explored. It runs higher
    wherever a model often submits without probing, which on Gemini is a fifth
    of the subset.

    `pooled` divides total duplicates by total explore queries across the whole
    batch, so a task issuing 118 queries counts for more than one issuing 4.

    Never mix them. Quote absolute counts on a slide instead, since those cannot
    be confused with any of the three.
    """
    tasks = 0            # tasks with a readable trace
    explorers = 0        # of those, tasks that issued at least one explore query
    total = 0
    dup_string = 0
    dup_ast = 0
    per_task_rates: list[float] = []
    per_task_unique: list[int] = []
    worst_repeat = (0, None, None)      # (count, sql, question_id)
    corpus: Counter[str] = Counter()

    for row in json.load(batch.open()).get("rows", []):
        coord = row.get("coord_trace_path")
        if not coord:
            continue
        traces = replica_traces(Path(str(coord)))
        if not traces:
            continue
        sqls: list[str] = []
        for tp in traces:
            sqls.extend(explore_sql_from_trace(tp))

        tasks += 1
        if not sqls:
            per_task_rates.append(0.0)   # counted, exactly as the batch does
            continue

        explorers += 1
        total += len(sqls)
        counts = Counter(sqls)
        per_task_unique.append(len(counts))
        dup = len(sqls) - len(counts)
        dup_string += dup
        per_task_rates.append(100.0 * dup / len(sqls))
        corpus.update(counts)

        sql, n = counts.most_common(1)[0]
        if n > worst_repeat[0]:
            worst_repeat = (n, sql, row.get("question_id"))

        dup_ast += len(sqls) - len(Counter(ast_key(s) for s in sqls))

    if not explorers:
        return {}
    explorer_rates = [r for r in per_task_rates if r > 0] or [0.0]
    return {
        "tasks": tasks,
        "explorers": explorers,
        "total": total,
        "per_task": total / explorers,
        "unique_per_task": sum(per_task_unique) / explorers,
        "mean_all": sum(per_task_rates) / max(len(per_task_rates), 1),
        "mean_explorers": sum(explorer_rates) / len(explorer_rates),
        "pooled": 100.0 * dup_string / total,
        "pooled_ast": 100.0 * dup_ast / total,
        "worst_repeat": worst_repeat,
        "corpus_top": corpus.most_common(3),
    }


def main() -> int:
    from analyze_v8_results import MODELS, baseline_for  # noqa: PLC0415

    ap = argparse.ArgumentParser()
    ap.add_argument("--scale", default="50", choices=["50", "500"])
    args = ap.parse_args()
    ns = (3, 10, 25) if args.scale == "50" else (3, 10)

    print(f"Duplicated exploratory SQL, P0 baselines, {args.scale}-task")
    print("=" * 104)
    print(f"{'N':>3} {'model':9} {'tasks':>5} {'expl':>5} {'explore SQL':>12} "
          f"{'per task':>9} {'distinct':>9} | {'mean(all)':>9} {'mean(expl)':>10} "
          f"{'pooled':>7} {'AST':>7}")
    print(f"{'':47} | {'= paper':>9}")

    rollup: dict[int, list[dict]] = {}
    for n in ns:
        for key, short in MODELS:
            path = baseline_for(args.scale, n, key)
            if path is None:
                print(f"{n:>3} {short:9} MISSING")
                continue
            s = stats_for(path)
            if not s:
                print(f"{n:>3} {short:9} no explore SQL in traces")
                continue
            rollup.setdefault(n, []).append(s)
            print(f"{n:>3} {short:9} {s['tasks']:>5} {s['explorers']:>5} "
                  f"{s['total']:>12,} {s['per_task']:>9.1f} {s['unique_per_task']:>9.1f} | "
                  f"{s['mean_all']:>8.1f}% {s['mean_explorers']:>9.1f}% "
                  f"{s['pooled']:>6.1f}% {s['pooled_ast']:>6.1f}%")

    print("\nAcross all three models (absolute counts, safe to quote anywhere)")
    print("-" * 104)
    for n, rows in sorted(rollup.items()):
        total = sum(r["total"] for r in rows)
        expl = sum(r["explorers"] for r in rows)
        per = total / expl
        uniq = sum(r["unique_per_task"] * r["explorers"] for r in rows) / expl
        lo = min(r["mean_all"] for r in rows)
        hi = max(r["mean_all"] for r in rows)
        print(f"N={n:<3} {total:>8,} explore queries over {expl} task-runs, "
              f"{per:.0f} per task collapsing to {uniq:.0f} distinct "
              f"(paper's range {lo:.0f}-{hi:.0f}%)")

    print("\nThe most-repeated single statement in each cell")
    print("-" * 92)
    for n, rows in sorted(rollup.items()):
        cnt, sql, qid = max((r["worst_repeat"] for r in rows), key=lambda w: w[0])
        text = (sql or "")[:64] + ("..." if sql and len(sql) > 64 else "")
        print(f"N={n:<3} issued {cnt:>3}x on question {qid}: {text}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
