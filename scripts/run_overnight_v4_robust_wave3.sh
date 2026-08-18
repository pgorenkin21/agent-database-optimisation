#!/usr/bin/env bash
# Robustness wave 3 — remaining high-ROI API gaps for draft_paper_ieee_v4.
#
# Wave 1: composition smoke N=25 rep2 × 3
#         (PC+P1+P4+hybrid prune — deployment stack was single-run at smoke)
# Wave 2: P4 isolated full-500 N=3 rep2 × 3
#         (execution-layer claim at scale; second seed)
# Wave 3: compose full-500 N=3 rep2 × 3
#         (future-work composition at scale; second seed)
#
# Models parallel within wave; Gemini delayed. Long run — leave machine up.
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$REPO_ROOT"

STAMP="${OVERNIGHT_STAMP:-$(date -u +%Y%m%d_%H%M%S)_robust_wave3}"
OUT_DIR="$REPO_ROOT/runs/overnight/$STAMP"
mkdir -p "$OUT_DIR"
STATUS_FILE="$OUT_DIR/status.txt"
echo "$STAMP" > "$REPO_ROOT/runs/overnight/LATEST_ROBUST_WAVE3"

echo "overnight_stamp=$STAMP" | tee "$STATUS_FILE"
echo "started_utc=$(date -u +%Y-%m-%dT%H:%M:%SZ)" | tee -a "$STATUS_FILE"
echo "paper=draft_paper_ieee_v4 robustness wave3 (compose smoke + full500 rep2)" | tee -a "$STATUS_FILE"

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

gemini_delay_args() {
  if [[ "$1" == "gemini-2.5-flash" ]]; then
    echo --inter-task-delay 2.5
  fi
}

echo "=== WAVE 1: composition smoke N=25 rep2 ===" | tee -a "$STATUS_FILE"
PIDS=()
for model in gemini-2.5-flash gpt-4o-mini deepseek-v3.2; do
  safe=${model//./-}
  # shellcheck disable=SC2046
  run_one "compose_r25_rep2_${safe}" \
    --model "$model" \
    --limit 50 \
    --replicas 25 \
    --policy best_of_n \
    --shared-cache \
    --early-stop \
    --schema-pruning \
    --schema-pruning-mode hybrid \
    --prompt-cache \
    --explore-suppressor \
    $(gemini_delay_args "$model") \
    --batch-id "compose_r25_rep2" &
  PIDS+=($!)
done
wait_wave "${PIDS[@]}" || true
echo "[$(date -u +%H:%M:%S)] wave1_done" | tee -a "$STATUS_FILE"

echo "=== WAVE 2: P4 isolated full-500 N=3 rep2 ===" | tee -a "$STATUS_FILE"
PIDS=()
for model in gemini-2.5-flash gpt-4o-mini deepseek-v3.2; do
  safe=${model//./-}
  # shellcheck disable=SC2046
  run_one "p4_full500_r3_rep2_${safe}" \
    --model "$model" \
    --limit 500 \
    --replicas 3 \
    --policy best_of_n \
    --prompt-cache \
    --explore-suppressor \
    $(gemini_delay_args "$model") \
    --batch-id "p4_full500_r3_rep2" &
  PIDS+=($!)
done
wait_wave "${PIDS[@]}" || true
echo "[$(date -u +%H:%M:%S)] wave2_done" | tee -a "$STATUS_FILE"

echo "=== WAVE 3: compose full-500 N=3 rep2 ===" | tee -a "$STATUS_FILE"
PIDS=()
for model in gemini-2.5-flash gpt-4o-mini deepseek-v3.2; do
  safe=${model//./-}
  # shellcheck disable=SC2046
  run_one "compose_full500_r3_rep2_${safe}" \
    --model "$model" \
    --limit 500 \
    --replicas 3 \
    --policy best_of_n \
    --shared-cache \
    --early-stop \
    --schema-pruning \
    --schema-pruning-mode hybrid \
    --prompt-cache \
    --explore-suppressor \
    $(gemini_delay_args "$model") \
    --batch-id "compose_full500_r3_rep2" &
  PIDS+=($!)
done
wait_wave "${PIDS[@]}" || true
echo "[$(date -u +%H:%M:%S)] wave3_done" | tee -a "$STATUS_FILE"

echo "=== Offline bootstrap refresh ===" | tee -a "$STATUS_FILE"
uv run python scripts/bootstrap_ex_cis.py \
  --out "$OUT_DIR/bootstrap_ex_cis_v4.md" \
  >"$OUT_DIR/bootstrap.log" 2>&1 || true
cp -f "$OUT_DIR/bootstrap_ex_cis_v4.md" "$REPO_ROOT/runs/reports/bootstrap_ex_cis_v4.md" 2>/dev/null || true

echo "finished_utc=$(date -u +%Y-%m-%dT%H:%M:%SZ)" | tee -a "$STATUS_FILE"
ls -lt "$REPO_ROOT/runs/batches"/parallel_compose_r25_rep2_* \
       "$REPO_ROOT/runs/batches"/parallel_p4_full500_r3_rep2_* \
       "$REPO_ROOT/runs/batches"/parallel_compose_full500_r3_rep2_* 2>/dev/null | head -30 || true
