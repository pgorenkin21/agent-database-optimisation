# Middleware Stack Comparison

Generated: 2026-06-17T16:07:42.181706+00:00

Policies: **P0** (baseline), **P1** (shared SQL cache), **P2** (discovery board), **P1+P2** (both), **early_stop** (Chapter 3; same `best_of_n` selection). 50-task smoke subset unless noted.

## N=10

### Execution accuracy (%)

| Model | P0 | P1 | P2 | P1+P2 | early_stop |
|-------|--------:|--------:|--------:|--------:|--------:|
| GPT-4o mini | 58.0 | 62.0 | 58.0 | 56.0 | 60.0 |
| Gemini 2.5 Flash | 74.0 | 74.0 | 76.0 | 76.0 | 74.0 |
| DeepSeek V3.2 | 60.0 | 60.0 | 62.0 | 62.0 | 60.0 |

### Explore redundancy (%)

| Model | P0 | P1 | P2 | P1+P2 | early_stop |
|-------|--------:|--------:|--------:|--------:|--------:|
| GPT-4o mini | 78.7 | 78.1 | 79.3 | 76.0 | 77.8 |
| Gemini 2.5 Flash | 73.6 | 74.1 | 66.9 | 67.0 | 73.6 |
| DeepSeek V3.2 | 71.3 | 70.3 | 75.4 | 72.7 | 75.0 |

### Token overhead (×)

| Model | P0 | P1 | P2 | P1+P2 | early_stop |
|-------|--------:|--------:|--------:|--------:|--------:|
| GPT-4o mini | 10.55 | 10.55 | 11.07 | 10.67 | 9.94 |
| Gemini 2.5 Flash | 10.54 | 10.72 | 11.26 | 11.03 | 10.28 |
| DeepSeek V3.2 | 13.38 | 13.68 | 11.54 | 12.38 | 10.72 |

### Token Δ vs P0

| Model | P1 | P2 | P1+P2 | early_stop |
|-------|--------:|--------:|--------:|--------:|
| GPT-4o mini | +5.8% | +9.6% | -0.7% | +3.9% |
| Gemini 2.5 Flash | +0.5% | +11.2% | +6.5% | -2.5% |
| DeepSeek V3.2 | -3.8% | -17.5% | -15.3% | -14.3% |

### P1+P2 combined (cache + discovery)

**GPT-4o mini** — batch `parallel_p1p2_r10_bo_gpt-4o-mini_r10_best_of_n_p1_cache_p2_discovery.json`
- EX: 58.0 → 56.0%
- Redundancy: 78.72 → 75.95%
- Cache hit: 65.4%
- Discovery fragments/task: 14.74

**Gemini 2.5 Flash** — batch `parallel_p1p2_r10_bo_gemini-2.5-flash_r10_best_of_n_p1_cache_p2_discovery.json`
- EX: 74.0 → 76.0%
- Redundancy: 73.56 → 66.97%
- Cache hit: 61.6%
- Discovery fragments/task: 9.28

**DeepSeek V3.2** — batch `parallel_p1p2_r10_bo_deepseek-v3.2_r10_best_of_n_p1_cache_p2_discovery.json`
- EX: 60.0 → 62.0%
- Redundancy: 71.33 → 72.73%
- Cache hit: 69.0%
- Discovery fragments/task: 20.16
