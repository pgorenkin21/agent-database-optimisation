# Early Stop vs P0 Comparison

Generated: 2026-06-12T16:00:50.014161+00:00

Apples-to-apples: same model, replica count, and `best_of_n` policy. Only difference is `--early-stop` (P0_parallel vs P0_early_stop traces).

## Summary

| Model | P0 EX % | ES EX % | P0 redundancy % | ES redundancy % | P0 tokens | ES tokens | Token Δ | P0 overhead | ES overhead | ES triggered |
|-------|--------:|--------:|----------------:|----------------:|----------:|----------:|--------:|------------:|------------:|-------------:|
| GPT-4o mini | 58.0 | 60.0 | 78.5 | 77.8 | 2,400,807 | 2,432,022 | +1.3% | 10.53× | 9.94× | 30/50 |
| Gemini 2.5 Flash | 74.0 | 74.0 | 73.6 | 73.6 | 1,568,278 | 1,529,204 | -2.5% | 10.54× | 10.28× | 37/50 |
| DeepSeek V3.2 | 60.0 | 60.0 | 71.3 | 75.0 | 7,792,210 | 6,676,709 | -14.3% | 13.38× | 10.72× | 30/50 |

## GPT-4o mini

- P0 batch: `parallel_20260611_123556_a3baef_baseline_r10_gpt-4o-mini_r10_best_of_n.json`
- Early stop batch: `parallel_earlystop_r10_bo_gpt-4o-mini_r10_best_of_n_early_stop.json`
- Early stop triggered: **30/50** tasks
- Avg replicas cancelled: **5.08** per task

- Avg tokens/task when triggered: **36,137** (vs **67,396** when not triggered)

## Gemini 2.5 Flash

- P0 batch: `parallel_20260611_123711_91299c_baseline_r10_gemini-2.5-flash_r10_best_of_n.json`
- Early stop batch: `parallel_earlystop_r10_bo_gemini-2.5-flash_r10_best_of_n_early_stop.json`
- Early stop triggered: **37/50** tasks
- Avg replicas cancelled: **6.02** per task

- Avg tokens/task when triggered: **31,355** (vs **28,390** when not triggered)

## DeepSeek V3.2

- P0 batch: `parallel_20260611_123747_60b677_baseline_r10_deepseek-v3.2_r10_best_of_n.json`
- Early stop batch: `parallel_earlystop_r10_bo_deepseek-v3.2_r10_best_of_n_early_stop.json`
- Early stop triggered: **30/50** tasks
- Avg replicas cancelled: **5.14** per task

- Avg tokens/task when triggered: **99,846** (vs **184,066** when not triggered)
