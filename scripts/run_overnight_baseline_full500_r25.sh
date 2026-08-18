#!/usr/bin/env bash
# Baseline (P0) full-500 at N=25 — high-N scale-up on full mini-dev.
#
# Already on disk: baseline_full500_r3, baseline_full500_r10.
# This run: same P0 flags at --replicas 25 on all 500 mini-dev tasks.
#
# Models run in parallel. Gemini gets a slightly longer inter-task delay.
# NOTE: run_parallel_batch.py returns rc=1 whenever any task scores EX=0,
# so judge success by the written JSON (task_count / api_failure_count).
#
# Usage:
#   nohup bash scripts/run_overnight_baseline_full500_r25.sh \
#     > runs/overnight/<stamp>/driver.log 2>&1 &
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$REPO_ROOT"

STAMP="${OVERNIGHT_STAMP:-$(date -u +%Y%m%d_%H%M%S)_baseline_full500_r25}"
OUT_DIR="$REPO_ROOT/runs/overnight/$STAMP"
mkdir -p "$OUT_DIR"
STATUS_FILE="$OUT_DIR/status.txt"
MANIFEST="$OUT_DIR/manifest.txt"
echo "$STAMP" > "$REPO_ROOT/runs/overnight/LATEST_BASELINE_FULL500_R25"

echo "overnight_stamp=$STAMP" | tee "$STATUS_FILE"
echo "started_utc=$(date -u +%Y-%m-%dT%H:%M:%SZ)" | tee -a "$STATUS_FILE"
echo "paper=draft_paper_ieee_v5 — baseline full-500 N=25 scale-up" | tee -a "$STATUS_FILE"
echo "repo=$REPO_ROOT" | tee -a "$STATUS_FILE"

run_one() {
  local name="$1"
  shift
  local log="$OUT_DIR/${name}.log"
  echo "[$(date -u +%H:%M:%S)] START $name" | tee -a "$STATUS_FILE"
  echo "$name $*" >> "$MANIFEST"
  set +e
  uv run python -u scripts/run_parallel_batch.py "$@" >"$log" 2>&1
  local rc=$?
  set -e
  echo "[$(date -u +%H:%M:%S)] DONE  $name (rc=$rc; rc=1 is normal — check JSON)" | tee -a "$STATUS_FILE"
  return 0
}

wait_wave() {
  for pid in "$@"; do
    wait "$pid" || true
  done
}

echo "=== WAVE: P0 baseline full-500 N=25 (3 models in parallel) ===" | tee -a "$STATUS_FILE"
PIDS=()
for model in gemini-2.5-flash gpt-4o-mini deepseek-v3.2; do
  safe=${model//./-}
  delay_args=()
  if [[ "$model" == "gemini-2.5-flash" ]]; then
    delay_args=(--inter-task-delay 2.0)
  fi
  run_one "baseline_full500_r25_${safe}" \
    --model "$model" \
    --limit 500 \
    --replicas 25 \
    --policy best_of_n \
    "${delay_args[@]}" \
    --batch-id "baseline_full500_r25" &
  PIDS+=($!)
done
wait_wave "${PIDS[@]}"

echo "finished_utc=$(date -u +%Y-%m-%dT%H:%M:%SZ)" | tee -a "$STATUS_FILE"
echo "=== summary (header fields) ===" | tee -a "$STATUS_FILE"
for f in "$REPO_ROOT"/runs/batches/parallel_baseline_full500_r25_*.json; do
  [[ -f "$f" ]] || continue
  head -c 2000 "$f" | tr ',' '\n' | rg '"(batch_id|model_key|n_replicas|task_count|completed_task_count|api_failure_count|ex_accuracy_pct)"' \
    | tee -a "$STATUS_FILE" || true
  echo "--- $f ---" | tee -a "$STATUS_FILE"
done
