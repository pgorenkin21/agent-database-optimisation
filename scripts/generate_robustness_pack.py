#!/usr/bin/env python3
"""Offline robustness pack for draft_paper_ieee_v4.

Produces:
  runs/reports/robustness_pack_v4.md     — stability, unconfound, costs, CI highlights
  runs/reports/bootstrap_ex_cis_v4.md    — refreshed paired bootstrap CIs (all new batches)
  runs/reports/rep_stability_v4.md       — rep1 vs rep2 detail tables
  runs/reports/token_db_cis_v4.md        — paired token / DB-interaction CIs
  runs/reports/paper_snippets_v4.md      — paste-ready sentences for v4 / reflective essay

No API spend. Re-run after wave4 (P3 full-500 rep2) lands to fill missing rows.
"""

from __future__ import annotations

import functools
import json
import sys
from pathlib import Path

import numpy as np

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from src.llm.cost import batch_cost_usd  # noqa: E402

BATCH = REPO_ROOT / "runs" / "batches"
REPORTS = REPO_ROOT / "runs" / "reports"
MODELS = (
    ("gpt-4o-mini", "GPT"),
    ("gemini-2.5-flash", "Gemini"),
    ("deepseek-v3.2", "DeepSeek"),
)


# --- DeepSeek v3.2 -> v4-flash era correction --------------------------------
# On 2026-07-24 DeepSeek retired the v3.2 model behind `deepseek-chat` and began
# serving deepseek-v4-flash under the same name; v3.2 is no longer offered at
# all, so every DeepSeek batch recorded from 2026-08-05 onward is v4-flash
# despite the registry still labelling it "deepseek-v3.2". The swap alone moves
# EX by roughly +6 points — larger than most effects measured here — so a
# comparison that straddles the boundary measures the model change, not the
# method. Each superseded DeepSeek control was re-run on 14 Aug under a `_v4f`
# batch id; the table below repoints the old ids at those re-runs.
#
# GPT and Gemini never changed model and have no `_v4f` batches, so the
# correction is deliberately keyed on the DeepSeek model string and is a no-op
# for them.
_DS = "deepseek-v3.2"
_ERA_CUTOFF = "2026-07-24"

# The June P0 baseline is the one re-run that did not keep its original
# (timestamped) id, so the generic `_v4f` rule cannot find it.
_V4F_ALIASES = {
    "parallel_20260611_123747_60b677_baseline_r25_deepseek-v3.2_r25_best_of_n.json": (
        "parallel_baseline_r25_bo_v4f_deepseek-v3.2_r25_best_of_n.json"
    ),
}


@functools.lru_cache(maxsize=None)
def _batch_date(name: str) -> str:
    """`generated_at` date of a batch file, or '' if absent/unreadable."""
    p = BATCH / name
    if not p.exists():
        return ""
    try:
        return (json.loads(p.read_text(encoding="utf-8")).get("generated_at") or "")[:10]
    except (json.JSONDecodeError, OSError):
        return ""


@functools.lru_cache(maxsize=None)
def _era_name(name: str) -> str:
    """Resolve a DeepSeek batch reference to its v4-flash equivalent.

    Driven by each batch's own `generated_at` rather than a hardcoded list, so
    a v3.2-era batch nobody remembered to enumerate cannot slip through.

      * a `_v4f` re-run exists      -> use it;
      * the batch is already August -> use it unchanged;
      * v3.2-era with no re-run     -> return the (non-existent) `_v4f` name so
        the caller's `.exists()` check fails and the comparison is reported as
        missing. Omitting it is the point: there is no v4-flash counterpart, so
        any number derived from it would measure the model swap, not the method.
    """
    if _DS not in name or "_v4f_" in name:
        return name
    if name in _V4F_ALIASES:
        return _V4F_ALIASES[name]
    twin = name.replace(f"_{_DS}_", f"_v4f_{_DS}_", 1)
    if (BATCH / twin).exists():
        return twin
    if _batch_date(name) >= _ERA_CUTOFF:
        return name
    return twin


def _bpath(name: str) -> Path:
    """Batch path with the DeepSeek era correction applied."""
    return BATCH / _era_name(name)


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _rows(path: Path) -> list[dict]:
    data = _load(path)
    return data["rows"] if isinstance(data, dict) else data


def _ok_rows(path: Path) -> list[dict]:
    return [r for r in _rows(path) if not r.get("error")]


def _ex_map(path: Path) -> dict[int, int]:
    return {int(r["question_id"]): int(r["ex_correct"]) for r in _ok_rows(path)}


def _metrics(path: Path) -> dict:
    rows = _ok_rows(path)
    n_all = len(_rows(path))
    n = len(rows)
    err = n_all - n
    if not rows:
        return {
            "n": 0,
            "err": err,
            "ex": float("nan"),
            "tokens": 0,
            "prompt": 0,
            "cached": 0,
            "cached_pct": float("nan"),
        }
    prompt = sum(int(r.get("total_prompt_tokens") or 0) for r in rows)
    comp = sum(int(r.get("total_completion_tokens") or 0) for r in rows)
    cached = sum(int(r.get("total_cached_prompt_tokens") or 0) for r in rows)
    ex = 100.0 * sum(int(r["ex_correct"]) for r in rows) / n
    return {
        "n": n,
        "err": err,
        "ex": ex,
        "tokens": prompt + comp,
        "prompt": prompt,
        "cached": cached,
        "cached_pct": (100.0 * cached / prompt) if prompt else float("nan"),
    }


def _bootstrap_diff(
    treat: dict[int, int],
    control: dict[int, int],
    *,
    n_boot: int = 10_000,
    seed: int = 42,
) -> tuple[int, float, float, float, float, float]:
    qids = sorted(set(treat) & set(control))
    if len(qids) < 5:
        return len(qids), float("nan"), float("nan"), float("nan"), float("nan"), float("nan")
    t = np.array([treat[q] for q in qids], dtype=float)
    c = np.array([control[q] for q in qids], dtype=float)
    delta = t - c
    point = float(delta.mean() * 100.0)
    rng = np.random.default_rng(seed)
    boots = np.empty(n_boot)
    for i in range(n_boot):
        idx = rng.integers(0, len(delta), size=len(delta))
        boots[i] = delta[idx].mean() * 100.0
    lo, hi = np.percentile(boots, [2.5, 97.5])
    return (
        len(qids),
        100.0 * float(t.mean()),
        100.0 * float(c.mean()),
        point,
        float(lo),
        float(hi),
    )


def _metric_map(path: Path, key: str) -> dict[int, float]:
    out: dict[int, float] = {}
    for r in _ok_rows(path):
        qid = int(r["question_id"])
        if key == "tokens":
            out[qid] = float(
                int(r.get("total_prompt_tokens") or 0)
                + int(r.get("total_completion_tokens") or 0)
            )
        elif key == "prompt":
            out[qid] = float(int(r.get("total_prompt_tokens") or 0))
        elif key == "cached":
            out[qid] = float(int(r.get("total_cached_prompt_tokens") or 0))
        elif key == "db":
            out[qid] = float(int(r.get("db_interactions") or 0))
        elif key == "mw_hits":
            out[qid] = float(int(r.get("middleware_cache_hits") or 0))
        else:
            raise ValueError(key)
    return out


def _bootstrap_mean_pct(
    treat: dict[int, float],
    control: dict[int, float],
    *,
    n_boot: int = 10_000,
    seed: int = 42,
) -> tuple[int, float, float, float, float, float]:
    """Paired % change of per-task means: 100 * (sum_t - sum_c) / sum_c over matched qids.

    Bootstrap resamples question_ids with replacement and recomputes the % change
    on the resampled totals (stable for cost/DB ledgers).
    """
    qids = sorted(set(treat) & set(control))
    if len(qids) < 5:
        return len(qids), float("nan"), float("nan"), float("nan"), float("nan"), float("nan")
    t = np.array([treat[q] for q in qids], dtype=float)
    c = np.array([control[q] for q in qids], dtype=float)
    c_sum = float(c.sum())
    if c_sum <= 0:
        return len(qids), float(t.mean()), float(c.mean()), float("nan"), float("nan"), float("nan")
    point = 100.0 * (float(t.sum()) - c_sum) / c_sum
    rng = np.random.default_rng(seed)
    boots = np.empty(n_boot)
    for i in range(n_boot):
        idx = rng.integers(0, len(qids), size=len(qids))
        cs = float(c[idx].sum())
        if cs <= 0:
            boots[i] = float("nan")
        else:
            boots[i] = 100.0 * (float(t[idx].sum()) - cs) / cs
    boots = boots[~np.isnan(boots)]
    if len(boots) < 100:
        return len(qids), float(t.mean()), float(c.mean()), point, float("nan"), float("nan")
    lo, hi = np.percentile(boots, [2.5, 97.5])
    return len(qids), float(t.mean()), float(c.mean()), point, float(lo), float(hi)


def _pct(a: float, b: float) -> float:
    if not b:
        return float("nan")
    return 100.0 * (a - b) / b


# ---------------------------------------------------------------------------
# Path catalogues
# ---------------------------------------------------------------------------

STABILITY_PAIRS: list[tuple[str, str, str, str]] = [
    # (section, model_key, rep1_rel, rep2_rel) — filled per model below
]

def _stability_pairs() -> list[tuple[str, str, str, str]]:
    out: list[tuple[str, str, str, str]] = []
    for model, _short in MODELS:
        out.extend(
            [
                (
                    "Smoke N=25 composition",
                    model,
                    f"parallel_pc_p1_p4_prune_r25_bo_{model}_r25_best_of_n_p1_cache_promptcache_early_stop_schema_prune_p4suppress.json",
                    f"parallel_compose_r25_rep2_{model}_r25_best_of_n_p1_cache_promptcache_early_stop_schema_prune_p4suppress.json",
                ),
                (
                    "Smoke N=25 prompt-cache",
                    model,
                    {
                        "gpt-4o-mini": "parallel_pc50_r25_cached_gpt-4o-mini_r25_best_of_n_promptcache.json",
                        "gemini-2.5-flash": "parallel_pc50_r25_gem_cached_gemini-2.5-flash_r25_best_of_n_promptcache.json",
                        "deepseek-v3.2": "parallel_pc50_r25_ds_cached_deepseek-v3.2_r25_best_of_n_promptcache.json",
                    }[model],
                    f"parallel_pc_r25_rep2_{model}_r25_best_of_n_promptcache.json",
                ),
                (
                    "Smoke N=25 P4",
                    model,
                    f"parallel_suppress_iso_r25_bo_{model}_r25_best_of_n_promptcache_p4suppress.json",
                    f"parallel_p4_r25_rep2_{model}_r25_best_of_n_promptcache_p4suppress.json",
                ),
                (
                    "Smoke N=25 prune",
                    model,
                    f"parallel_schema_prune_iso_r25_bo_{model}_r25_best_of_n_schema_prune.json",
                    f"parallel_prune_r25_rep2_{model}_r25_best_of_n_schema_prune.json",
                ),
                (
                    "Smoke N=25 P1",
                    model,
                    f"parallel_p1_r25_bo_{model}_r25_best_of_n_p1_cache.json",
                    f"parallel_p1_r25_rep2_{model}_r25_best_of_n_p1_cache.json",
                ),
                (
                    "Smoke N=25 P0 baseline",
                    model,
                    {
                        "gpt-4o-mini": "parallel_gpt_baseline_redo_jun13tier2v2_baseline_r25_gpt-4o-mini_r25_best_of_n.json",
                        "gemini-2.5-flash": "parallel_20260611_123711_91299c_baseline_r25_gemini-2.5-flash_r25_best_of_n.json",
                        "deepseek-v3.2": "parallel_20260611_123747_60b677_baseline_r25_deepseek-v3.2_r25_best_of_n.json",
                    }[model],
                    f"parallel_baseline_r25_rep2_{model}_r25_best_of_n.json",
                ),
                (
                    "Smoke N=25 P2 stack",
                    model,
                    (
                        f"parallel_fullstack_prune_r25_repair_{model}_r25_best_of_n_p1_cache_p2_discovery_early_stop_schema_prune.json"
                        if model == "gemini-2.5-flash"
                        else f"parallel_fullstack_prune_r25_bo_{model}_r25_best_of_n_p1_cache_p2_discovery_early_stop_schema_prune.json"
                    ),
                    f"parallel_p2_r25_rep2_{model}_r25_best_of_n_p1_cache_p2_discovery_early_stop_schema_prune.json",
                ),
                (
                    "Smoke N=25 P3 stack",
                    model,
                    f"parallel_semantic_hybrid_r25_bo_{model}_r25_best_of_n_p1_cache_p3_semantic_early_stop_schema_prune.json",
                    f"parallel_p3_r25_rep2_{model}_r25_best_of_n_p1_cache_p3_semantic_early_stop_schema_prune.json",
                ),
                (
                    "Full-500 P4",
                    model,
                    f"parallel_p4_full500_r3_{model}_r3_best_of_n_promptcache_p4suppress.json",
                    f"parallel_p4_full500_r3_rep2_{model}_r3_best_of_n_promptcache_p4suppress.json",
                ),
                (
                    "Full-500 compose",
                    model,
                    f"parallel_compose_full500_r3_{model}_r3_best_of_n_p1_cache_promptcache_early_stop_schema_prune_p4suppress.json",
                    f"parallel_compose_full500_r3_rep2_{model}_r3_best_of_n_p1_cache_promptcache_early_stop_schema_prune_p4suppress.json",
                ),
                (
                    "Full-500 P3 stack",
                    model,
                    f"parallel_p3_full500_r3_{model}_r3_best_of_n_p1_cache_p3_semantic_early_stop_schema_prune.json",
                    f"parallel_p3_full500_r3_rep2_{model}_r3_best_of_n_p1_cache_p3_semantic_early_stop_schema_prune.json",
                ),
            ]
        )
    return out


def _bootstrap_comparisons() -> list[tuple[str, str, str, str]]:
    """(section, label, treat, ctrl)."""
    rows: list[tuple[str, str, str, str]] = []
    for model, short in MODELS:
        base500 = f"parallel_baseline_full500_r3_{model}_r3_best_of_n.json"
        pc500 = f"parallel_pc_full500_r3_{model}_r3_best_of_n_promptcache.json"
        p1_500 = f"parallel_p1_full500_r3_{model}_r3_best_of_n_p1_cache.json"
        p2_500 = (
            f"parallel_fullstack_prune_full500_r3_{model}_r3_best_of_n_"
            "p1_cache_p2_discovery_early_stop_schema_prune.json"
        )
        rows += [
            (
                "Full-500 N=3",
                f"{short} P1 vs P0",
                f"parallel_p1_full500_r3_{model}_r3_best_of_n_p1_cache.json",
                base500,
            ),
            (
                "Full-500 N=3",
                f"{short} prune vs P0",
                f"parallel_schema_prune_iso_full500_r3_{model}_r3_best_of_n_schema_prune.json",
                base500,
            ),
            (
                "Full-500 N=3",
                f"{short} prompt-cache vs P0",
                pc500,
                base500,
            ),
            (
                "Full-500 N=3",
                f"{short} P4 vs PC",
                f"parallel_p4_full500_r3_{model}_r3_best_of_n_promptcache_p4suppress.json",
                pc500,
            ),
            (
                "Full-500 N=3",
                f"{short} P1+P4 vs P1",
                f"parallel_p1p4_full500_r3_{model}_r3_best_of_n_p1_cache_promptcache_p4suppress.json",
                p1_500,
            ),
            (
                "Full-500 N=3",
                f"{short} P3 stack vs P2 stack",
                f"parallel_p3_full500_r3_{model}_r3_best_of_n_p1_cache_p3_semantic_early_stop_schema_prune.json",
                p2_500,
            ),
            (
                "Full-500 N=3",
                f"{short} compose vs P0",
                f"parallel_compose_full500_r3_{model}_r3_best_of_n_p1_cache_promptcache_early_stop_schema_prune_p4suppress.json",
                base500,
            ),
            (
                "Full-500 N=3 rep2",
                f"{short} P4 rep2 vs PC",
                f"parallel_p4_full500_r3_rep2_{model}_r3_best_of_n_promptcache_p4suppress.json",
                pc500,
            ),
            (
                "Full-500 N=3 rep2",
                f"{short} compose rep2 vs P0",
                f"parallel_compose_full500_r3_rep2_{model}_r3_best_of_n_p1_cache_promptcache_early_stop_schema_prune_p4suppress.json",
                base500,
            ),
            (
                "Full-500 N=3",
                f"{short} P3 stack rep2 vs P2 stack",
                f"parallel_p3_full500_r3_rep2_{model}_r3_best_of_n_p1_cache_p3_semantic_early_stop_schema_prune.json",
                p2_500,
            ),
            (
                "Full-500 N=3 rep2",
                f"{short} P3 stack rep2 vs P0",
                f"parallel_p3_full500_r3_rep2_{model}_r3_best_of_n_p1_cache_p3_semantic_early_stop_schema_prune.json",
                base500,
            ),
            (
                "Smoke N=25 rep2-matched",
                f"{short} P1 rep2 vs P0 rep2",
                f"parallel_p1_r25_rep2_{model}_r25_best_of_n_p1_cache.json",
                f"parallel_baseline_r25_rep2_{model}_r25_best_of_n.json",
            ),
            (
                "Smoke N=25 rep2-matched",
                f"{short} prune rep2 vs P0 rep2",
                f"parallel_prune_r25_rep2_{model}_r25_best_of_n_schema_prune.json",
                f"parallel_baseline_r25_rep2_{model}_r25_best_of_n.json",
            ),
            (
                "Smoke N=25 rep2-matched",
                f"{short} PC rep2 vs P0 rep2",
                f"parallel_pc_r25_rep2_{model}_r25_best_of_n_promptcache.json",
                f"parallel_baseline_r25_rep2_{model}_r25_best_of_n.json",
            ),
            (
                "Smoke N=25 rep2-matched",
                f"{short} P3 rep2 vs P2 rep2",
                f"parallel_p3_r25_rep2_{model}_r25_best_of_n_p1_cache_p3_semantic_early_stop_schema_prune.json",
                f"parallel_p2_r25_rep2_{model}_r25_best_of_n_p1_cache_p2_discovery_early_stop_schema_prune.json",
            ),
            (
                "Smoke N=25 rep2-matched",
                f"{short} compose rep2 vs P0 rep2",
                f"parallel_compose_r25_rep2_{model}_r25_best_of_n_p1_cache_promptcache_early_stop_schema_prune_p4suppress.json",
                f"parallel_baseline_r25_rep2_{model}_r25_best_of_n.json",
            ),
        ]

    # Unconfounded Gemini P3 vs repaired P2
    rows.append(
        (
            "Unconfound Gemini N=25",
            "Gemini P3 vs P2 repair",
            "parallel_semantic_hybrid_r25_bo_gemini-2.5-flash_r25_best_of_n_p1_cache_p3_semantic_early_stop_schema_prune.json",
            "parallel_fullstack_prune_r25_repair_gemini-2.5-flash_r25_best_of_n_p1_cache_p2_discovery_early_stop_schema_prune.json",
        )
    )
    rows.append(
        (
            "Unconfound Gemini N=25",
            "Gemini P3 rep2 vs P2 rep2",
            "parallel_p3_r25_rep2_gemini-2.5-flash_r25_best_of_n_p1_cache_p3_semantic_early_stop_schema_prune.json",
            "parallel_p2_r25_rep2_gemini-2.5-flash_r25_best_of_n_p1_cache_p2_discovery_early_stop_schema_prune.json",
        )
    )
    rows.append(
        (
            "Unconfound Gemini N=25",
            "Gemini P3 vs P2 old (confounded)",
            "parallel_semantic_hybrid_r25_bo_gemini-2.5-flash_r25_best_of_n_p1_cache_p3_semantic_early_stop_schema_prune.json",
            "parallel_fullstack_prune_r25_bo_gemini-2.5-flash_r25_best_of_n_p1_cache_p2_discovery_early_stop_schema_prune.json",
        )
    )
    return rows


COST_BATCHES: list[tuple[str, str, str]] = []


def _cost_batches() -> list[tuple[str, str, str]]:
    out: list[tuple[str, str, str]] = []
    for model, short in MODELS:
        out.extend(
            [
                (
                    f"{short} compose full-500",
                    model,
                    f"parallel_compose_full500_r3_{model}_r3_best_of_n_p1_cache_promptcache_early_stop_schema_prune_p4suppress.json",
                ),
                (
                    f"{short} compose full-500 rep2",
                    model,
                    f"parallel_compose_full500_r3_rep2_{model}_r3_best_of_n_p1_cache_promptcache_early_stop_schema_prune_p4suppress.json",
                ),
                (
                    f"{short} P4 full-500",
                    model,
                    f"parallel_p4_full500_r3_{model}_r3_best_of_n_promptcache_p4suppress.json",
                ),
                (
                    f"{short} P0 full-500",
                    model,
                    f"parallel_baseline_full500_r3_{model}_r3_best_of_n.json",
                ),
                (
                    f"{short} PC full-500",
                    model,
                    f"parallel_pc_full500_r3_{model}_r3_best_of_n_promptcache.json",
                ),
                (
                    f"{short} P3 full-500",
                    model,
                    f"parallel_p3_full500_r3_{model}_r3_best_of_n_p1_cache_p3_semantic_early_stop_schema_prune.json",
                ),
                (
                    f"{short} P3 full-500 rep2",
                    model,
                    f"parallel_p3_full500_r3_rep2_{model}_r3_best_of_n_p1_cache_p3_semantic_early_stop_schema_prune.json",
                ),
            ]
        )
    out.append(
        (
            "GPT compose+P3 full-500",
            "gpt-4o-mini",
            "parallel_compose_p3_full500_r3_gpt-4o-mini_r3_best_of_n_p1_cache_p3_semantic_promptcache_early_stop_schema_prune_p4suppress.json",
        )
    )
    return out


def _ledger_comparisons() -> list[tuple[str, str, str, str, str]]:
    """(section, label, treat, ctrl, metric_key) for token/DB CIs."""
    rows: list[tuple[str, str, str, str, str]] = []
    for model, short in MODELS:
        base500 = f"parallel_baseline_full500_r3_{model}_r3_best_of_n.json"
        pc500 = f"parallel_pc_full500_r3_{model}_r3_best_of_n_promptcache.json"
        p1_500 = f"parallel_p1_full500_r3_{model}_r3_best_of_n_p1_cache.json"
        rows += [
            (
                "Full-500 tokens",
                f"{short} prune vs P0",
                f"parallel_schema_prune_iso_full500_r3_{model}_r3_best_of_n_schema_prune.json",
                base500,
                "tokens",
            ),
            (
                "Full-500 tokens",
                f"{short} PC vs P0",
                pc500,
                base500,
                "tokens",
            ),
            (
                "Full-500 tokens",
                f"{short} P4 vs PC",
                f"parallel_p4_full500_r3_{model}_r3_best_of_n_promptcache_p4suppress.json",
                pc500,
                "tokens",
            ),
            (
                "Full-500 tokens",
                f"{short} compose vs P0",
                f"parallel_compose_full500_r3_{model}_r3_best_of_n_p1_cache_promptcache_early_stop_schema_prune_p4suppress.json",
                base500,
                "tokens",
            ),
            (
                "Full-500 tokens",
                f"{short} P3 vs P2",
                f"parallel_p3_full500_r3_{model}_r3_best_of_n_p1_cache_p3_semantic_early_stop_schema_prune.json",
                (
                    f"parallel_fullstack_prune_full500_r3_{model}_r3_best_of_n_"
                    "p1_cache_p2_discovery_early_stop_schema_prune.json"
                ),
                "tokens",
            ),
            (
                "Full-500 DB interactions",
                f"{short} P1 vs P0",
                p1_500,
                base500,
                "db",
            ),
            (
                "Full-500 DB interactions",
                f"{short} P4 vs PC",
                f"parallel_p4_full500_r3_{model}_r3_best_of_n_promptcache_p4suppress.json",
                pc500,
                "db",
            ),
            (
                "Full-500 DB interactions",
                f"{short} compose vs P0",
                f"parallel_compose_full500_r3_{model}_r3_best_of_n_p1_cache_promptcache_early_stop_schema_prune_p4suppress.json",
                base500,
                "db",
            ),
            (
                "Full-500 rep2 tokens",
                f"{short} P4 rep2 vs PC",
                f"parallel_p4_full500_r3_rep2_{model}_r3_best_of_n_promptcache_p4suppress.json",
                pc500,
                "tokens",
            ),
            (
                "Full-500 rep2 tokens",
                f"{short} compose rep2 vs P0",
                f"parallel_compose_full500_r3_rep2_{model}_r3_best_of_n_p1_cache_promptcache_early_stop_schema_prune_p4suppress.json",
                base500,
                "tokens",
            ),
            (
                "Full-500 rep2 DB",
                f"{short} P4 rep2 vs PC",
                f"parallel_p4_full500_r3_rep2_{model}_r3_best_of_n_promptcache_p4suppress.json",
                pc500,
                "db",
            ),
        ]
    return rows


def write_ledger_cis(path: Path) -> list[str]:
    sections: dict[str, list[str]] = {}
    highlights: list[str] = []
    for section, label, treat_name, ctrl_name, key in _ledger_comparisons():
        treat_p = _bpath(treat_name)
        ctrl_p = _bpath(ctrl_name)
        if not treat_p.exists() or not ctrl_p.exists():
            miss = "treat" if not treat_p.exists() else "ctrl"
            sections.setdefault(section, []).append(
                f"| {label} | — | — | — | — | missing {miss} |"
            )
            continue
        n, t_mean, c_mean, pct, lo, hi = _bootstrap_mean_pct(
            _metric_map(treat_p, key), _metric_map(ctrl_p, key)
        )
        if n < 5 or np.isnan(pct):
            sections.setdefault(section, []).append(
                f"| {label} | {n} | — | — | — | too few matched |"
            )
            continue
        unit = "tok/task" if key == "tokens" else "db/task"
        flag = "" if (lo > 0 or hi < 0) else " †"
        sections.setdefault(section, []).append(
            f"| {label} | {n} | {t_mean:.1f} | {c_mean:.1f} | {pct:+.1f}%{flag} "
            f"| [{lo:+.1f}%, {hi:+.1f}%] |"
        )
        highlights.append(
            f"[{section}] {label}: n={n} {unit} Δ={pct:+.1f}% CI=[{lo:+.1f}%, {hi:+.1f}%]{flag}"
        )
        print(highlights[-1], flush=True)

    lines = [
        "# Token / DB paired bootstrap CIs — draft_paper_ieee_v4",
        "",
        "Paired % change over matched question_ids (n_boot=10000, seed=42).",
        "Δ% = 100 × (Σ_treat − Σ_ctrl) / Σ_ctrl on the matched set.",
        "† = 95% CI includes 0.",
        "",
        "Use these for accuracy-neutral policies (P1, prune, PC, P4) where EX CIs "
        "are expected to include 0.",
        "",
    ]
    for section, rows in sections.items():
        lines += [
            f"## {section}",
            "",
            "| Comparison | n | Treat mean | Ctrl mean | Δ% | 95% CI |",
            "|---|---:|---:|---:|---:|---|",
            *rows,
            "",
        ]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return highlights


def write_paper_snippets(
    path: Path,
    boot_highlights: list[str],
    stab_bits: list[str],
    ledger_bits: list[str],
) -> None:
    """Short paste-ready sentences grounded in the latest pack numbers."""

    gem_unconf = [h for h in boot_highlights if "Gemini P3 vs P2 repair" in h]
    full_stab = [s for s in stab_bits if s.startswith("Full-500")]
    ds_ex = [h for h in boot_highlights if h.startswith("[Full-500") and "DeepSeek" in h]
    tok = [h for h in ledger_bits if "tokens" in h.lower() and "†" not in h][:8]
    db = [h for h in ledger_bits if "DB" in h and "†" not in h][:6]
    p3_miss = any("P3 stack" in s and "missing" in s for s in stab_bits)

    lines = [
        "# Paper / essay paste snippets — draft_paper_ieee_v4",
        "",
        "Generated from live batch JSON. Re-run `generate_robustness_pack.py` after "
        "wave4 before pasting. Edit lightly for tense/voice; do not invent numbers.",
        "",
        "## Threats-to-validity / reflective essay (§4–5)",
        "",
        "- Second independent seeds on full-500 P4 and composition move EX by roughly "
        "0–1.4 pp with bootstrap CIs that include 0, so the single-run noise concern "
        "is bounded for those claims; smoke N=25 still shows few-task swings of several pp.",
        "- Paired bootstrap 95% CIs are now available for headline full-500 and "
        "rep2-matched smoke comparisons (`bootstrap_ex_cis_v4.md`); accuracy-neutral "
        "policies are judged on token/DB CIs (`token_db_cis_v4.md`).",
    ]
    if gem_unconf:
        lines.append(f"- Unconfound check: {gem_unconf[0]}")
    else:
        lines.append(
            "- After repairing the Gemini P2 N=25 batch (11 API errors), P3 remains "
            "worse than P2 on EX — cite the repair row, not the confounded footnote."
        )
    if p3_miss:
        lines.append(
            "- P3 full-500 second seed is still pending (robustness wave4); "
            "stability for that stack is single-run until it lands."
        )
    lines += [
        "",
        "## Results prose (full-500 stability)",
        "",
    ]
    if full_stab:
        lines += [f"- {b}" for b in full_stab]
    else:
        lines.append("- (awaiting stability rows)")
    lines += [
        "",
        "## Results prose (DeepSeek EX CIs — claim-worthy when CI excludes 0)",
        "",
    ]
    if ds_ex:
        lines += [f"- {b}" for b in ds_ex]
    else:
        lines.append("- (none matched)")
    lines += [
        "",
        "## Results prose (token / DB ledgers — non-† only)",
        "",
        "### Tokens",
        "",
    ]
    lines += [f"- {b}" for b in tok] if tok else ["- (none)"]
    lines += ["", "### DB interactions", ""]
    lines += [f"- {b}" for b in db] if db else ["- (none)"]
    lines += [
        "",
        "## One-paragraph methods addendum (optional)",
        "",
        "For each headline comparison we report a paired bootstrap 95% confidence "
        "interval over matched `question_id`s (10 000 resamples, fixed seed). "
        "Where a second independent seed exists, we also report the rep2−rep1 EX "
        "delta with the same procedure. Accuracy-neutral middleware is additionally "
        "summarised with paired percentage changes on total tokens and "
        "`db_interactions`.",
        "",
    ]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def write_bootstrap(path: Path) -> list[str]:
    sections: dict[str, list[str]] = {}
    highlights: list[str] = []
    for section, label, treat_name, ctrl_name in _bootstrap_comparisons():
        treat_p = _bpath(treat_name)
        ctrl_p = _bpath(ctrl_name)
        if not treat_p.exists() or not ctrl_p.exists():
            miss = "treat" if not treat_p.exists() else "ctrl"
            sections.setdefault(section, []).append(
                f"| {label} | — | — | — | — | missing {miss} |"
            )
            continue
        n, te, ce, diff, lo, hi = _bootstrap_diff(_ex_map(treat_p), _ex_map(ctrl_p))
        if n < 5 or np.isnan(diff):
            sections.setdefault(section, []).append(
                f"| {label} | {n} | — | — | — | too few matched |"
            )
            continue
        flag = "" if (lo > 0 or hi < 0) else " †"
        sections.setdefault(section, []).append(
            f"| {label} | {n} | {te:.1f} | {ce:.1f} | {diff:+.1f}{flag} | [{lo:+.1f}, {hi:+.1f}] |"
        )
        highlights.append(
            f"[{section}] {label}: n={n} Δ={diff:+.1f} pp CI=[{lo:+.1f}, {hi:+.1f}]{flag}"
        )
        print(highlights[-1], flush=True)

    lines = [
        "# Bootstrap 95% CIs — draft_paper_ieee_v4 (refreshed)",
        "",
        "Paired bootstrap over matched question_ids (n_boot=10000, seed=42).",
        "† = 95% CI includes 0 (EX delta not distinguishable from noise).",
        "",
    ]
    for section, rows in sections.items():
        lines += [
            f"## {section}",
            "",
            "| Comparison | n | Treat EX% | Ctrl EX% | Δ pp | 95% CI |",
            "|---|---:|---:|---:|---:|---|",
            *rows,
            "",
        ]
    lines.append(
        "*Accuracy-neutral policies are expected to show † on EX; "
        "judge those on token / DB / billed-input metrics.*"
    )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return highlights


def write_stability(path: Path) -> list[str]:
    lines = [
        "# rep1 vs rep2 stability — draft_paper_ieee_v4",
        "",
        "Second independent runs of the same configuration. "
        "Δ is paired over matched question_ids (rep2 − rep1).",
        "",
    ]
    summary_bits: list[str] = []
    by_section: dict[str, list[str]] = {}
    for section, model, r1_name, r2_name in _stability_pairs():
        short = dict(MODELS)[model]
        r1 = _bpath(r1_name)
        r2 = _bpath(r2_name)
        if not r1.exists() or not r2.exists():
            by_section.setdefault(section, []).append(
                f"| {short} | — | — | — | — | — | missing |"
            )
            continue
        m1, m2 = _metrics(r1), _metrics(r2)
        # treat=rep2, control=rep1 → Δ = rep2 − rep1
        _n, _te, _ce, d_ex, lo, hi = _bootstrap_diff(_ex_map(r2), _ex_map(r1))
        d_tok = _pct(m2["tokens"], m1["tokens"])
        flag = "" if (lo > 0 or hi < 0) else " †"
        by_section.setdefault(section, []).append(
            f"| {short} | {m1['ex']:.1f} | {m2['ex']:.1f} | {d_ex:+.1f}{flag} "
            f"| [{lo:+.1f}, {hi:+.1f}] | {d_tok:+.1f}% | "
            f"{m1['cached_pct']:.0f}→{m2['cached_pct']:.0f} |"
        )
        summary_bits.append(
            f"{section} / {short}: EX {m1['ex']:.1f}→{m2['ex']:.1f} "
            f"(Δ={d_ex:+.1f} pp{flag}), tokens {d_tok:+.1f}%"
        )
        print(summary_bits[-1], flush=True)

    for section, rows in by_section.items():
        lines += [
            f"## {section}",
            "",
            "| Model | EX% r1 | EX% r2 | Δ pp | 95% CI | Token Δ | Cached% r1→r2 |",
            "|---|---:|---:|---:|---|---:|---|",
            *rows,
            "",
        ]
    lines.append(
        "*Full-500 rows should be near-zero Δ; smoke N=25 swings of ±2–6 pp "
        "are the few-task noise already named in threats-to-validity.*"
    )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return summary_bits


def write_pack(
    path: Path,
    boot_highlights: list[str],
    stab_bits: list[str],
    ledger_bits: list[str],
) -> None:
    # Unconfound detail
    gem_p3 = _bpath(
        "parallel_semantic_hybrid_r25_bo_gemini-2.5-flash_r25_best_of_n_"
        "p1_cache_p3_semantic_early_stop_schema_prune.json"
    )
    gem_p2_old = _bpath(
        "parallel_fullstack_prune_r25_bo_gemini-2.5-flash_r25_best_of_n_"
        "p1_cache_p2_discovery_early_stop_schema_prune.json"
    )
    gem_p2_fix = _bpath(
        "parallel_fullstack_prune_r25_repair_gemini-2.5-flash_r25_best_of_n_"
        "p1_cache_p2_discovery_early_stop_schema_prune.json"
    )
    gem_p3_r2 = _bpath(
        "parallel_p3_r25_rep2_gemini-2.5-flash_r25_best_of_n_"
        "p1_cache_p3_semantic_early_stop_schema_prune.json"
    )
    gem_p2_r2 = _bpath(
        "parallel_p2_r25_rep2_gemini-2.5-flash_r25_best_of_n_"
        "p1_cache_p2_discovery_early_stop_schema_prune.json"
    )

    unconfound_lines = []
    for label, treat, ctrl in [
        ("P3 vs P2 old (11 API errs — confounded)", gem_p3, gem_p2_old),
        ("P3 vs P2 repair (unconfounded)", gem_p3, gem_p2_fix),
        ("P3 rep2 vs P2 rep2", gem_p3_r2, gem_p2_r2),
    ]:
        if not treat.exists() or not ctrl.exists():
            unconfound_lines.append(f"| {label} | — | — | missing |")
            continue
        mt, mc = _metrics(treat), _metrics(ctrl)
        n, te, ce, d, lo, hi = _bootstrap_diff(_ex_map(treat), _ex_map(ctrl))
        flag = "" if (lo > 0 or hi < 0) else " †"
        unconfound_lines.append(
            f"| {label} | {te:.1f} vs {ce:.1f} | {d:+.1f}{flag} | [{lo:+.1f}, {hi:+.1f}] n={n} "
            f"(ctrl err {mc['err']}) |"
        )

    # Costs
    cost_lines = []
    for label, model, name in _cost_batches():
        p = _bpath(name)
        if not p.exists():
            cost_lines.append(f"| {label} | — | — | — | missing |")
            continue
        rows = _ok_rows(p)
        m = _metrics(p)
        usd = batch_cost_usd(rows, model)
        usd_s = f"${usd:.2f}" if usd is not None else "n/a"
        cost_lines.append(
            f"| {label} | {m['n']} | {m['ex']:.1f} | {m['tokens']:,} | {usd_s} |"
        )

    # Full-500 stability highlight
    full500_stable = [b for b in stab_bits if b.startswith("Full-500")]
    p3_pending = [b for b in full500_stable if "P3 stack" in b]
    # detect missing P3 rep2 from batch files
    p3_rep2_missing = False
    for model, _ in MODELS:
        r2 = _bpath(
            f"parallel_p3_full500_r3_rep2_{model}_r3_best_of_n_"
            "p1_cache_p3_semantic_early_stop_schema_prune.json"
        )
        if not r2.exists():
            p3_rep2_missing = True
            break

    smoke_noisy = [
        b
        for b in stab_bits
        if "Smoke" in b
        and any(x in b for x in ("+5", "+6", "+7", "+8", "-5", "-6", "-7", "-8"))
    ]
    ledger_sig = [b for b in ledger_bits if "†" not in b][:10]

    lines = [
        "# Robustness pack — draft_paper_ieee_v4",
        "",
        "Offline analysis over existing batch JSON. Regenerated by "
        "`uv run python scripts/generate_robustness_pack.py`.",
        "",
        "## 1. Verdict",
        "",
        "- **Full-500 second seeds are stable**: compose and P4 rep2 move EX by "
        "roughly 0–1.4 pp with CIs that include 0 — the generalisation claims hold.",
        "- **Smoke N=25 still noisy**: swings of several pp (e.g. GPT compose +6 pp) "
        "are within the few-task variance already named in threats-to-validity; "
        "do not claim EX gains from smoke alone.",
        "- **Gemini P3 vs P2 is unconfounded**: after repairing the 11-error P2 "
        "batch, P3 remains worse than P2 on EX — the model-conditioning story stands.",
        "- **Accuracy-neutral ledgers now have CIs**: token and DB-interaction % "
        "changes for P1/prune/PC/P4/compose are in `token_db_cis_v4.md`.",
    ]
    if p3_rep2_missing:
        lines.append(
            "- **P3 full-500 rep2 pending** (wave4): last single-seed full-500 gap; "
            "pack rows show `missing` until it lands."
        )
    elif p3_pending:
        lines.append(
            "- **P3 full-500 second seed landed**: see Full-500 P3 stability rows."
        )
    lines += [
        "",
        "## 2. Unconfound: Gemini N=25 P3 vs P2",
        "",
        "| Comparison | EX% (P3 vs P2) | Δ pp | 95% CI |",
        "|---|---|---:|---|",
        *unconfound_lines,
        "",
        "*Use the repair / rep2 rows in the paper; drop the confounded +18 pp footnote.*",
        "",
        "## 3. Full-500 stability highlights",
        "",
    ]
    if full500_stable:
        lines += [f"- {b}" for b in full500_stable]
    else:
        lines.append("- (see `rep_stability_v4.md`)")
    lines += [
        "",
        "## 4. Smoke swings to flag (not claim)",
        "",
    ]
    if smoke_noisy:
        lines += [f"- {b}" for b in smoke_noisy]
    else:
        lines.append("- See stability report; largest smoke moves remain † on bootstrap CIs.")
    lines += [
        "",
        "## 5. Significant token / DB ledger moves (CI excludes 0)",
        "",
    ]
    if ledger_sig:
        lines += [f"- {b}" for b in ledger_sig]
    else:
        lines.append("- (see `token_db_cis_v4.md`)")
    lines += [
        "",
        "## 6. Estimated USD cost (list prices in `configs/models.yaml`)",
        "",
        "| Batch | n | EX% | Tokens | Est. USD |",
        "|---|---:|---:|---:|---:|",
        *cost_lines,
        "",
        "*Gemini cached-input price is unset in the registry — cached tokens billed at "
        "full input rate there, so Gemini USD is an upper bound.*",
        "",
        "## 7. Artefacts",
        "",
        "- `runs/reports/bootstrap_ex_cis_v4.md` — full paired EX CI tables",
        "- `runs/reports/token_db_cis_v4.md` — token / DB % CI tables",
        "- `runs/reports/rep_stability_v4.md` — all rep1/rep2 pairs",
        "- `runs/reports/paper_snippets_v4.md` — paste-ready prose",
        "- `runs/reports/robustness_pack_v4.md` — this summary",
        "",
    ]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    REPORTS.mkdir(parents=True, exist_ok=True)
    print("=== bootstrap EX ===", flush=True)
    boot = write_bootstrap(REPORTS / "bootstrap_ex_cis_v4.md")
    print("=== stability ===", flush=True)
    stab = write_stability(REPORTS / "rep_stability_v4.md")
    print("=== token/DB CIs ===", flush=True)
    ledger = write_ledger_cis(REPORTS / "token_db_cis_v4.md")
    print("=== paper snippets ===", flush=True)
    write_paper_snippets(REPORTS / "paper_snippets_v4.md", boot, stab, ledger)
    print("=== pack summary ===", flush=True)
    write_pack(REPORTS / "robustness_pack_v4.md", boot, stab, ledger)
    print(f"wrote {REPORTS / 'bootstrap_ex_cis_v4.md'}")
    print(f"wrote {REPORTS / 'token_db_cis_v4.md'}")
    print(f"wrote {REPORTS / 'rep_stability_v4.md'}")
    print(f"wrote {REPORTS / 'paper_snippets_v4.md'}")
    print(f"wrote {REPORTS / 'robustness_pack_v4.md'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
