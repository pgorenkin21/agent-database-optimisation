#!/usr/bin/env bash
# Statistical / generalisation credibility queue for draft_paper_ieee_v4.
#
# v4 §Threats: smoke-50 only; same full-split check pending beyond pruning.
# v4 §Future work (2): scale-up of all five policies to full 500-task mini-dev
#                      with bootstrap CIs.
#
# Already on disk at full-500 N=3: P0, P1, prune, prompt-cache, fullstack+prune.
# Still missing at full-500 (this script):
#   1. P4 isolated  (prompt-cache + explore-suppressor)  × 3 models
#   2. P1+P4        (shared-cache + prompt-cache + P4)   × 3 models
#   3. P3 stack     (P1 + early-stop + hybrid prune + P3) × 3 models
#      → directly tests the model-conditioning claim at scale
#
# Runs models in parallel within each wave; waves sequential.
# Use --limit 500 against default.yaml (subset_limit 50 overridden by --limit).
#
# Optional: wait for an existing overnight composition job first:
#   WAIT_FOR_PATTERN='pc_p1_p4_prune_r25' bash scripts/run_overnight_v4_credibility.sh
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
echo "paper=draft_paper_ieee_v4 statistical/generalisation credibility" | tee -a "$STATUS_FILE"
echo "repo=$REPO_ROOT" | tee -a "$STATUS_FILE"

if [[ -n "${WAIT_FOR_PATTERN:-}" ]]; then
  echo "[$(date -u +%H:%M:%S)] waiting for processes matching: $WAIT_FOR_PATTERN" | tee -a "$STATUS_FILE"
  while pgrep -f "$WAIT_FOR_PATTERN" >/dev/null 2>&1; do
    sleep 60
  done
  echo "[$(date -u +%H:%M:%S)] wait cleared — starting credibility waves" | tee -a "$STATUS_FILE"
fi

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

wait_wave() {
  local rc=0
  for pid in "$@"; do
    wait "$pid" || rc=1
  done
  return $rc
}

echo "=== WAVE 1: P4 isolated full-500 N=3 (3 models) ===" | tee -a "$STATUS_FILE"
PIDS=()
for model in gemini-2.5-flash gpt-4o-mini deepseek-v3.2; do
  safe=${model//./-}
  delay_args=()
  if [[ "$model" == "gemini-2.5-flash" ]]; then
    delay_args=(--inter-task-delay 2.0)
  fi
  run_one "p4_full500_r3_${safe}" \
    --model "$model" \
    --limit 500 \
    --replicas 3 \
    --policy best_of_n \
    --prompt-cache \
    --explore-suppressor \
    "${delay_args[@]}" \
    --batch-id "p4_full500_r3" &
  PIDS+=($!)
done
wait_wave "${PIDS[@]}" || true
echo "[$(date -u +%H:%M:%S)] wave1_done" | tee -a "$STATUS_FILE"

echo "=== WAVE 2: P1+P4 full-500 N=3 (3 models) ===" | tee -a "$STATUS_FILE"
PIDS=()
for model in gemini-2.5-flash gpt-4o-mini deepseek-v3.2; do
  safe=${model//./-}
  delay_args=()
  if [[ "$model" == "gemini-2.5-flash" ]]; then
    delay_args=(--inter-task-delay 2.0)
  fi
  run_one "p1p4_full500_r3_${safe}" \
    --model "$model" \
    --limit 500 \
    --replicas 3 \
    --policy best_of_n \
    --shared-cache \
    --prompt-cache \
    --explore-suppressor \
    "${delay_args[@]}" \
    --batch-id "p1p4_full500_r3" &
  PIDS+=($!)
done
wait_wave "${PIDS[@]}" || true
echo "[$(date -u +%H:%M:%S)] wave2_done" | tee -a "$STATUS_FILE"

echo "=== WAVE 3: P3 stack full-500 N=3 (model-conditioning at scale) ===" | tee -a "$STATUS_FILE"
PIDS=()
for model in gemini-2.5-flash gpt-4o-mini deepseek-v3.2; do
  safe=${model//./-}
  delay_args=()
  if [[ "$model" == "gemini-2.5-flash" ]]; then
    delay_args=(--inter-task-delay 2.0)
  fi
  run_one "p3_full500_r3_${safe}" \
    --model "$model" \
    --limit 500 \
    --replicas 3 \
    --policy best_of_n \
    --shared-cache \
    --early-stop \
    --semantic-store \
    --schema-pruning \
    --schema-pruning-mode hybrid \
    "${delay_args[@]}" \
    --batch-id "p3_full500_r3" &
  PIDS+=($!)
done
wait_wave "${PIDS[@]}" || true
echo "[$(date -u +%H:%M:%S)] wave3_done" | tee -a "$STATUS_FILE"

# Refresh bootstrap report including any new full-500 files once they land
echo "=== Offline: refresh bootstrap CIs ===" | tee -a "$STATUS_FILE"
uv run python scripts/bootstrap_ex_cis.py \
  --out "$OUT_DIR/bootstrap_ex_cis_v4.md" \
  >"$OUT_DIR/bootstrap.log" 2>&1 || true

echo "finished_utc=$(date -u +%Y-%m-%dT%H:%M:%SZ)" | tee -a "$STATUS_FILE"
echo "Done. Status: $STATUS_FILE"
ls -lt "$REPO_ROOT/runs/batches"/parallel_p4_full500_* \
       "$REPO_ROOT/runs/batches"/parallel_p1p4_full500_* \
       "$REPO_ROOT/runs/batches"/parallel_p3_full500_* 2>/dev/null | head -30 || true
