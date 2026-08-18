#!/usr/bin/env python3
"""Assemble draft_paper_ieee_v9.tex from the per-section markdown drafts.

v9 is a prose-quality pass over v8: same results, same numbers, same structure,
rewritten for varied sentence construction and a less formulaic register. It is
kept alongside v8 rather than replacing it so the two can be compared.

Each file in `thesis/paper drafts/v8_sections/` carries its LaTeX inside a single
```latex fenced block. This script extracts those blocks and splices them into a
skeleton built from v7's preamble, title block, reference list and appendix.

Re-run it whenever a section is redrafted; it overwrites the .tex and never
touches the section files or v7. Sections not yet drafted become a visible
`\\section{...}` stub carrying a TODO, so the document always compiles and the
gaps are obvious in the PDF rather than silent.

    uv run python scripts/assemble_v8.py [--check]

--check reports what would be written without writing it.
"""

from __future__ import annotations

import argparse
import re
import sys
import zipfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
DRAFTS = REPO_ROOT / "thesis" / "paper drafts"
SECTIONS = DRAFTS / "v9_sections"
V7 = DRAFTS / "draft_paper_ieee_v7.tex"
OUT = DRAFTS / "draft_paper_ieee_v9.tex"

# Body order. (file stem, fallback \section title if not yet drafted)
ORDER: list[tuple[str, str]] = [
    ("01_introduction", "Introduction"),
    ("02_background", "Background and related work"),
    ("03_system_cost_model", "System and the prompt cost model"),
    ("04_methods", "Three prompt-layer methods"),
    ("05_experimental_method", "Experimental method"),
    ("06_results", "Results"),
    ("07_discussion", "Discussion"),
    ("08_conclusion", "Conclusion and future work"),
]

# §4 needs these; v7's preamble has neither. Fig. 1 needs nothing beyond v7's tikz.
EXTRA_PACKAGES = "\\usepackage{algorithm}\n\\usepackage{algpseudocode}\n"

FENCE = re.compile(r"```latex\n(.*?)\n```", re.S)


def extract(stem: str) -> str | None:
    """Return the LaTeX block from a section file, or None if not yet drafted."""
    path = SECTIONS / f"{stem}.md"
    if not path.exists():
        return None
    blocks = FENCE.findall(path.read_text(encoding="utf-8"))
    # Section files may carry a short preamble snippet as well as the body; the
    # body is the block that opens a sectioning command.
    bodies = [b for b in blocks if re.search(r"\\section\*?\{", b)]
    if not bodies:
        return None
    if len(bodies) > 1:
        print(f"  [warn] {stem}.md has {len(bodies)} sectioning blocks; using the longest")
        bodies.sort(key=len, reverse=True)
    return bodies[0].strip()


def _balanced(text: str, macro: str) -> str | None:
    """Extract `\\macro{...}` with brace matching, so nested groups survive.

    A non-greedy `\\title\\{(.*?)\\}` truncates at the first inner `}` --- which
    every real title and author block has --- so this walks the braces instead.
    """
    start = text.find("\\" + macro + "{")
    if start < 0:
        return None
    i = text.index("{", start)
    depth = 0
    for j in range(i, len(text)):
        if text[j] == "{" and text[j - 1] != "\\":
            depth += 1
        elif text[j] == "}" and text[j - 1] != "\\":
            depth -= 1
            if depth == 0:
                return text[start : j + 1]
    return None


def front_matter(v7_front: str) -> tuple[str, str]:
    """Build \\begin{document}..keywords, preferring v8's title and abstract.

    v7's front matter names five policies and the database ledger, both of which
    left with the cut arms, so carrying it over silently ships a paper whose
    abstract contradicts its results. Take the title, abstract and keywords from
    00_title_abstract.md when it has been drafted; keep v7's author block either
    way, since that has not changed.
    """
    author = _balanced(v7_front, "author") or ""
    path = SECTIONS / "00_title_abstract.md"
    blocks = FENCE.findall(path.read_text(encoding="utf-8")) if path.exists() else []
    src = next((b for b in blocks if "\\title{" in b and "\\begin{abstract}" in b), None)
    if src is None:
        return v7_front, "carried over from v7 --- still to rewrite"

    title = _balanced(src, "title")
    abstract = re.search(r"\\begin\{abstract\}.*?\\end\{abstract\}", src, re.S)
    keywords = re.search(r"\\begin\{IEEEkeywords\}.*?\\end\{IEEEkeywords\}", src, re.S)
    if not (title and abstract and keywords):
        return v7_front, "00_title_abstract.md incomplete --- fell back to v7"

    words = len(re.findall(r"[A-Za-z][A-Za-z'-]+", abstract.group(0)))
    front = (
        "\\begin{document}\n\n"
        f"{title}\n\n{author}\n\n\\maketitle\n\n"
        f"{abstract.group(0)}\n\n{keywords.group(0)}\n"
    )
    return front, f"v8 --- {words} words"


def stub(title: str, stem: str) -> str:
    label = "sec:" + stem.split("_", 1)[1].replace("_", "-")
    # The stem carries an underscore ("07_discussion") and must be escaped for
    # text mode. Escaping the literal "v8\_sections" but interpolating the stem
    # raw put a bare `_` in \texttt{}, which is a subscript outside maths: every
    # build with an undrafted section failed with an unclosed group.
    safe = stem.replace("_", "\\_")
    return (
        f"\\section{{{title}}}\\label{{{label}}}\n\n"
        f"\\textbf{{[TODO --- not yet drafted. See "
        f"\\texttt{{v9\\_sections/{safe}.md}}.]}}\n"
    )


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true", help="report without writing")
    ap.add_argument("--zip", action="store_true",
                    help="also write draft_paper_ieee_v8_overleaf.zip")
    args = ap.parse_args()

    if not V7.exists():
        print(f"missing {V7}")
        return 1
    v7 = V7.read_text(encoding="utf-8").splitlines(keepends=True)

    # v7 boundaries, located by content rather than hardcoded line numbers so the
    # script survives edits to v7.
    def find(pred) -> int:
        for i, line in enumerate(v7):
            if pred(line):
                return i
        raise SystemExit(f"could not locate a required marker in {V7.name}")

    i_doc = find(lambda l: l.startswith("\\begin{document}"))
    i_kw_end = find(lambda l: l.startswith("\\end{IEEEkeywords}"))
    i_refs = find(lambda l: l.startswith("\\section*{References}"))
    i_appendix = find(lambda l: l.startswith("\\section*{Appendix"))

    preamble = "".join(v7[:i_doc]).rstrip("\n")
    # Insert the two extra packages just before \begin{document}.
    preamble = preamble + "\n" + EXTRA_PACKAGES
    front, front_status = front_matter("".join(v7[i_doc : i_kw_end + 1]))
    # References: prefer v8's own list. v7's was short ten works that §2 and §4
    # cite, so carrying it over shipped a draft with unresolvable citations.
    refs_v8 = next(
        (b for b in FENCE.findall((SECTIONS / "09_references.md").read_text(encoding="utf-8"))
         if "\\section*{References}" in b),
        None,
    ) if (SECTIONS / "09_references.md").exists() else None
    refs = (refs_v8.strip() if refs_v8
            else "".join(v7[i_refs:i_appendix]).rstrip("\n"))
    n_refs = refs.count("\\refentry")
    refs_status = (f"v8 --- {n_refs} entries" if refs_v8
                   else f"v7 carried over --- {n_refs} entries, needs the pass in 09_references.md")
    appendix = extract("10_appendix") or (
        "\\section*{Appendix --- GenAI usage and supporting material}\n\n"
        "\\textbf{[TODO --- not yet drafted. See \\texttt{v9\\_sections/10\\_appendix.md}.\n"
        "v7's appendix is deliberately NOT carried over: it cites tables and analysis\n"
        "scripts that belong to the cut policies.]}\n"
    )
    back = refs + "\n\n" + appendix + "\n\\end{document}\n"

    parts, drafted, missing = [], [], []
    for stem, title in ORDER:
        tex = extract(stem)
        if tex:
            parts.append(tex)
            drafted.append(stem)
        else:
            parts.append(stub(title, stem))
            missing.append(stem)

    body = "\n\n".join(parts)
    doc = (
        preamble
        + "\n"
        + front
        + "\n"
        + "% ==== body assembled by scripts/assemble_v9.py. Edit the section\n"
        + "% ==== files under v8_sections/, not this file, then re-run it.\n\n"
        + body
        + "\n\n"
        + back
    )

    print(f"drafted sections spliced : {', '.join(drafted) or 'none'}")
    print(f"stubbed (still TODO)     : {', '.join(missing) or 'none'}")
    print(f"title/abstract           : {front_status}")
    print(f"references               : {refs_status}")

    # Cheap structural checks before writing.
    for env in ("figure", "table", "table*", "tabular", "algorithm",
                "algorithmic", "enumerate", "equation", "tikzpicture", "abstract"):
        o = len(re.findall(r"\\begin\{" + re.escape(env) + r"\}", doc))
        c = len(re.findall(r"\\end\{" + re.escape(env) + r"\}", doc))
        if o != c:
            print(f"  [ERROR] {env}: {o} begin / {c} end")
    # Follow \input so labels defined in generated fragments are not reported
    # as dangling -- a checker that cries wolf stops being read.
    resolved = doc
    for inc in re.findall(r"\\input\{([^}]+)\}", doc):
        frag = DRAFTS / (inc if inc.endswith(".tex") else inc + ".tex")
        if frag.exists():
            resolved += "\n" + frag.read_text(encoding="utf-8")
        else:
            print(f"  [ERROR] \\input{{{inc}}} -> {frag} does not exist")

    labels = re.findall(r"\\label\{([^}]+)\}", resolved)
    dupes = {l for l in labels if labels.count(l) > 1}
    if dupes:
        print(f"  [ERROR] duplicate labels: {sorted(dupes)}")
    undefined = sorted(set(re.findall(r"\\ref\{([^}]+)\}", resolved)) - set(labels))
    if undefined:
        print(f"  [warn] \\ref to undefined labels: {undefined}")

    if args.check:
        print("\n--check: nothing written")
        return 0

    OUT.write_text(doc, encoding="utf-8")
    print(f"\nwrote {OUT.relative_to(REPO_ROOT)}  ({len(doc.splitlines())} lines)")
    if args.zip:
        make_bundle(doc)
    return 0


# Carried in the bundle without being referenced. Fig. 1 and Fig. 2 are drawn in
# the document and need no file; the body references only fig4. These two were
# cut from §6 for space and are kept so that restoring either in Overleaf is one
# \includegraphics away rather than a re-zip.
#
# schema_prune_offline_by_db.png was dropped on 2026-08-18. It is the old
# two-database, 50-task render, superseded by fig8_recall_split.png, and its
# numbers disagree with the ones the body prints. An unreferenced figure costs
# nothing until someone opens the zip and reads it.
V9_FIGURES = [
    "fig2_cached_by_turn.png",
    "fig5_additivity.png",
]


def make_bundle(doc: str) -> None:
    """Zip the .tex with everything it needs, at the paths it expects."""
    zip_path = DRAFTS / "draft_paper_ieee_v9_overleaf.zip"
    members: list[tuple[Path, str]] = [(OUT, OUT.name), (DRAFTS / "IEEEtran.cls", "IEEEtran.cls")]

    for inc in re.findall(r"\\input\{([^}]+)\}", doc):
        rel = inc if inc.endswith(".tex") else inc + ".tex"
        members.append((DRAFTS / rel, rel))

    # Figures live in two places historically: paper-spec renders in
    # thesis/figures/, older paper-local copies in thesis/paper drafts/figures/.
    # Search both, and complain rather than silently shipping an incomplete zip.
    # This applies to figures the document actually references as well as to the
    # V9_FIGURES carry-list -- resolving only the latter across both directories
    # meant an \includegraphics{figures/x.png} whose file lived in thesis/figures
    # was recorded at the paper-local path, shadowed the carry-list entry, and
    # failed the existence check with a path nothing had ever written to.
    figdirs = [REPO_ROOT / "thesis" / "figures", DRAFTS / "figures"]

    def resolve(rel: str) -> Path:
        """Locate a figure referenced at `rel` (a path relative to the .tex)."""
        direct = DRAFTS / rel
        if direct.exists():
            return direct
        return next((d / Path(rel).name for d in figdirs
                     if (d / Path(rel).name).exists()), direct)

    for g in re.findall(r"\\includegraphics(?:\[[^]]*\])?\{([^}]+)\}", doc):
        members.append((resolve(g), g))

    for name in V9_FIGURES:
        if any(Path(m[1]).name == name for m in members):
            continue
        src = next((d / name for d in figdirs if (d / name).exists()), None)
        if src is None:
            print(f"  [warn] figure not found in {[str(d) for d in figdirs]}: {name}")
            continue
        members.append((src, f"figures/{name}"))

    missing = [str(s) for s, _ in members if not s.exists()]
    if missing:
        print("  [ERROR] cannot bundle, missing:")
        for m in missing:
            print(f"    {m}")
        return

    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as z:
        for src, arc in members:
            z.write(src, arc)
    total = sum(s.stat().st_size for s, _ in members)
    print(f"wrote {zip_path.relative_to(REPO_ROOT)}  "
          f"({len(members)} files, {total/1024:.0f} KB uncompressed)")
    for _, arc in sorted(members, key=lambda m: m[1]):
        print(f"    {arc}")


if __name__ == "__main__":
    sys.exit(main())
