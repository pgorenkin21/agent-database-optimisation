#!/usr/bin/env python3
"""Additivity check and EX audit, parsed from runs/reports/v8_numbers.txt.

Every earlier version of this table was a hand-transcribed list of rows, which
is the one thing the §6.4 brief warns against: isolated and composed cells must
come from the same generation of the report, and a hand-copied row silently
survives a refresh that moves it. This reads the report instead, so the table
cannot drift from the numbers it claims to summarise.

The null is *multiplicative* -- three independent proportional reductions
compose as a product, not a sum. Say so wherever the gap is quoted; an additive
null gives materially different gaps.

  uv run python scripts/v8_additivity.py
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
REPORT = REPO / "runs" / "reports" / "v8_numbers.txt"

METHOD_KEY = {
    "pruning": "prune",
    "P3 facts": "p3",
    "prompt cache": "pc",
    "composed": "comp",
}
MODELS = ("GPT", "Gemini", "DeepSeek")

# N=3 GPT n=50 EX 58.0v 56.0 +2.0pp [-6.0,+10.0]† tok -25.8% [...]† billed -24.3% [...]
ROW = re.compile(
    r"\s+N=(\d+)\s+(\S+)\s+n=(\d+)\s+"
    r"EX\s+[\d.]+v\s*[\d.]+\s+([-+][\d.]+)pp\s+\[\s*([-+][\d.]+),\s*([-+][\d.]+)\](.)\s+"
    r"tok\s+([-+][\d.]+)%\s+\[\s*([-+][\d.]+),\s*([-+][\d.]+)\](.)\s+"
    r"billed\s+([-+][\d.]+)%\s+\[\s*([-+][\d.]+),\s*([-+][\d.]+)\](.)"
)


def parse(path: Path) -> tuple[dict, list]:
    cells: dict[tuple[str, int, str, str], dict] = {}
    ex_significant: list[tuple] = []
    scale = method = None
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.startswith("##########"):
            scale = line.split()[1].split("-")[0]
        head = re.match(r"--- (.+) ---", line.strip())
        if head:
            method = METHOD_KEY[head.group(1)]
        m = ROW.match(line)
        if not m or scale is None or method is None:
            continue
        n, model = int(m.group(1)), m.group(2)
        cells[(scale, n, model, method)] = {
            "n": int(m.group(3)),
            "ex": float(m.group(4)),
            "tok": float(m.group(8)),
            "billed": float(m.group(12)),
        }
        if m.group(7) != "†":
            ex_significant.append(
                (scale, n, model, method, float(m.group(4)), m.group(5), m.group(6))
            )
    return cells, ex_significant


def main() -> int:
    if not REPORT.exists():
        print(f"missing {REPORT}; run scripts/analyze_v8_results.py first")
        return 1
    cells, ex_sig = parse(REPORT)

    print(f"cells parsed: {len(cells)}")
    print(f"EX intervals excluding zero: {len(ex_sig)} of {len(cells)}")
    for scale, n, model, method, d, lo, hi in ex_sig:
        print(f"    {scale}t N={n} {model} {method}: {d:+.1f}pp [{lo}, {hi}]")
    # 95% intervals over k comparisons throw ~0.05k exceptions under a true null.
    print(f"    (expected under a true null at 95%: ~{0.05 * len(cells):.1f})")

    print("\nadditivity -- measured composed vs MULTIPLICATIVE prediction from isolated parts")
    print(f"{'scale':>6} {'N':>3} {'model':9} {'prune':>7} {'p3':>7} {'pc':>7}"
          f" {'pred':>8} {'meas':>8} {'gap':>8}  verdict")
    tally = {"beats": 0, "misses": 0}
    for scale in ("50", "500"):
        for n in (3, 10, 25):
            for model in MODELS:
                parts = [cells.get((scale, n, model, k)) for k in ("prune", "p3", "pc")]
                comp = cells.get((scale, n, model, "comp"))
                if comp is None or any(p is None for p in parts):
                    continue
                factor = 1.0
                for p in parts:
                    factor *= 1 + p["tok"] / 100
                pred = 100 * (factor - 1)
                gap = comp["tok"] - pred
                verdict = "beats" if gap < 0 else "misses"
                tally[verdict] += 1
                print(f"{scale:>6} {n:>3} {model:9} {parts[0]['tok']:+7.1f} {parts[1]['tok']:+7.1f}"
                      f" {parts[2]['tok']:+7.1f} {pred:+8.1f} {comp['tok']:+8.1f} {gap:+8.1f}"
                      f"  {verdict}")
    total = tally["beats"] + tally["misses"]
    print(f"\nstack beats the product of its parts in {tally['beats']} of {total} configurations")

    incomplete = [
        (scale, n, model, method)
        for scale, ns in (("50", (3, 10, 25)), ("500", (3, 10)))
        for n in ns
        for model in MODELS
        for method in ("prune", "p3", "pc", "comp")
        if (scale, n, model, method) not in cells
    ]
    if incomplete:
        print(f"\nmissing cells ({len(incomplete)}):")
        for c in incomplete:
            print(f"    {c[0]}t N={c[1]} {c[2]} {c[3]}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
