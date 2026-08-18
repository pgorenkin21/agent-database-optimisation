#!/usr/bin/env bash
# Resume Gemini-blocked + unfinished Wave B after credits topped up.
#   Wave 1 (parallel, different APIs):
#     - Gemini compose full-500 N=3 (restart; prior run died ~237/500)
#     - GPT compose+P3 full-500 N=3 (never started)
#   Wave 2 (sequential Gemini, higher delay):
#     - Gemini P2-stack N=25 repair (v4 confound)
#     - Gemini smoke N=25 rep2: PC, P4, prune, P1
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$REPO_ROOT"

STAMP="${OVERNIGHT_STAMP:-$(date -u +%Y%m%d_%H%M%S)_gemini_resume}"
OUT_DIR="$REPO_ROOT/runs/overnight/$STAMP"
mkdir -p "$OUT_DIR"
STATUS_FILE="$OUT_DIR/status.txt"
echo "$STAMP" > "$REPO_ROOT/runs/overnight/LATEST_GEMINI_RESUME"

echo "overnight_stamp=$STAMP" | tee "$STATUS_FILE"
echo "started_utc=$(date -u +%Y-%m-%dT%H:%M:%SZ)" | tee -a "$STATUS_FILE"
echo "paper=draft_paper_ieee_v4 gemini resume after credits" | tee -a "$STATUS_FILE"

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

echo "=== WAVE 1: Gemini compose + GPT compose+P3 (parallel) ===" | tee -a "$STATUS_FILE"

run_one compose_full500_r3_gemini-2-5-flash \
  --model gemini-2.5-flash \
  --limit 500 \
  --replicas 3 \
  --policy best_of_n \
  --shared-cache \
  --early-stop \
  --schema-pruning \
  --schema-pruning-mode hybrid \
  --prompt-cache \
  --explore-suppressor \
  --inter-task-delay 2.5 \
  --batch-id compose_full500_r3 &
PID_GEM=$!

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
  --batch-id compose_p3_full500_r3 &
PID_GPT=$!

wait "$PID_GEM" || true
wait "$PID_GPT" || true
echo "[$(date -u +%H:%M:%S)] wave1_done" | tee -a "$STATUS_FILE"

echo "=== WAVE 2: Gemini smoke repair + rep2 (sequential) ===" | tee -a "$STATUS_FILE"

run_one fullstack_prune_r25_repair_gemini-2-5-flash \
  --model gemini-2.5-flash \
  --limit 50 \
  --replicas 25 \
  --policy best_of_n \
  --shared-cache \
  --discovery-board \
  --early-stop \
  --schema-pruning \
  --schema-pruning-mode hybrid \
  --inter-task-delay 2.5 \
  --batch-id fullstack_prune_r25_repair || true

run_one pc_r25_rep2_gemini-2-5-flash \
  --model gemini-2.5-flash \
  --limit 50 \
  --replicas 25 \
  --policy best_of_n \
  --prompt-cache \
  --inter-task-delay 2.5 \
  --batch-id pc_r25_rep2 || true

run_one p4_r25_rep2_gemini-2-5-flash \
  --model gemini-2.5-flash \
  --limit 50 \
  --replicas 25 \
  --policy best_of_n \
  --prompt-cache \
  --explore-suppressor \
  --inter-task-delay 2.5 \
  --batch-id p4_r25_rep2 || true

run_one prune_r25_rep2_gemini-2-5-flash \
  --model gemini-2.5-flash \
  --limit 50 \
  --replicas 25 \
  --policy best_of_n \
  --schema-pruning \
  --schema-pruning-mode hybrid \
  --inter-task-delay 2.5 \
  --batch-id prune_r25_rep2 || true

run_one p1_r25_rep2_gemini-2-5-flash \
  --model gemini-2.5-flash \
  --limit 50 \
  --replicas 25 \
  --policy best_of_n \
  --shared-cache \
  --inter-task-delay 2.5 \
  --batch-id p1_r25_rep2 || true

echo "=== Offline bootstrap refresh ===" | tee -a "$STATUS_FILE"
uv run python scripts/bootstrap_ex_cis.py \
  --out "$OUT_DIR/bootstrap_ex_cis_v4.md" \
  >"$OUT_DIR/bootstrap.log" 2>&1 || true
cp -f "$OUT_DIR/bootstrap_ex_cis_v4.md" "$REPO_ROOT/runs/reports/bootstrap_ex_cis_v4.md" 2>/dev/null || true

echo "finished_utc=$(date -u +%Y-%m-%dT%H:%M:%SZ)" | tee -a "$STATUS_FILE"
ls -lt "$REPO_ROOT/runs/batches"/parallel_compose_full500_r3_gemini* \
       "$REPO_ROOT/runs/batches"/parallel_compose_p3_full500* \
       "$REPO_ROOT/runs/batches"/parallel_fullstack_prune_r25_repair* \
       "$REPO_ROOT/runs/batches"/parallel_*_rep2_gemini* 2>/dev/null | head -20 || true
