#!/usr/bin/env bash
# v8 prune fill — the two schema-pruning cells missing from the 50-task matrix.
#
# run_v8_matrix.sh skipped prune 50t N=10/25 on the grounds that they were
# "already on disk". They are, but only as `schema_prune_iso_r{10,25}_bo` from
# 27 Jun — and June batches are not reused in v8, for the same reason GAP 1 of
# run_v8_cleanup.sh re-runs the P0 baselines rather than citing the old ones:
# the legacy 50-task batches do not form one consistent task set. There are
# five competing GPT N=25 baselines alone, one of which (20260611_123556_a3baef)
# carries only 36 usable rows out of 50. Rather than adjudicate which legacy
# batch is the right control, every v8 cell is re-run under a clean `v8_*` id.
#
# DeepSeek has an additional, independent problem: its June runs predate the
# 2026-07-24 `deepseek-chat` swap to deepseek-v4-flash, so they are a different
# model from every other v8 cell — worth ~6 EX points on its own.
#
# Flags are byte-identical to the v8_prune_50t_r3 cell already on disk:
# schema pruning only, hybrid mode, nothing else enabled.
#
# ~40 min, ~$5. MODELS=<space-separated keys> restricts the re-run, but the
# default of all three is what keeps the matrix internally consistent.
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$REPO_ROOT"

# --- guard: never run alongside another v8 batch driver ----------------------
# Two drivers at once doubles the per-provider request rate, and Gemini is the
# failure-prone one; this is the concurrency warning in run_v8_cleanup.sh made
# enforceable rather than advisory.
for other in run_v8_matrix.sh run_v8_cleanup.sh run_v8_resume.sh; do
  if pgrep -f "$other" >/dev/null 2>&1; then
    echo "REFUSING TO START: $other is still running." >&2
    echo "Wait for it to finish, then re-run this script." >&2
    exit 1
  fi
done

STAMP="${OVERNIGHT_STAMP:-$(date -u +%Y%m%d_%H%M%S)_v8_prune_fill}"
OUT_DIR="$REPO_ROOT/runs/overnight/$STAMP"
mkdir -p "$OUT_DIR"
STATUS="$OUT_DIR/status.txt"
echo "$STAMP" > "$REPO_ROOT/runs/overnight/LATEST_V8_PRUNE_FILL"

echo "overnight_stamp=$STAMP"                     | tee    "$STATUS"
echo "started_utc=$(date -u +%Y-%m-%dT%H:%M:%SZ)" | tee -a "$STATUS"
echo "paper=draft_paper_ieee_v8 — schema-pruning 50t N=10/25 fill" | tee -a "$STATUS"

IFS=' ' read -r -a MODELS <<< "${MODELS:-gpt-4o-mini gemini-2.5-flash deepseek-v3.2}"
MIN_COMPLETION=0.90

echo "models=${MODELS[*]}" | tee -a "$STATUS"

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

# wave_done_already <batch_id> -> 0 if every requested model is present at >=90%
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

# gate <batch_id> — stop if the wave is not usable, rather than press on
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
    print(f"  GATE FAILED for {', '.join(bad)} — stopping. Fix connectivity and "
          f"re-run; completed waves are skipped automatically.")
    sys.exit(3)
print(f"  GATE {bid} PASSED")
PY
}

# Identical to run_v8_matrix.sh's prune arm: schema pruning only, hybrid mode.
PRUNE=(--schema-pruning --schema-pruning-mode hybrid)

for n in 10 25; do
  batch_id="v8_prune_50t_r${n}"
  if wave_done_already "$batch_id"; then
    echo "=== SKIP $batch_id (already complete) ===" | tee -a "$STATUS"
    continue
  fi
  echo "=== WAVE $batch_id ===" | tee -a "$STATUS"
  pids=()
  for m in "${MODELS[@]}"; do
    safe=${m//./-}
    delay=""
    [[ "$m" == "gemini-2.5-flash" ]] && delay="--inter-task-delay 2.5"
    # shellcheck disable=SC2086
    run_one "${batch_id}_${safe}" \
      --model "$m" --limit 50 --replicas "$n" --policy best_of_n \
      "${PRUNE[@]}" $delay --batch-id "$batch_id" &
    pids+=($!)
  done
  for p in "${pids[@]}"; do wait "$p" || true; done
  gate "$batch_id"
done

echo "=== completeness ===" | tee -a "$STATUS"
uv run python - <<'PY' 2>&1 | tee -a "$STATUS"
import json, glob
for p in sorted(glob.glob('runs/batches/parallel_v8_prune_50t_*.json')):
    d = json.load(open(p))
    print(f"  {d.get('batch_id'):20s} {d.get('model_key'):17s} r{d.get('n_replicas'):<3} "
          f"tasks={d.get('completed_task_count')}/{d.get('task_count')} "
          f"fail={d.get('api_failure_count')} EX={d.get('ex_accuracy_pct')}")
PY

echo "finished_utc=$(date -u +%Y-%m-%dT%H:%M:%SZ)" | tee -a "$STATUS"
