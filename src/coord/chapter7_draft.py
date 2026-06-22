"""Generate thesis Chapter 7 draft — P3 semantic store evaluation."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from src.coord.baseline_plots import MODEL_LABELS
from src.coord.p3_analysis import (
    P2P3_BATCH_IDS,
    P3_BATCH_IDS,
    load_comparisons_by_replica_counts,
)


def _model_label(model_key: str) -> str:
    return MODEL_LABELS.get(model_key, model_key)


def _fmt_pct(value: float | None, *, digits: int = 1) -> str:
    if value is None:
        return "—"
    return f"{value:.{digits}f}"


def _fmt_delta(value: float | None, *, suffix: str = "%") -> str:
    if value is None:
        return "—"
    sign = "+" if value > 0 else ""
    return f"{sign}{value:.1f}{suffix}"


def _rec_label(rec: str) -> str:
    return {
        "adopt": "**Adopt P3**",
        "mixed": "**Mixed**",
        "avoid": "**Avoid P3** (prefer P2 full stack+prune)",
        "investigate": "**Investigate**",
    }.get(rec, rec)


def _p3_vs_p2_table(rows: list[dict[str, Any]], *, n_replicas: int, table_num: int) -> str:
    lines = [
        f"**Table 7.{table_num}.** P3 semantic store vs P2 full stack+schema prune at *N*={n_replicas} "
        "(50-task smoke subset, `best_of_n`).",
        "",
        "| Model | P2+prune EX % | P3 EX % | EX Δ | P2 tokens | P3 tokens | Token Δ | "
        "Facts/task | Inj/task | Middleware % | Recommendation |",
        "|-------|-------------:|--------:|-----:|----------:|----------:|--------:|"
        "-----------:|---------:|-------------:|----------------|",
    ]
    for entry in rows:
        p2 = entry["p2_full_stack_prune"]
        p3 = entry["p3"]
        d = entry["delta"]
        label = _model_label(p3["model_key"])
        rec = d.get("recommendation", "mixed")
        lines.append(
            f"| {label} | {_fmt_pct(p2['ex_accuracy_pct'])} | {_fmt_pct(p3['ex_accuracy_pct'])} | "
            f"{d['ex_delta_pp']:+.1f}pp | {p2['total_tokens']:,} | {p3['total_tokens']:,} | "
            f"{_fmt_delta(d.get('token_delta_pct'))} | "
            f"{p3.get('avg_semantic_facts_per_task', 0):.1f} | "
            f"{p3.get('avg_semantic_injections_per_task', 0):.1f} | "
            f"{_fmt_pct(p3.get('avg_middleware_interaction_pct'))} | {_rec_label(rec)} |"
        )
    return "\n".join(lines)


def _p2p3_table(entries: list[dict[str, Any]], *, n_replicas: int, table_num: int) -> str:
    lines = [
        f"**Table 7.{table_num}.** P2+P3 combined vs P2+prune and P3-only at *N*={n_replicas}.",
        "",
        "| Model | P2+prune EX | P3 only EX | P2+P3 EX | P2+P3 tokens | Δ tok vs P2 | Δ tok vs P3 |",
        "|-------|----------:|-----------:|---------:|-------------:|------------:|------------:|",
    ]
    for entry in entries:
        label = _model_label(entry["model_key"])
        p2 = entry.get("p2_full_stack_prune", {})
        p3 = entry.get("p3_only", {})
        c = entry["p2p3"]
        d2 = entry.get("vs_p2", {})
        d3 = entry.get("vs_p3", {})
        lines.append(
            f"| {label} | {_fmt_pct(p2.get('ex_accuracy_pct'))} | "
            f"{_fmt_pct(p3.get('ex_accuracy_pct'))} | {_fmt_pct(c.get('ex_accuracy_pct'))} | "
            f"{c.get('total_tokens', 0):,} | {_fmt_delta(d2.get('token_delta_pct'))} | "
            f"{_fmt_delta(d3.get('token_delta_pct'))} |"
        )
    return "\n".join(lines)


def _p3_vs_p0_table(entries: list[dict[str, Any]], *, n_replicas: int, table_num: int) -> str:
    lines = [
        f"**Table 7.{table_num}.** P3 stack vs P0 baseline at *N*={n_replicas}.",
        "",
        "| Model | P0 EX % | P3 EX % | P0 tokens | P3 tokens | Token Δ vs P0 |",
        "|-------|--------:|--------:|----------:|----------:|--------------:|",
    ]
    for entry in entries:
        p0, p3, d = entry["p0"], entry["p3"], entry["delta"]
        label = _model_label(p3["model_key"])
        lines.append(
            f"| {label} | {_fmt_pct(p0['ex_accuracy_pct'])} | {_fmt_pct(p3['ex_accuracy_pct'])} | "
            f"{p0['total_tokens']:,} | {p3['total_tokens']:,} | "
            f"{_fmt_delta(d.get('token_delta_pct'))} |"
        )
    return "\n".join(lines)


def _per_model_p3_detail(rows: list[dict[str, Any]]) -> list[str]:
    lines: list[str] = []
    for entry in rows:
        p3 = entry["p3"]
        d = entry["delta"]
        label = _model_label(p3["model_key"])
        lines.extend(
            [
                f"### {label}",
                "",
                f"- **P3 stack:** EX **{_fmt_pct(p3['ex_accuracy_pct'])}%** "
                f"({d['ex_delta_pp']:+.0f} pp vs P2+prune); tokens "
                f"{_fmt_delta(d.get('token_delta_pct'))} vs P2+prune.",
                f"- Semantic store: **{p3.get('avg_semantic_facts_per_task', 0):.1f}** facts/task; "
                f"**{p3.get('avg_semantic_injections_per_task', 0):.1f}** injections/task; "
                f"**{p3.get('avg_cache_hit_rate_pct', 0):.1f}%** cache hit rate.",
                f"- Middleware interaction: **{_fmt_pct(p3.get('avg_middleware_interaction_pct'))}%** "
                f"(cache hits + semantic injections; no P2 discovery board in P3-only runs).",
                f"- Recommendation: {_rec_label(d.get('recommendation', 'mixed'))} — "
                f"{d.get('recommendation_reason', '')}",
                f"- Batch: `{Path(p3['path']).name}`",
                "",
            ]
        )
    return lines


def generate_chapter7_markdown(
    data: dict[str, Any],
    *,
    generated_at: str | None = None,
) -> str:
    vs_p2 = data.get("vs_full_stack_prune", {})
    vs_p0 = data.get("vs_p0", {})
    p2p3 = data.get("p2p3_combined", {})
    recs_by_n = data.get("recommendations", {})

    if not vs_p2 and not vs_p0:
        raise ValueError("No P3 comparison data for Chapter 7")

    ts = generated_at or datetime.now(timezone.utc).strftime("%Y-%m-%d")
    p3_id = P3_BATCH_IDS.get(10, "semantic_hybrid_r10_bo")
    p2p3_id = P2P3_BATCH_IDS.get(10, "p2p3_hybrid_r10_bo")

    lines: list[str] = [
        "# Chapter 7: Semantic Fact Store (P3)",
        "",
        f"*Draft generated {ts} from P3 and P2+P3 batch comparisons. "
        f"Regenerate with `uv run python scripts/generate_chapter7_draft.py`.*",
        "",
        "## 7.1 Motivation",
        "",
        "Chapter 5 (P2) shares **syntactic fragments**—tables, columns, predicates extracted via "
        "sqlglot—and injects them as peer-discovery blocks before each LLM turn. That policy can "
        "steer exploration for some models (notably Gemini at *N*=10) but often **raises token "
        "spend** because fragment lists grow with replica count and are re-sent every turn.",
        "",
        "Chapter 6 showed that **full stack + schema prune** (P1 cache + P2 board + early stop + "
        "hybrid schema pruning) delivers the best overall trade-off for Gemini and DeepSeek at "
        "*N*=10, while GPT loses 2 pp execution accuracy. P2's prompt cost remains a concern when "
        "stacked with other layers.",
        "",
        "**P3** replaces fragment lists with a **bounded semantic fact store**: after each explore "
        "`execute_sql`, rule-based extractors distil SQL, row counts, numeric summaries, distinct "
        "value samples, and error messages into short natural-language facts. Before each LLM turn, "
        "replicas receive a capped bullet list of peer facts (default: 8 bullets, 500 characters). "
        "The design targets **token-efficient broadcasting**—sharing *outcomes* of probes rather "
        "than re-listing structural hints on every turn.",
        "",
        "Unlike P2, P3 does not attempt to deduplicate explore SQL strings directly; it gives models "
        "compact evidence (e.g. \"`transactions` returned 0 rows\", \"column[2] min=1 max=99\") so "
        "siblings can skip redundant probes. P3 stacks with P1 cache, early stop, and **hybrid schema "
        "pruning** (keyword seeds with TF-IDF semantic fallback) for apples-to-apples comparison "
        "against Chapter 6's full stack+prune baseline.",
        "",
        "## 7.2 Policy: P3_semantic_store",
        "",
        "P3 extends the parallel coordinator with a per-task `SharedSemanticStore`:",
        "",
        "1. Spawn *N* agents with shared P1 SQL cache and early stop (same as full stack+prune).",
        "2. On each explore `execute_sql`, run `extract_semantic_facts()` (no LLM calls): normalized "
        "AST snippet, join hints, row counts, column stats, distinct samples, SQLite errors.",
        "3. Publish new facts to the store (deduplicated by lowercase key; max 128 entries per task).",
        "4. Before each LLM `complete`, inject a **semantic context** user message (replacing prior "
        "injection for that turn), capped at 8 bullets and 500 characters.",
        "5. Log `semantic_injection` events; aggregate `semantic_stats` in coordination traces.",
        "",
        "**Hybrid schema pruning** (`--schema-pruning-mode hybrid`) scores tables from question + "
        "evidence keywords first; if no signal, falls back to TF-IDF cosine similarity between "
        "question+evidence and table/column descriptions. Offline recall on the smoke subset: "
        "**100%** gold-table recall with **34.5%** average schema size reduction.",
        "",
        "**P3-only stack** (`--semantic-store --shared-cache --early-stop --schema-pruning`): "
        "P1 + P3 + early stop + hybrid prune; **no P2 discovery board**.",
        "",
        f"**P2+P3 combined** (`--discovery-board --semantic-store …`): both fragment injection and "
        f"semantic facts enabled; batch ID `{p2p3_id}`.",
        "",
        "## 7.3 Experimental setup",
        "",
        "Settings match Chapters 2–6 unless noted:",
        "",
        "- **Benchmark:** BIRD mini-dev smoke subset (50 tasks).",
        "- **Models:** GPT-4o mini, Gemini 2.5 Flash, DeepSeek V3.2.",
        "- **Replica count:** *N* = 10 (`best_of_n`).",
        "- **P2 baseline:** full stack + schema prune (`fullstack_prune_r10_bo`) — P1 + P2 + early "
        "stop + keyword/hybrid schema prune (Chapter 6 §6.7).",
        f"- **P3 batches:** `{p3_id}` (`--semantic-store --schema-pruning-mode hybrid`).",
        f"- **P2+P3 batches:** `{p2p3_id}` (Gemini and DeepSeek only; follow-up to recover EX).",
        "",
        "## 7.4 Metrics",
        "",
        "| Metric | Definition |",
        "|--------|------------|",
        "| **Semantic facts / task** | Mean unique facts published per task after explore queries. |",
        "| **Semantic injections / task** | Mean LLM turns where a non-empty semantic context block was injected. |",
        "| **Middleware interaction %** | (cache hits + semantic injections [+ discovery injections for P2+P3]) / total interactions. |",
        "| **EX %** | Coordinated execution accuracy vs P2+prune and P0. |",
        "| **Token Δ** | Total batch tokens vs baseline. |",
        "",
        "## 7.5 Results",
        "",
    ]

    table_num = 1
    for n in sorted(vs_p2, key=int):
        rows = vs_p2[n]
        lines.extend(
            [
                f"### 7.5.{n // 10} Replica count *N*={n}",
                "",
                _p3_vs_p2_table(rows, n_replicas=n, table_num=table_num),
                "",
            ]
        )
        table_num += 1

        recs = recs_by_n.get(n, {})
        lines.extend(["**Recommendations**", ""])
        for entry in rows:
            p3 = entry["p3"]
            d = entry["delta"]
            label = _model_label(p3["model_key"])
            lines.append(
                f"- **{label}:** {_rec_label(d.get('recommendation', 'mixed'))} — "
                f"{d.get('recommendation_reason', '')}"
            )
        lines.append("")

        adopt = [m for m, r in recs.items() if r.get("recommendation") == "adopt"]
        avoid = [m for m, r in recs.items() if r.get("recommendation") == "avoid"]
        mixed = [m for m, r in recs.items() if r.get("recommendation") == "mixed"]
        lines.extend(
            [
                f"**Cross-model summary (N={n}):**",
                "",
                f"- Adopt P3: {', '.join(_model_label(m) for m in adopt) or 'none'}",
                f"- Prefer P2+prune: {', '.join(_model_label(m) for m in avoid) or 'none'}",
                f"- Mixed / model-specific: {', '.join(_model_label(m) for m in mixed) or 'none'}",
                "",
            ]
        )

        if n in p2p3 and p2p3[n]:
            lines.extend(
                [
                    "#### P2+P3 combined follow-up",
                    "",
                    "P3-only runs dropped EX for Gemini (−6 pp) and DeepSeek (−4 pp) vs P2+prune. "
                    "We ran **P2+P3 combined** on those two models to test whether P2 fragment hints "
                    "recover accuracy while semantic facts cap redundant outcome probes.",
                    "",
                    _p2p3_table(p2p3[n], n_replicas=n, table_num=table_num),
                    "",
                ]
            )
            table_num += 1
            for entry in p2p3[n]:
                label = _model_label(entry["model_key"])
                c = entry["p2p3"]
                d2 = entry.get("vs_p2", {})
                d3 = entry.get("vs_p3", {})
                lines.append(
                    f"- **{label}:** P2+P3 EX **{_fmt_pct(c.get('ex_accuracy_pct'))}%** "
                    f"({d2.get('ex_delta_pp', 0):+.0f} pp vs P2+prune, "
                    f"{d3.get('ex_delta_pp', 0):+.0f} pp vs P3-only); tokens "
                    f"{_fmt_delta(d2.get('token_delta_pct'))} vs P2+prune."
                )
            lines.append("")

        if n in vs_p0 and vs_p0[n]:
            lines.extend(
                [
                    "#### P3 vs P0 baseline",
                    "",
                    _p3_vs_p0_table(vs_p0[n], n_replicas=n, table_num=table_num),
                    "",
                ]
            )
            table_num += 1

        lines.extend(["#### Per-model detail", ""])
        lines.extend(_per_model_p3_detail(rows))

    lines.extend(
        [
            "## 7.6 Discussion",
            "",
            "**P3 outcomes are strongly model-dependent.** Replacing P2 fragment lists with capped "
            "semantic facts is not a universal upgrade over full stack+prune:",
            "",
            "**GPT-4o mini — adopt P3.** P3 improves EX by **+4 pp** (60% vs 56%) while cutting tokens "
            "**−6.5%** vs P2+prune and **−26.3%** vs P0. GPT appears over-constrained by P2 discovery "
            "injections combined with schema pruning; compact outcome facts steer exploration without "
            "the fragment-list prompt premium.",
            "",
            "**Gemini 2.5 Flash — mixed; prefer P2+prune.** P3-only drops EX **−6 pp** (70% vs 76%) "
            "with flat tokens (−0.2%). P2+P3 recovers to **74%** (+4 pp vs P3-only) but remains **−2 pp** "
            "below P2+prune at +1.7% tokens. Gemini benefited from P2 fragment hints in Chapter 5; "
            "removing them hurts more than semantic facts compensate.",
            "",
            "**DeepSeek V3.2 — avoid P3; prefer P2+prune.** P3-only loses **−4 pp** EX and adds "
            "**+42.5%** tokens vs P2+prune. The token spike correlates with heavy semantic activity "
            "(~62 facts/task, ~56 injections/task) and likely APITimeout retries during the P3 sweep. "
            "P2+P3 raises EX to **66%** (+2 pp vs P2+prune) but at **+30.7%** tokens—worse than "
            "P2+prune on both cost and the original P3-only failure mode.",
            "",
            "**Semantic store vs discovery board.** P3 middleware interaction rises via "
            "`semantic_injection` events (60–80% across models) without P2's `discovery_injection` "
            "channel. Facts are shorter per bullet but DeepSeek publishes far more of them, "
            "suggesting the extractor fires on every explore outcome and the model does not reduce "
            "probe count accordingly.",
            "",
            "**Stacking P2 and P3 does not reliably beat P2 alone.** For Gemini, combined middleware "
            "adds both fragment lists *and* semantic bullets—prompt growth without reaching P2+prune "
            "accuracy. For DeepSeek, dual injection channels inflate tokens while EX gains remain "
            "modest (+2 pp vs P2+prune).",
            "",
            "## 7.7 Limitations",
            "",
            "1. **Rule-based extraction only.** Facts are structural/statistical; no LLM summarisation "
            "or embedding dedup across semantically equivalent outcomes.",
            "2. **Smoke subset (50 tasks).** Model-specific recommendations may shift on full BIRD dev.",
            "3. ***N*=10 only.** P3 at *N*=25 not evaluated; semantic injection frequency scales with "
            "replica count.",
            "4. **DeepSeek token anomaly.** P3-only +42.5% token increase warrants retry analysis "
            "(timeouts, longer completions) before attributing solely to middleware design.",
            "5. **GPT P2+P3 not run.** Combined stack untested on the one model that favours P3 alone.",
            "6. **P4 not implemented.** Phase-aware sharing and cross-model ensembles remain future work.",
            "",
            "## 7.8 Summary and thesis implications",
            "",
            "P3 (`P3_semantic_store`) distils explore SQL outcomes into **8–62 facts per task** "
            "(model-dependent) and injects capped semantic context before each LLM turn. Against "
            "Chapter 6's best stack (P2+prune), results split by model:",
            "",
            "| Model | Best policy (*N*=10) | Rationale |",
            "|-------|---------------------|-----------|",
            "| GPT-4o mini | **P3** (not P2+prune) | +4 pp EX, −6.5% tokens vs P2+prune |",
            "| Gemini 2.5 Flash | **P2+prune** | 76% EX; P3 70%; P2+P3 74% |",
            "| DeepSeek V3.2 | **P2+prune** | 64% EX, lowest tokens; P3 costly |",
            "",
            "The middleware thesis therefore closes with a **model-conditioned deployment rule**: "
            "there is no single optimal stack. Token-efficient coordination requires matching "
            "middleware layers to how each model responds to shared syntactic hints vs distilled "
            "outcome facts.",
            "",
            "---",
            "",
            "## Appendix: source artefacts",
            "",
            "| Artefact | Path |",
            "|----------|------|",
            f"| P3 batches (*N*=10) | `runs/batches/parallel_{p3_id}_*` |",
            f"| P2+P3 batches | `runs/batches/parallel_{p2p3_id}_*` |",
            "| P3 comparison report | `runs/reports/p3_vs_p2.json` |",
            "| Comparison script | `scripts/compare_p3.py` |",
            "| Semantic store | `src/coord/semantic_store.py` |",
            "| Fact extractors | `src/coord/semantic_extractors.py` |",
            "",
        ]
    )

    return "\n".join(lines) + "\n"
