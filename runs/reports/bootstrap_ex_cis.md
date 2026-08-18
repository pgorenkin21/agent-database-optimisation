# Bootstrap 95% CIs on EX% (paired, task-matched)

n_boot=10000, seed=42. Diff = treatment − control (percentage points).

| Comparison | n | Treat EX% | Ctrl EX% | Δ pp | 95% CI |
|---|---:|---:|---:|---:|---|
| Gemini t03_stag2s vs P2+prune | 50 | 82.0 | 76.0 | +6.0 | [+0.0, +14.0] |
| GPT P3 vs P2+prune | 50 | 60.0 | 56.0 | +4.0 | [-4.0, +12.0] |
| DeepSeek P2+prune vs P3 | 50 | 64.0 | 60.0 | +4.0 | [+0.0, +10.0] |
| Gemini schedule+P2 vs schedule-only | 50 | 80.0 | 82.0 | -2.0 | [-6.0, +0.0] |

*Paired bootstrap resamples matched question_ids with replacement. CI is percentile interval on mean EX difference (pp).*
