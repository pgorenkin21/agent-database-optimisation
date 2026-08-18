#!/usr/bin/env python3
"""Typeset the reflective essay to the Project Guide format and count pages.

The guide (MSc Project Guide 25/26, §4.5.1) fixes the format: Arial, 11pt,
single line spacing, single column, 5 pages max excluding references. Word
counts are a poor proxy for that -- headings, list spacing and paragraph breaks
all consume vertical space -- so this measures instead of estimating, the same
discipline scripts/v8_pagecount.sh applies to the paper.

Helvetica stands in for Arial. The two are metric-compatible by design, so line
breaks and therefore page breaks land in the same places.

    uv run python scripts/essay_pagecount.py                       # v9 essay
    uv run python scripts/essay_pagecount.py --md <path> --keep

Requires pdflatex (brew install texlive).
"""

from __future__ import annotations

import argparse
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
DEFAULT_MD = REPO / "thesis" / "paper drafts" / "reflective_essay_v9.md"
PDFLATEX = "/opt/homebrew/bin/pdflatex"

PREAMBLE = r"""\documentclass[11pt,a4paper,oneside]{article}
\usepackage[utf8]{inputenc}
\usepackage[T1]{fontenc}
\usepackage[scaled]{helvet}
\renewcommand{\familydefault}{\sfdefault}
\usepackage[margin=2.5cm]{geometry}
\usepackage{parskip}
\usepackage{microtype}
\linespread{1.0}
\setlength{\emergencystretch}{3em}
\pagestyle{plain}
\begin{document}
"""

# Unicode the source uses that pdflatex will not take verbatim.
UNICODE = {
    "\u2013": "--", "\u2014": "---", "\u2018": "`", "\u2019": "'",
    "\u201c": "``", "\u201d": "''", "\u00b7": r"\textperiodcentered{}",
    "\u00a7": r"\S{}", "\u00d7": r"$\times$", "\u2265": r"$\ge$",
    "\u2264": r"$\le$", "\u2192": r"$\rightarrow$", "\u2020": r"\dag{}",
}
# Order matters: backslash first, or it escapes the escapes.
ESCAPE = [("\\", r"\textbackslash{}"), ("&", r"\&"), ("%", r"\%"),
          ("$", r"\$"), ("#", r"\#"), ("_", r"\_"), ("{", r"\{"),
          ("}", r"\}"), ("~", r"\textasciitilde{}"), ("^", r"\textasciicircum{}")]


def inline(text: str) -> str:
    for a, b in ESCAPE:
        text = text.replace(a, b)
    for a, b in UNICODE.items():
        text = text.replace(a, b)
    text = re.sub(r"\*\*(.+?)\*\*", r"\\textbf{\1}", text)
    text = re.sub(r"(?<!\*)\*([^*]+?)\*(?!\*)", r"\\emph{\1}", text)
    text = re.sub(r"`(.+?)`", r"\\texttt{\1}", text)
    return text


def convert(md: str) -> str:
    out = []
    for raw in md.splitlines():
        line = raw.rstrip()
        if not line:
            out.append("")
        elif line.startswith("---") and set(line) == {"-"}:
            out.append(r"\vspace{0.5em}\hrule\vspace{0.5em}")
        elif line.startswith("# "):
            out.append(r"\section*{" + inline(line[2:]) + "}")
        elif line.startswith("## "):
            out.append(r"\subsection*{" + inline(line[3:]) + "}")
        elif line.startswith("> "):
            # The format note is scaffolding for me, not essay content. It is
            # typeset small so the page count reflects what gets submitted.
            out.append(r"{\small\itshape " + inline(line[2:]) + r"\par}")
        else:
            out.append(inline(line))
    return PREAMBLE + "\n".join(out) + "\n\\end{document}\n"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--md", default=str(DEFAULT_MD))
    ap.add_argument("--keep", action="store_true", help="keep the build dir")
    args = ap.parse_args()

    src = Path(args.md)
    if not src.exists():
        print(f"missing {src}")
        return 1
    if not Path(PDFLATEX).exists():
        print(f"pdflatex not found at {PDFLATEX}")
        return 1

    build = Path(tempfile.mkdtemp(prefix="essay-"))
    tex = build / "essay.tex"
    tex.write_text(convert(src.read_text(encoding="utf-8")), encoding="utf-8")
    for _ in range(2):
        subprocess.run([PDFLATEX, "-interaction=nonstopmode", "essay.tex"],
                       cwd=build, capture_output=True)

    pdf = build / "essay.pdf"
    if not pdf.exists():
        log = (build / "essay.log").read_text(errors="ignore")
        print("compile failed:")
        print("\n".join(l for l in log.splitlines() if l.startswith("!"))[:2000])
        return 1

    import pypdf
    pages = len(pypdf.PdfReader(str(pdf)).pages)
    words = len(re.findall(r"[A-Za-z][A-Za-z'-]+", src.read_text(encoding="utf-8")))

    # How full the last page is, so "5 pages" that is really 4.5 reads as
    # headroom rather than as a hard fit. Measure the last page's text depth
    # against a FULL page's, not against the paper height: the top and bottom
    # margins are dead space on every page and would flatter the number.
    reader = pypdf.PdfReader(str(pdf))

    def depths(page) -> list[float]:
        # Skip the folio. It sits below the bottom margin on every page, so
        # counting it makes every page look equally full.
        ys: list[float] = []

        def visit(t, cm, tm, font, size):
            s = t.strip()
            if s and not s.isdigit():
                ys.append(tm[5])

        page.extract_text(visitor_text=visit)
        return ys

    # The reference is the DEEPEST any earlier page reaches, not the page before.
    # An earlier page can break a paragraph early and end well short of the
    # margin, which would make a half-empty last page score as full.
    earlier = [depths(p) for p in reader.pages[:-1]]
    ys = depths(reader.pages[-1])
    fill = 0.0
    if len(ys) > 1 and any(len(e) > 1 for e in earlier):
        top = max(max(e) for e in earlier if e)
        floor = min(min(e) for e in earlier if e)
        fill = min(1.0, (top - min(ys)) / (top - floor))

    print(f"{src.name}: {words} words")
    print(f"PAGES = {pages}   (limit 5, excluding references)")
    print(f"last page is ~{fill * 100:.0f}% full")
    if pages > 5:
        print(f"  OVER by {pages - 5} page(s)")
    else:
        print("  within limit")

    dest = src.with_suffix(".pdf")
    shutil.copy(pdf, dest)
    print(f"wrote {dest.relative_to(REPO)}")
    if args.keep:
        print(f"build dir: {build}")
    else:
        shutil.rmtree(build)
    return 0


if __name__ == "__main__":
    sys.exit(main())
