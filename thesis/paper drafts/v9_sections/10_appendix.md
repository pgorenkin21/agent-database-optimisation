# Appendix — not counted against the page limit

**Status:** not started
**Source:** v7's appendix is at lines 1078+ (`\section*{Appendix --- GenAI usage and supporting
material}`).

---

## The appendix is free space — use it

It does not count against the 8 ± 10% limit. **Anything that will not fit the body goes here rather
than being cut.** This is the release valve referenced by the trim-order list in the scaffold README:
before removing content, move it here.

## Required

**GenAI usage statement.** Mandatory per the MSc Project Guide; the QM+ template governs the wording.
v7 has one — carry it over and update it for the v8 workflow if the tooling used has changed.

**Supporting material / reproducibility map.** The guide requires supporting material, and this is
currently unplanned — worth building because it is cheap and directly evidences rigour. A table
mapping claim → script → batch id → result file:

| Paper claim | Script | Batch id | Result |
|---|---|---|---|
| §6.1 pruning, 50-task | `run_v8_matrix.sh`, `run_v8_prune_fill.sh` | `v8_prune_50t_r{3,10,25}` | `runs/reports/v8_numbers.txt` |
| §6.1 offline recall | `scripts/analyze_schema_pruning.py` | — | `runs/reports/schema_pruning{,_full500}.md` |
| §6.2 fact store | `run_v8_matrix.sh` | `v8_p3_{50t,500t}_r*` | `runs/reports/v8_numbers.txt` |
| §6.3 prompt cache | `run_v8_matrix.sh`, `run_v8_cleanup.sh` | `v8_pc_50t_r{3,10,25}` | `runs/reports/v8_numbers.txt` |
| §6.4 composition | `run_v8_matrix.sh` | `v8_comp_50t_r{3,10,25}` | `runs/reports/v8_numbers.txt` |
| baselines | `run_v8_cleanup.sh` | `v8_p0_50t_r{3,10,25}` | — |
| all CIs | `scripts/analyze_v8_results.py` | — | `runs/reports/v8_numbers.txt` |

Note the analyser must be run **strict** (no `--allow-legacy`) to reproduce the published numbers.

## Strong candidates to move here if the body runs long

In the order they should be displaced from the body:

1. **The full per-database pruning table** — reduction and gold recall for all 11 databases. The body
   keeps only the 62.5% / 15.8% extremes and the aggregate recall figures.
2. **The complete 36-cell matrix** — if §6 can only fit summary rows, the full tables belong here.
   This is the single most useful appendix item for a marker checking rigour.
3. **Extended threats to validity** — the body keeps the eleven items compressed; the appendix can
   expand the ones that need argument, particularly the Gemini cached-price discrepancy and the
   single-seed consequence for §6.4.
4. **Algorithm 1 in full**, if the body version has to be abridged to fit §4.1.
5. **The additivity regeneration snippet**, so the derived table is reproducible.

## Constraints

- Appendix material must be *referenced from the body*. An unreferenced appendix reads as padding.
- Do not put anything load-bearing here. If a claim depends on it, it belongs in the body.
- Check separately whether the GenAI statement is expected as an appendix section or a separate
  submitted document — the guide should say.

---

## DRAFT

**Status: drafted 2026-08-16. Not compiled.**

**Does not count against the page limit**, so it carries the full 36-cell matrix and the
per-database pruning breakdown that §6 only summarises. That is what buys §6 the 0.3–0.4pp it needs
(see the README budget note).

**The two big tables are generated, not pasted:**

```bash
uv run python scripts/make_v8_appendix_tables.py   # -> generated/appendix_tables.tex
```

The appendix `\input`s that file, so the tables cannot drift when a wave lands and
`analyze_v8_results.py` is re-run. **Ship `generated/appendix_tables.tex` in the Overleaf bundle.**

**Two definitions the generator had to get right, both of which silently produced wrong numbers on
the first pass — do not "simplify" them back:**

- **Gold recall** has two readings. *Complete* recall — the share of tasks retaining **every** gold
  table — is 89.6%, and is the figure §6.1 quotes. *Mean* per-task fractional recall is 95.8%. The
  table shows both because the gap is informative (most misses drop one table of two, not all), but
  the body must use the complete figure: a query needs all of its tables.
- **Full-schema count** is `pruning_applied == False` (116). The `fallback_reason` field is never
  populated by the offline analyser, so counting it gives zero.

Every script named in the reproducibility map was checked to exist before being cited.

---

```latex
\section*{Appendix}

\subsection*{Generative AI usage}

\scriptsize
Generative AI tools (Claude Code and Cursor agents) were used, under the
author's direction and review, for implementation assistance on the agent
harness and the three prompt-layer methods; for generation of intermediate
chapter drafts from experiment reports; and for editorial drafting of this paper
from those drafts. All quantitative content is computed by deterministic scripts
from JSONL execution traces. No figure or table value is model-generated, and
the tables in this appendix are emitted directly from the analysis outputs by
\texttt{make\_v8\_appendix\_tables.py}. All design decisions, result
interpretation and final text were reviewed and approved by the author;
AI-suggested references were verified against source records before inclusion.
\normalsize

\subsection*{Reproducibility}

\scriptsize
Source code, batch summaries, analysis reports and figure-generation scripts are
submitted with the paper, together with the complete JSONL traces of one
demonstration run so that the trace format can be inspected. Every quantitative
claim traces to a batch identifier
and a generating script, listed in Table~\ref{tab:appendix-repro}. Identifiers
follow the pattern \texttt{v8\_[arm]\_[scale]\_r[N]}, where scale is
\texttt{50t} or \texttt{500t} and $N \in \{3,10,25\}$ at 50 tasks and
$\{3,10\}$ at 500; the table lists the arm only. The analysis
is run in strict mode, meaning \texttt{analyze\_v8\_results.py} without
\texttt{-{}-allow-legacy}, so only batches carrying a clean \texttt{v8\_}
identifier are admitted and pre-v8 batches are refused rather than silently
reused (§\ref{sec:setup}). Batches completing under 90\% of their tasks are
likewise refused. Regenerating every number, figure and appendix table from the
submitted batch summaries is four commands, and needs neither the benchmark
databases nor any model call.
\normalsize

\begin{table}[t]
\caption{Claim to batch to script. All analysis is offline: no result in this
paper requires re-running the agents.}
\label{tab:appendix-repro}
\centering
\scriptsize
\begin{tabular}{@{}>{\raggedright\arraybackslash}p{1.75cm}>{\raggedright\arraybackslash}p{1.0cm}>{\raggedright\arraybackslash}p{4.3cm}@{}}
\toprule
Claim & Arm & Generating script \\
\midrule
Baselines (§\ref{sec:waste}) & \texttt{p0} &
\texttt{run\_v8\_cleanup.sh}, \texttt{run\_v8\_500t\_r3.sh},
\texttt{run\_v8\_500t\_r10.sh} \\
Pruning (§\ref{sec:results-prune}) & \texttt{prune} &
\texttt{run\_v8\_matrix.sh}, \texttt{run\_v8\_prune\_fill.sh} \\
Offline recall (§\ref{sec:results-prune}) & n/a &
\texttt{analyze\_schema\_pruning.py} \\
Fact store (§\ref{sec:results-p3}) & \texttt{p3} &
\texttt{run\_v8\_matrix.sh} \\
Prompt cache (§\ref{sec:results-pcache}) & \texttt{pc} &
\texttt{run\_v8\_matrix.sh}, \texttt{run\_v8\_cleanup.sh} \\
Composition (§\ref{sec:results-compose}) & \texttt{comp} &
\texttt{run\_v8\_matrix.sh}, \texttt{run\_v8\_500t\_r3.sh} \\
\midrule
All intervals & n/a & \texttt{analyze\_v8\_results.py} \\
Additivity, cell counts & n/a & \texttt{v8\_additivity.py} \\
Fig.~\ref{fig:twoledger} & n/a & \texttt{make\_v8\_figures.py} \\
Tables \ref{tab:appendix-matrix-50}--\ref{tab:appendix-perdb} & n/a &
\texttt{make\_v8\_appendix\_tables.py} \\
\bottomrule
\end{tabular}
\end{table}

\subsection*{Worked examples}

The two examples of §\ref{sec:methods} in full. Both are reproduced from live
runs rather than reconstructed.

\begin{table}[h]
\caption{Hybrid pruning on question 1317 (§\ref{sec:prune}). Gold tables in
bold. Seeds are drawn from non-zero keyword scores, so the third gold table,
which the question never names, is admitted only by the recall rule.}
\label{tab:appendix-prune-example}
\centering
\footnotesize
\begin{tabular}{@{}lrrl@{}}
\toprule
Table & Keyword & Hybrid & Admitted by \\
\midrule
\textbf{event}      & 8 & 0.780 & seed \\
\textbf{member}     & 3 & 0.688 & seed \\
\textbf{attendance} & 0 & 0.329 & recall rule \\
budget              & 0 & 0.216 & \\
major               & 0 & 0.164 & \\
expense             & 0 & 0.153 & \\
income              & 0 & 0.123 & \\
zip\_code           & 0 & 0.089 & \\
\bottomrule
\end{tabular}
\end{table}

\begin{figure}[h]
\centering
\fbox{\begin{minipage}{0.93\columnwidth}
\footnotesize\ttfamily\raggedright
Shared semantic facts from parallel replicas on this task (reuse these instead
of re-probing):\\[2pt]
- budget/event/expense returned 0 row(s)\\
- explored: select e.status from expense as ex join budget as b on
  ex.link\_to\_budget = b.budget\_id join event as e on b.link\_to\_even\ldots\\
- join works: b.link\_to\_event = e.event\_id\\
- join works: ex.link\_to\_budget = b.budget\_id\\
- budget/expense returned 0 row(s)\\
- explored: select ex.expense\_id, ex.expense\_description, ex.expense\_date,
  b.link\_to\_event from expense as ex join budget as b on ex\ldots\\
- expense returned 0 row(s)
\end{minipage}}
\caption{The peer digest served to one replica on question 1350 of
\texttt{student\_club} (§\ref{sec:p3}), reproduced verbatim. Seven bullets and
500 characters of fact text: both caps bind. Five of the seven report a negative
result.}
\label{fig:appendix-digest}
\end{figure}

\subsection*{Complete results}

\scriptsize
Section~\ref{sec:results} reports summary rows. The full matrix follows: every
measured cell, all three ledgers, with paired bootstrap intervals.
Table~\ref{tab:appendix-perdb} breaks the offline pruning analysis down by
database, which is where the shortfall between smoke-subset and full-scale
recall becomes legible. The databases carrying hand-written recall rules retain
every gold table, and those without account for almost all of the misses.
\normalsize

\input{generated/appendix_tables}
```

---

## Figure labels this appendix depends on

The reproducibility table cites figures by label. **Never write a figure number in prose** — LaTeX
numbers floats by source order, so any hardcoded "Fig. 2" silently rots the moment a figure is
added, moved or cut. Always `\ref{}`.

| Label | Defined in | Content | Image |
|---|---|---|---|
| `fig:anatomy` | §3.2 ✅ | prompt anatomy + cost identity | TikZ, inline |
| `fig:zones` | §4.3 ✅ | three-zone prompt structure | TikZ, inline |
| `fig:twoledger` | §6.3 ✅ | raw vs billed, all 60 cells | `fig4_two_ledger.png` |
| `fig:appendix-digest` | appendix ✅ | fact-store digest example | inline listing |
| `tab:appendix-prune-example` | appendix ✅ | pruning score table, q1317 | — |

✅ = float written. ⬜ = still referenced but undefined; §6.4 must define it.

**Three floats moved out of the body on 2026-08-17** to recover ~0.65pp against the 8.8-page
ceiling (README budget note):

- `tab:prune-example` and `fig:digest` → the appendix, as `tab:appendix-prune-example` and
  `fig:appendix-digest`. §4 keeps both worked examples in prose, including every number they
  quoted; only the exhibits moved. This was chosen over cutting §4's mechanism prose, which is what
  the whole v8 restructure was for.
- `fig:twoledger` was cut, then **restored 2026-08-17** and extended to all 60 cells. Reviewing
  figures against contributions showed C4 (two ledgers) was the best-evidenced result in the paper
  with no picture, while C5's additivity figure had weakened to 11 of 15 with the full-scale cells
  sitting on the null. The scatter shows something no table does: two populations, content-changing
  methods on the diagonal and repricing far below it.
- `fig:additivity` (composed vs predicted) → **cut in the same swap**, one-for-one, so the exchange
  cost nothing against the page budget. §6.4 states the count and the DeepSeek case in prose.
  Its LaTeX and PNG are both preserved if it needs to come back.
- `fig:perdb` (per-database reduction vs recall) → **cut 2026-08-17** after the first real compile.
  §6.1's prose already gives the two databases that supply most of the shortfall and the
  `student_club` extreme, and `tab:appendix-perdb` carries the full breakdown. Cutting it did double
  duty: it recovered ~0.24pp *and* relieved the float congestion in §6 that was deferring
  `fig:cachedturn` and `fig:additivity` a page and a half past the subsections discussing them.
  The PNG is still generated and still bundled.
- `fig:cachedturn` (cached share by turn) → **cut 2026-08-17**, same pass. Its two quantitative
  claims — DeepSeek at 94--97% from turn one, GPT climbing 53%→80% — are kept verbatim in §6.3's
  prose, so only the picture was lost. `tab:pcache-500` was the alternative candidate and was
  deliberately kept instead: it is §6.3's headline evidence, and sending a reader to the appendix
  for the best-evidenced result in the paper is worse than losing an explanatory figure.
