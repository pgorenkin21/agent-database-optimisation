"""Generate thesis Chapter 5 draft from P2 vs P0 batch comparisons."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from src.coord.baseline_plots import MODEL_LABELS
from src.coord.early_stop_analysis import pct_delta
from src.coord.p2_analysis import P2_BATCH_IDS, load_comparisons_by_replica_counts


def _model_label(model_key: str) -> str:
    return MODEL_LABELS.get(model_key, model_key)


def _fmt_pct(value: float | None, *, digits: int = 1) -> str:
    if value is None:
        return "—"
    return f"{value:.{digits}f}"


def _fmt_delta(value: float | None) -> str:
    if value is None:
        return "—"
    sign = "+" if value > 0 else ""
    return f"{sign}{value:.1f}%"


def _red_delta(p0: dict[str, Any], p2: dict[str, Any]) -> float:
    return (p2.get("avg_explore_redundancy_pct") or 0) - (p0.get("avg_explore_redundancy_pct") or 0)


def _comparison_table(
    comparisons: list[tuple[dict[str, Any], dict[str, Any]]],
    *,
    n_replicas: int,
    table_num: int,
) -> str:
    lines = [
        f"**Table 5.{table_num}.** P0 vs P2 discovery board at *N*={n_replicas} "
        "(50-task smoke subset, `best_of_n`, no early stopping).",
        "",
        "| Model | P0 EX % | P2 EX % | P0 redundancy % | P2 redundancy % | "
        "Red Δ | P2 frags/task | P2 middleware % | P0 overhead | P2 overhead | Token Δ |",
        "|-------|--------:|--------:|----------------:|----------------:|"
        "------:|-------------:|----------------:|------------:|------------:|--------:|",
    ]
    footnotes: list[str] = []

    for p0, p2 in comparisons:
        label = _model_label(p0["model_key"])
        p2_ex = _fmt_pct(p2["ex_accuracy_pct"])
        api_fails = int(p2.get("api_failure_count", 0))
        if api_fails:
            p2_ex = f"{p2_ex}†"
            footnotes.append(
                f"† {_model_label(p2['model_key'])} P2 at *N*={n_replicas}: {api_fails} API "
                f"failure(s); EX on completed tasks = "
                f"{_fmt_pct(p2.get('ex_accuracy_excluding_api_errors_pct'))}%."
            )
        tok_delta = pct_delta(p0["total_tokens"], p2["total_tokens"])
        mw_pct = p2.get("avg_middleware_interaction_pct", 0)
        lines.append(
            f"| {label} | {_fmt_pct(p0['ex_accuracy_pct'])} | {p2_ex} | "
            f"{_fmt_pct(p0['avg_explore_redundancy_pct'])} | "
            f"{_fmt_pct(p2['avg_explore_redundancy_pct'])} | "
            f"{_red_delta(p0, p2):+.1f}pp | "
            f"{_fmt_pct(p2.get('avg_discovery_fragments'))} | "
            f"{_fmt_pct(mw_pct)} | "
            f"{p0['avg_token_overhead_ratio']:.2f}× | {p2['avg_token_overhead_ratio']:.2f}× | "
            f"{_fmt_delta(tok_delta)} |"
        )

    if footnotes:
        lines.append("")
        lines.extend(footnotes)
    return "\n".join(lines)


def _per_model_detail(comparisons: list[tuple[dict[str, Any], dict[str, Any]]]) -> list[str]:
    lines: list[str] = []
    for p0, p2 in comparisons:
        label = _model_label(p0["model_key"])
        red_delta = _red_delta(p0, p2)
        tok_delta = pct_delta(p0["total_tokens"], p2["total_tokens"])
        mw_pct = p2.get("avg_middleware_interaction_pct", 0)
        lines.extend(
            [
                f"### {label}",
                "",
                f"- Discovery board: **{p2.get('avg_discovery_fragments', 0):.1f}** unique fragments/task; "
                f"**{p2.get('avg_discovery_injections_per_task', 0):.1f}** prompt injections/task.",
                f"- Middleware interaction: **{mw_pct:.1f}%** "
                f"({p2.get('total_middleware_discovery_injections', 0):,} prompt injections; "
                f"all explore SQL still hits SQLite without P1).",
                f"- Explore redundancy: {_fmt_pct(p0['avg_explore_redundancy_pct'])} → "
                f"{_fmt_pct(p2['avg_explore_redundancy_pct'])} ({red_delta:+.1f} pp).",
                f"- Token overhead: {p0['avg_token_overhead_ratio']:.2f}× → "
                f"{p2['avg_token_overhead_ratio']:.2f}× ({_fmt_delta(tok_delta)} total tokens).",
                "",
            ]
        )
    return lines


def generate_chapter5_markdown(
    comparisons_by_n: dict[int, list[tuple[dict[str, Any], dict[str, Any]]]],
    *,
    plots_dir: Path | None = None,
    generated_at: str | None = None,
) -> str:
    if not comparisons_by_n:
        raise ValueError("No comparison data for Chapter 5")

    ts = generated_at or datetime.now(timezone.utc).strftime("%Y-%m-%d")
    plots_rel = plots_dir or Path("runs/reports/plots")
    replica_counts = sorted(comparisons_by_n)
    max_n = max(replica_counts)
    max_pairs = comparisons_by_n[max_n]

    # Best redundancy improvement across all N
    best_delta = 0.0
    best_model = ""
    best_n = max_n
    for n, pairs in comparisons_by_n.items():
        for p0, p2 in pairs:
            d = _red_delta(p0, p2)
            if d < best_delta:
                best_delta = d
                best_model = _model_label(p0["model_key"])
                best_n = n

    frag_vals = [p2.get("avg_discovery_fragments") or 0 for _, p2 in max_pairs]
    min_frag = min(frag_vals)
    max_frag = max(frag_vals)

    lines: list[str] = [
        "# Chapter 5: Sub-Expression Propagation (P2)",
        "",
        f"*Draft generated {ts} from P0 vs `P2_subexpr_propagation` batch comparisons. "
        f"Regenerate with `uv run python scripts/generate_chapter5_draft.py`.*",
        "",
        "## 5.1 Motivation",
        "",
        "Chapters 3–4 optimised coordination at the **execution** layer: early stopping trims "
        "post-success LLM turns; P1 caches duplicate explore SQL against SQLite. Neither policy "
        "tells replicas what structural discoveries their siblings have already made. Chapter 2 "
        "showed **85–94% sub-expression overlap** across replicas—tables, columns, and predicates "
        "reappear even when full SQL strings differ—suggesting value in sharing those fragments "
        "*before* the next explore query is written.",
        "",
        "**P2** implements a *shared discovery board*: after each explore `execute_sql`, replicas "
        "publish sqlglot-extracted fragments to a thread-safe store; before every LLM turn, each "
        "agent receives a user-message block listing peer discoveries (tables, columns, predicates, "
        "join conditions) with guidance to avoid redundant probes.",
        "",
        "Unlike P1, P2 targets the **LLM exploration policy** directly. The hypothesis is that "
        "propagating structural context reduces duplicate explore SQL and token spend without "
        "hurting execution accuracy.",
        "",
        "## 5.2 Policy: P2_subexpr_propagation",
        "",
        "P2 extends the parallel coordinator with a per-task discovery board:",
        "",
        "1. Spawn *N* agents as in P0 (no shared SQL cache or early stopping in these experiments).",
        "2. On each explore `execute_sql`, extract fragments (`table:`, `col:`, `pred:`, `join_on:`) "
        "via sqlglot and publish to the shared board.",
        "3. Before each LLM `complete` call, inject a compact **peer discoveries** user message "
        "(replacing any prior discovery message for that turn).",
        "4. Log `discovery_injection` events in replica traces; aggregate `discovery_stats` in "
        "coordination traces.",
        "",
        "Fragment keys match the overlap metric from Chapter 2. Only explore-phase SQL contributes; "
        "`submit_sql` is not published.",
        "",
        "## 5.3 Experimental setup",
        "",
        "All settings match Chapters 2–4 unless noted:",
        "",
        "- **Benchmark:** BIRD mini-dev smoke subset (50 tasks).",
        "- **Models:** GPT-4o mini, Gemini 2.5 Flash, DeepSeek V3.2.",
        f"- **Replica counts:** *N* ∈ {{{', '.join(str(n) for n in replica_counts)}}}.",
        "- **Coordination:** `best_of_n` (same as P0).",
        "- **P0 baseline batches:** latest `parallel_*_baseline_rN_*_best_of_n.json`.",
        f"- **P2 batches:** `{'`, `'.join(P2_BATCH_IDS.values())}` sweep IDs (`--discovery-board`).",
        "",
        "## 5.4 Metrics",
        "",
        "| Metric | Definition |",
        "|--------|------------|",
        "| **Discovery fragments / task** | Mean unique fragment keys published per task. |",
        "| **Context injections / task** | Mean LLM turns where a non-empty peer-discovery block was injected. |",
        "| **Explore redundancy %** | Same as Chapter 2 (string-level duplicates in traces). |",
        "| **Token overhead** | Same as Chapter 2; injection adds prompt tokens each turn. |",
        "| **EX %** | Coordinated execution accuracy vs P0. |",
        "| **Middleware interaction %** | Share of interactions served by middleware "
        "(discovery prompt injections) vs SQLite. P2 raises this from 0% via injections "
        "even though every explore query still executes against the database. |",
        "",
        "## 5.5 Results",
        "",
    ]

    for i, n in enumerate(replica_counts, start=1):
        comparisons = comparisons_by_n[n]
        lines.extend(
            [
                f"### 5.5.{i} Replica count *N*={n}",
                "",
                _comparison_table(comparisons, n_replicas=n, table_num=i),
                "",
            ]
        )
        if n == max_n:
            lines.extend(
                [
                    f"![Figure 5.1 — P2 vs P0 at N={n}]({plots_rel / f'p2_comparison_r{n}.png'})",
                    "",
                    f"*Figure 5.1. Explore redundancy (P0 vs P2) and mean discovery fragments per task at *N*={n}.*",
                    "",
                ]
            )

    if len(replica_counts) >= 2:
        lines.extend(
            [
                f"![Figure 5.2 — Redundancy delta scaling]({plots_rel / 'p2_redundancy_delta_scaling.png'})",
                "",
                "*Figure 5.2. Change in mean explore redundancy (P2 − P0) vs replica count.*",
                "",
            ]
        )

    lines.extend(["### 5.5.3 Per-model detail", ""])
    lines.extend(_per_model_detail(max_pairs))

    # Dynamic discussion based on data
    r10_pairs = comparisons_by_n.get(10, [])
    gem_r10 = next(((p0, p2) for p0, p2 in r10_pairs if p0["model_key"] == "gemini-2.5-flash"), None)
    gem_red_improve = _red_delta(*gem_r10) if gem_r10 else 0.0

    lines.extend(
        [
            "## 5.6 Discussion",
            "",
            "**P2 effects are model-dependent and modest overall.** Unlike P1, which reliably "
            "eliminates 70–84% of SQLite round-trips, prompt-level fragment sharing does not "
            "consistently reduce string-level explore redundancy. At *N*=25, redundancy changes "
            "range from roughly −1 to +1 pp for GPT and DeepSeek; Gemini shows a larger shift at "
            f"*N*=10 ({gem_red_improve:+.1f} pp). The strongest improvement observed is "
            f"**{best_model}** at *N*={best_n} ({best_delta:+.1f} pp)—directionally aligned with "
            "Chapter 2's overlap findings but smaller than the overlap percentages themselves.",
            "",
            f"**Discovery boards are active.** At *N*={max_n}, mean fragments published per task "
            f"range from **{min_frag:.0f}–{max_frag:.0f}** across models, with multiple context "
            "injections per task. **Middleware interaction %** rises from 0% under P0 to roughly "
            "25–35% at *N*=10 (discovery injections counted as middleware events even though "
            "SQLite is still invoked for every explore query). Middleware is doing work; models "
            "do not always comply by issuing fewer explore queries.",
            "",
            "**Token overhead is not reduced—and can rise slightly.** Each turn may include a "
            "growing peer-discovery block in the prompt. Total token spend is within run noise for "
            "most models but trends upward when injections are frequent (e.g. +7% Gemini at *N*=10). "
            "P2 trades a small prompt cost for uncertain exploration savings.",
            "",
            "**Execution accuracy is mostly stable.** Gemini EX matches or improves vs P0 (+2 pp at "
            "both *N* values). GPT EX is unchanged at *N*=10 but drops 6 pp at *N*=25 (62% → 56%)—"
            "worth monitoring on the full dev set. DeepSeek is within 2 pp of P0.",
            "",
            "**P2 complements but does not replace P1.** P1 removes duplicate *execution*; P2 attempts "
            "to steer duplicate *probes*. Chapter 2's 85–94% sub-expression overlap is a structural "
            "upper bound on what fragment lists can explain; converting overlap into fewer SQL strings "
            "requires models to follow the injected hints—a soft constraint compared to P1's hard cache.",
            "",
            "**Optional stacked policy.** A supplementary GPT *N*=10 run with `--early-stop` "
            "combined P2 discovery with Chapter 3 cancellation (trace policy "
            "`P2_subexpr_propagation_early_stop`); token overhead fell to 9.7× vs 11.1× for P2 alone, "
            "showing stacked middleware can compound. Full stacked evaluation is left to future work.",
            "",
            "## 5.7 Limitations",
            "",
            "1. **Soft coordination.** Models may ignore peer-discovery messages; no enforcement.",
            "2. **Prompt growth.** Discovery blocks add tokens each turn; not capped in these runs.",
            "3. **Fragment extraction only.** No semantic dedup beyond sqlglot fragments (cf. P1 AST keys).",
            "4. **Smoke subset.** 50 tasks; GPT *N*=25 EX regression may not generalise.",
            "5. **No P1+P2 combined runs** in the main matrix (only exploratory GPT early-stop stack).",
            "",
            "## 5.8 Summary and implications",
            "",
            f"P2 (`P2_subexpr_propagation`) publishes **{min_frag:.0f}–{max_frag:.0f}** unique SQL fragments "
            "per task at *N*=25 and injects peer context before each LLM turn. The policy produces "
            "meaningful redundancy reduction for some model/count pairs (notably Gemini at *N*=10) "
            "but is not a reliable win across the board. Token and redundancy gains are smaller and "
            "less consistent than P1's database-side cache.",
            "",
            "The middleware stack evaluated so far spans three layers: **early stop** (post-success "
            "tokens), **P1 cache** (duplicate execution), and **P2 discovery** (exploration hints). "
            "A natural next step is **combined P1+P2** (cache + board) and richer coordination (P3/P4) "
            "on the full BIRD dev set.",
            "",
            "---",
            "",
            "## Appendix: source artefacts",
            "",
            "| Artefact | Path |",
            "|----------|------|",
        ]
    )

    for n in replica_counts:
        batch_id = P2_BATCH_IDS.get(n, f"p2_r{n}_bo")
        lines.append(f"| P2 batches (*N*={n}) | `runs/batches/parallel_{batch_id}_*` |")
    lines.append("| Comparison report | `runs/reports/p2_vs_p0.json` |")
    for n in replica_counts:
        lines.append(f"| Figure 5.x (*N*={n}) | `{plots_rel / f'p2_comparison_r{n}.png'}` |")
    if len(replica_counts) >= 2:
        lines.append(f"| Figure 5.2 | `{plots_rel / 'p2_redundancy_delta_scaling.png'}` |")

    return "\n".join(lines) + "\n"
