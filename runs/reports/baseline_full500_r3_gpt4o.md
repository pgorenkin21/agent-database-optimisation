# Baseline Redundancy Report (P0)

Generated: 2026-07-16T15:03:23.275409+00:00

Policy: **P0** — independent parallel replicas (`P0_parallel`), no shared middleware.

- Model: `gpt-4o-mini`
- Dataset: `mini_dev`
- Batches analysed: 1

## Redundancy vs agent count

| Replicas | Tasks | EX % | EX % (no API fail) | API fails | Total SQL | Explore SQL | Unique explore | Avg explore redundancy % | Avg sub-expr overlap % | Token overhead | Avg wall (ms) | Total tokens |
|---------:|------:|-----:|-------------------:|----------:|----------:|------------:|---------------:|-------------------------:|-----------------------:|---------------:|--------------:|-------------:|
| 3 | 500 | 52.8 | 52.8 | 0 | 6016 | 4577 | 1989 | 52.8 | 89.1 | 3.21x | 7024 | 15,122,305 |

## 3 replicas — `baseline_full500_r3`

- Execution accuracy: **52.8%**
- Execution accuracy (excluding API failures): **52.8%**
- API failures: **0** (500/500 tasks completed)
- Explore query uniqueness: **43.5%** (1989 unique / 4577 total explore queries)
- AST-unique explore queries: **1919**
- Median explore redundancy: **66.7%**
- Median sub-expression overlap: **100.0%**
- Median wall-clock (coord): **4866 ms**

### By difficulty

| Difficulty | Tasks | Avg explore redundancy % |
|------------|------:|---------------------------:|
| challenging | 102 | 49.5 |
| moderate | 250 | 52.4 |
| simple | 148 | 55.7 |

## Metric definitions

- **Explore redundancy %**: fraction of explore SQL statements that duplicate a prior statement (whitespace-normalised) within the same task's replica set.
- **Sub-expression overlap %**: fraction of sqlglot-extracted fragments (tables, columns, predicates) that appear in explore queries from two or more replicas.
- **Token overhead ratio**: total tokens across replicas divided by tokens of the cheapest correct replica.
- **Wall-clock**: coordination session time (parallel_start → coordination_end).
- **EX % (no API fail)**: execution accuracy counting only tasks that finished without a transport/API error (tasks where the whole parallel run raised after retries).
- **API failures**: tasks where all replicas failed before producing a coordinated answer; recorded as EX=0 in the headline metric.
