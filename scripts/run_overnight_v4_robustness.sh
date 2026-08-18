#!/usr/bin/env bash
# Robustness queue for draft_paper_ieee_v4:
#   - Second independent smoke-50 N=25 runs (single-run / ±2–6pp noise threat)
#   - Repair confounded Gemini N=25 P2-stack (11 API failures; excluded from claims)
#
# Phase 1 (NOW): GPT + DeepSeek only — leaves Gemini alone while P3 full-500 crawls.
# Phase 2 (after overnight_more compose JSONs): Gemini repair + Gemini repeats.
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$REPO_ROOT"
BATCH="$REPO_ROOT/runs/batches"

STAMP="${OVERNIGHT_STAMP:-$(date -u +%Y%m%d_%H%M%S)_robustness}"
OUT_DIR="$REPO_ROOT/runs/overnight/$STAMP"
mkdir -p "$OUT_DIR"
STATUS_FILE="$OUT_DIR/status.txt"
echo "$STAMP" > "$REPO_ROOT/runs/overnight/LATEST_ROBUSTNESS"

echo "overnight_stamp=$STAMP" | tee "$STATUS_FILE"
echo "started_utc=$(date -u +%Y-%m-%dT%H:%M:%SZ)" | tee -a "$STATUS_FILE"
echo "paper=draft_paper_ieee_v4 robustness (rep2 + Gemini P2 repair)" | tee -a "$STATUS_FILE"

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

############################################
# Phase 1 — GPT + DeepSeek smoke N=25 repeats
############################################
echo "=== PHASE 1: GPT+DeepSeek N=25 second runs ===" | tee -a "$STATUS_FILE"

echo "--- Wave 1a: prompt-cache rep2 ---" | tee -a "$STATUS_FILE"
PIDS=()
for model in gpt-4o-mini deepseek-v3.2; do
  safe=${model//./-}
  run_one "pc_r25_rep2_${safe}" \
    --model "$model" \
    --limit 50 \
    --replicas 25 \
    --policy best_of_n \
    --prompt-cache \
    --batch-id "pc_r25_rep2" &
  PIDS+=($!)
done
wait_wave "${PIDS[@]}" || true

echo "--- Wave 1b: P4 rep2 ---" | tee -a "$STATUS_FILE"
PIDS=()
for model in gpt-4o-mini deepseek-v3.2; do
  safe=${model//./-}
  run_one "p4_r25_rep2_${safe}" \
    --model "$model" \
    --limit 50 \
    --replicas 25 \
    --policy best_of_n \
    --prompt-cache \
    --explore-suppressor \
    --batch-id "p4_r25_rep2" &
  PIDS+=($!)
done
wait_wave "${PIDS[@]}" || true

echo "--- Wave 1c: prune rep2 ---" | tee -a "$STATUS_FILE"
PIDS=()
for model in gpt-4o-mini deepseek-v3.2; do
  safe=${model//./-}
  run_one "prune_r25_rep2_${safe}" \
    --model "$model" \
    --limit 50 \
    --replicas 25 \
    --policy best_of_n \
    --schema-pruning \
    --schema-pruning-mode hybrid \
    --batch-id "prune_r25_rep2" &
  PIDS+=($!)
done
wait_wave "${PIDS[@]}" || true

echo "--- Wave 1d: P1 rep2 ---" | tee -a "$STATUS_FILE"
PIDS=()
for model in gpt-4o-mini deepseek-v3.2; do
  safe=${model//./-}
  run_one "p1_r25_rep2_${safe}" \
    --model "$model" \
    --limit 50 \
    --replicas 25 \
    --policy best_of_n \
    --shared-cache \
    --batch-id "p1_r25_rep2" &
  PIDS+=($!)
done
wait_wave "${PIDS[@]}" || true

echo "[$(date -u +%H:%M:%S)] phase1_done" | tee -a "$STATUS_FILE"

############################################
# Phase 2 — wait for compose full-500, then Gemini
############################################
COMPOSE_FILES=(
  "$BATCH/parallel_compose_full500_r3_gpt-4o-mini_r3_best_of_n_p1_cache_promptcache_early_stop_schema_prune_p4suppress.json"
  "$BATCH/parallel_compose_full500_r3_gemini-2.5-flash_r3_best_of_n_p1_cache_promptcache_early_stop_schema_prune_p4suppress.json"
  "$BATCH/parallel_compose_full500_r3_deepseek-v3.2_r3_best_of_n_p1_cache_promptcache_early_stop_schema_prune_p4suppress.json"
)

SKIP_GEMINI_FILE="$REPO_ROOT/runs/overnight/SKIP_GEMINI"
skip_gemini() { [[ -f "$SKIP_GEMINI_FILE" ]] || [[ "${SKIP_GEMINI:-}" == "1" ]]; }

echo "[$(date -u +%H:%M:%S)] waiting for compose full-500 JSONs (overnight_more)..." | tee -a "$STATUS_FILE"
while true; do
  ready=0
  for f in "${COMPOSE_FILES[@]}"; do
    [[ -f "$f" ]] && ready=$((ready + 1))
  done
  echo "[$(date -u +%H:%M:%S)] compose outputs ready: $ready/3" | tee -a "$STATUS_FILE"
  if [[ "$ready" -eq 3 ]]; then
    break
  fi
  # Credits exhausted: Phase 2 is Gemini-only — do not wait forever for a dead compose.
  if skip_gemini && [[ "$ready" -ge 2 ]]; then
    echo "[$(date -u +%H:%M:%S)] SKIP gemini compose wait (credits) — $ready/3 ready; skipping Phase 2 Gemini API" | tee -a "$STATUS_FILE"
    echo "=== PHASE 2 SKIPPED: Gemini credits depleted ===" | tee -a "$STATUS_FILE"
    echo "=== Offline: refresh bootstrap (incl. rep2 if wired) ===" | tee -a "$STATUS_FILE"
    uv run python scripts/bootstrap_ex_cis.py \
      --out "$OUT_DIR/bootstrap_ex_cis_v4.md" \
      >"$OUT_DIR/bootstrap.log" 2>&1 || true
    cp -f "$OUT_DIR/bootstrap_ex_cis_v4.md" "$REPO_ROOT/runs/reports/bootstrap_ex_cis_v4.md" 2>/dev/null || true
    echo "finished_utc=$(date -u +%Y-%m-%dT%H:%M:%SZ)" | tee -a "$STATUS_FILE"
    ls -lt "$BATCH"/parallel_*_rep2_* "$BATCH"/parallel_fullstack_prune_r25_repair_* 2>/dev/null | head -30 || true
    exit 0
  fi
  sleep 180
done

echo "=== PHASE 2: Gemini repair + N=25 repeats ===" | tee -a "$STATUS_FILE"

# Explicit v4 confound: P2-stack N=25 had 11 API failures
echo "--- Wave 2a: Gemini P2-stack N=25 repair ---" | tee -a "$STATUS_FILE"
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
  --batch-id "fullstack_prune_r25_repair" || true

echo "--- Wave 2b: Gemini prompt-cache / P4 / prune / P1 rep2 (sequential) ---" | tee -a "$STATUS_FILE"
run_one pc_r25_rep2_gemini-2-5-flash \
  --model gemini-2.5-flash \
  --limit 50 \
  --replicas 25 \
  --policy best_of_n \
  --prompt-cache \
  --inter-task-delay 2.5 \
  --batch-id "pc_r25_rep2" || true

run_one p4_r25_rep2_gemini-2-5-flash \
  --model gemini-2.5-flash \
  --limit 50 \
  --replicas 25 \
  --policy best_of_n \
  --prompt-cache \
  --explore-suppressor \
  --inter-task-delay 2.5 \
  --batch-id "p4_r25_rep2" || true

run_one prune_r25_rep2_gemini-2-5-flash \
  --model gemini-2.5-flash \
  --limit 50 \
  --replicas 25 \
  --policy best_of_n \
  --schema-pruning \
  --schema-pruning-mode hybrid \
  --inter-task-delay 2.5 \
  --batch-id "prune_r25_rep2" || true

run_one p1_r25_rep2_gemini-2-5-flash \
  --model gemini-2.5-flash \
  --limit 50 \
  --replicas 25 \
  --policy best_of_n \
  --shared-cache \
  --inter-task-delay 2.5 \
  --batch-id "p1_r25_rep2" || true

echo "=== Offline: refresh bootstrap (incl. rep2 if wired) ===" | tee -a "$STATUS_FILE"
uv run python scripts/bootstrap_ex_cis.py \
  --out "$OUT_DIR/bootstrap_ex_cis_v4.md" \
  >"$OUT_DIR/bootstrap.log" 2>&1 || true
cp -f "$OUT_DIR/bootstrap_ex_cis_v4.md" "$REPO_ROOT/runs/reports/bootstrap_ex_cis_v4.md" 2>/dev/null || true

echo "finished_utc=$(date -u +%Y-%m-%dT%H:%M:%SZ)" | tee -a "$STATUS_FILE"
ls -lt "$BATCH"/parallel_*_rep2_* "$BATCH"/parallel_fullstack_prune_r25_repair_* 2>/dev/null | head -30 || true
