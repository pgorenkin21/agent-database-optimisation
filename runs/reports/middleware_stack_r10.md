# Middleware Stack Comparison

Generated: 2026-06-19T13:22:33.809115+00:00

Policies: **P0** (baseline), **P1** (shared SQL cache), **P2** (discovery board), **P1+P2** (both), **early_stop** (Chapter 3; same `best_of_n` selection), **full_stack** (P1+P2+early stop), **full_stack+prune** (P1+P2+early stop+schema pruning), **P3 semantic+prune** (P1+P3 semantic store+early stop+hybrid schema prune). 50-task smoke subset unless noted.

## N=10

### Execution accuracy (%)

| Model | P0 | P1 | P2 | P1+P2 | early_stop | full_stack+prune | P3 semantic+prune |
|-------|--------:|--------:|--------:|--------:|--------:|--------:|--------:|
| GPT-4o mini | 58.0 | 62.0 | 58.0 | 56.0 | 60.0 | 56.0 | 60.0 |
| Gemini 2.5 Flash | 74.0 | 74.0 | 76.0 | 76.0 | 74.0 | 76.0 | 70.0 |
| DeepSeek V3.2 | 60.0 | 60.0 | 62.0 | 62.0 | 60.0 | 64.0 | 60.0 |

### Explore redundancy (%)

| Model | P0 | P1 | P2 | P1+P2 | early_stop | full_stack+prune | P3 semantic+prune |
|-------|--------:|--------:|--------:|--------:|--------:|--------:|--------:|
| GPT-4o mini | 78.7 | 78.1 | 79.3 | 76.0 | 77.8 | 79.9 | 79.4 |
| Gemini 2.5 Flash | 73.6 | 74.1 | 66.9 | 67.0 | 73.6 | 69.9 | 69.2 |
| DeepSeek V3.2 | 71.3 | 70.3 | 75.4 | 72.7 | 75.0 | 75.7 | 71.8 |

### Token overhead (×)

| Model | P0 | P1 | P2 | P1+P2 | early_stop | full_stack+prune | P3 semantic+prune |
|-------|--------:|--------:|--------:|--------:|--------:|--------:|--------:|
| GPT-4o mini | 10.55 | 10.55 | 11.07 | 10.67 | 9.94 | 9.83 | 9.81 |
| Gemini 2.5 Flash | 10.54 | 10.72 | 11.26 | 11.03 | 10.28 | 10.61 | 10.82 |
| DeepSeek V3.2 | 13.38 | 13.68 | 11.54 | 12.38 | 10.72 | 10.35 | 10.88 |

### Middleware interaction (%)

| Model | P0 | P1 | P2 | P1+P2 | early_stop | full_stack+prune | P3 semantic+prune |
|-------|--------:|--------:|--------:|--------:|--------:|--------:|--------:|
| GPT-4o mini | 0.0 | 48.5 | 34.0 | 61.6 | 0.0 | 75.0 | 75.8 |
| Gemini 2.5 Flash | 0.0 | 40.4 | 24.5 | 49.2 | 0.0 | 61.8 | 60.5 |
| DeepSeek V3.2 | 0.0 | 54.6 | 35.1 | 70.2 | 0.0 | 79.5 | 79.9 |

### Token Δ vs P0

| Model | P1 | P2 | P1+P2 | early_stop | full_stack_prune | P3_semantic |
|-------|--------:|--------:|--------:|--------:|--------:|--------:|
| GPT-4o mini | +5.8% | +9.6% | -0.7% | +3.9% | -21.1% | -26.3% |
| Gemini 2.5 Flash | +0.5% | +11.2% | +6.5% | -2.5% | -28.3% | -28.5% |
| DeepSeek V3.2 | -3.8% | -17.5% | -15.3% | -14.3% | -32.6% | -4.0% |

### P1+P2 combined (cache + discovery)

**GPT-4o mini** — batch `parallel_p1p2_r10_bo_gpt-4o-mini_r10_best_of_n_p1_cache_p2_discovery.json`
- EX: 58.0 → 56.0%
- Redundancy: 78.72 → 75.95%
- Cache hit: 65.4%
- Middleware interaction: 61.6% (DB: 886, middleware: 1,705)
- Discovery fragments/task: 14.74

**Gemini 2.5 Flash** — batch `parallel_p1p2_r10_bo_gemini-2.5-flash_r10_best_of_n_p1_cache_p2_discovery.json`
- EX: 74.0 → 76.0%
- Redundancy: 73.56 → 66.97%
- Cache hit: 61.6%
- Middleware interaction: 49.2% (DB: 677, middleware: 1,011)
- Discovery fragments/task: 9.28

**DeepSeek V3.2** — batch `parallel_p1p2_r10_bo_deepseek-v3.2_r10_best_of_n_p1_cache_p2_discovery.json`
- EX: 60.0 → 62.0%
- Redundancy: 71.33 → 72.73%
- Cache hit: 69.0%
- Middleware interaction: 70.2% (DB: 1,408, middleware: 3,645)
- Discovery fragments/task: 20.16
