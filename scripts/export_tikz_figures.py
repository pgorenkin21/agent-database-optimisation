#!/usr/bin/env python3
"""Export the paper's TikZ figures as standalone PNGs for the slide deck.

Fig. 1 (prompt anatomy) is drawn in TikZ inside draft_paper_ieee_v9.tex. The
slide deck needs it as an image, and screenshotting the paper PDF gives a
low-resolution crop with the caption attached. This lifts the `tikzpicture`
environment out of the paper verbatim, compiles it against the `standalone`
class, and rasterises it, so the slide and the paper cannot drift apart.

The figure is lifted, never retyped. If §3's layout changes, re-run this.

    uv run python scripts/export_tikz_figures.py

Writes thesis/figures/slides/fig1_anatomy.png. Needs pdflatex and ImageMagick.
"""

from __future__ import annotations

import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
PAPER = REPO / "thesis" / "paper drafts" / "draft_paper_ieee_v9.tex"
OUT = REPO / "thesis" / "figures" / "slides" / "fig1_anatomy.png"
PDFLATEX = "/opt/homebrew/bin/pdflatex"
MAGICK = "/opt/homebrew/bin/magick"

# The paper's \ref calls resolve against its own labels, which do not exist in a
# standalone build. Rendering "§??" on a slide is worse than rendering the
# section number, so the references are replaced with their printed values.
SECTION_NUMBERS = {"sec:prune": "4.1", "sec:p3": "4.2", "sec:pcache": "4.3"}

PREAMBLE = r"""\documentclass[border=6pt,varwidth=false]{standalone}
\usepackage[T1]{fontenc}
\usepackage{tikz}
\usetikzlibrary{positioning,shapes.geometric,arrows.meta}
% The paper sets this inside IEEEtran at 10pt. standalone defaults to 10pt too,
% so \footnotesize matches the paper; the deck scales the raster, not the type.
\begin{document}
"""


def extract(tex: str, index: int = 0) -> str:
    blocks = re.findall(r"\\begin\{tikzpicture\}.*?\\end\{tikzpicture\}", tex, re.S)
    if len(blocks) <= index:
        raise SystemExit(f"no tikzpicture #{index} in {PAPER.name}")
    body = blocks[index]
    for label, number in SECTION_NUMBERS.items():
        body = body.replace(f"\\ref{{{label}}}", number)
    if "\\ref{" in body:
        stray = re.findall(r"\\ref\{([^}]*)\}", body)
        raise SystemExit(f"unresolved \\ref in the lifted figure: {stray}. "
                         "Add them to SECTION_NUMBERS.")
    return body


def main() -> int:
    for tool in (PDFLATEX, MAGICK):
        if not Path(tool).exists():
            print(f"missing {tool}")
            return 1
    if not PAPER.exists():
        print(f"missing {PAPER}")
        return 1

    body = extract(PAPER.read_text(encoding="utf-8"))
    build = Path(tempfile.mkdtemp(prefix="tikz-"))
    (build / "fig.tex").write_text(PREAMBLE + body + "\n\\end{document}\n",
                                   encoding="utf-8")
    for _ in range(2):
        subprocess.run([PDFLATEX, "-interaction=nonstopmode", "fig.tex"],
                       cwd=build, capture_output=True)
    pdf = build / "fig.pdf"
    if not pdf.exists():
        log = (build / "fig.log").read_text(errors="ignore")
        print("compile failed:")
        print("\n".join(line for line in log.splitlines() if line.startswith("!")))
        return 1

    OUT.parent.mkdir(parents=True, exist_ok=True)
    # 600dpi: the figure is ~7cm wide in the paper, so a slide blows it up
    # roughly fourfold and 300dpi would show it.
    subprocess.run([MAGICK, "-density", "600", str(pdf), "-background", "white",
                    "-alpha", "remove", "-alpha", "off", str(OUT)], check=True)
    size = subprocess.run([MAGICK, "identify", "-format", "%wx%h", str(OUT)],
                          capture_output=True, text=True).stdout
    print(f"wrote {OUT.relative_to(REPO)}  ({size})")
    shutil.rmtree(build)
    return 0


if __name__ == "__main__":
    sys.exit(main())
