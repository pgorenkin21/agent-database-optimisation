# Thesis references

Bibliography: [`references.bib`](references.bib)

## Chapter → citation map

Use these keys in markdown (`[@bird2023]`) or LaTeX (`\cite{bird2023}`).

### All chapters (benchmark & setup)

| Key | Paper |
|-----|-------|
| `bird2023` | Li et al. — BIRD benchmark (NeurIPS 2023) |
| `spider2018` | Yu et al. — Spider (EMNLP 2018) |
| `zhong2020execution` | Zhong et al. — execution accuracy / test suites |
| `lei2020schemalinking` | Lei et al. — schema linking role |

### Chapter 2 — P0 baseline redundancy

| Key | Paper |
|-----|-------|
| `yao2023react` | ReAct — tool/action agent loop |
| `wang2023selfconsistency` | Self-consistency — multiple trajectories |
| `wang2025macsql` | MAC-SQL — multi-agent text-to-SQL (contrast) |
| `pourreza2023dinsql` | DIN-SQL — decomposed in-context learning |
| `lewis2020rag` | RAG — contrast with execution-based agents (§2.1.1) |

### Chapter 3 — Early stopping

| Key | Paper |
|-----|-------|
| `chen2023frugalgpt` | FrugalGPT — cost-aware inference |
| `snell2024testtime` | Test-time compute scaling |
| `wang2023selfconsistency` | Best-of-N / aggregate answer |

### Chapter 4 — P1 shared SQL cache

| Key | Paper |
|-----|-------|
| `zheng2023gptcache` | GPTCache — semantic LLM cache (contrast) |
| `stonebraker1987postgres` | Classical result caching (optional) |
| `sqlglot2024` | AST normalisation tool |

### Chapter 5 — P2 discovery board

| Key | Paper |
|-----|-------|
| `hayesroth1985blackboard` | Blackboard architecture |
| `wu2023autogen` | AutoGen — agent messaging |
| `hong2023metagpt` | MetaGPT — multi-agent orchestration |
| `sqlglot2024` | Fragment extraction |

### Chapter 6 — Middleware stack

| Key | Paper |
|-----|-------|
| `chen2023frugalgpt` | Cost–accuracy trade-offs |
| `wang2025macsql` | Closest multi-agent prior work |
| `zhang2023schemalinking` | Schema pruning motivation |
| `jiang2023llmlingua` | Prompt compression (alternative) |
| `wang2020ratsql` | Schema encoding baseline |

### Chapter 7 — P3 semantic store

| Key | Paper |
|-----|-------|
| `lewis2020rag` | Retrieval vs outcome sharing |
| `zheng2023gptcache` | Semantic caching landscape |
| `talaie2024chess` | Context harnessing for SQL |
| `karpukhin2020dpr` | Dense retrieval (TF-IDF contrast) |

### Chapter 8 — Temperature & stagger

| Key | Paper |
|-----|-------|
| `wang2023selfconsistency` | Sampling diversity |
| `brown2024largelanguagemonkeys` | Repeated sampling at inference |
| `snell2024testtime` | Inference-time compute |

### Chapter 9 — Synthesis

| Key | Paper |
|-----|-------|
| `bird2023` | Benchmark & EX metric |
| `chen2023frugalgpt` | Deployment cost rules |
| `wang2025macsql` | Model-conditioned stacks (contrast) |
| `wooldridge2009mas` | Coordination vocabulary |

### Chapter 10 — Provider prompt caching

| Key | Paper |
|-----|-------|
| `openai2024promptcache` | OpenAI automatic prefix cache |
| `google2024geminicache` | Gemini implicit/explicit caching |
| `anthropic2024promptcache` | Claude `cache_control` |
| `gim2024promptcache` | Prefix reuse background |
| `jiang2023llmlingua` | Contrast: compression vs caching |
| `chen2023frugalgpt` | Cost-aware inference framing |

Draft: [`chapter10_prompt_caching.md`](chapter10_prompt_caching.md). Design deep-dive: [`other docs/prompt_caching.md`](../other%20docs/prompt_caching.md). Regenerate: `uv run python scripts/generate_chapter10_draft.py`

### Chapter 11 — Schema pruning

| Key | Paper |
|-----|-------|
| `zhang2023schemalinking` | Schema linking / table selection |
| `jiang2023llmlingua` | Prompt compression (contrast) |
| `wang2020ratsql` | Schema encoding baseline |
| `lei2020schemalinking` | Schema linking role |

Draft: [`chapter11_schema_pruning.md`](chapter11_schema_pruning.md). Regenerate: `uv run python scripts/generate_chapter11_draft.py`

### Chapter 12 — Persistent database profiles

| Key | Paper |
|-----|-------|
| `zheng2023gptcache` | Contrast: task-scoped semantic cache |
| `talaie2024chess` | Context harnessing for SQL |
| `lewis2020rag` | Retrieval vs precomputed metadata |
| `chen2023frugalgpt` | Cost-aware inference framing |

Draft (design): [`chapter12_database_profiles.md`](chapter12_database_profiles.md). Design proposal: [`other docs/optimisation_proposal.md`](../other%20docs/optimisation_proposal.md) (Idea 2). Regenerate: `uv run python scripts/generate_chapter12_draft.py`

### Chapter 13 — Structural explore suppression (P4)

| Key | Paper |
|-----|-------|
| `zheng2023gptcache` | Semantic caching (contrast: rows vs advisory facts) |
| `talaie2024chess` | Context harnessing for SQL |
| `sqlglot2024` | AST normalisation / fragment signatures |

Draft (design): [`chapter13_explore_suppression.md`](chapter13_explore_suppression.md). Idea 3 in [`other docs/optimisation_proposal.md`](../other%20docs/optimisation_proposal.md).

### Chapter 14 — Heterogeneous multi-model ensemble

| Key | Paper |
|-----|-------|
| `wang2023selfconsistency` | Self-consistency / multi-trajectory (homogeneous contrast) |
| `brown2024largelanguagemonkeys` | Repeated sampling at inference |
| `snell2024testtime` | Test-time compute scaling |
| `wang2025macsql` | Multi-agent text-to-SQL (role coordination contrast) |
| `pourreza2023dinsql` | Decomposed in-context learning |
| `yao2023react` | Tool-using agent loop |
| `bird2023` | BIRD benchmark |
| `zhong2020execution` | Execution accuracy |

Draft: [`chapter14_model_ensemble.md`](chapter14_model_ensemble.md). Regenerate: `uv run python scripts/generate_chapter14_draft.py`

## Core 15 (minimal related work)

1. `bird2023`
2. `spider2018`
3. `yao2023react`
4. `wang2023selfconsistency`
5. `wang2025macsql`
6. `pourreza2023dinsql`
7. `lewis2020rag`
8. `hayesroth1985blackboard`
9. `zheng2023gptcache`
10. `chen2023frugalgpt`
11. `snell2024testtime`
12. `zhang2023schemalinking`
13. `gao2024dailsql`
14. `openai2024promptcache` / `google2024geminicache`
15. `wooldridge2009mas`

## Example usage

**Pandoc / markdown:**

```markdown
We evaluate on BIRD [@bird2023] with a ReAct-style loop [@yao2023react].
```

**LaTeX:**

```latex
We evaluate on BIRD~\cite{bird2023} with a ReAct-style loop~\cite{yao2023react}.
\bibliography{thesis/references}
```
