# Coordinating Speculative Agent Workloads Over Data Backends

MSc project: middleware coordination policies for redundancy elimination in multi-agent BIRD text-to-SQL workloads.

## Phase 0 - Project scaffold

### Prerequisites

- Python 3.10+ (3.12 recommended; see `.python-version`)
- [uv](https://docs.astral.sh/uv/)
- `wget` and `unzip`
- API keys for models you run (see below)

### Setup (uv)

```bash
cd "/workspaces/Cursor Agent Database Optimisation"

uv sync --all-groups
cp .env.example .env
# Set OPENAI_API_KEY, GEMINI_API_KEY, DEEPSEEK_API_KEY (all three for full eval matrix)
uv run python scripts/check_setup.py
uv run pytest -q
```

### LLM models

Configured in [`configs/models.yaml`](configs/models.yaml) and referenced from [`configs/default.yaml`](configs/default.yaml):

| Registry key | Provider | API model ID | Env var |
|--------------|----------|--------------|---------|
| `gpt-4o-mini` | OpenAI | `gpt-4o-mini` | `OPENAI_API_KEY` |
| `gemini-2.5-flash` | Google | `gemini-2.5-flash` | `GEMINI_API_KEY` or `GOOGLE_API_KEY` |
| `deepseek-v3.2` | DeepSeek | `deepseek-chat` (V3.2) | `DEEPSEEK_API_KEY` |

- **Default agent:** `llm.default` (currently `gpt-4o-mini`)
- **Thesis eval matrix:** `llm.eval_models` lists all three

Change the default for a single run (Phase 1+): set `llm.default` or pass `--model gemini-2.5-flash`.

DeepSeek uses the [OpenAI-compatible API](https://api-docs.deepseek.com/) at `https://api.deepseek.com`.

If `gemini-2.5-flash` is unavailable in your region, edit `api_model` in `configs/models.yaml`.

### Download BIRD mini-dev (default)

Use **mini-dev first** (500 tasks, 11 databases). Switch to full dev only when the harness is stable.

```bash
chmod +x scripts/download_bird.sh
./scripts/download_bird.sh
uv run python scripts/check_setup.py
```

Expected paths:

```
data/bird/mini_dev/mini_dev_sqlite.json
data/bird/mini_dev/dev_databases/<db_id>/sqlite/*.sqlite
```

**Cheap smoke runs** (50 tasks):

```bash
uv run python scripts/list_question_ids.py --limit 50 > configs/subsets/smoke_50.txt
```

Set in `configs/default.yaml`:

```yaml
bird:
  subset_file: configs/subsets/smoke_50.txt
  subset_limit: 0
```

Or keep `subset_limit: 50` with no subset file (first 50 tasks in JSON order).

### Full BIRD dev (later)

```bash
chmod +x scripts/download_bird_full_dev.sh
./scripts/download_bird_full_dev.sh
uv run python scripts/check_setup.py --config configs/full_dev.yaml
```

### Configuration

| Setting | Default (mini-dev) | Notes |
|---------|-------------------|--------|
| `bird.split` | `mini_dev` | `full_dev` in `configs/full_dev.yaml` |
| `bird.tasks_json` | `mini_dev_sqlite.json` | Task list + gold SQL |
| `bird.subset_limit` | `50` | `0` = all 500 mini-dev tasks |
| `use_evidence` | `true` | Gold evidence in prompts |
| `llm.model` | `gpt-4o-mini` | Primary model |

### Repository layout

```
configs/default.yaml      # mini-dev paths (default)
configs/full_dev.yaml       # full dev paths
data/bird/mini_dev/         # downloaded mini-dev (gitignored)
data/bird/full_dev/         # full dev when needed (gitignored)
```

### Phase 1a — Gold SQL and execution accuracy (done)

Runs use **SQLite** (same as official BIRD `evaluation.py`), not DuckDB, so gold SQL with `IIF` and other SQLite syntax executes correctly.

```bash
# One task (default: first in JSON)
uv run python scripts/run_one_gold.py --question-id 1471

# Sanity: gold SQL vs itself on 20 tasks (expect 20/20 EX=1)
uv run python scripts/run_gold_sanity.py --limit 20

# Wrong SQL on purpose (expect EX=0)
uv run python scripts/run_one_gold.py --question-id 1471 --predicted-sql "SELECT 1"
```

### Phase 1b — JSONL traces (done)

Each `run_one_gold.py` run writes `runs/<run_id>.jsonl` with events:

| Event | Fields |
|-------|--------|
| `run_start` | `question_id`, `db_id`, `policy` (P0), `seed`, `bird_split` |
| `sql_execute` | `sql_raw`, `sql_role`, `latency_ms`, `row_count`, `result_sample`, `error` |
| `run_end` | `ex_correct`, `predicted_sql`, `gold_sql`, `wall_clock_ms` |

```bash
uv run python scripts/run_one_gold.py --question-id 1471
uv run python scripts/inspect_trace.py runs/<run_id>.jsonl
```

### Phase 1c — Single agent (done)

Tool-calling agent: `execute_sql` (explore) and `submit_sql` (final answer). Traces in `runs/<run_id>.jsonl`.

```bash
uv run python scripts/run_one_agent.py --question-id 1471 --model gpt-4o-mini
uv run python scripts/run_one_agent.py --index 0 --model deepseek-v3.2
uv run python scripts/run_one_agent.py --question-id 1471 --model gemini-2.5-flash
uv run python scripts/inspect_trace.py runs/<run_id>.jsonl
```

Models: registry keys from `configs/models.yaml` (`gpt-4o-mini`, `gemini-2.5-flash`, `deepseek-v3.2`).

### Batch runs

```bash
# Uses bird.subset_limit (default 50) from configs/default.yaml
uv run python scripts/run_batch.py --model gpt-4o-mini

# Custom limit or subset file
uv run python scripts/run_batch.py --model gpt-4o-mini --limit 5
uv run python scripts/list_question_ids.py --limit 10 > configs/subsets/smoke_10.txt
uv run python scripts/run_batch.py --subset-file configs/subsets/smoke_10.txt --limit 0

# Preview task list without API calls
uv run python scripts/run_batch.py --dry-run --limit 5
```

Outputs: `runs/batches/batch_<id>_<model>.csv` and `.json` plus per-task traces in `runs/<run_id>.jsonl`.

### Phase 2 — Parallel agents (in progress)

Run **N replicas** on the same task, coordinate the final answer, and measure redundancy.

**Policies** (`src/coord/policies.py`):

| Policy | Behaviour |
|--------|-----------|
| `best_of_n` | Pick any correct replica (fewest turns); else shortest submission |
| `first_success` | First replica to finish with EX=1 |
| `majority_vote` | Largest result-set bucket; prefer correct within bucket |

Per-replica traces use `policy=P0_parallel` (or `P0_early_stop` with `--early-stop`) and `agent_id=agent_0..N-1`. A coordinator trace is written to `runs/coord_<id>.jsonl`.

```bash
# One task, 3 replicas
uv run python scripts/run_parallel_one.py --question-id 1471 --replicas 3 --policy best_of_n

# Early stopping: cancel siblings when one replica gets EX=1 (use best_of_n for apples-to-apples vs P0)
uv run python scripts/run_parallel_one.py --question-id 1471 --replicas 3 --early-stop --policy best_of_n

# Batch (smoke subset)
uv run python scripts/run_parallel_batch.py --model gemini-2.5-flash --limit 5 --replicas 3

# Batch with early stopping (apples-to-apples: same policy as P0 baseline)
uv run python scripts/run_parallel_batch.py --model gpt-4o-mini --limit 50 --replicas 10 \
  --early-stop --policy best_of_n --batch-id earlystop_r10_bo

# Compare early stop vs P0 baseline reports
uv run python scripts/compare_early_stop.py --early-stop-batch-id earlystop_r10_bo

# P1 shared SQL result cache (explore-query dedup across replicas)
uv run python scripts/run_parallel_batch.py --model gpt-4o-mini --limit 5 --replicas 3 \
  --shared-cache --policy best_of_n --batch-id p1_smoke_test

# Compare P1 vs P0 baseline reports + regenerate Chapter 4 draft
uv run python scripts/compare_p1.py
uv run python scripts/generate_chapter4_draft.py

# P2 shared discovery board (sub-expression propagation via prompt injection)
uv run python scripts/run_parallel_batch.py --model gpt-4o-mini --limit 5 --replicas 3 \
  --discovery-board --policy best_of_n --batch-id p2_smoke_test

# Compare P2 vs P0 baseline reports + regenerate Chapter 5 draft
uv run python scripts/compare_p2.py
uv run python scripts/generate_chapter5_draft.py

# Compare P3 vs P2 full stack+prune + recommendations
uv run python scripts/compare_p3.py

# P3 semantic store (rule-based facts, bounded prompt injection)
uv run python scripts/run_parallel_batch.py --model gpt-4o-mini --limit 5 --replicas 3 \
  --semantic-store --shared-cache --policy best_of_n --batch-id p3_smoke_test

# Semantic schema pruning (TF-IDF on column descriptions; modes: keyword | semantic | hybrid)
uv run python scripts/analyze_schema_pruning.py --mode semantic
uv run python scripts/run_parallel_batch.py --model gpt-4o-mini --limit 5 --replicas 3 \
  --schema-pruning --schema-pruning-mode hybrid --batch-id schema_semantic_hybrid

# Middleware stack (P0/P1/P2/P1+P2/early stop/full stack) + Chapter 6 synthesis
uv run python scripts/compare_middleware_stack.py
uv run python scripts/compare_p1p2.py
uv run python scripts/generate_chapter6_draft.py

# Full stack: P1 cache + P2 discovery + early stop (all eval models, N=25)
uv run python scripts/run_full_stack_sweep.py --dry-run
uv run python scripts/run_full_stack_sweep.py

# Dry-run task list
uv run python scripts/run_parallel_batch.py --dry-run --limit 5 --replicas 3
```

**Redundancy metrics** (in coord trace + batch JSON): duplicate explore SQL, token overhead ratio vs cheapest replica, replicas with EX=1.

### Eval matrix (all models × variations)

Run every model in `llm.eval_models` for each variation. Within a variation, all models run **concurrently** (default 3 workers); variations run one after another.

```bash
# All 3 models × single-agent + parallel (smoke-50 from config)
uv run python scripts/run_eval_matrix.py

# Preview the 6 jobs without API calls
uv run python scripts/run_eval_matrix.py --dry-run --limit 5

# Custom subset, sequential model runs
uv run python scripts/run_eval_matrix.py --limit 10 --sequential

# Single-agent only
uv run python scripts/run_eval_matrix.py --variations single
```

Writes per-model batch JSON/CSV plus a manifest at `runs/batches/matrix_<id>.json`.

### Phase 2a — Baseline redundancy report (P0)

Independent parallel replicas (`P0_parallel`) with no shared middleware. Measures query overlap, sub-expression duplication, token overhead, and wall-clock time for thesis Chapter 2.

```bash
# Run replica-count sweep (3, 10, 25) on smoke subset — expensive at r=25
uv run python scripts/run_baseline_sweep.py --model gpt-4o-mini --dry-run
uv run python scripts/run_baseline_sweep.py --model gpt-4o-mini --replicas 3 10 25

# Analyse existing parallel batches → runs/reports/baseline_<id>.md + .json
uv run python scripts/analyze_baseline_redundancy.py \
  --sweep-id 20260610_124547_2f8250 --model gpt-4o-mini --report-id smoke_r3
```

Metrics: total/unique explore SQL (string + AST), sub-expression overlap (sqlglot fragments), explore redundancy %, token overhead ratio, coordination wall-clock.

```bash
# Plot scaling curves for all three model reports → runs/reports/plots/*.png
uv run python scripts/plot_baseline_redundancy.py

# Custom reports or output directory
uv run python scripts/plot_baseline_redundancy.py \
  runs/reports/baseline_gemini_baseline_full.json \
  --out-dir runs/reports/plots/gemini
```

### Phase 2a — Chapter 2 draft (P0 write-up)

Generate a thesis-ready Chapter 2 markdown from the three baseline report JSON files:

```bash
uv run python scripts/generate_chapter2_draft.py
# → thesis/chapter2_baseline_redundancy.md
```

Figures are embedded from `runs/reports/plots/`. Re-run `plot_baseline_redundancy.py` after updating reports.

**Not yet built:** P4 richer coordination (phase-aware sharing, cross-model ensembles). P1 shared SQL cache (`--shared-cache`), P2 discovery board (`--discovery-board`), and **P3 semantic store** (`--semantic-store`) are available on parallel batch scripts. Schema pruning supports `--schema-pruning-mode keyword|semantic|hybrid`.
