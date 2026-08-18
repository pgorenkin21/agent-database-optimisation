# Prompt Cache (Idea 1) vs Baseline

Generated: 2026-06-24T12:53:48.948891+00:00

- Baseline batch: `parallel_pc50_ds_base_deepseek-v3.2_r3_best_of_n.json`
- Cached batch:   `parallel_pc50_ds_cached_deepseek-v3.2_r3_best_of_n_promptcache.json`
- Matched tasks (no API error in either): **50**
- Cache discount applied to cached input tokens: **0.50** (cached billed at 50%)

| Metric | Baseline | Prompt cache | Δ |
|--------|---------:|-------------:|---:|
| EX accuracy | 60.0% | 56.0% | -4.0pp |
| Input tokens (raw) | 2,024,527 | 2,103,131 | +3.9% |
| Cached input tokens | — | 1,985,664 (94.4%) | — |
| **Effective billed input** | 2,024,527 | 1,110,299 | -45.2% |
| Completion tokens | 114,897 | 120,007 | — |

**Trajectory-controlled caching saving (within the cached run): −47.2% billed input.** This isolates the cache benefit from cross-run turn-count divergence.

**Read:** prefer the trajectory-controlled line above as the headline. The cross-run *effective billed input* row also reflects trajectory differences (turn counts) between the two independent runs, which dominate on small or low-EX samples; the EX Δ confirms accuracy is unchanged.
