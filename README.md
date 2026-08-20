# Prompt Cost Optimisation for Speculative Parallelism in Text-to-SQL

Schema pruning, a semantic fact store, and cache-stable structure for parallel text-to-SQL agents.

**Pavel Gorenkin** · MSc Project 2025/26 · School of Electronic Engineering and Computer Science, Queen Mary University of London

This is the supporting material for the dissertation research paper. It holds the agent harness, the three prompt-layer methods the paper evaluates, the experiment runners, the analysis that produces every number in the paper, and the scripts that build the paper's figures and tables.

---

## What is here

| Path | What it is |
|---|---|
| `src/agent/` | the ReAct agent loop, schema pruning, prompt construction, and the cache-stable loop |
| `src/coord/` | replica coordination, the semantic fact store, and the analysis modules |
| `src/llm/` | provider clients, the model registry, retry and cost accounting |
| `src/db/`, `src/bird/`, `src/eval/` | SQLite execution, BIRD task loading, execution-accuracy scoring |
| `src/logging/trace.py` | the append-only JSONL trace writer that every measurement is drawn from |
| `scripts/` | experiment runners, analysis, and figure/table generation (see below) |
| `tests/` | 191 tests covering the mechanisms the paper claims |
| `configs/` | `default.yaml`, the model registry `models.yaml`, and task subsets |
| `runs/reports/` | the analysis outputs, including `v8_numbers.txt`, which is the source of every table |
| `runs/batches/` | per-batch result summaries, one JSON per experiment cell *(submission zip only)* |
| `thesis/paper drafts/` | the paper source, the reflective essay, and the presentation deck |

### The scripts that matter

These twelve scripts are the ones the paper depends on. The rest of `scripts/` is experiment plumbing from earlier waves.

| Script | Does |
|---|---|
| `run_parallel_batch.py` | the experiment runner: N replicas on a task set, with any combination of methods |
| `run_v8_matrix.sh` | the 50-task grid, four arms × three models × three replica counts |
| `run_v8_500t_r3.sh`, `run_v8_500t_r10.sh` | the full-split waves |
| `run_v8_cleanup.sh`, `run_v8_prune_fill.sh` | the re-runs that put every cell on a clean `v8_` identifier |
| `analyze_v8_results.py` | paired bootstrap intervals for all 60 cells → `runs/reports/v8_numbers.txt` |
| `analyze_schema_pruning.py` | the offline gold-table recall analysis, which calls no model |
| `v8_additivity.py` | the composition check against a multiplicative null |
| `explore_redundancy_stats.py` | duplicated exploratory SQL in absolute terms |
| `make_v8_figures.py` | the charts, at column size or `--slides` for presentation size. Seven of the eight rebuild from the batch summaries; `fig2_cached_by_turn` needs the per-replica traces and is shipped pre-rendered |
| `make_v8_appendix_tables.py` | the appendix result matrices |
| `assemble_v9.py` | splices `v9_sections/*.md` into the submitted LaTeX and the Overleaf bundle |

---

## Running it

### Prerequisites

- Python 3.12 and [uv](https://docs.astral.sh/uv/)
- API keys for whichever providers you run

```bash
uv sync --all-groups
cp .env.example .env      # then set OPENAI_API_KEY, GEMINI_API_KEY, DEEPSEEK_API_KEY
uv run python scripts/check_setup.py
uv run pytest -q          # 191 passed
```

### The BIRD dataset is not included

BIRD mini-dev is roughly 5 GB and carries its own licence, so it is not redistributed here. Fetch it once:

```bash
bash scripts/download_bird.sh
```

That writes `data/bird/mini_dev/`, the path `configs/default.yaml` expects. **Everything below that only reads results works without it.** Only running agents needs the databases.

### Why there is no executable

The project is a set of experiments against commercial LLM APIs, not an application, so there is nothing meaningful to package as a binary.

**Reproduce a run end to end** (needs the dataset and an OpenAI key, costs a few cents):

```bash
uv run python scripts/run_parallel_batch.py \
    --subset-file configs/subsets/demo_one_task.txt \
    --replicas 5 --model gpt-4o-mini \
    --schema-pruning --schema-pruning-mode hybrid \
    --semantic-store --prompt-cache
```

One question, five replicas, all three methods. Expect execution accuracy 100%, the schema pruned from 11,847 to 6,354 characters, and roughly 87% of input tokens served from cache. It writes a batch summary to `runs/batches/` and one JSONL trace per replica to `runs/`.

**Regenerate every number in the paper** from the batch summaries, no API calls and no dataset needed:

```bash
uv run python scripts/analyze_v8_results.py       # -> runs/reports/v8_numbers.txt
uv run python scripts/v8_additivity.py            # the composition check
uv run python scripts/make_v8_figures.py          # -> thesis/figures/
uv run python scripts/make_v8_appendix_tables.py  # -> the appendix tables
```

`analyze_v8_results.py` runs in strict mode by default: only batches carrying a clean `v8_` identifier are admitted, and any batch that completed under 90% of its tasks is refused rather than reported on a shrunken sample.

---

## Tracing a claim back to its evidence

Every quantitative claim follows the same path: **paper → `v8_numbers.txt` → a batch JSON → the script that produced it.**

| Claim in the paper | Batch identifier | Produced by |
|---|---|---|
| Baselines (§3.3) | `v8_p0_*` | `run_v8_cleanup.sh`, `run_v8_500t_r3.sh`, `run_v8_500t_r10.sh` |
| Schema pruning (§6.1) | `v8_prune_*` | `run_v8_matrix.sh`, `run_v8_prune_fill.sh` |
| Offline recall (§6.1) | n/a, offline | `analyze_schema_pruning.py` |
| Fact store (§6.2) | `v8_p3_*` | `run_v8_matrix.sh` |
| Prompt cache (§6.3) | `v8_pc_*` | `run_v8_matrix.sh`, `run_v8_cleanup.sh` |
| Composition (§6.4) | `v8_comp_*` | `run_v8_matrix.sh`, `run_v8_500t_r3.sh` |
| All intervals | n/a | `analyze_v8_results.py` |

Identifiers follow `v8_[arm]_[scale]_r[N]`, where scale is `50t` or `500t` and N is 3, 10 or 25 at 50 tasks and 3 or 10 at 500.

