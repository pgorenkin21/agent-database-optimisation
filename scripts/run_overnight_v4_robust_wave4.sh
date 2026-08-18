#!/usr/bin/env bash
# Robustness wave 4 — last high-ROI API gap for draft_paper_ieee_v4.
#
# Prior waves covered:
#   Wave 1–3: composition smoke rep2, P4 full-500 rep2, compose full-500 rep2
#   Credibility: P3 full-500 N=3 × 3 (single seed only)
#
# This wave: P3 stack full-500 N=3 rep2 × 3 models
#   Closes the only remaining single-seed full-500 gap in the v4 credibility set.
#
# Models parallel; Gemini delayed. Leave machine up.
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$REPO_ROOT"

STAMP="${OVERNIGHT_STAMP:-$(date -u +%Y%m%d_%H%M%S)_robust_wave4}"
OUT_DIR="$REPO_ROOT/runs/overnight/$STAMP"
mkdir -p "$OUT_DIR"
STATUS_FILE="$OUT_DIR/status.txt"
echo "$STAMP" > "$REPO_ROOT/runs/overnight/LATEST_ROBUST_WAVE4"

echo "overnight_stamp=$STAMP" | tee "$STATUS_FILE"
echo "started_utc=$(date -u +%Y-%m-%dT%H:%M:%SZ)" | tee -a "$STATUS_FILE"
echo "paper=draft_paper_ieee_v4 robustness wave4 (P3 full-500 N=3 rep2)" | tee -a "$STATUS_FILE"

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

echo "=== WAVE: P3 stack full-500 N=3 rep2 ===" | tee -a "$STATUS_FILE"
PIDS=()
for model in gemini-2.5-flash gpt-4o-mini deepseek-v3.2; do
  safe=${model//./-}
  # shellcheck disable=SC2046
  run_one "p3_full500_r3_rep2_${safe}" \
    --model "$model" \
    --limit 500 \
    --replicas 3 \
    --policy best_of_n \
    --shared-cache \
    --early-stop \
    --semantic-store \
    --schema-pruning \
    --schema-pruning-mode hybrid \
    $(gemini_delay_args "$model") \
    --batch-id "p3_full500_r3_rep2" &
  PIDS+=($!)
done
wait_wave "${PIDS[@]}" || true
echo "[$(date -u +%H:%M:%S)] wave_done" | tee -a "$STATUS_FILE"

echo "=== Offline robustness pack refresh ===" | tee -a "$STATUS_FILE"
uv run python scripts/generate_robustness_pack.py \
  >"$OUT_DIR/robustness_pack.log" 2>&1 || true
cp -f "$REPO_ROOT/runs/reports/bootstrap_ex_cis_v4.md" "$OUT_DIR/" 2>/dev/null || true
cp -f "$REPO_ROOT/runs/reports/rep_stability_v4.md" "$OUT_DIR/" 2>/dev/null || true
cp -f "$REPO_ROOT/runs/reports/robustness_pack_v4.md" "$OUT_DIR/" 2>/dev/null || true

echo "finished_utc=$(date -u +%Y-%m-%dT%H:%M:%SZ)" | tee -a "$STATUS_FILE"
ls -lt "$REPO_ROOT/runs/batches"/parallel_p3_full500_r3_rep2_* 2>/dev/null | head -20 || true
