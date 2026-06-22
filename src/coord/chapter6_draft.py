"""Generate thesis Chapter 6 draft — middleware stack synthesis."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from src.coord.baseline_plots import MODEL_LABELS
from src.coord.early_stop_analysis import pct_delta
from src.coord.middleware_stack_analysis import FULL_STACK_BATCH_IDS, P1P2_BATCH_IDS, load_stack_by_replica_counts


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


def _stack_table(
    stack_by_model: dict[str, dict[str, dict[str, Any]]],
    *,
    n_replicas: int,
    table_num: int,
) -> str:
    policies = ["P0", "P1", "P2", "P1+P2", "early_stop", "full_stack"]
    present = [p for p in policies if any(p in stack_by_model[m] for m in stack_by_model)]
    lines = [
        f"**Table 6.{table_num}.** Middleware stack at *N*={n_replicas} (50-task smoke subset).",
        "",
    ]
    for metric_key, metric_label, fmt in [
        ("ex_accuracy_pct", "Execution accuracy (%)", "{:.1f}"),
        ("avg_explore_redundancy_pct", "Explore redundancy (%)", "{:.1f}"),
        ("avg_token_overhead_ratio", "Token overhead (×)", "{:.2f}"),
        ("avg_middleware_interaction_pct", "Middleware interaction (%)", "{:.1f}"),
    ]:
        lines.extend([f"*{metric_label}*", ""])
        lines.append("| Model | " + " | ".join(present) + " |")
        lines.append("|-------|" + "|".join(["--------:" for _ in present]) + "|")
        for model, pmap in stack_by_model.items():
            label = _model_label(model)
            cells = []
            for p in present:
                row = pmap.get(p)
                val = row.get(metric_key) if row else None
                cells.append(fmt.format(val) if val is not None else "—")
            lines.append(f"| {label} | " + " | ".join(cells) + " |")
        lines.append("")
    return "\n".join(lines)


def generate_chapter6_markdown(
    stacks_by_n: dict[int, dict[str, dict[str, dict[str, Any]]]],
    *,
    plots_dir: Path | None = None,
    generated_at: str | None = None,
) -> str:
    if not stacks_by_n:
        raise ValueError("No stack data for Chapter 6")

    ts = generated_at or datetime.now(timezone.utc).strftime("%Y-%m-%d")
    plots_rel = plots_dir or Path("runs/reports/plots")
    replica_counts = sorted(stacks_by_n)

    # Pull r=10 P1+P2 highlights
    r10 = stacks_by_n.get(10, {})
    gem = r10.get("gemini-2.5-flash", {})
    p0_gem = gem.get("P0", {})
    p1_gem = gem.get("P1", {})
    p2_gem = gem.get("P2", {})
    p12_gem = gem.get("P1+P2", {})

    lines: list[str] = [
        "# Chapter 6: Middleware Stack Synthesis",
        "",
        f"*Draft generated {ts} from P0, P1, P2, P1+P2, and early-stop batch comparisons. "
        f"Regenerate with `uv run python scripts/generate_chapter6_draft.py`.*",
        "",
        "## 6.1 Overview",
        "",
        "Chapters 2–5 evaluated coordination policies in isolation on a 50-task BIRD "
        "mini-dev smoke subset. This chapter places them side-by-side and adds **P1+P2** "
        "(`P1_P2_combined`): shared SQL cache plus discovery-board prompt injection at "
        "*N*=10.",
        "",
        "| Layer | Policy | Mechanism | Primary target |",
        "|-------|--------|-----------|----------------|",
        "| Ch. 3 | Early stop | Cancel siblings after EX=1 | Post-success LLM turns |",
        "| Ch. 4 | P1 cache | AST-keyed SQL result LRU | Duplicate DB execution |",
        "| Ch. 5 | P2 board | Fragment prompt injection | Duplicate explore probes |",
        "| §6.4 | P1+P2 | Both enabled | DB + exploration hints |",
        "",
        "The headline finding across chapters: **explore redundancy in traces is a poor "
        "proxy for token savings**. P0 reports 70–88% duplicate explore SQL at high *N*, "
        "yet only early stopping reliably reduces total tokens (~8–12% at *N*=25). P1 and "
        "P2 optimise different layers; stacking them does not produce additive token wins.",
        "",
        "## 6.2 What each policy actually saves",
        "",
        "**Early stopping (Ch. 3)** is the only policy that directly removes LLM turns. "
        "It fires only after a correct `submit_sql`, so pre-success exploration—where most "
        "duplication occurs—is untouched. At *N*=25, token savings are ~8–12% with overhead "
        "ratio dropping from ~27× to ~24× (GPT).",
        "",
        "**P1 shared cache (Ch. 4)** removes 70–84% of SQLite round-trips on cache hits but "
        "leaves explore SQL strings and LLM trajectories unchanged. Token overhead is flat "
        "(±3% run noise). Middleware interaction % rises to ~40–55% at *N*=10.",
        "",
        "**P2 discovery board (Ch. 5)** publishes sqlglot fragments and injects peer context "
        "before each turn. Redundancy drops meaningfully for Gemini at *N*=10 (−6.7 pp) but "
        "tokens often **rise** because injection grows the prompt. Middleware interaction % "
        "reaches ~25–35% at *N*=10 via discovery injections alone.",
        "",
        "## 6.2.1 Middleware interaction metric",
        "",
        "To separate **database work** from **middleware work**, we count every agent "
        "interaction in replica traces:",
        "",
        "| Class | Trace event | Policy |",
        "|-------|-------------|--------|",
        "| SQLite execution | `sql_execute` without `cache_hit` | P0, P1 miss, P2, final submit |",
        "| Middleware (cache) | `sql_execute` with `cache_hit=true` | P1, P1+P2 |",
        "| Middleware (discovery) | `discovery_injection` | P2, P1+P2 |",
        "",
        "**Middleware interaction %** = (cache hits + discovery injections) / (SQLite "
        "executions + cache hits + discovery injections). Under P0 this is **0%** by "
        "definition. Table 6.x shows how each policy shifts the balance.",
        "",
        "## 6.3 Cross-policy comparison",
        "",
    ]

    for i, n in enumerate(replica_counts, start=1):
        if n not in stacks_by_n:
            continue
        lines.extend(
            [
                f"### 6.3.{i} Replica count *N*={n}",
                "",
                _stack_table(stacks_by_n[n], n_replicas=n, table_num=i),
                "",
            ]
        )
        if n == 10:
            lines.extend(
                [
                    f"![Figure 6.1 — Middleware stack at N={n}]({plots_rel / f'middleware_stack_r{n}.png'})",
                    "",
                    f"*Figure 6.1. Token overhead, explore redundancy, middleware interaction %, and total tokens across policies at *N*={n}.*",
                    "",
                ]
            )

    if p12_gem and p0_gem:
        tok_d_p2 = pct_delta(p0_gem.get("total_tokens"), p2_gem.get("total_tokens")) if p2_gem else None
        tok_d_p12 = pct_delta(p0_gem.get("total_tokens"), p12_gem.get("total_tokens"))
        red_p2 = (p2_gem.get("avg_explore_redundancy_pct") or 0) - (p0_gem.get("avg_explore_redundancy_pct") or 0)
        red_p12 = (p12_gem.get("avg_explore_redundancy_pct") or 0) - (p0_gem.get("avg_explore_redundancy_pct") or 0)
        lines.extend(
            [
                "## 6.4 P1+P2 combined stack (*N*=10)",
                "",
                f"Batch ID `{'`, `'.join(P1P2_BATCH_IDS.values())}` with `--shared-cache --discovery-board`.",
                "",
                "### Gemini 2.5 Flash (best P2 responder)",
                "",
                f"| Metric | P0 | P1 | P2 | P1+P2 |",
                f"|--------|---:|---:|---:|------:|",
                f"| EX % | {_fmt_pct(p0_gem.get('ex_accuracy_pct'))} | {_fmt_pct(p1_gem.get('ex_accuracy_pct'))} | "
                f"{_fmt_pct(p2_gem.get('ex_accuracy_pct'))} | {_fmt_pct(p12_gem.get('ex_accuracy_pct'))} |",
                f"| Redundancy % | {_fmt_pct(p0_gem.get('avg_explore_redundancy_pct'))} | "
                f"{_fmt_pct(p1_gem.get('avg_explore_redundancy_pct'))} | "
                f"{_fmt_pct(p2_gem.get('avg_explore_redundancy_pct'))} | "
                f"{_fmt_pct(p12_gem.get('avg_explore_redundancy_pct'))} |",
                f"| Overhead × | {p0_gem.get('avg_token_overhead_ratio', 0):.2f} | "
                f"{p1_gem.get('avg_token_overhead_ratio', 0):.2f} | "
                f"{p2_gem.get('avg_token_overhead_ratio', 0):.2f} | "
                f"{p12_gem.get('avg_token_overhead_ratio', 0):.2f} |",
                f"| Cache hit % | — | {_fmt_pct(p1_gem.get('avg_cache_hit_rate_pct'))} | — | "
                f"{_fmt_pct(p12_gem.get('avg_cache_hit_rate_pct'))} |",
                f"| Middleware interaction % | 0.0 | {_fmt_pct(p1_gem.get('avg_middleware_interaction_pct'))} | "
                f"{_fmt_pct(p2_gem.get('avg_middleware_interaction_pct'))} | "
                f"{_fmt_pct(p12_gem.get('avg_middleware_interaction_pct'))} |",
                "",
                "P1+P2 preserves P2's redundancy reduction (~67% vs 73.6% P0) while token spend "
                f"({_fmt_delta(tok_d_p12)} vs P0) is "
                f"{'lower than P2 alone (' + _fmt_delta(tok_d_p2) + ')' if tok_d_p2 is not None else 'moderate'}. Cache hits "
                "remain high (~62%) despite slightly different SQL strings from discovery hints.",
                "",
                "### GPT-4o mini and DeepSeek V3.2",
                "",
            ]
        )
        for mk in ("gpt-4o-mini", "deepseek-v3.2"):
            pmap = r10.get(mk, {})
            p0, p1, p2, p12 = pmap.get("P0"), pmap.get("P1"), pmap.get("P2"), pmap.get("P1+P2")
            if not (p0 and p12):
                continue
            label = _model_label(mk)
            tok_d = pct_delta(p0.get("total_tokens"), p12.get("total_tokens"))
            red_d = (p12.get("avg_explore_redundancy_pct") or 0) - (p0.get("avg_explore_redundancy_pct") or 0)
            mw = p12.get("avg_middleware_interaction_pct", 0)
            lines.append(
                f"- **{label}:** redundancy {red_d:+.1f} pp vs P0; tokens {_fmt_delta(tok_d)} vs P0; "
                f"cache {p12.get('avg_cache_hit_rate_pct', 0):.0f}%; middleware interaction {mw:.1f}%."
            )
        lines.append("")

    r25 = stacks_by_n.get(25, {})
    fs_batch_id = FULL_STACK_BATCH_IDS.get(25)
    has_full_stack = any("full_stack" in pmap for pmap in r25.values())
    if has_full_stack and fs_batch_id:
        lines.extend(
            [
                "## 6.5 Full stack at *N*=25 (P1+P2+early stop)",
                "",
                f"Batch ID `{fs_batch_id}` with `--shared-cache --discovery-board --early-stop`. "
                "Trace policy: `P1_P2_combined_early_stop`.",
                "",
                "| Model | P0 EX % | full_stack EX % | P0 overhead | full_stack overhead | "
                "Token Δ vs P0 | Cache hit % | Middleware % | ES triggered |",
                "|-------|--------:|----------------:|------------:|--------------------:|"
                "------------:|------------:|-------------:|-------------:|",
            ]
        )
        for model, pmap in r25.items():
            p0 = pmap.get("P0")
            fs = pmap.get("full_stack")
            es = pmap.get("early_stop")
            if not p0 or not fs:
                continue
            label = _model_label(model)
            tok_d = pct_delta(p0.get("total_tokens"), fs.get("total_tokens"))
            tok_d_es = pct_delta(es.get("total_tokens"), fs.get("total_tokens")) if es else None
            lines.append(
                f"| {label} | {_fmt_pct(p0.get('ex_accuracy_pct'))} | "
                f"{_fmt_pct(fs.get('ex_accuracy_pct'))} | "
                f"{p0.get('avg_token_overhead_ratio', 0):.2f}× | "
                f"{fs.get('avg_token_overhead_ratio', 0):.2f}× | "
                f"{_fmt_delta(tok_d)} | "
                f"{_fmt_pct(fs.get('avg_cache_hit_rate_pct'))} | "
                f"{_fmt_pct(fs.get('avg_middleware_interaction_pct'))} | "
                f"{fs.get('early_stop_triggered_count', 0)}/{fs.get('task_count', 0)} |"
            )
        # Per-model narrative from data
        fs_bullets: list[str] = []
        for model, pmap in r25.items():
            p0 = pmap.get("P0")
            fs = pmap.get("full_stack")
            es = pmap.get("early_stop")
            if not p0 or not fs:
                continue
            label = _model_label(model)
            tok_d = pct_delta(p0.get("total_tokens"), fs.get("total_tokens"))
            tok_d_es = pct_delta(es.get("total_tokens"), fs.get("total_tokens")) if es else None
            ex_d = (fs.get("ex_accuracy_pct") or 0) - (p0.get("ex_accuracy_pct") or 0)
            es_part = f", {_fmt_delta(tok_d_es)} vs early stop alone" if tok_d_es is not None else ""
            fs_bullets.append(
                f"- **{label}:** EX {ex_d:+.0f} pp vs P0; tokens {_fmt_delta(tok_d)} vs P0{es_part}; "
                f"cache {fs.get('avg_cache_hit_rate_pct', 0):.0f}%; middleware {fs.get('avg_middleware_interaction_pct', 0):.0f}%."
            )
        deepseek_fs = r25.get("deepseek-v3.2", {}).get("full_stack")
        deepseek_p0 = r25.get("deepseek-v3.2", {}).get("P0")
        deepseek_tok_d = (
            pct_delta(deepseek_p0.get("total_tokens"), deepseek_fs.get("total_tokens"))
            if deepseek_p0 and deepseek_fs
            else None
        )
        lines.extend(
            [
                "",
                "The full stack combines post-success cancellation with shared cache and discovery "
                "hints. Results are **model-dependent**:",
                "",
            ]
        )
        lines.extend(fs_bullets)
        lines.extend(
            [
                "",
                f"**DeepSeek V3.2** is the standout: {_fmt_delta(deepseek_tok_d)} tokens vs P0 at "
                f"*N*=25 while preserving EX, with ~83% cache hits and ~86% middleware interaction. "
                "P1 cache removes most redundant SQLite work; early stop trims sibling turns; "
                "discovery hints do not dominate token cost for this model.",
                "",
                "**GPT-4o mini and Gemini 2.5 Flash** see P2 prompt injections offset early-stop "
                "savings: full-stack token spend exceeds early stop alone (+17–19%) even when "
                "middleware interaction rises to 65–81%. Gemini gains +8 pp EX vs P0 (78% vs 70%) "
                "at the cost of +3.5% tokens.",
                "",
            ]
        )

    lines.extend(
        [
            "## 6.6 Discussion: why overhead changes are smaller than redundancy suggests",
            "",
            "1. **Metric layers differ.** Explore redundancy counts duplicate SQL *strings* in "
            "traces. Token overhead sums *all replica LLM trajectories* divided by the cheapest "
            "correct answer. Most tokens live in schema context, chat history, and completions—not "
            "in the SQL tool call itself.",
            "",
            "2. **P1 is below the token ledger.** Cache hits skip SQLite, not LLM turns. An 80% "
            "cache hit rate does not imply an 80% token reduction. The **middleware interaction %** "
            "metric (cache hits + discovery injections vs SQLite executions) makes this layer "
            "explicit: P1 raises it via cache; P2 via prompt injections; P0 stays near 0%.",
            "",
            "3. **P2 adds prompt cost.** Each injection lists peer fragments. Savings from fewer "
            "explore queries (when they occur) compete with larger per-turn prompts.",
            "",
            "4. **Early stop is timed late.** ~60% of tasks trigger cancellation at *N*=25, but "
            "only after exploration-heavy work is already done.",
            "",
            "5. **Unique exploration saturates.** Chapter 2 showed unique explore queries plateau "
            "as *N* grows; policies that deduplicate execution or hint at fragments do not collapse "
            "*N* independent LLM dialogues into one.",
            "",
            "## 6.7 Recommendations",
            "",
            "| Goal | Prefer | Rationale |",
            "|------|--------|-----------|",
            "| Cut SQLite load | **P1** or **P1+P2** | 65–84% cache hits; middleware interaction 50–70% at *N*=10 |",
            "| Cut tokens modestly | **Early stop** | Only policy with consistent −8–12% tokens |",
            "| Cut explore redundancy (Gemini) | **P2** or **P1+P2** | −6.7 pp at *N*=10 |",
            "| Preserve EX | **P1** or **P1+P2** | Stable across models |",
            "| Full stack | **P1+P2+early stop** | "
            + (
                "DeepSeek −25% tokens at *N*=25; GPT/Gemini: use early stop alone for token cuts"
                if has_full_stack
                else "Exploratory GPT *N*=10 run suggests compounding; *N*=25 pending"
            )
            + " |",
            "",
            "## 6.8 Limitations and future work",
            "",
            "- Smoke subset (50 tasks); GPT *N*=25 EX dip under P2 may not generalise.",
        ]
    )
    if not has_full_stack:
        lines.append("- P1+P2 evaluated at *N*=10 only; full stack at *N*=25 pending.")
    lines.extend(
        [
            "- P3/P4 (`majority_vote`, cross-model ensembles) not implemented.",
            "- Discovery prompt size uncapped; overhead could improve with truncation.",
            "- Full BIRD dev scale-up not yet run.",
            "",
            "## 6.9 Summary",
            "",
            "Parallel text-to-SQL replicas waste work at multiple layers: duplicate LLM trajectories "
            "(token overhead 10–33×), duplicate explore SQL (70–88% redundancy), and duplicate "
            "database execution. **No single policy removes all three.** Early stop trims tokens "
            "after success; P1 removes redundant DB work (middleware interaction ~40–55% at *N*=10); "
            "P2 nudges exploration via shared fragments (~25–35% middleware interaction). "
            "**P1+P2** combines both—middleware interaction reaches **50–70%** at *N*=10. "
            + (
                "At *N*=25, the **full stack** (P1+P2+early stop) delivers the best token reduction "
                "for **DeepSeek** (−24.9% vs P0, EX unchanged); GPT and Gemini pay a P2 prompt "
                "premium that exceeds early-stop savings alone."
                if has_full_stack
                else "Full-stack evaluation at *N*=25 is pending."
            ),
            "",
            "---",
            "",
            "## Appendix: source artefacts",
            "",
            "| Artefact | Path |",
            "|----------|------|",
            "| Stack comparison | `runs/reports/middleware_stack.json` |",
            "| P1+P2 r=10 report | `runs/reports/p1p2_stack_r10.json` |",
        ]
    )
    if has_full_stack and fs_batch_id:
        lines.append(f"| Full stack *N*=25 batches | `runs/batches/parallel_{fs_batch_id}_*` |")
    for n in replica_counts:
        lines.append(f"| Figure 6.x (*N*={n}) | `{plots_rel / f'middleware_stack_r{n}.png'}` |")

    return "\n".join(lines) + "\n"
