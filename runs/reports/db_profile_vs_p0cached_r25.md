# DB Profile (Chapter 12): P0_cached vs +db-profile

Generated: 2026-07-02T10:10:37.687746+00:00

Apples-to-apples: same model, replica count, `best_of_n`, both under `--prompt-cache`. Only difference is `--db-profile` (the DB Profile Card).

## Summary

| Model | EX base % | EX +DPC % | EX Δ | Explore/task base | Explore/task +DPC | Explore Δ | Explore Δ% | Value-dom Δ | Join Δ | Token Δ | Traces |
|-------|----------:|----------:|-----:|------------------:|------------------:|----------:|-----------:|------------:|-------:|--------:|-------:|
| GPT-4o mini | 60.0 | 62.0 | +2.0pp | 72.80 | 66.20 | -6.60 | -9.1% | +1.26 | -3.60 | +13.1% | 50/50 |
| Gemini 2.5 Flash | 74.0 | 78.0 | +4.0pp | 32.84 | 31.48 | -1.36 | -4.1% | -4.22 | +3.04 | +34.1% | 50/50 |
| DeepSeek V3.2 | 62.0 | 58.0 | -4.0pp | 155.88 | 137.34 | -18.54 | -11.9% | +0.68 | +0.30 | +7.8% | 50/50 |

## GPT-4o mini

- Baseline batch: `parallel_dbprofile_base_r25_bo_gpt-4o-mini_r25_best_of_n_promptcache.json`
- +db-profile batch: `parallel_dbprofile_iso_r25_bo_gpt-4o-mini_r25_best_of_n_promptcache_dbprofile.json`
- Explore-trace coverage (+DPC): **50/50** tasks

## Gemini 2.5 Flash

- Baseline batch: `parallel_dbprofile_base_r25_bo_gemini-2.5-flash_r25_best_of_n_promptcache.json`
- +db-profile batch: `parallel_dbprofile_iso_r25_bo_gemini-2.5-flash_r25_best_of_n_promptcache_dbprofile.json`
- Explore-trace coverage (+DPC): **50/50** tasks

## DeepSeek V3.2

- Baseline batch: `parallel_dbprofile_base_r25_bo_deepseek-v3.2_r25_best_of_n_promptcache.json`
- +db-profile batch: `parallel_dbprofile_iso_r25_bo_deepseek-v3.2_r25_best_of_n_promptcache_dbprofile.json`
- Explore-trace coverage (+DPC): **50/50** tasks
