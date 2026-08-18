#!/usr/bin/env python3
"""Recompute DeepSeek full-500 comparisons within the v4-flash era only."""
import sys, glob
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "scripts"))
from generate_robustness_pack import (  # noqa: E402
    _ex_map, _metric_map, _bootstrap_diff, _bootstrap_mean_pct,
)

BATCH = REPO / "runs" / "batches"


def find(tag: str) -> Path | None:
    g = sorted(glob.glob(str(BATCH / f"parallel_{tag}_deepseek*.json")))
    return Path(g[0]) if g else None


# treatment, control, label — all treatments are Aug/v4-flash batches
PAIRS = [
    ("p1_full500_r3_v4f",       "baseline_full500_r3_v4f", "P1 vs P0"),
    ("pc_full500_r3_v4f",       "baseline_full500_r3_v4f", "prompt-cache vs P0"),
    ("p4_full500_r3",           "pc_full500_r3_v4f",       "P4 vs PC"),
    ("p4_full500_r3_rep2",      "pc_full500_r3_v4f",       "P4 rep2 vs PC"),
    ("p1p4_full500_r3",         "p1_full500_r3_v4f",       "P1+P4 vs P1"),
    ("compose_full500_r3",      "baseline_full500_r3_v4f", "compose vs P0"),
    ("compose_full500_r3_rep2", "baseline_full500_r3_v4f", "compose rep2 vs P0"),
    ("p3_full500_r3",           "baseline_full500_r3_v4f", "P3 stack vs P0"),
    ("p3_full500_r3_rep2",      "baseline_full500_r3_v4f", "P3 stack rep2 vs P0"),
    ("schema_prune_iso_full500_r3_v4f", "baseline_full500_r3_v4f", "prune vs P0"),
    ("p3_full500_r3",           "fullstack_prune_full500_r3_v4f", "P3 stack vs P2 stack"),
    ("p3_full500_r3_rep2",      "fullstack_prune_full500_r3_v4f", "P3 rep2 vs P2 stack"),
    ("fullstack_prune_full500_r3_v4f", "baseline_full500_r3_v4f", "P2 stack vs P0"),
]

# what the paper currently claims (cross-era), for side-by-side
OLD = {
    "P1 vs P0": "+1.2 †",
    "prompt-cache vs P0": "+0.8 †",
    "P4 vs PC": "+6.0 [+2.6,+9.2]",
    "P4 rep2 vs PC": "+6.0 [+2.6,+9.6]",
    "P1+P4 vs P1": "+5.8 [+2.6,+9.0]",
    "compose vs P0": "+7.0 [+3.8,+10.4]",
    "compose rep2 vs P0": "+7.4 [+3.8,+11.0]",
    "P3 stack vs P0": "n/a",
    "P3 stack rep2 vs P0": "+7.4 [+3.8,+11.1]",
    "prune vs P0": "+0.4 †",
    "P3 stack vs P2 stack": "+3.0 †",
    "P3 rep2 vs P2 stack": "+4.8 [+1.8,+8.0]",
    "P2 stack vs P0": "n/a",
}

print("=" * 96)
print("DeepSeek full-500 N=3 — WITHIN-ERA (all v4-flash), paired bootstrap 95% CI")
print("=" * 96)
print(f"{'Comparison':<24}{'n':>5}{'treat':>8}{'ctrl':>8}{'EX Δpp [95% CI]':>26}   {'v5 claimed (cross-era)'}")
for t_tag, c_tag, label in PAIRS:
    tp, cp = find(t_tag), find(c_tag)
    if not tp or not cp:
        print(f"{label:<24}  MISSING ({t_tag if not tp else c_tag})")
        continue
    n, tex, cex, d, lo, hi = _bootstrap_diff(_ex_map(tp), _ex_map(cp))
    sig = "" if (lo <= 0 <= hi) else "  *"
    dag = " †" if (lo <= 0 <= hi) else ""
    print(f"{label:<24}{n:>5}{tex:>8.1f}{cex:>8.1f}"
          f"{f'{d:+.1f} [{lo:+.1f},{hi:+.1f}]{dag}':>26}   {OLD.get(label,''):<20}{sig}")

print()
print("=" * 96)
print("Ledgers — WITHIN-ERA paired % change")
print("=" * 96)
print(f"{'Comparison':<24}{'metric':>8}{'n':>5}{'Δ% [95% CI]':>28}")
for t_tag, c_tag, label in PAIRS:
    tp, cp = find(t_tag), find(c_tag)
    if not tp or not cp:
        continue
    for key, name in (("tokens", "tokens"), ("db", "db")):
        n, tm, cm, d, lo, hi = _bootstrap_mean_pct(_metric_map(tp, key), _metric_map(cp, key))
        dag = " †" if (lo <= 0 <= hi) else ""
        print(f"{label:<24}{name:>8}{n:>5}{f'{d:+.1f}% [{lo:+.1f},{hi:+.1f}]{dag}':>28}")

print()
print("=" * 96)
print("Era coverage — every control used above must be a v4-flash batch")
print("=" * 96)
controls = sorted({c for _, c, _ in PAIRS})
for c in controls:
    p = find(c)
    era = "v4-flash" if c.endswith("_v4f") else "SEE NOTE"
    print(f"  {c:<38} {'present' if p else 'ABSENT':<9} {era}")
print()
print("  Superseded July/V3.2 controls (must NOT be used for DeepSeek deltas):")
for tag in ("baseline_full500_r3", "pc_full500_r3", "p1_full500_r3",
            "schema_prune_iso_full500_r3", "fullstack_prune_full500_r3"):
    p = find(tag)
    print(f"    {tag:<36} {'on disk' if p else 'absent':<9} -> use {tag}_v4f")
print()
print("  NOTE: p3_full500_r3* and compose/p4/p1p4 batches are Aug (v4-flash)")
print("  treatments, so they need no _v4f twin. generate_robustness_pack.py")
print("  still points DeepSeek at the July controls and is NOT corrected.")
