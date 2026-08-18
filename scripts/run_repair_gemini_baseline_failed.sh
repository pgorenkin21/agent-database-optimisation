#!/usr/bin/env bash
# Re-run only Gemini API-failed tasks from baseline full-500 batches,
# then merge repaired rows back into the original batch JSON/CSV.
#
# Targets (failed counts from batch error field):
#   baseline_full500_r25 gemini: 15 tasks
#   baseline_full500_r10 gemini:  2 tasks
#
# Requires Gemini credits topped up. Uses higher inter-task delay.
#
# Usage:
#   nohup bash scripts/run_repair_gemini_baseline_failed.sh \
#     > runs/overnight/<stamp>/driver.log 2>&1 &
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$REPO_ROOT"

STAMP="${OVERNIGHT_STAMP:-$(date -u +%Y%m%d_%H%M%S)_gemini_baseline_repair}"
OUT_DIR="$REPO_ROOT/runs/overnight/$STAMP"
mkdir -p "$OUT_DIR"
STATUS_FILE="$OUT_DIR/status.txt"
echo "$STAMP" > "$REPO_ROOT/runs/overnight/LATEST_GEMINI_BASELINE_REPAIR"

echo "overnight_stamp=$STAMP" | tee "$STATUS_FILE"
echo "started_utc=$(date -u +%Y-%m-%dT%H:%M:%SZ)" | tee -a "$STATUS_FILE"
echo "paper=draft_paper_ieee_v5 — repair Gemini baseline full-500 API failures" | tee -a "$STATUS_FILE"

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
  local repair="$2"
  echo "[$(date -u +%H:%M:%S)] MERGE $repair -> $original" | tee -a "$STATUS_FILE"
  uv run python -u scripts/merge_parallel_batch_repair.py \
    --original "$original" \
    --repair "$repair" \
    --backup-dir "$OUT_DIR/backups" | tee -a "$STATUS_FILE"
}

ORIG_R25="$REPO_ROOT/runs/batches/parallel_baseline_full500_r25_gemini-2.5-flash_r25_best_of_n.json"
ORIG_R10="$REPO_ROOT/runs/batches/parallel_baseline_full500_r10_gemini-2.5-flash_r10_best_of_n.json"

echo "=== Repair Gemini baseline N=25 (15 failed tasks) ===" | tee -a "$STATUS_FILE"
run_one gemini_baseline_r25_failed \
  --model gemini-2.5-flash \
  --replicas 25 \
  --policy best_of_n \
  --subset-file configs/subsets/gemini_baseline_full500_r25_failed.txt \
  --inter-task-delay 2.5 \
  --batch-id baseline_full500_r25_gemini_repair

REPAIR_R25=$(ls -1t "$REPO_ROOT"/runs/batches/parallel_baseline_full500_r25_gemini_repair_gemini-2.5-flash_*.json 2>/dev/null | head -1 || true)
if [[ -n "${REPAIR_R25:-}" && -f "$REPAIR_R25" ]]; then
  merge_repair "$ORIG_R25" "$REPAIR_R25"
else
  echo "[$(date -u +%H:%M:%S)] WARN no N=25 repair JSON found — skip merge" | tee -a "$STATUS_FILE"
fi

echo "=== Repair Gemini baseline N=10 (2 failed tasks) ===" | tee -a "$STATUS_FILE"
run_one gemini_baseline_r10_failed \
  --model gemini-2.5-flash \
  --replicas 10 \
  --policy best_of_n \
  --subset-file configs/subsets/gemini_baseline_full500_r10_failed.txt \
  --inter-task-delay 2.5 \
  --batch-id baseline_full500_r10_gemini_repair

REPAIR_R10=$(ls -1t "$REPO_ROOT"/runs/batches/parallel_baseline_full500_r10_gemini_repair_gemini-2.5-flash_*.json 2>/dev/null | head -1 || true)
if [[ -n "${REPAIR_R10:-}" && -f "$REPAIR_R10" ]]; then
  merge_repair "$ORIG_R10" "$REPAIR_R10"
else
  echo "[$(date -u +%H:%M:%S)] WARN no N=10 repair JSON found — skip merge" | tee -a "$STATUS_FILE"
fi

echo "finished_utc=$(date -u +%Y-%m-%dT%H:%M:%SZ)" | tee -a "$STATUS_FILE"
