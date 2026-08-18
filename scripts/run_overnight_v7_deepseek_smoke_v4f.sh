#!/usr/bin/env bash
# Re-run every DeepSeek 50-task (smoke) batch the paper cites on v4-flash,
# retiring the last V3.2-era numbers so the paper is single-era throughout.
#
# CONTEXT
#   All full-500 DeepSeek comparisons are already era-matched on v4-flash.
#   The only V3.2 residue is the 50-task rows in the per-policy tables
#   (P1 hit rate, prune, P3 vs P2, prompt cache, P4 suppression).
#
# ORDERING
#   Waves are ordered by how load-bearing the numbers are, so an interrupted
#   run still delivers the most valuable batches:
#     Wave 1 — P3 vs P2 stack: the model-conditioning claim ("DeepSeek is
#              actively harmed, +42.5% tokens") rests entirely on these.
#     Wave 2 — prompt cache: feeds the 64-96% cached / 32-48% billed ranges.
#     Wave 3 — P1 / prune / P4: corroborated by full-500 v4-flash data, so
#              lowest risk if they do not finish.
#
# All batches are DeepSeek, so they run sequentially to stay inside per-key
# rate limits. Estimated ~15 h total, ~$20 at list prices.
#
# NOTE: run_parallel_batch.py returns 1 whenever any task scores EX=0, so a
# non-zero rc is normal. Judge success by the written JSON, not by rc.
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$REPO_ROOT"

STAMP="${OVERNIGHT_STAMP:-$(date -u +%Y%m%d_%H%M%S)_v7_ds_smoke_v4f}"
OUT_DIR="$REPO_ROOT/runs/overnight/$STAMP"
mkdir -p "$OUT_DIR"
STATUS_FILE="$OUT_DIR/status.txt"
echo "$STAMP" > "$REPO_ROOT/runs/overnight/LATEST_V7_DS_SMOKE"

echo "overnight_stamp=$STAMP" | tee "$STATUS_FILE"
echo "started_utc=$(date -u +%Y-%m-%dT%H:%M:%SZ)" | tee -a "$STATUS_FILE"
echo "paper=draft_paper_ieee_v7 — DeepSeek smoke batches on v4-flash" | tee -a "$STATUS_FILE"

DS="--model deepseek-v3.2"
COMMON="--limit 50 --policy best_of_n"

run_one() {
  local name="$1"
  shift
  local log="$OUT_DIR/${name}.log"
  echo "[$(date -u +%H:%M:%S)] START $name" | tee -a "$STATUS_FILE"
  set +e
  uv run python -u scripts/run_parallel_batch.py "$@" >"$log" 2>&1
  local rc=$?
  set -e
  local ex
  ex=$(grep -oP 'EX:\s+\K[0-9.]+' "$log" | tail -1 || true)
  echo "[$(date -u +%H:%M:%S)] DONE  $name (rc=$rc, EX=${ex:-?})" | tee -a "$STATUS_FILE"
  return 0
}

echo "=== WAVE 1: P3 vs P2 stack (model-conditioning claim) ===" | tee -a "$STATUS_FILE"
for r in 10 25; do
  # P2 stack (fragment hints) — the comparator
  run_one "w1_fullstack_prune_r${r}_v4f" $DS $COMMON --replicas $r \
    --shared-cache --discovery-board --early-stop \
    --schema-pruning --schema-pruning-mode hybrid \
    --batch-id "fullstack_prune_r${r}_bo_v4f"
  # P3 stack (distilled facts)
  run_one "w1_semantic_hybrid_r${r}_v4f" $DS $COMMON --replicas $r \
    --shared-cache --semantic-store --early-stop \
    --schema-pruning --schema-pruning-mode hybrid \
    --batch-id "semantic_hybrid_r${r}_bo_v4f"
done

echo "=== WAVE 2: prompt cache (billing headline) ===" | tee -a "$STATUS_FILE"
run_one "w2_pc50_r25_base_v4f" $DS $COMMON --replicas 25 \
  --batch-id "pc50_r25_ds_base_v4f"
run_one "w2_pc50_r25_cached_v4f" $DS $COMMON --replicas 25 \
  --prompt-cache \
  --batch-id "pc50_r25_ds_cached_v4f"

echo "=== WAVE 3: P1 / prune / P4 (corroborated by full-500) ===" | tee -a "$STATUS_FILE"
run_one "w3_baseline_r25_v4f" $DS $COMMON --replicas 25 \
  --batch-id "baseline_r25_bo_v4f"
run_one "w3_p1_r25_v4f" $DS $COMMON --replicas 25 \
  --shared-cache \
  --batch-id "p1_r25_bo_v4f"
run_one "w3_suppress_iso_r25_v4f" $DS $COMMON --replicas 25 \
  --prompt-cache --explore-suppressor \
  --batch-id "suppress_iso_r25_bo_v4f"
run_one "w3_schema_prune_iso_r25_v4f" $DS $COMMON --replicas 25 \
  --schema-pruning --schema-pruning-mode hybrid \
  --batch-id "schema_prune_iso_r25_bo_v4f"
run_one "w3_baseline_r10_v4f" $DS $COMMON --replicas 10 \
  --batch-id "baseline_r10_bo_v4f"
run_one "w3_schema_prune_iso_r10_v4f" $DS $COMMON --replicas 10 \
  --schema-pruning --schema-pruning-mode hybrid \
  --batch-id "schema_prune_iso_r10_bo_v4f"
run_one "w3_suppress_iso_r10_v4f" $DS $COMMON --replicas 10 \
  --prompt-cache --explore-suppressor \
  --batch-id "suppress_iso_r10_bo_v4f"

echo "=== Completeness check ===" | tee -a "$STATUS_FILE"
uv run python - <<'PY' 2>&1 | tee -a "$STATUS_FILE"
import json, glob
for p in sorted(glob.glob('runs/batches/parallel_*_v4f_deepseek*.json')):
    d = json.load(open(p))
    if d.get('task_count', 0) > 100:
        continue
    print(f"{d.get('batch_id'):34s} r{d.get('n_replicas'):<3} "
          f"tasks={d.get('task_count')} apifail={d.get('api_failure_count')} "
          f"EX={d.get('ex_accuracy_pct')} "
          f"hit={d.get('avg_cache_hit_rate_pct')} "
          f"cached%={d.get('batch_cached_prompt_pct')}")
PY

echo "finished_utc=$(date -u +%Y-%m-%dT%H:%M:%SZ)" | tee -a "$STATUS_FILE"
