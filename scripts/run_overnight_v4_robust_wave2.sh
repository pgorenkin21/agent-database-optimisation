#!/usr/bin/env bash
# Overnight robustness API wave (draft_paper_ieee_v4):
#   Wave 1: P0 baseline N=25 rep2 × 3 models  (matched control for P1/prune/PC/P4 rep2)
#   Wave 2: P2 stack N=25 rep2 × 3            (matched control for P3; unconfound + stability)
#   Wave 3: P3 stack N=25 rep2 × 3            (noisiest model-conditioning claim)
#
# Note: a separate "PC-base" wave is omitted — it is identical to P0 baseline.
# Models parallel within a wave; waves sequential. Gemini gets extra delay.
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$REPO_ROOT"

STAMP="${OVERNIGHT_STAMP:-$(date -u +%Y%m%d_%H%M%S)_robust_wave2}"
OUT_DIR="$REPO_ROOT/runs/overnight/$STAMP"
mkdir -p "$OUT_DIR"
STATUS_FILE="$OUT_DIR/status.txt"
echo "$STAMP" > "$REPO_ROOT/runs/overnight/LATEST_ROBUST_WAVE2"

echo "overnight_stamp=$STAMP" | tee "$STATUS_FILE"
echo "started_utc=$(date -u +%Y-%m-%dT%H:%M:%SZ)" | tee -a "$STATUS_FILE"
echo "paper=draft_paper_ieee_v4 robustness wave2 (baseline/P2/P3 rep2)" | tee -a "$STATUS_FILE"

run_one() {
  local name="$1"
  shift
  local log="$OUT_DIR/${name}.log"
  echo "[$(date -u +%H:%M:%S)] START $name" | tee -a "$STATUS_FILE"
  set +e
  uv run python -u scripts/run_parallel_batch.py "$@" >"$log" 2>&1
  local rc=$?
  set -e
  if [[ $rc -eq 0 ]]; then
    echo "[$(date -u +%H:%M:%S)] OK    $name (rc=0)" | tee -a "$STATUS_FILE"
  else
    echo "[$(date -u +%H:%M:%S)] FAIL  $name (rc=$rc) — see $log" | tee -a "$STATUS_FILE"
  fi
  return $rc
}

wait_wave() {
  local rc=0
  for pid in "$@"; do
    wait "$pid" || rc=1
  done
  return $rc
}

gemini_delay() {
  local model="$1"
  if [[ "$model" == "gemini-2.5-flash" ]]; then
    echo --inter-task-delay 2.5
  fi
}

echo "=== WAVE 1: P0 baseline N=25 rep2 ===" | tee -a "$STATUS_FILE"
PIDS=()
for model in gemini-2.5-flash gpt-4o-mini deepseek-v3.2; do
  safe=${model//./-}
  # shellcheck disable=SC2046
  run_one "baseline_r25_rep2_${safe}" \
    --model "$model" \
    --limit 50 \
    --replicas 25 \
    --policy best_of_n \
    $(gemini_delay "$model") \
    --batch-id "baseline_r25_rep2" &
  PIDS+=($!)
done
wait_wave "${PIDS[@]}" || true
echo "[$(date -u +%H:%M:%S)] wave1_done" | tee -a "$STATUS_FILE"

echo "=== WAVE 2: P2 stack N=25 rep2 (P1+P2+early-stop+hybrid prune) ===" | tee -a "$STATUS_FILE"
PIDS=()
for model in gemini-2.5-flash gpt-4o-mini deepseek-v3.2; do
  safe=${model//./-}
  # shellcheck disable=SC2046
  run_one "p2_r25_rep2_${safe}" \
    --model "$model" \
    --limit 50 \
    --replicas 25 \
    --policy best_of_n \
    --shared-cache \
    --discovery-board \
    --early-stop \
    --schema-pruning \
    --schema-pruning-mode hybrid \
    $(gemini_delay "$model") \
    --batch-id "p2_r25_rep2" &
  PIDS+=($!)
done
wait_wave "${PIDS[@]}" || true
echo "[$(date -u +%H:%M:%S)] wave2_done" | tee -a "$STATUS_FILE"

echo "=== WAVE 3: P3 stack N=25 rep2 ===" | tee -a "$STATUS_FILE"
PIDS=()
for model in gemini-2.5-flash gpt-4o-mini deepseek-v3.2; do
  safe=${model//./-}
  # shellcheck disable=SC2046
  run_one "p3_r25_rep2_${safe}" \
    --model "$model" \
    --limit 50 \
    --replicas 25 \
    --policy best_of_n \
    --shared-cache \
    --early-stop \
    --semantic-store \
    --schema-pruning \
    --schema-pruning-mode hybrid \
    $(gemini_delay "$model") \
    --batch-id "p3_r25_rep2" &
  PIDS+=($!)
done
wait_wave "${PIDS[@]}" || true
echo "[$(date -u +%H:%M:%S)] wave3_done" | tee -a "$STATUS_FILE"

echo "=== Offline: bootstrap + rep1/rep2 note ===" | tee -a "$STATUS_FILE"
uv run python scripts/bootstrap_ex_cis.py \
  --out "$OUT_DIR/bootstrap_ex_cis_v4.md" \
  >"$OUT_DIR/bootstrap.log" 2>&1 || true
cp -f "$OUT_DIR/bootstrap_ex_cis_v4.md" "$REPO_ROOT/runs/reports/bootstrap_ex_cis_v4.md" 2>/dev/null || true

echo "finished_utc=$(date -u +%Y-%m-%dT%H:%M:%SZ)" | tee -a "$STATUS_FILE"
ls -lt "$REPO_ROOT/runs/batches"/parallel_baseline_r25_rep2_* \
       "$REPO_ROOT/runs/batches"/parallel_p2_r25_rep2_* \
       "$REPO_ROOT/runs/batches"/parallel_p3_r25_rep2_* 2>/dev/null | head -30 || true
