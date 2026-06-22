# Chapter 9: Synthesis and Deployment Rules

*Draft generated 2026-06-21 from Chapters 2–8 batch comparisons and the Gemini schedule+P2 follow-up (`sched_p2_t03_stag2s_r10_bo`). Regenerate with `uv run python scripts/generate_chapter9_draft.py`.*

## 9.1 Problem recap

Chapter 2 established that independent parallel replicas waste coordination budget at four layers: duplicate LLM trajectories (token overhead 10–33× at *N*=10–25), duplicate explore SQL strings (70–88% redundancy), duplicate SQLite execution, and full schema context re-sent every turn. Subsequent chapters evaluated policies that target each layer—but **no single middleware removes all four**, and policies that help one model can hurt another.

## 9.2 Policy taxonomy

| Layer | Policy | When it helps | Primary cost |
|-------|--------|---------------|--------------|
| Turn trimming | Early stop (Ch. 3) | Post-success siblings | None; misses pre-success dupes |
| DB execution | P1 shared cache (Ch. 4) | Identical explore SQL | Memory; no LLM savings alone |
| Explore hints | P2 discovery board (Ch. 5) | Models that use fragment hints (Gemini) | Prompt growth every turn |
| Outcome facts | P3 semantic store (Ch. 7) | GPT; token-efficient broadcasting | Model-dependent fact volume |
| Prompt size | Hybrid schema prune (Ch. 6) | All models | Offline recall dependency |
| Replica diversity | Temperature / stagger (Ch. 8) | Redundant T=0 replicas | Scheduling complexity |

Policies operate at different points in the loop: **schedule** (before first LLM call), **cache** (at SQL execution), **injection** (before each LLM turn), **early stop** (after EX=1). Stacking without understanding these interaction points produced counter-intuitive results throughout the thesis.

## 9.3 Cross-model stack comparison (*N*=10)

Table 9.1 summarises the strongest candidate from each chapter family on the 50-task smoke subset.

**Table 9.1.** Candidate stacks per model at *N*=10.

| Model | Stack | EX % | Redundancy % | Tokens |
|-------|-------|-----:|-------------:|-------:|
| DeepSeek V3.2 — P2+prune | 64.0 | 75.7 | 5,251,285 |
| DeepSeek V3.2 — P3 | 60.0 | 71.8 | 7,482,194 |
| DeepSeek V3.2 — `ladder` | 68.0 | 50.9 | 6,941,153 |
| Gemini 2.5 Flash — P2+prune | 76.0 | 69.9 | 1,124,009 |
| Gemini 2.5 Flash — P3 | 70.0 | 69.2 | 1,121,670 |
| Gemini 2.5 Flash — `t03_stag2s` | 82.0 | 16.3 | 483,807 |
| GPT-4o mini — P2+prune | 56.0 | 79.9 | 1,847,079 |
| GPT-4o mini — P3 | 60.0 | 79.4 | 1,726,234 |
| GPT-4o mini — `t03_stag2s` | 64.0 | 39.0 | 2,262,297 |

**Headline conflicts resolved:**

- **Gemini:** Chapter 6 favoured P2+prune (76% EX); Chapter 8 showed schedule-only `t03_stag2s` beats it (82% EX, −57% tokens). P2 is not required when stagger + temperature already diversify exploration.
- **GPT:** Chapter 6 P2+prune loses 2 pp EX vs P0; Chapter 7 P3 gains +4 pp with −6.5% tokens. Chapter 8 schedule raises EX to 64% but at +22% tokens vs P2+prune and far above P3.
- **DeepSeek:** P2+prune remains lowest-cost; P3 adds +42.5% tokens (Ch. 7). Schedule ladder improves EX (+4 pp) but not token budget.

## 9.4 Gemini follow-up: schedule + P2 discovery

Chapter 8 §8.6 noted that the best combined stack (schedule + P2) was not evaluated. We ran **`sched_p2_t03_stag2s_r10_bo`**: Gemini 2.5 Flash at *N*=10 with `t03_stag2s` schedule **plus** P2 discovery board (P1 + early stop + hybrid prune).

**Table 9.2.** `t03_stag2s` + P2 vs schedule-only and P2+prune (Gemini).

| Stack | EX % | Redundancy % | Tokens |
|-------|-----:|-------------:|-------:|
| `t03_stag2s` only (Ch. 8) | 82.0 | 16.3 | 483,807 |
| `t03_stag2s` + P2 (follow-up) | 80.0 | 14.6 | 489,040 |
| P2+prune (Ch. 6) | 76.0 | 69.9 | 1,124,009 |

- **EX:** -2.0pp vs schedule-only (80.0% vs 82.0%).
- **Redundancy:** -1.7pp vs schedule-only.
- **Tokens:** +1.1% vs schedule-only (489,040 vs 483,807).

**Finding:** Adding P2 discovery on top of `t03_stag2s` **does not improve** the Chapter 8 winner. EX drops 2 pp with essentially flat tokens (+1%). Schedule diversity already substitutes for P2 fragment hints on Gemini; dual injection adds prompt cost without accuracy gain. P2+prune remains dominated on all three metrics by schedule-only.

## 9.5 Model-conditioned deployment rules

**Table 9.3.** Recommended stacks at *N*=10 (50-task smoke subset).

| Model | Recommended stack | EX % | Tokens | Notes |
|-------|-------------------|-----:|-------:|-------|
| DeepSeek V3.2 | P2 discovery + P1 + early stop + hybrid prune | 64.0 | 5,251,285 | Lowest token budget at acceptable EX — 64.0% EX, 5,251,285 tokens. Schedule `... |
| Gemini 2.5 Flash | `t03_stag2s` + P1 + early stop + hybrid prune (no P2) | 82.0 | 483,807 | `t03_stag2s` + P1 + early stop + hybrid prune — 82.0% EX, 483,807 tokens. P2 ... |
| GPT-4o mini | P3 semantic store + P1 + early stop + hybrid prune | 60.0 | 1,726,234 | P3 replaces P2 fragment injection — 60.0% EX, 1,726,234 tokens vs P2+prune 56... |

### Per-model rationale

#### DeepSeek V3.2

Lowest token budget at acceptable EX — 64.0% EX, 5,251,285 tokens. Schedule `ladder` raises EX +4 pp but tokens +32.2% — not cost-effective.

**Alternatives considered:**
- `p3_only`: 60.0% EX, 7,482,194 tokens
- `best_schedule`: 68.0% EX, 6,941,153 tokens

#### Gemini 2.5 Flash

`t03_stag2s` + P1 + early stop + hybrid prune — 82.0% EX, 483,807 tokens. P2 discovery on top drops EX −2 pp with flat tokens (§9.4); omit P2.

**Alternatives considered:**
- `p2_prune`: 76.0% EX, 1,124,009 tokens
- `p3_only`: 70.0% EX, 1,121,670 tokens
- `sched_p2_gemini`: 80.0% EX, 489,040 tokens

#### GPT-4o mini

P3 replaces P2 fragment injection — 60.0% EX, 1,726,234 tokens vs P2+prune 56.0% / 1,847,079 tokens.

**Alternatives considered:**
- `p2_prune`: 56.0% EX, 1,847,079 tokens
- `best_schedule`: 64.0% EX, 2,262,297 tokens

## 9.6 Decision flow

```
For each model at deployment:
  1. Always enable: P1 cache + early stop + hybrid schema prune
  2. If Gemini → use t03_stag2s schedule; skip P2
  3. If GPT     → use P3 semantic store; skip P2
  4. If DeepSeek → use P2 discovery; skip P3; schedule optional for EX only
```

This is a **heuristic from the smoke subset**, not a universal law. The unifying principle: match coordination to how each model responds to shared syntactic hints (P2) vs distilled outcome facts (P3) vs pre-loop diversity (schedule).

## 9.7 Limitations

- **50-task smoke subset**; deployment rules may shift on full BIRD dev.
- ***N*=10 only** for schedule and P3 synthesis; *N*=25 gaps remain (Ch. 6).
- **GPT schedule + P3** and **DeepSeek schedule + P2** not run.
- **P4** (phase-aware sharing, cross-model ensembles) not implemented.
- **DeepSeek P3 token anomaly** (+42.5%) may include timeout retries.

## 9.8 Summary

Parallel text-to-SQL coordination has no single optimal stack. The thesis evaluated policies across execution (cache), turn (early stop), prompt (P2/P3/prune), and schedule (temperature/stagger) layers. **Gemini** benefits most from cheap schedule knobs—`t03_stag2s` delivers 82% EX at under half the tokens of P2+prune, and adding P2 on top does not help. **GPT** benefits from P3 outcome facts over P2 fragments. **DeepSeek** remains P2+prune on cost grounds. The deployment rule is **model-conditioned**: token-efficient parallel agents require matching middleware to model behaviour, not applying the fullest stack uniformly.

---

## Appendix: source artefacts

| Artefact | Path |
|----------|------|
| P2+prune batches | `runs/batches/parallel_fullstack_prune_r10_bo_*` |
| P3 batches | `runs/batches/parallel_semantic_hybrid_r10_bo_*` |
| Schedule sweep | `runs/batches/parallel_sched_r10_bo_*` |
| Gemini schedule+P2 | `runs/batches/parallel_sched_p2_t03_stag2s_r10_bo_*` |
| Synthesis loader | `src/coord/synthesis_analysis.py` |
| Generate script | `scripts/generate_chapter9_draft.py` |

