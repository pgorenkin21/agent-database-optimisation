#!/usr/bin/env bash
# Overnight queue aligned to draft_paper_ieee_v4.tex future work (1):
#   "composition of prompt caching with the pruning + P1 + P4 stack —
#    orthogonal by construction, but not yet run combined"
#
# Already have (do NOT re-run):
#   parallel_p1p4_r25_bo_*          = P1 + P4 + prompt-cache (no prune)
#   parallel_pc_p1_prune_r25_bo_*   = P1 + prune + prompt-cache (no P4)
#
# Primary (parallel, N=25 smoke-50 — matches v4 PC/P4 table scale):
#   pc_p1_p4_prune_r25_bo  ×  {gemini, gpt, deepseek}
#     = --prompt-cache --shared-cache --explore-suppressor
#       --schema-pruning hybrid --early-stop
#
# Secondary (after primary; v4 deployment recipe §Discussion):
#   GPT only: same stack + P3 semantic store
#
# Usage:
#   nohup bash scripts/run_overnight_v4_composition.sh \
#     > runs/overnight/<stamp>/driver.log 2>&1 &
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
echo "paper=draft_paper_ieee_v4 future-work (1) composition" | tee -a "$STATUS_FILE"
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

# Exact stack named in v4 §Conclusion future work (1)
CORE=(
  --limit 50
  --replicas 25
  --policy best_of_n
  --shared-cache
  --early-stop
  --schema-pruning
  --schema-pruning-mode hybrid
  --prompt-cache
  --explore-suppressor
)

echo "=== PRIMARY: prompt-cache + P1 + P4 + hybrid prune (N=25) ===" | tee -a "$STATUS_FILE"

run_one pc_p1_p4_prune_r25_bo_gemini \
  --model gemini-2.5-flash \
  "${CORE[@]}" \
  --inter-task-delay 2.0 \
  --batch-id "pc_p1_p4_prune_r25_bo" &
PID_GEM=$!

run_one pc_p1_p4_prune_r25_bo_gpt \
  --model gpt-4o-mini \
  "${CORE[@]}" \
  --batch-id "pc_p1_p4_prune_r25_bo" &
PID_GPT=$!

run_one pc_p1_p4_prune_r25_bo_deepseek \
  --model deepseek-v3.2 \
  "${CORE[@]}" \
  --batch-id "pc_p1_p4_prune_r25_bo" &
PID_DS=$!

RC_PRIMARY=0
wait "$PID_GEM" || RC_PRIMARY=1
wait "$PID_GPT" || RC_PRIMARY=1
wait "$PID_DS" || RC_PRIMARY=1
echo "[$(date -u +%H:%M:%S)] primary_wave_done rc=$RC_PRIMARY" | tee -a "$STATUS_FILE"

echo "=== SECONDARY: GPT deployment stack (+P3 on top of composition) ===" | tee -a "$STATUS_FILE"

run_one pc_p1_p4_prune_p3_r25_bo_gpt \
  --model gpt-4o-mini \
  "${CORE[@]}" \
  --semantic-store \
  --batch-id "pc_p1_p4_prune_p3_r25_bo" || true

echo "finished_utc=$(date -u +%Y-%m-%dT%H:%M:%SZ)" | tee -a "$STATUS_FILE"
echo "Done. Status: $STATUS_FILE"
ls -lt "$REPO_ROOT/runs/batches"/parallel_pc_p1_p4_prune_* 2>/dev/null | head -20 || true
