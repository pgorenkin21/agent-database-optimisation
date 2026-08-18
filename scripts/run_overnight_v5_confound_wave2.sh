#!/usr/bin/env bash
# v5 confound cleanup, wave 2 — the last two DeepSeek controls still stranded
# in the V3.2 era.
#
# Wave 1 (run_overnight_v5_deepseek_confound.sh) re-ran P0 / PC / P1 on
# v4-flash and CONFIRMED the confound: DeepSeek P0 51.4 (V3.2, Jul) -> 58.8
# (v4-flash, Aug), a +7.4 pp era shift that fully accounts for the paper's
# claimed +7.0 pp compose gain (within-era: -0.4 pp, CI includes 0).
#
# Two DeepSeek comparisons still straddle the eras because no v4-flash control
# exists for them:
#   prune vs P0        -> needs schema_prune_iso on v4-flash
#   P3 stack vs P2     -> needs fullstack_prune (the P2 stack) on v4-flash
#
# Flags below are copied from the July batches they replace, so the only thing
# that differs is the model era.
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$REPO_ROOT"

STAMP="${OVERNIGHT_STAMP:-$(date -u +%Y%m%d_%H%M%S)_v5_confound_w2}"
OUT_DIR="$REPO_ROOT/runs/overnight/$STAMP"
mkdir -p "$OUT_DIR"
STATUS_FILE="$OUT_DIR/status.txt"
echo "$STAMP" > "$REPO_ROOT/runs/overnight/LATEST_V5_CONFOUND_W2"

echo "overnight_stamp=$STAMP" | tee "$STATUS_FILE"
echo "started_utc=$(date -u +%Y-%m-%dT%H:%M:%SZ)" | tee -a "$STATUS_FILE"
echo "paper=draft_paper_ieee_v5 — remaining DeepSeek v4-flash controls" | tee -a "$STATUS_FILE"

# NOTE: run_parallel_batch.py returns 1 whenever any task scores EX=0, so a
# non-zero rc is normal for any batch below 100% EX. Judge success by the
# written JSON (task_count / api_failure_count), not by rc.
run_one() {
  local name="$1"
  shift
  local log="$OUT_DIR/${name}.log"
  echo "[$(date -u +%H:%M:%S)] START $name" | tee -a "$STATUS_FILE"
  set +e
  uv run python -u scripts/run_parallel_batch.py "$@" >"$log" 2>&1
  local rc=$?
  set -e
  echo "[$(date -u +%H:%M:%S)] DONE  $name (rc=$rc; rc=1 is normal — see NOTE)" | tee -a "$STATUS_FILE"
  return 0
}

echo "=== DeepSeek v4-flash controls (sequential, one provider) ===" | tee -a "$STATUS_FILE"

run_one "ds_schema_prune_iso_full500_r3_v4f" \
  --model deepseek-v3.2 \
  --limit 500 --replicas 3 --policy best_of_n \
  --schema-pruning --schema-pruning-mode hybrid \
  --batch-id "schema_prune_iso_full500_r3_v4f"

run_one "ds_fullstack_prune_full500_r3_v4f" \
  --model deepseek-v3.2 \
  --limit 500 --replicas 3 --policy best_of_n \
  --shared-cache --discovery-board --early-stop \
  --schema-pruning --schema-pruning-mode hybrid \
  --batch-id "fullstack_prune_full500_r3_v4f"

echo "=== Completeness check ===" | tee -a "$STATUS_FILE"
uv run python - <<'PY' 2>&1 | tee -a "$STATUS_FILE"
import json, glob
for tag in ("schema_prune_iso_full500_r3_v4f", "fullstack_prune_full500_r3_v4f"):
    g = glob.glob(f'runs/batches/parallel_{tag}_deepseek*.json')
    if not g:
        print(f'{tag}: MISSING')
        continue
    d = json.load(open(g[0]))
    print(f"{tag}: tasks={d.get('task_count')} completed={d.get('completed_task_count')} "
          f"apifail={d.get('api_failure_count')} EX={d.get('ex_accuracy_pct')}")
PY

echo "finished_utc=$(date -u +%Y-%m-%dT%H:%M:%SZ)" | tee -a "$STATUS_FILE"
