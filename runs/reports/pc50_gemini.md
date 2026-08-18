# Prompt Cache (Idea 1) vs Baseline

Generated: 2026-06-24T13:51:52.952862+00:00

- Baseline batch: `parallel_pc50_gem_base_gemini-2.5-flash_r3_best_of_n.json`
- Cached batch:   `parallel_pc50_gem_cached_gemini-2.5-flash_r3_best_of_n_promptcache.json`
- Matched tasks (no API error in either): **17**
- Cache discount applied to cached input tokens: **0.50** (cached billed at 50%)

| Metric | Baseline | Prompt cache | Δ |
|--------|---------:|-------------:|---:|
| EX accuracy | 64.7% | 64.7% | +0.0pp |
| Input tokens (raw) | 121,130 | 119,251 | -1.6% |
| Cached input tokens | — | 64,892 (54.4%) | — |
| **Effective billed input** | 121,130 | 86,805 | -28.3% |
| Completion tokens | 5,434 | 5,268 | — |

**Trajectory-controlled caching saving (within the cached run): −27.2% billed input.** This isolates the cache benefit from cross-run turn-count divergence.

**Read:** prefer the trajectory-controlled line above as the headline. The cross-run *effective billed input* row also reflects trajectory differences (turn counts) between the two independent runs, which dominate on small or low-EX samples; the EX Δ confirms accuracy is unchanged.
