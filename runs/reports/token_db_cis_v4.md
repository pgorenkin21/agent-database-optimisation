# Token / DB paired bootstrap CIs — draft_paper_ieee_v4

Paired % change over matched question_ids (n_boot=10000, seed=42).
Δ% = 100 × (Σ_treat − Σ_ctrl) / Σ_ctrl on the matched set.
† = 95% CI includes 0.

Use these for accuracy-neutral policies (P1, prune, PC, P4) where EX CIs are expected to include 0.

## Full-500 tokens

| Comparison | n | Treat mean | Ctrl mean | Δ% | 95% CI |
|---|---:|---:|---:|---:|---|
| GPT prune vs P0 | 498 | 26409.6 | 30298.5 | -12.8% | [-20.3%, -4.5%] |
| GPT PC vs P0 | 498 | 30293.1 | 30298.5 | -0.0% † | [-5.3%, +5.5%] |
| GPT P4 vs PC | 498 | 29320.2 | 30293.1 | -3.2% † | [-8.9%, +2.9%] |
| GPT compose vs P0 | 498 | 30103.0 | 30298.5 | -0.6% † | [-9.9%, +9.3%] |
| GPT P3 vs P2 | 498 | 21401.3 | 24676.4 | -13.3% | [-18.7%, -7.4%] |
| Gemini prune vs P0 | 494 | 17451.5 | 18146.4 | -3.8% † | [-12.0%, +5.3%] |
| Gemini PC vs P0 | 497 | 18158.2 | 18245.4 | -0.5% † | [-2.7%, +1.5%] |
| Gemini P4 vs PC | 497 | 18442.9 | 18158.2 | +1.6% † | [-0.8%, +4.4%] |
| Gemini compose vs P0 | 497 | 17188.1 | 18245.4 | -5.8% † | [-13.8%, +2.8%] |
| Gemini P3 vs P2 | 496 | 16860.5 | 16142.6 | +4.4% † | [-0.2%, +9.1%] |
| DeepSeek prune vs P0 | 498 | 41669.6 | 49976.7 | -16.6% | [-24.3%, -9.3%] |
| DeepSeek PC vs P0 | 498 | 48877.8 | 49976.7 | -2.2% † | [-10.8%, +5.8%] |
| DeepSeek P4 vs PC | 498 | 54055.0 | 48877.8 | +10.6% | [+2.5%, +19.8%] |
| DeepSeek compose vs P0 | 498 | 51525.9 | 49976.7 | +3.1% † | [-6.6%, +12.9%] |
| DeepSeek P3 vs P2 | 498 | 45705.4 | 44896.0 | +1.8% † | [-5.7%, +10.1%] |

## Full-500 DB interactions

| Comparison | n | Treat mean | Ctrl mean | Δ% | 95% CI |
|---|---:|---:|---:|---:|---|
| GPT P1 vs P0 | 498 | 8.2 | 12.0 | -31.7% | [-35.6%, -27.7%] |
| GPT P4 vs PC | 498 | 11.2 | 12.1 | -7.9% | [-12.3%, -3.4%] |
| GPT compose vs P0 | 498 | 6.8 | 12.0 | -43.3% | [-47.0%, -39.4%] |
| Gemini P1 vs P0 | 497 | 5.4 | 6.7 | -19.2% | [-20.8%, -17.5%] |
| Gemini P4 vs PC | 497 | 6.6 | 6.6 | +0.0% † | [-1.5%, +1.7%] |
| Gemini compose vs P0 | 497 | 4.5 | 6.7 | -32.1% | [-34.9%, -29.4%] |
| DeepSeek P1 vs P0 | 498 | 13.7 | 15.0 | -8.4% | [-10.8%, -5.9%] |
| DeepSeek P4 vs PC | 498 | 13.3 | 14.8 | -10.1% | [-13.1%, -7.0%] |
| DeepSeek compose vs P0 | 498 | 10.7 | 15.0 | -28.6% | [-31.7%, -25.4%] |

## Full-500 rep2 tokens

| Comparison | n | Treat mean | Ctrl mean | Δ% | 95% CI |
|---|---:|---:|---:|---:|---|
| GPT P4 rep2 vs PC | 498 | 29331.8 | 30293.1 | -3.2% † | [-8.1%, +2.0%] |
| GPT compose rep2 vs P0 | 498 | 29902.6 | 30298.5 | -1.3% † | [-9.7%, +8.0%] |
| Gemini P4 rep2 vs PC | 497 | 18684.5 | 18158.2 | +2.9% | [+0.2%, +6.2%] |
| Gemini compose rep2 vs P0 | 494 | 16640.7 | 18287.0 | -9.0% | [-16.8%, -0.6%] |
| DeepSeek P4 rep2 vs PC | 498 | 57258.1 | 48877.8 | +17.1% | [+8.7%, +27.2%] |
| DeepSeek compose rep2 vs P0 | 498 | 48753.0 | 49976.7 | -2.4% † | [-11.4%, +6.2%] |

## Full-500 rep2 DB

| Comparison | n | Treat mean | Ctrl mean | Δ% | 95% CI |
|---|---:|---:|---:|---:|---|
| GPT P4 rep2 vs PC | 498 | 11.3 | 12.1 | -6.4% | [-9.9%, -2.9%] |
| Gemini P4 rep2 vs PC | 497 | 6.6 | 6.6 | -0.1% † | [-1.5%, +1.2%] |
| DeepSeek P4 rep2 vs PC | 498 | 13.3 | 14.8 | -10.0% | [-12.7%, -7.0%] |

