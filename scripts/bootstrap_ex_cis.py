#!/usr/bin/env python3
"""Bootstrap 95% CIs on EX% for draft_paper_ieee_v4 headline comparisons.

Covers:
  - Full-500 N=3 generalisation already on disk (P1, prune, prompt-cache)
  - Smoke-50 N=10/25 policy tables cited in v4 (P1, prune, P3, P4, prompt-cache)

Paired bootstrap over matched question_ids. Offline — no API spend.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

sys.path.insert(0, str(REPO_ROOT / "scripts"))

from generate_robustness_pack import _era_name  # noqa: E402

BATCH_DIR = REPO_ROOT / "runs" / "batches"
MODELS = ("gpt-4o-mini", "gemini-2.5-flash", "deepseek-v3.2")


def _ex_by_qid(path: Path) -> dict[int, int]:
    data = json.loads(path.read_text(encoding="utf-8"))
    rows = data["rows"] if isinstance(data, dict) else data
    out: dict[int, int] = {}
    for row in rows:
        if row.get("error"):
            continue
        out[int(row["question_id"])] = int(row["ex_correct"])
    return out


def _bootstrap_mean_diff(
    treat: np.ndarray,
    control: np.ndarray,
    *,
    n_boot: int,
    seed: int,
) -> tuple[float, float, float]:
    delta = treat - control
    point = float(delta.mean() * 100.0)
    rng = np.random.default_rng(seed)
    n = len(delta)
    boots = np.empty(n_boot, dtype=float)
    for i in range(n_boot):
        idx = rng.integers(0, n, size=n)
        boots[i] = delta[idx].mean() * 100.0
    lo, hi = np.percentile(boots, [2.5, 97.5])
    return point, float(lo), float(hi)


def _resolve(name: str) -> Path | None:
    p = Path(name)
    if not p.is_absolute():
        # Repoint pre-2026-07-24 DeepSeek batches at their v4-flash re-runs so
        # no comparison straddles the model swap; no-op for GPT/Gemini. The
        # mapping lives in generate_robustness_pack.py to keep one source.
        p = BATCH_DIR / _era_name(name)
    return p if p.exists() else None


def _comparisons() -> list[tuple[str, str, str, str]]:
    """(section, label, treat_file, ctrl_file) — filenames under runs/batches."""
    rows: list[tuple[str, str, str, str]] = []

    # --- Full mini-dev (N=3): the generalisation evidence already collected ---
    for model in MODELS:
        short = {
            "gpt-4o-mini": "GPT",
            "gemini-2.5-flash": "Gemini",
            "deepseek-v3.2": "DeepSeek",
        }[model]
        base = f"parallel_baseline_full500_r3_{model}_r3_best_of_n.json"
        rows.append(
            (
                "Full-500 N=3",
                f"{short} P1 vs P0",
                f"parallel_p1_full500_r3_{model}_r3_best_of_n_p1_cache.json",
                base,
            )
        )
        rows.append(
            (
                "Full-500 N=3",
                f"{short} prune vs P0",
                f"parallel_schema_prune_iso_full500_r3_{model}_r3_best_of_n_schema_prune.json",
                base,
            )
        )
        rows.append(
            (
                "Full-500 N=3",
                f"{short} prompt-cache vs P0",
                f"parallel_pc_full500_r3_{model}_r3_best_of_n_promptcache.json",
                base,
            )
        )

    # --- Smoke P1 (N=25) vs baseline ---
    baseline_r25 = {
        "gpt-4o-mini": "parallel_gpt_baseline_redo_jun13tier2v2_baseline_r25_gpt-4o-mini_r25_best_of_n.json",
        "gemini-2.5-flash": "parallel_20260611_123711_91299c_baseline_r25_gemini-2.5-flash_r25_best_of_n.json",
        "deepseek-v3.2": "parallel_20260611_123747_60b677_baseline_r25_deepseek-v3.2_r25_best_of_n.json",
    }
    for model in MODELS:
        short = {
            "gpt-4o-mini": "GPT",
            "gemini-2.5-flash": "Gemini",
            "deepseek-v3.2": "DeepSeek",
        }[model]
        rows.append(
            (
                "Smoke N=25",
                f"{short} P1 vs P0",
                f"parallel_p1_r25_bo_{model}_r25_best_of_n_p1_cache.json",
                baseline_r25[model],
            )
        )
        rows.append(
            (
                "Smoke N=25",
                f"{short} prune vs P0",
                f"parallel_schema_prune_iso_r25_bo_{model}_r25_best_of_n_schema_prune.json",
                baseline_r25[model],
            )
        )

    # --- Prompt-cache isolation (N=25) ---
    pc_pairs = [
        ("GPT", "parallel_pc50_r25_cached_gpt-4o-mini_r25_best_of_n_promptcache.json",
         "parallel_pc50_r25_base_gpt-4o-mini_r25_best_of_n.json"),
        ("Gemini", "parallel_pc50_r25_gem_cached_gemini-2.5-flash_r25_best_of_n_promptcache.json",
         "parallel_pc50_r25_gem_base_gemini-2.5-flash_r25_best_of_n.json"),
        ("DeepSeek", "parallel_pc50_r25_ds_cached_deepseek-v3.2_r25_best_of_n_promptcache.json",
         "parallel_pc50_r25_ds_base_deepseek-v3.2_r25_best_of_n.json"),
    ]
    for short, treat, ctrl in pc_pairs:
        rows.append(("Smoke N=25", f"{short} prompt-cache vs base", treat, ctrl))

    # --- P4 vs prompt-cache baseline (N=25) ---
    for model in MODELS:
        short = {
            "gpt-4o-mini": "GPT",
            "gemini-2.5-flash": "Gemini",
            "deepseek-v3.2": "DeepSeek",
        }[model]
        rows.append(
            (
                "Smoke N=25",
                f"{short} P4 vs PC-base",
                f"parallel_suppress_iso_r25_bo_{model}_r25_best_of_n_promptcache_p4suppress.json",
                f"parallel_suppress_base_r25_bo_{model}_r25_best_of_n_promptcache.json",
            )
        )
        rows.append(
            (
                "Smoke N=25",
                f"{short} P1+P4 vs P1+PC",
                f"parallel_p1p4_r25_bo_{model}_r25_best_of_n_p1_cache_promptcache_p4suppress.json",
                f"parallel_p1_r25_bo_{model}_r25_best_of_n_p1_cache_promptcache.json",
            )
        )

    # --- P3 vs P2 stack (N=10) — model-conditioning claim ---
    for model in MODELS:
        short = {
            "gpt-4o-mini": "GPT",
            "gemini-2.5-flash": "Gemini",
            "deepseek-v3.2": "DeepSeek",
        }[model]
        rows.append(
            (
                "Smoke N=10",
                f"{short} P3 stack vs P2 stack",
                f"parallel_semantic_hybrid_r10_bo_{model}_r10_best_of_n_p1_cache_p3_semantic_early_stop_schema_prune.json",
                f"parallel_fullstack_prune_r10_bo_{model}_r10_best_of_n_p1_cache_p2_discovery_early_stop_schema_prune.json",
            )
        )

    # --- Full-500 gaps filled by run_overnight_v4_credibility.sh (if present) ---
    for model in MODELS:
        short = {
            "gpt-4o-mini": "GPT",
            "gemini-2.5-flash": "Gemini",
            "deepseek-v3.2": "DeepSeek",
        }[model]
        base = f"parallel_baseline_full500_r3_{model}_r3_best_of_n.json"
        pc = f"parallel_pc_full500_r3_{model}_r3_best_of_n_promptcache.json"
        p1 = f"parallel_p1_full500_r3_{model}_r3_best_of_n_p1_cache.json"
        p2stack = (
            f"parallel_fullstack_prune_full500_r3_{model}_r3_best_of_n_"
            "p1_cache_p2_discovery_early_stop_schema_prune.json"
        )
        rows.append(
            (
                "Full-500 N=3 (new)",
                f"{short} P4 vs PC",
                f"parallel_p4_full500_r3_{model}_r3_best_of_n_promptcache_p4suppress.json",
                pc,
            )
        )
        rows.append(
            (
                "Full-500 N=3 (new)",
                f"{short} P1+P4 vs P1",
                f"parallel_p1p4_full500_r3_{model}_r3_best_of_n_p1_cache_promptcache_p4suppress.json",
                p1,
            )
        )
        rows.append(
            (
                "Full-500 N=3 (new)",
                f"{short} P3 stack vs P2 stack",
                f"parallel_p3_full500_r3_{model}_r3_best_of_n_p1_cache_p3_semantic_early_stop_schema_prune.json",
                p2stack,
            )
        )
        rows.append(
            (
                "Full-500 N=3 (new)",
                f"{short} P3 stack vs P0",
                f"parallel_p3_full500_r3_{model}_r3_best_of_n_p1_cache_p3_semantic_early_stop_schema_prune.json",
                base,
            )
        )

    # Composition stack at full-500 (queued after P3)
    for model in MODELS:
        short = {
            "gpt-4o-mini": "GPT",
            "gemini-2.5-flash": "Gemini",
            "deepseek-v3.2": "DeepSeek",
        }[model]
        base = f"parallel_baseline_full500_r3_{model}_r3_best_of_n.json"
        p1p4 = (
            f"parallel_p1p4_full500_r3_{model}_r3_best_of_n_"
            "p1_cache_promptcache_p4suppress.json"
        )
        compose = (
            f"parallel_compose_full500_r3_{model}_r3_best_of_n_"
            "p1_cache_promptcache_early_stop_schema_prune_p4suppress.json"
        )
        rows.append(
            (
                "Full-500 N=3 (compose)",
                f"{short} compose vs P0",
                compose,
                base,
            )
        )
        rows.append(
            (
                "Full-500 N=3 (compose)",
                f"{short} compose vs P1+P4",
                compose,
                p1p4,
            )
        )
    rows.append(
        (
            "Full-500 N=3 (compose)",
            "GPT compose+P3 vs compose",
            "parallel_compose_p3_full500_r3_gpt-4o-mini_r3_best_of_n_"
            "p1_cache_p3_semantic_promptcache_early_stop_schema_prune_p4suppress.json",
            "parallel_compose_full500_r3_gpt-4o-mini_r3_best_of_n_"
            "p1_cache_promptcache_early_stop_schema_prune_p4suppress.json",
        )
    )

    return rows


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--n-boot", type=int, default=10_000)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument(
        "--out",
        type=Path,
        default=REPO_ROOT / "runs" / "reports" / "bootstrap_ex_cis_v4.md",
    )
    args = parser.parse_args()

    sections: dict[str, list[str]] = {}
    summary_lines: list[str] = []
    any_ok = False

    for section, label, treat_name, ctrl_name in _comparisons():
        treat_path = _resolve(treat_name)
        ctrl_path = _resolve(ctrl_name)
        if treat_path is None or ctrl_path is None:
            miss = "treat" if treat_path is None else "ctrl"
            row = f"| {label} | — | — | — | — | missing {miss} |"
            sections.setdefault(section, []).append(row)
            continue
        t_map = _ex_by_qid(treat_path)
        c_map = _ex_by_qid(ctrl_path)
        qids = sorted(set(t_map) & set(c_map))
        if len(qids) < 5:
            row = f"| {label} | {len(qids)} | — | — | — | too few matched |"
            sections.setdefault(section, []).append(row)
            continue
        treat = np.array([t_map[q] for q in qids], dtype=float)
        control = np.array([c_map[q] for q in qids], dtype=float)
        diff, lo, hi = _bootstrap_mean_diff(
            treat, control, n_boot=args.n_boot, seed=args.seed
        )
        # Flag CIs that include 0 (statistically inconclusive on EX)
        flag = "" if (lo > 0 or hi < 0) else " †"
        row = (
            f"| {label} | {len(qids)} | {100 * treat.mean():.1f} | "
            f"{100 * control.mean():.1f} | {diff:+.1f}{flag} | [{lo:+.1f}, {hi:+.1f}] |"
        )
        sections.setdefault(section, []).append(row)
        any_ok = True
        msg = (
            f"[{section}] {label}: n={len(qids)} "
            f"Δ={diff:+.1f} pp CI=[{lo:+.1f}, {hi:+.1f}]{flag}"
        )
        print(msg, flush=True)
        summary_lines.append(msg)

    lines = [
        "# Bootstrap 95% CIs — draft_paper_ieee_v4 headlines",
        "",
        f"n_boot={args.n_boot}, seed={args.seed}. Diff = treatment − control (pp EX).",
        "† = 95% CI includes 0 (EX delta not distinguishable from noise on this sample).",
        "",
    ]
    for section, rows in sections.items():
        lines.append(f"## {section}")
        lines.append("")
        lines.append("| Comparison | n | Treat EX% | Ctrl EX% | Δ pp | 95% CI |")
        lines.append("|---|---:|---:|---:|---:|---|")
        lines.extend(rows)
        lines.append("")

    lines.append(
        "*Paired bootstrap over matched question_ids. "
        "Accuracy-neutral policies are *expected* to show † on EX; "
        "use token/DB metrics for those claims. "
        "Full-500 rows are the strongest generalisation evidence currently on disk; "
        "P3/P4 still lack full-500 counterparts.*"
    )
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"wrote {args.out}")
    return 0 if any_ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
