#!/usr/bin/env bash
# v8 run matrix — three prompt-layer methods, in isolation and composed.
#
# METHODS (nothing else is ever enabled):
#   prune  : --schema-pruning --schema-pruning-mode hybrid   (prompt size)
#   p3     : --semantic-store                                (prompt content)
#   pc     : --prompt-cache                                  (billing)
#   comp   : all three together
#
# Deliberately NO --early-stop, NO --shared-cache (P1), NO --explore-suppressor
# (P4) in any arm, so the composed result is the sum of exactly these three.
# P0 baselines already exist at every cell and are not re-run.
#
# Cells already on disk and skipped: prune 50t N=10/25, prune 500t N=3,
# pc 50t N=3/10/25, pc 500t N=3.
#
# Ordering puts the cheap 50-task blocks first so the P3 mechanism is validated
# and the isolation story is complete before the long 500-task waves start.
#
# NOTE: run_parallel_batch.py returns 1 whenever any task scores EX=0, so a
# non-zero rc is normal. Judge success by the written JSON, not by rc.
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$REPO_ROOT"

STAMP="${OVERNIGHT_STAMP:-$(date -u +%Y%m%d_%H%M%S)_v8_matrix}"
OUT_DIR="$REPO_ROOT/runs/overnight/$STAMP"
mkdir -p "$OUT_DIR"
STATUS="$OUT_DIR/status.txt"
echo "$STAMP" > "$REPO_ROOT/runs/overnight/LATEST_V8_MATRIX"

# Optional: run a subset, e.g. BLOCKS="A C1" bash scripts/run_v8_matrix.sh
BLOCKS="${BLOCKS:-A C1 B C2}"

echo "overnight_stamp=$STAMP"                     | tee    "$STATUS"
echo "started_utc=$(date -u +%Y-%m-%dT%H:%M:%SZ)" | tee -a "$STATUS"
echo "paper=draft_paper_ieee_v8 — 3-method token-bill matrix" | tee -a "$STATUS"
echo "blocks=$BLOCKS"                             | tee -a "$STATUS"

MODELS=(gpt-4o-mini gemini-2.5-flash deepseek-v3.2)

flags_for() {  # $1 = method
  case "$1" in
    prune) echo "--schema-pruning --schema-pruning-mode hybrid" ;;
    p3)    echo "--semantic-store" ;;
    pc)    echo "--prompt-cache" ;;
    comp)  echo "--semantic-store --prompt-cache --schema-pruning --schema-pruning-mode hybrid" ;;
    *)     echo "UNKNOWN_METHOD_$1" ;;
  esac
}

run_one() {
  local name="$1"; shift
  local log="$OUT_DIR/${name}.log"
  echo "[$(date -u +%H:%M:%S)] START $name" | tee -a "$STATUS"
  set +e
  uv run python -u scripts/run_parallel_batch.py "$@" >"$log" 2>&1
  local rc=$?
  set -e
  # NB: BSD grep (macOS host) has no -P; this sed is portable across the host
  # and the Linux devcontainer, where the 15 Aug run happened to work.
  local ex; ex=$(sed -n 's/^[[:space:]]*EX:[[:space:]]*\([0-9][0-9.]*\)%.*/\1/p' "$log" | tail -1 || true)
  echo "[$(date -u +%H:%M:%S)] DONE  $name (rc=$rc, EX=${ex:-?})" | tee -a "$STATUS"
  return 0
}

# wave <method> <n_replicas> <task_limit> ; all three models in parallel
wave() {
  local method="$1" n="$2" limit="$3"
  local scale="500"; [[ "$limit" -le 100 ]] && scale="50"
  local batch_id="v8_${method}_${scale}t_r${n}"
  echo "=== WAVE $batch_id ===" | tee -a "$STATUS"
  local pids=() m safe delay
  for m in "${MODELS[@]}"; do
    safe=${m//./-}
    delay=""
    [[ "$m" == "gemini-2.5-flash" ]] && delay="--inter-task-delay 2.5"
    # shellcheck disable=SC2046
    run_one "${batch_id}_${safe}" \
      --model "$m" --limit "$limit" --replicas "$n" --policy best_of_n \
      $(flags_for "$method") $delay \
      --batch-id "$batch_id" &
    pids+=($!)
  done
  for p in "${pids[@]}"; do wait "$p" || true; done
  echo "[$(date -u +%H:%M:%S)] wave_done $batch_id" | tee -a "$STATUS"
}

has_block() { [[ " $BLOCKS " == *" $1 "* ]]; }

# ---- Block A: 50-task isolation (cheap; validates P3 before the long waves) --
if has_block A; then
  echo "##### BLOCK A — 50-task isolation #####" | tee -a "$STATUS"
  wave p3    3 50
  # Gate: isolated P3 is a never-before-run configuration. Stop the whole run
  # if it is not actually injecting facts, rather than burn the later waves.
  uv run python - <<'PY' 2>&1 | tee -a "$STATUS"
import json, glob, sys
ok = False
for p in glob.glob('runs/batches/parallel_v8_p3_50t_r3_*.json'):
    d = json.load(open(p))
    inj = d.get('total_middleware_semantic_injections') or 0
    print(f"  P3 GATE {d.get('model_key'):17s} injections={inj} "
          f"tasks={d.get('task_count')} EX={d.get('ex_accuracy_pct')}")
    if inj > 0:
        ok = True
if not ok:
    print("  P3 GATE FAILED — no semantic injections recorded. Stopping.")
    sys.exit(3)
print("  P3 GATE PASSED")
PY
  wave prune 3 50
  wave p3   10 50
  wave p3   25 50
fi

# ---- Block C1: 50-task composed -------------------------------------------
if has_block C1; then
  echo "##### BLOCK C1 — 50-task composed #####" | tee -a "$STATUS"
  wave comp  3 50
  wave comp 10 50
  wave comp 25 50
fi

# ---- Block B: 500-task isolation ------------------------------------------
if has_block B; then
  echo "##### BLOCK B — 500-task isolation #####" | tee -a "$STATUS"
  wave p3     3 500
  wave prune 10 500
  wave p3    10 500
  wave pc    10 500
fi

# ---- Block C2: 500-task composed ------------------------------------------
if has_block C2; then
  echo "##### BLOCK C2 — 500-task composed #####" | tee -a "$STATUS"
  wave comp  3 500
  wave comp 10 500
fi

echo "=== completeness ===" | tee -a "$STATUS"
uv run python - <<'PY' 2>&1 | tee -a "$STATUS"
import json, glob
rows = []
for p in glob.glob('runs/batches/parallel_v8_*.json'):
    d = json.load(open(p))
    rows.append((d.get('batch_id'), d.get('model_key'), d.get('n_replicas'),
                 d.get('task_count'), d.get('completed_task_count'),
                 d.get('api_failure_count'), d.get('ex_accuracy_pct'),
                 d.get('total_middleware_semantic_injections'),
                 d.get('batch_cached_prompt_pct')))
for r in sorted(rows):
    print(f"  {r[0]:22s} {r[1]:17s} r{r[2]:<3} tasks={r[3]} done={r[4]} "
          f"fail={r[5]} EX={r[6]} inj={r[7]} cached%={r[8]}")
print(f"  total v8 batches on disk: {len(rows)}")
PY

echo "finished_utc=$(date -u +%Y-%m-%dT%H:%M:%SZ)" | tee -a "$STATUS"
