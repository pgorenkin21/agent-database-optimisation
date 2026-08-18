# §2 Background and related work — 0.9pp

**Status:** not started
**Source to adapt:** `draft_paper_ieee_v7.tex` lines 153–204
**This section is worth 25% of the marks.** It is the single highest-value page in the paper.

---

## How to organise it

Organise by **claims you position against**, not by listing papers. The distinction-grade exemplar
this project is benchmarked against uses a compact related-work section that *positions* rather than
surveys. Close on the two gaps.

References do **not** count against the page limit, so be generous — budget ~28 entries rather than
the ~22 a page-constrained draft would allow.

## Cut from v7

- The **GPTCache-vs-P1 exactness contrast** — P1 is gone, so the "exact AST-normalised results vs
  semantic response caching" argument has nothing to attach to.
- The **P4 "conservative middle ground"** paragraph.

Both currently sit at v7 lines 178–187. Removing them frees room for the two anchors below.

## Keep and expand

**Benchmark and metric.** BIRD (Li et al. 2023) as a cross-domain text-to-SQL benchmark over
realistic databases with evidence annotations, succeeding Spider (Yu et al. 2018); execution accuracy
as the metric (Zhong, Yu and Klein 2020). The mini-dev SQLite split is used here.

**Parallel inference — Gap 1.** Self-consistency (Wang et al. 2023), repeated sampling (Brown et al.
2024), test-time compute scaling (Snell et al. 2024), FrugalGPT on the cost side (Chen, Zaharia and
Zou 2023). In all of it, replicas are treated as **independent**. None of it examines what the
replicas *re-send*. **This is the first gap.**

**Multi-agent and decomposed text-to-SQL — Gap 2.** MAC-SQL (Wang et al. 2025) coordinates
heterogeneous roles; DIN-SQL (Pourreza and Rafiei 2023) decomposes prompting for a single agent;
CHESS (Talaei et al. 2024) harnesses contextual signals. These improve *what one pipeline does*.
Here, *identical speculative replicas* are coordinated — an orthogonal axis that composes with any of
them. **This is the second gap.**

**Schema linking and prompt compression — now a primary anchor, not a footnote.** Lei et al. 2020 and
Zhang et al. 2023 on schema linking; LLMLingua (Jiang et al. 2023) on prompt compression. These are
the **single-agent ancestors of §4.1**, and the paper's contribution over them is specific: they
reduce context for one agent, whereas here the same reduction is multiplied by N replicas × T turns,
which changes the economics and makes recall failure proportionally more expensive. Give this real
space — it is where §4.1 gets its intellectual grounding.

**Provider prefix caching — the anchor for §4.3.** OpenAI 2024, Anthropic 2024, Google DeepMind 2024;
Gim et al. 2024 on prompt-cache design. Establish the two invariants here (byte-identical prefix,
append-only growth) so §4.3 can use them without re-deriving. Note that this line of work targets
*billing* and is orthogonal to content — which is exactly why it lands on a different ledger.

**Coordination vocabulary.** Blackboard architecture (Hayes-Roth 1985) for §4.2's framing of advisory,
ignorable shared knowledge. One sentence. **First to cut if the section overruns.**

## Close

Two-gap synthesis, one sentence, explicit:

> No prior work measures or removes cross-replica redundancy in the *prompt* — the layer that
> dominates billed cost in speculative agent workloads.

That is the new-insight sentence the higher marking bands ask for. Make it a standalone sentence, not
a subordinate clause.

## Constraints

- Harvard author–year throughout. Check `references.bib` renders author–year, not numeric.
- Do not cite GPTCache as a contrast to a policy this paper no longer contains. If it appears at all,
  it is one clause under caching generally.
- Verify every access date on the provider documentation entries — they are web sources.

---

## DRAFT

**Status: drafted 2026-08-16. Not compiled — no LaTeX toolchain on this machine.**

**Citations.** Every entry below already exists in `references.bib`; nothing new needs adding. Thirty
are cited here, against v7's nineteen — references do not count against the page limit, and this is
the section worth 25% of the marks. Author–year forms are taken from the bib entries, not from
memory. One correction carried over: the bib key is `talaie2024chess` but the author is **Talaei** —
v7 renders it correctly in text; the old outline had it wrong.

**Newly cited in v8** (present in the bib, unused by v7's §2): RAT-SQL, PICARD, DAIL-SQL, Toolformer,
ToolLLM, AutoGen, MetaGPT, Wooldridge, RAG and DPR. **Dropped:** the GPTCache-versus-shared-cache
contrast and the P4 paragraph, both of which described policies v8 no longer contains. `sqlglot2024`
moves to §4.2, where the fact store's query normalisation actually uses it.

---

```latex
\section{Background and related work}\label{sec:related}

\textbf{Text-to-SQL and its evaluation.} Spider (Yu et al.~2018) established
cross-database generalisation as the discipline's test, and BIRD (Li et
al.~2023) succeeded it with larger, dirtier, more realistic databases and
human-written evidence annotations. Both are scored by execution accuracy, meaning
the predicted query's result set must match the gold query's when run against
the live database (Zhong, Yu and Klein 2020). This paper uses BIRD's mini-dev
SQLite split. As the field moved from purpose-built encoders (RAT-SQL, Wang et
al.~2020; PICARD, Scholak et al.~2021) to prompted general-purpose models, the
design problem became what to put in the prompt. DIN-SQL decomposes the task
(Pourreza and Rafiei 2023), DAIL-SQL studies example selection (Gao et
al.~2024), and CHESS retrieves contextual signals (Talaei et al.~2024). All
of them optimise a single trajectory.

\textbf{Tool-using agents and speculative parallelism.} A separate line of work
gives models the ability to act. ReAct interleaves reasoning with tool calls
(Yao et al.~2023), while Toolformer (Schick et al.~2023) and ToolLLM (Qin et
al.~2023) study how models learn to invoke tools at all. An agent in this
setting does not translate a question in one shot but probes a live database,
reads the results and revises, and because no individual trajectory is reliable
the standard remedy is to run several at once. Self-consistency votes over sampled reasoning paths
(Wang et al.~2023), repeated sampling shows coverage growing with attempts
(Brown et al.~2024), and test-time-compute scaling studies the accuracy returned
per unit of inference (Snell et al.~2024). FrugalGPT
approaches the same trade-off from the cost side, cascading cheaper models
before expensive ones (Chen, Zaharia and Zou 2023). Across all of it replicas
are treated as \emph{independent} draws and cost is counted per trajectory.
What is not counted is that every replica re-sends the same schema,
instructions and question on every turn, so the static prefix is billed
proportionally to replicas multiplied by turns. \textbf{That multiplication is
the first gap this paper addresses.}

\textbf{Coordinating several agents.} Where agents are coordinated explicitly,
the coordination is almost always over \emph{roles}. MAC-SQL assigns
decomposition, selection and refinement to distinct text-to-SQL agents (Wang et
al.~2025), while AutoGen (Wu et al.~2023) and MetaGPT (Hong et al.~2023)
provide general frameworks for role-structured collaboration. The underlying
vocabulary is older. Blackboard architectures let independent knowledge sources
post partial results to a shared structure that peers may consult or ignore
(Hayes-Roth 1985; Wooldridge 2009). The setting here is narrower and, in the
speculative regime, more common. Replicas are \emph{identical}, differing only
by sampling, so nothing suggests a division of labour, and yet they duplicate
each other's work wholesale. \textbf{Coordination between identical
speculative replicas is the second gap.} Being orthogonal to role
specialisation, it composes with that line of work, which means the layers
evaluated here would sit beneath a MAC-SQL-style pipeline unchanged.

\textbf{Reducing what is sent.} The prompt-side lineage this paper draws on is
schema linking, which selects the tables and columns a question actually needs
(Lei et al.~2020; Zhang, Wang and Yu 2023), and prompt compression, which
shortens context at some risk to its content (LLMLingua; Jiang et al.~2023).
Both were developed for a single agent making a single pass, and both are
evaluated on whether the answer survives the reduction. Under speculative
parallelism the arithmetic changes twice over. A saving on the static prefix is
multiplied by replicas and turns instead of being taken once, so even a modest
reduction is worth more than it appears. A selection error is multiplied the same way, because every replica inherits
the same missing table and pays to rediscover it, so recall stops being a
quality metric and becomes a precondition, a shift §\ref{sec:prune} builds into
the mechanism and §\ref{sec:results-prune} quantifies.

\textbf{Reducing what it costs.} A third body of work leaves the prompt's
content untouched and attacks its price. Providers now discount input tokens
that repeat a previously seen prefix (OpenAI 2024; Google DeepMind 2024;
Anthropic 2024), and Gim et al.~(2024) set out the attention-state reuse that
makes such caching possible. These schemes are indifferent to what the prompt
says, requiring only that it begin identically and grow by appending. Semantic
response caching sits at the other extreme, reusing whole answers for
similar-looking questions and trading correctness risk for hit rate (GPTCache;
Zheng et al.~2023). The distinction matters for reading the results below.
Prefix caching changes the \emph{billing} ledger while leaving the content
ledger alone, and §\ref{sec:results-pcache} shows the two moving in opposite
directions on the same run.

\textbf{The gap this paper fills.} Prior work scales identical replicas without coordinating
them, coordinates specialised roles without measuring what identical ones waste,
and reduces or reprices the prompt for a single agent. None measures how prompt
cost scales with replica count, or asks which prompt-layer interventions recover
it and whether they compose.
```
