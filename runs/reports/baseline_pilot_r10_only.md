# Baseline Redundancy Report (P0)

Generated: 2026-06-10T15:43:34.538883+00:00

Policy: **P0** — independent parallel replicas (`P0_parallel`), no shared middleware.

- Model: `gpt-4o-mini`
- Dataset: `mini_dev`
- Batches analysed: 1

## Redundancy vs agent count

| Replicas | Tasks | EX % | Total SQL | Explore SQL | Unique explore | Avg explore redundancy % | Avg sub-expr overlap % | Token overhead | Avg wall (ms) | Total tokens |
|---------:|------:|-----:|----------:|------------:|---------------:|-------------------------:|-----------------------:|---------------:|--------------:|-------------:|
| 10 | 20 | 45.0 | 847 | 651 | 109 | 80.0 | 93.5 | 10.07x | 15233 | 782,337 |

## 10 replicas — `20260610_153343_f55e6c_baseline_r10`

- Execution accuracy: **45.0%**
- Explore query uniqueness: **16.7%** (109 unique / 651 total explore queries)
- AST-unique explore queries: **104**
- Median explore redundancy: **80.2%**
- Median sub-expression overlap: **100.0%**
- Median wall-clock (coord): **9484 ms**

### By difficulty

| Difficulty | Tasks | Avg explore redundancy % |
|------------|------:|---------------------------:|
| challenging | 3 | 89.1 |
| moderate | 8 | 78.0 |
| simple | 9 | 78.8 |

## Metric definitions

- **Explore redundancy %**: fraction of explore SQL statements that duplicate a prior statement (whitespace-normalised) within the same task's replica set.
- **Sub-expression overlap %**: fraction of sqlglot-extracted fragments (tables, columns, predicates) that appear in explore queries from two or more replicas.
- **Token overhead ratio**: total tokens across replicas divided by tokens of the cheapest correct replica.
- **Wall-clock**: coordination session time (parallel_start → coordination_end).
