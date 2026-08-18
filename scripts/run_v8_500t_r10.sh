#!/usr/bin/env bash
# v8 500-task generalisation at N=10 — all five conditions.
#
# Completes the matrix at a second replica count on the full benchmark. The
# 500-task N=3 row (finished 16 Aug) bounded accuracy change to ~+/-2pp while
# showing 40-86% billed-token reductions; this tests whether that holds as
# replicas scale.
#
# Two cells are expected to move rather than merely confirm:
#   * prompt cache should IMPROVE with N — each extra replica reuses the same
#     cached prefix.
#   * semantic store should get WORSE with N — the injection tax scaled hard at
#     50 tasks (DeepSeek 10.2 -> 32.4 -> 89.4 inj/task across N=3/10/25) but was
#     invisible at 500t N=3 (8.5 inj/task, null effect). N=10 roughly triples it.
#
# Waves are ordered by importance, not by method: control first, then the two
# arms the paper rests on, then the two that came back null at N=3. If the run
# is interrupted at hour 10, what survives is what matters.
#
# ~13h20, ~$113 (priced from the measured N=3 run: $33.84 for five conditions,
# scaled 3.33x for tokens; wall-clock scales only ~1.2x since replicas run
# concurrently within a task).
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$REPO_ROOT"

# --- guard: never run alongside another v8 batch driver ----------------------
for other in run_v8_matrix.sh run_v8_cleanup.sh run_v8_resume.sh \
             run_v8_prune_fill.sh run_v8_500t_r3.sh; do
  if pgrep -f "$other" >/dev/null 2>&1; then
    echo "REFUSING TO START: $other is already running." >&2
    echo "Wait for it to finish, then re-run this script." >&2
    exit 1
  fi
done

# A second copy of THIS script needs a pid lock rather than pgrep: pgrep would
# match our own process and the shell wrapper that launched us, and macOS pgrep
# has no -c to count matches. `kill -0` tests whether a recorded pid is alive,
# so a stale lock from a killed run does not block a restart.
LOCK="$REPO_ROOT/runs/.v8_500t_r10.lock"
if [ -e "$LOCK" ] && kill -0 "$(cat "$LOCK" 2>/dev/null)" 2>/dev/null; then
  echo "REFUSING TO START: another copy of this script is running (pid $(cat "$LOCK"))." >&2
  exit 1
fi
echo $$ > "$LOCK"
trap 'rm -f "$LOCK"' EXIT

STAMP="${OVERNIGHT_STAMP:-$(date -u +%Y%m%d_%H%M%S)_v8_500t_r10}"
OUT_DIR="$REPO_ROOT/runs/overnight/$STAMP"
mkdir -p "$OUT_DIR"
STATUS="$OUT_DIR/status.txt"
echo "$STAMP" > "$REPO_ROOT/runs/overnight/LATEST_V8_500T_R10"

echo "overnight_stamp=$STAMP"                     | tee    "$STATUS"
echo "started_utc=$(date -u +%Y-%m-%dT%H:%M:%SZ)" | tee -a "$STATUS"
echo "paper=draft_paper_ieee_v8 — 500-task N=10 generalisation" | tee -a "$STATUS"

IFS=' ' read -r -a MODELS <<< "${MODELS:-gpt-4o-mini gemini-2.5-flash deepseek-v3.2}"
MIN_COMPLETION=0.90
LIMIT=500
N=10
# Idle gap between waves so the providers are not hit continuously for 13h.
COOLDOWN="${COOLDOWN_SECONDS:-300}"
# Gemini is the only model that has ever needed pacing, and the only one that
# tripped a quota rejection (17 Aug). Raised 2.5 -> 4.0 to cut its request rate;
# costs ~12 min per 500-task wave, which is cheap against losing one.
GEMINI_DELAY="${GEMINI_INTER_TASK_DELAY:-4.0}"

echo "models=${MODELS[*]}" | tee -a "$STATUS"
echo "cooldown_between_waves=${COOLDOWN}s" | tee -a "$STATUS"

echo "=== pre-flight: provider reachability ===" | tee -a "$STATUS"
uv run python - "${MODELS[@]}" <<'PY' 2>&1 | tee -a "$STATUS"
# One 3-token request per model through the same client factory the batch
# runner uses, so an unreachable provider fails here rather than hours in.
import sys, time
from dotenv import load_dotenv
load_dotenv('.env')
from src.llm.client import create_chat_client
from src.llm.models import load_model_registry

registry = load_model_registry()
bad = []
for key in sys.argv[1:]:
    try:
        spec = registry.get(key)
        client = create_chat_client(spec)
        t = time.time()
        if spec.provider == "google":
            client.models.generate_content(model=spec.api_model, contents="hi")
        else:
            client.chat.completions.create(model=spec.api_model,
                                           messages=[{"role": "user", "content": "hi"}],
                                           max_tokens=3)
        print(f"  {key}: OK ({time.time()-t:.1f}s)")
    except Exception as e:
        print(f"  {key}: FAIL {type(e).__name__}: {str(e)[:80]}")
        bad.append(key)
if bad:
    print(f"  pre-flight FAILED for: {', '.join(bad)} — not starting.")
    sys.exit(2)
print("  pre-flight OK — all providers reachable")
PY

run_one() {
  local name="$1"; shift
  local log="$OUT_DIR/${name}.log"
  echo "[$(date -u +%H:%M:%S)] START $name" | tee -a "$STATUS"
  set +e
  uv run python -u scripts/run_parallel_batch.py "$@" >"$log" 2>&1
  local rc=$?
  set -e
  # BSD grep (macOS host) has no -P; this sed is portable across host and the
  # Linux devcontainer.
  local ex; ex=$(sed -n 's/^[[:space:]]*EX:[[:space:]]*\([0-9][0-9.]*\)%.*/\1/p' "$log" | tail -1 || true)
  # `grep -c` prints the count AND exits 1 when it is zero, so `|| echo 0`
  # would append a second "0" and break the status line on clean runs.
  local errs; errs=$(grep -c -- '-> ERROR' "$log" 2>/dev/null || true)
  echo "[$(date -u +%H:%M:%S)] DONE  $name (rc=$rc, EX=${ex:-?}, task-errors=$errs)" \
    | tee -a "$STATUS"
  return 0
}

wave_done_already() {
  uv run python - "$1" "$MIN_COMPLETION" "${MODELS[@]}" <<'PY'
import glob, json, sys
bid, floor, models = sys.argv[1], float(sys.argv[2]), sys.argv[3:]
ok = 0
for p in glob.glob(f"runs/batches/parallel_{bid}_*.json"):
    d = json.load(open(p))
    if d.get("model_key") not in models:
        continue
    tot, done = d.get("task_count") or 0, d.get("completed_task_count") or 0
    if tot and done / tot >= floor:
        ok += 1
sys.exit(0 if ok >= len(models) else 1)
PY
}

gate() {
  uv run python - "$1" "$MIN_COMPLETION" "${MODELS[@]}" <<'PY' 2>&1 | tee -a "$STATUS"
import glob, json, sys
bid, floor, models = sys.argv[1], float(sys.argv[2]), sys.argv[3:]
bad = []
for p in sorted(glob.glob(f"runs/batches/parallel_{bid}_*.json")):
    d = json.load(open(p))
    if d.get("model_key") not in models:
        continue
    tot, done = d.get("task_count") or 0, d.get("completed_task_count") or 0
    frac = done / tot if tot else 0
    flag = "" if frac >= floor else "  <-- BELOW FLOOR"
    print(f"  GATE {bid} {d.get('model_key'):17s} {done}/{tot} "
          f"({frac:.0%}) fail={d.get('api_failure_count')}{flag}")
    if frac < floor:
        bad.append(d.get("model_key"))
if bad:
    print(f"  GATE FAILED for {', '.join(bad)} — stopping so the remaining waves "
          f"are not wasted. Fix connectivity and re-run; completed waves are "
          f"skipped automatically.")
    sys.exit(3)
print(f"  GATE {bid} PASSED")
PY
}

# WAVE_RAN lets the caller decide whether a cooldown is warranted. Deliberately
# a global rather than a return code: calling wave() inside an `if` condition
# would suppress `set -e` for its whole body, so a failing gate would no longer
# halt the run — which is the one thing the gate exists to do.
WAVE_RAN=0

wave() {  # wave <method> <flags...>
  local method="$1"; shift
  local batch_id="v8_${method}_500t_r${N}"
  WAVE_RAN=0
  if wave_done_already "$batch_id"; then
    echo "=== SKIP $batch_id (already complete) ===" | tee -a "$STATUS"
    return 0
  fi
  echo "=== WAVE $batch_id ===" | tee -a "$STATUS"
  local pids=() m safe delay
  for m in "${MODELS[@]}"; do
    safe=${m//./-}
    delay=""
    [[ "$m" == "gemini-2.5-flash" ]] && delay="--inter-task-delay $GEMINI_DELAY"
    # shellcheck disable=SC2086
    run_one "${batch_id}_${safe}" \
      --model "$m" --limit "$LIMIT" --replicas "$N" --policy best_of_n \
      "$@" $delay --batch-id "$batch_id" &
    pids+=($!)
  done
  for p in "${pids[@]}"; do wait "$p" || true; done
  gate "$batch_id"
  WAVE_RAN=1
}

maybe_cooldown() {
  [ "$WAVE_RAN" -eq 1 ] || return 0
  echo "[$(date -u +%H:%M:%S)] cooldown ${COOLDOWN}s before next wave" | tee -a "$STATUS"
  sleep "$COOLDOWN"
}

# Same three methods as the 50-task matrix, same flags. Nothing else is ever
# enabled: no early-stop, no P1 shared cache, no P4 suppressor.
PRUNE=(--schema-pruning --schema-pruning-mode hybrid)
P3=(--semantic-store)
PC=(--prompt-cache)
COMP=(--semantic-store --prompt-cache --schema-pruning --schema-pruning-mode hybrid)

# Ordered by importance — see header.
wave p0;                  maybe_cooldown
wave pc    "${PC[@]}";    maybe_cooldown
wave comp  "${COMP[@]}";  maybe_cooldown
wave prune "${PRUNE[@]}"; maybe_cooldown
wave p3    "${P3[@]}"     # last — no cooldown needed after it

echo "=== completeness ===" | tee -a "$STATUS"
uv run python - <<'PY' 2>&1 | tee -a "$STATUS"
import json, glob
for p in sorted(glob.glob('runs/batches/parallel_v8_*_500t_r10_*.json')):
    d = json.load(open(p))
    print(f"  {d.get('batch_id'):21s} {d.get('model_key'):17s} "
          f"tasks={d.get('completed_task_count')}/{d.get('task_count')} "
          f"fail={d.get('api_failure_count')} EX={d.get('ex_accuracy_pct')} "
          f"cached%={d.get('batch_cached_prompt_pct')}")
PY

echo "finished_utc=$(date -u +%Y-%m-%dT%H:%M:%SZ)" | tee -a "$STATUS"
echo "Next: uv run python scripts/analyze_v8_results.py" | tee -a "$STATUS"
