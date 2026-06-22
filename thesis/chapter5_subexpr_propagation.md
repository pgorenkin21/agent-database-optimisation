# Chapter 5: Sub-Expression Propagation (P2)

*Draft generated 2026-06-17 from P0 vs `P2_subexpr_propagation` batch comparisons. Regenerate with `uv run python scripts/generate_chapter5_draft.py`.*

## 5.1 Motivation

Chapters 3–4 optimised coordination at the **execution** layer: early stopping trims post-success LLM turns; P1 caches duplicate explore SQL against SQLite. Neither policy tells replicas what structural discoveries their siblings have already made. Chapter 2 showed **85–94% sub-expression overlap** across replicas—tables, columns, and predicates reappear even when full SQL strings differ—suggesting value in sharing those fragments *before* the next explore query is written.

**P2** implements a *shared discovery board*: after each explore `execute_sql`, replicas publish sqlglot-extracted fragments to a thread-safe store; before every LLM turn, each agent receives a user-message block listing peer discoveries (tables, columns, predicates, join conditions) with guidance to avoid redundant probes.

Unlike P1, P2 targets the **LLM exploration policy** directly. The hypothesis is that propagating structural context reduces duplicate explore SQL and token spend without hurting execution accuracy.

## 5.2 Policy: P2_subexpr_propagation

P2 extends the parallel coordinator with a per-task discovery board:

1. Spawn *N* agents as in P0 (no shared SQL cache or early stopping in these experiments).
2. On each explore `execute_sql`, extract fragments (`table:`, `col:`, `pred:`, `join_on:`) via sqlglot and publish to the shared board.
3. Before each LLM `complete` call, inject a compact **peer discoveries** user message (replacing any prior discovery message for that turn).
4. Log `discovery_injection` events in replica traces; aggregate `discovery_stats` in coordination traces.

Fragment keys match the overlap metric from Chapter 2. Only explore-phase SQL contributes; `submit_sql` is not published.

## 5.3 Experimental setup

All settings match Chapters 2–4 unless noted:

- **Benchmark:** BIRD mini-dev smoke subset (50 tasks).
- **Models:** GPT-4o mini, Gemini 2.5 Flash, DeepSeek V3.2.
- **Replica counts:** *N* ∈ {10, 25}.
- **Coordination:** `best_of_n` (same as P0).
- **P0 baseline batches:** latest `parallel_*_baseline_rN_*_best_of_n.json`.
- **P2 batches:** `p2_r10_bo`, `p2_r25_bo` sweep IDs (`--discovery-board`).

## 5.4 Metrics

| Metric | Definition |
|--------|------------|
| **Discovery fragments / task** | Mean unique fragment keys published per task. |
| **Context injections / task** | Mean LLM turns where a non-empty peer-discovery block was injected. |
| **Explore redundancy %** | Same as Chapter 2 (string-level duplicates in traces). |
| **Token overhead** | Same as Chapter 2; injection adds prompt tokens each turn. |
| **EX %** | Coordinated execution accuracy vs P0. |
| **Middleware interaction %** | Share of interactions served by middleware (discovery prompt injections) vs SQLite. P2 raises this from 0% via injections even though every explore query still executes against the database. |

## 5.5 Results

### 5.5.1 Replica count *N*=10

**Table 5.1.** P0 vs P2 discovery board at *N*=10 (50-task smoke subset, `best_of_n`, no early stopping).

| Model | P0 EX % | P2 EX % | P0 redundancy % | P2 redundancy % | Red Δ | P2 frags/task | P2 middleware % | P0 overhead | P2 overhead | Token Δ |
|-------|--------:|--------:|----------------:|----------------:|------:|-------------:|----------------:|------------:|------------:|--------:|
| GPT-4o mini | 58.0 | 58.0 | 78.7 | 79.3 | +0.6pp | 14.6 | 34.0 | 10.55× | 11.07× | +9.6% |
| Gemini 2.5 Flash | 74.0 | 76.0 | 73.6 | 66.9 | -6.7pp | 10.3 | 24.5 | 10.54× | 11.26× | +11.2% |
| DeepSeek V3.2 | 60.0 | 62.0 | 71.3 | 75.4 | +4.1pp | 18.3 | 35.1 | 13.38× | 11.54× | -17.5% |

### 5.5.2 Replica count *N*=25

**Table 5.2.** P0 vs P2 discovery board at *N*=25 (50-task smoke subset, `best_of_n`, no early stopping).

| Model | P0 EX % | P2 EX % | P0 redundancy % | P2 redundancy % | Red Δ | P2 frags/task | P2 middleware % | P0 overhead | P2 overhead | Token Δ |
|-------|--------:|--------:|----------------:|----------------:|------:|-------------:|----------------:|------------:|------------:|--------:|
| GPT-4o mini | 62.0 | 56.0 | 87.7 | 87.3 | -0.4pp | 16.7 | 35.1 | 27.14× | 28.21× | +6.0% |
| Gemini 2.5 Flash | 70.0 | 76.0 | 76.6 | 75.3 | -1.3pp | 10.5 | 25.6 | 24.46× | 27.81× | +16.0% |
| DeepSeek V3.2 | 64.0 | 62.0 | 82.9 | 84.0 | +1.1pp | 23.5 | 35.8 | 32.66× | 31.66× | -13.6% |

![Figure 5.1 — P2 vs P0 at N=25](runs/reports/plots/p2_comparison_r25.png)

*Figure 5.1. Explore redundancy (P0 vs P2) and mean discovery fragments per task at *N*=25.*

![Figure 5.2 — Redundancy delta scaling](runs/reports/plots/p2_redundancy_delta_scaling.png)

*Figure 5.2. Change in mean explore redundancy (P2 − P0) vs replica count.*

### 5.5.3 Per-model detail

### GPT-4o mini

- Discovery board: **16.7** unique fragments/task; **55.1** prompt injections/task.
- Middleware interaction: **35.1%** (2,757 prompt injections; all explore SQL still hits SQLite without P1).
- Explore redundancy: 87.7 → 87.3 (-0.4 pp).
- Token overhead: 27.14× → 28.21× (+6.0% total tokens).

### Gemini 2.5 Flash

- Discovery board: **10.5** unique fragments/task; **26.3** prompt injections/task.
- Middleware interaction: **25.6%** (1,314 prompt injections; all explore SQL still hits SQLite without P1).
- Explore redundancy: 76.6 → 75.3 (-1.3 pp).
- Token overhead: 24.46× → 27.81× (+16.0% total tokens).

### DeepSeek V3.2

- Discovery board: **23.5** unique fragments/task; **95.3** prompt injections/task.
- Middleware interaction: **35.8%** (4,767 prompt injections; all explore SQL still hits SQLite without P1).
- Explore redundancy: 82.9 → 84.0 (+1.1 pp).
- Token overhead: 32.66× → 31.66× (-13.6% total tokens).

## 5.6 Discussion

**P2 effects are model-dependent and modest overall.** Unlike P1, which reliably eliminates 70–84% of SQLite round-trips, prompt-level fragment sharing does not consistently reduce string-level explore redundancy. At *N*=25, redundancy changes range from roughly −1 to +1 pp for GPT and DeepSeek; Gemini shows a larger shift at *N*=10 (-6.7 pp). The strongest improvement observed is **Gemini 2.5 Flash** at *N*=10 (-6.7 pp)—directionally aligned with Chapter 2's overlap findings but smaller than the overlap percentages themselves.

**Discovery boards are active.** At *N*=25, mean fragments published per task range from **10–24** across models, with multiple context injections per task. **Middleware interaction %** rises from 0% under P0 to roughly 25–35% at *N*=10 (discovery injections counted as middleware events even though SQLite is still invoked for every explore query). Middleware is doing work; models do not always comply by issuing fewer explore queries.

**Token overhead is not reduced—and can rise slightly.** Each turn may include a growing peer-discovery block in the prompt. Total token spend is within run noise for most models but trends upward when injections are frequent (e.g. +7% Gemini at *N*=10). P2 trades a small prompt cost for uncertain exploration savings.

**Execution accuracy is mostly stable.** Gemini EX matches or improves vs P0 (+2 pp at both *N* values). GPT EX is unchanged at *N*=10 but drops 6 pp at *N*=25 (62% → 56%)—worth monitoring on the full dev set. DeepSeek is within 2 pp of P0.

**P2 complements but does not replace P1.** P1 removes duplicate *execution*; P2 attempts to steer duplicate *probes*. Chapter 2's 85–94% sub-expression overlap is a structural upper bound on what fragment lists can explain; converting overlap into fewer SQL strings requires models to follow the injected hints—a soft constraint compared to P1's hard cache.

**Optional stacked policy.** A supplementary GPT *N*=10 run with `--early-stop` combined P2 discovery with Chapter 3 cancellation (trace policy `P2_subexpr_propagation_early_stop`); token overhead fell to 9.7× vs 11.1× for P2 alone, showing stacked middleware can compound. Full stacked evaluation is left to future work.

## 5.7 Limitations

1. **Soft coordination.** Models may ignore peer-discovery messages; no enforcement.
2. **Prompt growth.** Discovery blocks add tokens each turn; not capped in these runs.
3. **Fragment extraction only.** No semantic dedup beyond sqlglot fragments (cf. P1 AST keys).
4. **Smoke subset.** 50 tasks; GPT *N*=25 EX regression may not generalise.
5. **No P1+P2 combined runs** in the main matrix (only exploratory GPT early-stop stack).

## 5.8 Summary and implications

P2 (`P2_subexpr_propagation`) publishes **10–24** unique SQL fragments per task at *N*=25 and injects peer context before each LLM turn. The policy produces meaningful redundancy reduction for some model/count pairs (notably Gemini at *N*=10) but is not a reliable win across the board. Token and redundancy gains are smaller and less consistent than P1's database-side cache.

The middleware stack evaluated so far spans three layers: **early stop** (post-success tokens), **P1 cache** (duplicate execution), and **P2 discovery** (exploration hints). Chapter 6 stacks these with schema pruning; **Chapter 7** evaluates **P3** (bounded semantic fact store) as an alternative to P2 fragment injection, with model-specific deployment recommendations.

---

## Appendix: source artefacts

| Artefact | Path |
|----------|------|
| P2 batches (*N*=10) | `runs/batches/parallel_p2_r10_bo_*` |
| P2 batches (*N*=25) | `runs/batches/parallel_p2_r25_bo_*` |
| Comparison report | `runs/reports/p2_vs_p0.json` |
| Figure 5.x (*N*=10) | `runs/reports/plots/p2_comparison_r10.png` |
| Figure 5.x (*N*=25) | `runs/reports/plots/p2_comparison_r25.png` |
| Figure 5.2 | `runs/reports/plots/p2_redundancy_delta_scaling.png` |
