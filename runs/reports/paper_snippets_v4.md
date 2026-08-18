# Paper / essay paste snippets — draft_paper_ieee_v4

Generated from live batch JSON. Re-run `generate_robustness_pack.py` after wave4 before pasting. Edit lightly for tense/voice; do not invent numbers.

## Threats-to-validity / reflective essay (§4–5)

- Second independent seeds on full-500 P4 and composition move EX by roughly 0–1.4 pp with bootstrap CIs that include 0, so the single-run noise concern is bounded for those claims; smoke N=25 still shows few-task swings of several pp.
- Paired bootstrap 95% CIs are now available for headline full-500 and rep2-matched smoke comparisons (`bootstrap_ex_cis_v4.md`); accuracy-neutral policies are judged on token/DB CIs (`token_db_cis_v4.md`).
- Unconfound check: [Unconfound Gemini N=25] Gemini P3 vs P2 repair: n=48 Δ=-8.3 pp CI=[-16.7, -2.1]

## Results prose (full-500 stability)

- Full-500 P4 / GPT: EX 54.2→54.0 (Δ=-0.2 pp †), tokens +0.0%
- Full-500 compose / GPT: EX 53.6→54.0 (Δ=+0.4 pp †), tokens -0.7%
- Full-500 P3 stack / GPT: EX 53.2→52.8 (Δ=-0.4 pp †), tokens +6.8%
- Full-500 P4 / Gemini: EX 64.6→64.4 (Δ=-0.2 pp †), tokens +1.1%
- Full-500 compose / Gemini: EX 63.9→65.3 (Δ=+1.4 pp †), tokens -3.8%
- Full-500 P3 stack / Gemini: EX 63.9→63.3 (Δ=-0.8 pp †), tokens -1.7%
- Full-500 P4 / DeepSeek: EX 58.2→58.2 (Δ=+0.0 pp †), tokens +5.9%
- Full-500 compose / DeepSeek: EX 58.4→58.8 (Δ=+0.4 pp †), tokens -5.4%
- Full-500 P3 stack / DeepSeek: EX 57.0→58.9 (Δ=+1.8 pp †), tokens +2.1%

## Results prose (DeepSeek EX CIs — claim-worthy when CI excludes 0)

- [Full-500 N=3] DeepSeek P1 vs P0: n=498 Δ=+0.4 pp CI=[-1.6, +2.6] †
- [Full-500 N=3] DeepSeek prune vs P0: n=498 Δ=+0.0 pp CI=[-2.6, +2.4] †
- [Full-500 N=3] DeepSeek prompt-cache vs P0: n=498 Δ=-1.4 pp CI=[-3.6, +0.8] †
- [Full-500 N=3] DeepSeek P4 vs PC: n=498 Δ=+0.8 pp CI=[-1.8, +3.4] †
- [Full-500 N=3] DeepSeek P1+P4 vs P1: n=498 Δ=-0.8 pp CI=[-3.2, +1.6] †
- [Full-500 N=3] DeepSeek P3 stack vs P2 stack: n=498 Δ=-0.2 pp CI=[-2.8, +2.2] †
- [Full-500 N=3] DeepSeek compose vs P0: n=498 Δ=-0.4 pp CI=[-3.0, +2.2] †
- [Full-500 N=3 rep2] DeepSeek P4 rep2 vs PC: n=498 Δ=+0.8 pp CI=[-1.6, +3.2] †
- [Full-500 N=3 rep2] DeepSeek compose rep2 vs P0: n=498 Δ=+0.0 pp CI=[-2.6, +2.4] †
- [Full-500 N=3] DeepSeek P3 stack rep2 vs P2 stack: n=497 Δ=+1.6 pp CI=[-0.8, +4.0] †
- [Full-500 N=3 rep2] DeepSeek P3 stack rep2 vs P0: n=497 Δ=+0.0 pp CI=[-2.6, +2.6] †

## Results prose (token / DB ledgers — non-† only)

### Tokens

- [Full-500 tokens] GPT prune vs P0: n=498 tok/task Δ=-12.8% CI=[-20.3%, -4.5%]
- [Full-500 tokens] GPT P3 vs P2: n=498 tok/task Δ=-13.3% CI=[-18.7%, -7.4%]
- [Full-500 rep2 tokens] Gemini P4 rep2 vs PC: n=497 tok/task Δ=+2.9% CI=[+0.2%, +6.2%]
- [Full-500 rep2 tokens] Gemini compose rep2 vs P0: n=494 tok/task Δ=-9.0% CI=[-16.8%, -0.6%]
- [Full-500 tokens] DeepSeek prune vs P0: n=498 tok/task Δ=-16.6% CI=[-24.3%, -9.3%]
- [Full-500 tokens] DeepSeek P4 vs PC: n=498 tok/task Δ=+10.6% CI=[+2.5%, +19.8%]
- [Full-500 rep2 tokens] DeepSeek P4 rep2 vs PC: n=498 tok/task Δ=+17.1% CI=[+8.7%, +27.2%]

### DB interactions

- [Full-500 DB interactions] GPT P1 vs P0: n=498 db/task Δ=-31.7% CI=[-35.6%, -27.7%]
- [Full-500 DB interactions] GPT P4 vs PC: n=498 db/task Δ=-7.9% CI=[-12.3%, -3.4%]
- [Full-500 DB interactions] GPT compose vs P0: n=498 db/task Δ=-43.3% CI=[-47.0%, -39.4%]
- [Full-500 rep2 DB] GPT P4 rep2 vs PC: n=498 db/task Δ=-6.4% CI=[-9.9%, -2.9%]
- [Full-500 DB interactions] Gemini P1 vs P0: n=497 db/task Δ=-19.2% CI=[-20.8%, -17.5%]
- [Full-500 DB interactions] Gemini compose vs P0: n=497 db/task Δ=-32.1% CI=[-34.9%, -29.4%]

## One-paragraph methods addendum (optional)

For each headline comparison we report a paired bootstrap 95% confidence interval over matched `question_id`s (10 000 resamples, fixed seed). Where a second independent seed exists, we also report the rep2−rep1 EX delta with the same procedure. Accuracy-neutral middleware is additionally summarised with paired percentage changes on total tokens and `db_interactions`.

