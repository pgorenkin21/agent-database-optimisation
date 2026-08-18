# Baseline Redundancy Report (P0)

Generated: 2026-07-16T15:02:51.296875+00:00

Policy: **P0** — independent parallel replicas (`P0_parallel`), no shared middleware.

- Model: `gpt-4o-mini`
- Dataset: `mini_dev`
- Batches analysed: 3

## Redundancy vs agent count

| Replicas | Tasks | EX % | EX % (no API fail) | API fails | Total SQL | Explore SQL | Unique explore | Avg explore redundancy % | Avg sub-expr overlap % | Token overhead | Avg wall (ms) | Total tokens |
|---------:|------:|-----:|-------------------:|----------:|----------:|------------:|---------------:|-------------------------:|-----------------------:|---------------:|--------------:|-------------:|
| 3 | 50 | 60.0 | 60.0 | 0 | 543 | 396 | 178 | 50.6 | 89.3 | 3.06x | 6435 | 684,959 |
| 10 | 50 | 58.0 | 58.0 | 0 | 1863 | 1371 | 268 | 78.7 | 92.5 | 10.55x | 11656 | 2,341,781 |
| 25 | 50 | 62.0 | 62.0 | 0 | 4946 | 3728 | 454 | 87.7 | 93.2 | 27.14x | 31920 | 6,322,822 |

## 3 replicas — `gpt_baseline_redo_jun13tier2v2_baseline_r3`

- Execution accuracy: **60.0%**
- Execution accuracy (excluding API failures): **60.0%**
- API failures: **0** (50/50 tasks completed)
- Explore query uniqueness: **45.0%** (178 unique / 396 total explore queries)
- AST-unique explore queries: **172**
- Median explore redundancy: **51.2%**
- Median sub-expression overlap: **100.0%**
- Median wall-clock (coord): **4855 ms**

### By difficulty

| Difficulty | Tasks | Avg explore redundancy % |
|------------|------:|---------------------------:|
| challenging | 6 | 62.5 |
| moderate | 19 | 46.5 |
| simple | 25 | 50.9 |

## 10 replicas — `gpt_baseline_redo_jun13tier2v2_baseline_r10`

- Execution accuracy: **58.0%**
- Execution accuracy (excluding API failures): **58.0%**
- API failures: **0** (50/50 tasks completed)
- Explore query uniqueness: **19.6%** (268 unique / 1371 total explore queries)
- AST-unique explore queries: **252**
- Median explore redundancy: **80.3%**
- Median sub-expression overlap: **100.0%**
- Median wall-clock (coord): **7119 ms**

### By difficulty

| Difficulty | Tasks | Avg explore redundancy % |
|------------|------:|---------------------------:|
| challenging | 6 | 84.4 |
| moderate | 19 | 76.1 |
| simple | 25 | 79.3 |

## 25 replicas — `gpt_baseline_redo_jun13tier2v2_baseline_r25`

- Execution accuracy: **62.0%**
- Execution accuracy (excluding API failures): **62.0%**
- API failures: **0** (50/50 tasks completed)
- Explore query uniqueness: **12.2%** (454 unique / 3728 total explore queries)
- AST-unique explore queries: **427**
- Median explore redundancy: **88.7%**
- Median sub-expression overlap: **100.0%**
- Median wall-clock (coord): **8476 ms**

### By difficulty

| Difficulty | Tasks | Avg explore redundancy % |
|------------|------:|---------------------------:|
| challenging | 6 | 87.0 |
| moderate | 19 | 86.5 |
| simple | 25 | 88.8 |

## Metric definitions

- **Explore redundancy %**: fraction of explore SQL statements that duplicate a prior statement (whitespace-normalised) within the same task's replica set.
- **Sub-expression overlap %**: fraction of sqlglot-extracted fragments (tables, columns, predicates) that appear in explore queries from two or more replicas.
- **Token overhead ratio**: total tokens across replicas divided by tokens of the cheapest correct replica.
- **Wall-clock**: coordination session time (parallel_start → coordination_end).
- **EX % (no API fail)**: execution accuracy counting only tasks that finished without a transport/API error (tasks where the whole parallel run raised after retries).
- **API failures**: tasks where all replicas failed before producing a coordinated answer; recorded as EX=0 in the headline metric.
