#!/usr/bin/env bash
# Waves D + E after Waves B+C (compose full-500).
#
#   Wave D: P3 stack full-500 N=10 × {GPT, Gemini, DeepSeek}
#           P1 + early-stop + hybrid prune + semantic-store
#   Wave E: P2 stack full-500 N=10 × {GPT, Gemini, DeepSeek}
#           P1 + early-stop + hybrid prune + discovery-board
#
# Waits for Wave C (compose_full500_r25) to finish before starting.
#
# Usage:
#   nohup bash scripts/run_overnight_p2p3_full500_r10.sh \
#     > runs/overnight/<stamp>/driver.log 2>&1 &
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$REPO_ROOT"
BATCH="$REPO_ROOT/runs/batches"

STAMP="${OVERNIGHT_STAMP:-$(date -u +%Y%m%d_%H%M%S)_p2p3_full500_r10}"
OUT_DIR="$REPO_ROOT/runs/overnight/$STAMP"
mkdir -p "$OUT_DIR"
STATUS_FILE="$OUT_DIR/status.txt"
MANIFEST="$OUT_DIR/manifest.txt"
echo "$STAMP" > "$REPO_ROOT/runs/overnight/LATEST_P2P3_FULL500_R10"

echo "overnight_stamp=$STAMP" | tee "$STATUS_FILE"
echo "started_utc=$(date -u +%Y-%m-%dT%H:%M:%SZ)" | tee -a "$STATUS_FILE"
echo "paper=draft_paper_ieee_v5 — Waves D+E P3/P2 full-500 N=10" | tee -a "$STATUS_FILE"
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

# --- Wait for Waves B+C (compose N=25) ---
BC_STAMP_FILE="$REPO_ROOT/runs/overnight/LATEST_COMPOSE_WAVES_BC"
echo "[$(date -u +%H:%M:%S)] waiting for Waves B+C (compose_full500_r25) to finish..." | tee -a "$STATUS_FILE"

while true; do
  bc_stamp=""
  [[ -f "$BC_STAMP_FILE" ]] && bc_stamp=$(cat "$BC_STAMP_FILE")
  status_bc="$REPO_ROOT/runs/overnight/${bc_stamp}/status.txt"

  jsons=0
  for model in gpt-4o-mini gemini-2.5-flash deepseek-v3.2; do
    # glob — exact suffix varies with flag tags
    if compgen -G "$BATCH/parallel_compose_full500_r25_${model}_*.json" > /dev/null; then
      jsons=$((jsons + 1))
    fi
  done

  finished=0
  if [[ -n "$bc_stamp" && -f "$status_bc" ]] && grep -q '^finished_utc=' "$status_bc"; then
    finished=1
  fi

  still_running=0
  pgrep -f 'run_overnight_compose_waves_bc.sh' >/dev/null 2>&1 && still_running=1
  pgrep -f 'compose_full500_r25' >/dev/null 2>&1 && still_running=1
  pgrep -f 'compose_full500_r10_rep2' >/dev/null 2>&1 && still_running=1

  echo "[$(date -u +%H:%M:%S)] Wave C JSONs=$jsons/3 finished_flag=$finished bc_running=$still_running" | tee -a "$STATUS_FILE"

  if [[ "$jsons" -eq 3 && "$still_running" -eq 0 ]]; then
    break
  fi
  if [[ "$finished" -eq 1 && "$still_running" -eq 0 && "$jsons" -ge 2 ]]; then
    echo "[$(date -u +%H:%M:%S)] B+C marked finished with $jsons/3 N=25 JSONs — proceeding" | tee -a "$STATUS_FILE"
    break
  fi
  sleep 90
done
echo "[$(date -u +%H:%M:%S)] Waves B+C clear — starting D then E" | tee -a "$STATUS_FILE"

# --- Wave D: P3 stack N=10 ---
echo "=== WAVE D: P3 stack full-500 N=10 (P1+ES+prune+P3) ===" | tee -a "$STATUS_FILE"
PIDS=()
for model in gemini-2.5-flash gpt-4o-mini deepseek-v3.2; do
  safe=${model//./-}
  delay_args=()
  if [[ "$model" == "gemini-2.5-flash" ]]; then
    delay_args=(--inter-task-delay 2.5)
  fi
  run_one "p3_full500_r10_${safe}" \
    --model "$model" \
    --limit 500 \
    --replicas 10 \
    --policy best_of_n \
    --shared-cache \
    --early-stop \
    --semantic-store \
    --schema-pruning \
    --schema-pruning-mode hybrid \
    "${delay_args[@]}" \
    --batch-id "p3_full500_r10" &
  PIDS+=($!)
done
wait_wave "${PIDS[@]}"
echo "[$(date -u +%H:%M:%S)] waveD_done" | tee -a "$STATUS_FILE"

# --- Wave E: P2 stack N=10 ---
echo "=== WAVE E: P2 stack full-500 N=10 (P1+ES+prune+P2) ===" | tee -a "$STATUS_FILE"
PIDS=()
for model in gemini-2.5-flash gpt-4o-mini deepseek-v3.2; do
  safe=${model//./-}
  delay_args=()
  if [[ "$model" == "gemini-2.5-flash" ]]; then
    delay_args=(--inter-task-delay 2.5)
  fi
  run_one "p2_full500_r10_${safe}" \
    --model "$model" \
    --limit 500 \
    --replicas 10 \
    --policy best_of_n \
    --shared-cache \
    --discovery-board \
    --early-stop \
    --schema-pruning \
    --schema-pruning-mode hybrid \
    "${delay_args[@]}" \
    --batch-id "p2_full500_r10" &
  PIDS+=($!)
done
wait_wave "${PIDS[@]}"
echo "[$(date -u +%H:%M:%S)] waveE_done" | tee -a "$STATUS_FILE"

echo "finished_utc=$(date -u +%Y-%m-%dT%H:%M:%SZ)" | tee -a "$STATUS_FILE"
echo "=== summary ===" | tee -a "$STATUS_FILE"
for f in \
  "$BATCH"/parallel_p3_full500_r10_*.json \
  "$BATCH"/parallel_p2_full500_r10_*.json
do
  [[ -f "$f" ]] || continue
  head -c 2000 "$f" | tr ',' '\n' | rg '"(batch_id|model_key|n_replicas|task_count|completed_task_count|api_failure_count|ex_accuracy_pct)"' \
    | tee -a "$STATUS_FILE" || true
  echo "--- $f ---" | tee -a "$STATUS_FILE"
done
