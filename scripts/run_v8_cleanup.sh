#!/usr/bin/env bash
# v8 cleanup — closes two comparability gaps the first analysis pass exposed.
# Run AFTER run_v8_matrix.sh finishes (do not run concurrently: it would double
# the per-provider request rate and Gemini is already failure-prone).
#
# GAP 1 — stale 50-task P0 baselines.
#   GPT/Gemini 50-task baselines date from 11 Jun. The GPT N=25 one is degraded:
#   only 36 of 50 tasks match, at an implausible 50.0 EX, which drags every
#   GPT 50-task comparison. Fresh baselines at N=3/10/25 fix comparability for
#   all three models at once. analyze_v8_results.py already prefers a
#   `v8_p0_50t_r{N}` batch when present, so no code change is needed.
#
# GAP 2 — the 50-task prompt-cache cells are scavenged from five unrelated
#   experiments' batch ids (`pc50_*`, `dbprofile_base_*`, `suppress_base_*`),
#   and several are unusable: DeepSeek N=3/N=10 predate the current model
#   version, and Gemini N=3 matches only 21 of 50 tasks. Rather than depend on
#   that patchwork, re-run every 50-task PC cell under clean `v8_pc_50t_r*`
#   ids for all three models.
#
# ~1h30 total, ~$12.
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$REPO_ROOT"

STAMP="${OVERNIGHT_STAMP:-$(date -u +%Y%m%d_%H%M%S)_v8_cleanup}"
OUT_DIR="$REPO_ROOT/runs/overnight/$STAMP"
mkdir -p "$OUT_DIR"
STATUS="$OUT_DIR/status.txt"
echo "$STAMP" > "$REPO_ROOT/runs/overnight/LATEST_V8_CLEANUP"

echo "overnight_stamp=$STAMP"                     | tee    "$STATUS"
echo "started_utc=$(date -u +%Y-%m-%dT%H:%M:%SZ)" | tee -a "$STATUS"
echo "paper=draft_paper_ieee_v8 — baseline + DS prompt-cache cleanup" | tee -a "$STATUS"

MODELS=(gpt-4o-mini gemini-2.5-flash deepseek-v3.2)

run_one() {
  local name="$1"; shift
  local log="$OUT_DIR/${name}.log"
  echo "[$(date -u +%H:%M:%S)] START $name" | tee -a "$STATUS"
  set +e
  uv run python -u scripts/run_parallel_batch.py "$@" >"$log" 2>&1
  local rc=$?
  set -e
  # NB: BSD grep (macOS host) has no -P, which silently yielded EX=? for the
  # whole 16 Aug run. This sed is portable across host and Linux devcontainer.
  local ex; ex=$(sed -n 's/^[[:space:]]*EX:[[:space:]]*\([0-9][0-9.]*\)%.*/\1/p' "$log" | tail -1 || true)
  echo "[$(date -u +%H:%M:%S)] DONE  $name (rc=$rc, EX=${ex:-?})" | tee -a "$STATUS"
  return 0
}

echo "##### GAP 1 — fresh 50-task P0 baselines #####" | tee -a "$STATUS"
for n in 3 10 25; do
  echo "=== WAVE v8_p0_50t_r${n} ===" | tee -a "$STATUS"
  pids=()
  for m in "${MODELS[@]}"; do
    safe=${m//./-}
    delay=""
    [[ "$m" == "gemini-2.5-flash" ]] && delay="--inter-task-delay 2.5"
    # shellcheck disable=SC2086
    run_one "v8_p0_50t_r${n}_${safe}" \
      --model "$m" --limit 50 --replicas "$n" --policy best_of_n \
      $delay --batch-id "v8_p0_50t_r${n}" &
    pids+=($!)
  done
  for p in "${pids[@]}"; do wait "$p" || true; done
  echo "[$(date -u +%H:%M:%S)] wave_done v8_p0_50t_r${n}" | tee -a "$STATUS"
done

echo "##### GAP 2 — clean 50-task prompt-cache cells, all models #####" | tee -a "$STATUS"
for n in 3 10 25; do
  echo "=== WAVE v8_pc_50t_r${n} ===" | tee -a "$STATUS"
  pids=()
  for m in "${MODELS[@]}"; do
    safe=${m//./-}
    delay=""
    [[ "$m" == "gemini-2.5-flash" ]] && delay="--inter-task-delay 2.5"
    # shellcheck disable=SC2086
    run_one "v8_pc_50t_r${n}_${safe}" \
      --model "$m" --limit 50 --replicas "$n" --policy best_of_n \
      --prompt-cache $delay --batch-id "v8_pc_50t_r${n}" &
    pids+=($!)
  done
  for p in "${pids[@]}"; do wait "$p" || true; done
  echo "[$(date -u +%H:%M:%S)] wave_done v8_pc_50t_r${n}" | tee -a "$STATUS"
done

echo "=== completeness ===" | tee -a "$STATUS"
uv run python - <<'PY' 2>&1 | tee -a "$STATUS"
import json, glob
for p in sorted(glob.glob('runs/batches/parallel_v8_p0_50t_*.json')
                + glob.glob('runs/batches/parallel_v8_pc_50t_*.json')):
    d = json.load(open(p))
    print(f"  {d.get('batch_id'):18s} {d.get('model_key'):17s} r{d.get('n_replicas'):<3} "
          f"tasks={d.get('task_count')} fail={d.get('api_failure_count')} "
          f"EX={d.get('ex_accuracy_pct')} cached%={d.get('batch_cached_prompt_pct')}")
PY

echo "finished_utc=$(date -u +%Y-%m-%dT%H:%M:%SZ)" | tee -a "$STATUS"
