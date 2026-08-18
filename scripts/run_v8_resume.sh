#!/usr/bin/env bash
# v8 resume — the five 500-task waves still outstanding after the 16 Aug
# network incident. Run this on a connection you trust.
#
# Everything 50-task is already done (12 cells, all three models, verified
# >=90% complete). What remains:
#     v8_prune_500t_r10      v8_p3_500t_r10      v8_pc_500t_r10
#     v8_comp_500t_r3        v8_comp_500t_r10
# = 5 waves x 3 models = 15 batches, ~16h, ~$75.
#
# Safe to re-run: any wave whose three batches are already on disk at >=90%
# completion is skipped, so an interrupted run can simply be restarted.
#
# Two guards the original matrix script lacked:
#   * a pre-flight reachability check on all three providers;
#   * a post-wave completion gate that STOPS the run if a wave comes back
#     below 90% complete, instead of spending hours producing batches that
#     the analyser will refuse. (On 16 Aug a wave lost 205-294 of 500 tasks
#     per model to APIConnectionError and was only caught afterwards.)
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$REPO_ROOT"

STAMP="${OVERNIGHT_STAMP:-$(date -u +%Y%m%d_%H%M%S)_v8_resume}"
OUT_DIR="$REPO_ROOT/runs/overnight/$STAMP"
mkdir -p "$OUT_DIR"
STATUS="$OUT_DIR/status.txt"
echo "$STAMP" > "$REPO_ROOT/runs/overnight/LATEST_V8_RESUME"

echo "overnight_stamp=$STAMP"                     | tee    "$STATUS"
echo "started_utc=$(date -u +%Y-%m-%dT%H:%M:%SZ)" | tee -a "$STATUS"
echo "paper=draft_paper_ieee_v8 — resume 500-task waves" | tee -a "$STATUS"

MODELS=(gpt-4o-mini gemini-2.5-flash deepseek-v3.2)
MIN_COMPLETION=0.90

echo "=== pre-flight: provider reachability ===" | tee -a "$STATUS"
uv run python - "${MODELS[@]}" <<'PY' 2>&1 | tee -a "$STATUS"
# Sends one 3-token request per model through the same client factory the
# batch runner uses, so a provider that is unreachable (or misconfigured)
# fails here in seconds instead of hours into a wave.
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
  # NB: BSD grep (macOS host) has no -P, which silently yielded EX=? on 16 Aug.
  # This sed is portable across the host and the Linux devcontainer.
  local ex; ex=$(sed -n 's/^[[:space:]]*EX:[[:space:]]*\([0-9][0-9.]*\)%.*/\1/p' "$log" | tail -1 || true)
  # `grep -c` prints the count AND exits 1 when it is zero, so `|| echo 0`
  # would append a second "0" and break the status line on clean runs.
  local errs; errs=$(grep -c -- '-> ERROR' "$log" 2>/dev/null || true)
  echo "[$(date -u +%H:%M:%S)] DONE  $name (rc=$rc, EX=${ex:-?}, task-errors=$errs)" \
    | tee -a "$STATUS"
  return 0
}

# wave_done_already <batch_id> -> 0 if all three models present at >=90%
wave_done_already() {
  uv run python - "$1" "$MIN_COMPLETION" <<'PY'
import glob, json, sys
bid, floor = sys.argv[1], float(sys.argv[2])
ok = 0
for p in glob.glob(f"runs/batches/parallel_{bid}_*.json"):
    d = json.load(open(p))
    tot, done = d.get("task_count") or 0, d.get("completed_task_count") or 0
    if tot and done / tot >= floor:
        ok += 1
sys.exit(0 if ok >= 3 else 1)
PY
}

# gate <batch_id> — stop the whole run if the wave is not usable
gate() {
  uv run python - "$1" "$MIN_COMPLETION" <<'PY' 2>&1 | tee -a "$STATUS"
import glob, json, sys
bid, floor = sys.argv[1], float(sys.argv[2])
bad = []
for p in sorted(glob.glob(f"runs/batches/parallel_{bid}_*.json")):
    d = json.load(open(p))
    tot, done = d.get("task_count") or 0, d.get("completed_task_count") or 0
    frac = done / tot if tot else 0
    flag = "" if frac >= floor else "  <-- BELOW FLOOR"
    print(f"  GATE {bid} {d.get('model_key'):17s} {done}/{tot} "
          f"({frac:.0%}) fail={d.get('api_failure_count')}{flag}")
    if frac < floor:
        bad.append(d.get("model_key"))
if bad:
    print(f"  GATE FAILED for {', '.join(bad)} — stopping so the remaining "
          f"waves are not wasted. Fix connectivity and re-run this script; "
          f"completed waves are skipped automatically.")
    sys.exit(3)
print(f"  GATE {bid} PASSED")
PY
}

wave() {  # wave <method> <n> <flags...>
  local method="$1" n="$2"; shift 2
  local batch_id="v8_${method}_500t_r${n}"
  if wave_done_already "$batch_id"; then
    echo "=== SKIP $batch_id (already complete) ===" | tee -a "$STATUS"
    return 0
  fi
  echo "=== WAVE $batch_id ===" | tee -a "$STATUS"
  local pids=() m safe delay
  for m in "${MODELS[@]}"; do
    safe=${m//./-}
    delay=""
    [[ "$m" == "gemini-2.5-flash" ]] && delay="--inter-task-delay 2.5"
    # shellcheck disable=SC2086
    run_one "${batch_id}_${safe}" \
      --model "$m" --limit 500 --replicas "$n" --policy best_of_n \
      "$@" $delay --batch-id "$batch_id" &
    pids+=($!)
  done
  for p in "${pids[@]}"; do wait "$p" || true; done
  gate "$batch_id"
}

PRUNE=(--schema-pruning --schema-pruning-mode hybrid)
COMP=(--semantic-store --prompt-cache --schema-pruning --schema-pruning-mode hybrid)

wave prune 10 "${PRUNE[@]}"
wave p3    10 --semantic-store
wave pc    10 --prompt-cache
wave comp   3 "${COMP[@]}"
wave comp  10 "${COMP[@]}"

echo "finished_utc=$(date -u +%Y-%m-%dT%H:%M:%SZ)" | tee -a "$STATUS"
echo "Next: bash scripts/run_v8_cleanup.sh  (50-task baselines + PC cells, ~90 min)" \
  | tee -a "$STATUS"
