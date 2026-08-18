# §3 System and the prompt cost model — 0.8pp

**Status:** not started
**Source to adapt:** `draft_paper_ieee_v7.tex` lines 205–276 (harness) and 380–404 (waste baseline).
§3.2 and §3.4 are **new** — v7 has no cost identity and no two-ledger definition.

---

## 3.1 Agent harness (~0.2pp)

Reuse v7's `sec:harness` prose, compressed. ReAct loop; two tools, `execute_sql` (explore) and
`submit_sql` (final answer); ≤15 turns; N replicas per task; `best_of_n` coordinator; JSONL trace per
replica. Keep only what §4 and §6 depend on — the trace-event vocabulary can go, since the redundancy
analysis that used it is being cut to a paragraph.

## 3.2 Prompt anatomy and the cost identity (~0.3pp) — NEW, and the spine of the paper

Derive:

> **cost ≈ N × T × price(P + H̄)**
> replicas × turns × (static prefix + mean accumulated history)

Then the observation that motivates everything: the static prefix is re-billed on **every turn of
every replica** — on the order of **60×** for a 6-turn, 10-replica task. No policy that deduplicates
*queries* touches this term.

Name the three attack surfaces the identity exposes, and note that they are exhaustive over the
identity rather than a chosen list — that is what makes this a taxonomy and not an enumeration:

| Surface | Method | Ledger |
|---|---|---|
| Shrink **P** | recall-aware schema pruning | raw tokens |
| Reshape **H** against **T** | semantic fact store | raw tokens |
| Reprice **P + H** | cache-stable prompt structure | billed tokens |

**Fig. 1 goes here** — the only new figure, and the one that carries the paper. It should show the
frozen prefix (system | schema | question + evidence), the append-only history, and an arrow from
each method to the term it attacks. Get this right; a reader who understands Fig. 1 understands §4
and §6 without effort.

**Table 1 goes here too** — method × cost term × ledger × safety class. Four rows including a header.
Cheap, and it front-loads the whole argument.

## 3.3 The waste it exposes (~0.15pp)

**Compress v7's entire `sec:waste` section to one paragraph.** It motivates the paper; it is no
longer a contribution, and the redundancy figure it supported belongs to the cut policies.

Numbers to keep:

| Quantity | Value |
|---|---|
| Explore redundancy at N=25 | 80–88% on all three models |
| Token overhead vs cheapest correct replica | 26–33× |
| EX across N ∈ {3, 10, 25} | ~58–74%, approximately flat in N |
| Unique-exploration saturation (Gemini, N=3→25) | unique explores 96 → 111 while total explores 196 → 1,548 |

The saturation number is the best one — it shows added replicas almost entirely repeat existing work.
If you keep only one statistic, keep that one.

**Do not** reproduce v7's `fig:redundancy`. Figure budget is spent on Figs. 1–3.

## 3.4 Two ledgers, one constraint (~0.15pp) — NEW

Define precisely, because §6 depends on the distinction:

- **Raw tokens** — what the model consumed. What a content-level policy changes.
- **Billed tokens** — raw tokens priced with cached prefix tokens at the provider's discounted rate.
  What the user pays.
- **EX** — not a ledger. A **constraint** no policy may violate.

State the claim §6.3 will demonstrate: these two ledgers can move in opposite directions in the same
run. This replaces v7's "four ledgers" framing — the database-load ledger left with the cut policies,
so do not carry the four-way version over.

## Constraints

- Nothing in this section should mention database round-trips as a *result*. The harness executes
  SQL, that is all.
- The cost identity is an approximation — say so. It ignores completion tokens and treats turns as
  homogeneous. One clause is enough; do not over-qualify.

---

## DRAFT

**Status: drafted 2026-08-16. Not compiled — no LaTeX toolchain on this machine.**

**Preamble addition** (on top of `algorithm`/`algpseudocode` for §4). v7 already loads `tikz` with
`positioning`, `shapes.geometric` and `arrows.meta`; Fig. 1 needs nothing further. It deliberately
avoids `calc` and `decorations.pathreplacing` by using `[xshift=…]anchor` syntax, which is core TikZ.

**Every number here is re-derived from the clean `v8_p0_50t_r*` batches** — the same controls §6
measures against — rather than from the older `baseline_*_full.md` reports. Two reasons: the DeepSeek
baseline report on disk (`baseline_deepseek_baseline_full.md`) has no `_v4f` marker and may predate
the 2026-07-24 model swap, which would contradict §5's single-era claim; and using the same controls
throughout means §3.3's motivation and §6's results cannot drift apart. Regenerate with the snippet
at the foot of this file.

---

```latex
\section{The agent and what its prompt costs}\label{sec:system}

\subsection{How the agent works}\label{sec:harness}

Each replica runs a ReAct-style loop (Yao et al.~2023) with two tools.
\texttt{execute\_sql} runs an exploratory query, and \texttt{submit\_sql} ends
the episode with a final one. A run is capped at 15 turns. For each task, $N$
replicas are launched on identical inputs at temperature 0, differing only in
sampling, and a coordinator selects one answer by \texttt{best\_of\_n}, taking
the replica that reaches an executable submission in fewest turns. Every replica
writes a JSONL trace of its tool calls and per-turn token counts, and all
measurement in this paper is drawn from those traces.

\subsection{What a prompt contains, and what it costs}\label{sec:costmodel}

Because the chat APIs these agents run on are stateless, each turn re-sends the
whole conversation and the whole conversation is billed again, giving the
structure Fig.~\ref{fig:anatomy} shows. A prompt divides into a
\emph{static prefix} $P$, holding the system instructions, the database schema,
the question and its evidence, none of which change during an episode. The
second is an \emph{accumulated history} $H$ of probe results and any peer
context, which grows every turn. Writing $\bar{H}$ for the mean history size over an episode of
$T$ turns, the input billed for one task across $N$ replicas is approximately

\begin{equation}\label{eq:cost}
\mathrm{cost} \;\approx\; N \times T \times \mathrm{price}\!\left(P + \bar{H}\right).
\end{equation}

The approximation ignores completion tokens and treats turns as homogeneous,
neither of which affects the argument that follows.

What makes Eq.~\ref{eq:cost} worth stating is its implication for $P$, a term
sent on each turn of each replica rather than once. At the two-to-four turn
counts measured here, a twenty-five-replica task re-sends its schema fifty to a
hundred times, and that schema averages some 4{,}000 characters on the 50-task
subset. Prompt cost should therefore scale almost linearly in $N$, and it does: across
an eightfold change in replica count, per-replica prompt tokens move by 0.6\% on
Gemini, 1.5\% on DeepSeek and $-$4.4\% on GPT-4o mini. Nothing is shared between
replicas, so nothing amortises.

The identity also partitions the problem, because its three factors can be
attacked independently by shrinking $P$, reshaping $H$ against $T$, or changing
the price of both, and the three methods of §\ref{sec:methods} take one each. The
factors are independent, so the three methods are exhaustive over
Eq.~\ref{eq:cost} and not a selection from a longer list.

% LAYOUT NOTE -- read before editing this figure.
% Each label is anchored to the VERTICAL CENTRE of the element it annotates, so
% every arrow is horizontal and the pairing is unambiguous. That only works
% while the targets are spaced further apart than the labels are tall: the
% gaps are 1.39cm (schema->history) and 1.05cm (history->multiplier) against
% 2-line labels ~0.67cm high, leaving ~0.4cm clear at the tightest point.
% KEEP THE LABELS TO TWO LINES. A third line takes each to ~0.97cm and the
% bottom pair closes to ~0.1cm; a fourth would collide. The label column is
% 2.6cm wide, which fits every string below on two lines -- check any rewording
% against that before committing, and recompile.
% An earlier version chained the labels vertically instead, which guaranteed no
% overlap but produced steep diagonal arrows that read ambiguously.
\begin{figure}[t]
\centering
\begin{tikzpicture}[
  font=\footnotesize,
  bx/.style={draw=black!55, rounded corners=1.5pt, text width=3.3cm,
             align=center, minimum height=0.38cm, inner sep=2pt},
  frozen/.style={bx, fill=black!8},
  hist/.style={bx, fill=black!3, dashed, minimum height=0.72cm},
  note/.style={font=\scriptsize, align=left, text width=2.6cm, inner sep=1pt,
               anchor=west},
  arr/.style={-{Latex[length=1.3mm]}, black!55, thin}
]
\node[frozen]                      (sys)  {system instructions};
\node[frozen, below=1.5pt of sys]  (sch)  {schema: DDL + column descriptions};
\node[frozen, below=1.5pt of sch]  (task) {question + evidence};
\node[hist,   below=7pt   of task] (hst)  {accumulated history:\\probe results, peer facts};
\node[below=7pt of hst, font=\scriptsize, text width=3.3cm, align=center] (mul)
  {re-sent $\times\,T$ turns $\times\,N$ replicas, then priced};

\draw[black!45, line width=0.8pt]
  ([xshift=-3pt]sys.north west) -- ([xshift=-3pt]task.south west);
\draw[black!45, line width=0.8pt]
  ([xshift=-3pt]hst.north west) -- ([xshift=-3pt]hst.south west);
\node[font=\scriptsize] at ([xshift=-11pt]sch.west)  {$P$};
\node[font=\scriptsize] at ([xshift=-11pt]hst.west)  {$\bar{H}$};

% Anchored at each target's own height -> horizontal arrows.
\node[note] (m1) at ([xshift=13pt]sch.east)
  {\textbf{pruning} (§\ref{sec:prune})\\shrinks $P$};
\node[note] (m2) at ([xshift=13pt]hst.east)
  {\textbf{fact store} (§\ref{sec:p3})\\trades $\bar{H}$ for $T$};
\node[note] (m3) at ([xshift=13pt]mul.east)
  {\textbf{cache-stable} (§\ref{sec:pcache})\\reprices $P+\bar{H}$};

\draw[arr] (m1.west) -- (sch.east);
\draw[arr] (m2.west) -- (hst.east);
\draw[arr] (m3.west) -- (mul.east);
\end{tikzpicture}
\caption{Anatomy of one replica's prompt. The static prefix $P$ is re-sent
unchanged on every turn of every replica; the history $\bar{H}$ grows as the
episode proceeds. Each of the three methods attacks a different factor of
Eq.~\ref{eq:cost}.}
\label{fig:anatomy}
\end{figure}


\subsection{How much of that cost is wasted}\label{sec:waste}

Uncoordinated replication is expensive in exactly the way Eq.~\ref{eq:cost}
predicts. On the 50-task subset, moving from three replicas to twenty-five
raises duplicated exploratory SQL from 39--49\% to 76--89\% and total token
consumption from 3.1--3.5$\times$ to 26.6--36.7$\times$ that of the cheapest
correct replica, on all three models. Execution accuracy over the same range moves by at
most eight points, which is within the run-to-run variation of a 50-task subset,
so an eightfold increase in replicas buys an order of magnitude in cost and no
accuracy that can be distinguished from noise.

\subsection{Tokens consumed and tokens billed}\label{sec:ledgers}

Two quantities are reported separately throughout, because the results turn on
their difference. \emph{Raw tokens} are what the model consumed, and they are
what a content-level policy changes. \emph{Billed tokens} price that same
consumption with cached prefix tokens discounted at the provider's rate, and
they are what the user pays. A method that changes no content can move the
second without moving the first. Section~\ref{sec:results-pcache} reports a case
where the two move in opposite directions on one run, both significantly.
Execution accuracy is not a third ledger but a constraint, and nothing below is
reported as a saving unless accuracy survives it intact.
```

---

## Regenerating §3.3's waste numbers and the per-replica figures

```bash
uv run python - <<'PY'
import json, glob, statistics as st
print(f"{'model':18s} {'N':>3} {'EX%':>5} {'redund%':>8} {'overhead':>9} {'tok/replica':>12}")
for key, lab in [('gpt-4o-mini','GPT-4o mini'), ('gemini-2.5-flash','Gemini 2.5 Flash'),
                 ('deepseek-v3.2','DeepSeek v4-flash')]:
    for n in (3, 10, 25):
        f = glob.glob(f'runs/batches/parallel_v8_p0_50t_r{n}_{key}_r{n}_*.json')
        if not f: continue
        d = json.load(open(f[0]))
        ok = [r for r in d['rows'] if not r.get('error')]
        per = st.mean(r['total_prompt_tokens'] for r in ok) / n
        print(f"{lab:18s} {n:>3} {d['ex_accuracy_pct']:5.1f} "
              f"{d['avg_explore_redundancy_pct']:8.1f} {d['avg_token_overhead_ratio']:8.2f}x {per:12,.0f}")
PY
```

Values as of 2026-08-16 — redundancy 39.1→88.7%, overhead 3.13→36.70×, EX 56–76 with no monotone
trend. Mean chosen-replica turn counts are 1.9 (Gemini), 2.8–3.1 (GPT) and 3.2–3.8 (DeepSeek), which
is where "two to four turns" comes from. Mean full schema context over the 50 smoke tasks is 3,956
characters (median 2,252, max 6,513).

---

## Labels this section must define

§4 is drafted and forward-references these. Use exactly these names:

| Label | Where |
|---|---|
| `sec:costmodel` | §3.2, the cost identity — §4's opening sentence points here |
