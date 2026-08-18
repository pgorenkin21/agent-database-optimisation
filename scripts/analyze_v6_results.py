#!/usr/bin/env python3
"""All numbers needed for draft_paper_ieee_v6: N=10/25 full-500 scale-up,
new r3 seeds (11 Aug), DeepSeek within-era r3 (see analyze_deepseek_within_era),
and USD costs. DeepSeek controls are era-matched (v4-flash) throughout."""
import sys, glob, json
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(REPO / "scripts"))
from generate_robustness_pack import (  # noqa: E402
    _ex_map, _metric_map, _bootstrap_diff, _bootstrap_mean_pct,
)
from src.llm.cost import batch_cost_usd  # noqa: E402

BATCH = REPO / "runs" / "batches"
MODELS = [("gpt-4o-mini", "GPT"), ("gemini-2.5-flash", "Gemini"), ("deepseek-v3.2", "DS")]


def find(tag: str, model: str) -> Path | None:
    g = sorted(glob.glob(str(BATCH / f"parallel_{tag}_{model}_r*.json")))
    return Path(g[0]) if g else None


def ex_row(label, t_tag, c_tag, model):
    tp, cp = find(t_tag, model), find(c_tag, model)
    if not tp or not cp:
        print(f"  {label:<34} MISSING ({t_tag if not tp else c_tag})")
        return
    n, tex, cex, d, lo, hi = _bootstrap_diff(_ex_map(tp), _ex_map(cp))
    dag = " †" if (lo <= 0 <= hi) else ""
    print(f"  {label:<34}n={n:<4} {tex:5.1f} vs {cex:5.1f}  "
          f"EX {d:+.1f} [{lo:+.1f},{hi:+.1f}]{dag}")


def ledger_row(label, t_tag, c_tag, model):
    tp, cp = find(t_tag, model), find(c_tag, model)
    if not tp or not cp:
        return
    parts = []
    for key, name in (("tokens", "tok"), ("db", "db")):
        n, _, _, d, lo, hi = _bootstrap_mean_pct(_metric_map(tp, key), _metric_map(cp, key))
        dag = "†" if (lo <= 0 <= hi) else ""
        parts.append(f"{name} {d:+.1f}% [{lo:+.1f},{hi:+.1f}]{dag}")
    print(f"  {label:<34}{'  '.join(parts)}")


def cost_row(label, tag, model):
    p = find(tag, model)
    if not p:
        print(f"  {label:<40} MISSING")
        return
    d = json.load(open(p))
    usd = batch_cost_usd(d.get("rows", []), model)
    tok = d.get("total_prompt_tokens", 0) + d.get("total_completion_tokens", 0)
    ex = d.get("ex_accuracy_excluding_api_errors_pct") or d.get("ex_accuracy_pct")
    print(f"  {label:<40} EX {ex:5.1f}  tok {tok:>12,}  "
          f"${usd:.2f}" if usd is not None else f"  {label:<40} cost n/a")


print("=" * 100)
print("A. FULL-500 SCALE-UP — N=10 and N=25 (12-14 Aug, DS = v4-flash era throughout)")
print("=" * 100)
for model, short in MODELS:
    print(f"--- {short} ---")
    ex_row("r10 compose vs P0", "compose_full500_r10", "baseline_full500_r10", model)
    ex_row("r10 compose rep2 vs P0", "compose_full500_r10_rep2", "baseline_full500_r10", model)
    ex_row("r10 P3 stack vs P0", "p3_full500_r10", "baseline_full500_r10", model)
    ex_row("r25 compose vs P0", "compose_full500_r25", "baseline_full500_r25", model)
    ledger_row("r10 compose vs P0", "compose_full500_r10", "baseline_full500_r10", model)
    ledger_row("r10 compose rep2 vs P0", "compose_full500_r10_rep2", "baseline_full500_r10", model)
    ledger_row("r10 P3 stack vs P0", "p3_full500_r10", "baseline_full500_r10", model)
    ledger_row("r25 compose vs P0", "compose_full500_r25", "baseline_full500_r25", model)

print()
print("=" * 100)
print("B. NEW r3 SEEDS (10-11 Aug)")
print("=" * 100)
ex_row("GPT P1 rep2 vs P0", "p1_full500_r3_rep2", "baseline_full500_r3", "gpt-4o-mini")
ex_row("GPT prune rep2 vs P0", "schema_prune_iso_full500_r3_rep2", "baseline_full500_r3", "gpt-4o-mini")
ledger_row("GPT prune rep2 vs P0", "schema_prune_iso_full500_r3_rep2", "baseline_full500_r3", "gpt-4o-mini")
ex_row("Gemini P1 rep2 vs P0", "p1_full500_r3_rep2", "baseline_full500_r3", "gemini-2.5-flash")
ex_row("Gemini P3 redo vs P2 stack", "p3_full500_r3", "fullstack_prune_full500_r3", "gemini-2.5-flash")
ex_row("Gemini P3 redo vs P0", "p3_full500_r3", "baseline_full500_r3", "gemini-2.5-flash")
ledger_row("Gemini P3 redo vs P2 stack", "p3_full500_r3", "fullstack_prune_full500_r3", "gemini-2.5-flash")
ledger_row("GPT P1 rep2 vs P0 (db)", "p1_full500_r3_rep2", "baseline_full500_r3", "gpt-4o-mini")

print()
print("=" * 100)
print("C. USD COSTS (list prices; DS controls = v4-flash era)")
print("=" * 100)
for model, short in MODELS:
    print(f"--- {short} ---")
    base3 = "baseline_full500_r3_v4f" if model == "deepseek-v3.2" else "baseline_full500_r3"
    cost_row("P0 full-500 r3", base3, model)
    cost_row("compose full-500 r3", "compose_full500_r3", model)
    cost_row("P0 full-500 r10", "baseline_full500_r10", model)
    cost_row("compose full-500 r10", "compose_full500_r10", model)
    cost_row("P0 full-500 r25", "baseline_full500_r25", model)
    cost_row("compose full-500 r25", "compose_full500_r25", model)
