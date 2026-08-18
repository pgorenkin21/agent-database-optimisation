#!/usr/bin/env bash
# Wave E: P2 stack full-500 N=10 × {GPT, DeepSeek now; Gemini after noisy-repair rep2}.
#
# GPT/DeepSeek do not share the Gemini API, so they start immediately.
# Gemini waits until compose N=10 rep2 repair has merged (or the repair
# parent has exited) so we do not pile onto Flash during the mop-up.
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$REPO_ROOT"
BATCH="$REPO_ROOT/runs/batches"

STAMP="${OVERNIGHT_STAMP:-$(date -u +%Y%m%d_%H%M%S)_p2_full500_r10}"
OUT_DIR="$REPO_ROOT/runs/overnight/$STAMP"
mkdir -p "$OUT_DIR"
STATUS_FILE="$OUT_DIR/status.txt"
echo "$STAMP" > "$REPO_ROOT/runs/overnight/LATEST_P2_FULL500_R10"

echo "overnight_stamp=$STAMP" | tee "$STATUS_FILE"
echo "started_utc=$(date -u +%Y-%m-%dT%H:%M:%SZ)" | tee -a "$STATUS_FILE"
echo "paper=draft_paper_ieee_v5 — Wave E P2 full-500 N=10 (GPT+DS now, Gemini after repair)" | tee -a "$STATUS_FILE"

run_one() {
  local name="$1"
  shift
  local log="$OUT_DIR/${name}.log"
  echo "[$(date -u +%H:%M:%S)] START $name" | tee -a "$STATUS_FILE"
  set +e
  uv run python -u scripts/run_parallel_batch.py "$@" >"$log" 2>&1
  local rc=$?
  set -e
  echo "[$(date -u +%H:%M:%S)] DONE  $name (rc=$rc; rc=1 is normal — check JSON)" | tee -a "$STATUS_FILE"
  return 0
}

p2_args_common=(
  --limit 500
  --replicas 10
  --policy best_of_n
  --shared-cache
  --discovery-board
  --early-stop
  --schema-pruning
  --schema-pruning-mode hybrid
  --batch-id p2_full500_r10
)

echo "=== WAVE E: P2 GPT + DeepSeek (Gemini waits for repair) ===" | tee -a "$STATUS_FILE"

run_one p2_full500_r10_gpt-4o-mini \
  --model gpt-4o-mini \
  "${p2_args_common[@]}" &
PID_GPT=$!

run_one p2_full500_r10_deepseek-v3-2 \
  --model deepseek-v3.2 \
  "${p2_args_common[@]}" &
PID_DS=$!

echo "[$(date -u +%H:%M:%S)] waiting for Gemini compose N=10 rep2 repair to merge..." | tee -a "$STATUS_FILE"
REPAIR_STAMP_FILE="$REPO_ROOT/runs/overnight/LATEST_GEMINI_NOISY_REPAIR"
REP2_JSON="$BATCH/parallel_compose_full500_r10_rep2_gemini-2.5-flash_r10_best_of_n_p1_cache_promptcache_early_stop_schema_prune_p4suppress.json"

while true; do
  repaired=0
  if [[ -f "$REP2_JSON" ]] && python3 - "$REP2_JSON" <<'PY'
import json, sys
p = sys.argv[1]
d = json.load(open(p))
# merged repair sets repaired_at; also treat api_failure_count << 272 as done
api = int(d.get("api_failure_count") or 0)
rep = d.get("repaired_at")
sys.exit(0 if (rep and api < 200) else 1)
PY
  then
    repaired=1
  fi

  repair_running=0
  pgrep -f 'run_repair_gemini_noisy_resume.sh' >/dev/null 2>&1 && repair_running=1
  pgrep -f 'compose_full500_r10_rep2_gemini_repair' >/dev/null 2>&1 && repair_running=1

  echo "[$(date -u +%H:%M:%S)] rep2_merged=$repaired repair_running=$repair_running" | tee -a "$STATUS_FILE"

  if [[ "$repaired" -eq 1 ]]; then
    break
  fi
  if [[ "$repair_running" -eq 0 && "$repaired" -eq 0 ]]; then
    echo "[$(date -u +%H:%M:%S)] repair parent idle and rep2 not merged — starting Gemini P2 anyway" | tee -a "$STATUS_FILE"
    break
  fi
  sleep 60
done

echo "=== WAVE E: P2 Gemini ===" | tee -a "$STATUS_FILE"
run_one p2_full500_r10_gemini-2-5-flash \
  --model gemini-2.5-flash \
  --inter-task-delay 2.5 \
  "${p2_args_common[@]}" &
PID_GEM=$!

wait "$PID_GPT" || true
wait "$PID_DS" || true
wait "$PID_GEM" || true

echo "[$(date -u +%H:%M:%S)] waveE_done" | tee -a "$STATUS_FILE"
echo "finished_utc=$(date -u +%Y-%m-%dT%H:%M:%SZ)" | tee -a "$STATUS_FILE"
ls -lt "$BATCH"/parallel_p2_full500_r10_*.json 2>/dev/null | head -10 | tee -a "$STATUS_FILE" || true
