#!/usr/bin/env python3
"""Measure the v8 body length against the 8 +/- 10% page limit.

The limit excludes references and the appendix, so the body ends at
``\\section*{References}``. An earlier version of this measurement split only on
``\\section{`` and therefore swept the entire reference list and appendix into
the conclusion's bucket, reporting the stub conclusion as 1.31pp. Anything that
counts pages has to stop at that boundary explicitly.

Page estimates are approximations for IEEEtran two-column at 10pt:
WORDS_PER_PAGE prose, plus a flat allowance per float. They are for steering
during drafting; only pdflatex gives the real count.

  uv run python scripts/v8_budget.py
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
TEX = REPO / "thesis" / "paper drafts" / "draft_paper_ieee_v8.tex"

WORDS_PER_PAGE = 950.0
PP_PER_FLOAT = 0.24          # single-column float at ~\columnwidth
PP_PER_WIDE_FLOAT = 0.34     # table*/figure* spans both columns

CEILING = 8.8                # 8 pages + 10%
FLOOR = 7.2                  # 8 pages - 10%

# Planned budget for what is not yet written, so the projection is honest about
# what it is assuming rather than quietly costing unwritten sections at zero.
# Only sections with no drafted LaTeX belong here. A drafted section left in
# this dict is counted twice -- once from the .tex, once as "planned" -- which
# overstated the projection by 0.85pp the moment §6.2/6.4/6.5 were written.
# A section is drafted when its stub no longer appears in the assembled .tex.
PLANNED_REMAINING: dict[str, float] = {}   # every section is drafted
# Title block, author, abstract and keywords sit before the first \section, so
# the section loop never sees them. Measure them rather than carrying a planned
# figure: the abstract is drafted, and assuming 0.30 for it understated a
# 244-word abstract by about a third of its true cost.
TITLE_BLOCK_PP = 0.15  # \title + \author + \maketitle rules, roughly fixed
# LaTeX comments set no type. Counting them inflated section 3 by 0.13pp the
# moment a layout note was added to Fig. 1 -- a section appearing to grow when
# only its commentary did. Strip them before anything else.
COMMENT_RE = re.compile(r"(?<!\\)%.*?$", re.M)
FLOAT_RE = re.compile(r"\\begin\{(figure|table|algorithm)(\*?)\}")
ENV_RE = re.compile(r"\\begin\{(figure\*?|table\*?|algorithm|tabular|algorithmic)\}"
                    r".*?\\end\{\1\}", re.S)
MACRO_RE = re.compile(r"\\[a-zA-Z@]+\*?(\[[^]]*\])?(\{[^{}]*\})?")


def measure(chunk: str) -> tuple[int, float]:
    """Prose words and float allowance for one section."""
    chunk = COMMENT_RE.sub("", chunk)
    floats = 0.0
    for kind, star in FLOAT_RE.findall(chunk):
        floats += PP_PER_WIDE_FLOAT if star else PP_PER_FLOAT
    prose = MACRO_RE.sub(" ", ENV_RE.sub("", chunk))
    return len(re.findall(r"[A-Za-z][A-Za-z'-]+", prose)), floats


def main() -> int:
    if not TEX.exists():
        print(f"missing {TEX}; run scripts/assemble_v8.py first")
        return 1
    tex = TEX.read_text(encoding="utf-8")

    # The body is everything from the first \section to the reference list.
    end = re.search(r"\\section\*\{References\}", tex)
    body = tex[: end.start()] if end else tex
    if not end:
        print("  [warn] no \\section*{References} found -- counting to EOF, "
              "which will include the appendix and overstate the body")

    print(f"{'section':42s} {'words':>6} {'floats':>7} {'pp':>6}")
    total_w, total_f = 0, 0.0
    for chunk in re.split(r"\\section\{", body)[1:]:
        name = chunk.split("}")[0]
        w, f = measure(chunk)
        total_w += w
        total_f += f
        print(f"{name[:42]:42s} {w:6d} {f:7.2f} {w / WORDS_PER_PAGE + f:6.2f}")

    drafted = total_w / WORDS_PER_PAGE + total_f
    print(f"\n{'drafted body':42s} {total_w:6d} {total_f:7.2f} {drafted:6.2f}")

    m = re.search(r"\\begin\{abstract\}(.*?)\\end\{abstract\}", tex, re.S)
    abs_w, _ = measure(m.group(1)) if m else (0, 0.0)
    front_pp = abs_w / WORDS_PER_PAGE + TITLE_BLOCK_PP
    print(f"{'front matter (title + abstract)':42s} {abs_w:6d} {'':7s} {front_pp:6.2f}")

    print("\nplanned, not yet written:")
    for label, pp in PLANNED_REMAINING.items():
        print(f"  {label:40s} {pp:6.2f}")
    projected = drafted + front_pp + sum(PLANNED_REMAINING.values())

    print(f"\nPROJECTED BODY {projected:.2f}pp   (limit {FLOOR}--{CEILING}, "
          f"excl. references and appendix)")
    if projected > CEILING:
        print(f"  OVER by {projected - CEILING:.2f}pp -- see the budget note in "
              f"v8_sections/README.md")
    elif projected < FLOOR:
        print(f"  UNDER by {FLOOR - projected:.2f}pp")
    else:
        print("  within limit")
    return 0


if __name__ == "__main__":
    sys.exit(main())
