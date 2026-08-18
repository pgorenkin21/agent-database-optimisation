# §1 Introduction — 0.7pp

**Status:** not started
**Source to adapt:** `draft_paper_ieee_v7.tex` lines 77–151 (paragraphs 1–2 reusable nearly verbatim;
the research question and contributions must be rewritten)

---

## What to write

**Para 1 — context (reuse v7).** LLMs increasingly act as agents interleaving reasoning with tool
calls against live systems rather than producing a single completion (Yao et al. 2023). In the
database setting a schema is explored through SQL probes before a final query is submitted. Because
any single trajectory is unreliable, the standard remedy is **speculative parallelism**: N replicas
on one task, an answer chosen by self-consistency or best-of-N (Wang et al. 2023; Brown et al. 2024;
Snell et al. 2024).

**Para 2 — the problem (reuse v7, then pivot).** Replicas share a data backend but no state. Costs
scale with N; accuracy does not. v7 then went on to redundant *probes*; **v8 pivots to the prompt**:
the same static context is re-sent every turn by every replica, so the schema and instructions are
re-billed on the order of 60× for a 6-turn, 10-replica task. That term is untouched by anything that
deduplicates queries.

**Para 3 — the research question.** Narrowed from v7's "most effective architecture for coordinating
speculative agent workloads over data backends":

> Given that the prompt is re-billed N×T times, which of its attack surfaces actually pay, and do
> they compose?

State the cost identity here in one line — **N × T × price(P + H̄)** — and name the three surfaces it
exposes: shrink **P**, reshape **H** against **T**, reprice both.

**Para 4 — contributions.** Numbered:

- **C1** — a cost identity for speculative agent prompts and a three-surface taxonomy derived from
  it, under which the three methods are exhaustive rather than a list.
- **C2** — recall as the binding precondition on schema pruning: reliable −14.7% to −28.7% raw
  tokens, EX-flat, but full-scale gold-table recall of 89.6% makes correctness of table selection,
  not aggressiveness of pruning, the thing that determines whether it is safe.
- **C3** — shared knowledge, measured in isolation at two scales: the token effect has no consistent
  sign at 50 tasks, and the model that appeared to pay most there (DeepSeek, +16 to +21%) **saves**
  at full scale. Accuracy never improves anywhere, and on DeepSeek at full scale N=10 it
  significantly *degrades*. Plus the methodological correction: the previously reported win for one
  model was an artefact of measuring it inside a stack.
- **C4** — the two-ledger result: raw and billed tokens move independently, and can move in opposite
  directions in the same run with both intervals excluding zero.
- **C5** — composition beats the product of its parts on 11 of 15 configurations, reversing what
  isolated ablation would recommend. The margin is largest at 50 tasks and shrinks at full scale,
  where two of three N=10 cells sit within ~2pp of the multiplicative null.

**Para 5 — roadmap sentence.**

## Constraints

- The RQ narrowing is a **declared deviation** from the registered Project Definition, which named
  five policies. Do not hide it. One clause here, fuller treatment in §7 — framed as isolation
  discipline forcing a scope cut to what could be measured cleanly, which is what it was.
- Do not promise accuracy gains anywhere in the framing. The paper's accuracy result is flatness.
- C5's phrasing matters: "beats the product of its parts", not "is super-additive".

## Numbers cited here (all verified)

| Claim | Value |
|---|---|
| Pruning raw-token range (50-task, 9 cells) | −14.7% to −28.7%, 8 of 9 significant |
| Pruning, recall-complete tasks (500t, N=3 and N=10) | −9.9% to −19.7%, **6 of 6 significant** |
| Pruning, recall-incomplete tasks | +32.1% to +155.8%, 4 of 6 significant (GPT † at both N) |
| Pruning aggregate at full scale | N=3: 0 of 3 significant · N=10: 2 of 3 (−10.9%, −9.1%; Gemini −8.3% [−15.8, **+0.1**]) |
| Full-scale gold-table recall | 89.6% (448/500), 116 full-schema fallbacks |
| Fact store at full scale | GPT −8.9%/−8.8% (both significant), DeepSeek −5.8%†/−7.0%, Gemini null — the 50-task "DeepSeek pays" result does **not** replicate |
| Composition | 11 of 15 configurations beat the product of their parts; 4 of 6 at full scale, and the two full-scale N=10 misses are within 2.1pp of the null |
| EX | **58 of 60** intervals include zero. Both exceptions are DeepSeek at 500t N=10: fact store −3.5pp [−5.7, −1.4] and composed −2.4pp [−4.8, −0.2] |
| Prefix re-billing | ~60× for a 6-turn, 10-replica task |

**On the two EX exceptions — do not wave these away.** At 95% confidence, 60 comparisons would be
expected to throw ~3.0 false positives, so two is fewer than chance predicts. But they are **not
independent draws**: both are DeepSeek, both at 500 tasks and N=10, and the common factor is the
fact store (it appears alone, and inside the composed stack). The two arms *without* the fact store
at that cell are † (pruning −1.6, prompt cache −1.2). A clustered pair with a shared mechanism is
weaker evidence of chance than two scattered ones. State it as "58 of 60", name the cluster, and let
§6.2 own the interpretation. See §6.5.

---

## DRAFT

**Status: drafted 2026-08-16. Not compiled.**

**Budget:** 640 words ≈ 0.67pp, no floats. Deliberately just under its 0.7 allocation — the drafted
sections are ~7% over plan and the body projects to the 8.8 ceiling. See the README budget note.

**Two things deliberately kept count-free.** The accuracy claim says "everywhere it is measured"
rather than naming a cell count, and the full-scale claim says "at N=3" rather than listing arms.
Both change when `run_v8_500t_r3.sh` lands, and §6.5 is the one place the count should live. Do not
add a number here that will need chasing in two sections.

**Do not reinstate** v7's "database load, wall-clock" phrasing in paragraph 2. There is no timing
data in this project, and the database ledger belongs to the two cut policies.

---

```latex
\section{Introduction}\label{sec:intro}

Large language models increasingly act as \emph{agents}, interleaving reasoning
with tool calls instead of producing a single completion (Yao et al.~2023). In
the database setting a schema is explored through SQL probes before a final
query is submitted. No individual trajectory is reliable, so the standard remedy
is \textbf{speculative parallelism}: $N$ replicas are launched on one task and
an answer chosen by self-consistency or best-of-$N$ selection (Wang et al.~2023;
Brown et al.~2024; Snell et al.~2024).

What this costs is poorly characterised. Replicas share a database but no state,
so attention naturally falls on the duplicated queries they issue. The larger
and simpler waste sits in the prompt. Chat APIs are stateless, so every turn
re-sends the whole conversation, and each replica pays again for the same
instructions, schema and question on each turn it takes. None of that amortises.
Per-replica prompt consumption changes by at most 4\% between three replicas and
twenty-five, so cost grows almost linearly in $N$ while accuracy stays inside
the noise of the subset it is measured on, as §\ref{sec:waste} sets out.

This paper therefore asks a narrower question than the one usually posed about
agent coordination. \textbf{Given that a speculative workload re-sends its
prompt on every turn of every replica, which parts of that prompt can be made
cheaper, and do those savings compose?} Section~\ref{sec:costmodel} makes the
target precise. Billed input for one task is approximately $N \times T \times
\mathrm{price}(P + \bar{H})$, or replicas times turns times the price of a
static prefix plus an accumulated history, and that identity offers exactly
three factors to attack. One method is evaluated against each. \textbf{Recall-aware schema pruning}
shrinks the prefix, a \textbf{semantic fact store} trades history for turns, and
\textbf{cache-stable prompt structure} changes what the same bytes cost without
changing any of them. Each is measured alone and all three together, on BIRD
(Li et al.~2023) across three API models, with execution accuracy (Zhong, Yu and
Klein 2020) as a constraint no method may violate.

\textbf{Contributions.}

\begin{enumerate}
\item A cost identity for speculative agent prompts, and the taxonomy that
follows from it. The identity has three independent factors, so the three
methods evaluated here are exhaustive over it and not a selection from a longer
list, as §\ref{sec:costmodel} derives.
\item \emph{Recall is the binding precondition on prefix reduction, and it can
be measured in advance.} Pruning's saving is real but conditional. Across the
full split it removes 10--20\% of raw tokens wherever every gold table survives,
on every model and at both replica counts, with all six intervals excluding
zero. Where one table is missing it \emph{raises} consumption by 32--156\%. The
two regimes very nearly cancel, which makes the aggregate the least stable
quantity in the experiment: indistinguishable from zero on all three models at
three replicas, and 8--11\% at ten. An offline check that calls no model decides
which regime a task falls into, and §\ref{sec:results-prune} measures both.
\item \emph{Shared knowledge has no reliable sign, and the sign is not even
stable across scales.} On the 50-task subset the fact store saves 17\% of tokens
on one model and costs 20\% on another. Across all 500 tasks, the model that
appeared to pay most instead saves 7\%. Accuracy improves nowhere, and on one
model at full scale it significantly degrades, the only accuracy cost measured
anywhere in this study. Section~\ref{sec:results-p3} reports it.
\item \emph{Raw and billed tokens are separate ledgers.} Cache-stable structure
changes no content. It leaves raw consumption unmoved in fourteen of fifteen
configurations and still removes 18.8--86.0\% of billed input in all fifteen. In
one configuration the two ledgers move in opposite directions, both
significantly, as §\ref{sec:results-pcache} shows.
\item \emph{Composition exceeds the sum of its parts.} On eleven of fifteen
configurations the combined stack saves more than its components predict, and on
one model the parts predict a net increase where the stack delivers a 24\%
saving. That reverses what isolated ablation alone would recommend. The margin
is widest on the 50-task subset and narrows at full scale, where two of three
ten-replica cells fall within two points of the multiplicative null. Across all
60 measured cells, 58 accuracy
intervals contain zero, and the two that do not are the same model and cell, in
the two arms containing the fact store.
\end{enumerate}

Section~\ref{sec:system} derives the cost model, §\ref{sec:methods} specifies
the three methods, and §\ref{sec:setup}--\ref{sec:discussion} report and
interpret the results.
```
