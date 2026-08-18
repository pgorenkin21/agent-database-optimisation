#!/usr/bin/env python3
"""Emit the v8 appendix tables as a LaTeX fragment.

The appendix does not count against the paper's page limit, so it carries the
full result matrix and the per-database pruning breakdown that §6 only
summarises. Both are generated from the analysis outputs rather than pasted, so
they cannot drift when a wave lands and `analyze_v8_results.py` is re-run.

    uv run python scripts/make_v8_appendix_tables.py

Writes thesis/paper drafts/generated/appendix_tables.tex, which the appendix
pulls in with \\input{generated/appendix_tables}. Keep that file in the Overleaf
bundle.
"""

from __future__ import annotations

import json
import re
import statistics as st
import sys
from collections import defaultdict
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
NUMBERS = REPO_ROOT / "runs" / "reports" / "v8_numbers.txt"
PRUNE_50 = REPO_ROOT / "runs" / "reports" / "schema_pruning.json"
# The hybrid report, because that is the mode the arm runs and the caption
# claims. All three modes give identical recall and reduction on the full split
# -- selection is driven by the keyword seeds, FK expansion and the recall rules
# rather than by the scoring blend -- so this changes no number, only which file
# backs the table.
PRUNE_500 = REPO_ROOT / "runs" / "reports" / "schema_pruning_full500_hybrid.json"
OUT = REPO_ROOT / "thesis" / "paper drafts" / "generated" / "appendix_tables.tex"

METHOD_LABEL = {
    "pruning": "Schema pruning",
    "P3 facts": "Fact store",
    "prompt cache": "Prompt cache",
    "composed": "Composed",
}
MODEL_LABEL = {"GPT": "GPT-4o mini", "Gemini": "Gemini 2.5 Flash",
               "DeepSeek": "DeepSeek v4-flash"}

ROW_RE = re.compile(
    r"^\s*N=(?P<n>\d+)\s+(?P<model>GPT|Gemini|DeepSeek)\s+n=(?P<obs>\d+)\s+"
    r"EX\s+(?P<ex_t>[\d.]+)v\s*(?P<ex_c>[\d.]+)\s+(?P<ex>[-+][\d.]+)pp\s+"
    r"\[\s*(?P<exlo>[-+][\d.]+),\s*(?P<exhi>[-+][\d.]+)\](?P<exd>.?)\s+"
    r"tok\s+(?P<tok>[-+][\d.]+)%\s+\[\s*(?P<tlo>[-+][\d.]+),\s*(?P<thi>[-+][\d.]+)\](?P<td>.?)\s+"
    r"billed\s+(?P<bil>[-+][\d.]+)%\s+\[\s*(?P<blo>[-+][\d.]+),\s*(?P<bhi>[-+][\d.]+)\](?P<bd>.?)"
)
DAGGER = "\u2020"


def tex_escape_num(v: str) -> str:
    """LaTeX-safe signed number using an en-dash-free math minus."""
    return v.replace("-", "$-$")


def ci(lo: str, hi: str, dag: str) -> str:
    mark = "\\dag{}" if dag == DAGGER else ""
    return f"[{tex_escape_num(lo)}, {tex_escape_num(hi)}]{mark}"


def parse_numbers() -> list[dict]:
    rows, scale, method = [], None, None
    for line in NUMBERS.read_text(encoding="utf-8").splitlines():
        if line.startswith("##########"):
            scale = "50" if "50-task" in line else "500"
            continue
        if line.startswith("---") and line.rstrip().endswith("---"):
            method = line.strip().strip("- ").strip()
            continue
        m = ROW_RE.match(line)
        if m and scale and method:
            d = m.groupdict()
            d["scale"], d["method"] = scale, method
            rows.append(d)
    return rows


def matrix_table(rows: list[dict], scale: str) -> str:
    sel = [r for r in rows if r["scale"] == scale]
    if not sel:
        return ""
    tasks = "50-task subset" if scale == "50" else "full 500-task split"
    out = [
        "\\begin{table*}[t]",
        # The caption opens in an f-string, where `{{` is one literal brace, and
        # closes in a plain string, where `}` is one literal brace. Writing `}}`
        # on the closing line -- mirroring the opener by eye -- emits two and
        # fails the compile with a stray `}`. Count braces per string literal,
        # not across the pair.
        f"\\caption{{Complete {tasks} matrix: every measured cell against its matched",
        "baseline, with paired bootstrap 95\\% confidence intervals.",
        "\\dag{} marks an interval containing zero.}",
        f"\\label{{tab:appendix-matrix-{scale}}}",
        "\\centering\\footnotesize",
        "\\begin{tabular}{@{}llrrlrlrl@{}}",
        "\\toprule",
        "Method & Model & $N$ & \\multicolumn{2}{c}{EX $\\Delta$ (pp)} & "
        "\\multicolumn{2}{c}{Raw tokens} & \\multicolumn{2}{c}{Billed tokens} \\\\",
        "\\cmidrule(lr){4-5}\\cmidrule(lr){6-7}\\cmidrule(lr){8-9}",
        " & & & value & 95\\% CI & value & 95\\% CI & value & 95\\% CI \\\\",
        "\\midrule",
    ]
    last = None
    for key in ("pruning", "P3 facts", "prompt cache", "composed"):
        block = [r for r in sel if r["method"] == key]
        if not block:
            continue
        block.sort(key=lambda r: (list(MODEL_LABEL).index(r["model"]), int(r["n"])))
        if last is not None:
            out.append("\\midrule")
        last = key
        for i, r in enumerate(block):
            meth = METHOD_LABEL[key] if i == 0 else ""
            out.append(
                f"{meth} & {MODEL_LABEL[r['model']]} & {r['n']} & "
                f"{tex_escape_num(r['ex'])} & {ci(r['exlo'], r['exhi'], r['exd'])} & "
                f"{tex_escape_num(r['tok'])}\\% & {ci(r['tlo'], r['thi'], r['td'])} & "
                f"{tex_escape_num(r['bil'])}\\% & {ci(r['blo'], r['bhi'], r['bd'])} \\\\"
            )
    out += ["\\bottomrule", "\\end{tabular}", "\\end{table*}", ""]
    return "\n".join(out)


def per_db_table() -> str:
    if not PRUNE_500.exists():
        return ""
    # Two recall definitions, and they differ by six points. "Complete" is the
    # fraction of tasks retaining EVERY gold table -- the 89.6% quoted in the body
    # and the only one that matters, since a query needs all its tables. "Mean" is
    # the average per-task fraction and is more flattering; it is shown alongside
    # only to make the shape of a miss visible (most misses lose one table of two).
    # Full-schema count follows the report: pruning_applied == False, i.e. the
    # prune yielded no reduction. `fallback_reason` is never populated offline.
    agg: dict[str, dict] = defaultdict(
        lambda: {"red": [], "rec": [], "complete": 0, "full": 0, "n": 0})
    for r in json.load(PRUNE_500.open())["rows"]:
        a = agg[r["db_id"]]
        a["n"] += 1
        a["red"].append(float(r["reduction_pct"]))
        a["rec"].append(float(r["gold_table_recall"]))
        if float(r["gold_table_recall"]) >= 1.0:
            a["complete"] += 1
        if not r.get("pruning_applied"):
            a["full"] += 1
    out = [
        "\\begin{table}[t]",
        "\\caption{Offline hybrid pruning by database, full 500-task split.",
        "\\emph{Complete} recall is the share of tasks retaining every gold table, the",
        "figure quoted in the body, and the one that matters, since a query needs all of",
        "them. \\emph{Mean} is the average per-task fraction, shown only to make the shape",
        "of a miss visible: most misses drop one table of two rather than all. Databases",
        "without a hand-written recall rule account for the bulk of the shortfall.}",
        "\\label{tab:appendix-perdb}",
        "\\centering\\footnotesize",
        "\\begin{tabular}{@{}lrrrrr@{}}",
        "\\toprule",
        " & & & \\multicolumn{2}{c}{Gold recall} & Full \\\\",
        "\\cmidrule(lr){4-5}",
        "Database & Tasks & Reduction & complete & mean & schema \\\\",
        "\\midrule",
    ]
    for db in sorted(agg, key=lambda d: (-agg[d]["complete"] / agg[d]["n"], d)):
        a = agg[db]
        out.append(
            f"\\texttt{{{db.replace('_', chr(92) + '_')}}} & {a['n']} & "
            f"{st.mean(a['red']):.1f}\\% & {100 * a['complete'] / a['n']:.1f}\\% & "
            f"{100 * st.mean(a['rec']):.1f}\\% & {a['full']} \\\\"
        )
    n_all = sum(a["n"] for a in agg.values())
    tot_red = st.mean([v for a in agg.values() for v in a["red"]])
    tot_rec = st.mean([v for a in agg.values() for v in a["rec"]])
    tot_cpl = sum(a["complete"] for a in agg.values())
    out += [
        "\\midrule",
        f"\\textbf{{All}} & {n_all} & {tot_red:.1f}\\% & "
        f"\\textbf{{{100 * tot_cpl / n_all:.1f}\\%}} & {100 * tot_rec:.1f}\\% & "
        f"{sum(a['full'] for a in agg.values())} \\\\",
        "\\bottomrule", "\\end{tabular}", "\\end{table}", "",
    ]
    return "\n".join(out)


def main() -> int:
    if not NUMBERS.exists():
        print(f"missing {NUMBERS}; run scripts/analyze_v8_results.py first")
        return 1
    rows = parse_numbers()
    print(f"parsed {len(rows)} cells "
          f"({sum(r['scale'] == '50' for r in rows)} at 50-task, "
          f"{sum(r['scale'] == '500' for r in rows)} at 500-task)")

    parts = [
        "% Generated by scripts/make_v8_appendix_tables.py -- do not edit by hand.",
        "% Re-run after any change to runs/reports/v8_numbers.txt.",
        "",
        matrix_table(rows, "50"),
        matrix_table(rows, "500"),
        per_db_table(),
    ]
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text("\n".join(p for p in parts if p), encoding="utf-8")
    print(f"wrote {OUT.relative_to(REPO_ROOT)}")

    txt = OUT.read_text()
    ok = True
    for env in ("table", "table*", "tabular"):
        o = len(re.findall(r"\\begin\{" + re.escape(env) + r"\}", txt))
        c = len(re.findall(r"\\end\{" + re.escape(env) + r"\}", txt))
        ok &= o == c
        print(f"  {env:8s} {o} begin / {c} end {'OK' if o == c else '*** MISMATCH'}")

    # Environment counts alone missed a stray `}` in a caption that survived
    # several rebuilds and would have failed the first compile. Braces are what
    # actually break LaTeX, so count them too -- and report the offending line
    # rather than just a total, since a nonzero sum says nothing about where.
    depth, first_bad = 0, None
    for lineno, line in enumerate(txt.splitlines(), 1):
        stripped = re.sub(r"(?<!\\)%.*$", "", line).replace("\\{", "").replace("\\}", "")
        depth += stripped.count("{") - stripped.count("}")
        if depth < 0 and first_bad is None:
            first_bad = lineno
    if depth or first_bad:
        ok = False
        where = f" (first unmatched close at line {first_bad})" if first_bad else ""
        print(f"  braces   net {depth:+d} *** MISMATCH{where}")
    else:
        print("  braces   balanced OK")

    if not ok:
        print("  refusing to report success -- fix the generator before assembling")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
