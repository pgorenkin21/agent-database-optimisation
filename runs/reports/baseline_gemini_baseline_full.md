# Baseline Redundancy Report (P0)

Generated: 2026-07-16T15:03:04.524766+00:00

Policy: **P0** — independent parallel replicas (`P0_parallel`), no shared middleware.

- Model: `gemini-2.5-flash`
- Dataset: `mini_dev`
- Batches analysed: 3

## Redundancy vs agent count

| Replicas | Tasks | EX % | EX % (no API fail) | API fails | Total SQL | Explore SQL | Unique explore | Avg explore redundancy % | Avg sub-expr overlap % | Token overhead | Avg wall (ms) | Total tokens |
|---------:|------:|-----:|-------------------:|----------:|----------:|------------:|---------------:|-------------------------:|-----------------------:|---------------:|--------------:|-------------:|
| 3 | 50 | 72.0 | 72.0 | 0 | 346 | 196 | 96 | 45.9 | 70.5 | 3.15x | 7622 | 463,742 |
| 10 | 50 | 74.0 | 74.0 | 0 | 1153 | 653 | 113 | 73.6 | 87.0 | 10.54x | 8475 | 1,568,278 |
| 25 | 47 | 70.0 | 74.5 | 3 | 2723 | 1548 | 111 | 81.5 | 86.8 | 26.55x | 15714 | 3,685,459 |

## 3 replicas — `20260611_123711_91299c_baseline_r3`

- Execution accuracy: **72.0%**
- Execution accuracy (excluding API failures): **72.0%**
- API failures: **0** (50/50 tasks completed)
- Explore query uniqueness: **49.0%** (96 unique / 196 total explore queries)
- AST-unique explore queries: **96**
- Median explore redundancy: **66.7%**
- Median sub-expression overlap: **100.0%**
- Median wall-clock (coord): **4486 ms**

### By difficulty

| Difficulty | Tasks | Avg explore redundancy % |
|------------|------:|---------------------------:|
| challenging | 6 | 32.4 |
| moderate | 19 | 52.1 |
| simple | 25 | 44.3 |

## 10 replicas — `20260611_123711_91299c_baseline_r10`

- Execution accuracy: **74.0%**
- Execution accuracy (excluding API failures): **74.0%**
- API failures: **0** (50/50 tasks completed)
- Explore query uniqueness: **17.3%** (113 unique / 653 total explore queries)
- AST-unique explore queries: **113**
- Median explore redundancy: **80.7%**
- Median sub-expression overlap: **100.0%**
- Median wall-clock (coord): **5802 ms**

### By difficulty

| Difficulty | Tasks | Avg explore redundancy % |
|------------|------:|---------------------------:|
| challenging | 6 | 74.0 |
| moderate | 19 | 80.8 |
| simple | 25 | 67.9 |

## 25 replicas — `20260611_123711_91299c_baseline_r25`

- Execution accuracy: **70.0%**
- Execution accuracy (excluding API failures): **74.5%**
- API failures: **3** (47/50 tasks completed)
- Explore query uniqueness: **7.2%** (111 unique / 1548 total explore queries)
- AST-unique explore queries: **111**
- Median explore redundancy: **92.3%**
- Median sub-expression overlap: **100.0%**
- Median wall-clock (coord): **8159 ms**

### By difficulty

| Difficulty | Tasks | Avg explore redundancy % |
|------------|------:|---------------------------:|
| challenging | 6 | 89.6 |
| moderate | 17 | 88.6 |
| simple | 24 | 74.4 |

## Metric definitions

- **Explore redundancy %**: fraction of explore SQL statements that duplicate a prior statement (whitespace-normalised) within the same task's replica set.
- **Sub-expression overlap %**: fraction of sqlglot-extracted fragments (tables, columns, predicates) that appear in explore queries from two or more replicas.
- **Token overhead ratio**: total tokens across replicas divided by tokens of the cheapest correct replica.
- **Wall-clock**: coordination session time (parallel_start → coordination_end).
- **EX % (no API fail)**: execution accuracy counting only tasks that finished without a transport/API error (tasks where the whole parallel run raised after retries).
- **API failures**: tasks where all replicas failed before producing a coordinated answer; recorded as EX=0 in the headline metric.
