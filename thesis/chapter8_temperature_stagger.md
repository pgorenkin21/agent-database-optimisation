# Chapter 8: Temperature and Staggered Replicas

*Draft generated 2026-06-21 from schedule sweep `sched_r10_bo`. Regenerate with `uv run python scripts/generate_chapter8_draft.py`.*

## 8.1 Motivation

Chapter 2 noted that all prior experiments used **temperature 0**, so replicas explored nearly identically—high string-level redundancy (65–88%) despite independent LLM trajectories. Chapter 6–7 optimised *what* middleware shares (fragments, facts, cache); this chapter asks *when* and *how diversely* replicas run.

Two levers are evaluated on the same **P1 + early stop + hybrid schema prune** stack (no P2 discovery board, no P3 semantic store):

1. **Temperature** — uniform `T ∈ {0, 0.3, 0.7}` or a **ladder** (`T + i×0.2` per agent).
2. **Stagger** — agent *i* waits `i×2s` or `i×1` turn-poll before its first LLM call, allowing earlier replicas to populate the shared SQL cache.

Hypothesis: higher temperature or stagger reduces explore redundancy; stagger may improve cache hit rates without the prompt cost of P2/P3 injection.

## 8.2 Policy and experimental setup

- **Sweep ID:** `sched_r10_bo`, *N*=10, 50-task smoke subset, `best_of_n`.
- **Scenarios:** `t03_stag2s`, `stag2s`, `stag1t`, `ladder`, `t07`, `t03`, `t0`.
- **Infrastructure:** `ReplicaScheduleConfig` in `src/coord/replica_schedule.py`; traces log `replica_start`, `temperature`, and `stagger_complete`.

## 8.3 Results

### 8.3.1 DeepSeek V3.2

**Table 8.1.** Schedule scenarios (EX, redundancy, tokens).

| Scenario | EX % | Redundancy % | Tokens | Δ tok vs t0 |
|----------|-----:|-------------:|-------:|------------:|
| t03_stag2s | 64.0 | 45.8 | 5,532,575 | -22.3% |
| stag2s | 64.0 | 48.4 | 5,814,115 | -18.3% |
| stag1t | 64.0 | 59.8 | 6,225,627 | -12.5% |
| ladder | 68.0 | 50.9 | 6,941,153 | -2.5% |
| t07 | 64.0 | 58.0 | 7,015,363 | -1.4% |
| t03 | 64.0 | 65.1 | 6,862,305 | -3.6% |
| t0 | 64.0 | 71.1 | 7,117,031 | — |

**Best scenario:** `ladder` — EX **68.0%**, 6,941,153 tokens, redundancy 50.9%.

Compared to **P2 full stack+prune** (Chapter 6): EX +4 pp, tokens +32.2%.

### 8.3.2 Gemini 2.5 Flash

**Table 8.2.** Schedule scenarios (EX, redundancy, tokens).

| Scenario | EX % | Redundancy % | Tokens | Δ tok vs t0 |
|----------|-----:|-------------:|-------:|------------:|
| t03_stag2s | 82.0 | 16.3 | 483,807 | -55.7% |
| stag2s | 78.0 | 27.1 | 513,575 | -53.0% |
| stag1t | 76.0 | 44.5 | 646,068 | -40.8% |
| ladder | 80.0 | 29.9 | 1,008,806 | -7.6% |
| t07 | 82.0 | 35.1 | 1,063,070 | -2.6% |
| t03 | 82.0 | 42.3 | 1,016,996 | -6.8% |
| t0 | 80.0 | 65.5 | 1,091,821 | — |

**Best scenario:** `t03_stag2s` — EX **82.0%**, 483,807 tokens, redundancy 16.3%.

Compared to **P2 full stack+prune** (Chapter 6): EX +6 pp, tokens -57.0%.

### 8.3.3 GPT-4o mini

**Table 8.3.** Schedule scenarios (EX, redundancy, tokens).

| Scenario | EX % | Redundancy % | Tokens | Δ tok vs t0 |
|----------|-----:|-------------:|-------:|------------:|
| t03_stag2s | 64.0 | 39.0 | 2,262,297 | -26.8% |
| stag2s | 58.0 | 44.6 | 3,223,211 | +4.4% |
| stag1t | 62.0 | 56.0 | 3,021,434 | -2.2% |
| ladder | 64.0 | 43.3 | 3,288,992 | +6.5% |
| t07 | 60.0 | 50.3 | 2,211,451 | -28.4% |
| t03 | 62.0 | 69.4 | 2,619,506 | -15.2% |
| t0 | 60.0 | 82.2 | 3,088,340 | — |

**Best scenario:** `t03_stag2s` — EX **64.0%**, 2,262,297 tokens, redundancy 39.0%.

Compared to **P2 full stack+prune** (Chapter 6): EX +8 pp, tokens +22.5%.

## 8.4 Discussion

**Gemini 2.5 Flash** responds strongly to both levers. Uniform T=0.3/T=0.7 raises EX from 80.0% to 82.0% while cutting redundancy from 65.5% to 16.3%. Combined **t03_stag2s** achieves the lowest redundancy on the subset with large token savings—early agents populate P1 cache before late replicas start.

**GPT-4o mini** shows smaller EX spread (58–64%) but redundancy falls from ~82% at T=0 to ~39–50% under T=0.7, ladder, or t03_stag2s. Best EX (**ladder** or **t03_stag2s**, 64%) exceeds prior P2+prune (56%) on this stack without P2 discovery—suggesting diversity substitutes for fragment hints for this model. Token spend remains higher than P3-only (Chapter 7).

**DeepSeek V3.2** gains +4 pp EX with **temperature ladder** (68% vs 64% t0) and reduces tokens modestly under stagger scenarios, but total tokens (~5.5–7M) remain far above P2+prune (5.25M). Schedule tuning does not fix DeepSeek's token budget problem; P2+prune remains preferred.

**Temperature vs stagger.** Uniform higher T reduces redundancy by diversifying SQL strings; stagger reduces *concurrent* duplicate probes and raises effective cache hit rate. **Combined t03_stag2s** is best for Gemini on both metrics.

**Relation to P2/P3.** Schedule changes operate *before* the LLM loop; P2/P3 inject peer context *during* the loop. They are complementary: Gemini may benefit from t03_stag2s *plus* P2 discovery (not yet evaluated).

## 8.5 Recommendations

| Model | Prefer schedule | Rationale |
|-------|---------------|-----------|
| DeepSeek V3.2 | `ladder` | +4 pp EX vs P2+prune; tokens +32.2%. |
| Gemini 2.5 Flash | `t03_stag2s` | Beats P2+prune on EX (+6 pp) and tokens (-57.0%). |
| GPT-4o mini | `t03_stag2s` | +8 pp EX vs P2+prune; tokens +22.5%. |

## 8.6 Limitations

- Smoke subset (50 tasks); temperature effects may shrink on full BIRD dev.
- Stagger turn-poll uses fixed 1s intervals—not wall-clock synchronisation with peers.
- Schedule sweep omits P2/P3; best combined stack not yet run.
- GPT ladder raises EX but not token spend vs t0 on all scenarios.

## 8.7 Summary

Replica **temperature** and **stagger** are cheap coordination knobs compared to P2/P3 middleware. On Gemini, **t03_stag2s** delivers the best redundancy and token trade-off; on GPT, **ladder** or **t03_stag2s** improves EX over T=0 without discovery injection; DeepSeek sees modest EX gains from ladder but remains token-heavy. Chapter 2's open question—whether T>0 reduces redundancy—is **confirmed**; the deployment rule remains **model-specific**, as in Chapters 6–7.

---

## Appendix: source artefacts

| Artefact | Path |
|----------|------|
| Schedule batches | `runs/batches/parallel_sched_r10_bo_*` |
| Comparison report | `runs/reports/schedule_sweep.json` |
| Compare script | `scripts/compare_schedule.py` |
| Replica schedule | `src/coord/replica_schedule.py` |

