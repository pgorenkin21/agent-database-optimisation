#!/usr/bin/env bash
# v5 robustness — DeepSeek model-era confound check + remaining seed gaps.
#
# WHY THIS EXISTS
#   configs/models.yaml documents that `deepseek-chat` was folded into
#   deepseek-v4-flash on 2026-07-24. Confirmed live on 2026-08-10: the API now
#   serves `deepseek-v4-flash` and V3.2 is no longer listed at all.
#
#   The DeepSeek full-500 EX record splits exactly on that date:
#     Jul 16-19 (V3.2):      P0 51.4  prune 51.8  PC 52.2  P1 52.6  fullstack 54.0
#     Aug 06-09 (v4-flash):  P4 58.2  p1p4 58.4  compose 58.4  P3 57.0  ... 58.8
#
#   Every significant DeepSeek EX claim in v5 (compose +7.0, P4 +6.0, P1+P4 +5.8)
#   compares an August treatment against a July control — i.e. across a model
#   change. The step size (~6.6 pp) matches the claimed gains almost exactly.
#   GPT and Gemini, whose models did not change, show no such step.
#
#   V3.2 cannot be re-run (delisted), so the only available fix is to re-run the
#   CONTROLS on v4-flash, making both sides of each comparison the same model.
#
#   Wave A/B/C below do that, plus the two unrelated seed gaps.
#
# Batch-id suffix `_v4f` marks the model era; registry key stays deepseek-v3.2
# so filenames stay compatible with the analysis scripts (which are repointed
# afterwards by hand — see NOTE at the end).
#
# Waves are sequential; within a wave, providers run in parallel (DeepSeek
# batches never overlap each other, to stay clear of per-key rate limits).
# Expect ~3-5 h per wave based on waves 2-4. Leave the machine up.
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$REPO_ROOT"

STAMP="${OVERNIGHT_STAMP:-$(date -u +%Y%m%d_%H%M%S)_v5_confound}"
OUT_DIR="$REPO_ROOT/runs/overnight/$STAMP"
mkdir -p "$OUT_DIR"
STATUS_FILE="$OUT_DIR/status.txt"
echo "$STAMP" > "$REPO_ROOT/runs/overnight/LATEST_V5_CONFOUND"

echo "overnight_stamp=$STAMP" | tee "$STATUS_FILE"
echo "started_utc=$(date -u +%Y-%m-%dT%H:%M:%SZ)" | tee -a "$STATUS_FILE"
echo "paper=draft_paper_ieee_v5 — DeepSeek model-era confound + seed gaps" | tee -a "$STATUS_FILE"

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

# The existing Gemini p3_full500_r3 batch is 500/500 API failures (EX 0.0,
# completed 0) — worthless, and re-running under the same batch-id overwrites
# it so the analysis picks the good data up automatically. Back it up anyway.
mkdir -p "$OUT_DIR/replaced"
cp -f runs/batches/parallel_p3_full500_r3_gemini-2.5-flash_*.json \
      "$OUT_DIR/replaced/" 2>/dev/null || true
cp -f runs/batches/parallel_p3_full500_r3_gemini-2.5-flash_*.csv \
      "$OUT_DIR/replaced/" 2>/dev/null || true

# ---------------------------------------------------------------- WAVE A ----
# DeepSeek P0 on v4-flash is THE decisive run: if it lands near 58% then the
# +7.0 pp compose gain was a model swap; if near 51% the gain is real.
echo "=== WAVE A: DS P0 (v4f) | Gemini P3 rep1 redo | GPT P1 rep2 ===" | tee -a "$STATUS_FILE"
PIDS=()

run_one "A_ds_baseline_full500_r3_v4f" \
  --model deepseek-v3.2 \
  --limit 500 --replicas 3 --policy best_of_n \
  --batch-id "baseline_full500_r3_v4f" &
PIDS+=($!)

run_one "A_gemini_p3_full500_r3_redo" \
  --model gemini-2.5-flash \
  --limit 500 --replicas 3 --policy best_of_n \
  --shared-cache --early-stop --semantic-store \
  --schema-pruning --schema-pruning-mode hybrid \
  --inter-task-delay 2.5 \
  --batch-id "p3_full500_r3" &
PIDS+=($!)

run_one "A_gpt_p1_full500_r3_rep2" \
  --model gpt-4o-mini \
  --limit 500 --replicas 3 --policy best_of_n \
  --shared-cache \
  --batch-id "p1_full500_r3_rep2" &
PIDS+=($!)

wait_wave "${PIDS[@]}" || true
echo "[$(date -u +%H:%M:%S)] wave_A_done" | tee -a "$STATUS_FILE"

# ---------------------------------------------------------------- WAVE B ----
echo "=== WAVE B: DS prompt-cache (v4f) | GPT prune rep2 ===" | tee -a "$STATUS_FILE"
PIDS=()

run_one "B_ds_pc_full500_r3_v4f" \
  --model deepseek-v3.2 \
  --limit 500 --replicas 3 --policy best_of_n \
  --prompt-cache \
  --batch-id "pc_full500_r3_v4f" &
PIDS+=($!)

run_one "B_gpt_prune_full500_r3_rep2" \
  --model gpt-4o-mini \
  --limit 500 --replicas 3 --policy best_of_n \
  --schema-pruning --schema-pruning-mode hybrid \
  --batch-id "schema_prune_iso_full500_r3_rep2" &
PIDS+=($!)

wait_wave "${PIDS[@]}" || true
echo "[$(date -u +%H:%M:%S)] wave_B_done" | tee -a "$STATUS_FILE"

# ---------------------------------------------------------------- WAVE C ----
echo "=== WAVE C: DS P1 (v4f) | Gemini P1 rep2 ===" | tee -a "$STATUS_FILE"
PIDS=()

run_one "C_ds_p1_full500_r3_v4f" \
  --model deepseek-v3.2 \
  --limit 500 --replicas 3 --policy best_of_n \
  --shared-cache \
  --batch-id "p1_full500_r3_v4f" &
PIDS+=($!)

run_one "C_gemini_p1_full500_r3_rep2" \
  --model gemini-2.5-flash \
  --limit 500 --replicas 3 --policy best_of_n \
  --shared-cache \
  --inter-task-delay 2.5 \
  --batch-id "p1_full500_r3_rep2" &
PIDS+=($!)

wait_wave "${PIDS[@]}" || true
echo "[$(date -u +%H:%M:%S)] wave_C_done" | tee -a "$STATUS_FILE"

# ------------------------------------------------------------- ANALYSIS -----
echo "=== Offline robustness pack refresh ===" | tee -a "$STATUS_FILE"
uv run python scripts/generate_robustness_pack.py \
  >"$OUT_DIR/robustness_pack.log" 2>&1 || true
for f in bootstrap_ex_cis_v4 token_db_cis_v4 rep_stability_v4 robustness_pack_v4; do
  cp -f "$REPO_ROOT/runs/reports/${f}.md" "$OUT_DIR/" 2>/dev/null || true
done

echo "=== DeepSeek era comparison (the answer) ===" | tee -a "$STATUS_FILE"
uv run python - <<'PY' 2>&1 | tee -a "$STATUS_FILE"
import json, glob
def ex(tag):
    g = glob.glob(f'runs/batches/parallel_{tag}_deepseek*.json')
    if not g:
        return None
    d = json.load(open(g[0]))
    return d.get('ex_accuracy_pct'), d.get('generated_at', '')[:10]
old = ex('baseline_full500_r3')
new = ex('baseline_full500_r3_v4f')
print(f'DeepSeek P0 July  (V3.2)     : {old}')
print(f'DeepSeek P0 today (v4-flash) : {new}')
if old and new:
    print(f'era shift = {new[0] - old[0]:+.1f} pp')
    print('compose vs P0 claimed +7.0 pp -> within-era delta is '
          f'{58.4 - new[0]:+.1f} pp')
PY

echo "finished_utc=$(date -u +%Y-%m-%dT%H:%M:%SZ)" | tee -a "$STATUS_FILE"

# NOTE: generate_robustness_pack.py still points DeepSeek comparisons at the
# July controls (baseline_full500_r3, pc_full500_r3, p1_full500_r3). After these
# land, repoint the DeepSeek rows to the *_v4f controls before quoting any
# DeepSeek EX delta in the paper.
ls -lt "$REPO_ROOT/runs/batches"/parallel_*_v4f_* 2>/dev/null | head -20 || true
