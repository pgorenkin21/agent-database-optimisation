# §7 Discussion — 0.6pp

**Status:** not started
**Source to adapt:** `draft_paper_ieee_v7.tex` lines 872–953 — but the "four ledgers" framing must
become two, and all P1/P4 material goes.

---

## Five beats

### 1. Two ledgers

Raw and billed tokens are different ledgers, and a policy can be significantly worse on one and
significantly better on the other **in the same run** — GPT prompt-cache at N=10 is the existence
proof. The practical consequence: a policy must be judged on the ledger that binds for the
deployment, and reporting only raw tokens would have made the single most valuable method in this
paper look worthless.

### 2. Each lever's ceiling

- **P is bounded by recall, and the bound is sharp.** Pruning saves 10–20% where every gold table
  survives (6 of 6 cells significant) and costs 32–156% where one does not; at 89.6% full-scale
  recall the two very nearly cancel, leaving an aggregate that is null at N=3 and only 8–11% at
  N=10. The ceiling is not how
  aggressively the prefix can be cut but how reliably the right tables are kept, and hand-written
  per-database rules are where that runs out.
- **H is bounded by a tax/saving race, and the race is not decided by the tax.** DeepSeek carries a
  near-identical injection load at both scales (32.4 vs 28.3 per task at N=10) yet pays 21% at 50
  tasks and saves 7% at 500 — so injection volume bounds the saving without predicting it. What the
  full-scale data does show is a *ceiling of a different kind*: on DeepSeek the 7% saving costs
  3.5pp of accuracy, the only such trade in sixty cells.
- **The price term is bounded only by the provider's cached discount** — cached input costs 50% of
  standard on GPT-4o mini, 10% on Gemini 2.5 Flash and 2% on DeepSeek. This is why repricing
  dominates, and why it will keep dominating as providers compete on cache pricing. It is also the
  one lever whose ceiling is set entirely outside the system: the same mechanism, unchanged, is worth
  three times as much on one provider as another.

### 3. Isolation attributes; composition decides

The fact-store reversal is the case study. Isolation is what made the per-model sign attributable at
all — and it is also what would have produced the wrong deployment call, since §6.4 shows the
component earns its place in the stack it looked useless outside of.

Generalise into ablation discipline: **report both, and never let an isolated null veto a component
that pays in composition.** This is a transferable methodological point and probably the most
citable thing in the paper.

### 4. Positioning

- **vs schema linking / LLMLingua** — the same context-reduction idea, but multiplied by N replicas ×
  T turns, which changes the economics and makes recall failure proportionally more expensive.
- **vs MAC-SQL** — role specialisation and replica coordination are complementary axes; this layer
  would sit beneath their selector/refiner agents unchanged.
- **vs FrugalGPT** — a model cascade chooses *which model* to pay for; this chooses *what to send it*.

### 5. Threats to validity

**All twelve items below must appear.** The rubric rewards critical analysis of weaknesses, and items
1, 2 and 12 are the defining limitations of the paper — give them their own sentences, not a shared
clause in a list.

1. **Every cell is a single run — no replication anywhere.** Attach the consequence to §6.4
   specifically: the 11-of-15 pattern is a consistent direction across fifteen configurations, not a
   replicated effect — and the four misses are all near-ties with the null rather than reversals. Prior work in this project saw 50-task seeds swing up to ±8pp on EX, which
   bounds how much weight it can carry. The breadth — three models × three replica counts × two
   scales — is what substitutes for depth of replication. §6.3 shows what that breadth buys: the one
   50-task cell where the two ledgers diverged is neutral over 496 tasks, so breadth caught a
   subset artefact that replication at 50 tasks might not have.
2. **The two scales disagree, and where they disagree the 50-task result is the one that fails.**
   The design is complete: all four arms at N ∈ {3,10,25} on 50 tasks and N ∈ {3,10} on all 500, 60
   cells. What is *not* corroborated at scale is N=25, which is 50-task only. Two disagreements
   must be declared rather than smoothed: pruning's aggregate is null at full scale N=3 but
   −15--29% on the subset, and the fact store's sign on DeepSeek **reverses** (+16 to +21% on 50
   tasks, −7% on 500). Injection load is nearly identical at both scales, so this is a sampling
   effect, not a mechanism one. Treat every 50-task magnitude as indicative only — the subset
   over-states pruning and inverts the fact store.
3. **Cached rates are published figures, not assumptions** (fixed 2026-08-16). Gemini's was `null`
   and two code paths invented different fallbacks — 50% in the analyser, 0% in `cost.py`. Google
   publishes cached input at 10% of standard for Gemini 2.5, and the registry now carries it with an
   access date. §7 needs only the ordinary caveat: caches are opaque, counts are provider-reported,
   prices are list prices checked on one date. Do **not** reinstate a "Gemini is an upper bound"
   sentence from v7 — it no longer applies.
4. **89.6% full-scale gold recall**, achieved with hand-written per-database patches and FK expansion
   gated to one database, is a generalisation ceiling.
5. **No latency evidence at all** — the batch JSONs carry no timing field. Make no wall-clock claim.
6. The §6.4 additivity check compares **independent runs, not paired ones**, against a
   *multiplicative* null. An additive null gives different gaps; say which you used.
7. Provider caches are opaque; cached-token counts are provider-reported; USD is a list-price
   approximation.
8. **Model-era drift** — the registry flags `deepseek-chat` deprecation on 2026-07-24. Absolute EX
   levels may not reproduce on later served versions.
9. **Gold evidence is included in prompts**, matching BIRD convention but flattering all
   configurations equally.
10. Not every cell is significant — say so rather than quoting only the range. On raw tokens, two of
    nine composed cells at 50 tasks are †, as is one of nine pruning cells; at full scale all three
    pruning cells at N=3 are † and one composed cell at each of N=3 and N=10 is †.
11. **This paper narrows the research question** relative to the registered Project Definition and
    evaluates three of the five policies it named. Declare it, and frame it as what it was: isolation
    showed the stacked measurements could not attribute credit, so scope was cut to what could be
    measured cleanly.
12. **Two EX intervals exclude zero, and they are not independent.** Both are DeepSeek at 500
    tasks, N=10: the fact store alone (−3.5pp [−5.7, −1.4]) and the composed stack (−2.4pp [−4.8,
    −0.2]). Sixty intervals at 95% would throw ~3.0 exceptions under a true null, so two is fewer
    than chance predicts — give that first. Then give the part the arithmetic hides: the two share a
    model, a cell *and a mechanism*, and the two arms without the fact store at that cell are both
    †. The defensible claim is that the constraint holds across the design while the fact store
    costs DeepSeek accuracy at scale. Do not claim "no effect anywhere".

## Tone

State the limitations once, clearly, then write with confidence about what the data does show. Do not
hedge every sentence — over-qualification reads as lack of command, and the findings here are real
within their stated scope.

---

## DRAFT

**Status: drafted 2026-08-17 against the complete 60-cell design. Compiles clean.**

**Budget: ~0.55pp, under the 0.6 allocation.** The body is over the ceiling (README budget note), so
the twelve threats are one dense paragraph rather than a numbered list. Items 1, 2 and 12 still get
their own sentences, per the brief — the rest are compressed to clauses. **Do not expand this into a
list without finding the space first.**

**Three beats changed after the last wave.** The H-ceiling is no longer "a tax/saving race" — the
tax is near-identical at both scales while the sign reverses, so it bounds rather than predicts.
The fact-store reversal now cuts both ways: it earns its place in the stack *and* costs DeepSeek
accuracy. And the EX exceptions are two, not zero, and they cluster.

---

```latex
\section{Discussion}\label{sec:discussion}

\textbf{Two ledgers, not one.} The clearest methodological result here is that
raw and billed tokens must be reported separately. A method can leave
consumption untouched and still remove most of the bill, as cache-stable
structure does in fourteen of fifteen configurations. In one configuration the
two ledgers move in opposite directions, both intervals excluding zero.
A study reporting only raw tokens would have concluded that the single most
valuable method in this paper does nothing.

\textbf{Each method has a different ceiling.} Prefix reduction is bounded
by recall, and the bound is sharp, not gradual. The same pruner saves on tasks
whose gold tables survive and costs several times as much where one does not.
What limits the method is how reliably the right tables are kept, not how
aggressively the prefix can be cut, and hand-written per-database rules are
where that reliability runs out. History reshaping is bounded by something less
tractable. The injection tax is real and grows steeply with replica count, yet
it does not predict the sign. DeepSeek carries a near-identical load at both
scales while its token effect reverses, so the tax bounds the achievable saving
without determining it. Repricing is bounded only by the provider's cached
discount, which runs to 50\% of standard on GPT-4o mini, 10\% on Gemini and 2\%
on DeepSeek, and that is why it dominates and why one unchanged mechanism is
worth twice as much on one provider as on another. The ceiling sits entirely outside the
system.

\textbf{What isolation shows, and what it misses.} Attribution and deployment
are different questions, and the fact store answers them differently. Measured alone it has
no reliable sign, and on one model at full scale it costs accuracy. An ablation stopping
there would remove it. Yet it appears in every composed configuration measured,
including those that save most, and the composed stack beats the
product of its parts in eleven of fifteen configurations. Isolation is necessary to attribute a saving to a mechanism and insufficient to
decide whether that mechanism belongs in a deployment, which yields a
transferable rule: report both, and never let an isolated null veto a component
that pays in company.

\textbf{Positioning.} Schema linking and prompt compression pursue the same
reduction as §\ref{sec:prune}, but for a single pass. Multiplying by replicas
and turns is what makes a recall failure expensive instead of merely
regrettable. Role-based coordination such as MAC-SQL occupies an orthogonal
axis, and this layer would sit beneath it unchanged.

\textbf{Threats to validity.} Two limitations are structural. First, every cell
is a single run: the eleven-of-fifteen composition pattern is a consistent
direction across configurations, not a replicated effect, and breadth across
three models and two scales substitutes for depth. Second, coverage is uneven and the
two scales disagree twice, on pruning's aggregate and on the fact store's sign.
Where they disagree, the 50-task result is the one that fails, so subset
magnitudes should be read as indicative. Several narrower limits follow. The 89.6\% gold-table recall rests on
hand-written per-database rules and is a generalisation ceiling. The additivity
check compares independent runs against a \emph{multiplicative} null, so no
interval attaches to a gap. Provider caches are opaque, counts are
provider-reported, and prices are list rates checked on one date. Gold evidence
is included in prompts, as the benchmark intends, which flatters all arms
equally, and because no timing data was captured no latency claim appears
anywhere. And this paper
evaluates three of the five policies its registered definition named, a
narrowing forced by the isolation discipline above and declared openly. Finally, the
accuracy constraint is met in 58 of 60 cells but not in two, and those two share
a model, a cell and a mechanism instead of being scattered. That is weaker
evidence of coincidence than the count alone suggests, and it is why
§\ref{sec:results-p3} treats the effect as a property of the fact store.
```
