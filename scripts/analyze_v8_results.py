#!/usr/bin/env python3
"""v8 analysis: three prompt-layer methods, isolated and composed, vs matched P0.

Reports for every matrix cell a paired bootstrap 95% CI over matched
question_ids on EX, raw tokens, billed tokens (cached discounted) and USD,
plus the P3 injection counts that evidence the injection-tax mechanism.

  uv run python scripts/analyze_v8_results.py [--out runs/reports/v8_numbers.txt]
"""
from __future__ import annotations

import argparse
import glob
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(REPO / "scripts"))

from generate_robustness_pack import (  # noqa: E402
    _bootstrap_diff,
    _bootstrap_mean_pct,
    _ex_map,
    _metric_map,
    _ok_rows,
)
from src.llm.models import load_model_registry  # noqa: E402

BATCH = REPO / "runs" / "batches"
MODELS = [("gpt-4o-mini", "GPT"), ("gemini-2.5-flash", "Gemini"), ("deepseek-v3.2", "DeepSeek")]
METHODS = [("prune", "pruning"), ("p3", "P3 facts"), ("pc", "prompt cache"), ("comp", "composed")]

# P0 comparators. Same model version on both sides of every comparison:
# DeepSeek uses the v4-flash-era baselines; GPT/Gemini are version-stable.
BASELINES: dict[tuple[str, int, str], str] = {}
for _n in (3, 10, 25):
    BASELINES[("50", _n, "deepseek-v3.2")] = f"baseline_r{_n}_bo_v4f"
    BASELINES[("50", _n, "gpt-4o-mini")] = f"20260611_123556_a3baef_baseline_r{_n}"
    BASELINES[("50", _n, "gemini-2.5-flash")] = f"20260611_123711_91299c_baseline_r{_n}"
BASELINES[("500", 3, "deepseek-v3.2")] = "baseline_full500_r3_v4f"
for _m in ("gpt-4o-mini", "gemini-2.5-flash"):
    BASELINES[("500", 3, _m)] = "baseline_full500_r3"
for _n in (10, 25):
    for _m, _ in MODELS:
        BASELINES[("500", _n, _m)] = f"baseline_full500_r{_n}"


# A batch that lost a large share of its tasks to API failures is not a valid
# comparator: the surviving tasks are a non-random subset (connection errors
# correlate with long/expensive trajectories). Anything below this share of
# completed tasks is refused outright rather than silently reported on a
# shrunken n.
MIN_COMPLETION = 0.90


def _usable(path: Path) -> bool:
    d = json.load(open(path))
    total = d.get("task_count") or 0
    done = d.get("completed_task_count")
    if not total or done is None:
        return True
    return done / total >= MIN_COMPLETION


def find(batch_id: str, model: str) -> Path | None:
    for p in sorted(BATCH.glob(f"parallel_{batch_id}_{model}_r*.json")):
        if _usable(p):
            return p
        print(f"  [skipped {p.name}: only "
              f"{json.load(open(p)).get('completed_task_count')}/"
              f"{json.load(open(p)).get('task_count')} tasks completed]")
    return None


def baseline_for(scale: str, n: int, model: str) -> Path | None:
    """Prefer a freshly-run v8 baseline if one exists, else the mapped one."""
    fresh = find(f"v8_p0_{scale}t_r{n}", model)
    if fresh:
        return fresh
    bid = BASELINES.get((scale, n, model))
    return find(bid, model) if bid else None


def billed_map(path: Path) -> dict[int, float]:
    """Billed input proxy: uncached prompt + cached prompt at the cached rate,
    plus completion.

    A missing cached rate is an error, not a default. Until 2026-08-16 this
    silently assumed ``p_in * 0.5`` while ``src/llm/cost.py`` assumed the full
    input rate for the same model, so the project costed identical runs two
    different ways and Gemini's entire billed-savings result rested on an
    invented number (it swings from +2.9% to -37.8% across plausible discounts).
    Publish the rate in configs/models.yaml rather than guessing here.
    """
    reg = load_model_registry()
    d = json.load(open(path))
    spec = reg.get(d.get("model_key"))
    p_in = float(getattr(spec, "price_per_1m_input", 0) or 0)
    p_out = float(getattr(spec, "price_per_1m_output", 0) or 0)
    p_cache = getattr(spec, "price_per_1m_cached_input", None)
    if p_cache is None:
        raise SystemExit(
            f"{d.get('model_key')} has no price_per_1m_cached_input in "
            "configs/models.yaml. Add the provider's published rate; do not let "
            "this fall back to a guess -- see the note above."
        )
    p_cache = float(p_cache)
    out: dict[int, float] = {}
    for r in _ok_rows(path):
        prompt = int(r.get("total_prompt_tokens") or 0)
        cached = int(r.get("total_cached_prompt_tokens") or 0)
        comp = int(r.get("total_completion_tokens") or 0)
        uncached = max(prompt - cached, 0)
        out[int(r["question_id"])] = (
            uncached * p_in + cached * p_cache + comp * p_out
        ) / 1e6
    return out


def fmt(delta: float, lo: float, hi: float, unit: str = "") -> str:
    dag = "†" if lo <= 0 <= hi else " "
    return f"{delta:+7.1f}{unit} [{lo:+6.1f},{hi:+6.1f}]{dag}"


def p3_stats(path: Path) -> str:
    d = json.load(open(path))
    inj = d.get("total_middleware_semantic_injections") or 0
    tasks = d.get("completed_task_count") or d.get("task_count") or 1
    if not inj:
        return ""
    return f"  inj/task={inj / tasks:.1f}"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", type=Path, default=REPO / "runs" / "reports" / "v8_numbers.txt")
    ap.add_argument(
        "--allow-legacy",
        action="store_true",
        help="Substitute pre-v8 batches for matrix cells that have not been "
             "re-run. OFF by default: those batches come from other "
             "experiments' task sets (and, for DeepSeek, a different model "
             "version), which is exactly what GAP 1/2 of run_v8_cleanup.sh "
             "exist to replace. With this off, an un-run cell is reported as "
             "MISSING rather than silently filled.",
    )
    args = ap.parse_args()

    lines: list[str] = []

    def emit(s: str = "") -> None:
        print(s)
        lines.append(s)

    emit("=" * 108)
    emit("v8 — three prompt-layer methods vs matched P0 (paired bootstrap 95% CI; "
         "† = CI includes 0)")
    emit("no early-stop / no P1 / no P4 in any arm")
    emit("=" * 108)

    for scale, ns in (("50", (3, 10, 25)), ("500", (3, 10))):
        emit()
        emit(f"########## {scale}-task ##########")
        for method, mlabel in METHODS:
            emit()
            emit(f"--- {mlabel} ---")
            for n in ns:
                for model, short in MODELS:
                    tp = find(f"v8_{method}_{scale}t_r{n}", model)
                    declined: str | None = None
                    # fall back to pre-existing equivalents for cells not re-run
                    if tp is None:
                        # Pre-existing equivalents for cells not re-run. Some
                        # 50-task prompt-cache runs were produced under other
                        # experiments' batch ids, so those are per-model.
                        legacy = {
                            ("prune", "50", 10): "schema_prune_iso_r10_bo",
                            ("prune", "50", 25): "schema_prune_iso_r25_bo",
                            ("prune", "500", 3): "schema_prune_iso_full500_r3",
                            ("pc", "500", 3): "pc_full500_r3",
                            ("pc", "50", 10): "dbprofile_base_r10_bo",
                            ("pc", "50", 25): {
                                "gpt-4o-mini": "pc50_r25_cached",
                                "gemini-2.5-flash": "pc50_r25_gem_cached",
                                "deepseek-v3.2": "pc50_r25_ds_cached",
                            }[model],
                            ("pc", "50", 3): {
                                "gpt-4o-mini": "pc50_cached",
                                "gemini-2.5-flash": "pc50_gem_cached",
                                "deepseek-v3.2": "pc50_ds_cached",
                            }[model],
                        }.get((method, scale, n))
                        if legacy and not args.allow_legacy:
                            declined, legacy = legacy, None
                        if legacy:
                            if model == "deepseek-v3.2":
                                # DeepSeek must stay on the current model
                                # version; only take a legacy batch if a v4f
                                # variant of it exists.
                                tp = find(legacy + "_v4f", model)
                            else:
                                tp = find(legacy, model)
                    cp = baseline_for(scale, n, model)
                    if tp is None or cp is None:
                        why = "treat" if tp is None else "ctrl"
                        note = f"; legacy {declined} declined" if declined else ""
                        emit(f"  N={n:<3}{short:9s} MISSING ({why}{note})")
                        continue
                    nq, tex, cex, d, lo, hi = _bootstrap_diff(_ex_map(tp), _ex_map(cp))
                    _, _, _, td, tlo, thi = _bootstrap_mean_pct(
                        _metric_map(tp, "tokens"), _metric_map(cp, "tokens")
                    )
                    _, _, _, bd, blo, bhi = _bootstrap_mean_pct(billed_map(tp), billed_map(cp))
                    emit(
                        f"  N={n:<3}{short:9s}n={nq:<4} "
                        f"EX {tex:5.1f}v{cex:5.1f} {fmt(d, lo, hi, 'pp')}   "
                        f"tok {fmt(td, tlo, thi, '%')}   "
                        f"billed {fmt(bd, blo, bhi, '%')}{p3_stats(tp)}"
                    )

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"\nwrote {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
