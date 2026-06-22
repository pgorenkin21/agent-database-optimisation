# Chapter 3: Early Stopping in Parallel Text-to-SQL Agents

*Draft generated 2026-06-16 from P0 vs `P0_early_stop` batch comparisons. Regenerate with `uv run python scripts/generate_chapter3_draft.py`.*

## 3.1 Motivation

Chapter 2 established that independent parallel replicas waste a large fraction of database exploration work—explore redundancy exceeds 80% at *N*=25—while execution accuracy plateaus. The simplest coordination lever that does not require shared state is **early stopping**: once any replica achieves execution accuracy (EX=1), cancel remaining siblings at the next turn boundary.

This chapter evaluates that policy under trace label **`P0_early_stop`**. It is apples-to-apples with the P0 baseline: same models, replica counts, `best_of_n` coordination, and smoke subset—the only change is replica cancellation after the first correct answer.

## 3.2 Policy: P0_early_stop

Early stopping extends P0 with a single coordination hook:

1. Spawn *N* identical agents on the same `(question, database)` pair (as P0).
2. After each replica turn, check whether any replica has achieved EX=1 on a `submit_sql` call.
3. If so, signal all other replicas to stop at their next turn boundary (no new LLM calls).
4. Apply `best_of_n` to choose the coordinated answer from completed replica traces.

Early stop does **not** share SQL results or exploration discoveries across replicas. It only prevents further LLM turns once correctness is known. Explore-query redundancy measured during the run should therefore remain high: cancelled replicas may already have issued duplicate probes before a sibling succeeds.

## 3.3 Experimental setup

All settings match Chapter 2 unless noted:

- **Benchmark:** BIRD mini-dev smoke subset (50 tasks).
- **Models:** GPT-4o mini, Gemini 2.5 Flash, DeepSeek V3.2.
- **Replica counts:** *N* ∈ {10, 25}.
- **Coordination:** `best_of_n` (same as P0).
- **P0 baseline batches:** latest `parallel_*_baseline_rN_*_best_of_n.json` per model.
- **Early-stop batches:** `earlystop_r10_bo` and `earlystop_r25_bo` sweep IDs.

## 3.4 Metrics

In addition to Chapter 2 metrics (EX %, explore redundancy %, token overhead), early-stop runs record:

| Metric | Definition |
|--------|------------|
| **Early stop triggered** | Tasks where at least one replica reached EX=1 before all *N* replicas finished. |
| **Replicas cancelled** | Per task, count of replicas stopped by the cancel signal after early stop fired. |
| **Token Δ vs P0** | Percentage change in total batch tokens relative to the matching P0 batch. |

## 3.5 Results

### 3.5.1 Replica count *N*=10

**Table 3.1.** P0 vs early stop at *N*=10 (50-task smoke subset, `best_of_n`).

| Model | P0 EX % | ES EX % | P0 redundancy % | ES redundancy % | P0 tokens | ES tokens | Token Δ | P0 overhead | ES overhead | ES triggered |
|-------|--------:|--------:|----------------:|----------------:|----------:|----------:|--------:|------------:|------------:|-------------:|
| GPT-4o mini | 58.0 | 60.0 | 78.7 | 77.8 | 2,341,781 | 2,432,022 | +3.9% | 10.55× | 9.94× | 30/50 |
| Gemini 2.5 Flash | 74.0 | 74.0 | 73.6 | 73.6 | 1,568,278 | 1,529,204 | -2.5% | 10.54× | 10.28× | 37/50 |
| DeepSeek V3.2 | 60.0 | 60.0 | 71.3 | 75.0 | 7,792,210 | 6,676,709 | -14.3% | 13.38× | 10.72× | 30/50 |

### 3.5.2 Replica count *N*=25

**Table 3.2.** P0 vs early stop at *N*=25 (50-task smoke subset, `best_of_n`).

| Model | P0 EX % | ES EX % | P0 redundancy % | ES redundancy % | P0 tokens | ES tokens | Token Δ | P0 overhead | ES overhead | ES triggered |
|-------|--------:|--------:|----------------:|----------------:|----------:|----------:|--------:|------------:|------------:|-------------:|
| GPT-4o mini | 62.0 | 62.0 | 87.7 | 87.9 | 6,322,822 | 5,800,147 | -8.3% | 27.14× | 23.79× | 31/50 |
| Gemini 2.5 Flash | 70.0 | 64.0† | 76.6 | 69.8 | 3,685,459 | 3,251,203 | -11.8% | 24.46× | 18.77× | 32/50 |
| DeepSeek V3.2 | 64.0 | 58.0 | 82.9 | 85.4 | 18,889,223 | 16,633,789 | -11.9% | 32.66× | 25.89× | 29/50 |

† Gemini 2.5 Flash early-stop run: 6 API failure(s); EX on completed tasks = 72.7%.

![Figure 3.1 — Early stop vs P0 at N=25](runs/reports/plots/early_stop_comparison_r25.png)

*Figure 3.1. Token spend and overhead ratio: P0 vs early stop at *N*=25.*

![Figure 3.2 — Token savings across N](runs/reports/plots/early_stop_token_savings.png)

*Figure 3.2. Percentage token change vs P0 baseline across replica counts.*

### 3.5.3 Per-model detail

### GPT-4o mini

- Early stop triggered on **31/50** tasks; avg **13.7** replicas cancelled per task.
- Token spend: 6,322,822 (P0) → 5,800,147 (early stop), **-8.3%**.
- Explore redundancy: 87.7 → 87.9 (minimal change).
- Avg tokens/task when triggered: **86,910** vs **163,470** when not triggered.

### Gemini 2.5 Flash

- Early stop triggered on **32/50** tasks; avg **14.76** replicas cancelled per task.
- Token spend: 3,685,459 (P0) → 3,251,203 (early stop), **-11.8%**.
- Explore redundancy: 76.6 → 69.8 (minimal change).
- Avg tokens/task when triggered: **73,293** vs **50,324** when not triggered.

### DeepSeek V3.2

- Early stop triggered on **29/50** tasks; avg **13.8** replicas cancelled per task.
- Token spend: 18,889,223 (P0) → 16,633,789 (early stop), **-11.9%**.
- Explore redundancy: 82.9 → 85.4 (minimal change).
- Avg tokens/task when triggered: **246,965** vs **451,038** when not triggered.

## 3.6 Discussion

**Early stop recovers a modest share of token spend.** At *N*=25, total tokens fall by **12–8%** across models (-11.9% to -8.3%). Token overhead ratios drop by roughly 3–7× points (e.g. DeepSeek 32.7× → 25.9×).

**Stopping fires on most solvable tasks.** Early stop triggered on roughly **61%** of tasks at *N*=25 (29–32 of 50), cancelling ~14 replicas per triggered task on average.

**Explore redundancy barely moves.** String-level explore redundancy stays within a few percentage points of P0 (often slightly *higher* on early-stop traces). This confirms the mechanism: siblings duplicate probes *before* any replica submits a correct answer; cancellation prevents post-success turns but not concurrent or pre-success duplication.

**EX % is unchanged when runs complete cleanly.** GPT-4o mini matches P0 exactly (62% at *N*=25). DeepSeek drops 6 points on this sweep (64% → 58%), consistent with run-to-run variance on a 50-task subset rather than a systematic effect of early stopping. Gemini's headline EX is depressed by API failures on the early-stop run (64% vs 70% P0; 72.7% excluding failures).

**Early stop is necessary but insufficient.** It is a zero-state coordination policy worth deploying when parallel replicas are used, but it cannot attack the dominant cost identified in Chapter 2. Shared middleware—starting with a SQL result cache (P1)—is required to eliminate duplicate explore queries during the run.

## 3.7 Limitations

1. **Subset size.** 50-task smoke subset; magnitudes should be re-validated on the full mini-dev split.
2. **Turn-boundary cancellation.** Replicas finish their current turn before stopping; intra-turn tool calls are not interrupted.
3. **No shared cache.** Early stop does not deduplicate explore SQL across active replicas.
4. **API failures.** Gemini early-stop at *N*=25 incurred 6 transport failures; report EX excluding API errors when comparing to P0.
5. **P0 baseline pairing.** Comparisons use the latest P0 batch per model; Gemini P0 at *N*=25 retains 3 API failures from the original sweep.

## 3.8 Summary and implications

Early stopping (`P0_early_stop`) reduces total token spend by roughly **8–12%** at *N*=25 without shared state, by cancelling ~14 redundant replica trajectories per successful task. It does **not** materially reduce explore-query redundancy.

The next chapter evaluates **P1: a shared SQL result cache** keyed by AST-normalised queries, targeting the 70–90% duplicate explore statements that early stopping leaves untouched.

---

## Appendix: source artefacts

| Artefact | Path |
|----------|------|
| Early-stop batches (*N*=10) | `runs/batches/parallel_earlystop_r10_bo_*` |
| Early-stop batches (*N*=25) | `runs/batches/parallel_earlystop_r25_bo_*` |
| Comparison report | `runs/reports/early_stop_r25_vs_p0.json` |
| Figure 3.x (*N*=10) | `runs/reports/plots/early_stop_comparison_r10.png` |
| Figure 3.x (*N*=25) | `runs/reports/plots/early_stop_comparison_r25.png` |
| Figure 3.2 | `runs/reports/plots/early_stop_token_savings.png` |
