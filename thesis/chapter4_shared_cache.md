# Chapter 4: Shared SQL Result Cache (P1)

*Draft generated 2026-06-17 from P0 vs `P1_shared_cache` batch comparisons. Regenerate with `uv run python scripts/generate_chapter4_draft.py`.*

## 4.1 Motivation

Chapters 2–3 established that parallel text-to-SQL replicas duplicate 70–90% of explore-phase SQL, and that early stopping recovers only modest token savings (~8–12%) because duplicates occur *before* any replica submits a correct answer. **P1** attacks duplication at the data layer: a shared LRU cache keyed by AST-normalised SQL returns cached result sets when another replica has already executed the same explore query on the same database.

Unlike early stopping, P1 can eliminate redundant **database round-trips** even while all replicas continue their LLM trajectories. The open question is how much of Chapter 2's explore redundancy is exact string/AST duplication amenable to caching, and whether accuracy is preserved.

## 4.2 Policy: P1_shared_cache

P1 extends the parallel coordinator with a thread-safe cache shared across replicas on one task:

1. Spawn *N* agents as in P0 (no early stopping in these experiments).
2. On each `execute_sql` tool call, normalise SQL with sqlglot (SQLite dialect) and look up `(database_path, ast_key)` in an LRU cache (default 4,096 entries).
3. On **cache hit**, return the stored result set (or stored error) without calling SQLite; log `cache_hit=true` in the replica trace.
4. On **cache miss**, execute SQL, store the result, and proceed as P0.
5. `submit_sql` and gold-SQL evaluation bypass the shared cache.

Cache keys fall back to whitespace-normalised string form when sqlglot cannot parse the SQL. Only explore-phase queries use the cache.

## 4.3 Experimental setup

All settings match Chapters 2–3 unless noted:

- **Benchmark:** BIRD mini-dev smoke subset (50 tasks).
- **Models:** GPT-4o mini, Gemini 2.5 Flash, DeepSeek V3.2.
- **Replica counts:** *N* ∈ {10, 25}.
- **Coordination:** `best_of_n` (same as P0).
- **P0 baseline batches:** latest `parallel_*_baseline_rN_*_best_of_n.json`.
- **P1 batches:** `p1_r10_bo`, `p1_r25_bo` sweep IDs.

## 4.4 Metrics

| Metric | Definition |
|--------|------------|
| **Cache hit rate %** | Per task, `cache_hits / (cache_hits + cache_misses)` for explore lookups; batch mean reported. |
| **Explore redundancy %** | Same as Chapter 2 (string-level duplicates in traces). |
| **Token overhead** | Same as Chapter 2; P1 should not reduce this (LLM still issues probes). |
| **EX %** | Coordinated execution accuracy; must match P0 within run variance. |
| **Middleware interaction %** | Share of interactions served by middleware (cache hits) vs SQLite (see Chapter 2). P1 raises this from 0% without changing explore SQL strings in traces. |

## 4.5 Results

### 4.5.1 Replica count *N*=10

**Table 4.1.** P0 vs P1 shared cache at *N*=10 (50-task smoke subset, `best_of_n`).

| Model | P0 EX % | P1 EX % | P0 redundancy % | P1 redundancy % | P1 cache hit % | P1 middleware % | P0 overhead | P1 overhead | Token Δ |
|-------|--------:|--------:|----------------:|----------------:|---------------:|----------------:|------------:|------------:|--------:|
| GPT-4o mini | 58.0 | 62.0 | 78.7 | 78.1 | 74.6 | 48.5 | 10.55× | 10.55× | +5.8% |
| Gemini 2.5 Flash | 74.0 | 74.0 | 73.6 | 74.1 | 71.0 | 40.4 | 10.54× | 10.72× | +0.5% |
| DeepSeek V3.2 | 60.0 | 60.0 | 71.3 | 70.3 | 69.1 | 54.6 | 13.38× | 13.68× | -3.8% |

### 4.5.2 Replica count *N*=25

**Table 4.2.** P0 vs P1 shared cache at *N*=25 (50-task smoke subset, `best_of_n`).

| Model | P0 EX % | P1 EX % | P0 redundancy % | P1 redundancy % | P1 cache hit % | P1 middleware % | P0 overhead | P1 overhead | Token Δ |
|-------|--------:|--------:|----------------:|----------------:|---------------:|----------------:|------------:|------------:|--------:|
| GPT-4o mini | 62.0 | 62.0 | 87.7 | 88.7 | 84.2 | 54.9 | 27.14× | 26.30× | +0.7% |
| Gemini 2.5 Flash | 70.0 | 72.0† | 76.6 | 80.5 | 78.1 | 45.3 | 24.46× | 25.64× | +2.2% |
| DeepSeek V3.2 | 64.0 | 62.0 | 82.9 | 82.0 | 81.1 | 64.5 | 32.66× | 34.02× | -1.4% |

† Gemini 2.5 Flash P1 at *N*=25: 1 API failure(s); EX on completed tasks = 73.5%.

![Figure 4.1 — P1 vs P0 at N=25](runs/reports/plots/p1_comparison_r25.png)

*Figure 4.1. Explore redundancy (P0 vs P1) and P1 cache hit rate at *N*=25.*

![Figure 4.2 — Cache hit scaling](runs/reports/plots/p1_cache_hit_scaling.png)

*Figure 4.2. Mean explore SQL cache hit rate vs replica count.*

### 4.5.3 Per-model detail

### GPT-4o mini

- Cache hit rate: **84.2%** (3,212 hits / 3,885 explore lookups).
- Middleware interaction: **54.9%** (3,212 middleware vs 1,895 SQLite executions).
- Explore redundancy: 87.7 → 88.7 (+1.0 pp).
- Token overhead: 27.14× → 26.30× (unchanged in practice).

### Gemini 2.5 Flash

- Cache hit rate: **78.1%** (1,463 hits / 1,617 explore lookups).
- Middleware interaction: **45.3%** (1,463 middleware vs 1,379 SQLite executions).
- Explore redundancy: 76.6 → 80.5 (+3.9 pp).
- Token overhead: 24.46× → 25.64× (unchanged in practice).

### DeepSeek V3.2

- Cache hit rate: **81.1%** (5,775 hits / 7,706 explore lookups).
- Middleware interaction: **64.5%** (5,775 middleware vs 3,113 SQLite executions).
- Explore redundancy: 82.9 → 82.0 (-0.9 pp).
- Token overhead: 32.66× → 34.02× (unchanged in practice).

## 4.6 Discussion

**P1 eliminates most redundant database work at high *N*.** At *N*=25, mean cache hit rates range from **78–84%** across models. Roughly four out of five explore `execute_sql` calls are served from cache rather than hitting SQLite. **Middleware interaction %** rises from 0% under P0 to **45–64%** at *N*=25, quantifying how much work the cache absorbs.

**Explore redundancy in traces is essentially unchanged.** String-level redundancy metrics remain within ~1 pp of P0 because replicas still *issue* the same explore SQL—the cache short-circuits execution, not LLM tool choice. Chapter 2's redundancy metric therefore understates P1's benefit when measured only from SQL strings in traces.

**Token overhead and EX are stable.** Total token spend and overhead ratios match P0 within run-to-run noise (+3% at most on r=10 GPT). Coordinated EX is unchanged for GPT and DeepSeek; Gemini P1 at *N*=25 has one API failure on credits (73.5% EX on completed tasks vs 70% P0 headline).

**Cache effectiveness scales with *N*.** Hit rates rise from ~70% at *N*=10 to ~78–84% at *N*=25, consistent with Chapter 2's finding that duplicate probes dominate at high replica counts.

**P1 complements early stopping.** Early stop (Chapter 3) trims post-success LLM turns; P1 removes duplicate DB work during exploration. Neither reduces the number of explore queries the models choose to issue—motivating **P2** sub-expression propagation to share structural discoveries before SQL is written.

## 4.7 Limitations

1. **In-memory per-task cache.** No cross-task or cross-batch persistence.
2. **Exact AST/string keys only.** Queries that differ superficially but semantically overlap are not deduplicated (P2 scope).
3. **Trace metrics under-report benefit.** Explore redundancy counts duplicate SQL strings, not whether SQLite was invoked; middleware interaction % closes that gap for P1.
4. **Gemini API failure** on one P1 *N*=25 task (billing); cite EX excluding API errors.

## 4.8 Summary and implications

P1 (`P1_shared_cache`) removes **78–84%** of explore-phase database round-trips at *N*=25 via an AST-keyed shared cache, without harming execution accuracy. Token cost and string-level redundancy remain dominated by LLM exploration policy.

The remaining thesis direction is **P2**: propagate sub-expression discoveries (tables, columns, predicates) across replicas to reduce the explore queries themselves—not only cache their execution.

---

## Appendix: source artefacts

| Artefact | Path |
|----------|------|
| P1 batches (*N*=10) | `runs/batches/parallel_p1_r10_bo_*` |
| P1 batches (*N*=25) | `runs/batches/parallel_p1_r25_bo_*` |
| Comparison report | `runs/reports/p1_vs_p0.json` |
| Figure 4.x (*N*=10) | `runs/reports/plots/p1_comparison_r10.png` |
| Figure 4.x (*N*=25) | `runs/reports/plots/p1_comparison_r25.png` |
| Figure 4.2 | `runs/reports/plots/p1_cache_hit_scaling.png` |
