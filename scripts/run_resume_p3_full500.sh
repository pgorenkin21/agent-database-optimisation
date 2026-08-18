#!/usr/bin/env bash
# Resume unfinished Wave 3 only: P3 stack full-500 N=3 × 3 models.
# Waves 1–2 (P4, P1+P4) already complete on disk.
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$REPO_ROOT"

STAMP="${OVERNIGHT_STAMP:-$(date -u +%Y%m%d_%H%M%S)_p3_resume}"
OUT_DIR="$REPO_ROOT/runs/overnight/$STAMP"
mkdir -p "$OUT_DIR"
STATUS_FILE="$OUT_DIR/status.txt"
echo "$STAMP" > "$REPO_ROOT/runs/overnight/LATEST_CREDIBILITY"

echo "overnight_stamp=$STAMP" | tee "$STATUS_FILE"
echo "started_utc=$(date -u +%Y-%m-%dT%H:%M:%SZ)" | tee -a "$STATUS_FILE"
echo "paper=draft_paper_ieee_v4 P3 full-500 resume (wave 3 only)" | tee -a "$STATUS_FILE"

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

echo "=== P3 stack full-500 N=3 (3 models in parallel) ===" | tee -a "$STATUS_FILE"

run_one p3_full500_r3_gemini-2-5-flash \
  --model gemini-2.5-flash \
  --limit 500 \
  --replicas 3 \
  --policy best_of_n \
  --shared-cache \
  --early-stop \
  --semantic-store \
  --schema-pruning \
  --schema-pruning-mode hybrid \
  --inter-task-delay 2.0 \
  --batch-id p3_full500_r3 &
PID_GEM=$!

run_one p3_full500_r3_gpt-4o-mini \
  --model gpt-4o-mini \
  --limit 500 \
  --replicas 3 \
  --policy best_of_n \
  --shared-cache \
  --early-stop \
  --semantic-store \
  --schema-pruning \
  --schema-pruning-mode hybrid \
  --batch-id p3_full500_r3 &
PID_GPT=$!

run_one p3_full500_r3_deepseek-v3-2 \
  --model deepseek-v3.2 \
  --limit 500 \
  --replicas 3 \
  --policy best_of_n \
  --shared-cache \
  --early-stop \
  --semantic-store \
  --schema-pruning \
  --schema-pruning-mode hybrid \
  --batch-id p3_full500_r3 &
PID_DS=$!

wait "$PID_GEM" || true
wait "$PID_GPT" || true
wait "$PID_DS" || true

echo "[$(date -u +%H:%M:%S)] refreshing bootstrap CIs" | tee -a "$STATUS_FILE"
uv run python scripts/bootstrap_ex_cis.py \
  --out "$OUT_DIR/bootstrap_ex_cis_v4.md" \
  >"$OUT_DIR/bootstrap.log" 2>&1 || true
cp -f "$OUT_DIR/bootstrap_ex_cis_v4.md" "$REPO_ROOT/runs/reports/bootstrap_ex_cis_v4.md" 2>/dev/null || true

echo "finished_utc=$(date -u +%Y-%m-%dT%H:%M:%SZ)" | tee -a "$STATUS_FILE"
ls -lt "$REPO_ROOT/runs/batches"/parallel_p3_full500_* 2>/dev/null | head -10 || true
