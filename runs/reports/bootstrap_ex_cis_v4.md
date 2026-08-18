# Bootstrap 95% CIs — draft_paper_ieee_v4 headlines

n_boot=10000, seed=42. Diff = treatment − control (pp EX).
† = 95% CI includes 0 (EX delta not distinguishable from noise on this sample).

## Full-500 N=3

| Comparison | n | Treat EX% | Ctrl EX% | Δ pp | 95% CI |
|---|---:|---:|---:|---:|---|
| GPT P1 vs P0 | 498 | 55.4 | 52.6 | +2.8 | [+0.6, +5.2] |
| GPT prune vs P0 | 498 | 52.8 | 52.6 | +0.2 † | [-3.0, +3.4] |
| GPT prompt-cache vs P0 | 498 | 53.4 | 52.6 | +0.8 † | [-1.2, +3.0] |
| Gemini P1 vs P0 | 497 | 66.0 | 64.6 | +1.4 † | [-0.2, +3.2] |
| Gemini prune vs P0 | 494 | 63.2 | 64.4 | -1.2 † | [-3.8, +1.4] |
| Gemini prompt-cache vs P0 | 497 | 64.8 | 64.6 | +0.2 † | [-1.0, +1.4] |
| DeepSeek P1 vs P0 | 498 | 59.0 | 58.6 | +0.4 † | [-1.6, +2.6] |
| DeepSeek prune vs P0 | 498 | 58.6 | 58.6 | +0.0 † | [-2.6, +2.4] |
| DeepSeek prompt-cache vs P0 | 498 | 57.2 | 58.6 | -1.4 † | [-3.6, +0.8] |

## Smoke N=25

| Comparison | n | Treat EX% | Ctrl EX% | Δ pp | 95% CI |
|---|---:|---:|---:|---:|---|
| GPT P1 vs P0 | 50 | 62.0 | 62.0 | +0.0 † | [-6.0, +6.0] |
| GPT prune vs P0 | 50 | 60.0 | 62.0 | -2.0 † | [-10.0, +4.0] |
| Gemini P1 vs P0 | 46 | 73.9 | 73.9 | +0.0 † | [+0.0, +0.0] |
| Gemini prune vs P0 | 47 | 74.5 | 74.5 | +0.0 † | [-6.4, +6.4] |
| DeepSeek P1 vs P0 | 47 | 74.5 | 72.3 | +2.1 † | [+0.0, +6.4] |
| DeepSeek prune vs P0 | 49 | 69.4 | 69.4 | +0.0 † | [-6.1, +6.1] |
| GPT prompt-cache vs base | 49 | 63.3 | 59.2 | +4.1 † | [+0.0, +10.2] |
| Gemini prompt-cache vs base | 48 | 77.1 | 75.0 | +2.1 † | [+0.0, +6.2] |
| DeepSeek prompt-cache vs base | 50 | 68.0 | 68.0 | +0.0 † | [+0.0, +0.0] |
| GPT P4 vs PC-base | 50 | 62.0 | 58.0 | +4.0 † | [+0.0, +10.0] |
| GPT P1+P4 vs P1+PC | 50 | 60.0 | 62.0 | -2.0 † | [-6.0, +0.0] |
| Gemini P4 vs PC-base | 50 | 74.0 | 74.0 | +0.0 † | [-6.0, +6.0] |
| Gemini P1+P4 vs P1+PC | 48 | 79.2 | 79.2 | +0.0 † | [+0.0, +0.0] |
| DeepSeek P4 vs PC-base | — | — | — | — | missing ctrl |
| DeepSeek P1+P4 vs P1+PC | — | — | — | — | missing ctrl |

## Smoke N=10

| Comparison | n | Treat EX% | Ctrl EX% | Δ pp | 95% CI |
|---|---:|---:|---:|---:|---|
| GPT P3 stack vs P2 stack | 50 | 60.0 | 56.0 | +4.0 † | [-4.0, +12.0] |
| Gemini P3 stack vs P2 stack | 50 | 70.0 | 76.0 | -6.0 † | [-16.0, +4.0] |
| DeepSeek P3 stack vs P2 stack | 47 | 70.2 | 68.1 | +2.1 † | [-4.3, +10.6] |

## Full-500 N=3 (new)

| Comparison | n | Treat EX% | Ctrl EX% | Δ pp | 95% CI |
|---|---:|---:|---:|---:|---|
| GPT P4 vs PC | 498 | 54.0 | 53.4 | +0.6 † | [-1.6, +2.8] |
| GPT P1+P4 vs P1 | 498 | 55.2 | 55.4 | -0.2 † | [-2.4, +2.0] |
| GPT P3 stack vs P2 stack | 498 | 53.0 | 52.2 | +0.8 † | [-1.6, +3.2] |
| GPT P3 stack vs P0 | 498 | 53.0 | 52.6 | +0.4 † | [-2.8, +3.8] |
| Gemini P4 vs PC | 497 | 64.6 | 64.8 | -0.2 † | [-1.6, +1.2] |
| Gemini P1+P4 vs P1 | 462 | 67.1 | 66.9 | +0.2 † | [-1.5, +1.9] |
| Gemini P3 stack vs P2 stack | 496 | 63.7 | 65.5 | -1.8 † | [-4.2, +0.4] |
| Gemini P3 stack vs P0 | 496 | 63.9 | 64.5 | -0.6 † | [-3.4, +2.2] |
| DeepSeek P4 vs PC | 498 | 58.0 | 57.2 | +0.8 † | [-1.8, +3.4] |
| DeepSeek P1+P4 vs P1 | 498 | 58.2 | 59.0 | -0.8 † | [-3.2, +1.6] |
| DeepSeek P3 stack vs P2 stack | 498 | 56.8 | 57.0 | -0.2 † | [-2.8, +2.2] |
| DeepSeek P3 stack vs P0 | 498 | 56.8 | 58.6 | -1.8 † | [-4.6, +1.0] |

## Full-500 N=3 (compose)

| Comparison | n | Treat EX% | Ctrl EX% | Δ pp | 95% CI |
|---|---:|---:|---:|---:|---|
| GPT compose vs P0 | 498 | 53.4 | 52.6 | +0.8 † | [-2.2, +3.8] |
| GPT compose vs P1+P4 | 498 | 53.4 | 55.2 | -1.8 † | [-4.8, +1.2] |
| Gemini compose vs P0 | 497 | 63.8 | 64.6 | -0.8 † | [-3.4, +1.8] |
| Gemini compose vs P1+P4 | 462 | 64.7 | 67.1 | -2.4 † | [-5.2, +0.4] |
| DeepSeek compose vs P0 | 498 | 58.2 | 58.6 | -0.4 † | [-3.0, +2.2] |
| DeepSeek compose vs P1+P4 | 498 | 58.2 | 58.2 | +0.0 † | [-2.6, +2.6] |
| GPT compose+P3 vs compose | 498 | 53.0 | 53.4 | -0.4 † | [-2.8, +2.0] |

*Paired bootstrap over matched question_ids. Accuracy-neutral policies are *expected* to show † on EX; use token/DB metrics for those claims. Full-500 rows are the strongest generalisation evidence currently on disk; P3/P4 still lack full-500 counterparts.*
