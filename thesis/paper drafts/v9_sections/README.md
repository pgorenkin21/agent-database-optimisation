# v8 section scaffold

One markdown file per section of `draft_paper_ieee_v8.tex`. Each file is **self-sufficient**: it
carries its own brief, its own verified numbers, and its own constraints, so it can be drafted
without reading the others.

Full background — mechanism detail, the complete numbers matrix, project orientation — is in
[`../v8_handoff.md`](../v8_handoff.md). Read that once before starting; after that, work from the
section files.

## Assembly order and budget

| File | § | Target pp | Status |
|---|---|---:|---|
| `00_title_abstract.md` | — | 0.3 | **drafted** — 244-word abstract, new title; measured 0.40pp |
| `01_introduction.md` | 1 | 0.7 | **drafted** — 0.64pp, no floats |
| `02_background.md` | 2 | 0.9 | **drafted** — 882 words ≈ 0.93pp, 30 citations all verified against the bib |
| `03_system_cost_model.md` | 3 | 1.0 | **drafted** — 0.78pp incl. Fig. 1 (TikZ, labels re-laid-out 17 Aug) |
| `04_methods.md` | 4 | **2.3** | **drafted** — 2.34pp; worked-example floats moved to the appendix |
| `05_experimental_method.md` | 5 | 0.5 | **drafted** — 0.56pp, no floats |
| `06_results.md` | 6 | **2.0** | **§6.1 + §6.3 drafted** (1.97pp, 4 floats); §6.2/§6.4/§6.5 **now unblocked** — all 60 cells in, briefs rewritten 17 Aug |
| `07_discussion.md` | 7 | 0.6 | not started |
| `08_conclusion.md` | 8 | 0.4 | not started |
| | | **9.43 projected — over by 0.6** | see below |
| `09_references.md` | — | *not counted* | **drafted** — 31 entries, list now lives here not in v7; 10 missing works added |
| `10_appendix.md` | — | *not counted* | **drafted** — GenAI statement, reproducibility map, generated tables |

Update the Status column as you go: `not started` → `drafted` → `checked`.

### The appendix is the release valve

It does not count against the limit and now carries the complete 36-cell matrix and the
per-database pruning breakdown, both generated from the analysis outputs. **§6 should print summary
rows and point at `tab:appendix-matrix-50` for the rest** — that is where its 0.3–0.4pp comes from.

### ⚠ Budget position — still over, and this is the paper's biggest structural risk

**Measure, do not estimate.** `uv run python scripts/v8_budget.py` reads the assembled `.tex`,
stops at `\section*{References}` (the limit excludes references and appendix), and projects the
unwritten sections at their planned cost rather than at zero. Re-run it after every drafting
session.

As of 2026-08-17, after the cuts below:

| § | ≈pp | Target | |
|---|---:|---:|---|
| front matter (title + 244-word abstract) | 0.40 | 0.3 | over — abstract drafted, measured not assumed |
| 1 Introduction | 0.64 | 0.7 | ok |
| 2 Background | 0.87 | 0.9 | ok |
| 3 System / cost model | 0.78 | 1.0 | under |
| 4 Methods | 2.34 | 2.3 | ok — *was 2.79* |
| 5 Experimental method | 0.56 | 0.5 | slightly over |
| 6 Results (§6.1 + §6.3 only) | 1.97 | 2.0 | **three subsections still to come** |
| **drafted body + front matter** | **7.59** | | |
| **projected with §6.2/6.4/6.5, §7, §8** | **9.43** | **8.8** | **over by ~0.6** |

**Already done (recovered 0.65pp):**

1. §4's two worked examples moved to the appendix (`tab:appendix-prune-example`,
   `fig:appendix-digest`). The prose stayed, including every number the exhibits carried; only the
   floats moved. §4 went 2.79 → 2.34.
2. `fig:twoledger` cut from §6.3 — `tab:pcache-500` carries the claim numerically. LaTeX preserved
   in `06_results.md` if it needs to come back.

**Still needed, ~0.6pp, in priority order:**

3. **§6.2/§6.4 print summary rows only**, pointing at `tab:appendix-matrix-50/500` for the full
   grids. They are budgeted at 0.35 and 0.40 above — hold that line; the appendix is free.
4. **§2 Background 0.87 → 0.70** (−0.17). It is the most adaptable prose in the paper and the
   least load-bearing per page — it is v7 material, not a v8 contribution.
5. **Abstract 244 → ~200 words** (−0.05). Already trimmed once from 316.
6. **§5 0.56 → 0.50** (−0.06) and **§6.1 trim** (−0.15). §6.1 is the longest results subsection and
   `tab:recall-split` now carries both replica counts, so the prose can lean on it harder.

**Do not recover the space from §4's prose.** It is the section the restructure was for.

**The estimate has real error bars** — ~950 words/page and a flat 0.24pp per float are steering
figures, not measurements. Compile the Overleaf bundle to get the true count before making any
further cut beyond item 3; if the real number comes in under 8.8, items 4–6 are unnecessary.

**§4 and §6 are the paper.** They are 4.3 of the ~8.8 body pages and where the achievement marks sit.
Budget your effort accordingly — the other seven sections are largely adaptation of v7 prose.

## The one-paragraph thesis

Billed input per task is approximately **N × T × price(P + H̄)** — replicas × turns × (static prefix
+ mean accumulated history). The static prefix is re-billed on every turn of every replica. Three
methods each attack a different term: **schema pruning shrinks P**, the **semantic fact store
reshapes H against T**, and **cache-stable prompt structure reprices both without changing a byte**.
The findings: repricing is unconditional, shrinking is conditional on recall, reshaping has no
reliable sign at 50 tasks and saves modestly at 500 — yet the composed stack beats the product of
its parts on 11 of 15 configurations. Accuracy moves in 2 of 60 cells, fewer than chance predicts,
but both are DeepSeek at full scale N=10 in the two arms containing the fact store.

## Non-negotiable conventions

- **Harvard author–year citations only.** No numeric citations.
- **Body length 7.2–8.8 pages**, excluding references and appendix. See the budget note below —
the draft is currently projected at the ceiling.
- **† marks a confidence interval containing zero. Never claim an effect on a † cell.**
- **Label every 50-task claim as 50-task.** The design is complete: 60 cells, all four arms at
  N ∈ {3,10,25} on 50 tasks and N ∈ {3,10} on all 500. **N=25 is 50-task only.** The two scales
  disagree twice — pruning's aggregate, and the fact store's *sign* on DeepSeek — and in both cases
  the 50-task number is the unreliable one.
- **Make no wall-clock or latency claim.** No timing data exists.
- Avoid the bare labels "P1" and "P4" except in related work — those policies are cut.
- Every number must trace to a line in `runs/reports/v8_numbers.txt`.

## Decisions already taken — do not re-litigate

| Decision | Choice |
|---|---|
| Structure | Split methods (§4) and results (§6); **not** v7's per-policy interleaving |
| Scope | Three prompt-layer methods; P1, P4, early-stop cut entirely |
| Fact store | Full method, honest negative in isolation, reversed by §6.4 |
| Further experiments | Full-scale N=3 and N=10 waves were run after the freeze (16–17 Aug). `p3_500t_r10` is the last one; nothing further is planned |
| Cross-model ensemble | **Excluded**, including from future work |
| Companion deliverables | Out of scope (`reflective_essay.md`, `video_plan.md` need a later pass) |

## Preamble additions

§4 needs these two; v7's preamble has neither, and both are standard and present on Overleaf:

```latex
\usepackage{algorithm}
\usepackage{algpseudocode}
```

Fig. 1 (§3) needs **nothing further** — v7 already loads `tikz` with `positioning`,
`shapes.geometric` and `arrows.meta`. The diagram deliberately avoids `calc` and
`decorations.pathreplacing`.

**Table 1 was cut.** The original plan had a taxonomy table in §3; Fig. 1 already carries the
method→factor mapping, and its other two columns duplicated §3.4 and §4. Do not re-add it — §3 is
already 0.2pp over its original budget because it holds Fig. 1.

## Evidence base: complete as of 2026-08-17 13:47 UTC

All waves have finished; `v8_p3_500t_r10` was the last. **60 cells, no gaps, nothing further
planned.** After any change to the analysis, re-run:

```bash
uv run python scripts/analyze_v8_results.py    # strict — no --allow-legacy
uv run python scripts/make_v8_appendix_tables.py
uv run python scripts/v8_additivity.py         # cell count, EX audit, missing-cell list
uv run python scripts/assemble_v8.py --zip
```

**Three claims changed when that last wave landed — check you are not working from the old ones:**

1. **Composition is 11 of 15, not 10 of 12.** Both new full-scale N=10 cells miss, by +2.1 and +0.3
   against the null. Super-additivity is strongest at 50 tasks and near-absent at full scale N=10.
2. **The fact store's sign reverses with scale on DeepSeek** — +16 to +21% on 50 tasks, −7% on 500.
   The "DeepSeek pays the injection tax" story is a subset artefact.
3. **Two EX intervals now exclude zero**, both DeepSeek 500t N=10, both in arms containing the fact
   store. That is the study's only accuracy violation and it belongs in §6.2, §6.5 and §7.

## Figures

| ID | Content | File | Status |
|---|---|---|---|
| Fig. 1 | Prompt anatomy + where each method acts | TikZ, inline in `03_system_cost_model.md` | **drafted** — needs a visual check on first compile |
| Fig. 2 | Cached share of input by turn, three models | `thesis/figures/fig2_cached_by_turn.png` | built from v8 batches |
| Fig. 3 | Per-DB pruning reduction vs gold recall | `thesis/figures/schema_prune_offline_by_db.png` | exists (offline analysis) |
| Fig. 4 | Two-ledger scatter: raw vs billed change | `thesis/figures/fig4_two_ledger.png` | built |
| Fig. 5 | Composed vs predicted-from-parts | `thesis/figures/fig5_additivity.png` | built |

Figs. 2, 4, 5 regenerate with `uv run python scripts/make_v8_figures.py`, which **parses
`runs/reports/v8_numbers.txt`** rather than hardcoding, so they track the analyser. Re-run it after
any change to that file. Fig. 3 comes from `scripts/make_paper_figures.py`.

**Era warning.** The older `prompt_cache_hit_rate_by_turn.png` and `prompt_cache_tokens_by_turn.png`
in `thesis/figures/` are built from **legacy `pc50_*` batches that strict mode declines**. Using them
would mix model eras in a paper whose §5 claims single-era discipline. Fig. 2 replaces them.
`schema_prune_offline_by_db.png` is safe — it comes from the offline analysis, not a batch.

All figures share one palette: **colour is the model** (fixed hue, same as `make_paper_figures.py`),
**shape is the method**, so identity never rests on colour alone. Validated CVD-safe across all pairs
(worst OKLab ΔE 8.4 protan/deutan, 19.8 unsimulated). The amber slot sits at 2.99:1 against the light
surface, which is why every figure carries a legend and the paper's tables serve as the table view.

All captions must be self-contained — the rubric names figure quality explicitly.

## Assembling the .tex

**Do not hand-edit `draft_paper_ieee_v8.tex`.** It is generated. Edit the section files here, then:

```bash
uv run python scripts/assemble_v8.py          # writes draft_paper_ieee_v8.tex
uv run python scripts/assemble_v8.py --check  # report only, writes nothing
```

The assembler pulls the `” ```latex ” ` block out of each section file, splices them into a skeleton
built from v7's preamble, title block and Harvard reference list, adds the two `algorithm` packages,
and stubs any section not yet drafted with a visible TODO so the document always compiles and the
gaps show up in the PDF. It also checks environment balance, duplicate labels and dangling `\ref`s
before writing.

Current state: §1–§5 and the appendix spliced, §6–§8 stubbed. Two pieces of front/back matter are still v7's and are
flagged on every run:

- **Title and abstract** still describe five policies and database round-trips. Draft
  `00_title_abstract.md` and add it to `ORDER` in the assembler.
- **References** are v7's Harvard list, valid LaTeX but not yet through the pass in
  `09_references.md`.
- **The appendix is drafted** and deliberately does not reuse v7's, which cited tables and scripts
  belonging to the cut policies. It `\\input`s `generated/appendix_tables.tex` — regenerate with
  `uv run python scripts/make_v8_appendix_tables.py` and **ship that file in the Overleaf bundle**.

Check body length on the built PDF by finding the page where `\section*{References}` begins and
counting up to there, not the PDF total.
