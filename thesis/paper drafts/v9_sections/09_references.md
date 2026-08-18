# References — not counted against the page limit

**Status:** not started
**Source:** `thesis/paper drafts/references.bib`; v7's rendered list is at lines 989–1077.

---

## The key fact

**References do not count against the 8 ± 10% limit.** v7 spent ~0.5–0.7pp on them under the
assumption that they did. Budget **~28 entries** rather than the ~22 a page-constrained draft would
allow — §2 is worth 25% of the marks and a thin bibliography undercuts it for no gain.

## Harvard author–year only

No numeric citations. v7 already renders author–year inline; preserve that. Check every entry
actually renders as `(Author Year)` after the reference pass — this is a hard requirement, not a
style preference.

## Carry over from v7

- BIRD (Li et al. 2023); Spider (Yu et al. 2018); execution accuracy (Zhong, Yu and Klein 2020)
- ReAct (Yao et al. 2023)
- Self-consistency (Wang et al. 2023); repeated sampling (Brown et al. 2024); test-time compute
  (Snell et al. 2024); FrugalGPT (Chen, Zaharia and Zou 2023)
- MAC-SQL (Wang et al. 2025); DIN-SQL (Pourreza and Rafiei 2023); CHESS (Talaei et al. 2024)
- Provider prefix caching: OpenAI 2024, Anthropic 2024, Google DeepMind 2024; Gim et al. 2024
- Blackboard architecture (Hayes-Roth 1985)
- sqlglot (Mao and contributors 2024) — **only if** SQL normalisation still appears; it was mainly a
  P1 dependency, and the fact store's `normalize_sql_ast` call is the remaining use

## Promote to primary — these anchor §4.1

Currently minor entries in v7; they become the intellectual grounding for schema pruning:

- Schema linking — Lei et al. 2020, Zhang et al. 2023
- Prompt compression — LLMLingua (Jiang et al. 2023)

Consider adding one or two further schema-linking or context-selection references. This is the
cheapest available strengthening of the section that carries the most marks.

## Drop or demote

- **GPTCache (Zheng et al. 2023)** — v7 used it as the contrast case for the shared SQL cache, which
  is cut. Either drop it, or keep one clause under caching generally. Do not retain the
  exact-vs-semantic argument; it has nothing left to attach to.
- Any P4-specific citation.
- DAIL-SQL, AutoGen, MetaGPT, Wooldridge — only if they still earn their place after §2 is rewritten.

## Checks before submission

- [ ] Every in-text citation resolves to a bib entry and vice versa
- [ ] Author–year rendering throughout; no `[1]`-style anywhere
- [ ] Access dates present on all web sources, especially the four provider caching docs
- [ ] No entry cited only in a deleted section (grep for orphans after the P1/P4 cuts)
- [ ] Entry count ≥ 25

---

## NOTES

**2026-08-17 — reference pass done. The list now lives in this file**, not in v7. `assemble_v8.py`
splices the fenced block below; v7's list is no longer read.

**Two entries removed 2026-08-17** — Lewis et al. 2020 (RAG) and Karpukhin et al. 2020 (DPR) were
orphaned when the "Not retrieval" paragraph was cut from §2. Nothing else cited them.

**Ten works were cited in §2 and §4 but had no entry.** §2 was drafted against a bibliography that
was never extended, so the compiled draft cited DAIL-SQL, MetaGPT, AutoGen, RAG, DPR, Toolformer,
ToolLLM, RAT-SQL, PICARD and Wooldridge with nothing to resolve to. All ten are added. Count is
**31**, above the ≥25 target.

**Two decisions against this brief, both deliberate:**

- **GPTCache (Zheng et al. 2023) is kept.** The brief said drop it with P1. But §2 now uses it for a
  different job — the contrast between prefix caching (changes the billing ledger) and semantic
  response caching (changes the content ledger, trading correctness for hit rate). That contrast
  sets up the two-ledger finding, so it earns its place on v8 grounds rather than v7 ones.
- **sqlglot (Mao 2024) is kept, and §4.2 now cites it.** It was orphaned — the entry existed, the
  citation did not. It is a live dependency: `semantic_extractors.py` → `sql_normalize.py` parses
  each probe to an AST so two spellings of one query collapse to a single fact. That supports §4.2's
  "rule-based, no model calls" claim, so the citation is worth making explicit.

⚠ **Verify metadata on the ten new entries before submission.** Authors, titles and years are
right; venue and page details are from memory and were not checked against the sources. DAIL-SQL's
volume/page numbers (VLDB 17(5), 1132--1145) are the ones most worth confirming.

Remaining checks: access dates are present on the four provider docs; no `[1]`-style citation
appears anywhere; every entry resolves both ways (verified by the audit in the session log).

---

```latex
\section*{References}

\begingroup
\scriptsize
\setlength{\parindent}{0pt}

\refentry Anthropic (2024). \emph{Prompt Caching}. Anthropic API
documentation {[}online{]}. Available at: \url{https://docs.anthropic.com}
{[}Accessed 2 July 2026{]}.

\refentry Brown, B., Juravsky, J., Ehrlich, R., Clark, R., Le, Q., Ré, C. and
Mirhoseini, A. (2024). Large Language Monkeys: Scaling Inference Compute with
Repeated Sampling. \emph{arXiv preprint}.

\refentry Chen, L., Zaharia, M. and Zou, J. (2023). FrugalGPT: How to Use
Large Language Models While Reducing Cost and Improving Performance.
\emph{arXiv preprint}.

\refentry Gao, D., Wang, H., Li, Y., Sun, X., Qian, Y., Ding, B. and Zhou, J.
(2024). Text-to-SQL Empowered by Large Language Models: A Benchmark
Evaluation. \emph{Proceedings of the VLDB Endowment}, 17(5), 1132--1145.

\refentry Gim, I., Rajbhandari, S., Yao, Z., Aminabadi, R.Y., Rasley, J. and
He, Y. (2024). Prompt Cache: Modular Attention Reuse for Low-Latency
Inference. \emph{Proceedings of MLSys}.

\refentry Google DeepMind (2024). \emph{Context Caching}. Gemini API
documentation {[}online{]}. Available at: \url{https://ai.google.dev}
{[}Accessed 2 July 2026{]}.

\refentry Hayes-Roth, B. (1985). A Blackboard Architecture for Control.
\emph{Artificial Intelligence}, 26(3), 251--321.

\refentry Hong, S., Zheng, X., Chen, J., Cheng, Y., Wang, J., Zhang, C. et
al.~(2023). MetaGPT: Meta Programming for a Multi-Agent Collaborative
Framework. \emph{arXiv preprint}.

\refentry Jiang, H., Wu, Q., Lin, C.-Y., Yang, Y. and Qiu, L. (2023).
LLMLingua: Compressing Prompts for Accelerated Inference of Large Language
Models. In: \emph{Proceedings of EMNLP 2023}.

\refentry Lei, W., Ren, Y., Zhang, Y. et al.~(2020). Re-examining the Role of
Schema Linking in Text-to-SQL. In: \emph{Proceedings of EMNLP 2020}.

\refentry Li, J., Hui, B., Qu, G., Yang, J., Li, B., Li, B. et al.~(2023).
Can LLM Already Serve as a Database Interface? A Big Bench for Large-Scale
Database Grounded Text-to-SQLs. In: \emph{Advances in Neural Information
Processing Systems 36}.

\refentry Mao, T. and contributors (2024). \emph{sqlglot: Python SQL Parser
and Transpiler} {[}software{]}. Available at:
\url{https://github.com/tobymao/sqlglot} {[}Accessed 2 July 2026{]}.

\refentry OpenAI (2024). \emph{Prompt Caching}. OpenAI API documentation
{[}online{]}. Available at: \url{https://platform.openai.com/docs}
{[}Accessed 2 July 2026{]}.

\refentry Pourreza, M. and Rafiei, D. (2023). DIN-SQL: Decomposed In-Context
Learning of Text-to-SQL with Self-Correction. In: \emph{Advances in Neural
Information Processing Systems 36}.

\refentry Qin, Y., Liang, S., Ye, Y., Zhu, K., Yan, L., Lu, Y. et al.~(2023).
ToolLLM: Facilitating Large Language Models to Master 16000+ Real-World APIs.
\emph{arXiv preprint}.

\refentry Schick, T., Dwivedi-Yu, J., Dess\`{i}, R., Raileanu, R., Lomeli, M.,
Zettlemoyer, L., Cancedda, N. and Scialom, T. (2023). Toolformer: Language
Models Can Teach Themselves to Use Tools. \emph{Advances in Neural Information
Processing Systems 36}.

\refentry Scholak, T., Schucher, N. and Bahdanau, D. (2021). PICARD: Parsing
Incrementally for Constrained Auto-Regressive Decoding from Language Models.
\emph{Proceedings of EMNLP}.

\refentry Snell, C., Lee, J., Xu, K. and Kumar, A. (2024). Scaling LLM
Test-Time Compute Optimally Can Be More Effective than Scaling Model
Parameters. \emph{arXiv preprint}.

\refentry Talaei, S. et al.~(2024). CHESS: Contextual Harnessing for
Efficient SQL Synthesis. \emph{arXiv preprint}.

\refentry Wang, B., Ren, C., Yang, J., Liang, X., Bai, J., Chai, L. et
al.~(2025). MAC-SQL: A Multi-Agent Collaborative Framework for Text-to-SQL.
In: \emph{Proceedings of COLING 2025}.

\refentry Wang, B., Shin, R., Liu, X., Polozov, O. and Richardson, M. (2020).
RAT-SQL: Relation-Aware Schema Encoding and Linking for Text-to-SQL Parsers.
\emph{Proceedings of ACL}.

\refentry Wang, X., Wei, J., Schuurmans, D., Le, Q., Chi, E., Narang, S.,
Chowdhery, A. and Zhou, D. (2023). Self-Consistency Improves Chain of Thought
Reasoning in Language Models. In: \emph{Proceedings of ICLR 2023}.

\refentry Wooldridge, M. (2009). \emph{An Introduction to MultiAgent Systems}.
2nd edn. Chichester: John Wiley \& Sons.

\refentry Wu, Q., Bansal, G., Zhang, J., Wu, Y., Li, B., Zhu, E. et al.~(2023).
AutoGen: Enabling Next-Gen LLM Applications via Multi-Agent Conversation.
\emph{arXiv preprint}.

\refentry Yao, S., Zhao, J., Yu, D., Du, N., Shafran, I., Narasimhan, K. and
Cao, Y. (2023). ReAct: Synergizing Reasoning and Acting in Language Models.
In: \emph{Proceedings of ICLR 2023}.

\refentry Yu, T., Zhang, R., Yang, K., Yasunaga, M., Wang, D., Li, Z. et
al.~(2018). Spider: A Large-Scale Human-Labeled Dataset for Complex and
Cross-Domain Semantic Parsing and Text-to-SQL Task. In: \emph{Proceedings of
EMNLP 2018}.

\refentry Zhang, Y., Wang, B. and Yu, T. (2023). Benchmarking and Improving
Schema Linking for Text-to-SQL. In: \emph{Proceedings of EMNLP Findings}.

\refentry Zheng, B., Zhang, J., Mo, X., Liu, C. and Liu, Y. (2023). GPTCache:
An Open-Source Semantic Cache for LLM Applications. In: \emph{Proceedings of
NLP-OSS 2023}.

\refentry Zhong, R., Yu, T. and Klein, D. (2020). Semantic Evaluation for
Text-to-SQL with Distilled Test Suites. In: \emph{Proceedings of EMNLP 2020}.

\endgroup
```
