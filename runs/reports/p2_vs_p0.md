# P2 Discovery Board vs P0 Comparison

Generated: 2026-06-17T15:41:14.043784+00:00

Apples-to-apples: same model, replica count, and `best_of_n` policy. P2 adds `--discovery-board` (shared sub-expression propagation via prompt injection). Early-stop variants are excluded.

## N=10

| Model | P0 EX % | P2 EX % | P0 red % | P2 red % | Red Δ | P2 frags/task | P0 tokens | P2 tokens | Token Δ |
|-------|--------:|--------:|---------:|---------:|------:|-------------:|----------:|----------:|--------:|
| GPT-4o mini | 58.0 | 58.0 | 78.7 | 79.3 | +0.6pp | 14.6 | 2,341,781 | 2,565,800 | +9.6% |
| Gemini 2.5 Flash | 74.0 | 76.0 | 73.6 | 66.9 | -6.7pp | 10.3 | 1,568,278 | 1,743,769 | +11.2% |
| DeepSeek V3.2 | 60.0 | 62.0 | 71.3 | 75.4 | +4.1pp | 18.3 | 7,792,210 | 6,428,179 | -17.5% |

### GPT-4o mini (N=10)

- P0 batch: `parallel_gpt_baseline_redo_jun13tier2v2_baseline_r10_gpt-4o-mini_r10_best_of_n.json`
- P2 batch: `parallel_p2_r10_bo_gpt-4o-mini_r10_best_of_n_p2_discovery.json`
- Discovery: **14.6** fragments/task mean, **20.5** context injections/task
- Explore redundancy: 78.7% → 79.3%

### Gemini 2.5 Flash (N=10)

- P0 batch: `parallel_20260611_123711_91299c_baseline_r10_gemini-2.5-flash_r10_best_of_n.json`
- P2 batch: `parallel_p2_r10_bo_gemini-2.5-flash_r10_best_of_n_p2_discovery.json`
- Discovery: **10.3** fragments/task mean, **10.5** context injections/task
- Explore redundancy: 73.6% → 66.9%

### DeepSeek V3.2 (N=10)

- P0 batch: `parallel_20260611_123747_60b677_baseline_r10_deepseek-v3.2_r10_best_of_n.json`
- P2 batch: `parallel_p2_r10_bo_deepseek-v3.2_r10_best_of_n_p2_discovery.json`
- Discovery: **18.3** fragments/task mean, **36.9** context injections/task
- Explore redundancy: 71.3% → 75.4%

## N=25

| Model | P0 EX % | P2 EX % | P0 red % | P2 red % | Red Δ | P2 frags/task | P0 tokens | P2 tokens | Token Δ |
|-------|--------:|--------:|---------:|---------:|------:|-------------:|----------:|----------:|--------:|
| GPT-4o mini | 62.0 | 56.0 | 87.7 | 87.3 | -0.4pp | 16.7 | 6,322,822 | 6,703,656 | +6.0% |
| Gemini 2.5 Flash | 70.0 | 76.0 | 76.6 | 75.3 | -1.3pp | 10.5 | 3,685,459 | 4,275,557 | +16.0% |
| DeepSeek V3.2 | 64.0 | 62.0 | 82.9 | 84.0 | +1.1pp | 23.5 | 18,889,223 | 16,328,864 | -13.6% |

### GPT-4o mini (N=25)

- P0 batch: `parallel_gpt_baseline_redo_jun13tier2v2_baseline_r25_gpt-4o-mini_r25_best_of_n.json`
- P2 batch: `parallel_p2_r25_bo_gpt-4o-mini_r25_best_of_n_p2_discovery.json`
- Discovery: **16.7** fragments/task mean, **55.1** context injections/task
- Explore redundancy: 87.7% → 87.3%

### Gemini 2.5 Flash (N=25)

- P0 batch: `parallel_20260611_123711_91299c_baseline_r25_gemini-2.5-flash_r25_best_of_n.json`
- P2 batch: `parallel_p2_r25_bo_gemini-2.5-flash_r25_best_of_n_p2_discovery.json`
- Discovery: **10.5** fragments/task mean, **26.3** context injections/task
- Explore redundancy: 76.6% → 75.3%

### DeepSeek V3.2 (N=25)

- P0 batch: `parallel_20260611_123747_60b677_baseline_r25_deepseek-v3.2_r25_best_of_n.json`
- P2 batch: `parallel_p2_r25_bo_deepseek-v3.2_r25_best_of_n_p2_discovery.json`
- Discovery: **23.5** fragments/task mean, **95.3** context injections/task
- Explore redundancy: 82.9% → 84.0%
