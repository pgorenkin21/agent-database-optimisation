# Chapter 6: Middleware Stack Synthesis

*Draft generated 2026-06-18 from P0, P1, P2, P1+P2, early-stop, schema-prune, and P3 batch comparisons. Chapter 7 covers P3 in full. Regenerate stack sections with `uv run python scripts/generate_chapter6_draft.py`.*

## 6.1 Overview

Chapters 2–5 evaluated coordination policies in isolation on a 50-task BIRD mini-dev smoke subset. This chapter places them side-by-side and adds **P1+P2** (`P1_P2_combined`): shared SQL cache plus discovery-board prompt injection at *N*=10.

| Layer | Policy | Mechanism | Primary target |
|-------|--------|-----------|----------------|
| Ch. 3 | Early stop | Cancel siblings after EX=1 | Post-success LLM turns |
| Ch. 4 | P1 cache | AST-keyed SQL result LRU | Duplicate DB execution |
| Ch. 5 | P2 board | Fragment prompt injection | Duplicate explore probes |
| §6.4 | P1+P2 | Both enabled | DB + exploration hints |
| §6.6 | Schema prune | Keyword table selection in prompt | Initial schema context size |
| §6.7 | Full stack+prune | P1+P2+early stop+schema prune | All layers combined |
| Ch. 7 | P3 semantic store | Bounded outcome facts (replaces P2 hints) | Token-efficient broadcasting |

The headline finding across chapters: **explore redundancy in traces is a poor proxy for token savings**. P0 reports 70–88% duplicate explore SQL at high *N*, yet only early stopping and schema pruning reliably reduce total tokens at *N*=10. P1 and P2 optimise different layers; stacking middleware without pruning does not produce additive token wins—but **full stack + schema prune v2** does for Gemini and DeepSeek.

## 6.2 What each policy actually saves

**Early stopping (Ch. 3)** is the only policy that directly removes LLM turns. It fires only after a correct `submit_sql`, so pre-success exploration—where most duplication occurs—is untouched. At *N*=25, token savings are ~8–12% with overhead ratio dropping from ~27× to ~24× (GPT).

**P1 shared cache (Ch. 4)** removes 70–84% of SQLite round-trips on cache hits but leaves explore SQL strings and LLM trajectories unchanged. Token overhead is flat (±3% run noise). Middleware interaction % rises to ~40–55% at *N*=10.

**P2 discovery board (Ch. 5)** publishes sqlglot fragments and injects peer context before each turn. Redundancy drops meaningfully for Gemini at *N*=10 (−6.7 pp) but tokens often **rise** because injection grows the prompt. Middleware interaction % reaches ~25–35% at *N*=10 via discovery injections alone.

## 6.2.1 Middleware interaction metric

To separate **database work** from **middleware work**, we count every agent interaction in replica traces:

| Class | Trace event | Policy |
|-------|-------------|--------|
| SQLite execution | `sql_execute` without `cache_hit` | P0, P1 miss, P2, final submit |
| Middleware (cache) | `sql_execute` with `cache_hit=true` | P1, P1+P2 |
| Middleware (discovery) | `discovery_injection` | P2, P1+P2, P2+P3 |
| Middleware (semantic) | `semantic_injection` | P3, P2+P3 |

**Middleware interaction %** = (cache hits + discovery injections) / (SQLite executions + cache hits + discovery injections). Under P0 this is **0%** by definition. Table 6.x shows how each policy shifts the balance.

## 6.3 Cross-policy comparison

### 6.3.1 Replica count *N*=10

**Table 6.1.** Middleware stack at *N*=10 (50-task smoke subset).

*Execution accuracy (%)*

| Model | P0 | P1 | P2 | P1+P2 | early_stop | full_stack+prune |
|-------|--------:|--------:|--------:|--------:|--------:|--------:|
| GPT-4o mini | 58.0 | 62.0 | 58.0 | 56.0 | 60.0 | 56.0 |
| Gemini 2.5 Flash | 74.0 | 74.0 | 76.0 | 76.0 | 74.0 | 76.0 |
| DeepSeek V3.2 | 60.0 | 60.0 | 62.0 | 62.0 | 60.0 | 64.0 |

*Explore redundancy (%)*

| Model | P0 | P1 | P2 | P1+P2 | early_stop | full_stack+prune |
|-------|--------:|--------:|--------:|--------:|--------:|--------:|
| GPT-4o mini | 78.7 | 78.1 | 79.3 | 76.0 | 77.8 | 79.9 |
| Gemini 2.5 Flash | 73.6 | 74.1 | 66.9 | 67.0 | 73.6 | 69.9 |
| DeepSeek V3.2 | 71.3 | 70.3 | 75.4 | 72.7 | 75.0 | 75.7 |

*Token overhead (×)*

| Model | P0 | P1 | P2 | P1+P2 | early_stop | full_stack+prune |
|-------|--------:|--------:|--------:|--------:|--------:|--------:|
| GPT-4o mini | 10.55 | 10.55 | 11.07 | 10.67 | 9.94 | 9.83 |
| Gemini 2.5 Flash | 10.54 | 10.72 | 11.26 | 11.03 | 10.28 | 10.61 |
| DeepSeek V3.2 | 13.38 | 13.68 | 11.54 | 12.38 | 10.72 | 10.35 |

*Middleware interaction (%)*

| Model | P0 | P1 | P2 | P1+P2 | early_stop | full_stack+prune |
|-------|--------:|--------:|--------:|--------:|--------:|--------:|
| GPT-4o mini | 0.0 | 48.5 | 34.0 | 61.6 | 0.0 | 75.0 |
| Gemini 2.5 Flash | 0.0 | 40.4 | 24.5 | 49.2 | 0.0 | 61.8 |
| DeepSeek V3.2 | 0.0 | 54.6 | 35.1 | 70.2 | 0.0 | 79.5 |


![Figure 6.1 — Middleware stack at N=10](runs/reports/plots/middleware_stack_r10.png)

*Figure 6.1. Token overhead, explore redundancy, middleware interaction %, and total tokens across policies at *N*=10.*

### 6.3.2 Replica count *N*=25

**Table 6.2.** Middleware stack at *N*=25 (50-task smoke subset).

*Execution accuracy (%)*

| Model | P0 | P1 | P2 | early_stop | full_stack |
|-------|--------:|--------:|--------:|--------:|--------:|
| GPT-4o mini | 62.0 | 62.0 | 56.0 | 62.0 | 60.0 |
| Gemini 2.5 Flash | 70.0 | 72.0 | 76.0 | 64.0 | 78.0 |
| DeepSeek V3.2 | 64.0 | 62.0 | 62.0 | 58.0 | 64.0 |

*Explore redundancy (%)*

| Model | P0 | P1 | P2 | early_stop | full_stack |
|-------|--------:|--------:|--------:|--------:|--------:|
| GPT-4o mini | 87.7 | 88.7 | 87.3 | 87.9 | 86.8 |
| Gemini 2.5 Flash | 76.6 | 80.5 | 75.3 | 69.8 | 69.6 |
| DeepSeek V3.2 | 82.9 | 82.0 | 84.0 | 85.4 | 84.0 |

*Token overhead (×)*

| Model | P0 | P1 | P2 | early_stop | full_stack |
|-------|--------:|--------:|--------:|--------:|--------:|
| GPT-4o mini | 27.14 | 26.30 | 28.21 | 23.79 | 24.08 |
| Gemini 2.5 Flash | 24.46 | 25.64 | 27.81 | 18.77 | 24.00 |
| DeepSeek V3.2 | 32.66 | 34.02 | 31.66 | 25.89 | 27.27 |

*Middleware interaction (%)*

| Model | P0 | P1 | P2 | early_stop | full_stack |
|-------|--------:|--------:|--------:|--------:|--------:|
| GPT-4o mini | 0.0 | 54.9 | 35.1 | 0.0 | 81.2 |
| Gemini 2.5 Flash | 0.0 | 45.3 | 25.6 | 0.0 | 64.8 |
| DeepSeek V3.2 | 0.0 | 64.5 | 35.8 | 0.0 | 86.0 |


## 6.4 P1+P2 combined stack (*N*=10)

Batch ID `p1p2_r10_bo` with `--shared-cache --discovery-board`.

### Gemini 2.5 Flash (best P2 responder)

| Metric | P0 | P1 | P2 | P1+P2 |
|--------|---:|---:|---:|------:|
| EX % | 74.0 | 74.0 | 76.0 | 76.0 |
| Redundancy % | 73.6 | 74.1 | 66.9 | 67.0 |
| Overhead × | 10.54 | 10.72 | 11.26 | 11.03 |
| Cache hit % | — | 71.0 | — | 61.6 |
| Middleware interaction % | 0.0 | 40.4 | 24.5 | 49.2 |

P1+P2 preserves P2's redundancy reduction (~67% vs 73.6% P0) while token spend (+6.5% vs P0) is lower than P2 alone (+11.2%). Cache hits remain high (~62%) despite slightly different SQL strings from discovery hints.

### GPT-4o mini and DeepSeek V3.2

- **GPT-4o mini:** redundancy -2.8 pp vs P0; tokens -0.7% vs P0; cache 65%; middleware interaction 61.6%.
- **DeepSeek V3.2:** redundancy +1.4 pp vs P0; tokens -15.3% vs P0; cache 69%; middleware interaction 70.2%.

## 6.5 Full stack at *N*=25 (P1+P2+early stop)

Batch ID `fullstack_r25_bo` with `--shared-cache --discovery-board --early-stop`. Trace policy: `P1_P2_combined_early_stop`.

| Model | P0 EX % | full_stack EX % | P0 overhead | full_stack overhead | Token Δ vs P0 | Cache hit % | Middleware % | ES triggered |
|-------|--------:|----------------:|------------:|--------------------:|------------:|------------:|-------------:|-------------:|
| GPT-4o mini | 62.0 | 60.0 | 27.14× | 24.08× | +9.4% | 79.5 | 81.2 | 30/50 |
| Gemini 2.5 Flash | 70.0 | 78.0 | 24.46× | 24.00× | +3.5% | 68.1 | 64.8 | 39/50 |
| DeepSeek V3.2 | 64.0 | 64.0 | 32.66× | 27.27× | -24.9% | 82.8 | 86.0 | 32/50 |

The full stack combines post-success cancellation with shared cache and discovery hints. Results are **model-dependent**:

- **GPT-4o mini:** EX -2 pp vs P0; tokens +9.4% vs P0, +19.2% vs early stop alone; cache 80%; middleware 81%.
- **Gemini 2.5 Flash:** EX +8 pp vs P0; tokens +3.5% vs P0, +17.3% vs early stop alone; cache 68%; middleware 65%.
- **DeepSeek V3.2:** EX +0 pp vs P0; tokens -24.9% vs P0, -14.7% vs early stop alone; cache 83%; middleware 86%.

**DeepSeek V3.2** is the standout: -24.9% tokens vs P0 at *N*=25 while preserving EX, with ~83% cache hits and ~86% middleware interaction. P1 cache removes most redundant SQLite work; early stop trims sibling turns; discovery hints do not dominate token cost for this model.

**GPT-4o mini and Gemini 2.5 Flash** see P2 prompt injections offset early-stop savings: full-stack token spend exceeds early stop alone (+17–19%) even when middleware interaction rises to 65–81%. Gemini gains +8 pp EX vs P0 (78% vs 70%) at the cost of +3.5% tokens.

## 6.6 Schema pruning (prompt layer)

Schema pruning trims the **initial user message**—DDL plus column descriptions—before any replica runs. The full schema is re-sent on every LLM turn, so even modest per-task cuts compound across *N* replicas.

**Mechanism (v2).** Score tables from question + evidence keywords; expand FK neighbors on `debit_card_specializing` only; apply database-specific recall rules (`transactions_1k` / `gasstations` for debit card; `event`→`attendance`, `expense`→`budget` for student_club); floor to two tables on larger schemas. **Static fallback:** no keyword signal → full schema. **Runtime fallback:** on `no such table` during `execute_sql`, restore full schema in the prompt.

Batch ID `schema_prune_r10_bo_v2` with `--schema-pruning`, Gemini 2.5 Flash, *N*=10.

| Metric | P0 | Schema prune v1 | Schema prune v2 |
|--------|---:|----------------:|----------------:|
| EX % | 74.0 | 68.0 | 72.0 |
| Total tokens | 1.57M | 2.12M (+35%) | **1.17M (−26%)** |
| Median token Δ vs P0 | — | +1.3% | **−15.1%** |

Offline gold-table recall: **100%** (50/50) with **34.5%** avg schema size reduction. v1 missed gold tables on 10 debit-card tasks, inflating tokens via failed exploration.

## 6.7 Full stack + schema prune (*N*=10)

Batch ID `fullstack_prune_r10_bo` with `--shared-cache --discovery-board --early-stop --schema-pruning`. All three eval models.

| Model | P0 EX % | full_stack+prune EX % | Token Δ vs P0 | Cache hit % | Middleware % | ES triggered |
|-------|--------:|----------------------:|--------------:|------------:|-------------:|-------------:|
| Gemini 2.5 Flash | 74.0 | **76.0** | **−28.3%** | 62.3 | 61.8 | 38/50 |
| DeepSeek V3.2 | 60.0 | **64.0** | **−32.6%** | 72.5 | 79.5 | 31/50 |
| GPT-4o mini | 58.0 | 56.0 | −21.1% | 72.8 | 75.0 | 28/50 |

**Gemini** and **DeepSeek** gain EX (+2 and +4 pp) with the largest token cuts in this chapter. **GPT** saves −21% tokens but loses −2 pp EX. Stacking is strongly positive when offline gold-table recall is preserved; GPT may be over-constrained by pruning plus discovery injections.

## 6.8 P3 semantic store (Chapter 7 preview)

Chapter 7 evaluates **P3**—replacing P2 fragment lists with a **capped semantic fact store**—against the same full stack+prune baseline at *N*=10. All P3 runs use P1 cache, early stop, and hybrid schema pruning; P3-only runs omit the P2 discovery board.

**Table 6.3.** P3 vs P2 full stack+prune (*N*=10).

| Model | P2+prune EX % | P3 EX % | EX Δ | Token Δ vs P2 | Recommendation |
|-------|-------------:|--------:|-----:|--------------:|----------------|
| GPT-4o mini | 56.0 | **60.0** | +4.0 pp | **−6.5%** | Adopt P3 |
| Gemini 2.5 Flash | **76.0** | 70.0 | −6.0 pp | −0.2% | Mixed (prefer P2+prune) |
| DeepSeek V3.2 | **64.0** | 60.0 | −4.0 pp | +42.5% | Avoid P3 |

A **P2+P3 combined** follow-up on Gemini and DeepSeek partially recovered EX (74% and 66%) but neither matched P2+prune on accuracy at acceptable token cost. See Chapter 7 for mechanism, metrics, and model-conditioned deployment rules.

## 6.9 Discussion: why overhead changes are smaller than redundancy suggests

1. **Metric layers differ.** Explore redundancy counts duplicate SQL *strings* in traces. Token overhead sums *all replica LLM trajectories* divided by the cheapest correct answer. Most tokens live in schema context, chat history, and completions—not in the SQL tool call itself.

2. **P1 is below the token ledger.** Cache hits skip SQLite, not LLM turns. An 80% cache hit rate does not imply an 80% token reduction. The **middleware interaction %** metric (cache hits + discovery injections vs SQLite executions) makes this layer explicit: P1 raises it via cache; P2 via prompt injections; P0 stays near 0%.

3. **P2 adds prompt cost.** Each injection lists peer fragments. Savings from fewer explore queries (when they occur) compete with larger per-turn prompts.

4. **Early stop is timed late.** ~60% of tasks trigger cancellation at *N*=25, but only after exploration-heavy work is already done.

5. **Unique exploration saturates.** Chapter 2 showed unique explore queries plateau as *N* grows; policies that deduplicate execution or hint at fragments do not collapse *N* independent LLM dialogues into one.

6. **P3 adds a third middleware channel.** Semantic injections count toward middleware interaction % alongside cache hits and discovery injections. Outcome facts are capped per turn but DeepSeek still publishes ~62 facts/task—prompt load can exceed P2 fragment lists for verbose models.

## 6.10 Recommendations

| Goal | Prefer | Rationale |
|------|--------|-----------|
| Cut SQLite load | **P1** or **P1+P2** | 65–84% cache hits; middleware interaction 50–70% at *N*=10 |
| Cut tokens modestly | **Early stop**, **schema prune v2**, or **full stack+prune** | −8–12% at *N*=25 (early stop); −26–33% at *N*=10 (prune / stack+prune) |
| Cut explore redundancy (Gemini) | **P2**, **P1+P2**, or **full stack+prune** | −6.7 pp at *N*=10 |
| Shrink prompt schema | **Schema prune v2** or **full stack+prune** | −34.5% schema chars offline |
| Preserve EX | **P1+P2** or **full stack+prune** (Gemini/DeepSeek); **P3** (GPT) | GPT loses 2 pp with full stack+prune but gains +4 pp with P3 |
| Best overall (*N*=10) | **full stack+prune** (Gemini/DeepSeek); **P3** (GPT) | Model-conditioned; see Ch. 7 |

## 6.11 Limitations and future work

- Smoke subset (50 tasks); GPT *N*=25 EX dip under P2 may not generalise.
- **P3 evaluated at *N*=10** (Chapter 7); P4 (phase-aware sharing, cross-model ensembles) not implemented.
- Discovery and semantic prompt sizes partially capped in P3; P2 fragment lists remain uncapped in P2+prune runs.
- Full stack + schema prune at *N*=25 not yet run (DeepSeek candidate).
- GPT EX regression under full stack+prune (−2 pp) partially explained by P3 adoption (+4 pp when P2 hints removed).
- Full BIRD dev scale-up not yet run.

## 6.12 Summary

Parallel text-to-SQL replicas waste work at multiple layers: duplicate LLM trajectories (token overhead 10–33×), duplicate explore SQL (70–88% redundancy), duplicate database execution, and oversized schema context re-sent every turn. **No single policy removes all four.** Early stop trims tokens after success; P1 removes redundant DB work; P2 nudges exploration via shared fragments. **Schema pruning v2** cuts prompt schema ~35% offline. **Full stack + schema prune** at *N*=10 delivers **−28–33% tokens** vs P0 for Gemini and DeepSeek with EX gains; GPT trades 2 pp EX for −21% tokens under P2+prune but **+4 pp EX with P3** (Chapter 7). At *N*=25, **full stack** without prune still favours **DeepSeek** (−24.9% tokens, EX unchanged). **Middleware choice is model-dependent**—the optimal stack is not universal.

---

## Appendix: source artefacts

| Artefact | Path |
|----------|------|
| Stack comparison | `runs/reports/middleware_stack.json` |
| P1+P2 r=10 report | `runs/reports/p1p2_stack_r10.json` |
| Full stack *N*=25 batches | `runs/batches/parallel_fullstack_r25_bo_*` |
| Schema pruning v2 batch | `runs/batches/parallel_schema_prune_r10_bo_v2_*` |
| Full stack + schema prune *N*=10 | `runs/batches/parallel_fullstack_prune_r10_bo_*` |
| P3 semantic store *N*=10 | `runs/batches/parallel_semantic_hybrid_r10_bo_*` |
| P2+P3 combined *N*=10 | `runs/batches/parallel_p2p3_hybrid_r10_bo_*` |
| P3 comparison report | `runs/reports/p3_vs_p2.json` |
| Chapter 7 draft | `thesis/chapter7_semantic_store.md` |
| Schema pruning offline report | `runs/reports/schema_pruning.json` |
| Figure 6.x (*N*=10) | `runs/reports/plots/middleware_stack_r10.png` |
| Figure 6.x (*N*=25) | `runs/reports/plots/middleware_stack_r25.png` |
