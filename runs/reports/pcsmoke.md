# Prompt Cache (Idea 1) vs Baseline

Generated: 2026-06-24T11:55:33.576324+00:00

- Baseline batch: `parallel_pcsmoke_base_gpt-4o-mini_r3_best_of_n.json`
- Cached batch:   `parallel_pcsmoke_cached_gpt-4o-mini_r3_best_of_n_promptcache.json`
- Matched tasks (no API error in either): **3**
- Cache discount applied to cached input tokens: **0.50** (cached billed at 50%)

| Metric | Baseline | Prompt cache | Δ |
|--------|---------:|-------------:|---:|
| EX accuracy | 33.3% | 33.3% | +0.0pp |
| Input tokens (raw) | 62,116 | 91,596 | +47.5% |
| Cached input tokens | — | 50,944 (55.6%) | — |
| **Effective billed input** | 62,116 | 66,124 | +6.5% |
| Completion tokens | 2,356 | 3,304 | — |

**Trajectory-controlled caching saving (within the cached run): −27.8% billed input.** This isolates the cache benefit from cross-run turn-count divergence.

**Read:** prefer the trajectory-controlled line above as the headline. The cross-run *effective billed input* row also reflects trajectory differences (turn counts) between the two independent runs, which dominate on small or low-EX samples; the EX Δ confirms accuracy is unchanged.
