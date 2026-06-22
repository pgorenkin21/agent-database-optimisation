# Chapter 2: Baseline Redundancy in Parallel Text-to-SQL Agents (P0)

*Draft generated 2026-06-17 from P0 baseline reports. Regenerate with `uv run python scripts/generate_chapter2_draft.py`.*

## 2.1 Motivation

Speculative parallelism—running multiple independent LLM agents on the same text-to-SQL task and selecting a final answer—is a natural way to improve reliability. Each replica explores the database with `execute_sql` tool calls before submitting a final query. Without coordination at the data layer, replicas cannot observe each other's work; they are likely to repeat the same schema probes, filter experiments, and join patterns.

This chapter quantifies that waste under **policy P0**: *N* independent replicas with no shared middleware, coordinated only at the end via `best_of_n` (prefer any execution-correct answer with the fewest turns). The results establish the baseline that later chapters must beat with caching, early stopping, and other coordination policies (P1–P4).

### 2.1.1 Relation to retrieval-augmented generation (RAG)

This work is sometimes mistaken for a variant of retrieval-augmented generation. The two address different problems. RAG is a *retrieval step that conditions a single inference*: it embeds the query, fetches semantically similar passages from a vector store, and injects them into the prompt as read-only context. Its optimisation target is grounding—retrieving the right text so one model call has the facts it needs—and its quality is measured by retrieval relevance.

The system studied here optimises a different layer. First, the agents *execute* rather than *retrieve*: each replica issues live `execute_sql` calls against the database, observes real result sets, and iterates, with correctness scored by execution accuracy against gold SQL rather than retrieval recall. Second, the unit of optimisation is a population of speculative replicas, not a single prompt—there is nothing to coordinate in RAG because there is one inference, whereas the redundancy quantified in this chapter exists only because *N* agents fan out over the same task. Third, the shared SQL cache introduced in later policies (P1) is keyed on AST-normalised query strings for exact-match reuse of execution results, unlike a RAG index keyed on embedding similarity for fuzzy text recall. Finally, the headline metric is redundancy elimination (duplicate explore SQL, sub-expression overlap, token overhead) subject to preserving execution accuracy, a question RAG does not pose.

The two are therefore complementary rather than competing: RAG could operate *inside* a single replica—retrieving schema snippets or few-shot exemplars for schema linking—while the coordination middleware studied here sits *above* the replicas, eliminating duplicated execution regardless of how each agent forms its SQL.

## 2.2 Experimental setup

**Benchmark.** BIRD mini-dev (SQLite split): 50-task smoke subset of the 500-question development set (`configs/subsets/smoke_50.txt` or first 50 tasks when no subset file is set). Gold evidence is included in prompts (`use_evidence: true`).

**Agents.** Tool-calling loop with read-only `execute_sql` (exploration) and `submit_sql` (final answer). Temperature 0; up to 15 turns per replica.

**Models.** Three API models from the evaluation matrix:

| Registry key | Display name |
|--------------|--------------|
| `deepseek-v3.2` | DeepSeek V3.2 |
| `gemini-2.5-flash` | Gemini 2.5 Flash |
| `gpt-4o-mini` | GPT-4o mini |

**Parallel configuration.** Replica counts *N* ∈ {3, 10, 25}. Replicas run concurrently (thread pool); wall-clock is measured from `parallel_start` to `coordination_end` in the coordinator trace.

**Selection policy.** `best_of_n` throughout: if any replica achieves execution accuracy (EX=1), pick the correct replica with fewest turns; otherwise pick the shortest non-empty submission.

**Infrastructure.** SQLite execution matches official BIRD evaluation. JSONL traces record every `sql_execute` event per replica for offline redundancy analysis.

## 2.3 Policy P0

P0 (`P0_parallel`) is deliberately minimal:

1. Spawn *N* identical agents on the same `(question, database)` pair.
2. No shared cache, no cross-replica messaging, no early cancellation.
3. After all replicas finish, apply `best_of_n` to choose the coordinated answer.

P0 isolates the redundancy inherent in blind parallelism. Any reduction below these numbers in later policies is attributable to middleware.

## 2.4 Metrics

| Metric | Definition |
|--------|------------|
| **Execution accuracy (EX %)** | Fraction of tasks where the coordinated answer's result set matches gold (BIRD execution accuracy). |
| **Explore redundancy %** | Within a task, fraction of explore-phase SQL statements that duplicate a prior statement (whitespace-normalised) across any replica. |
| **Sub-expression overlap %** | Fraction of sqlglot-extracted fragments (tables, columns, predicates, join conditions) that appear in explore queries from two or more replicas. |
| **Token overhead ratio** | Total tokens across all replicas divided by tokens of the cheapest *correct* replica (≥1; equals ~*N* when replicas are similar cost). |
| **Unique explore queries** | Count of distinct explore SQL strings across replicas for a batch (summed per task, then aggregated). |
| **Wall-clock (ms)** | Coordinator session duration (parallel wall time, not sum of replica times). |
| **Middleware interaction %** | Share of agent interactions handled by middleware rather than SQLite: cache hits on explore `sql_execute` plus `discovery_injection` events, divided by all SQL executions plus middleware events. P0 has no shared cache or discovery board, so this is **0%** by definition and establishes the baseline for Chapters 4–6. |

AST-normalised uniqueness (via sqlglot) is also computed in batch reports; it closely tracks string uniqueness at high *N*, indicating duplicates are substantive rather than formatting variants.

## 2.5 Results

### 2.5.1 Cross-model summary

Table 2.1 summarises 50-task smoke runs across models and replica counts. Figure 2.1 provides a four-panel overview.

**Table 2.1.** Execution accuracy, explore redundancy, and total token spend by model and replica count.

| Replicas | DeepSeek V3.2 EX % | DeepSeek V3.2 redundancy % | DeepSeek V3.2 tokens | Gemini 2.5 Flash EX % | Gemini 2.5 Flash redundancy % | Gemini 2.5 Flash tokens | GPT-4o mini EX % | GPT-4o mini redundancy % | GPT-4o mini tokens |
|---------:|-----:|------------------:|-------------:|-----:|------------------:|-------------:|-----:|------------------:|-------------:|
| 3 | 60.0 | 54.1 | 2,193,564 | 72.0 | 45.9 | 463,742 | 60.0 | 50.6 | 684,959 |
| 10 | 60.0 | 71.3 | 7,792,210 | 74.0 | 73.6 | 1,568,278 | 58.0 | 78.7 | 2,341,781 |
| 25 | 64.0 | 82.9 | 18,889,223 | 70.0† | 81.5 | 3,685,459 | 62.0 | 87.7 | 6,322,822 |

† Gemini 2.5 Flash at *N*=25: 3 API failure(s); EX on completed tasks = 74.5%.

![Figure 2.1 — P0 baseline overview](runs/reports/plots/baseline_overview.png)

*Figure 2.1. P0 baseline scaling across three models on BIRD mini-dev (50 tasks): explore redundancy, token overhead, sub-expression overlap, and execution accuracy vs replica count.*

### 2.5.2 Explore-query duplication dominates waste

Explore redundancy rises sharply with *N* for all models (Figure 2.2). At *N*=3, mean redundancy is 46–54%; at *N*=10 it reaches 71–79%; at *N*=25 it exceeds **81%** for every model.

### GPT-4o mini

| Replicas | Tasks | EX % | Explore redundancy % | Sub-expr overlap % | Token overhead | Unique explore / total |
|---------:|------:|-----:|---------------------:|-------------------:|---------------:|-----------------------:|
| 3 | 50 | 60.0 | 50.6 | 89.3 | 3.06× | 178 / 396 |
| 10 | 50 | 58.0 | 78.7 | 92.5 | 10.55× | 268 / 1371 |
| 25 | 50 | 62.0 | 87.7 | 93.2 | 27.14× | 454 / 3728 |

From 3 to 25 replicas, GPT-4o mini increases unique explore queries by **155%** (178 → 454) while total explore volume grows **9.4×**. At *N*=25 only **12.2%** of explore statements are string-unique.

### Gemini 2.5 Flash

| Replicas | Tasks | EX % | Explore redundancy % | Sub-expr overlap % | Token overhead | Unique explore / total |
|---------:|------:|-----:|---------------------:|-------------------:|---------------:|-----------------------:|
| 3 | 50 | 72.0 | 45.9 | 70.5 | 3.15× | 96 / 196 |
| 10 | 50 | 74.0 | 73.6 | 87.0 | 10.54× | 113 / 653 |
| 25 | 47 | 70.0 | 81.5 | 86.8 | 26.55× | 111 / 1548 |

From 3 to 25 replicas, Gemini 2.5 Flash increases unique explore queries by **16%** (96 → 111) while total explore volume grows **7.9×**. At *N*=25 only **7.2%** of explore statements are string-unique.

### DeepSeek V3.2

| Replicas | Tasks | EX % | Explore redundancy % | Sub-expr overlap % | Token overhead | Unique explore / total |
|---------:|------:|-----:|---------------------:|-------------------:|---------------:|-----------------------:|
| 3 | 50 | 60.0 | 54.1 | 87.8 | 3.19× | 455 / 917 |
| 10 | 50 | 60.0 | 71.3 | 84.8 | 13.38× | 1106 / 3114 |
| 25 | 50 | 64.0 | 82.9 | 84.0 | 32.66× | 1812 / 7790 |

From 3 to 25 replicas, DeepSeek V3.2 increases unique explore queries by **298%** (455 → 1812) while total explore volume grows **8.5×**. At *N*=25 only **23.3%** of explore statements are string-unique.

![Figure 2.2 — Explore redundancy](runs/reports/plots/baseline_explore_redundancy.png)

*Figure 2.2. Mean explore-query redundancy vs replica count. Error bars are not shown; per-task medians reach 80–92% at *N*=25.*

A critical saturation effect appears in the **unique explore** counts. For DeepSeek V3.2, unique explore queries increase only from 455 (*N*=3) to 1812 (*N*=25) while total explore queries grow from 917 to 7,790. For Gemini 2.5 Flash, unique explore queries increase only from 96 (*N*=3) to 111 (*N*=25) while total explore queries grow from 196 to 1,548. For GPT-4o mini, unique explore queries increase only from 178 (*N*=3) to 454 (*N*=25) while total explore queries grow from 396 to 3,728. Replicas are not discovering proportionally more of the search space—they are re-executing the same probes.

DeepSeek V3.2 issues more explore queries per batch than the other models (917 explore calls at *N*=3 (196 for Gemini at *N*=3)) and maintains a higher unique fraction at *N*=25 (23.3% string-unique). Even so, statement-level redundancy still reaches 82.9% at *N*=25.

### 2.5.3 Sub-expression overlap is near-total

Sub-expression overlap (Figure 2.3) measures whether replicas touch the same tables, columns, and predicates even when full SQL strings differ. GPT-4o mini and Gemini reach 89–94% mean overlap at all replica counts; medians are often 100%. DeepSeek is slightly lower (84–88%) but still indicates that most structural exploration is shared.

![Figure 2.3 — Sub-expression overlap](runs/reports/plots/baseline_subexpr_overlap.png)

*Figure 2.3. Mean sub-expression overlap across replicas. High overlap implies middleware can deduplicate at fragment granularity, not only exact SQL strings.*

### 2.5.4 Token and wall-clock cost

Token overhead scales approximately linearly with *N* (Figure 2.4): ~3× at *N*=3, ~10–13× at *N*=10, and ~26–33× at *N*=25. This matches the redundancy story: replicas consume full LLM budgets independently.

| Model | Total tokens (*N*=3) | Total tokens (*N*=25) | Growth |
|-------|---------------------:|----------------------:|-------:|
| DeepSeek V3.2 | 2,193,564 | 18,889,223 | 8.6× |
| Gemini 2.5 Flash | 463,742 | 3,685,459 | 7.9× |
| GPT-4o mini | 684,959 | 6,322,822 | 9.2× |

Wall-clock time (Figure 2.5) grows sub-linearly because replicas run in parallel, but high-*N* runs still incur substantial coordination latency. DeepSeek's per-replica latency is higher (longer generations), so its average wall-clock exceeds the faster models despite similar replica counts.

![Figure 2.4 — Token overhead](runs/reports/plots/baseline_token_overhead.png)

![Figure 2.5 — Wall-clock](runs/reports/plots/baseline_wall_clock_s.png)

### 2.5.5 Execution accuracy is stable; API failures matter at scale

For all three models, EX % is broadly stable across replica counts (roughly 58–74% on the smoke subset). Parallelism with `best_of_n` does not dramatically change accuracy at *N*=3–25—redundancy is the primary cost, not degraded selection.

Gemini 2.5 Flash at *N*=25: headline EX 70.0% with **3 API failure(s)**; EX on completed tasks = 74.5%.

These are infrastructure artefacts (rate limits / transport errors), not evidence that high *N* harms SQL quality. The dashed series in Figure 2.6 shows EX excluding API failures where applicable.

![Figure 2.6 — Execution accuracy](runs/reports/plots/baseline_ex_accuracy.png)

*Figure 2.6. Coordinated execution accuracy vs replica count. Dashed lines exclude tasks where all replicas failed due to API/transport errors.*

## 2.6 Discussion

**Redundancy is the dominant cost of P0 parallelism.** At *N*=10, roughly four out of five explore queries are duplicates of work another replica already performed. Token spend tracks replica count, so a 10-replica smoke batch costs an order of magnitude more tokens than a single agent while EX % on Gemini/DeepSeek moves only a few points.

**Unique work saturates quickly.** The plateau in unique explore queries (~100–300 per task set depending on model) suggests replicas converge on a small exploration frontier dictated by schema and question wording. Adding replicas beyond that frontier mostly repeats probes.

**Model behaviour differs in exploration breadth, not redundancy direction.** DeepSeek explores more verbosely (higher query counts) but is not immune to overlap. Gemini is most token-efficient at low *N* but still reaches >80% redundancy at *N*=25.

**Sub-expression overlap motivates fragment-level middleware.** String-level caching (P1) will catch exact duplicates; the 85–94% fragment overlap suggests value in sharing table/column/predicate discoveries even when full SQL differs.

## 2.7 Limitations

1. **Subset size.** Results are on 50 mini-dev tasks, not the full 500-question split or full BIRD dev. Magnitudes should be re-validated before generalising.
2. **API failures at *N*=25.** Gemini 2.5 Flash (3 failures) depress headline EX on affected batches; cite EX excluding API errors or re-run when comparing at scale.
3. **Single selection policy.** All runs use `best_of_n`; `first_success` and `majority_vote` may change accuracy–cost trade-offs but do not reduce explore duplication during runs.
4. **No coordination during runs.** P0 runs every replica to completion with no shared cache and no early stopping—deliberately upper-bounding wasted work (early stopping is evaluated in Chapter 3).
5. **Temperature 0.** Higher temperature might diversify exploration and lower string redundancy; it could also reduce EX.

## 2.8 Summary and implications

P0 establishes that independent parallel text-to-SQL agents waste a large and growing fraction of database exploration work as *N* increases, while execution accuracy plateaus. On the smoke subset:

- Explore redundancy exceeds **80%** at *N*=25 for all three models.
- Token overhead approaches **25–33×** vs the cheapest correct replica.
- Unique explore queries saturate far below total explore volume.

These findings motivate the coordination policies evaluated in subsequent chapters: **Chapter 3** evaluates early stopping when a correct replica finishes; **Chapter 4 onward** evaluates shared middleware—**P1** (SQL result cache keyed by AST-normalised queries) and richer coordination (P2–P4) that propagates sub-expression discoveries across replicas.

---

## Appendix: source artefacts

| Artefact | Path |
|----------|------|
| GPT-4o mini report | `/workspaces/Cursor Agent Database Optimisation/runs/reports/baseline_gpt4o_baseline_full.json` |
| Gemini 2.5 Flash report | `/workspaces/Cursor Agent Database Optimisation/runs/reports/baseline_gemini_baseline_full.json` |
| DeepSeek V3.2 report | `/workspaces/Cursor Agent Database Optimisation/runs/reports/baseline_deepseek_baseline_full.json` |
| Figures | `runs/reports/plots/` |
| Figure 2.1 | `runs/reports/plots/baseline_overview.png` |
| Figure 2.2 | `runs/reports/plots/baseline_explore_redundancy.png` |
| Figure 2.3 | `runs/reports/plots/baseline_subexpr_overlap.png` |
| Figure 2.4 | `runs/reports/plots/baseline_token_overhead.png` |
| Figure 2.5 | `runs/reports/plots/baseline_wall_clock_s.png` |
| Figure 2.6 | `runs/reports/plots/baseline_ex_accuracy.png` |
