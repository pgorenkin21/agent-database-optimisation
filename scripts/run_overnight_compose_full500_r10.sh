#!/usr/bin/env bash
# Wave A: composed stack full-500 at N=10 × {GPT, Gemini, DeepSeek}.
#
# Stack matches compose_full500_r3:
#   P1 shared-cache + early-stop + hybrid prune + prompt-cache + P4 suppressor
#
# Models run in parallel. Gemini gets a longer inter-task delay.
# NOTE: run_parallel_batch.py returns rc=1 whenever any task scores EX=0;
# judge success by the written JSON (task_count / api_failure_count).
#
# Usage:
#   nohup bash scripts/run_overnight_compose_full500_r10.sh \
#     > runs/overnight/<stamp>/driver.log 2>&1 &
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$REPO_ROOT"

STAMP="${OVERNIGHT_STAMP:-$(date -u +%Y%m%d_%H%M%S)_compose_full500_r10}"
OUT_DIR="$REPO_ROOT/runs/overnight/$STAMP"
mkdir -p "$OUT_DIR"
STATUS_FILE="$OUT_DIR/status.txt"
MANIFEST="$OUT_DIR/manifest.txt"
echo "$STAMP" > "$REPO_ROOT/runs/overnight/LATEST_COMPOSE_FULL500_R10"

echo "overnight_stamp=$STAMP" | tee "$STATUS_FILE"
echo "started_utc=$(date -u +%Y-%m-%dT%H:%M:%SZ)" | tee -a "$STATUS_FILE"
echo "paper=draft_paper_ieee_v5 — Wave A compose full-500 N=10" | tee -a "$STATUS_FILE"
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

echo "=== WAVE A: compose PC+P1+ES+prune+P4 full-500 N=10 (3 models) ===" | tee -a "$STATUS_FILE"
PIDS=()
for model in gemini-2.5-flash gpt-4o-mini deepseek-v3.2; do
  safe=${model//./-}
  delay_args=()
  if [[ "$model" == "gemini-2.5-flash" ]]; then
    delay_args=(--inter-task-delay 2.5)
  fi
  run_one "compose_full500_r10_${safe}" \
    --model "$model" \
    --limit 500 \
    --replicas 10 \
    --policy best_of_n \
    --shared-cache \
    --early-stop \
    --schema-pruning \
    --schema-pruning-mode hybrid \
    --prompt-cache \
    --explore-suppressor \
    "${delay_args[@]}" \
    --batch-id "compose_full500_r10" &
  PIDS+=($!)
done
wait_wave "${PIDS[@]}"

echo "finished_utc=$(date -u +%Y-%m-%dT%H:%M:%SZ)" | tee -a "$STATUS_FILE"
echo "=== summary (header fields) ===" | tee -a "$STATUS_FILE"
for f in "$REPO_ROOT"/runs/batches/parallel_compose_full500_r10_*.json; do
  [[ -f "$f" ]] || continue
  [[ "$f" == *repair* ]] && continue
  head -c 2200 "$f" | tr ',' '\n' | rg '"(batch_id|model_key|n_replicas|task_count|completed_task_count|api_failure_count|ex_accuracy_pct|avg_explore_redundancy_pct|batch_cached_prompt_pct)"' \
    | tee -a "$STATUS_FILE" || true
  echo "--- $f ---" | tee -a "$STATUS_FILE"
done
