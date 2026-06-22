"""Generate thesis Chapter 9 — cross-chapter synthesis and deployment rules."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from src.coord.baseline_plots import MODEL_LABELS
from src.coord.synthesis_analysis import BEST_SCHEDULE_SCENARIO, SCHED_P2_GEMINI_BATCH_ID


def _label(model_key: str) -> str:
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


def _fmt_pp(value: float | None) -> str:
    if value is None:
        return "—"
    sign = "+" if value > 0 else ""
    return f"{sign}{value:.1f}pp"


def _stack_row(summary: dict[str, Any], *, label: str) -> str:
    return (
        f"| {label} | {_fmt_pct(summary.get('ex_accuracy_pct'))} | "
        f"{_fmt_pct(summary.get('avg_explore_redundancy_pct'))} | "
        f"{summary.get('total_tokens', 0):,} |"
    )


def generate_chapter9_markdown(
    data: dict[str, Any],
    *,
    generated_at: str | None = None,
) -> str:
    by_model = data.get("by_model", {})
    if not by_model:
        raise ValueError("No synthesis data for Chapter 9")

    ts = generated_at or datetime.now(timezone.utc).strftime("%Y-%m-%d")
    n = data.get("n_replicas", 10)
    sched_p2 = data.get("sched_p2_gemini_followup")

    lines: list[str] = [
        "# Chapter 9: Synthesis and Deployment Rules",
        "",
        f"*Draft generated {ts} from Chapters 2–8 batch comparisons and the "
        f"Gemini schedule+P2 follow-up (`{SCHED_P2_GEMINI_BATCH_ID}`). "
        f"Regenerate with `uv run python scripts/generate_chapter9_draft.py`.*",
        "",
        "## 9.1 Problem recap",
        "",
        "Chapter 2 established that independent parallel replicas waste coordination budget "
        "at four layers: duplicate LLM trajectories (token overhead 10–33× at *N*=10–25), "
        "duplicate explore SQL strings (70–88% redundancy), duplicate SQLite execution, and "
        "full schema context re-sent every turn. Subsequent chapters evaluated policies that "
        "target each layer—but **no single middleware removes all four**, and policies that "
        "help one model can hurt another.",
        "",
        "## 9.2 Policy taxonomy",
        "",
        "| Layer | Policy | When it helps | Primary cost |",
        "|-------|--------|---------------|--------------|",
        "| Turn trimming | Early stop (Ch. 3) | Post-success siblings | None; misses pre-success dupes |",
        "| DB execution | P1 shared cache (Ch. 4) | Identical explore SQL | Memory; no LLM savings alone |",
        "| Explore hints | P2 discovery board (Ch. 5) | Models that use fragment hints (Gemini) | Prompt growth every turn |",
        "| Outcome facts | P3 semantic store (Ch. 7) | GPT; token-efficient broadcasting | Model-dependent fact volume |",
        "| Prompt size | Hybrid schema prune (Ch. 6) | All models | Offline recall dependency |",
        "| Replica diversity | Temperature / stagger (Ch. 8) | Redundant T=0 replicas | Scheduling complexity |",
        "",
        "Policies operate at different points in the loop: **schedule** (before first LLM call), "
        "**cache** (at SQL execution), **injection** (before each LLM turn), **early stop** "
        "(after EX=1). Stacking without understanding these interaction points produced "
        "counter-intuitive results throughout the thesis.",
        "",
        "## 9.3 Cross-model stack comparison (*N*=10)",
        "",
        "Table 9.1 summarises the strongest candidate from each chapter family on the "
        "50-task smoke subset.",
        "",
        "**Table 9.1.** Candidate stacks per model at *N*=10.",
        "",
        "| Model | Stack | EX % | Redundancy % | Tokens |",
        "|-------|-------|-----:|-------------:|-------:|",
    ]

    for model in sorted(by_model):
        stacks = by_model[model].get("stacks", {})
        label = _label(model)
        if stacks.get("p2_prune"):
            lines.append(_stack_row(stacks["p2_prune"], label=f"{label} — P2+prune"))
        if stacks.get("p3_only"):
            lines.append(_stack_row(stacks["p3_only"], label=f"{label} — P3"))
        if stacks.get("best_schedule"):
            sc = stacks["best_schedule"].get("scenario", BEST_SCHEDULE_SCENARIO.get(model, "?"))
            lines.append(_stack_row(stacks["best_schedule"], label=f"{label} — `{sc}`"))
    lines.append("")

    lines.extend(
        [
            "**Headline conflicts resolved:**",
            "",
            "- **Gemini:** Chapter 6 favoured P2+prune (76% EX); Chapter 8 showed schedule-only "
            "`t03_stag2s` beats it (82% EX, −57% tokens). P2 is not required when stagger + "
            "temperature already diversify exploration.",
            "- **GPT:** Chapter 6 P2+prune loses 2 pp EX vs P0; Chapter 7 P3 gains +4 pp with "
            "−6.5% tokens. Chapter 8 schedule raises EX to 64% but at +22% tokens vs P2+prune "
            "and far above P3.",
            "- **DeepSeek:** P2+prune remains lowest-cost; P3 adds +42.5% tokens (Ch. 7). "
            "Schedule ladder improves EX (+4 pp) but not token budget.",
            "",
            "## 9.4 Gemini follow-up: schedule + P2 discovery",
            "",
            "Chapter 8 §8.6 noted that the best combined stack (schedule + P2) was not evaluated. "
            f"We ran **`{SCHED_P2_GEMINI_BATCH_ID}`**: Gemini 2.5 Flash at *N*=10 with "
            "`t03_stag2s` schedule **plus** P2 discovery board (P1 + early stop + hybrid prune).",
            "",
        ]
    )

    if sched_p2:
        base = sched_p2["baseline"]
        var = sched_p2["variant"]
        lines.extend(
            [
                "**Table 9.2.** `t03_stag2s` + P2 vs schedule-only and P2+prune (Gemini).",
                "",
                "| Stack | EX % | Redundancy % | Tokens |",
                "|-------|-----:|-------------:|-------:|",
                _stack_row(base, label="`t03_stag2s` only (Ch. 8)"),
                _stack_row(var, label="`t03_stag2s` + P2 (follow-up)"),
            ]
        )
        gem_stacks = by_model.get("gemini-2.5-flash", {}).get("stacks", {})
        if gem_stacks.get("p2_prune"):
            lines.append(_stack_row(gem_stacks["p2_prune"], label="P2+prune (Ch. 6)"))
        lines.extend(
            [
                "",
                f"- **EX:** {_fmt_pp(sched_p2.get('ex_delta_pp'))} vs schedule-only "
                f"({_fmt_pct(var.get('ex_accuracy_pct'))}% vs {_fmt_pct(base.get('ex_accuracy_pct'))}%).",
                f"- **Redundancy:** {_fmt_pp(sched_p2.get('redundancy_delta_pp'))} vs schedule-only.",
                f"- **Tokens:** {_fmt_delta(sched_p2.get('token_delta_pct'))} vs schedule-only "
                f"({var.get('total_tokens', 0):,} vs {base.get('total_tokens', 0):,}).",
                "",
                "**Finding:** Adding P2 discovery on top of `t03_stag2s` **does not improve** the "
                "Chapter 8 winner. EX drops 2 pp with essentially flat tokens (+1%). Schedule "
                "diversity already substitutes for P2 fragment hints on Gemini; dual injection "
                "adds prompt cost without accuracy gain. P2+prune remains dominated on all three "
                "metrics by schedule-only.",
                "",
            ]
        )
    else:
        lines.append("*Follow-up batch not found; run `sched_p2_t03_stag2s_r10_bo` for Gemini.*\n")

    lines.extend(
        [
            "## 9.5 Model-conditioned deployment rules",
            "",
            "**Table 9.3.** Recommended stacks at *N*=10 (50-task smoke subset).",
            "",
            "| Model | Recommended stack | EX % | Tokens | Notes |",
            "|-------|-------------------|-----:|-------:|-------|",
        ]
    )

    for model in sorted(by_model):
        rec = by_model[model].get("recommendation", {})
        chosen = rec.get("recommended") or {}
        lines.append(
            f"| {_label(model)} | {rec.get('stack_label', '—')} | "
            f"{_fmt_pct(chosen.get('ex_accuracy_pct'))} | "
            f"{chosen.get('total_tokens', 0):,} | "
            f"{_short_note(rec.get('rationale', ''))} |"
        )
    lines.append("")

    lines.extend(
        [
            "### Per-model rationale",
            "",
        ]
    )

    for model in sorted(by_model):
        rec = by_model[model].get("recommendation", {})
        lines.extend([f"#### {_label(model)}", "", rec.get("rationale", ""), ""])
        alts = rec.get("alternatives") or []
        if alts:
            lines.append("**Alternatives considered:**")
            for alt in alts:
                role = alt.get("role", alt.get("stack_role", "?"))
                lines.append(
                    f"- `{role}`: {_fmt_pct(alt.get('ex_accuracy_pct'))}% EX, "
                    f"{alt.get('total_tokens', 0):,} tokens"
                )
            lines.append("")

    lines.extend(
        [
            "## 9.6 Decision flow",
            "",
            "```",
            "For each model at deployment:",
            "  1. Always enable: P1 cache + early stop + hybrid schema prune",
            "  2. If Gemini → use t03_stag2s schedule; skip P2",
            "  3. If GPT     → use P3 semantic store; skip P2",
            "  4. If DeepSeek → use P2 discovery; skip P3; schedule optional for EX only",
            "```",
            "",
            "This is a **heuristic from the smoke subset**, not a universal law. The unifying "
            "principle: match coordination to how each model responds to shared syntactic hints "
            "(P2) vs distilled outcome facts (P3) vs pre-loop diversity (schedule).",
            "",
            "## 9.7 Limitations",
            "",
            "- **50-task smoke subset**; deployment rules may shift on full BIRD dev.",
            f"- ***N*={n} only** for schedule and P3 synthesis; *N*=25 gaps remain (Ch. 6).",
            "- **GPT schedule + P3** and **DeepSeek schedule + P2** not run.",
            "- **P4** (phase-aware sharing, cross-model ensembles) not implemented.",
            "- **DeepSeek P3 token anomaly** (+42.5%) may include timeout retries.",
            "",
            "## 9.8 Summary",
            "",
            "Parallel text-to-SQL coordination has no single optimal stack. The thesis evaluated "
            "policies across execution (cache), turn (early stop), prompt (P2/P3/prune), and "
            "schedule (temperature/stagger) layers. **Gemini** benefits most from cheap schedule "
            "knobs—`t03_stag2s` delivers 82% EX at under half the tokens of P2+prune, and adding "
            "P2 on top does not help. **GPT** benefits from P3 outcome facts over P2 fragments. "
            "**DeepSeek** remains P2+prune on cost grounds. The deployment rule is "
            "**model-conditioned**: token-efficient parallel agents require matching middleware "
            "to model behaviour, not applying the fullest stack uniformly.",
            "",
            "---",
            "",
            "## Appendix: source artefacts",
            "",
            "| Artefact | Path |",
            "|----------|------|",
            "| P2+prune batches | `runs/batches/parallel_fullstack_prune_r10_bo_*` |",
            "| P3 batches | `runs/batches/parallel_semantic_hybrid_r10_bo_*` |",
            "| Schedule sweep | `runs/batches/parallel_sched_r10_bo_*` |",
            f"| Gemini schedule+P2 | `runs/batches/parallel_{SCHED_P2_GEMINI_BATCH_ID}_*` |",
            "| Synthesis loader | `src/coord/synthesis_analysis.py` |",
            "| Generate script | `scripts/generate_chapter9_draft.py` |",
            "",
        ]
    )

    return "\n".join(lines) + "\n"


def _short_note(text: str, *, max_len: int = 80) -> str:
    one_line = " ".join(text.split())
    if len(one_line) <= max_len:
        return one_line
    return one_line[: max_len - 3] + "..."
