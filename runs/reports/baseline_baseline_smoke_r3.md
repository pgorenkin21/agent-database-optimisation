# Baseline Redundancy Report (P0)

Generated: 2026-06-10T15:31:24.243386+00:00

Policy: **P0** — independent parallel replicas (`P0_parallel`), no shared middleware.

- Model: `gpt-4o-mini`
- Dataset: `mini_dev`
- Batches analysed: 1

## Redundancy vs agent count

| Replicas | Tasks | EX % | Total SQL | Explore SQL | Unique explore | Avg explore redundancy % | Avg sub-expr overlap % | Token overhead | Avg wall (ms) | Total tokens |
|---------:|------:|-----:|----------:|------------:|---------------:|-------------------------:|-----------------------:|---------------:|--------------:|-------------:|
| 3 | 50 | 58.0 | 572 | 424 | 173 | 52.2 | 88.3 | 3.18x | 11160 | 717,658 |

## 3 replicas — `20260610_124547_2f8250_parallel_gpt-4o-mini`

- Execution accuracy: **58.0%**
- Explore query uniqueness: **40.8%** (173 unique / 424 total explore queries)
- AST-unique explore queries: **169**
- Median explore redundancy: **64.1%**
- Median sub-expression overlap: **100.0%**
- Median wall-clock (coord): **5916 ms**

### By difficulty

| Difficulty | Tasks | Avg explore redundancy % |
|------------|------:|---------------------------:|
| challenging | 6 | 63.9 |
| moderate | 19 | 50.6 |
| simple | 25 | 50.7 |

## Metric definitions

- **Explore redundancy %**: fraction of explore SQL statements that duplicate a prior statement (whitespace-normalised) within the same task's replica set.
- **Sub-expression overlap %**: fraction of sqlglot-extracted fragments (tables, columns, predicates) that appear in explore queries from two or more replicas.
- **Token overhead ratio**: total tokens across replicas divided by tokens of the cheapest correct replica.
- **Wall-clock**: coordination session time (parallel_start → coordination_end).
