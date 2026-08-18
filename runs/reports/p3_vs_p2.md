# P3 Semantic Store Comparison

Generated: 2026-06-19T14:18:17.441356+00:00

**P3 stack:** P1 cache + P3 semantic fact store + early stop + hybrid schema prune (`--semantic-store --shared-cache --early-stop --schema-pruning --schema-pruning-mode hybrid`).

**P2 baseline:** full stack + schema prune (P1 + P2 discovery board + early stop + schema prune).

50-task BIRD mini-dev smoke subset; `best_of_n` at N=10 unless noted.

## N=10: P3 vs P2 full stack+prune

| Model | P2 EX % | P3 EX % | EX Δ | P2 tokens | P3 tokens | Token Δ | Semantic inj/task | Recommendation |
|-------|--------:|--------:|-----:|----------:|----------:|--------:|----------------:|----------------|
| GPT-4o mini | 56.0 | 60.0 | +4.0pp | 1,847,079 | 1,726,234 | -6.5% | 18.8 | **Adopt P3** |
| Gemini 2.5 Flash | 76.0 | 70.0 | -6.0pp | 1,124,009 | 1,121,670 | -0.2% | 9.8 | **Mixed** |
| DeepSeek V3.2 | 64.0 | 60.0 | -4.0pp | 5,251,285 | 7,482,194 | +42.5% | 55.9 | **Avoid P3** (use P2 full stack+prune) |

### Recommendations

- **GPT-4o mini:** **Adopt P3** — EX +4 pp and tokens -6.5% vs P2 full stack+prune.
- **Gemini 2.5 Flash:** **Mixed** — EX -6 pp; consider P2+P3 combined or P2 alone.
- **DeepSeek V3.2:** **Avoid P3** (use P2 full stack+prune) — EX -4 pp and tokens +42.5% — prefer P2 full stack+prune.

### Thesis summary (N=10)

- **Adopt P3 for:** GPT-4o mini
- **Prefer P2 full stack+prune for:** DeepSeek V3.2
- **Mixed / further work:** Gemini 2.5 Flash

### GPT-4o mini (N=10)

- P2 batch: `parallel_fullstack_prune_r10_bo_gpt-4o-mini_r10_best_of_n_p1_cache_p2_discovery_early_stop_schema_prune.json`
- P3 batch: `parallel_semantic_hybrid_r10_bo_gpt-4o-mini_r10_best_of_n_p1_cache_p3_semantic_early_stop_schema_prune.json`
- Cache hit (P3): 72.1%
- Semantic: 14.2 facts/task, 18.8 injections/task
- Middleware interaction (P3): 75.8%

### Gemini 2.5 Flash (N=10)

- P2 batch: `parallel_fullstack_prune_r10_bo_gemini-2.5-flash_r10_best_of_n_p1_cache_p2_discovery_early_stop_schema_prune.json`
- P3 batch: `parallel_semantic_hybrid_r10_bo_gemini-2.5-flash_r10_best_of_n_p1_cache_p3_semantic_early_stop_schema_prune.json`
- Cache hit (P3): 59.4%
- Semantic: 8.1 facts/task, 9.8 injections/task
- Middleware interaction (P3): 60.5%

### DeepSeek V3.2 (N=10)

- P2 batch: `parallel_fullstack_prune_r10_bo_deepseek-v3.2_r10_best_of_n_p1_cache_p2_discovery_early_stop_schema_prune.json`
- P3 batch: `parallel_semantic_hybrid_r10_bo_deepseek-v3.2_r10_best_of_n_p1_cache_p3_semantic_early_stop_schema_prune.json`
- Cache hit (P3): 69.4%
- Semantic: 61.4 facts/task, 55.9 injections/task
- Middleware interaction (P3): 79.9%

## P2+P3 combined (discovery + semantic store)

### N=10

| Model | P2+prune EX | P3 only EX | P2+P3 EX | P2+P3 tokens | Δ vs P2 | Δ vs P3 |
|-------|----------:|-----------:|---------:|-------------:|--------:|--------:|
| Gemini 2.5 Flash | 76.0 | 70.0 | 74.0 | 1,143,254 | +1.7% | +1.9% |
| DeepSeek V3.2 | 64.0 | 60.0 | 66.0 | 6,864,235 | +30.7% | -8.3% |

- **Gemini 2.5 Flash:** P2+P3 EX **74.0%** (-2 pp vs P2+prune); tokens +1.7% vs P2+prune.
- **DeepSeek V3.2:** P2+P3 EX **66.0%** (+2 pp vs P2+prune); tokens +30.7% vs P2+prune.

## P3 vs P0 baseline

### N=10

| Model | P0 EX % | P3 EX % | P0 tokens | P3 tokens | Token Δ vs P0 |
|-------|--------:|--------:|----------:|----------:|--------------:|
| GPT-4o mini | 58.0 | 60.0 | 2,341,781 | 1,726,234 | -26.3% |
| Gemini 2.5 Flash | 74.0 | 70.0 | 1,568,278 | 1,121,670 | -28.5% |
| DeepSeek V3.2 | 60.0 | 60.0 | 7,792,210 | 7,482,194 | -4.0% |
