#!/usr/bin/env bash
# Compile the Overleaf bundle and report the TRUE body page count.
#
# The body ends at \section*{References} -- references and the appendix do not
# count against the 8 +/- 10% limit. Undrafted sections (if any remain) are
# filled with placeholder prose at their planned length, so the number answers
# "how long will the finished body be?" rather than "how long is it so far".
#
# Requires pdflatex (brew install texlive) and pypdf in the project venv.
#
#   bash scripts/v8_pagecount.sh          # defaults to v9, the current paper
#   bash scripts/v8_pagecount.sh v8       # measure an older bundle
set -euo pipefail

REPO="$(cd "$(dirname "$0")/.." && pwd)"
VER="${1:-v9}"
BUILD="${V8_BUILD_DIR:-/private/tmp/claude-501/-Users-pgorenkin-Desktop-Cursor-Agent-Database-Optimisation/b0517ce4-5d43-417f-83b5-ce60098f1ad6/scratchpad/build}"
ZIP="$REPO/thesis/paper drafts/draft_paper_ieee_${VER}_overleaf.zip"
PDFLATEX="${PDFLATEX:-/opt/homebrew/bin/pdflatex}"

[ -x "$PDFLATEX" ] || { echo "pdflatex not found at $PDFLATEX"; exit 1; }
[ -f "$ZIP" ] || { echo "missing $ZIP -- run scripts/assemble_${VER}.py --zip"; exit 1; }

rm -rf "$BUILD"; mkdir -p "$BUILD"; cd "$BUILD"
unzip -q "$ZIP"

VER="$VER" python3 - <<'PYFILL'
from pathlib import Path
import os
p = Path(f"draft_paper_ieee_{os.environ['VER']}.tex"); s = p.read_text()
filler = ("Placeholder sentence standing in for prose at the planned length so "
          "the page count reflects a finished body. ")
planned = {"07\\_discussion": 570, "08\\_conclusion": 380}   # from v8_sections/README.md
for stem, words in planned.items():
    stub = ("\\textbf{[TODO --- not yet drafted. See "
            f"\\texttt{{v8\\_sections/{stem}.md}}.]}}")
    if stub in s:
        s = s.replace(stub, (filler * max(1, round(words / len(filler.split())))).strip())
s = s.replace("\\section*{References}", "\\label{pg:endbody}\n\\section*{References}", 1)
Path("probe.tex").write_text(s)
PYFILL

for i in 1 2 3; do "$PDFLATEX" -interaction=nonstopmode probe.tex >/dev/null 2>&1 || true; done

ENDPAGE=$(sed -n 's/.*newlabel{pg:endbody}{{[^}]*}{\([0-9]*\)}.*/\1/p' probe.aux)

cd "$REPO"
uv run python - "$BUILD/probe.pdf" "$ENDPAGE" <<'PYMEASURE'
import sys
import pypdf

# Measure where the reference list starts from its RENDERED POSITION, not from a
# character offset. References are set \scriptsize and pack far more characters
# per unit height than body text, so a character fraction understated the body
# and needed a fudge factor -- which saturated at the page boundary and could
# not tell 8.9 from 9.2, exactly the range the decision turns on.
pdf, endpage = sys.argv[1], int(sys.argv[2])
reader = pypdf.PdfReader(pdf)
page = reader.pages[endpage - 1]

runs = []
def visit(text, cm, tm, font, size):
    if text.strip():
        runs.append((tm[4], tm[5], text.strip()))
page.extract_text(visitor_text=visit)

# IEEEtran sets \section*{References} in small caps, so the extracted run reads
# "EFERENCES" after the larger initial letter is emitted separately.
head = next((r for r in runs if "EFERENC" in r[2].upper()), None)
if head is None:
    raise SystemExit("could not locate the References heading on the body's last page")

width = float(page.mediabox.width)
top = max(y for _, y, _ in runs)
bottom = min(y for _, y, _ in runs)
hx, hy, _ = head
col = 0 if hx < width / 2 else 1
frac_in_col = (top - hy) / (top - bottom)
body = (endpage - 1) + (col + frac_in_col) / 2

print(f"references start in column {col + 1} of page {endpage}, "
      f"{frac_in_col * 100:.0f}% down it")
print(f"BODY = {body:.2f} pages   (limit 7.2-8.8, excl. references and appendix)")
if body > 8.8:
    over = body - 8.8
    print(f"  OVER by {over:.2f}pp  (~{over * 950:.0f} words to cut)")
elif body < 7.2:
    print(f"  UNDER by {7.2 - body:.2f}pp")
else:
    print("  within limit")
print(f"total document: {len(reader.pages)} pages")
PYMEASURE

grep -c "Overfull" "$BUILD/probe.log" | sed 's/^/overfull boxes: /'
