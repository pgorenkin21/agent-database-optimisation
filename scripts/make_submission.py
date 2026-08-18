#!/usr/bin/env python3
"""Build the supporting-material zip for submission (MSc Project Guide §4.4).

The guide asks for source code, a README guiding the examiner through the files,
and an executable or the steps to run the code. This assembles exactly that and
nothing else, refusing to include anything that is secret, licensed to somebody
else, enormous, or regenerable.

Selection is explicit rather than "everything not ignored", because the two have
drifted before and a submission is a bad place to discover it.

    uv run python scripts/make_submission.py
    uv run python scripts/make_submission.py --list    # show contents, write nothing

Writes submission_pavelgorenkin.zip in the repo root.
"""

from __future__ import annotations

import argparse
import re
import sys
import zipfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(REPO / "scripts"))

OUT = REPO / "submission_pavelgorenkin.zip"

# Whole directories, with the patterns inside them that are excluded.
TREES: list[tuple[str, tuple[str, ...]]] = [
    ("src", ("__pycache__",)),
    ("scripts", ("__pycache__",)),
    ("tests", ("__pycache__",)),
    ("configs", ("__pycache__",)),
    ("runs/reports", ()),
    # The paper source, so the examiner can rebuild the PDF from the sections.
    ("thesis/paper drafts/v9_sections", ()),
    ("thesis/paper drafts/generated", ()),
    ("thesis/figures", ("baseline_explore_redundancy.png",)),
]

FILES = [
    "README.md",
    "pyproject.toml",
    "requirements.txt",
    "uv.lock",
    ".python-version",
    ".env.example",
    "thesis/paper drafts/draft_paper_ieee_v9.pdf",
    "thesis/paper drafts/draft_paper_ieee_v9.tex",
    "thesis/paper drafts/reflective_essay_v9.pdf",
    "thesis/paper drafts/reflective_essay_v9.md",
    "thesis/paper drafts/slides_v9.html",
    "thesis/paper drafts/video_script_v9.md",
    "thesis/paper drafts/IEEEtran.cls",
    "thesis/paper drafts/references.bib",
]

# Nothing matching these may enter the zip, whatever else selects it. Checked
# against every candidate path as a last line of defence.
FORBIDDEN = re.compile(
    r"(^|/)\.env$"           # API keys
    r"|(^|/)\.git/"
    r"|(^|/)\.venv/"
    r"|(^|/)data/bird/"      # 5 GB, licensed to BIRD
    r"|(^|/)pdf_documents/"  # the QMUL handbook and someone else's dissertation
    r"|(^|/)latex template/"
    r"|__pycache__"
    r"|\.pyc$"
)


def batch_files() -> list[Path]:
    """The batch summaries the strict analysis actually reads.

    runs/batches holds 794 files and 126 MB, most of it superseded runs from
    earlier versions of the project. Resolving the set through the analyser's
    own lookup means the zip contains every cell the paper reports and its
    matched baseline, and nothing else, and that it stays correct if the cell
    map changes.
    """
    import analyze_v8_results as A  # noqa: PLC0415

    need: set[Path] = set()
    for scale, ns in (("50", (3, 10, 25)), ("500", (3, 10))):
        for method, _ in A.METHODS:
            for n in ns:
                for model, _short in A.MODELS:
                    for p in (A.find(f"v8_{method}_{scale}t_r{n}", model),
                              A.baseline_for(scale, n, model)):
                        if p is not None:
                            need.add(p)
    return sorted(need)


def demo_traces() -> list[Path]:
    """One worked example of the JSONL trace format, from the demo run.

    The paper describes the trace schema and the reproducibility section points
    at it, so shipping one complete task's worth lets an examiner see the format
    without the historical traces being present.
    """
    from src.logging.trace import read_trace_events  # noqa: PLC0415

    batch = REPO / ("runs/batches/parallel_demo_gpt-4o-mini_r5_best_of_n"
                    "_p3_semantic_promptcache_schema_prune.json")
    if not batch.exists():
        return []
    import json
    out = [batch, batch.with_suffix(".csv")]
    for row in json.loads(batch.read_text()).get("rows", []):
        coord = Path(str(row.get("coord_trace_path", "")))
        if not coord.exists():
            continue
        out.append(coord)
        out += [Path(str(e["trace_path"])) for e in read_trace_events(coord)
                if e.get("event") == "replica_end" and Path(str(e["trace_path"])).exists()]
    return [p for p in out if p.exists()]


def collect() -> list[tuple[Path, str]]:
    members: list[tuple[Path, str]] = []

    def add(src: Path, arc: str) -> None:
        if FORBIDDEN.search(arc) or FORBIDDEN.search(str(src)):
            raise SystemExit(f"refusing to package excluded path: {arc}")
        members.append((src, arc))

    for tree, skip in TREES:
        root = REPO / tree
        if not root.exists():
            print(f"  [warn] missing tree: {tree}")
            continue
        for p in sorted(root.rglob("*")):
            if not p.is_file():
                continue
            rel = p.relative_to(REPO).as_posix()
            if any(s in rel for s in skip):
                continue
            add(p, rel)

    for f in FILES:
        p = REPO / f
        if p.exists():
            add(p, p.relative_to(REPO).as_posix())
        else:
            print(f"  [warn] missing file: {f}")

    for p in batch_files():
        add(p, f"runs/batches/{p.name}")
    for p in demo_traces():
        add(p, f"runs/traces_demo/{p.name}")
    return members


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--list", action="store_true", help="print contents, write nothing")
    args = ap.parse_args()

    members = collect()
    raw = sum(s.stat().st_size for s, _ in members)

    def area_of(arc: str) -> str:
        parts = arc.split("/")
        if len(parts) == 1:
            return "(root)"
        # runs/ and thesis/ hold several distinct things; everything else reads
        # better rolled up to its top-level directory.
        return "/".join(parts[:2]) if parts[0] in ("runs", "thesis") else parts[0]

    by_area: dict[str, tuple[int, int]] = {}
    for src, arc in members:
        area = area_of(arc)
        n, b = by_area.get(area, (0, 0))
        by_area[area] = (n + 1, b + src.stat().st_size)
    print(f"{'area':34}{'files':>7}{'MB':>9}")
    for area, (n, b) in sorted(by_area.items(), key=lambda kv: -kv[1][1]):
        print(f"{area:34}{n:>7}{b / 1e6:>9.1f}")
    print(f"{'TOTAL':34}{len(members):>7}{raw / 1e6:>9.1f}")

    if args.list:
        return 0

    # Duplicate archive names would silently drop a file.
    seen: set[str] = set()
    for _, arc in members:
        if arc in seen:
            raise SystemExit(f"duplicate archive path: {arc}")
        seen.add(arc)

    with zipfile.ZipFile(OUT, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as z:
        for src, arc in members:
            z.write(src, arc)

    print(f"\nwrote {OUT.name}  {OUT.stat().st_size / 1e6:.1f} MB "
          f"({len(members)} files, {raw / 1e6:.1f} MB uncompressed)")

    with zipfile.ZipFile(OUT) as z:
        bad = z.testzip()
        if bad:
            raise SystemExit(f"archive is corrupt at {bad}")
        names = z.namelist()
    assert "README.md" in names, "README.md is required by §4.4 and is missing"
    leaks = [n for n in names if FORBIDDEN.search(n)]
    if leaks:
        raise SystemExit(f"excluded paths leaked into the archive: {leaks[:5]}")
    print("verified: archive intact, README present, no excluded paths")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
