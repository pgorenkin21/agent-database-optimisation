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

### Next (Month 1 week 3–4)

Parallel agents on the same task, redundancy analysis scripts.
