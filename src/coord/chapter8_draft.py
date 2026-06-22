"""Generate thesis Chapter 8 draft — temperature and stagger scheduling."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from src.coord.baseline_plots import MODEL_LABELS
from src.coord.schedule_analysis import SCHEDULE_SCENARIOS, build_schedule_comparisons


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


def _scenario_table(scenarios: list[dict[str, Any]], *, t0: dict[str, Any], table_num: int) -> str:
    lines = [
        f"**Table 8.{table_num}.** Schedule scenarios (EX, redundancy, tokens).",
        "",
        "| Scenario | EX % | Redundancy % | Tokens | Δ tok vs t0 |",
        "|----------|-----:|-------------:|-------:|------------:|",
    ]
    for s in scenarios:
        sc = s.get("scenario", "—")
        if sc == "t0":
            tok_d = "—"
        else:
            from src.coord.schedule_analysis import compare_row

            tok_d = _fmt_delta(compare_row(t0, s).get("token_delta_pct"))
        lines.append(
            f"| {sc} | {_fmt_pct(s.get('ex_accuracy_pct'))} | "
            f"{_fmt_pct(s.get('avg_explore_redundancy_pct'))} | "
            f"{s.get('total_tokens', 0):,} | {tok_d} |"
        )
    return "\n".join(lines)


def generate_chapter8_markdown(
    data: dict[str, Any],
    *,
    generated_at: str | None = None,
) -> str:
    by_model = data.get("by_model", {})
    if not by_model:
        raise ValueError("No schedule sweep data for Chapter 8")

    ts = generated_at or datetime.now(timezone.utc).strftime("%Y-%m-%d")
    sweep_id = data.get("sweep_id", "sched_r10_bo")
    n = data.get("n_replicas", 10)

    lines: list[str] = [
        "# Chapter 8: Temperature and Staggered Replicas",
        "",
        f"*Draft generated {ts} from schedule sweep `{sweep_id}`. "
        f"Regenerate with `uv run python scripts/generate_chapter8_draft.py`.*",
        "",
        "## 8.1 Motivation",
        "",
        "Chapter 2 noted that all prior experiments used **temperature 0**, so replicas "
        "explored nearly identically—high string-level redundancy (65–88%) despite independent "
        "LLM trajectories. Chapter 6–7 optimised *what* middleware shares (fragments, facts, cache); "
        "this chapter asks *when* and *how diversely* replicas run.",
        "",
        "Two levers are evaluated on the same **P1 + early stop + hybrid schema prune** stack "
        "(no P2 discovery board, no P3 semantic store):",
        "",
        "1. **Temperature** — uniform `T ∈ {0, 0.3, 0.7}` or a **ladder** (`T + i×0.2` per agent).",
        "2. **Stagger** — agent *i* waits `i×2s` or `i×1` turn-poll before its first LLM call, "
        "allowing earlier replicas to populate the shared SQL cache.",
        "",
        "Hypothesis: higher temperature or stagger reduces explore redundancy; stagger may "
        "improve cache hit rates without the prompt cost of P2/P3 injection.",
        "",
        "## 8.2 Policy and experimental setup",
        "",
        f"- **Sweep ID:** `{sweep_id}`, *N*={n}, 50-task smoke subset, `best_of_n`.",
        f"- **Scenarios:** {', '.join(f'`{s}`' for s in SCHEDULE_SCENARIOS)}.",
        "- **Infrastructure:** `ReplicaScheduleConfig` in `src/coord/replica_schedule.py`; "
        "traces log `replica_start`, `temperature`, and `stagger_complete`.",
        "",
        "## 8.3 Results",
        "",
    ]

    table_num = 1
    for model in sorted(by_model):
        entry = by_model[model]
        label = _model_label(model)
        scenarios = entry.get("scenarios", [])
        t0 = entry.get("t0", {})
        best = entry.get("best", {})
        p2 = entry.get("p2_full_stack_prune")
        vs_p2 = entry.get("best_vs_p2_prune")

        lines.extend([f"### 8.3.{table_num} {_model_label(model)}", ""])
        lines.append(_scenario_table(scenarios, t0=t0, table_num=table_num))
        lines.append("")
        lines.append(
            f"**Best scenario:** `{best.get('scenario')}` — EX **{_fmt_pct(best.get('ex_accuracy_pct'))}%**, "
            f"{best.get('total_tokens', 0):,} tokens, redundancy "
            f"{_fmt_pct(best.get('avg_explore_redundancy_pct'))}%."
        )
        lines.append("")

        if p2 and vs_p2:
            lines.extend(
                [
                    f"Compared to **P2 full stack+prune** (Chapter 6): EX "
                    f"{vs_p2.get('ex_delta_pp', 0):+.0f} pp, tokens "
                    f"{_fmt_delta(vs_p2.get('token_delta_pct'))}.",
                    "",
                ]
            )
        table_num += 1

    # Narrative blocks from data
    gem = by_model.get("gemini-2.5-flash", {})
    gpt = by_model.get("gpt-4o-mini", {})
    ds = by_model.get("deepseek-v3.2", {})
    g_best = gem.get("best", {})
    g_t0 = gem.get("t0", {})
    gpt_best = gpt.get("best", {})
    ds_best = ds.get("best", {})

    lines.extend(
        [
            "## 8.4 Discussion",
            "",
        ]
    )

    if g_best and g_t0:
        lines.extend(
            [
                "**Gemini 2.5 Flash** responds strongly to both levers. Uniform T=0.3/T=0.7 "
                f"raises EX from {_fmt_pct(g_t0.get('ex_accuracy_pct'))}% to "
                f"{_fmt_pct(g_best.get('ex_accuracy_pct'))}% while cutting redundancy from "
                f"{_fmt_pct(g_t0.get('avg_explore_redundancy_pct'))}% to "
                f"{_fmt_pct(g_best.get('avg_explore_redundancy_pct'))}%. "
                f"Combined **t03_stag2s** achieves the lowest redundancy on the subset with "
                "large token savings—early agents populate P1 cache before late replicas start.",
                "",
            ]
        )

    if gpt_best:
        lines.extend(
            [
                "**GPT-4o mini** shows smaller EX spread (58–64%) but redundancy falls from "
                "~82% at T=0 to ~39–50% under T=0.7, ladder, or t03_stag2s. "
                "Best EX (**ladder** or **t03_stag2s**, 64%) exceeds prior P2+prune (56%) on "
                "this stack without P2 discovery—suggesting diversity substitutes for fragment "
                "hints for this model. Token spend remains higher than P3-only (Chapter 7).",
                "",
            ]
        )

    if ds_best:
        lines.extend(
            [
                "**DeepSeek V3.2** gains +4 pp EX with **temperature ladder** (68% vs 64% t0) "
                "and reduces tokens modestly under stagger scenarios, but total tokens (~5.5–7M) "
                "remain far above P2+prune (5.25M). Schedule tuning does not fix DeepSeek's "
                "token budget problem; P2+prune remains preferred.",
                "",
            ]
        )

    lines.extend(
        [
            "**Temperature vs stagger.** Uniform higher T reduces redundancy by diversifying "
            "SQL strings; stagger reduces *concurrent* duplicate probes and raises effective "
            "cache hit rate. **Combined t03_stag2s** is best for Gemini on both metrics.",
            "",
            "**Relation to P2/P3.** Schedule changes operate *before* the LLM loop; P2/P3 inject "
            "peer context *during* the loop. They are complementary: Gemini may benefit from "
            "t03_stag2s *plus* P2 discovery (not yet evaluated).",
            "",
            "## 8.5 Recommendations",
            "",
            "| Model | Prefer schedule | Rationale |",
            "|-------|---------------|-----------|",
        ]
    )

    for model in sorted(by_model):
        best = by_model[model].get("best", {})
        p2 = by_model[model].get("p2_full_stack_prune")
        vs_p2 = by_model[model].get("best_vs_p2_prune")
        label = _model_label(model)
        sc = best.get("scenario", "t0")
        rationale = f"Best EX/tokens on subset ({best.get('ex_accuracy_pct')}% EX)."
        if p2 and vs_p2:
            ex_d = vs_p2.get("ex_delta_pp", 0)
            tok_d = vs_p2.get("token_delta_pct")
            if ex_d >= 0 and tok_d is not None and tok_d <= 0:
                rationale = f"Beats P2+prune on EX ({ex_d:+.0f} pp) and tokens ({tok_d:+.1f}%)."
            elif ex_d > 0:
                rationale = f"+{ex_d:.0f} pp EX vs P2+prune; tokens {_fmt_delta(tok_d)}."
            else:
                rationale = f"Does not beat P2+prune on EX; use P2+prune for deployment."
        lines.append(f"| {label} | `{sc}` | {rationale} |")

    lines.extend(
        [
            "",
            "## 8.6 Limitations",
            "",
            "- Smoke subset (50 tasks); temperature effects may shrink on full BIRD dev.",
            "- Stagger turn-poll uses fixed 1s intervals—not wall-clock synchronisation with peers.",
            "- Schedule sweep omits P2/P3; best combined stack not yet run.",
            "- GPT ladder raises EX but not token spend vs t0 on all scenarios.",
            "",
            "## 8.7 Summary",
            "",
            "Replica **temperature** and **stagger** are cheap coordination knobs compared to "
            "P2/P3 middleware. On Gemini, **t03_stag2s** delivers the best redundancy and token "
            "trade-off; on GPT, **ladder** or **t03_stag2s** improves EX over T=0 without "
            "discovery injection; DeepSeek sees modest EX gains from ladder but remains token-heavy. "
            "Chapter 2's open question—whether T>0 reduces redundancy—is **confirmed**; the "
            "deployment rule remains **model-specific**, as in Chapters 6–7.",
            "",
            "---",
            "",
            "## Appendix: source artefacts",
            "",
            "| Artefact | Path |",
            "|----------|------|",
            f"| Schedule batches | `runs/batches/parallel_{sweep_id}_*` |",
            "| Comparison report | `runs/reports/schedule_sweep.json` |",
            "| Compare script | `scripts/compare_schedule.py` |",
            "| Replica schedule | `src/coord/replica_schedule.py` |",
            "",
        ]
    )

    return "\n".join(lines) + "\n"
