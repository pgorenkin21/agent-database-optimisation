# §5 Experimental method — 0.5pp

**Status:** not started
**Source to adapt:** `draft_paper_ieee_v7.tex` lines 313–379

---

## Setup

BIRD mini-dev SQLite; **50-task subset (primary)** and 500-task split over 11 databases; gold evidence
included in prompts, per BIRD convention; `best_of_n` coordination; temperature 0; N ∈ {3, 10, 25};
GPT-4o mini, Gemini 2.5 Flash, DeepSeek v4-flash.

Prices, from `configs/models.yaml`:

| Model | input $/1M | output $/1M | cached input $/1M | discount |
|---|---:|---:|---:|---|
| gpt-4o-mini | 0.15 | 0.60 | 0.075 | 50% |
| gemini-2.5-flash | 0.30 | 2.50 | **null** | assumed 50% — see §7 |
| deepseek-v3.2 | 0.14 | 0.28 | 0.0028 | **50×** |

## Lead with two disciplines — both are genuine contributions

Do not bury these in a methods list. They are the reason the results are attributable, and the second
one is what makes §6.2's correction possible.

**Isolation.** No early-stop, no shared SQL cache, no explore suppression in any arm, so the composed
arm is exactly the three methods of §4. Contrast explicitly with the stacked measurements this
project ran previously — that contrast sets up §6.2.

**Single-era, clean-id re-running.** Every cell is re-run under a clean `v8_*` batch id rather than
reusing older batches. The reason, from `scripts/run_v8_prune_fill.sh`: the legacy 50-task batches
"do not form one consistent task set. There are five competing GPT N=25 baselines alone, one of which
carries only 36 usable rows out of 50", and DeepSeek's earlier runs predate the 2026-07-24
`deepseek-chat` → v4-flash swap, "worth ~6 EX points on its own." Quoting the concrete numbers is
more persuasive than asserting rigour.

## Metrics

EX; raw prompt + completion tokens; cached-token share; billed tokens (uncached at input rate +
cached at cached rate + completion at output rate); USD at list price; fact-store injections per task.

## Statistics

Paired bootstrap 95% confidence intervals over matched `question_id`s. **† marks an interval
containing zero**; no effect is claimed on a † cell. A ≥90% batch-completion gate
(`MIN_COMPLETION = 0.90`) causes the analyser to refuse degraded batches outright rather than report
them with a caveat.

## Declare the scope limits HERE, not only in §7

Two sentences, stated plainly, so no reader can mistake the coverage:

1. **50 tasks is the primary scale.** All four arms are complete at 50 tasks across N ∈ {3, 10, 25} —
   36 cells. At 500 tasks all four arms have an N=3 column (complete 2026-08-16). The offline pruning
   recall analysis *is* full-scale and is reported as such in §6.1.
2. **Every cell is a single run.** No configuration is replicated on a second seed.

Also declare the **deviation from the registered Project Definition**: this paper narrows the
research question to the prompt layer and evaluates three of the five originally named policies. The
honest reason is the one in §6.2 — isolation showed the stacked measurements could not attribute
credit, so scope was cut to what could be measured cleanly. Frame it as a methodological decision,
which it was, not as an apology.

## Constraints

- **Make no latency or wall-clock claim.** The batch JSONs carry no timing field.
- Do not describe database round-trips as a measured outcome.
- Name the served model versions; note that providers revise them, so absolute EX may not reproduce.

---

## DRAFT

**Status: drafted 2026-08-16. Not compiled. No floats — §5 deliberately carries none, because §3 ran
0.2pp over budget and the plan now has only ~0.1pp of slack.**

**One dependency.** This draft describes the 500-task column as covering all four arms at N=3. That
is true once `run_v8_500t_r3.sh` finishes — as of writing, P0 has passed its gate (498/500 on all
three models) and pruning is mid-wave, with prompt cache and composed to follow. **If any wave fails
the ≥90% gate, cut it from the coverage sentence in §5.2 and from §6.** The fallback wording, if only
the fact store has a full-scale column, is in the brief above.

**CI half-widths are measured, not asserted:** median ±7.0pp across the 36 fifty-task cells against
±2.4pp across the full-scale cells. Regenerate with the snippet at the foot of this file.

---

```latex
\section{How the experiments were run}\label{sec:setup}

\textbf{Data, models and configuration.} All experiments run on BIRD mini-dev
over its eleven SQLite databases, with the gold evidence annotations included in
the prompt as the benchmark intends. Three API models are used, GPT-4o mini,
Gemini 2.5 Flash and DeepSeek v4-flash, at temperature 0 with
\texttt{best\_of\_n} coordination and a 15-turn cap. Each method of
§\ref{sec:methods} is evaluated alone, and all three together, against a matched
uncoordinated baseline.

\textbf{How the coverage is split.} Coverage is split deliberately, not uniformly. On a
50-task subset the full grid runs at $N \in \{3, 10, 25\}$, giving four arms by
three models by three replica counts for thirty-six cells, while on the full
500-task split the same four arms run at $N \in \{3, 10\}$ and add twenty-four
more. Sixty cells in all. Spending the larger budget on tasks instead of a third replica count
follows from the accuracy constraint. At fifty tasks the paired interval on an
execution-accuracy difference has a median half-width of $\pm$7.0 percentage
points, so ``no accuracy cost'' can only mean ``a seven-point loss cannot be
ruled out''. That is too weak to carry a paper whose central claim is that cost
falls while accuracy does not. At roughly 500 matched tasks the same interval
tightens to $\pm$2.4 points. Only $N = 25$ is therefore subset-only, and
§\ref{sec:results-p3} shows what the choice bought: one 50-task result reverses
outright at full scale.

\textbf{Isolation.} No policy outside the three under study is enabled in any
arm. There is no early stopping, no shared execution cache, and no suppression of
repeated probes, so the composed arm is exactly these three methods and each
isolated arm differs from its baseline in exactly one respect. This is
stricter than such layers are usually reported, and §\ref{sec:results-compose}
shows why it matters: a component that looks worthless measured alone turns out
to earn its place in the stack.

\textbf{Metrics and statistics.} Five quantities are reported per cell:
execution accuracy, raw prompt and completion tokens, the share of input served
from the provider cache, billed tokens with cached input priced at each
provider's published cached rate, and digest injections per task for arms that
include the fact store. All comparisons are paired. The intersection of completed
\texttt{question\_id}s is taken, a per-question difference vector formed, and
that vector resampled with replacement 10{,}000 times under a fixed seed to give
a percentile 95\% interval. Token ratios are bootstrapped as a ratio of
resampled sums, not as a mean of per-task ratios, so that a few cheap tasks
cannot dominate. Throughout, $\dag$ marks an interval containing zero, and no
effect is claimed for such a cell. Batches completing under 90\% of their tasks
are refused outright.

\textbf{Scope.} Two limits belong here rather than in the discussion. The design
is complete at both scales for all four arms, but $N = 25$ was measured only on
the subset, so every claim about behaviour at twenty-five replicas rests on
fifty tasks. And no cell is replicated on a second seed, which means run-to-run
variation is bounded by the reported intervals and not by repetition. This paper also narrows the scope registered in its project definition, which
named five policies across the execution and prompt layers. The two
execution-layer policies are omitted because their contribution could not be
attributed cleanly when measured inside a stack.
```

---

## Regenerating the confidence-interval widths

```bash
python3 - <<'PY'
import re, statistics as st
pat = re.compile(r'n=(\d+)\s+EX\s+[\d.]+v\s*[\d.]+\s+[-+][\d.]+pp\s+\[\s*([-+][\d.]+),\s*([-+][\d.]+)\]')
half = {'50-task': [], '500-task': []}
for ln in open('runs/reports/v8_numbers.txt'):
    m = pat.search(ln)
    if m:
        n, lo, hi = int(m.group(1)), float(m.group(2)), float(m.group(3))
        half['50-task' if n < 200 else '500-task'].append((hi - lo) / 2)
for k, v in half.items():
    if v:
        print(f'{k}: {len(v)} cells, median EX CI half-width ±{st.median(v):.2f} pp')
PY
```

As of 2026-08-16: 36 fifty-task cells at median ±7.0pp; full-scale cells at ±2.4pp. **Re-run this
once the 500-task waves land** — the full-scale figure is currently computed from three cells and
will firm up to twelve.
