#!/usr/bin/env bash
# Overnight queue: stack prompt-cache on Chapter-9 winning stacks (smoke-50, N=10).
#
# Primary (parallel across providers — different API keys):
#   1. Gemini  → t03_stag2s + P1 + early-stop + hybrid prune + prompt-cache
#   2. GPT     → P3 + P1 + early-stop + hybrid prune + prompt-cache
#   3. DeepSeek→ P2 + P1 + early-stop + hybrid prune + prompt-cache
#
# Secondary (after primaries finish; Ch.9 open gaps + P4 on DeepSeek winner):
#   4. GPT     → schedule + P3 + core + prompt-cache
#   5. DeepSeek→ schedule + P2 + core + prompt-cache
#   6. DeepSeek→ P2 + P4 suppressor + core + prompt-cache
#
# Usage:
#   nohup bash scripts/run_overnight_pc_winners.sh > runs/overnight/<stamp>/driver.log 2>&1 &
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$REPO_ROOT"

STAMP="${OVERNIGHT_STAMP:-$(date -u +%Y%m%d_%H%M%S)}"
OUT_DIR="$REPO_ROOT/runs/overnight/$STAMP"
mkdir -p "$OUT_DIR"
STATUS_FILE="$OUT_DIR/status.txt"
MANIFEST="$OUT_DIR/manifest.txt"

echo "overnight_stamp=$STAMP" | tee "$STATUS_FILE"
echo "started_utc=$(date -u +%Y-%m-%dT%H:%M:%SZ)" | tee -a "$STATUS_FILE"
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
  if [[ $rc -eq 0 ]]; then
    echo "[$(date -u +%H:%M:%S)] OK    $name (rc=0)" | tee -a "$STATUS_FILE"
  else
    echo "[$(date -u +%H:%M:%S)] FAIL  $name (rc=$rc) — see $log" | tee -a "$STATUS_FILE"
  fi
  return $rc
}

COMMON=(
  --limit 50
  --replicas 10
  --policy best_of_n
  --shared-cache
  --early-stop
  --schema-pruning
  --schema-pruning-mode hybrid
  --prompt-cache
)

echo "=== PRIMARY WAVE (3 models in parallel) ===" | tee -a "$STATUS_FILE"

run_one pc_winner_gemini_t03_stag2s_r10_bo \
  --model gemini-2.5-flash \
  "${COMMON[@]}" \
  --temperature 0.3 \
  --stagger-mode linear_seconds \
  --stagger-seconds 2.0 \
  --inter-task-delay 2.0 \
  --batch-id "pc_winner_gemini_t03_stag2s_r10_bo" &
PID_GEM=$!

run_one pc_winner_gpt_p3_r10_bo \
  --model gpt-4o-mini \
  "${COMMON[@]}" \
  --semantic-store \
  --batch-id "pc_winner_gpt_p3_r10_bo" &
PID_GPT=$!

run_one pc_winner_deepseek_p2_r10_bo \
  --model deepseek-v3.2 \
  "${COMMON[@]}" \
  --discovery-board \
  --batch-id "pc_winner_deepseek_p2_r10_bo" &
PID_DS=$!

RC_PRIMARY=0
wait "$PID_GEM" || RC_PRIMARY=1
wait "$PID_GPT" || RC_PRIMARY=1
wait "$PID_DS" || RC_PRIMARY=1
echo "[$(date -u +%H:%M:%S)] primary_wave_done rc=$RC_PRIMARY" | tee -a "$STATUS_FILE"

echo "=== SECONDARY WAVE (sequential; Ch.9 gaps) ===" | tee -a "$STATUS_FILE"

# GPT schedule + P3 (never measured; Ch.9 §9.7)
run_one pc_gpt_sched_p3_r10_bo \
  --model gpt-4o-mini \
  "${COMMON[@]}" \
  --semantic-store \
  --temperature 0.3 \
  --stagger-mode linear_seconds \
  --stagger-seconds 2.0 \
  --batch-id "pc_gpt_sched_p3_r10_bo" || true

# DeepSeek schedule + P2 (never measured; Ch.9 §9.7)
run_one pc_deepseek_sched_p2_r10_bo \
  --model deepseek-v3.2 \
  "${COMMON[@]}" \
  --discovery-board \
  --temperature 0.3 \
  --stagger-mode linear_seconds \
  --stagger-seconds 2.0 \
  --batch-id "pc_deepseek_sched_p2_r10_bo" || true

# DeepSeek P2 + P4 suppressor on the winning content stack
run_one pc_winner_deepseek_p2_p4_r10_bo \
  --model deepseek-v3.2 \
  "${COMMON[@]}" \
  --discovery-board \
  --explore-suppressor \
  --batch-id "pc_winner_deepseek_p2_p4_r10_bo" || true

echo "finished_utc=$(date -u +%Y-%m-%dT%H:%M:%SZ)" | tee -a "$STATUS_FILE"
echo "Done. Status: $STATUS_FILE"
ls -lt "$REPO_ROOT/runs/batches"/parallel_pc_winner_* "$REPO_ROOT/runs/batches"/parallel_pc_gpt_* "$REPO_ROOT/runs/batches"/parallel_pc_deepseek_* 2>/dev/null | head -40 || true
