# Regenerating §4's worked examples

Both examples in `04_methods.md` are real output, not illustrations. If the pruning heuristics or the
extractor change, re-run these and update the section — do not hand-edit the numbers.

---

## §4.1 — pruning on question 1317 (Table `tab:prune-example`)

```bash
uv run python - <<'PY'
import sys; sys.path.insert(0, '.')
from src.bird.tasks import load_tasks, sqlite_path_for_task
from src.agent.schema_pruning import (
    build_pruned_schema_context, combined_table_scores, score_tables_for_task)
from src.config import load_config

cfg = load_config()
t = next(x for x in load_tasks(cfg) if x.question_id == 1317)
db = sqlite_path_for_task(t, cfg)

print('Q:', t.question)
print('gold SQL:', ' '.join(t.gold_sql.split())[:200])

kw = score_tables_for_task(t, db)
hybrid, keyword, semantic = combined_table_scores(t, db, cfg.databases_dir, mode='hybrid')
for tbl in sorted(hybrid, key=lambda x: -hybrid[x]):
    print(f'  {tbl:12s} keyword={keyword[tbl]:>2}  hybrid={hybrid[tbl]:.3f}')

r = build_pruned_schema_context(t, db, cfg.databases_dir, mode='hybrid')
print('selected :', sorted(r.selected_tables))
print(f'chars    : {r.full_chars} -> {r.pruned_chars}  ({r.reduction_pct:.1f}% reduction)')
print('fallback :', r.fallback_reason, '| applied:', r.pruning_applied)
PY
```

Expected as of 2026-08-16:

```
event 8 / 0.780 · member 3 / 0.688 · attendance 0 / 0.329 · budget 0 / 0.216
major 0 / 0.164 · expense 0 / 0.153 · income 0 / 0.123 · zip_code 0 / 0.089
selected: ['attendance', 'event', 'member']
chars: 6513 -> 2479  (61.9% reduction)
```

**Why this task was chosen.** Its gold query joins `event`, `attendance` and `member`, and
`attendance` scores **zero** on keywords — seeds come only from non-zero keyword scores, so it is
admitted purely by the `event → attendance` recall rule. It is the cleanest available demonstration
that the hand-written rules are load-bearing rather than cosmetic, which is exactly the point §6.1
then quantifies at 89.6% full-scale recall.

---

## §4.2 — the peer digest on question 1350 (Fig. `fig:digest`)

Replays the recorded probes through the real extractor and store. Probes are **re-executed against
the live database** because the trace's `result_sample` field is truncated, which would understate
row counts.

```bash
uv run python - <<'PY'
import sys, json, sqlite3; sys.path.insert(0, '.')
from pathlib import Path
from src.coord.semantic_store import SharedSemanticStore
from src.agent.prompt import format_semantic_context
from src.bird.tasks import load_tasks, sqlite_path_for_task
from src.config import load_config

cfg = load_config()
batch = sorted(Path('runs/batches').glob('parallel_v8_p3_50t_r10_gpt-4o-mini_*.json'))[0]
b = json.load(open(batch))
row = sorted((x for x in b['rows'] if x.get('semantic_injections')),
             key=lambda x: -x['semantic_injections'])[2]

t = next(x for x in load_tasks(cfg) if x.question_id == row['question_id'])
db = sqlite_path_for_task(t, cfg)
print(f"Q{t.question_id} ({t.db_id}): {t.question}")

# Trace paths in the batch JSON are absolute from the machine that ran it.
coord = Path('runs') / Path(row['coord_trace_path']).name
evs = [json.loads(l) for l in coord.read_text().splitlines()]
replicas = sorted((e['agent_id'], Path('runs') / Path(e['trace_path']).name)
                  for e in evs if e.get('event') == 'replica_end' and e.get('trace_path'))

probes = []
for aid, p in replicas:
    if not p.exists():
        continue
    for line in p.read_text().splitlines():
        ev = json.loads(line)
        if ev.get('event') == 'sql_execute' and ev.get('sql_role') == 'explore':
            probes.append((ev.get('seq', 0), aid, ev.get('sql_raw'), ev.get('error')))
probes.sort()

store, con = SharedSemanticStore(), sqlite3.connect(db)
for seq, aid, sql, err in probes[:24]:
    rows, e = [], err
    if sql and not err:
        try:
            rows = con.execute(sql).fetchall()
        except Exception as ex:
            e = str(ex)
    store.publish(agent_id=aid, sql=sql or '', rows=rows, error=e)

facts = store.peer_facts('agent_3')
block = format_semantic_context(facts)
print(f'{len(probes[:24])} probes -> {len(store._entries)} distinct facts')
print(f'digest: {len(facts)} bullets, {len(block)} chars total')
print(block)
PY
```

Expected as of 2026-08-16: 24 probes → 14 distinct facts; digest of 7 bullets (500 characters of fact
text, 555 including the header line — both the 8-bullet and 500-character caps bind).

**Two things the figure is doing.** It shows the caps actually binding rather than being nominal
limits, and it shows what the peers mostly report: working joins and empty results. Negative results
being the commonest payload is honest and it sets up §6.2 — a digest that grows without shortening
any trajectory is precisely the injection tax.

**The `agent_3` choice is arbitrary** but not cherry-picked: any replica's digest has the same shape,
since the peer/own split only excludes that replica's own discoveries.
