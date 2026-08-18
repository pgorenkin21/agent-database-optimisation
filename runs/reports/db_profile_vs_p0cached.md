# DB Profile (Chapter 12): P0_cached vs +db-profile

Generated: 2026-07-01T15:47:04.355060+00:00

Apples-to-apples: same model, replica count, `best_of_n`, both under `--prompt-cache`. Only difference is `--db-profile` (the DB Profile Card).

## Summary

| Model | EX base % | EX +DPC % | EX Δ | Explore/task base | Explore/task +DPC | Explore Δ | Explore Δ% | Value-dom Δ | Join Δ | Token Δ | Traces |
|-------|----------:|----------:|-----:|------------------:|------------------:|----------:|-----------:|------------:|-------:|--------:|-------:|
| GPT-4o mini | 54.0 | 60.0 | +6.0pp | 25.39 | 25.98 | +0.59 | +2.3% | -0.03 | +1.46 | +42.0% | 50/50 |
| Gemini 2.5 Flash | 72.0 | 78.0 | +6.0pp | 13.16 | 12.56 | -0.60 | -4.6% | -1.56 | +1.24 | +32.9% | 50/50 |
| DeepSeek V3.2 | 60.0 | 60.0 | 0.0pp | 62.12 | 56.04 | -6.08 | -9.8% | +3.08 | +0.42 | +11.3% | 50/50 |

## GPT-4o mini

- Baseline batch: `parallel_dbprofile_base_r10_bo_gpt-4o-mini_r10_best_of_n_promptcache.json`
- +db-profile batch: `parallel_dbprofile_iso_r10_bo_gpt-4o-mini_r10_best_of_n_promptcache_dbprofile.json`
- Explore-trace coverage (+DPC): **50/50** tasks

## Gemini 2.5 Flash

- Baseline batch: `parallel_dbprofile_base_r10_bo_gemini-2.5-flash_r10_best_of_n_promptcache.json`
- +db-profile batch: `parallel_dbprofile_iso_r10_bo_gemini-2.5-flash_r10_best_of_n_promptcache_dbprofile.json`
- Explore-trace coverage (+DPC): **50/50** tasks

## DeepSeek V3.2

- Baseline batch: `parallel_dbprofile_base_r10_bo_deepseek-v3.2_r10_best_of_n_promptcache.json`
- +db-profile batch: `parallel_dbprofile_iso_r10_bo_deepseek-v3.2_r10_best_of_n_promptcache_dbprofile.json`
- Explore-trace coverage (+DPC): **50/50** tasks
