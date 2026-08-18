# Baseline Redundancy Report (P0)

Generated: 2026-07-16T15:03:32.757122+00:00

Policy: **P0** — independent parallel replicas (`P0_parallel`), no shared middleware.

- Model: `deepseek-v3.2`
- Dataset: `mini_dev`
- Batches analysed: 1

## Redundancy vs agent count

| Replicas | Tasks | EX % | EX % (no API fail) | API fails | Total SQL | Explore SQL | Unique explore | Avg explore redundancy % | Avg sub-expr overlap % | Token overhead | Avg wall (ms) | Total tokens |
|---------:|------:|-----:|-------------------:|----------:|----------:|------------:|---------------:|-------------------------:|-----------------------:|---------------:|--------------:|-------------:|
| 3 | 500 | 51.4 | 51.4 | 0 | 10756 | 9339 | 5712 | 42.3 | 81.7 | 3.53x | 13863 | 36,927,487 |

## 3 replicas — `baseline_full500_r3`

- Execution accuracy: **51.4%**
- Execution accuracy (excluding API failures): **51.4%**
- API failures: **0** (500/500 tasks completed)
- Explore query uniqueness: **61.2%** (5712 unique / 9339 total explore queries)
- AST-unique explore queries: **5540**
- Median explore redundancy: **40.0%**
- Median sub-expression overlap: **88.2%**
- Median wall-clock (coord): **9764 ms**

### By difficulty

| Difficulty | Tasks | Avg explore redundancy % |
|------------|------:|---------------------------:|
| challenging | 102 | 38.6 |
| moderate | 250 | 41.6 |
| simple | 148 | 46.2 |

## Metric definitions

- **Explore redundancy %**: fraction of explore SQL statements that duplicate a prior statement (whitespace-normalised) within the same task's replica set.
- **Sub-expression overlap %**: fraction of sqlglot-extracted fragments (tables, columns, predicates) that appear in explore queries from two or more replicas.
- **Token overhead ratio**: total tokens across replicas divided by tokens of the cheapest correct replica.
- **Wall-clock**: coordination session time (parallel_start → coordination_end).
- **EX % (no API fail)**: execution accuracy counting only tasks that finished without a transport/API error (tasks where the whole parallel run raised after retries).
- **API failures**: tasks where all replicas failed before producing a coordinated answer; recorded as EX=0 in the headline metric.
