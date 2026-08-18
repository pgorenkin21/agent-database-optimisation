# Title, abstract, index terms — 0.3pp

**Status:** not started
**Source to adapt:** `draft_paper_ieee_v7.tex` lines 32–75

---

## Title

Title, chosen 2026-08-18:

> **Prompt Cost Optimisation for Speculative Parallelism in Text-to-SQL: Schema Pruning, a
> Semantic Fact Store, and Cache-Stable Structure**

v7's title was *"Coordinating Speculative Agent Workloads Over Data Backends: Caching, Pruning, and
Suppression Policies for Parallel Text-to-SQL Agents"*. It no longer fits — suppression and
result-caching are both gone, and "over data backends" points at the database ledger that left with
them.

v8's was *"One Prompt, Three Levers: Schema Pruning, Fact Distillation, and Cache-Stable Structure
for Parallel Text-to-SQL Agents"*. Three problems, all fixed above. "Levers" was a metaphor;
"fact distillation" was a coinage that appears nowhere in §4, where the component is a **semantic
fact store**; and "prompt optimisation" alone would collide with the prompt-search and prompt-tuning
literature, which optimises for accuracy. This paper optimises **cost** and holds accuracy fixed, so
the word must be in the title.

Whatever you choose must signal: **the prompt is the object**, and there are **three** things done
to it.

## Abstract — target ~180 words

Beats, in order:

1. **Setup.** LLM SQL agents buy reliability with speculative parallelism: N replicas attempt one
   task, a coordinator selects. Replicas share a backend but no state.
2. **The framing.** Billed input is approximately N × T × (static prefix + accumulated history), and
   the prefix is re-billed on every turn of every replica. Three prompt-layer methods each attack a
   different term of that identity — evaluated in isolation and composed, on BIRD, across three API
   models at N ∈ {3, 10, 25}, with paired bootstrap confidence intervals.
3. **Result 1 — repricing is the unconditional win.** Cache-stable prompt structure changes no
   content byte, leaves raw tokens statistically unchanged in 8 of 9 cells, and cuts billed input
   **18.6–82.0%** in all nine.
4. **Result 2 — the two ledgers.** Raw and billed tokens move independently, and in one cell in
   opposite directions with both intervals excluding zero.
5. **Result 3 — pruning works, conditional on recall.** −14.7% to −28.7% raw tokens, 8 of 9
   significant, EX flat — but full-scale gold-table recall falls to **89.6%**, and recall is the
   binding precondition.
6. **Result 4 — composition over-delivers.** The fact store has no reliable sign alone, yet the
   composed stack beats the product of its parts on **11 of 15** configurations; on one model the
   parts predict a token *increase* and the stack delivers a 23.8% *saving*.
7. **The constraint.** Accuracy never moves: every one of 39 EX intervals includes zero.
8. **One-line contribution.** Isolation attributes; composition decides — and a reproducible
   trace-driven harness is released.

## Index terms

`LLM agents, text-to-SQL, speculative parallelism, prompt caching, schema pruning, context
compression, BIRD benchmark`

Drop v7's `middleware, caching` framing — it pointed at the execution-layer policies.

## Constraints

- Do not put a database-round-trip number in the abstract. That result belongs to the cut policies.
- Do not claim any accuracy improvement. The EX result is *flatness*, and that is the point.
- If you quote the composition finding, the honest phrasing is "beats the product of its parts on 7
  of 9 configurations" — not "is super-additive", which overstates a descriptive comparison of
  independent runs.
- Say "50-task" or "500-task" wherever a headline number needs it. The pruning and cache numbers
  above are 50-task.

---

## DRAFT

**Status: drafted 2026-08-17. Not compiled.** 191 words.

**The beats above were written before the full-scale data landed and three of them are now wrong.**
Do not restore them:

- Beat 3 said prompt cache was "8 of 9 cells, 18.6–82.0%". It is now **15 configurations across two
  scales**, raw-neutral in 14, billed down **18.8–86.0%** in all 15.
- Beat 5 said pruning is "−14.7% to −28.7%, 8 of 9 significant". That is the 50-task subset only. At
  full scale the aggregate is null at N=3, so the abstract must lead with the **recall condition**,
  not the headline range.
- Beat 7 said "every one of 39 EX intervals includes zero". It is **58 of 60**, and both exceptions
  are DeepSeek at full scale N=10 in the two arms containing the fact store. The abstract says "two
  of sixty ... though both are the same model at full scale", which is accurate without spending a
  sentence on it — §6.5 and §7 carry the detail.

**Composition is quoted as 11 of 15** (it was 7 of 9, then 10 of 12, as full-scale cells landed),
and the phrasing stays "beats the product of its parts" — never "super-additive", which would
overstate a descriptive comparison of independent runs.

**No database-round-trip number appears**, per the constraint above; that result belongs to the two
cut policies.

---

```latex
\title{Prompt Cost Optimisation for Speculative Parallelism in Text-to-SQL:
Schema Pruning, a Semantic Fact Store, and Cache-Stable Structure}

\begin{abstract}
Large language models deployed as tool-using SQL agents buy reliability with
\emph{speculative parallelism}: $N$ replicas attempt one task and a coordinator
selects an answer. The resulting waste is usually sought in their duplicated
queries. It is larger in the prompt. Because chat APIs are stateless, billed
input per task is approximately $N \times T \times \mathrm{price}(P + \bar{H})$,
or replicas times turns times the price of a static prefix plus an accumulated
history, so a schema is re-billed some sixty times for a six-turn, ten-replica
task. That identity has three factors, and this paper
evaluates one method against each: recall-aware schema pruning, a semantic fact
store, and cache-stable prompt structure, measured in isolation and composed,
on BIRD across three API models, on a 50-task subset and over all 500 tasks.

Repricing is the unconditional win: cache-stable structure changes no content
byte, leaves raw consumption unmoved in fourteen of fifteen configurations, and
removes 18.8--86.0\% of billed input in all fifteen. Raw and billed tokens are
separate ledgers, moving in opposite directions in one configuration with both
intervals excluding zero. Prefix reduction is conditional on recall, and
the condition is measurable offline: pruning removes 9.9--19.7\% of tokens where
every gold table survives and \emph{adds} 32--156\% where one does not, leaving
a near-zero aggregate. Composition over-delivers. The fact store has no
reliable sign at 50 tasks and saves modestly at 500, yet the stack beats the
product of its parts in eleven of fifteen configurations. Accuracy moves in two
of sixty cells, fewer than chance predicts. Isolation attributes credit;
composition decides deployment.
\end{abstract}

\begin{IEEEkeywords}
LLM agents, text-to-SQL, speculative parallelism, prompt caching, schema
pruning, context compression, BIRD benchmark
\end{IEEEkeywords}
```
