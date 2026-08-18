# P1 Shared Cache vs P0 Comparison

Generated: 2026-06-17T12:32:19.390060+00:00

Apples-to-apples: same model, replica count, and `best_of_n` policy. P1 adds `--shared-cache` (AST-keyed LRU for explore-phase `execute_sql`).

## N=10

| Model | P0 EX % | P1 EX % | P0 red % | P1 red % | Red Δ | P1 cache hit % | P0 tokens | P1 tokens | Token Δ |
|-------|--------:|--------:|---------:|---------:|------:|---------------:|----------:|----------:|--------:|
| GPT-4o mini | 58.0 | 62.0 | 78.7 | 78.1 | -0.6pp | 74.6 | 2,341,781 | 2,477,695 | +5.8% |
| Gemini 2.5 Flash | 74.0 | 74.0 | 73.6 | 74.1 | +0.5pp | 71.0 | 1,568,278 | 1,575,690 | +0.5% |
| DeepSeek V3.2 | 60.0 | 60.0 | 71.3 | 70.3 | -1.0pp | 69.1 | 7,792,210 | 7,493,360 | -3.8% |

### GPT-4o mini (N=10)

- P0 batch: `parallel_gpt_baseline_redo_jun13tier2v2_baseline_r10_gpt-4o-mini_r10_best_of_n.json`
- P1 batch: `parallel_p1_r10_bo_gpt-4o-mini_r10_best_of_n_p1_cache.json`
- Cache: **1,143** hits / **1,512** explore lookups (74.6% per-task mean)
- Explore redundancy: 78.7% → 78.1%

### Gemini 2.5 Flash (N=10)

- P0 batch: `parallel_20260611_123711_91299c_baseline_r10_gemini-2.5-flash_r10_best_of_n.json`
- P1 batch: `parallel_p1_r10_bo_gemini-2.5-flash_r10_best_of_n_p1_cache.json`
- Cache: **528** hits / **672** explore lookups (71.0% per-task mean)
- Explore redundancy: 73.6% → 74.1%

### DeepSeek V3.2 (N=10)

- P0 batch: `parallel_20260611_123747_60b677_baseline_r10_deepseek-v3.2_r10_best_of_n.json`
- P1 batch: `parallel_p1_r10_bo_deepseek-v3.2_r10_best_of_n_p1_cache.json`
- Cache: **1,940** hits / **3,102** explore lookups (69.1% per-task mean)
- Explore redundancy: 71.3% → 70.3%

## N=25

| Model | P0 EX % | P1 EX % | P0 red % | P1 red % | Red Δ | P1 cache hit % | P0 tokens | P1 tokens | Token Δ |
|-------|--------:|--------:|---------:|---------:|------:|---------------:|----------:|----------:|--------:|
| GPT-4o mini | 62.0 | 62.0 | 87.7 | 88.7 | +1.0pp | 84.2 | 6,322,822 | 6,364,118 | +0.7% |
| Gemini 2.5 Flash | 70.0 | 72.0† | 76.6 | 80.5 | +3.9pp | 78.1 | 3,685,459 | 3,765,559 | +2.2% |
| DeepSeek V3.2 | 64.0 | 62.0 | 82.9 | 82.0 | -0.9pp | 81.1 | 18,889,223 | 18,623,369 | -1.4% |

† Gemini 2.5 Flash P1 run: 1 API failure(s); EX on completed tasks = 73.5%.

### GPT-4o mini (N=25)

- P0 batch: `parallel_gpt_baseline_redo_jun13tier2v2_baseline_r25_gpt-4o-mini_r25_best_of_n.json`
- P1 batch: `parallel_p1_r25_bo_gpt-4o-mini_r25_best_of_n_p1_cache.json`
- Cache: **3,212** hits / **3,885** explore lookups (84.2% per-task mean)
- Explore redundancy: 87.7% → 88.7%

### Gemini 2.5 Flash (N=25)

- P0 batch: `parallel_20260611_123711_91299c_baseline_r25_gemini-2.5-flash_r25_best_of_n.json`
- P1 batch: `parallel_p1_r25_bo_gemini-2.5-flash_r25_best_of_n_p1_cache.json`
- Cache: **1,463** hits / **1,617** explore lookups (78.1% per-task mean)
- Explore redundancy: 76.6% → 80.5%

### DeepSeek V3.2 (N=25)

- P0 batch: `parallel_20260611_123747_60b677_baseline_r25_deepseek-v3.2_r25_best_of_n.json`
- P1 batch: `parallel_p1_r25_bo_deepseek-v3.2_r25_best_of_n_p1_cache.json`
- Cache: **5,775** hits / **7,706** explore lookups (81.1% per-task mean)
- Explore redundancy: 82.9% → 82.0%
