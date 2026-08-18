#!/usr/bin/env python3
"""Count the stylistic tics of machine-drafted academic prose, per section.

This exists to make a prose pass measurable instead of impressionistic. None of
these constructions is wrong in itself -- the problem is density and uniformity.
Good writing uses "not X but Y" occasionally; a draft that reaches for it twelve
times has a tic. Judge the numbers as rates, not as errors to drive to zero.

Compares two assembled papers so a rewrite can be checked against its source:

  uv run python scripts/v9_style_audit.py                    # v8 vs v9
  uv run python scripts/v9_style_audit.py --single v8        # one paper
"""
from __future__ import annotations

import argparse
import re
import statistics as st
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
DRAFTS = REPO / "thesis" / "paper drafts"

ENV = re.compile(r"\\begin\{(figure\*?|table\*?|algorithm|tabular|algorithmic)\}"
                 r".*?\\end\{\1\}", re.S)
COMMENT = re.compile(r"(?<!\\)%.*?$", re.M)
MACRO = re.compile(r"\\[a-zA-Z@]+\*?(\[[^]]*\])?(\{[^{}]*\})?")

# Each pattern is (label, regex). Counted over prose only.
PATTERNS: list[tuple[str, re.Pattern]] = [
    ("not X but Y", re.compile(
        r"\bnot\b[^.;]{3,60}?\bbut\b|\bis not\b[^.;]{3,60}?[;:]\s*it is\b", re.I)),
    ("rather than", re.compile(r"\brather than\b", re.I)),
    ("signposted opener", re.compile(
        r"(?m)^(?:The (?:prediction|question|reason|result|point|consequence|"
        r"claim|finding|distinction|argument)\b|Two (?:things|cautions|"
        r"qualifications|limitations)\b|Three\b|What follows\b)")),
    ("verdict phrasing", re.compile(
        r"\bthe (?:defensible|honest|correct|right) (?:claim|reading|"
        r"treatment|answer|version)\b", re.I)),
    ("em-dash aside", re.compile(r"---")),
    ("colon-then-elaboration", re.compile(r"[a-z]:\s+[a-z]")),
    ("worth Xing", re.compile(r"\bworth (?:reporting|noting|stating|drawing|"
                              r"knowing|making|doing)\b", re.I)),
    ("it is/this is X that", re.compile(r"\b(?:it|this) is\b[^.;]{3,40}?\bthat\b", re.I)),
]


def prose_of(tex: str) -> str:
    body = tex[tex.index(r"\section{Introduction}"):tex.index(r"\section*{References}")]
    body = ENV.sub(" ", COMMENT.sub("", body))
    return MACRO.sub(" ", body)


def sections_of(tex: str) -> dict[str, str]:
    body = tex[tex.index(r"\section{Introduction}"):tex.index(r"\section*{References}")]
    out = {}
    for chunk in re.split(r"\\section\{", body)[1:]:
        name = chunk.split("}")[0]
        out[name] = MACRO.sub(" ", ENV.sub(" ", COMMENT.sub("", chunk)))
    return out


def measure(prose: str) -> dict:
    words = re.findall(r"[A-Za-z][A-Za-z'-]+", prose)
    n = max(len(words), 1)
    counts = {label: len(rx.findall(prose)) for label, rx in PATTERNS}
    sents = [s for s in re.split(r"(?<=[.!?])\s+", prose) if len(s.split()) > 2]
    lens = [len(s.split()) for s in sents] or [0]
    return {
        "words": len(words),
        "per1k": {k: 1000 * v / n for k, v in counts.items()},
        "raw": counts,
        "sent_mean": st.mean(lens),
        # Uniform sentence length is the strongest single tell: human academic
        # prose mixes 6-word sentences with 40-word ones.
        "sent_sd": st.pstdev(lens) if len(lens) > 1 else 0.0,
    }


def show(label: str, tex: str) -> dict:
    m = measure(prose_of(tex))
    print(f"\n=== {label} ===  {m['words']} prose words")
    print(f"{'construction':26s} {'count':>6} {'per 1k words':>13}")
    for k in m["per1k"]:
        print(f"  {k:24s} {m['raw'][k]:6d} {m['per1k'][k]:13.1f}")
    print(f"  {'sentence length mean':24s} {m['sent_mean']:6.1f}")
    print(f"  {'sentence length sd':24s} {m['sent_sd']:6.1f}   (higher = more varied)")
    return m


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--single", help="audit one version only, e.g. v8")
    ap.add_argument("--per-section", action="store_true")
    args = ap.parse_args()

    def load(v: str) -> str:
        p = DRAFTS / f"draft_paper_ieee_{v}.tex"
        if not p.exists():
            raise SystemExit(f"missing {p}")
        return p.read_text(encoding="utf-8")

    if args.single:
        m = show(args.single, load(args.single))
        if args.per_section:
            print("\nper section (per 1k words):")
            for name, chunk in sections_of(load(args.single)).items():
                s = measure(chunk)
                worst = sorted(s["per1k"].items(), key=lambda kv: -kv[1])[:3]
                print(f"  {name[:32]:34s} {s['words']:5d}w  sd {s['sent_sd']:4.1f}  "
                      + ", ".join(f"{k} {v:.1f}" for k, v in worst))
        return 0

    a, b = show("v8", load("v8")), show("v9", load("v9"))
    print("\n=== change, v8 -> v9 (per 1k words; negative = less formulaic) ===")
    for k in a["per1k"]:
        d = b["per1k"][k] - a["per1k"][k]
        print(f"  {k:24s} {a['per1k'][k]:6.1f} -> {b['per1k'][k]:5.1f}   {d:+6.1f}")
    print(f"  {'sentence length sd':24s} {a['sent_sd']:6.1f} -> {b['sent_sd']:5.1f}   "
          f"{b['sent_sd'] - a['sent_sd']:+6.1f}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
