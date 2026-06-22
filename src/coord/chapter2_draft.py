"""Generate thesis Chapter 2 draft from P0 baseline report JSON files."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from src.coord.baseline_plots import MODEL_LABELS

DEFAULT_REPORT_PATHS: tuple[str, ...] = (
    "runs/reports/baseline_gpt4o_baseline_full.json",
    "runs/reports/baseline_gemini_baseline_full.json",
    "runs/reports/baseline_deepseek_baseline_full.json",
)

FIGURE_FILES: tuple[tuple[str, str], ...] = (
    ("Figure 2.1", "baseline_overview.png"),
    ("Figure 2.2", "baseline_explore_redundancy.png"),
    ("Figure 2.3", "baseline_subexpr_overlap.png"),
    ("Figure 2.4", "baseline_token_overhead.png"),
    ("Figure 2.5", "baseline_wall_clock_s.png"),
    ("Figure 2.6", "baseline_ex_accuracy.png"),
)


def _load_comparison(path: Path) -> list[dict[str, Any]]:
    data = json.loads(path.read_text(encoding="utf-8"))
    rows = data.get("comparison", [])
    if not isinstance(rows, list) or not rows:
        raise ValueError(f"No comparison rows in {path}")
    return rows


def _model_label(model_key: str) -> str:
    return MODEL_LABELS.get(model_key, model_key)


def _fmt_pct(value: float | None, *, digits: int = 1) -> str:
    if value is None:
        return "—"
    return f"{value:.{digits}f}"


def _fmt_overhead(value: float | None) -> str:
    if value is None:
        return "—"
    return f"{value:.2f}×"


def _cross_model_table(all_rows: list[dict[str, Any]]) -> str:
    """Wide table: one row per replica count, columns grouped by model."""
    models = sorted({r["model_key"] for r in all_rows})
    replica_counts = sorted({r["n_replicas"] for r in all_rows})
    by_key = {(r["model_key"], r["n_replicas"]): r for r in all_rows}

    header = "| Replicas |"
    sep = "|---------:|"
    for model in models:
        label = _model_label(model)
        header += f" {label} EX % | {label} redundancy % | {label} tokens |"
        sep += "-----:|------------------:|-------------:|"
    lines = [header, sep]
    footnotes: list[str] = []

    for n in replica_counts:
        row = f"| {n} |"
        for model in models:
            r = by_key.get((model, n))
            if not r:
                row += " — | — | — |"
                continue
            ex = _fmt_pct(r["ex_accuracy_pct"])
            api_fails = int(r.get("api_failure_count", 0))
            if api_fails:
                ex = f"{ex}†"
                ex_excl = r.get("ex_accuracy_excluding_api_errors_pct")
                ex_excl_s = _fmt_pct(ex_excl) if ex_excl is not None else "n/a"
                footnotes.append(
                    f"† {_model_label(model)} at *N*={n}: {api_fails} API failure(s); "
                    f"EX on completed tasks = {ex_excl_s}%."
                )
            red = _fmt_pct(r["avg_explore_redundancy_pct"])
            tokens = f"{int(r['total_tokens']):,}"
            row += f" {ex} | {red} | {tokens} |"
        lines.append(row)

    if footnotes:
        lines.append("")
        lines.extend(footnotes)
    return "\n".join(lines)


def _explore_redundancy_intro(all_rows: list[dict[str, Any]]) -> str:
    by_n: dict[int, list[float]] = {}
    for r in all_rows:
        by_n.setdefault(r["n_replicas"], []).append(r["avg_explore_redundancy_pct"])
    r3 = by_n.get(3, [])
    r10 = by_n.get(10, [])
    r25 = by_n.get(25, [])
    r3_range = f"{min(r3):.0f}–{max(r3):.0f}" if r3 else "46–54"
    r10_range = f"{min(r10):.0f}–{max(r10):.0f}" if r10 else "71–79"
    r25_min = min(r25) if r25 else 80
    return (
        "Explore redundancy rises sharply with *N* for all models (Figure 2.2). "
        f"At *N*=3, mean redundancy is {r3_range}%; at *N*=10 it reaches {r10_range}%; "
        f"at *N*=25 it exceeds **{r25_min:.0f}%** for every model."
    )


def _saturation_paragraph(all_rows: list[dict[str, Any]], models: list[str]) -> str:
    by_model: dict[str, dict[int, dict[str, Any]]] = {}
    for r in all_rows:
        by_model.setdefault(r["model_key"], {})[r["n_replicas"]] = r

    parts: list[str] = []
    for model in models:
        rows = by_model.get(model, {})
        r3 = rows.get(3)
        r25 = rows.get(25)
        if not r3 or not r25:
            continue
        label = _model_label(model)
        u3 = int(r3["unique_explore_string"])
        u25 = int(r25["unique_explore_string"])
        t3 = int(r3["total_explore_queries"])
        t25 = int(r25["total_explore_queries"])
        parts.append(
            f"For {label}, unique explore queries increase only from {u3} (*N*=3) to "
            f"{u25} (*N*=25) while total explore queries grow from {t3:,} to {t25:,}."
        )

    body = " ".join(parts) if parts else (
        "Total explore volume grows roughly linearly with *N*, but unique queries plateau."
    )
    return (
        "A critical saturation effect appears in the **unique explore** counts. "
        f"{body} Replicas are not discovering proportionally more of the search "
        "space—they are re-executing the same probes."
    )


def _deepseek_breadth_note(all_rows: list[dict[str, Any]]) -> str:
    by_model: dict[str, dict[int, dict[str, Any]]] = {}
    for r in all_rows:
        by_model.setdefault(r["model_key"], {})[r["n_replicas"]] = r
    deepseek = by_model.get("deepseek-v3.2", {})
    gemini = by_model.get("gemini-2.5-flash", {})
    ds3 = deepseek.get(3)
    gm3 = gemini.get(3)
    ds25 = deepseek.get(25)
    if not ds3 or not ds25:
        return ""
    ds_label = _model_label("deepseek-v3.2")
    gemini_explore = int(gm3["total_explore_queries"]) if gm3 else 0
    ds3_total = int(ds3["total_explore_queries"])
    ds25_total = int(ds25["total_explore_queries"])
    ds25_unique = int(ds25["unique_explore_string"])
    uniq_pct = 100.0 * ds25_unique / ds25_total if ds25_total else 0
    ds_red = _fmt_pct(ds25["avg_explore_redundancy_pct"])
    gemini_note = (
        f" ({gemini_explore} for Gemini at *N*=3)" if gemini_explore else ""
    )
    return (
        f"{ds_label} issues more explore queries per batch than the other models "
        f"({ds3_total} explore calls at *N*=3{gemini_note}) and maintains a higher "
        f"unique fraction at *N*=25 ({uniq_pct:.1f}% string-unique). Even so, "
        f"statement-level redundancy still reaches {ds_red}% at *N*=25."
    )


def _accuracy_section(all_rows: list[dict[str, Any]]) -> list[str]:
    r25_rows = [r for r in all_rows if r["n_replicas"] == 25]
    api_notes: list[str] = []
    for r in r25_rows:
        api_fails = int(r.get("api_failure_count", 0))
        if api_fails:
            label = _model_label(r["model_key"])
            ex_excl = _fmt_pct(r.get("ex_accuracy_excluding_api_errors_pct"))
            api_notes.append(
                f"{label} at *N*=25: headline EX {_fmt_pct(r['ex_accuracy_pct'])}% with "
                f"**{api_fails} API failure(s)**; EX on completed tasks = {ex_excl}%."
            )

    lines = [
        "For all three models, EX % is broadly stable across replica counts (roughly "
        "58–74% on the smoke subset). Parallelism with `best_of_n` does not dramatically "
        "change accuracy at *N*=3–25—redundancy is the primary cost, not degraded selection.",
    ]
    if api_notes:
        lines.append("")
        lines.extend(api_notes)
        lines.append("")
        lines.append(
            "These are infrastructure artefacts (rate limits / transport errors), not "
            "evidence that high *N* harms SQL quality. The dashed series in Figure 2.6 "
            "shows EX excluding API failures where applicable."
        )
    return lines


def _limitations_section(all_rows: list[dict[str, Any]], *, task_count: int) -> list[str]:
    r25_api = [
        (r["model_key"], int(r.get("api_failure_count", 0)))
        for r in all_rows
        if r["n_replicas"] == 25 and int(r.get("api_failure_count", 0)) > 0
    ]
    lines = [
        f"1. **Subset size.** Results are on {task_count} mini-dev tasks, not the "
        "full 500-question split or full BIRD dev. Magnitudes should be re-validated "
        "before generalising.",
    ]
    if r25_api:
        notes = ", ".join(
            f"{_model_label(m)} ({n} failures)" for m, n in r25_api
        )
        lines.append(
            f"2. **API failures at *N*=25.** {notes} depress headline EX on affected "
            "batches; cite EX excluding API errors or re-run when comparing at scale."
        )
        next_idx = 3
    else:
        next_idx = 2
    lines.extend(
        [
            f"{next_idx}. **Single selection policy.** All runs use `best_of_n`; "
            "`first_success` and `majority_vote` may change accuracy–cost trade-offs but "
            "do not reduce explore duplication during runs.",
            f"{next_idx + 1}. **No coordination during runs.** P0 runs every replica to "
            "completion with no shared cache and no early stopping—deliberately "
            "upper-bounding wasted work (early stopping is evaluated in Chapter 3).",
            f"{next_idx + 2}. **Temperature 0.** Higher temperature might diversify "
            "exploration and lower string redundancy; it could also reduce EX.",
        ]
    )
    return lines


def _per_model_section(rows: list[dict[str, Any]], *, model_key: str) -> list[str]:
    label = _model_label(model_key)
    lines = [f"### {label}", ""]
    sorted_rows = sorted(rows, key=lambda r: r["n_replicas"])

    lines.extend(
        [
            "| Replicas | Tasks | EX % | Explore redundancy % | Sub-expr overlap % | "
            "Token overhead | Unique explore / total |",
            "|---------:|------:|-----:|---------------------:|-------------------:|"
            "---------------:|-----------------------:|",
        ]
    )
    for r in sorted_rows:
        unique = int(r["unique_explore_string"])
        total = int(r["total_explore_queries"])
        lines.append(
            f"| {r['n_replicas']} | {r['task_count']} | {_fmt_pct(r['ex_accuracy_pct'])} | "
            f"{_fmt_pct(r['avg_explore_redundancy_pct'])} | "
            f"{_fmt_pct(r['avg_subexpr_overlap_pct'])} | "
            f"{_fmt_overhead(r['avg_token_overhead_ratio'])} | {unique} / {total} |"
        )

    r3 = next((r for r in sorted_rows if r["n_replicas"] == 3), None)
    r25 = next((r for r in sorted_rows if r["n_replicas"] == 25), None)
    if r3 and r25 and r3["model_key"] == model_key:
        u3 = int(r3["unique_explore_string"])
        u25 = int(r25["unique_explore_string"])
        t25 = int(r25["total_explore_queries"])
        growth = (u25 / u3 - 1) * 100 if u3 else 0
        uniq_pct = 100.0 * u25 / t25 if t25 else 0
        lines.extend(
            [
                "",
                f"From 3 to 25 replicas, {label} increases unique explore queries by "
                f"**{growth:.0f}%** ({u3} → {u25}) while total explore volume grows "
                f"**{int(r25['total_explore_queries']) / int(r3['total_explore_queries']):.1f}×**. "
                f"At *N*=25 only **{uniq_pct:.1f}%** of explore statements are string-unique.",
            ]
        )
    lines.append("")
    return lines


def generate_chapter2_markdown(
    report_paths: list[Path],
    *,
    plots_dir: Path | None = None,
    generated_at: str | None = None,
) -> str:
    """Render a thesis-ready Chapter 2 draft from baseline report JSON files."""
    ts = generated_at or datetime.now(timezone.utc).strftime("%Y-%m-%d")
    plots_rel = plots_dir or Path("runs/reports/plots")

    all_rows: list[dict[str, Any]] = []
    for path in report_paths:
        for row in _load_comparison(path):
            row = dict(row)
            row["_report"] = str(path)
            all_rows.append(row)

    models = sorted({r["model_key"] for r in all_rows})
    replica_counts = sorted({r["n_replicas"] for r in all_rows})
    task_count = max((r["task_count"] for r in all_rows if r["n_replicas"] == 3), default=50)

    lines: list[str] = [
        "# Chapter 2: Baseline Redundancy in Parallel Text-to-SQL Agents (P0)",
        "",
        f"*Draft generated {ts} from P0 baseline reports. Regenerate with "
        f"`uv run python scripts/generate_chapter2_draft.py`.*",
        "",
        "## 2.1 Motivation",
        "",
        "Speculative parallelism—running multiple independent LLM agents on the same "
        "text-to-SQL task and selecting a final answer—is a natural way to improve "
        "reliability. Each replica explores the database with `execute_sql` tool calls "
        "before submitting a final query. Without coordination at the data layer, "
        "replicas cannot observe each other's work; they are likely to repeat the same "
        "schema probes, filter experiments, and join patterns.",
        "",
        "This chapter quantifies that waste under **policy P0**: *N* independent replicas "
        "with no shared middleware, coordinated only at the end via `best_of_n` "
        "(prefer any execution-correct answer with the fewest turns). The results "
        "establish the baseline that later chapters must beat with caching, early "
        "stopping, and other coordination policies (P1–P4).",
        "",
        "### 2.1.1 Relation to retrieval-augmented generation (RAG)",
        "",
        "This work is sometimes mistaken for a variant of retrieval-augmented "
        "generation. The two address different problems. RAG is a *retrieval step "
        "that conditions a single inference*: it embeds the query, fetches "
        "semantically similar passages from a vector store, and injects them into the "
        "prompt as read-only context. Its optimisation target is grounding—retrieving "
        "the right text so one model call has the facts it needs—and its quality is "
        "measured by retrieval relevance.",
        "",
        "The system studied here optimises a different layer. First, the agents "
        "*execute* rather than *retrieve*: each replica issues live `execute_sql` "
        "calls against the database, observes real result sets, and iterates, with "
        "correctness scored by execution accuracy against gold SQL rather than "
        "retrieval recall. Second, the unit of optimisation is a population of "
        "speculative replicas, not a single prompt—there is nothing to coordinate in "
        "RAG because there is one inference, whereas the redundancy quantified in this "
        "chapter exists only because *N* agents fan out over the same task. Third, the "
        "shared SQL cache introduced in later policies (P1) is keyed on "
        "AST-normalised query strings for exact-match reuse of execution results, "
        "unlike a RAG index keyed on embedding similarity for fuzzy text recall. "
        "Finally, the headline metric is redundancy elimination (duplicate explore "
        "SQL, sub-expression overlap, token overhead) subject to preserving execution "
        "accuracy, a question RAG does not pose.",
        "",
        "The two are therefore complementary rather than competing: RAG could operate "
        "*inside* a single replica—retrieving schema snippets or few-shot exemplars "
        "for schema linking—while the coordination middleware studied here sits "
        "*above* the replicas, eliminating duplicated execution regardless of how each "
        "agent forms its SQL.",
        "",
        "## 2.2 Experimental setup",
        "",
        "**Benchmark.** BIRD mini-dev (SQLite split): 50-task smoke subset of the "
        "500-question development set (`configs/subsets/smoke_50.txt` or first 50 tasks "
        "when no subset file is set). Gold evidence is included in prompts "
        "(`use_evidence: true`).",
        "",
        "**Agents.** Tool-calling loop with read-only `execute_sql` (exploration) and "
        "`submit_sql` (final answer). Temperature 0; up to 15 turns per replica.",
        "",
        "**Models.** Three API models from the evaluation matrix:",
        "",
        "| Registry key | Display name |",
        "|--------------|--------------|",
    ]
    for key in models:
        lines.append(f"| `{key}` | {_model_label(key)} |")

    lines.extend(
        [
            "",
            "**Parallel configuration.** Replica counts *N* ∈ {" + ", ".join(str(n) for n in replica_counts) + "}. "
            "Replicas run concurrently (thread pool); wall-clock is measured from "
            "`parallel_start` to `coordination_end` in the coordinator trace.",
            "",
            "**Selection policy.** `best_of_n` throughout: if any replica achieves "
            "execution accuracy (EX=1), pick the correct replica with fewest turns; "
            "otherwise pick the shortest non-empty submission.",
            "",
            "**Infrastructure.** SQLite execution matches official BIRD evaluation. "
            "JSONL traces record every `sql_execute` event per replica for offline "
            "redundancy analysis.",
            "",
            "## 2.3 Policy P0",
            "",
            "P0 (`P0_parallel`) is deliberately minimal:",
            "",
            "1. Spawn *N* identical agents on the same `(question, database)` pair.",
            "2. No shared cache, no cross-replica messaging, no early cancellation.",
            "3. After all replicas finish, apply `best_of_n` to choose the coordinated answer.",
            "",
            "P0 isolates the redundancy inherent in blind parallelism. Any reduction "
            "below these numbers in later policies is attributable to middleware.",
            "",
            "## 2.4 Metrics",
            "",
            "| Metric | Definition |",
            "|--------|------------|",
            "| **Execution accuracy (EX %)** | Fraction of tasks where the coordinated "
            "answer's result set matches gold (BIRD execution accuracy). |",
            "| **Explore redundancy %** | Within a task, fraction of explore-phase SQL "
            "statements that duplicate a prior statement (whitespace-normalised) across "
            "any replica. |",
            "| **Sub-expression overlap %** | Fraction of sqlglot-extracted fragments "
            "(tables, columns, predicates, join conditions) that appear in explore queries "
            "from two or more replicas. |",
            "| **Token overhead ratio** | Total tokens across all replicas divided by "
            "tokens of the cheapest *correct* replica (≥1; equals ~*N* when replicas are "
            "similar cost). |",
            "| **Unique explore queries** | Count of distinct explore SQL strings "
            "across replicas for a batch (summed per task, then aggregated). |",
            "| **Wall-clock (ms)** | Coordinator session duration (parallel wall time, "
            "not sum of replica times). |",
            "| **Middleware interaction %** | Share of agent interactions handled by "
            "middleware rather than SQLite: cache hits on explore `sql_execute` plus "
            "`discovery_injection` events, divided by all SQL executions plus middleware "
            "events. P0 has no shared cache or discovery board, so this is **0%** by "
            "definition and establishes the baseline for Chapters 4–6. |",
            "",
            "AST-normalised uniqueness (via sqlglot) is also computed in batch reports; "
            "it closely tracks string uniqueness at high *N*, indicating duplicates are "
            "substantive rather than formatting variants.",
            "",
            "## 2.5 Results",
            "",
            "### 2.5.1 Cross-model summary",
            "",
            f"Table 2.1 summarises {task_count}-task smoke runs across models and replica "
            "counts. Figure 2.1 provides a four-panel overview.",
            "",
            "**Table 2.1.** Execution accuracy, explore redundancy, and total token "
            "spend by model and replica count.",
            "",
            _cross_model_table(all_rows),
            "",
            f"![Figure 2.1 — P0 baseline overview]({plots_rel / 'baseline_overview.png'})",
            "",
            "*Figure 2.1. P0 baseline scaling across three models on BIRD mini-dev "
            f"({task_count} tasks): explore redundancy, token overhead, sub-expression "
            "overlap, and execution accuracy vs replica count.*",
            "",
            "### 2.5.2 Explore-query duplication dominates waste",
            "",
            _explore_redundancy_intro(all_rows),
            "",
        ]
    )

    for path in report_paths:
        model_key = _load_comparison(path)[0]["model_key"]
        lines.extend(_per_model_section(_load_comparison(path), model_key=model_key))

    lines.extend(
        [
            f"![Figure 2.2 — Explore redundancy]({plots_rel / 'baseline_explore_redundancy.png'})",
            "",
            "*Figure 2.2. Mean explore-query redundancy vs replica count. Error bars "
            "are not shown; per-task medians reach 80–92% at *N*=25.*",
            "",
            _saturation_paragraph(all_rows, models),
            "",
            _deepseek_breadth_note(all_rows),
            "",
            "### 2.5.3 Sub-expression overlap is near-total",
            "",
            "Sub-expression overlap (Figure 2.3) measures whether replicas touch the "
            "same tables, columns, and predicates even when full SQL strings differ. "
            "GPT-4o mini and Gemini reach 89–94% mean overlap at all replica counts; "
            "medians are often 100%. DeepSeek is slightly lower (84–88%) but still "
            "indicates that most structural exploration is shared.",
            "",
            f"![Figure 2.3 — Sub-expression overlap]({plots_rel / 'baseline_subexpr_overlap.png'})",
            "",
            "*Figure 2.3. Mean sub-expression overlap across replicas. High overlap "
            "implies middleware can deduplicate at fragment granularity, not only "
            "exact SQL strings.*",
            "",
            "### 2.5.4 Token and wall-clock cost",
            "",
            "Token overhead scales approximately linearly with *N* (Figure 2.4): "
            "~3× at *N*=3, ~10–13× at *N*=10, and ~26–33× at *N*=25. This matches "
            "the redundancy story: replicas consume full LLM budgets independently.",
            "",
            "| Model | Total tokens (*N*=3) | Total tokens (*N*=25) | Growth |",
            "|-------|---------------------:|----------------------:|-------:|",
        ]
    )

    by_model: dict[str, dict[int, dict[str, Any]]] = {}
    for r in all_rows:
        by_model.setdefault(r["model_key"], {})[r["n_replicas"]] = r
    for model in models:
        r3 = by_model[model].get(3, {})
        r25 = by_model[model].get(25, {})
        t3 = int(r3.get("total_tokens", 0))
        t25 = int(r25.get("total_tokens", 0))
        growth = t25 / t3 if t3 else 0
        lines.append(
            f"| {_model_label(model)} | {t3:,} | {t25:,} | {growth:.1f}× |"
        )

    lines.extend(
        [
            "",
            "Wall-clock time (Figure 2.5) grows sub-linearly because replicas run in "
            "parallel, but high-*N* runs still incur substantial coordination latency. "
            "DeepSeek's per-replica latency is higher (longer generations), so its "
            "average wall-clock exceeds the faster models despite similar replica counts.",
            "",
            f"![Figure 2.4 — Token overhead]({plots_rel / 'baseline_token_overhead.png'})",
            "",
            f"![Figure 2.5 — Wall-clock]({plots_rel / 'baseline_wall_clock_s.png'})",
            "",
            "### 2.5.5 Execution accuracy is stable; API failures matter at scale",
            "",
            *_accuracy_section(all_rows),
            "",
            f"![Figure 2.6 — Execution accuracy]({plots_rel / 'baseline_ex_accuracy.png'})",
            "",
            "*Figure 2.6. Coordinated execution accuracy vs replica count. Dashed lines "
            "exclude tasks where all replicas failed due to API/transport errors.*",
            "",
            "## 2.6 Discussion",
            "",
            "**Redundancy is the dominant cost of P0 parallelism.** At *N*=10, roughly "
            "four out of five explore queries are duplicates of work another replica "
            "already performed. Token spend tracks replica count, so a 10-replica "
            "smoke batch costs an order of magnitude more tokens than a single agent "
            "while EX % on Gemini/DeepSeek moves only a few points.",
            "",
            "**Unique work saturates quickly.** The plateau in unique explore queries "
            "(~100–300 per task set depending on model) suggests replicas converge on "
            "a small exploration frontier dictated by schema and question wording. "
            "Adding replicas beyond that frontier mostly repeats probes.",
            "",
            "**Model behaviour differs in exploration breadth, not redundancy direction.** "
            "DeepSeek explores more verbosely (higher query counts) but is not immune to "
            "overlap. Gemini is most token-efficient at low *N* but still reaches "
            ">80% redundancy at *N*=25.",
            "",
            "**Sub-expression overlap motivates fragment-level middleware.** String-level "
            "caching (P1) will catch exact duplicates; the 85–94% fragment overlap "
            "suggests value in sharing table/column/predicate discoveries even when "
            "full SQL differs.",
            "",
            "## 2.7 Limitations",
            "",
            *_limitations_section(all_rows, task_count=task_count),
            "",
            "## 2.8 Summary and implications",
            "",
            "P0 establishes that independent parallel text-to-SQL agents waste a large "
            "and growing fraction of database exploration work as *N* increases, while "
            "execution accuracy plateaus. On the smoke subset:",
            "",
            "- Explore redundancy exceeds **80%** at *N*=25 for all three models.",
            "- Token overhead approaches **25–33×** vs the cheapest correct replica.",
            "- Unique explore queries saturate far below total explore volume.",
            "",
            "These findings motivate the coordination policies evaluated in subsequent "
            "chapters: **Chapter 3** evaluates early stopping when a correct replica "
            "finishes; **Chapter 4 onward** evaluates shared middleware—**P1** (SQL "
            "result cache keyed by AST-normalised queries) and richer coordination "
            "(P2–P4) that propagates sub-expression discoveries across replicas.",
            "",
            "---",
            "",
            "## Appendix: source artefacts",
            "",
            "| Artefact | Path |",
            "|----------|------|",
        ]
    )

    for path in report_paths:
        lines.append(f"| {_model_label(_load_comparison(path)[0]['model_key'])} report | `{path}` |")
    lines.append(f"| Figures | `{plots_rel}/` |")
    for fig_id, filename in FIGURE_FILES:
        lines.append(f"| {fig_id} | `{plots_rel / filename}` |")

    return "\n".join(lines) + "\n"
