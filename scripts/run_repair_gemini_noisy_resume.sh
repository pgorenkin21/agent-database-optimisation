#!/usr/bin/env bash
# Resume Gemini noisy repairs from step 3 (compose r10 + P3 already merged).
# Steps: baseline N=25 leftovers → compose N=25 → compose N=10 rep2
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$REPO_ROOT"
BATCH="$REPO_ROOT/runs/batches"

STAMP="${OVERNIGHT_STAMP:-$(cat "$REPO_ROOT/runs/overnight/LATEST_GEMINI_NOISY_REPAIR")}"
OUT_DIR="$REPO_ROOT/runs/overnight/$STAMP"
mkdir -p "$OUT_DIR/backups"
STATUS_FILE="$OUT_DIR/status.txt"
echo "$STAMP" > "$REPO_ROOT/runs/overnight/LATEST_GEMINI_NOISY_REPAIR"

echo "[$(date -u +%H:%M:%S)] RESUME steps 3–5 (baseline r25, compose r25, compose r10 rep2)" | tee -a "$STATUS_FILE"

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
  shift
  local repair=""
  if [[ $# -gt 0 ]]; then
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

echo "=== Repair compose N=25 Gemini (~30 failed) ===" | tee -a "$STATUS_FILE"
run_one gemini_compose_r25_failed \
  "${COMPOSE_FLAGS[@]}" \
  --replicas 25 \
  --subset-file configs/subsets/gemini_compose_full500_r25_failed.txt \
  --batch-id compose_full500_r25_gemini_repair
merge_repair \
  "$BATCH/parallel_compose_full500_r25_gemini-2.5-flash_r25_best_of_n_p1_cache_promptcache_early_stop_schema_prune_p4suppress.json" \
  "$BATCH"/parallel_compose_full500_r25_gemini_repair_gemini-2.5-flash_*.json

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
