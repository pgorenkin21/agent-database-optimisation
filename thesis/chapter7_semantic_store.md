# Chapter 7: Semantic Fact Store (P3)

*Draft generated 2026-06-20 from P3 and P2+P3 batch comparisons. Regenerate with `uv run python scripts/generate_chapter7_draft.py`.*

## 7.1 Motivation

Chapter 5 (P2) shares **syntactic fragments**—tables, columns, predicates extracted via sqlglot—and injects them as peer-discovery blocks before each LLM turn. That policy can steer exploration for some models (notably Gemini at *N*=10) but often **raises token spend** because fragment lists grow with replica count and are re-sent every turn.

Chapter 6 showed that **full stack + schema prune** (P1 cache + P2 board + early stop + hybrid schema pruning) delivers the best overall trade-off for Gemini and DeepSeek at *N*=10, while GPT loses 2 pp execution accuracy. P2's prompt cost remains a concern when stacked with other layers.

**P3** replaces fragment lists with a **bounded semantic fact store**: after each explore `execute_sql`, rule-based extractors distil SQL, row counts, numeric summaries, distinct value samples, and error messages into short natural-language facts. Before each LLM turn, replicas receive a capped bullet list of peer facts (default: 8 bullets, 500 characters). The design targets **token-efficient broadcasting**—sharing *outcomes* of probes rather than re-listing structural hints on every turn.

Unlike P2, P3 does not attempt to deduplicate explore SQL strings directly; it gives models compact evidence (e.g. "`transactions` returned 0 rows", "column[2] min=1 max=99") so siblings can skip redundant probes. P3 stacks with P1 cache, early stop, and **hybrid schema pruning** (keyword seeds with TF-IDF semantic fallback) for apples-to-apples comparison against Chapter 6's full stack+prune baseline.

## 7.2 Policy: P3_semantic_store

P3 extends the parallel coordinator with a per-task `SharedSemanticStore`:

1. Spawn *N* agents with shared P1 SQL cache and early stop (same as full stack+prune).
2. On each explore `execute_sql`, run `extract_semantic_facts()` (no LLM calls): normalized AST snippet, join hints, row counts, column stats, distinct samples, SQLite errors.
3. Publish new facts to the store (deduplicated by lowercase key; max 128 entries per task).
4. Before each LLM `complete`, inject a **semantic context** user message (replacing prior injection for that turn), capped at 8 bullets and 500 characters.
5. Log `semantic_injection` events; aggregate `semantic_stats` in coordination traces.

**Hybrid schema pruning** (`--schema-pruning-mode hybrid`) scores tables from question + evidence keywords first; if no signal, falls back to TF-IDF cosine similarity between question+evidence and table/column descriptions. Offline recall on the smoke subset: **100%** gold-table recall with **34.5%** average schema size reduction.

**P3-only stack** (`--semantic-store --shared-cache --early-stop --schema-pruning`): P1 + P3 + early stop + hybrid prune; **no P2 discovery board**.

**P2+P3 combined** (`--discovery-board --semantic-store …`): both fragment injection and semantic facts enabled; batch ID `p2p3_hybrid_r10_bo`.

## 7.3 Experimental setup

Settings match Chapters 2–6 unless noted:

- **Benchmark:** BIRD mini-dev smoke subset (50 tasks).
- **Models:** GPT-4o mini, Gemini 2.5 Flash, DeepSeek V3.2.
- **Replica count:** *N* = 10 (`best_of_n`).
- **P2 baseline:** full stack + schema prune (`fullstack_prune_r10_bo`) — P1 + P2 + early stop + keyword/hybrid schema prune (Chapter 6 §6.7).
- **P3 batches:** `semantic_hybrid_r10_bo` (`--semantic-store --schema-pruning-mode hybrid`).
- **P2+P3 batches:** `p2p3_hybrid_r10_bo` (Gemini and DeepSeek only; follow-up to recover EX).

## 7.4 Metrics

| Metric | Definition |
|--------|------------|
| **Semantic facts / task** | Mean unique facts published per task after explore queries. |
| **Semantic injections / task** | Mean LLM turns where a non-empty semantic context block was injected. |
| **Middleware interaction %** | (cache hits + semantic injections [+ discovery injections for P2+P3]) / total interactions. |
| **EX %** | Coordinated execution accuracy vs P2+prune and P0. |
| **Token Δ** | Total batch tokens vs baseline. |

## 7.5 Results

### 7.5.1 Replica count *N*=10

**Table 7.1.** P3 semantic store vs P2 full stack+schema prune at *N*=10 (50-task smoke subset, `best_of_n`).

| Model | P2+prune EX % | P3 EX % | EX Δ | P2 tokens | P3 tokens | Token Δ | Facts/task | Inj/task | Middleware % | Recommendation |
|-------|-------------:|--------:|-----:|----------:|----------:|--------:|-----------:|---------:|-------------:|----------------|
| GPT-4o mini | 56.0 | 60.0 | +4.0pp | 1,847,079 | 1,726,234 | -6.5% | 14.2 | 18.8 | 75.8 | **Adopt P3** |
| Gemini 2.5 Flash | 76.0 | 70.0 | -6.0pp | 1,124,009 | 1,121,670 | -0.2% | 8.1 | 9.8 | 60.5 | **Mixed** |
| DeepSeek V3.2 | 64.0 | 60.0 | -4.0pp | 5,251,285 | 7,482,194 | +42.5% | 61.4 | 55.9 | 79.9 | **Avoid P3** (prefer P2 full stack+prune) |

**Recommendations**

- **GPT-4o mini:** **Adopt P3** — EX +4 pp and tokens -6.5% vs P2 full stack+prune.
- **Gemini 2.5 Flash:** **Mixed** — EX -6 pp; consider P2+P3 combined or P2 alone.
- **DeepSeek V3.2:** **Avoid P3** (prefer P2 full stack+prune) — EX -4 pp and tokens +42.5% — prefer P2 full stack+prune.

**Cross-model summary (N=10):**

- Adopt P3: GPT-4o mini
- Prefer P2+prune: DeepSeek V3.2
- Mixed / model-specific: Gemini 2.5 Flash

#### P2+P3 combined follow-up

P3-only runs dropped EX for Gemini (−6 pp) and DeepSeek (−4 pp) vs P2+prune. We ran **P2+P3 combined** on those two models to test whether P2 fragment hints recover accuracy while semantic facts cap redundant outcome probes.

**Table 7.2.** P2+P3 combined vs P2+prune and P3-only at *N*=10.

| Model | P2+prune EX | P3 only EX | P2+P3 EX | P2+P3 tokens | Δ tok vs P2 | Δ tok vs P3 |
|-------|----------:|-----------:|---------:|-------------:|------------:|------------:|
| Gemini 2.5 Flash | 76.0 | 70.0 | 74.0 | 1,143,254 | +1.7% | +1.9% |
| DeepSeek V3.2 | 64.0 | 60.0 | 66.0 | 6,864,235 | +30.7% | -8.3% |

- **Gemini 2.5 Flash:** P2+P3 EX **74.0%** (-2 pp vs P2+prune, +4 pp vs P3-only); tokens +1.7% vs P2+prune.
- **DeepSeek V3.2:** P2+P3 EX **66.0%** (+2 pp vs P2+prune, +6 pp vs P3-only); tokens +30.7% vs P2+prune.

#### P3 vs P0 baseline

**Table 7.3.** P3 stack vs P0 baseline at *N*=10.

| Model | P0 EX % | P3 EX % | P0 tokens | P3 tokens | Token Δ vs P0 |
|-------|--------:|--------:|----------:|----------:|--------------:|
| GPT-4o mini | 58.0 | 60.0 | 2,341,781 | 1,726,234 | -26.3% |
| Gemini 2.5 Flash | 74.0 | 70.0 | 1,568,278 | 1,121,670 | -28.5% |
| DeepSeek V3.2 | 60.0 | 60.0 | 7,792,210 | 7,482,194 | -4.0% |

#### Per-model detail

### GPT-4o mini

- **P3 stack:** EX **60.0%** (+4 pp vs P2+prune); tokens -6.5% vs P2+prune.
- Semantic store: **14.2** facts/task; **18.8** injections/task; **72.1%** cache hit rate.
- Middleware interaction: **75.8%** (cache hits + semantic injections; no P2 discovery board in P3-only runs).
- Recommendation: **Adopt P3** — EX +4 pp and tokens -6.5% vs P2 full stack+prune.
- Batch: `parallel_semantic_hybrid_r10_bo_gpt-4o-mini_r10_best_of_n_p1_cache_p3_semantic_early_stop_schema_prune.json`

### Gemini 2.5 Flash

- **P3 stack:** EX **70.0%** (-6 pp vs P2+prune); tokens -0.2% vs P2+prune.
- Semantic store: **8.1** facts/task; **9.8** injections/task; **59.4%** cache hit rate.
- Middleware interaction: **60.5%** (cache hits + semantic injections; no P2 discovery board in P3-only runs).
- Recommendation: **Mixed** — EX -6 pp; consider P2+P3 combined or P2 alone.
- Batch: `parallel_semantic_hybrid_r10_bo_gemini-2.5-flash_r10_best_of_n_p1_cache_p3_semantic_early_stop_schema_prune.json`

### DeepSeek V3.2

- **P3 stack:** EX **60.0%** (-4 pp vs P2+prune); tokens +42.5% vs P2+prune.
- Semantic store: **61.4** facts/task; **55.9** injections/task; **69.4%** cache hit rate.
- Middleware interaction: **79.9%** (cache hits + semantic injections; no P2 discovery board in P3-only runs).
- Recommendation: **Avoid P3** (prefer P2 full stack+prune) — EX -4 pp and tokens +42.5% — prefer P2 full stack+prune.
- Batch: `parallel_semantic_hybrid_r10_bo_deepseek-v3.2_r10_best_of_n_p1_cache_p3_semantic_early_stop_schema_prune.json`

## 7.6 Discussion

**P3 outcomes are strongly model-dependent.** Replacing P2 fragment lists with capped semantic facts is not a universal upgrade over full stack+prune:

**GPT-4o mini — adopt P3.** P3 improves EX by **+4 pp** (60% vs 56%) while cutting tokens **−6.5%** vs P2+prune and **−26.3%** vs P0. GPT appears over-constrained by P2 discovery injections combined with schema pruning; compact outcome facts steer exploration without the fragment-list prompt premium.

**Gemini 2.5 Flash — mixed; prefer P2+prune.** P3-only drops EX **−6 pp** (70% vs 76%) with flat tokens (−0.2%). P2+P3 recovers to **74%** (+4 pp vs P3-only) but remains **−2 pp** below P2+prune at +1.7% tokens. Gemini benefited from P2 fragment hints in Chapter 5; removing them hurts more than semantic facts compensate.

**DeepSeek V3.2 — avoid P3; prefer P2+prune.** P3-only loses **−4 pp** EX and adds **+42.5%** tokens vs P2+prune. The token spike correlates with heavy semantic activity (~62 facts/task, ~56 injections/task) and likely APITimeout retries during the P3 sweep. P2+P3 raises EX to **66%** (+2 pp vs P2+prune) but at **+30.7%** tokens—worse than P2+prune on both cost and the original P3-only failure mode.

**Semantic store vs discovery board.** P3 middleware interaction rises via `semantic_injection` events (60–80% across models) without P2's `discovery_injection` channel. Facts are shorter per bullet but DeepSeek publishes far more of them, suggesting the extractor fires on every explore outcome and the model does not reduce probe count accordingly.

**Stacking P2 and P3 does not reliably beat P2 alone.** For Gemini, combined middleware adds both fragment lists *and* semantic bullets—prompt growth without reaching P2+prune accuracy. For DeepSeek, dual injection channels inflate tokens while EX gains remain modest (+2 pp vs P2+prune).

## 7.7 Limitations

1. **Rule-based extraction only.** Facts are structural/statistical; no LLM summarisation or embedding dedup across semantically equivalent outcomes.
2. **Smoke subset (50 tasks).** Model-specific recommendations may shift on full BIRD dev.
3. ***N*=10 only.** P3 at *N*=25 not evaluated; semantic injection frequency scales with replica count.
4. **DeepSeek token anomaly.** P3-only +42.5% token increase warrants retry analysis (timeouts, longer completions) before attributing solely to middleware design.
5. **GPT P2+P3 not run.** Combined stack untested on the one model that favours P3 alone.
6. **P4 not implemented.** Phase-aware sharing and cross-model ensembles remain future work.

## 7.8 Summary and thesis implications

P3 (`P3_semantic_store`) distils explore SQL outcomes into **8–62 facts per task** (model-dependent) and injects capped semantic context before each LLM turn. Against Chapter 6's best stack (P2+prune), results split by model:

| Model | Best policy (*N*=10) | Rationale |
|-------|---------------------|-----------|
| GPT-4o mini | **P3** (not P2+prune) | +4 pp EX, −6.5% tokens vs P2+prune |
| Gemini 2.5 Flash | **P2+prune** | 76% EX; P3 70%; P2+P3 74% |
| DeepSeek V3.2 | **P2+prune** | 64% EX, lowest tokens; P3 costly |

The middleware thesis therefore closes with a **model-conditioned deployment rule**: there is no single optimal stack. Token-efficient coordination requires matching middleware layers to how each model responds to shared syntactic hints vs distilled outcome facts.

---

## Appendix: source artefacts

| Artefact | Path |
|----------|------|
| P3 batches (*N*=10) | `runs/batches/parallel_semantic_hybrid_r10_bo_*` |
| P2+P3 batches | `runs/batches/parallel_p2p3_hybrid_r10_bo_*` |
| P3 comparison report | `runs/reports/p3_vs_p2.json` |
| Comparison script | `scripts/compare_p3.py` |
| Semantic store | `src/coord/semantic_store.py` |
| Fact extractors | `src/coord/semantic_extractors.py` |

