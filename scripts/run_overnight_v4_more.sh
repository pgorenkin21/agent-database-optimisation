#!/usr/bin/env bash
# Overnight continuation after P3 full-500 resume.
# Waits for P3 batch JSON files (file-based — avoids pgrep self-deadlock), then runs:
#   Wave A: PC + P1 + P4 + hybrid prune   full-500 N=3 × 3 models  (v4 future-work 1 at scale)
#   Wave B: same + P3 on GPT only         full-500 N=3            (deployment recipe at scale)
#   Then: refresh bootstrap_ex_cis_v4.md
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$REPO_ROOT"
BATCH="$REPO_ROOT/runs/batches"

STAMP="${OVERNIGHT_STAMP:-$(date -u +%Y%m%d_%H%M%S)_overnight_more}"
OUT_DIR="$REPO_ROOT/runs/overnight/$STAMP"
mkdir -p "$OUT_DIR"
STATUS_FILE="$OUT_DIR/status.txt"
echo "$STAMP" > "$REPO_ROOT/runs/overnight/LATEST_OVERNIGHT_MORE"

echo "overnight_stamp=$STAMP" | tee "$STATUS_FILE"
echo "started_utc=$(date -u +%Y-%m-%dT%H:%M:%SZ)" | tee -a "$STATUS_FILE"
echo "paper=draft_paper_ieee_v4 composition full-500 + GPT+P3 full-500" | tee -a "$STATUS_FILE"

P3_FILES=(
  "$BATCH/parallel_p3_full500_r3_gpt-4o-mini_r3_best_of_n_p1_cache_p3_semantic_early_stop_schema_prune.json"
  "$BATCH/parallel_p3_full500_r3_gemini-2.5-flash_r3_best_of_n_p1_cache_p3_semantic_early_stop_schema_prune.json"
  "$BATCH/parallel_p3_full500_r3_deepseek-v3.2_r3_best_of_n_p1_cache_p3_semantic_early_stop_schema_prune.json"
)

SKIP_GEMINI_FILE="$REPO_ROOT/runs/overnight/SKIP_GEMINI"
skip_gemini() { [[ -f "$SKIP_GEMINI_FILE" ]] || [[ "${SKIP_GEMINI:-}" == "1" ]]; }

echo "[$(date -u +%H:%M:%S)] waiting for P3 full-500 JSON outputs..." | tee -a "$STATUS_FILE"
while true; do
  ready=0
  for f in "${P3_FILES[@]}"; do
    [[ -f "$f" ]] && ready=$((ready + 1))
  done
  echo "[$(date -u +%H:%M:%S)] P3 outputs ready: $ready/3" | tee -a "$STATUS_FILE"
  if [[ "$ready" -eq 3 ]]; then
    break
  fi
  # Credits exhausted: proceed with GPT+DeepSeek P3 only (2/3)
  if skip_gemini && [[ "$ready" -ge 2 ]]; then
    echo "[$(date -u +%H:%M:%S)] SKIP gemini P3 wait (credits) — proceeding with $ready/3" | tee -a "$STATUS_FILE"
    break
  fi
  sleep 120
done
echo "[$(date -u +%H:%M:%S)] P3 complete — starting queued waves" | tee -a "$STATUS_FILE"

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

echo "=== WAVE A: composition PC+P1+P4+prune full-500 N=3 ===" | tee -a "$STATUS_FILE"
PIDS=()
for model in gemini-2.5-flash gpt-4o-mini deepseek-v3.2; do
  safe=${model//./-}
  if [[ "$model" == "gemini-2.5-flash" ]] && skip_gemini; then
    echo "[$(date -u +%H:%M:%S)] SKIP compose_full500_r3_${safe} (Gemini credits depleted)" | tee -a "$STATUS_FILE"
    continue
  fi
  delay_args=()
  if [[ "$model" == "gemini-2.5-flash" ]]; then
    delay_args=(--inter-task-delay 2.0)
  fi
  run_one "compose_full500_r3_${safe}" \
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
    "${delay_args[@]}" \
    --batch-id "compose_full500_r3" &
  PIDS+=($!)
done
wait_wave "${PIDS[@]}" || true
echo "[$(date -u +%H:%M:%S)] waveA_done" | tee -a "$STATUS_FILE"

echo "=== WAVE B: GPT composition + P3 full-500 N=3 ===" | tee -a "$STATUS_FILE"
run_one compose_p3_full500_r3_gpt-4o-mini \
  --model gpt-4o-mini \
  --limit 500 \
  --replicas 3 \
  --policy best_of_n \
  --shared-cache \
  --early-stop \
  --schema-pruning \
  --schema-pruning-mode hybrid \
  --prompt-cache \
  --explore-suppressor \
  --semantic-store \
  --batch-id "compose_p3_full500_r3" || true
echo "[$(date -u +%H:%M:%S)] waveB_done" | tee -a "$STATUS_FILE"

echo "=== Offline: refresh bootstrap CIs ===" | tee -a "$STATUS_FILE"
uv run python scripts/bootstrap_ex_cis.py \
  --out "$OUT_DIR/bootstrap_ex_cis_v4.md" \
  >"$OUT_DIR/bootstrap.log" 2>&1 || true
cp -f "$OUT_DIR/bootstrap_ex_cis_v4.md" "$REPO_ROOT/runs/reports/bootstrap_ex_cis_v4.md" 2>/dev/null || true

echo "finished_utc=$(date -u +%Y-%m-%dT%H:%M:%SZ)" | tee -a "$STATUS_FILE"
ls -lt "$BATCH"/parallel_compose_full500_* "$BATCH"/parallel_compose_p3_full500_* 2>/dev/null | head -20 || true
