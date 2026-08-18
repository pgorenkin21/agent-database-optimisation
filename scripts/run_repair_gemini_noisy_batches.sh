#!/usr/bin/env bash
# Repair noisy Gemini full-500 batches (API / DNS / timeout failures), then merge.
#
# Order: small → large (paper-critical high-N first among the small set).
#   1) compose N=10          (~9)
#   2) P3 N=10               (~7)
#   3) baseline N=25 leftover (~2)
#   4) compose N=25          (~32)
#   5) compose N=10 rep2     (~272)
#
# Usage:
#   nohup bash scripts/run_repair_gemini_noisy_batches.sh \
#     > runs/overnight/<stamp>/driver.log 2>&1 &
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$REPO_ROOT"
BATCH="$REPO_ROOT/runs/batches"

STAMP="${OVERNIGHT_STAMP:-$(date -u +%Y%m%d_%H%M%S)_gemini_noisy_repair}"
OUT_DIR="$REPO_ROOT/runs/overnight/$STAMP"
mkdir -p "$OUT_DIR/backups"
STATUS_FILE="$OUT_DIR/status.txt"
echo "$STAMP" > "$REPO_ROOT/runs/overnight/LATEST_GEMINI_NOISY_REPAIR"

echo "overnight_stamp=$STAMP" | tee "$STATUS_FILE"
echo "started_utc=$(date -u +%Y-%m-%dT%H:%M:%SZ)" | tee -a "$STATUS_FILE"
echo "paper=draft_paper_ieee_v5 — repair noisy Gemini full-500 API failures" | tee -a "$STATUS_FILE"

run_one() {
  local name="$1"
  shift
  local log="$OUT_DIR/${name}.log"
  echo "[$(date -u +%H:%M:%S)] START $name" | tee -a "$STATUS_FILE"
  set +e
  uv run python -u scripts/run_parallel_batch.py "$@" >"$log" 2>&1
  local rc=$?
  set -e
  echo "[$(date -u +%H:%M:%S)] DONE  $name (rc=$rc; check JSON)" | tee -a "$STATUS_FILE"
  return 0
}

merge_repair() {
  local original="$1"
  # Remaining args are a glob pattern (unquoted by caller so shell expands).
  shift
  local repair=""
  if [[ $# -gt 0 ]]; then
    # Prefer newest among expanded matches
    repair=$(ls -1t "$@" 2>/dev/null | head -1 || true)
  fi
  if [[ -z "${repair:-}" || ! -f "$repair" ]]; then
    echo "[$(date -u +%H:%M:%S)] WARN no repair JSON matched — skip merge" | tee -a "$STATUS_FILE"
    return 0
  fi
  echo "[$(date -u +%H:%M:%S)] MERGE $repair -> $original" | tee -a "$STATUS_FILE"
  uv run python -u scripts/merge_parallel_batch_repair.py \
    --original "$original" \
    --repair "$repair" \
    --backup-dir "$OUT_DIR/backups" | tee -a "$STATUS_FILE"
}

COMPOSE_FLAGS=(
  --model gemini-2.5-flash
  --policy best_of_n
  --shared-cache
  --early-stop
  --prompt-cache
  --schema-pruning
  --schema-pruning-mode hybrid
  --explore-suppressor
  --inter-task-delay 2.5
)

# --- 1) compose N=10 (~9) ---
echo "=== Repair compose N=10 Gemini (~9 failed) ===" | tee -a "$STATUS_FILE"
run_one gemini_compose_r10_failed \
  "${COMPOSE_FLAGS[@]}" \
  --replicas 10 \
  --subset-file configs/subsets/gemini_compose_full500_r10_failed.txt \
  --batch-id compose_full500_r10_gemini_repair
merge_repair \
  "$BATCH/parallel_compose_full500_r10_gemini-2.5-flash_r10_best_of_n_p1_cache_promptcache_early_stop_schema_prune_p4suppress.json" \
  "$BATCH"/parallel_compose_full500_r10_gemini_repair_gemini-2.5-flash_*.json

# --- 2) P3 N=10 (~7) ---
echo "=== Repair P3 N=10 Gemini (~7 failed) ===" | tee -a "$STATUS_FILE"
run_one gemini_p3_r10_failed \
  --model gemini-2.5-flash \
  --replicas 10 \
  --policy best_of_n \
  --shared-cache \
  --early-stop \
  --semantic-store \
  --schema-pruning \
  --schema-pruning-mode hybrid \
  --inter-task-delay 2.5 \
  --subset-file configs/subsets/gemini_p3_full500_r10_failed.txt \
  --batch-id p3_full500_r10_gemini_repair
merge_repair \
  "$BATCH/parallel_p3_full500_r10_gemini-2.5-flash_r10_best_of_n_p1_cache_p3_semantic_early_stop_schema_prune.json" \
  "$BATCH"/parallel_p3_full500_r10_gemini_repair_gemini-2.5-flash_*.json

# --- 3) baseline N=25 leftovers (~2) ---
echo "=== Repair baseline N=25 Gemini leftovers (~2 failed) ===" | tee -a "$STATUS_FILE"
run_one gemini_baseline_r25_failed3 \
  --model gemini-2.5-flash \
  --replicas 25 \
  --policy best_of_n \
  --inter-task-delay 2.5 \
  --subset-file configs/subsets/gemini_baseline_full500_r25_failed3.txt \
  --batch-id baseline_full500_r25_gemini_repair3
merge_repair \
  "$BATCH/parallel_baseline_full500_r25_gemini-2.5-flash_r25_best_of_n.json" \
  "$BATCH"/parallel_baseline_full500_r25_gemini_repair3_gemini-2.5-flash_*.json

# --- 4) compose N=25 (~32) ---
echo "=== Repair compose N=25 Gemini (~32 failed) ===" | tee -a "$STATUS_FILE"
run_one gemini_compose_r25_failed \
  "${COMPOSE_FLAGS[@]}" \
  --replicas 25 \
  --subset-file configs/subsets/gemini_compose_full500_r25_failed.txt \
  --batch-id compose_full500_r25_gemini_repair
merge_repair \
  "$BATCH/parallel_compose_full500_r25_gemini-2.5-flash_r25_best_of_n_p1_cache_promptcache_early_stop_schema_prune_p4suppress.json" \
  "$BATCH"/parallel_compose_full500_r25_gemini_repair_gemini-2.5-flash_*.json

# --- 5) compose N=10 rep2 (~272) ---
echo "=== Repair compose N=10 rep2 Gemini (~272 failed) ===" | tee -a "$STATUS_FILE"
run_one gemini_compose_r10_rep2_failed \
  "${COMPOSE_FLAGS[@]}" \
  --replicas 10 \
  --subset-file configs/subsets/gemini_compose_full500_r10_rep2_failed.txt \
  --batch-id compose_full500_r10_rep2_gemini_repair
merge_repair \
  "$BATCH/parallel_compose_full500_r10_rep2_gemini-2.5-flash_r10_best_of_n_p1_cache_promptcache_early_stop_schema_prune_p4suppress.json" \
  "$BATCH"/parallel_compose_full500_r10_rep2_gemini_repair_gemini-2.5-flash_*.json

echo "finished_utc=$(date -u +%Y-%m-%dT%H:%M:%SZ)" | tee -a "$STATUS_FILE"
echo "[$(date -u +%H:%M:%S)] ALL REPAIRS DONE — see $STATUS_FILE" | tee -a "$STATUS_FILE"
