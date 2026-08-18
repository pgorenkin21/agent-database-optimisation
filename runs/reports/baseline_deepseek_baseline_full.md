# Baseline Redundancy Report (P0)

Generated: 2026-07-16T15:03:12.795400+00:00

Policy: **P0** — independent parallel replicas (`P0_parallel`), no shared middleware.

- Model: `deepseek-v3.2`
- Dataset: `mini_dev`
- Batches analysed: 3

## Redundancy vs agent count

| Replicas | Tasks | EX % | EX % (no API fail) | API fails | Total SQL | Explore SQL | Unique explore | Avg explore redundancy % | Avg sub-expr overlap % | Token overhead | Avg wall (ms) | Total tokens |
|---------:|------:|-----:|-------------------:|----------:|----------:|------------:|---------------:|-------------------------:|-----------------------:|---------------:|--------------:|-------------:|
| 3 | 50 | 60.0 | 60.0 | 0 | 1061 | 917 | 455 | 54.1 | 87.8 | 3.19x | 61091 | 2,193,564 |
| 10 | 50 | 60.0 | 60.0 | 0 | 3572 | 3114 | 1106 | 71.3 | 84.8 | 13.38x | 101957 | 7,792,210 |
| 25 | 50 | 64.0 | 64.0 | 0 | 8962 | 7790 | 1812 | 82.9 | 84.0 | 32.66x | 21537 | 18,889,223 |

## 3 replicas — `20260611_123747_60b677_baseline_r3`

- Execution accuracy: **60.0%**
- Execution accuracy (excluding API failures): **60.0%**
- API failures: **0** (50/50 tasks completed)
- Explore query uniqueness: **49.6%** (455 unique / 917 total explore queries)
- AST-unique explore queries: **449**
- Median explore redundancy: **66.7%**
- Median sub-expression overlap: **100.0%**
- Median wall-clock (coord): **8758 ms**

### By difficulty

| Difficulty | Tasks | Avg explore redundancy % |
|------------|------:|---------------------------:|
| challenging | 6 | 47.0 |
| moderate | 19 | 51.8 |
| simple | 25 | 57.6 |

## 10 replicas — `20260611_123747_60b677_baseline_r10`

- Execution accuracy: **60.0%**
- Execution accuracy (excluding API failures): **60.0%**
- API failures: **0** (50/50 tasks completed)
- Explore query uniqueness: **35.5%** (1106 unique / 3114 total explore queries)
- AST-unique explore queries: **1080**
- Median explore redundancy: **74.6%**
- Median sub-expression overlap: **87.7%**
- Median wall-clock (coord): **10017 ms**

### By difficulty

| Difficulty | Tasks | Avg explore redundancy % |
|------------|------:|---------------------------:|
| challenging | 6 | 62.1 |
| moderate | 19 | 66.5 |
| simple | 25 | 77.2 |

## 25 replicas — `20260611_123747_60b677_baseline_r25`

- Execution accuracy: **64.0%**
- Execution accuracy (excluding API failures): **64.0%**
- API failures: **0** (50/50 tasks completed)
- Explore query uniqueness: **23.3%** (1812 unique / 7790 total explore queries)
- AST-unique explore queries: **1766**
- Median explore redundancy: **88.0%**
- Median sub-expression overlap: **85.7%**
- Median wall-clock (coord): **12443 ms**

### By difficulty

| Difficulty | Tasks | Avg explore redundancy % |
|------------|------:|---------------------------:|
| challenging | 6 | 73.3 |
| moderate | 19 | 78.1 |
| simple | 25 | 88.8 |

## Metric definitions

- **Explore redundancy %**: fraction of explore SQL statements that duplicate a prior statement (whitespace-normalised) within the same task's replica set.
- **Sub-expression overlap %**: fraction of sqlglot-extracted fragments (tables, columns, predicates) that appear in explore queries from two or more replicas.
- **Token overhead ratio**: total tokens across replicas divided by tokens of the cheapest correct replica.
- **Wall-clock**: coordination session time (parallel_start → coordination_end).
- **EX % (no API fail)**: execution accuracy counting only tasks that finished without a transport/API error (tasks where the whole parallel run raised after retries).
- **API failures**: tasks where all replicas failed before producing a coordinated answer; recorded as EX=0 in the headline metric.
