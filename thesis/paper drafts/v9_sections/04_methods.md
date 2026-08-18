# §4 Three prompt-layer methods — 2.3pp

**Status:** not started
**Source to adapt:** the `Mechanism` subsections of v7 §prune (469–488), §p3 (544–559), §pcache
(620–646) — but each roughly triples in length. §4.4 is new.
**This is the point of v8.** Everything else is adaptation; this is the section the extra space was
freed for, and where the "achievement" and "difficulty and ambition" marks live.

---

## Uniform template — use it for all three

Keeping the template identical is what lets a reader compare the three designs. Do not let one
method drift into a different shape.

**(a) which term it attacks · (b) the algorithm · (c) safety rails and failure mode · (d) how it
composes**

Budget: **0.8 / 0.7 / 0.6 / 0.2pp** across 4.1 / 4.2 / 4.3 / 4.4.

## What the extra space should buy: concreteness, not more prose

Three concrete artefacts, one per method. These are cheap to produce because the code paths are
documented below, and they are exactly what the marking criteria reward.

1. **§4.1 — Algorithm 1**, formal pseudocode: score → seed → FK expand → floor → recall patch → two
   rails. Plus a worked example: one BIRD question, its table scores, the selected set, the resulting
   character reduction.
2. **§4.2 — a worked fact digest**: the actual facts extracted from one probe, and the 8-bullet /
   500-character digest a peer replica then receives. Makes "advisory soft coordination" concrete in
   a way prose cannot.
3. **§4.3 — a before/after message-list listing**: the baseline loop's interior re-splice collapsing
   the stable prefix to `[system, task]`, against the append-only delta. The clearest mechanism
   illustration available in the whole project.

---

# 4.1 Recall-aware schema pruning — shrinks **P** (0.8pp)

**Source:** `src/agent/schema_pruning.py` (386 lines), `src/agent/schema_embeddings.py`,
`src/agent/schema.py`. Integration: `src/agent/loop.py:145–200, 415–445`,
`src/agent/loop_cached.py:181–254, 510–546`. Trace: `RunTrace.log_schema_pruning`.

### (a) Term attacked

Every turn re-sends the schema — DDL plus BIRD column descriptions — so schema bytes multiply by
turns × replicas even when the agent touches few tables. Pruning trims this fixed per-turn prefix
**before any replica runs**.

### (b) Algorithm

Entry point: `build_pruned_schema_context(task, db_path, databases_dir, *, expand_fk=True,
min_tables=2, mode, semantic_min_score=0.05) -> SchemaPruningResult`, carrying `selected_tables`,
`schema_context`, `full_chars`, `pruned_chars`, `table_scores`, `pruning_applied`, `fallback_reason`,
and a `reduction_pct` property.

**Scoring — three modes, unified in `combined_table_scores`:**

1. **keyword** (`score_tables_for_task`) — integer scores. Tokenise `question + " " + evidence` with
   `[a-z_][a-z0-9_]*`, then per table: **+5** table name is an exact token; **+3** table name is a
   substring of the text; **+2** per column name that is an exact token; **+1** per column-name
   substring. One hard-coded domain boost: `debit_card_specializing` with any transactional keyword
   gives `transactions_1k` **+4**.
2. **semantic** (`score_tables_semantic_for_task`) — build a per-table profile document via
   `table_profile_text`: table name, name with underscores split, column names, and every
   `column_description` / `data_format` row from
   `<databases_dir>/<db_id>/database_description/<table>.csv`. Then TF-IDF — sublinear tf, smoothed
   idf `log((1+N)/(1+df)) + 1`, L2-normalised — and cosine against the query document. Max-normalised
   to [0,1]. **Hand-rolled; no external embedding model.** Worth one sentence: it keeps the method
   dependency-free and cheap, which matters when it runs per task.
3. **hybrid** — `0.5 · norm(keyword) + 0.5 · norm(semantic)`. **The default and the only mode
   evaluated online in v8.**

**Selection — `select_tables_for_task`:**

- Rank by `(-float_score, name)`.
- Seeds = tables with **integer keyword score > 0**. If none and mode ≠ keyword, fall back to
  `_seed_tables_from_scores`: all tables with float score > 0, else the single top-ranked table if
  its score ≥ `semantic_min_score`.
- Still no seeds → **full schema**, `fallback_reason="no_match_full_schema"`.
- `_expand_fk_neighbors` — BFS over the undirected FK graph from `PRAGMA foreign_key_list`.
- `_apply_min_tables_floor(min_tables=2)` — pad with next-highest scorers; skipped when the schema is
  tiny (`len(tables) <= min_tables + 1`).
- `_apply_domain_recall_rules` — per-database patches: `debit_card_specializing` always adds
  `transactions_1k`, adds `gasstations` when customers/yearmonth/fact are selected, adds `products`
  on a "product" mention; `student_club` adds `attendance` when `event` is selected and `budget` when
  `expense` is selected.
- If the selection covers every table, return the full schema with `pruning_applied=False`.

**What reaches the prompt:** assembled exactly like `build_schema_context` but restricted to
surviving tables — `## SQLite schema (CREATE TABLE)` + `ddl_for_tables(...)`, then optionally
`## Column descriptions` + `descriptions_for_tables(...)`. Becomes `schema_context` inside the single
frozen user message built by `build_initial_messages` → `build_task_user_message`.

### (c) Safety rails and failure mode

**Two rails, asymmetric in cost:**

- **Static fallback** — no table scores above zero → emit the full schema. Free.
- **Runtime fallback** — a `no such table` SQLite error while pruning is active → restore the full
  schema. **Costs a turn.**

**The rail is implemented twice, differently, and this deserves a sentence.** `loop.py:426` rewrites
`messages[1]` in place, which breaks prefix caching. `loop_cached.py:514–546` instead appends the
restored schema into *that turn's tool-result text*, prefixed `"[System: Full database schema
restored after a missing-table SQL error. …]"`, sets `schema_runtime_fallback = True` and
`schema_pruning_active = False` so it fires at most once, and logs
`fallback_reason="runtime_missing_table"`. **The cached loop pays a turn to protect the prefix** —
a concrete instance of the substitutive tension named in §4.4.

**Failure mode.** A recall miss makes the agent explore blind and tokens go **up**. A v1 heuristic
that missed gold tables on 10/50 tasks *increased* tokens by ~35%. Pruning that breaks recall is
worse than no pruning at all. Say this plainly — it is the strongest motivation for the recall-first
framing and it sets up §6.1.

**Honest limits — state them here, do not leave them for §7 alone:** FK expansion is gated to
`debit_card_specializing` (`student_club`'s FK graph is fully connected, so expansion there would
undo the prune entirely), and the recall patches are hand-written per database. That is precisely the
generalisation ceiling §6.1 measures at 89.6%.

### (d) Composition

Substitutive with §4.3: pruning shrinks the very prefix the cache would have discounted.

### Backing test to cite

`tests/test_schema_pruning.py::test_smoke_subset_gold_recall_threshold` asserts minimum recall = 1.0
and mean ≥ 0.98 over the first 50 tasks.

---

# 4.2 Semantic fact store — reshapes **H** (0.7pp)

**Source:** `src/coord/semantic_store.py` (126 lines), `src/coord/semantic_extractors.py` (131
lines), `src/agent/prompt.py`, `src/agent/prompt_cached.py`. Hooks: `loop.py:285–298, 463–469`,
`loop_cached.py:351–365, 554–560`. Trace: `log_semantic_injection`.

### (a) Term attacked

Trades injected bytes in **H** against a reduction in **T**: if a replica reads a peer's distilled
finding, it need not re-probe for it.

### (b) Algorithm

**Scope.** One `SharedSemanticStore` per **task**, shared across that task's N replicas, created in
`run_parallel_agents` when `semantic_store=True`, thread-safe via a single `threading.Lock`. Two
structures:

- `_entries: dict[str, SemanticEntry]` keyed on `fact.lower().strip()` — the dedup identity.
- `_agents_per_key: dict[str, set[str]]` — which replicas independently discovered each fact. This is
  what makes peer-vs-own distinguishable and what enables corroboration ranking.

**Write path — `publish(agent_id, sql, rows, error)`**, after every **explore** `execute_sql`, never
after `submit_sql`.

**Fact extraction — rule-based, zero LLM calls.** Make this a selling point: the coordination layer
adds no inference cost of its own, so every token it costs is prompt bytes and nothing else.
`extract_semantic_facts(sql, rows, error)` emits:

- `"explored: <normalize_sql_ast(sql), truncated to 120 chars>"`
- up to 2 × `"join works: <join_on fragment, 80 chars>"`
- on error: `"<tables> error: <err, 100 chars>"`, and **returns early**
- otherwise `"<tables> returned N row(s)"`
- `_numeric_stats` — up to 3 columns: `"column[i]=v"` for a single value, else
  `"column[i] min=… max=… avg=…"`
- `_distinct_samples` — only when `len(rows) <= 50`, first 4 columns, emits
  `"column[i] samples: a, b, c"` when a column has 2–5 distinct values

**Read path — `peer_facts(agent_id)`** partitions into *peer* (found by ≥1 other replica) and *own*,
**sorts peer facts by number of discovering agents, descending** — corroboration-first, worth
calling out as a design choice — concatenates peer + own, then truncates against a bullet cap and a
character cap while guaranteeing at least one fact:

```
if len(selected) >= max_inject_bullets: break
if total_chars + len(fact) + 2 > max_inject_chars and selected: break
```

Defaults: `max_entries: 128`, `max_inject_chars: 500`, `max_inject_bullets: 8`.

**Two injection disciplines — the pivot into §4.3:**

- `loop.py` — `format_semantic_context` → `apply_semantic_context` **filters out** any prior message
  starting with `SEMANTIC_CONTEXT_PREFIX` and re-appends a fresh full block each turn. Mutates the
  message interior and shifts everything after the schema. **Cache-hostile.**
- `loop_cached.py` — `append_semantic_delta` appends **only facts not yet shown to this replica**
  (per-replica `shown_semantic` set) as one trailing user message. Never edits existing messages.
  **Cache-safe.**

Block format:

```
Shared semantic facts from parallel replicas on this task (reuse these instead of re-probing):
- <fact>
```

### (c) Safety and failure mode

**Advisory by design** — blackboard-style soft coordination (Hayes-Roth 1985). The model may ignore
the digest entirely; nothing forces its use. No expiry or invalidation: the store is task-scoped and
torn down with the task, so a "miss" is an empty peer list or an all-already-shown delta.

**The two competing terms — the analytical core of this subsection.** An **injection tax** is paid on
every turn of every replica and grows with N, because more peers publish more facts. Against it, a
**probe saving** that reduces T. Which term wins is not a design choice; §6.2 shows it is a property
of the model.

**Honest design limit:** the 128-entry cap has **no eviction**. Once full, new keys are silently
dropped, though `_agents_per_key` keeps accruing attribution. Say so — it is a real limitation and
volunteering it costs nothing.

### (d) Composition

Enabling-dependency on §4.3 (the delta injector exists *solely* so the two can compose), and
complementary with §4.1 — the channel §6.4 finds dominant.

### Backing test to cite

`tests/test_semantic_store.py::test_injection_cap` asserts both caps hold.

---

# 4.3 Cache-stable prompt structure — reprices **P + H** (0.6pp)

**Source:** `src/agent/loop_cached.py` (594 lines), `src/agent/prompt_cached.py` (78 lines),
`src/llm/chat_cached.py` (291 lines), `src/logging/trace_cached.py`, `src/llm/cost.py`. Activated in
`src/coord/parallel.py:331–336`, which late-imports the cached loop so the baseline path stays
byte-for-byte unchanged.

### (a) Term attacked

The **price** multiplier. Content is untouched; only ordering, stability and attribution change.

**State plainly: this is provider prefix caching, not a local cache.** Nothing is stored in-process.
Explicit Gemini `cachedContent` is deliberately not used, to avoid extra state.

### (b) Algorithm

**Two provider invariants:** the cached span must be **byte-identical from token 0**, and it can only
**grow by appending**.

**The baseline loop violates both:**

- peer-context injection removes and re-appends a mid-list message every turn, collapsing the stable
  prefix to `[system, task]`;
- the pruning runtime fallback rewrites the schema message in place;
- and no backend recorded provider cached-token counts, so any savings would have been invisible.

**The fix — three zones:**

1. **Frozen static prefix.** `messages[0]` (system) and `messages[1]` (task + schema) built once by
   `build_initial_messages`, never mutated.
2. **Append-only history.** `append_semantic_delta` / `append_discovery_delta` append only
   previously-unseen items as a single trailing user message. The pruning fallback folds the restored
   schema into the trailing tool result rather than splicing the prefix.
3. **Optional single volatile trailer.**

**Cached-token attribution.** `CachedChatResponse` adds `cached_prompt_tokens`, parsed per provider
in `_openai_cached_tokens`: OpenAI's `usage.prompt_tokens_details.cached_tokens`, falling back to
DeepSeek's `usage.prompt_cache_hit_tokens`; Gemini's `usage_metadata.cached_content_token_count`.
Accumulated per turn into the trace.

**Cost model.** `estimate_cost_usd` computes `uncached = max(prompt - cached, 0)` and bills
`uncached × input_rate + cached × cached_rate + completion × output_rate`.

### (c) Safety and failure mode

**Accuracy-neutral by construction** — not one content byte changes.

**The guarantee is an executable test.** `tests/test_prompt_cached.py::
test_zone1_prefix_is_byte_stable_across_injections` simulates five turns of injections plus
assistant/tool appends and asserts `messages[:2] == frozen`; its docstring explicitly names "the
interior-mutation bug that the original `apply_*_context` helpers had". **Cite this test.**
Construction-level safety with a machine-checked invariant is a claim most papers cannot make, and it
is directly what the "achievement" criterion rewards.

**Failure mode** is degradation, not error: if an invariant is broken the cache silently stops
firing and cost returns to baseline. Nothing becomes incorrect. Contrast with §4.1 and §4.2, whose
failure modes change what the model sees.

### (d) Composition

Substitutive with §4.1, enabled by §4.2's delta injector.

**Honesty flag — put it here, not only in §7.** The cached discount is the provider's choice, not
the method's: cached input costs **50% of standard on GPT-4o mini, 10% on Gemini 2.5 Flash, 2% on
DeepSeek** (`configs/models.yaml`, checked 2026-08-16). DeepSeek's dominant billed savings are
therefore largely a **price-schedule fact, not a mechanism fact**. Saying so here inoculates §6.3
against the obvious objection.

---

# 4.4 How the three interact (0.2pp) — NEW

Name three channels and present them as **competing predictions**, not as a conclusion:

1. **Substitutive** (pruning ↔ cache) — pruning removes bytes the cache would otherwise have
   discounted, so their savings partly cancel. Predicts the stack **underperforms** its parts.
2. **Enabling** (fact store → cache) — the delta injector exists solely so soft coordination can ride
   a stable prefix. Predicts composition is at least feasible where it otherwise would not be.
3. **Complementary** (pruning ↔ fact store) — with a pruned prefix, distilled facts may substitute
   for schema the pruner removed, so facts stop being pure overhead. Predicts the stack
   **overperforms** its parts.

Hand off to §6.4, which finds the complementary channel dominant on 11 of 15 configurations.

**Do not pre-commit to sub-additivity here.** That was the intuitive prediction during planning and
the data contradicts it. Framing this as an open empirical question and then resolving it in §6.4 is
much stronger than asserting an answer and hedging later.

---

## DRAFT

**Status: drafted 2026-08-16. Not yet compiled — no LaTeX toolchain on this machine.**

**Preamble additions required** (v7's preamble has neither; both are standard and present on
Overleaf):

```latex
\usepackage{algorithm}
\usepackage{algpseudocode}
```

If either is unavailable, Algorithm 1 degrades cleanly to a `figure` containing a `\small\ttfamily`
block — the content is line-oriented and needs no algorithmic-specific markup.

**Provenance of the two worked examples.** Both are real, not illustrative. The pruning example is
`build_pruned_schema_context` run on BIRD mini-dev question 1317 in hybrid mode; the scores and
character counts are its actual output. The fact digest is produced by replaying the 24 recorded
explore probes from question 1350's ten replicas through the real `extract_semantic_facts` and
`SharedSemanticStore`, re-executing each probe against the live database so the row counts are true
rather than reconstructed from the truncated `result_sample` field in the trace. Regenerate either
with the snippets in `v8_sections/_worked_examples.md`.

---

```latex
\section{Three ways to make the prompt cheaper}\label{sec:methods}

The cost identity of §\ref{sec:costmodel} exposes three distinct surfaces, and
the three methods evaluated here attack one each: schema pruning shrinks the
static prefix $P$, the semantic fact store reshapes the accumulated history $H$
against the turn count $T$, and cache-stable prompt structure changes the price
at which both are billed. Each is described below in the same four parts, covering what it changes,
the algorithm, its safety rails and failure mode, and how it composes. The
uniformity is deliberate, letting the designs be compared and not only their
results.

\subsection{Schema pruning: send a smaller schema}\label{sec:prune}

\textbf{What it changes.} Every turn re-sends the database schema, meaning the
DDL plus BIRD's column descriptions. Because that text sits in the static prefix, its
cost is multiplied by turns and again by replicas, even when the agent touches
two tables out of eight. Pruning trims the prefix once, before any replica
starts, so the saving applies to every subsequent billing event.

\textbf{Scoring.} Tables are scored against the question and evidence in one of
three modes, unified by \texttt{combined\_table\_scores}. The \emph{keyword}
mode tokenises the question and evidence and awards each table $+5$ where its
name appears as an exact token, $+3$ as a substring, $+2$ per column name
matching an exact token and $+1$ per column-name substring. The \emph{semantic}
mode builds a profile document per table, holding its name, the name split on
underscores, its column names, and every column description shipped with the
database. It then scores TF--IDF cosine similarity against the question, using
sublinear term frequency, smoothed inverse document frequency and $L_2$
normalisation. The implementation is self-contained, and no external embedding model
is involved, which keeps the step cheap enough to run per task. The
\emph{hybrid} mode, the default and the only one evaluated online here, averages
the two after max-normalising each.

\textbf{Selection.} Algorithm~\ref{alg:prune} gives the procedure, in which
seeds are drawn from tables carrying a non-zero \emph{keyword} score while the
continuous hybrid score orders candidates without by itself admitting them.
Those seeds are then expanded across the foreign-key graph, padded to a floor of
two tables, and finally passed through a set of per-database recall rules.

\begin{algorithm}[t]
\caption{Recall-aware hybrid schema pruning}\label{alg:prune}
\begin{algorithmic}[1]
\Require question $q$, evidence $e$, database $d$ with tables $\mathcal{T}$
\Ensure schema context over a subset of $\mathcal{T}$
\State $k \gets \textsc{KeywordScores}(q \Vert e, \mathcal{T})$
\State $s \gets \textsc{TfIdfCosine}(q \Vert e, \textsc{Profiles}(\mathcal{T}))$
\State $h \gets \tfrac{1}{2}\,\overline{k} + \tfrac{1}{2}\,\overline{s}$
  \Comment{max-normalised}
\State $S \gets \{t \in \mathcal{T} : k[t] > 0\}$
\If{$S = \emptyset$}
  \State $S \gets \{t : s[t] > 0\}$ \textbf{or} $\arg\max_t h[t]$ if
    $h[t] \geq \tau$
\EndIf
\If{$S = \emptyset$}
  \State \Return full schema
    \Comment{static fallback}
\EndIf
\State $S \gets S \cup \textsc{FkNeighbours}(S)$
\State $S \gets S \cup \textsc{TopUp}(h, S)$ \textbf{while} $|S| < 2$
\State $S \gets S \cup \textsc{RecallRules}(d, S)$
\If{$S = \mathcal{T}$} \State \Return full schema \EndIf
\State \Return DDL and column descriptions restricted to $S$
\end{algorithmic}
\end{algorithm}

\textbf{A worked example.} Question 1317 asks, of the \texttt{student\_club}
database, ``Among the students from the Student\_Club who attended the event
`Women's Soccer', how many of them want a T-shirt that's in medium size?''. The
gold query joins \texttt{event}, \texttt{attendance} and \texttt{member}. Only
two of the eight tables score on keywords, and the gold table
\texttt{attendance} scores exactly zero. The question names an event and a
garment, never the join table connecting them. It ranks third on the hybrid score, which is
not sufficient for admission, and enters the selection solely through the recall
rule that adds \texttt{attendance} whenever \texttt{event} is selected. The
result keeps three tables of eight and cuts the schema from 6{,}513 to 2{,}479
characters, a 61.9\% reduction, with gold-table coverage intact. The full score
table is Table~\ref{tab:appendix-prune-example}.

\textbf{Safety rails.} Two rails protect recall, and they differ in what they
cost. The \emph{static} fallback emits the full schema when nothing scores above
zero, and is free. The \emph{runtime} fallback restores the full schema after a
\texttt{no such table} execution error, and costs a turn. The runtime rail is
implemented twice, for one reason. The baseline loop rewrites the schema
message in place, whereas the cache-aware loop of §\ref{sec:pcache} folds the
restored schema into that turn's tool result instead, because rewriting the
prefix would invalidate the provider cache. The cached loop pays a turn to
protect the prefix. That is the first concrete instance of the tension
analysed in §\ref{sec:interact}.

\textbf{Failure mode.} A recall miss does more than forgo a saving, because it
sets the agent exploring blind and tokens rise. This was first seen during
development, when an earlier heuristic that missed gold tables on 10 of 50 tasks
increased token consumption by roughly 35\%, and §\ref{sec:results-prune} measures
the same effect at full scale and finds it larger still. Pruning that breaks
recall is worse than no pruning at all, which is why recall is treated below as
a precondition rather than a diagnostic.

\textbf{Known limits.} Foreign-key expansion is enabled for one database
only. In \texttt{student\_club} the key graph is fully connected, so expanding
across it would re-admit the whole schema and undo the prune. The recall rules
are likewise hand-written per database. Both are the reason the method's
generalisation is bounded, and §\ref{sec:results-prune} measures where that
bound falls.

\subsection{The fact store: share what replicas learn}\label{sec:p3}

\textbf{What it changes.} Where pruning shrinks what is sent once, the fact store
changes what accumulates. It trades additional bytes in $H$ for a reduction in
$T$: if a replica can read a peer's finding, it need not spend a turn
rediscovering it.

\textbf{Structure.} One store exists per task and is shared by that task's $N$
replicas under a single lock. It holds two maps. The first keys distilled facts on their
normalised text, and, for each fact, the set of replicas that discovered it
independently. The second map is what makes peer knowledge distinguishable from
a replica's own, and it is also what allows corroborated facts to be ranked
first.

\textbf{Write path.} After every exploratory query, and never after a
submission, the outcome is distilled by rules that make no model calls at all, so the
coordination layer adds no inference cost of its own and every token it costs is
prompt text. Queries are canonicalised by parsing them to an
abstract syntax tree with \texttt{sqlglot} (Mao 2024), so that two spellings of
one probe collapse to a single fact. The rules emit a normalised form of the
query itself,
up to two working join predicates, a row count, simple statistics over at most
three numeric columns, and, for small results, the distinct values of up to four
low-cardinality columns. An execution error short-circuits the rest and is
published as a fact in its own right.

\textbf{Read path.} Before each turn a replica requests the facts it did not
itself discover. These are ordered by the number of replicas that found them
independently, so corroborated findings surface first, and are then truncated to
at most eight bullets and 500 characters, with a guarantee of at least one fact.

\textbf{A worked example.} Question 1350 of \texttt{student\_club} asks ``What
is the status of the event which bought `Post Cards, Posters' on 2019/8/20?''.
Across ten replicas, 24 exploratory probes distil to 14 distinct facts, of which
one replica's digest receives seven. Both caps bind. That digest is reproduced
verbatim as Fig.~\ref{fig:appendix-digest}, and what the peers mostly report is
worth noting: joins that work, and probes that returned nothing. Negative
results are the store's most common payload, and they are genuinely useful,
since a peer that has established a join is empty saves another replica the same
query. They are also why the digest can grow without shortening any
trajectory.

\textbf{Two ways to add the digest.} How the digest reaches the prompt matters
more than it first appears. The baseline loop removes any previous digest from
the middle of the message list and appends a fresh one each turn. The
cache-aware loop instead appends only the facts a given replica has not yet
seen, tracked per replica, as a single trailing message, and never edits an
existing one. The second exists solely so that this method and the next can
coexist. Section~\ref{sec:pcache} explains why the first would make the third method
inert.

\textbf{Failure mode.} The digest is advisory, presented as context that the
model remains free to ignore. What the design cannot control is the balance of
two opposing terms. The injection is paid on every turn of every replica and
grows with $N$, because more replicas publish more facts. The saving depends on
whether reading a fact actually removes a probe. Nothing in the mechanism
determines which term wins, and §\ref{sec:results-p3} finds the answer is a
property of the model rather than of the configuration.

\textbf{A known limit.} The store caps at 128 entries with no eviction,
so once it is full new facts are silently dropped, and although the cap is
rarely reached on the tasks studied here it remains a real ceiling on longer
trajectories.

\subsection{Cache-stable structure: pay less for the same bytes}\label{sec:pcache}

\textbf{What it changes.} Neither preceding method touches the rate at which
tokens are billed. Providers discount input that repeats a previously seen
prefix, which makes the price of $P + H$, rather than their size, a third and
independent lever. Nothing here is stored locally. The mechanism is entirely a
matter of presenting the prompt so that the provider's own cache can fire.

\textbf{Two invariants.} Provider prefix caches share two requirements. The
cached span must be byte-identical from the first token, and it may only grow by
appending. The baseline loop violates both. Peer-context injection removes and
re-appends a message in the middle of the list every turn, which shifts
everything after the schema and collapses the stable prefix to the system
message and the task, and the pruning runtime fallback rewrites the schema message
in place. A third problem is subtler still: no backend recorded the provider's
cached-token counts, so even a cache that did fire would have been invisible in
the results.

\textbf{Three zones.} The cache-aware loop partitions the prompt instead, and
Fig.~\ref{fig:zones} contrasts the two message lists. Zone~1 holds the system
message and the task message carrying the schema, question and evidence, and it
is built once and never mutated. Zone~2 is append-only, so peer context arrives as
deltas, and the pruning fallback folds a restored schema into the trailing tool
result rather than splicing the prefix. An optional Zone~3 carries a single
volatile trailer. Cached-token counts are read from each provider's usage
metadata and recorded per turn, which is what makes the billing ledger of
§\ref{sec:results-pcache} measurable at all.

\begin{figure}[t]
\footnotesize\ttfamily\raggedright
\textbf{\rmfamily Baseline loop, turn $n$:}\\
{[}0{]} system\\
{[}1{]} task + schema \quad\textrm{\itshape (rewritten by fallback)}\\
{[}2{]} \ldots history \ldots\\
{[}k{]} peer context \quad\textrm{\itshape (removed, re-appended: shifts $k{+}1$ on)}\\[4pt]
\textbf{\rmfamily Cache-aware loop, turn $n$:}\\
{[}0{]} system \quad\textrm{\itshape (frozen)}\\
{[}1{]} task + schema \quad\textrm{\itshape (frozen)}\\
{[}2{]} \ldots history, append-only \ldots\\
{[}n{]} new peer facts only \quad\textrm{\itshape (appended)}
\normalfont\rmfamily
\caption{Why the baseline loop cannot cache. Re-appending peer context mutates
the interior of the message list, so no prefix beyond the first two messages is
byte-stable across turns.}
\label{fig:zones}
\end{figure}

\textbf{Safety.} This method is accuracy-neutral by construction. Not one
content byte differs between the two loops, only the order and stability of the
messages carrying it. That claim is enforced, not merely asserted: a unit test
simulates five turns of injections and tool results, then checks that the first
two messages remain byte-identical throughout. Its failure mode is also
benign. If an invariant is broken the cache silently stops firing and cost
returns to baseline. Nothing becomes incorrect. This distinguishes it from the
two preceding methods, whose failure modes change what the model sees.

\textbf{Why the saving is this large.} The size of the billing saving is set as much by
the provider's price list as by the mechanism. Cached input costs 50\% of the
standard input rate on GPT-4o mini, 10\% on Gemini 2.5 Flash and 2\% on
DeepSeek, so the identical mechanism is worth twenty-five times more on one
provider than another. Section~\ref{sec:results-pcache} reports all three, and
the spread between them should be read as a pricing fact rather than a property
of the method.

\subsection{How the three methods interact}\label{sec:interact}

Composed, the three methods interact through three channels, and they do not
point the same way.

The channel most easily anticipated is \emph{substitutive}: pruning removes
schema bytes that the cache would otherwise have served at a discount, so the
two savings overlap and the stack should recover less than the sum of its parts.
The second is \emph{enabling}: the delta-based injector of §\ref{sec:p3} exists
only so that shared knowledge can be added without breaking the prefix, so
without it the combination would not merely underperform but would disable the
third method outright. The third is \emph{complementary}: against a pruned
prefix, distilled facts may substitute for schema the pruner discarded, in which
case the digest stops being pure overhead and begins to carry information the
model would otherwise have gone looking for.

The first channel predicts a stack that underperforms its components, the third
one that exceeds them. Which dominates is an empirical question, and
§\ref{sec:results-compose} measures it.
```
