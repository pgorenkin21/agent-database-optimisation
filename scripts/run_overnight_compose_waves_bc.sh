#!/usr/bin/env bash
# Waves B + C after Wave A (compose full-500 N=10).
#
#   Wave B: compose N=10 rep2 × {GPT, Gemini, DeepSeek}
#   Wave C: compose N=25      × {GPT, Gemini, DeepSeek}
#
# Same stack as Wave A / compose_full500_r3:
#   P1 + early-stop + hybrid prune + prompt-cache + P4
#
# Waits for Wave A overnight to finish (Gemini still running) before starting,
# so we do not stack another high-N wave on a busy Gemini quota.
#
# Usage:
#   nohup bash scripts/run_overnight_compose_waves_bc.sh \
#     > runs/overnight/<stamp>/driver.log 2>&1 &
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$REPO_ROOT"
BATCH="$REPO_ROOT/runs/batches"

STAMP="${OVERNIGHT_STAMP:-$(date -u +%Y%m%d_%H%M%S)_compose_waves_bc}"
OUT_DIR="$REPO_ROOT/runs/overnight/$STAMP"
mkdir -p "$OUT_DIR"
STATUS_FILE="$OUT_DIR/status.txt"
MANIFEST="$OUT_DIR/manifest.txt"
echo "$STAMP" > "$REPO_ROOT/runs/overnight/LATEST_COMPOSE_WAVES_BC"

echo "overnight_stamp=$STAMP" | tee "$STATUS_FILE"
echo "started_utc=$(date -u +%Y-%m-%dT%H:%M:%SZ)" | tee -a "$STATUS_FILE"
echo "paper=draft_paper_ieee_v5 — Waves B+C compose full-500" | tee -a "$STATUS_FILE"
echo "repo=$REPO_ROOT" | tee -a "$STATUS_FILE"

COMPOSE_FLAGS=(
  --policy best_of_n
  --shared-cache
  --early-stop
  --schema-pruning
  --schema-pruning-mode hybrid
  --prompt-cache
  --explore-suppressor
)

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

# --- Wait for Wave A ---
WAVE_A_STAMP_FILE="$REPO_ROOT/runs/overnight/LATEST_COMPOSE_FULL500_R10"
WAVE_A_GEMINI_JSON="$BATCH/parallel_compose_full500_r10_gemini-2.5-flash_r10_best_of_n_p1_cache_promptcache_early_stop_schema_prune_p4suppress.json"
WAVE_A_GPT_JSON="$BATCH/parallel_compose_full500_r10_gpt-4o-mini_r10_best_of_n_p1_cache_promptcache_early_stop_schema_prune_p4suppress.json"
WAVE_A_DS_JSON="$BATCH/parallel_compose_full500_r10_deepseek-v3.2_r10_best_of_n_p1_cache_promptcache_early_stop_schema_prune_p4suppress.json"

echo "[$(date -u +%H:%M:%S)] waiting for Wave A compose_full500_r10 to finish..." | tee -a "$STATUS_FILE"
while true; do
  a_stamp=""
  [[ -f "$WAVE_A_STAMP_FILE" ]] && a_stamp=$(cat "$WAVE_A_STAMP_FILE")
  status_a="$REPO_ROOT/runs/overnight/${a_stamp}/status.txt"
  finished=0
  if [[ -n "$a_stamp" && -f "$status_a" ]] && grep -q '^finished_utc=' "$status_a"; then
    finished=1
  fi
  # Also accept all three JSONs present (in case status write races)
  jsons=0
  [[ -f "$WAVE_A_GPT_JSON" ]] && jsons=$((jsons + 1))
  [[ -f "$WAVE_A_DS_JSON" ]] && jsons=$((jsons + 1))
  [[ -f "$WAVE_A_GEMINI_JSON" ]] && jsons=$((jsons + 1))
  # Wave A driver still running?
  still_running=0
  pgrep -f 'run_overnight_compose_full500_r10.sh' >/dev/null 2>&1 && still_running=1
  pgrep -f 'batch-id compose_full500_r10' >/dev/null 2>&1 && still_running=1
  pgrep -f -- '--batch-id compose_full500_r10' >/dev/null 2>&1 && still_running=1

  echo "[$(date -u +%H:%M:%S)] Wave A JSONs=$jsons/3 finished_flag=$finished driver_running=$still_running" | tee -a "$STATUS_FILE"

  if [[ "$jsons" -eq 3 && "$still_running" -eq 0 ]]; then
    break
  fi
  if [[ "$finished" -eq 1 && "$jsons" -ge 2 && "$still_running" -eq 0 ]]; then
    # Prefer not to block forever if Gemini JSON missing; but Wave A should write it.
    echo "[$(date -u +%H:%M:%S)] Wave A marked finished with $jsons/3 JSONs — proceeding" | tee -a "$STATUS_FILE"
    break
  fi
  sleep 60
done
echo "[$(date -u +%H:%M:%S)] Wave A clear — starting Waves B then C" | tee -a "$STATUS_FILE"

# --- Wave B: compose N=10 rep2 ---
echo "=== WAVE B: compose full-500 N=10 rep2 (GPT + Gemini + DeepSeek) ===" | tee -a "$STATUS_FILE"
PIDS=()
for model in gemini-2.5-flash gpt-4o-mini deepseek-v3.2; do
  safe=${model//./-}
  delay_args=()
  if [[ "$model" == "gemini-2.5-flash" ]]; then
    delay_args=(--inter-task-delay 2.5)
  fi
  run_one "compose_full500_r10_rep2_${safe}" \
    --model "$model" \
    --limit 500 \
    --replicas 10 \
    "${COMPOSE_FLAGS[@]}" \
    "${delay_args[@]}" \
    --batch-id "compose_full500_r10_rep2" &
  PIDS+=($!)
done
wait_wave "${PIDS[@]}"
echo "[$(date -u +%H:%M:%S)] waveB_done" | tee -a "$STATUS_FILE"

# --- Wave C: compose N=25 ---
echo "=== WAVE C: compose full-500 N=25 (GPT + Gemini + DeepSeek) ===" | tee -a "$STATUS_FILE"
PIDS=()
for model in gemini-2.5-flash gpt-4o-mini deepseek-v3.2; do
  safe=${model//./-}
  delay_args=()
  if [[ "$model" == "gemini-2.5-flash" ]]; then
    delay_args=(--inter-task-delay 2.5)
  fi
  run_one "compose_full500_r25_${safe}" \
    --model "$model" \
    --limit 500 \
    --replicas 25 \
    "${COMPOSE_FLAGS[@]}" \
    "${delay_args[@]}" \
    --batch-id "compose_full500_r25" &
  PIDS+=($!)
done
wait_wave "${PIDS[@]}"
echo "[$(date -u +%H:%M:%S)] waveC_done" | tee -a "$STATUS_FILE"

echo "finished_utc=$(date -u +%Y-%m-%dT%H:%M:%SZ)" | tee -a "$STATUS_FILE"
echo "=== summary ===" | tee -a "$STATUS_FILE"
for f in \
  "$BATCH"/parallel_compose_full500_r10_rep2_*.json \
  "$BATCH"/parallel_compose_full500_r25_*.json
do
  [[ -f "$f" ]] || continue
  head -c 2000 "$f" | tr ',' '\n' | rg '"(batch_id|model_key|n_replicas|task_count|completed_task_count|api_failure_count|ex_accuracy_pct|batch_cached_prompt_pct)"' \
    | tee -a "$STATUS_FILE" || true
  echo "--- $f ---" | tee -a "$STATUS_FILE"
done
