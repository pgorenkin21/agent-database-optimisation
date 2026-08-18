# Baseline Redundancy Report (P0)

Generated: 2026-07-16T15:03:25.406034+00:00

Policy: **P0** — independent parallel replicas (`P0_parallel`), no shared middleware.

- Model: `gemini-2.5-flash`
- Dataset: `mini_dev`
- Batches analysed: 1

## Redundancy vs agent count

| Replicas | Tasks | EX % | EX % (no API fail) | API fails | Total SQL | Explore SQL | Unique explore | Avg explore redundancy % | Avg sub-expr overlap % | Token overhead | Avg wall (ms) | Total tokens |
|---------:|------:|-----:|-------------------:|----------:|----------:|------------:|---------------:|-------------------------:|-----------------------:|---------------:|--------------:|-------------:|
| 3 | 499 | 64.6 | 64.7 | 1 | 3335 | 1839 | 880 | 44.2 | 72.0 | 3.21x | 6468 | 9,095,459 |

## 3 replicas — `baseline_full500_r3`

- Execution accuracy: **64.6%**
- Execution accuracy (excluding API failures): **64.7%**
- API failures: **1** (499/500 tasks completed)
- Explore query uniqueness: **47.9%** (880 unique / 1839 total explore queries)
- AST-unique explore queries: **872**
- Median explore redundancy: **50.0%**
- Median sub-expression overlap: **100.0%**
- Median wall-clock (coord): **3966 ms**

### By difficulty

| Difficulty | Tasks | Avg explore redundancy % |
|------------|------:|---------------------------:|
| challenging | 101 | 47.3 |
| moderate | 250 | 45.3 |
| simple | 148 | 40.3 |

## Metric definitions

- **Explore redundancy %**: fraction of explore SQL statements that duplicate a prior statement (whitespace-normalised) within the same task's replica set.
- **Sub-expression overlap %**: fraction of sqlglot-extracted fragments (tables, columns, predicates) that appear in explore queries from two or more replicas.
- **Token overhead ratio**: total tokens across replicas divided by tokens of the cheapest correct replica.
- **Wall-clock**: coordination session time (parallel_start → coordination_end).
- **EX % (no API fail)**: execution accuracy counting only tasks that finished without a transport/API error (tasks where the whole parallel run raised after retries).
- **API failures**: tasks where all replicas failed before producing a coordinated answer; recorded as EX=0 in the headline metric.
