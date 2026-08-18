# §6 Results — 2.0pp

**Status:** not started
**All numbers below are transcribed from `runs/reports/v8_numbers.txt` and cross-checked against the
source file.** Paired bootstrap 95% CI vs matched P0. **† = interval includes zero.**

> **Full-scale N=3 is complete for all four arms** (2026-08-16), against a fresh `v8_p0_500t_r3`
> baseline. The 500-task rows below were re-derived after that refresh — the earlier ones, taken
> against the July control, differed by up to 1.6pp of EX. N=10 at full scale is still running.

Structure as four questions plus a closing constraint paragraph.

---

## 6.1 Does shrinking the prefix pay? (~0.5pp)

**Verdict: conditional on recall, and the aggregate at full scale is null.** ⚠ **This brief is
superseded by the drafted §6.1 below** — the "most consistent lever" reading came from the 50-task
sweep alone and does not survive the full split. Read the DRAFT section, not this.

Isolated schema pruning, 50-task:

| N | Model | EX Δ pp | Raw tokens Δ | Billed Δ |
|---:|---|---|---|---|
| 3 | GPT | +2.0 † | **−25.8%** [−43.3, −2.3] | **−24.3%** [−41.1, −0.2] |
| 3 | Gemini | +4.0 † | **−22.6%** [−31.0, −13.7] | **−16.7%** [−25.0, −8.0] |
| 3 | DeepSeek | −6.0 † | **−14.7%** [−26.2, −2.7] | **−14.1%** [−25.3, −2.2] |
| 10 | GPT | +4.0 † | −19.2% [−39.0, +10.1] † | −16.0% † |
| 10 | Gemini | −2.0 † | **−22.1%** [−30.8, −13.1] | **−16.1%** [−24.4, −7.8] |
| 10 | DeepSeek | −2.0 † | **−20.2%** [−27.4, −12.2] | **−19.3%** [−26.5, −11.3] |
| 25 | GPT | +6.0 † | **−28.7%** [−41.1, −9.1] | **−25.7%** [−38.2, −6.1] |
| 25 | Gemini | −2.0 † | **−24.8%** [−32.2, −16.8] | **−19.6%** [−26.2, −13.1] |
| 25 | DeepSeek | +0.0 † | **−18.8%** [−27.3, −9.6] | **−18.1%** [−26.4, −8.9] |

**Claims this supports.** Raw tokens fall in all nine cells, **−14.7% to −28.7%**, with **8 of 9
intervals excluding zero** — only GPT N=10 is †. EX flat everywhere. The saving does not decay with
N; it is largest at N=25 on GPT (−28.7%) and Gemini (−24.8%), which is what the cost identity
predicts since the prefix is re-billed on every turn of every replica.

**The recall panel — the paper's only full-scale online-independent evidence.** From
`runs/reports/schema_pruning.md` and `schema_pruning_full500.md`:

| | 50-task | 500-task |
|---|---|---|
| Gold-table recall | **100%** (50/50) | **89.6%** (448/500) |
| Avg schema reduction | 34.5% | 29.4% |
| Avg tables kept | 3.4 | 4.4 |
| Full-schema fallbacks | 2 | 116 |

Per-database reduction spread: **62.5%** on `student_club` down to **15.8%** on
`debit_card_specializing`. Misses concentrate on databases without hand-written recall patches —
`california_schools`, `financial`, `toxicology`, `superhero`.

**Lean on this.** It is genuine full-scale evidence, it is a scale effect a 50-task study would
otherwise have missed, and it converts the paper's biggest coverage gap into a demonstrated
understanding of its own limits. The deployment rule: validate offline gold-table recall per
database, and treat anything under 100% as a blocker.

**Fig. 3** goes here (`thesis/figures/schema_prune_offline_by_db.png`) — per-database reduction vs
gold recall. This one is safe to reuse as-is: it comes from the offline analysis, not from a batch,
so the strict-mode purge does not touch it.

---

## 6.2 Does sharing knowledge pay — on its own? (~0.45pp)

⚠ **Rewritten 2026-08-17 — the full-scale N=10 column reverses the planned verdict. Read this, not
the 50-task narrative below it.**

**Verdict: in isolation the token effect has no consistent sign *at 50 tasks*, but at full scale it
is consistently non-positive — and it is the one place in the study where a method buys tokens with
accuracy.** Scope every sign claim to its scale, and forward-reference §6.4.

### The scale reversal — this is the subsection's real finding

| | 50-task | 500-task |
|---|---|---|
| GPT | −17.2% · +0.9%† · −13.2%† | **−8.9%** · **−8.8%** (both significant) |
| Gemini | +1.9%† · +8.4%† · +3.4%† | +1.5%† · +1.4%† (null, consistently) |
| DeepSeek | **+20.2%** · +21.1%† · **+16.0%** | −5.8%† · **−7.0%** |

*(50-task cells are N=3 · 10 · 25; 500-task are N=3 · 10.)*

**DeepSeek's sign flips completely.** On the 50-task subset it pays 16–21% in all three cells, two
significantly; across all 500 tasks it *saves*, significantly at N=10. The "DeepSeek pays the
injection tax" mechanism story below was built on the subset and **does not replicate**. Injections
per task are nearly identical at the two scales (N=10: 32.4 vs 28.3), so the tax is not what
changed — the 50-task sample was.

At full scale the picture is much tidier than "no reliable sign": **four of six cells save, three
significantly, and none pay.** Do not carry the 50-task framing into the full-scale paragraph.

### The accuracy cost — the constraint's only violation

**DeepSeek, 500 tasks, N=10: EX −3.5pp [−5.7, −1.4] while saving 7.0% of tokens.** This is the only
cell in sixty where a method *in isolation* moves accuracy significantly, and it is the paper's one
genuine trade rather than a free saving. Note also that the composed arm at the same cell is the
only other EX exception (−2.4pp), and the two arms *without* the fact store there are both † — so
the fact store is the common factor, not chance. §6.5 must not present the two exceptions as
independent draws.

**The honest verdict for the abstract and §8:** the fact store saves modestly at scale on two models
of three, but on one of them the saving is paid for in accuracy — which is exactly what an
EX-as-constraint design exists to detect.

50-task:

| N | Model | EX Δ pp | Raw tokens Δ | Billed Δ | inj/task |
|---:|---|---|---|---|---:|
| 3 | GPT | −2.0 † | **−17.2%** [−29.8, −0.7] | **−17.5%** [−29.6, −1.3] | 6.0 |
| 3 | Gemini | +0.0 † | +1.9% † | +1.1% † | 3.1 |
| 3 | DeepSeek | −6.0 † | **+20.2%** [+0.6, +39.2] | +19.7% † | 10.2 |
| 10 | GPT | −4.0 † | +0.9% † | +1.5% † | 21.2 |
| 10 | Gemini | +2.0 † | +8.4% † | +7.2% † | 11.2 |
| 10 | DeepSeek | −4.1 † | +21.1% † | +21.6% † | 32.4 |
| 25 | GPT | −6.0 † | −13.2% † | −11.8% † | 52.6 |
| 25 | Gemini | +2.0 † | +3.4% † | +2.9% † | 27.2 |
| 25 | DeepSeek | +2.0 † | **+16.0%** [+0.8, +30.9] | +14.6% † | 89.4 |

500-task, N=3 (against the fresh baseline):

| Model | n | EX Δ pp | Raw tokens Δ | Billed Δ | inj/task |
|---|---:|---|---|---|---:|
| GPT | 496 | −0.2 † | **−8.9%** [−15.4, −1.9] | **−8.8%** [−15.2, −2.0] | 6.1 |
| Gemini | 495 | +0.0 † | +1.5% † | +1.1% † | 3.2 |
| DeepSeek | 496 | −0.8 † | −5.8% † | −6.0% † | 8.5 |

⚠ **Superseded — see the scale-reversal block at the top of §6.2.** This note was written when only
the 500t N=3 column existed and said the "no reliable sign" verdict still held. With N=10 in, the
full-scale column is consistently non-positive and the verdict needs scoping to the 50-task subset.

**The pattern, 50-task only:** GPT saves (−17.2% at N=3). DeepSeek pays (+20.2% at N=3, +16.0% at
N=25). Gemini is null at every N. ⚠ **Label this as 50-task wherever it appears** — DeepSeek's sign
reverses at full scale.

**The mechanism argument — but weaker than it looked.** Injections per task scale steeply with N
(GPT 6.0 → 21.2 → 52.6; DeepSeek 10.2 → 32.4 → 89.4) because more peers publish more facts. The tax
is real and it is measurable. It is **not sufficient** to explain the sign, and the full-scale data
shows why: DeepSeek carries a near-identical injection load at both scales (32.4 vs 28.3 per task at
N=10) yet pays 21% at 50 tasks and saves 7% at 500. Whatever decides the sign, it is not injection
volume alone. Report the tax as a mechanism that *bounds* the saving, not one that predicts it.

**The correction — a genuine methodological contribution.** The previously reported "GPT adopts the
fact store" win was measured *inside* a stack containing the shared SQL cache, early stopping and
pruning; v7's corresponding table is a fact-store-vs-fragment-stack comparison, not an isolation
result. Isolation is what makes the per-model sign attributable at all. Present this as ablation
discipline, not as an erratum.

---

## 6.3 Does repricing pay? (~0.45pp)

**Verdict: the unconditional win, and the best-evidenced section in the paper — the arm is complete,
9/9.**

| N | Model | EX Δ pp | Raw tokens Δ | Billed Δ |
|---:|---|---|---|---|
| 3 | GPT | +6.0 † | −13.3% † | **−36.5%** [−49.9, −21.1] |
| 3 | Gemini | +0.0 † | +2.8% † | **−35.9%** [−43.4, −27.1] |
| 3 | DeepSeek | +0.0 † | +5.6% † | **−81.9%** [−84.2, −79.2] |
| 10 | GPT | +2.0 † | **+10.2%** [+0.6, +24.0] | **−18.8%** [−26.6, −8.8] |
| 10 | Gemini | −2.0 † | −0.6% † | **−45.3%** [−49.5, −40.5] |
| 10 | DeepSeek | −2.0 † | +4.8% † | **−81.5%** [−83.1, −79.9] |
| 25 | GPT | −2.0 † | −1.5% † | **−28.0%** [−34.5, −20.2] |
| 25 | Gemini | +0.0 † | +1.4% † | **−44.7%** [−48.8, −40.1] |
| 25 | DeepSeek | +0.0 † | −0.3% † | **−82.0%** [−83.2, −80.7] |

**Headline.** Across all nine cells, raw tokens are statistically indistinguishable from zero in
**eight**, while billed input falls in **all nine**, −18.8% to −82.0%, every interval excluding zero.
The N=25 row is the cleanest demonstration that the same bytes are being repriced: raw −1.5† / +1.4†
/ −0.3† against billed −28.0% / −44.7% / −82.0%.

**The two-ledger punchline** is the one cell that breaks raw-token neutrality — **GPT at N=10: raw
+10.2% [+0.6, +24.0], billed −18.8% [−26.6, −8.8]**. Same model, same run, both intervals excluding
zero, opposite directions.

**Handle it precisely.** The loop is content-neutral *per turn* but not *trajectory*-identical, so
run-to-run divergence surfaces in raw tokens; one significant excursion in nine is consistent with
that, and the billed comparison is the meaningful one. **Do not present it as a mechanism effect** —
it illustrates why the two ledgers must be reported separately, it is not evidence that caching
increases consumption.

Repeat the price caveat in one clause: cached input costs 50% of standard on GPT, 10% on Gemini and
2% on DeepSeek, so the spread across models is a price schedule as much as a mechanism.

**Two figures serve this subsection.**

**Fig. 2** (`thesis/figures/fig2_cached_by_turn.png`) — cached share of input by turn. Draft caption:

> **Fig. 2.** Share of input tokens served from the provider cache, by turn index, under the
> cache-stable loop at N=25 (50 tasks). DeepSeek holds 94–97% from the first turn; GPT-4o mini climbs
> from 53% to ~80% as the append-only history grows against a frozen prefix. Each series is truncated
> where fewer than 20 replica-turns reach that depth.

**The truncation must stay in the caption.** Without it Gemini shows a dip to 17% at turn 7 computed
from **three observations**, which reads as a cache collapse and is noise. Do not restore the untruncated
version, and do not add a P0 comparison line: baseline batches report zero cached tokens because that
backend never reads the provider field, not because the cache demonstrably failed.

**Fig. 4** (`thesis/figures/fig4_two_ledger.png`) — the visual form of this whole subsection. Draft
caption:

> **Fig. 4.** Raw versus billed token change for all 36 measured 50-task cells (three methods plus the
> composed stack, three models, N ∈ {3, 10, 25}). Colour is the model, shape the method; the dashed
> line marks raw = billed. Schema-pruning and fact-store cells track the diagonal — both ledgers move
> together. Prompt-cache cells fall well below it, and the DeepSeek cells sit on a −82% billed floor at
> near-zero raw change. The labelled cell moves in opposite directions on the two ledgers, both
> intervals excluding zero.

---

## 6.4 Does composition add up? (~0.5pp) — the paper's most interesting result

**Verdict: it over-delivers, but less emphatically than the 50-task sweep suggested — 11 of 15
configurations beat the product of their parts.**

⚠ **Updated 2026-08-17 with the full-scale N=10 row.** The count was 10 of 12 when full scale had
only N=3. The two new cells both *miss*, and they miss by almost nothing: Gemini +2.1pp and DeepSeek
+0.3pp against the multiplicative null. DeepSeek at 500t N=10 is the closest fit to plain
multiplicative composition anywhere in the study (predicted −16.6%, measured −16.3%).

**What this does to the claim.** Super-additivity is strongest where the evidence is weakest (50
tasks, wide intervals) and weakest where the evidence is strongest (500 tasks, N=10, tight
intervals). Full scale splits 4 of 6. That does not overturn the finding — the stack still beats or
matches its parts in every one of fifteen configurations, and never meaningfully underperforms them
— but the defensible sentence is **"composition at least matches, and usually beats, the product of
its parts"**, with super-additivity presented as strongest at small N. Do not lead with 11 of 15 as
though it were 15 of 15, and do not quote the 50-task gaps as representative.

Composed (all three) vs matched P0, 50-task:

| N | Model | EX Δ pp | Raw tokens Δ | Billed Δ | inj/task |
|---:|---|---|---|---|---:|
| 3 | GPT | +6.0 † | **−39.3%** [−59.0, −11.3] | **−47.1%** [−63.8, −23.9] | 4.7 |
| 3 | Gemini | +0.0 † | **−23.6%** [−32.8, −13.1] | **−23.4%** [−31.8, −13.9] | 3.2 |
| 3 | DeepSeek | +0.0 † | **−23.8%** [−36.3, −9.8] | **−83.6%** [−86.2, −80.7] | 6.1 |
| 10 | GPT | +0.0 † | **−29.5%** [−43.9, −7.6] | **−37.4%** [−48.9, −20.2] | 15.2 |
| 10 | Gemini | −6.0 † | **−24.6%** [−33.5, −14.5] | **−32.0%** [−38.1, −25.1] | 10.3 |
| 10 | DeepSeek | +0.0 † | −10.0% † | **−81.1%** [−83.5, −78.3] | 19.9 |
| 25 | GPT | −2.0 † | **−35.4%** [−47.4, −18.7] | **−43.9%** [−53.5, −30.3] | 39.1 |
| 25 | Gemini | −4.0 † | **−24.4%** [−34.7, −12.7] | **−37.9%** [−44.3, −30.8] | 25.6 |
| 25 | DeepSeek | +4.0 † | −11.2% † | **−82.0%** [−84.3, −79.8] | 46.1 |

Raw tokens fall in all nine (−10.0% to −39.3%, **significant in 7 of 9** — the two † are DeepSeek at
N=10 and N=25). Billed falls in all nine (−23.4% to −83.6%, every interval excluding zero). EX flat.

**The additivity check.** Against a multiplicative prediction from the isolated cells:

| N | Model | prune | fact store | cache | predicted | measured | gap |
|---:|---|---:|---:|---:|---:|---:|---:|
| 3 | GPT | −25.8 | −17.2 | −13.3 | −46.7 | −39.3 | +7.4 (under) |
| 3 | Gemini | −22.6 | +1.9 | +2.8 | −18.9 | −23.6 | −4.7 |
| 3 | DeepSeek | −14.7 | +20.2 | +5.6 | **+8.3** | **−23.8** | **−32.1** |
| 10 | GPT | −19.2 | +0.9 | +10.2 | −10.2 | −29.5 | −19.3 |
| 10 | Gemini | −22.1 | +8.4 | −0.6 | −16.1 | −24.6 | −8.5 |
| 10 | DeepSeek | −20.2 | +21.1 | +4.8 | **+1.3** | **−10.0** | **−11.3** |
| 25 | GPT | −28.7 | −13.2 | −1.5 | −39.0 | −35.4 | +3.6 (under) |
| 25 | Gemini | −24.8 | +3.4 | +1.4 | −21.2 | −24.4 | −3.2 |
| 25 | DeepSeek | −18.8 | +16.0 | −0.3 | −6.1 | −11.2 | −5.1 |

**Full scale (500 tasks, N=3) — all three beat their parts:**

| N | model | prune | P3 | cache | predicted | measured | gap |
|---:|---|---:|---:|---:|---:|---:|---:|
| 3 | GPT | −8.5 | −8.9 | −2.5 | −18.7 | −28.8 | −10.1 |
| 3 | Gemini | −3.9 | +1.5 | +1.4 | −1.1 | −3.3 | −2.2 |
| 3 | DeepSeek | −3.0 | −5.8 | −0.4 | −9.0 | −13.2 | −4.2 |

**11 of 15 across both scales**, but only 4 of 6 at full scale, where the intervals are tightest
and the two misses are near-exact ties with the null. This is
the strongest form of the claim: the pattern is not an artefact of the noisy subset.

**The DeepSeek rows carry the finding.** In isolation the parts predict a net token *increase* —
+8.3% at N=3, +1.3% at N=10 — yet the composed stack *saves* 23.8% and 10.0%. The complementary
channel (facts substituting for schema the pruner removed) dominates the substitutive one, which
survives only as GPT's two under-delivering cells.

**It reverses §6.2's deployment implication.** Isolated ablation says *do not enable the fact store*;
composition says *it earns its place in the stack*. That tension is the paper's sharpest
methodological point: **isolation is necessary for attribution and insufficient for deployment.**

**Three caveats that must accompany the table — do not omit any:**
1. Isolated and composed batches are **independent runs**, so this is descriptive arithmetic, not a
   paired test.
2. The isolated intervals are wide.
3. 7-of-9 in one direction is suggestive but **does not reach significance on a sign test alone**
   (p ≈ 0.18 two-sided). Every cell is a single run.

The defensible claim is a **consistent direction across nine configurations**, not a replicated
effect. Say it that way.

**Fig. 5** goes here (`thesis/figures/fig5_additivity.png`). Draft caption:

> **Fig. 5.** Measured composed raw-token change against the multiplicative prediction from the three
> isolated arms. Filled markers are the 50-task sweep across replica counts; open markers are the
> full 500-task split at N=3. Both axes are percentage change, so points in the shaded region below
> the diagonal save *more* than their parts predict. Ten of twelve configurations fall there,
> including all three at full scale; the two exceptions are GPT-4o mini at N=3 and N=25. For the
> labelled cell the isolated arms predict a net token *increase* of 8.3% while the stack delivers a
> 23.8% saving — DeepSeek at N=10 shows the same reversal. Isolated and composed runs are
> independent, so the comparison is descriptive.

The shaded region is **below** the diagonal — more negative measured change means more saving. An
earlier version of this figure shaded above the line, which inverts the claim.

---

## 6.5 Accuracy is untouched (~0.1pp)

⚠ **Revised 2026-08-17 — the absolute claim no longer holds.** Across the **60 cells** now measured (the complete 36-cell 50-task design plus 24 full-scale
cells), **58 of 60 EX intervals include zero.** The two exceptions are both **DeepSeek at 500
tasks, N=10**: the **fact store alone at −3.5pp [−5.7, −1.4]**, and the **composed stack at −2.4pp
[−4.8, −0.2]**.

**The multiple-comparisons argument is necessary but no longer sufficient — do not stop there.**
Sixty intervals at 95% confidence would be expected to produce roughly **3.0** exceptions under a
true null, so two is fewer than chance predicts. That is the right first sentence. It is not the
last one, because **the two exceptions are not independent draws**: same model, same scale, same
replica count, and the common factor is the fact store, which appears in both arms. The two arms at
that cell *without* the fact store are both † (pruning −1.6pp, prompt cache −1.2pp).

So the honest reading has two parts: across the design as a whole the constraint holds, and at one
identified cell — DeepSeek, full scale, ten replicas — the fact store costs accuracy while saving
tokens. Give both. Cross-reference §6.2, which owns the interpretation. Never write "all cells".

Then frame the constraint as met *with one identified exception*: no prompt-layer policy moves
accuracy at any replica count on any model by more than the noise of the design, except the fact
store on DeepSeek at full scale, where it trades 3.5pp of accuracy for 7% of tokens. That
exception is a finding, not an embarrassment — an EX-as-constraint design exists precisely to
surface it, and a paper that reported only token savings would have shipped it silently.

**Cell count is load-bearing in three places** (§1 C5, here, §7 item 12). The design is now
complete at 60 cells — 36 at 50 tasks, 24 at full scale — and `p3_500t_r10` was the last wave, so
this number should not move again. Recount with `scripts/v8_additivity.py` rather than trusting it.

---

## Regenerating the additivity table, the EX audit and the coverage list

    uv run python scripts/analyze_v8_results.py    # strict: no --allow-legacy
    uv run python scripts/v8_additivity.py

`v8_additivity.py` **parses `v8_numbers.txt`** rather than carrying transcribed rows. The previous
version of this snippet was a hardcoded list, which is precisely the failure its own warning
described: isolated and composed cells must come from the same generation of the report, and a
copied row survives a refresh that moves it. Do not reintroduce hand-entered numbers here.

It prints three things §6 needs and one it must not forget:

- the additivity table with a **multiplicative** null (state the null wherever the gap is quoted — an
  additive null gives materially different gaps)
- the count of EX intervals excluding zero, with the expected-under-null figure for §6.5
- the total cell count, which is load-bearing in §1 C5, §6.5 and §7
- **the list of still-missing cells** — check this before writing any "across all cells" sentence

Output as of 2026-08-17 (design complete): **60 cells**, **11 of 15 configurations beat the product
of their parts**, 2 of 60 EX intervals exclude zero (~3.0 expected), **0 cells missing**.

---

## DRAFT

**Status: §6.1 drafted 2026-08-16, revised 2026-08-17 for the N=10 full-scale wave.
§6.2–§6.5 pending — see the coverage note below.**

**Coverage as of 2026-08-17.** The N=10 full-scale wave is complete for `p0`, `prune`, `pc` and
`comp` on all three models (Gemini's prune landed 12:08 at 480/500, inside the 90% gate).
**The one outstanding wave is `p3_500t_r10`, all three models.** Until it lands,
§6.2 has no full-scale replica axis and §6.4 cannot compute a full-scale N=10 additivity row.
§6.3 is unblocked and complete at both scales.

The assembler splices whichever `\section`-opening block is longest, so this partial draft is wrapped
as `\section{Results}` with only the first subsection filled. **Add §6.2–§6.5 into this same block**
rather than starting a second one.

**§6.1 was rewritten after the full-scale column landed.** The brief above called pruning "the most
consistent lever in the matrix" on the strength of the 50-task sweep. At 500 tasks the isolated
saving is **not significant on any model**. The reason is in the recall split, and it turns a
weakened result into the paper's cleanest causal finding — so the subsection now leads with the
condition rather than the aggregate. **Do not restore the old verdict.**

Numbers verified against `runs/reports/v8_numbers.txt` and the two offline pruning reports; the
recall split is regenerated by the snippet at the foot of this file.

```latex
\section{Results}\label{sec:results}

\subsection{Does a smaller schema pay?}\label{sec:results-prune}

On the 50-task subset, pruning looks like the most dependable lever in the
study. Raw tokens fall in all nine configurations by 14.7--28.7\%, eight of the
nine intervals exclude zero, and no accuracy interval does. Nor does the saving
decay as replicas are added. It is largest at $N = 25$, reaching $-$28.7\%
on GPT-4o mini and $-$24.8\% on Gemini, exactly as Eq.~\ref{eq:cost} predicts of
a term re-billed on every turn of every replica
(Table~\ref{tab:appendix-matrix-50}).

At full scale that result largely disappears. Across all 500 tasks at $N = 3$,
isolated pruning saves $-$8.5\% on GPT ([$-$16.6, $+$0.9]), $-$3.9\% on Gemini
([$-$11.9, $+$4.8]) and $-$3.0\% on DeepSeek ([$-$11.8, $+$6.9]). Not one
interval excludes zero. At $N = 10$ the same measurement partly recovers:
$-$10.9\% on GPT ([$-$17.6, $-$3.2]) and $-$9.1\% on DeepSeek ([$-$15.5,
$-$1.8]) both exclude zero, while Gemini reaches $-$8.3\% on an interval that
misses by a tenth of a point ([$-$15.8, $+$0.1]). A method that does nothing at three replicas and something at ten is not a
method whose headline number means much, and the offline analysis explains why
the aggregate is the wrong object of study in the first place.
On the smoke subset the pruner retains every gold table on every task, and across
the full split it does so for 448 of the 500, or 89.6\%, because the recall rules
of §\ref{sec:prune} are written per database and eleven databases are not eleven
rules. Splitting the full-scale runs on that offline signal separates two
populations the aggregate had been averaging together
(Table~\ref{tab:recall-split}): a 9.9--19.7\% saving where recall is complete,
and a 32--156\% \emph{increase} where a gold table is missing. The regimes are
stable where the aggregate is not.

\begin{table}[t]
\caption{Isolated pruning at full scale, split by whether the offline analysis
retained every gold table for that question. Paired bootstrap 95\% intervals on
raw tokens, in per cent; \dag\ marks an interval containing zero. Recall-complete
groups hold 440--446 questions, recall-incomplete groups 38--50. Every
recall-complete cell saves significantly and every recall-incomplete cell costs,
and the split is the same at both replica counts.}
\label{tab:recall-split}
\centering
\scriptsize
\begin{tabular}{@{}llrr@{}}
\toprule
 & & \multicolumn{2}{c}{Raw-token change (\%)} \\
\cmidrule(l){3-4}
$N$ & Model & Recall complete & Recall incomplete \\
\midrule
3 & GPT-4o mini & $-$16.1 [$-$21.6, $-$10.3] & $+$55.3 [$-$0.6, $+$139.7]\dag \\
3 & Gemini 2.5 Flash & $-$19.4 [$-$23.1, $-$15.6] & $+$155.8 [$+$87.2, $+$230.8] \\
3 & DeepSeek v4-flash & $-$9.9 [$-$17.9, $-$0.8] & $+$57.4 [$+$21.5, $+$110.1] \\
\midrule
10 & GPT-4o mini & $-$17.8 [$-$22.1, $-$13.4] & $+$49.7 [$-$2.0, $+$123.3]\dag \\
10 & Gemini 2.5 Flash & $-$19.7 [$-$23.7, $-$15.3] & $+$137.2 [$+$55.8, $+$230.4] \\
10 & DeepSeek v4-flash & $-$13.8 [$-$20.5, $-$5.9] & $+$32.1 [$+$13.2, $+$56.3] \\
\bottomrule
\end{tabular}
\end{table}

A missed table therefore does more than forfeit the saving: it multiplies the
cost, because an agent handed a schema without a table it needs does not fail
quickly but explores, retries, and on Gemini spends more than two and a half
times what the unpruned run spends on the same question. One task in ten behaving that
way cancels the saving on the other nine, which yields a deployment rule with a
test attached. Which regime a task falls into is knowable \emph{before any model
is called}, because offline gold-table recall needs no inference, only the gold
queries, and it predicts the sign of the token effect. Validate it per database,
enable pruning where recall is complete, and treat anything short of complete
recall as a blocker for that database. Correctness of table selection, not
aggressiveness of reduction, decides whether shrinking the prefix pays at all.

The shortfall is concentrated rather than diffuse, since the four databases
carrying
hand-written recall rules retain every gold table, while \texttt{financial} and
\texttt{california\_schools}, which carry none, retain them on 56\% and 60\% of
tasks and account for most of the misses. Reduction and recall are not in
tension, since the most aggressively pruned database, \texttt{student\_club} at
62.5\%, keeps every gold table. The per-database breakdown is
Table~\ref{tab:appendix-perdb}.

\subsection{Does the fact store pay on its own?}\label{sec:results-p3}

Measured in isolation, the fact store is the least predictable of the three
methods, and the only one whose direction depends on how many tasks it is
measured over.

On the 50-task subset its token effect has no consistent sign. GPT-4o mini saves
17.2\% at three replicas, Gemini is indistinguishable from zero at every replica
count, and DeepSeek \emph{pays}, at 20.2\%, 21.1\% and 16.0\% for three, ten and
twenty-five replicas, two of the three intervals excluding zero. Read on its own
that is a clean per-model result, and it invites a mechanical explanation. The
store taxes every turn of every replica with injected text. Injections per task
grow steeply with $N$, from 6.0 to 52.6 on GPT and 10.2 to 89.4 on DeepSeek, and
whether the method pays turns on whether saved probes outrun that tax.

The full split contradicts it. Across all 500 tasks the fact store saves 8.9\%
and 8.8\% on GPT at three and ten replicas, both intervals excluding zero.
Gemini remains null, and DeepSeek, the model that appeared to pay most,
\emph{saves} 5.8\% and 7.0\%, significantly at ten replicas. Four of the six
full-scale cells save, three of them significantly, and none pay, as the
complete grid in Table~\ref{tab:appendix-matrix-500} shows.

The injection tax cannot explain the reversal, because the tax barely moved:
DeepSeek carries 32.4 injections per task at fifty tasks and 28.3 at five
hundred, for the same ten replicas. What changed is the sample. The subset
over-represents tasks on which peer facts are redundant, and the tax that looked
decisive is better described as a quantity that \emph{bounds} the saving than
one that predicts its sign. This is the clearest instance in the study of a
50-task result that does not survive scale, and it is a caution about the subset
sizes at which coordination layers are usually evaluated.

Accuracy is where the method's real cost appears. On DeepSeek at full scale and
ten replicas the fact store saves 7.0\% of tokens while losing 3.5 points of
execution accuracy ([$-$5.7, $-$1.4]), which is the only cell in the entire
design where a method in isolation moves accuracy at all, as
§\ref{sec:results-ex} sets out. Everywhere else the store is accuracy-neutral, and
nowhere does it improve accuracy. Shared knowledge is advisory, and a replica
that adopts a peer's premature finding can be led away from a correct
trajectory as easily as toward one.

\subsection{Does cache-stable structure pay?}\label{sec:results-pcache}

Unconditionally, and by the largest margin in the study. Cache-stable structure
is the only method here that changes no content: the bytes sent are identical to
the baseline's, reordered only so that the prefix stays stable and growth
remains append-only. What changes is the rate at which they are billed.

The prediction is unusually sharp and falsifiable in two directions at once:
raw consumption should not move, while billed input should fall by whatever
share of the prompt the provider serves from cache. Across the fifteen measured
configurations, raw tokens are indistinguishable from zero in fourteen, while
billed input falls in \emph{all} fifteen, from 18.8\% to 86.0\%, every interval
excluding zero.


The full-scale half of that grid is the cleanest evidence in the paper for the
two-ledger claim of §\ref{sec:ledgers}: six cells in which one ledger does not
move while the other falls from $-$38.3\% on GPT-4o mini to $-$86.0\% on
DeepSeek. Fig.~\ref{fig:twoledger} shows that
separation across the whole design, with the methods that change content lying
along the diagonal and the method that changes only price falling far below it.
The complete grids, with intervals, are
Tables~\ref{tab:appendix-matrix-50} and~\ref{tab:appendix-matrix-500}.

The single cell that breaks raw-token neutrality is worth reporting rather than
rounding away. On the 50-task subset at $N = 10$, GPT-4o mini records raw
$+$10.2\% [$+$0.6, $+$24.0] against billed $-$18.8\% [$-$26.6, $-$8.8]: the same
run, both intervals excluding zero, the two ledgers moving in opposite
directions. This is not a mechanism effect, because a method that changes no
content cannot make an agent consume more. It is the expected consequence of a
design that is content-neutral \emph{per turn} yet not trajectory-identical: a
reordered prompt can still tip a sampled decision. The full-scale measurement
settles it, recording raw $+$1.9\% [$-$0.7, $+$4.7] on ten times the sample. The
excursion was subset noise, and the billed comparison was the meaningful one
throughout.

The per-turn cache shares show the mechanism directly. DeepSeek serves 94--97\%
of input from cache from the first turn, while GPT-4o mini climbs from 53\% at the
first turn to roughly 80\% by the fourth, as an append-only history accumulates
behind a frozen prefix. That climb is the cost identity read backwards. The
longer the conversation runs, the larger the share of $P + \bar{H}$ already
seen, and the more of it the provider discounts.

Two qualifications belong with the result. First, the spread across models is a price schedule as much as a mechanism,
since DeepSeek's 86\% is mostly its 50-fold cached discount and an identical hit
rate would be worth 40\% on GPT. Second,
provider caches are opaque and cached-token counts are provider-reported. This
work takes both at face value and prices them at published list rates.

\begin{figure}[t]
\centering
\includegraphics[width=\columnwidth]{figures/fig4_two_ledger.png}
\caption{Raw against billed token change for all sixty measured cells. Colour is
the model, shape the method. Filled markers are the 50-task subset and open
markers the 500-task split. The dashed line marks raw $=$ billed. Pruning and
fact-store cells track it, because they change content and so move both ledgers
together, while prompt-cache and composed cells fall far below it. Every
DeepSeek cell carrying the cache sits on a floor near $-$85\%. The labelled cell is the
one that moves in opposite directions on the two ledgers, both intervals
excluding zero.}
\label{fig:twoledger}
\end{figure}


\subsection{Do the three add up when combined?}\label{sec:results-compose}

Because the three methods act on different factors of Eq.~\ref{eq:cost}, their
savings would compose multiplicatively if they did not interact. That product is
the null tested here. For each of the fifteen configurations the isolated arms
give a predicted change and the composed arm a measured one, and the gap between
them is the interaction.

The stack beats that prediction in eleven of fifteen configurations. The
clearest case is DeepSeek at three replicas on
the subset, where the parts predict a net \emph{increase} of 8.3\%, the fact
store's 20.2\% penalty outweighing pruning's 14.7\% saving. The composed stack
removes 23.8\% instead, a gap of 32 points. Two of the three interaction
channels of §\ref{sec:interact} predict exactly this: distilled peer facts
substitute for schema the pruner removed, and the append-only injection
discipline lets the fact store coexist with the cache instead of invalidating
it. The four configurations that miss do so narrowly, and none reverses: GPT
falls 7.4 and 3.6 points short at three and twenty-five replicas on the subset,
and at full scale with ten replicas Gemini and DeepSeek come within 2.1 and 0.3
points of the null. In no configuration does the stack save appreciably less
than its parts.


Two cautions constrain how far that can be pushed. The comparison is
descriptive, not inferential:
isolated and composed cells come from independent runs rather than paired ones,
so no interval attaches to a gap, and eleven of fifteen in one direction is a
tendency rather than a tested effect. And the tendency is strongest where the
evidence is weakest. The four misses concentrate at full scale, where intervals
are tightest, while the widest super-additive gaps all sit at fifty tasks. The defensible claim is that composition at least matches, and usually
exceeds, the product of its parts, with the excess largest at small $N$.

The deployment consequence is the reason this matters.
Section~\ref{sec:results-p3} found the fact store had no reliable sign alone and
cost accuracy on one model, so an ablation stopping there would drop it. Yet it is
a component of every composed configuration measured here, including the two
that save most. Isolation is necessary to attribute a saving to a mechanism. It
is not sufficient to decide whether that mechanism belongs in the stack, and a
study that reported only isolated ablations would recommend removing a component
that pays for itself in company.

\subsection{Does accuracy hold throughout?}\label{sec:results-ex}

Across all sixty measured cells, fifty-eight execution-accuracy intervals
contain zero. Sixty intervals at 95\% confidence would be expected to
produce roughly three exceptions if no method affected accuracy anywhere, so two
is fewer than chance alone would give.

That arithmetic is not the whole answer, because the two exceptions are not
independent draws. Both are DeepSeek at full scale and ten replicas, the fact
store alone at $-$3.5 points and the composed stack at $-$2.4 points. The two
arms at that same cell that do \emph{not} contain the fact store are both
consistent with zero, pruning at $-$1.6 and prompt cache at $-$1.2. A pair of exceptions
sharing a model, a cell and a mechanism is weaker evidence of coincidence than a
scattered pair would be. The constraint holds across the design as a whole,
and it is violated in one identified place by one identified component, as
§\ref{sec:results-p3} explains.

```

**`fig:twoledger` was cut here on 2026-08-17 for space** (README budget note). Table
`tab:pcache-500` carries the two-ledger claim numerically and the prose states it in words, so the
scatter was the most decorative float in the paper. `fig5_additivity.png` earns its place in §6.4
because the diagonal comparison is genuinely hard to read off a table; this one did not.

The figure is still generated by `make_v8_figures.py` and still bundled. To restore it, drop this
block back into the §6.3 LaTeX after the closing paragraph, and remove the appendix's note that it
was cut:

```latex
\begin{figure}[t]
\centering
\includegraphics[width=\columnwidth]{figures/fig4_two_ledger.png}
\caption{Raw versus billed token change across the 36 measured 50-task cells
(three methods and the composed stack, three models, $N \in \{3, 10, 25\}$).
Colour is the model, shape the method; the dashed line marks raw $=$ billed.
Pruning and fact-store cells track the diagonal, moving both ledgers together.
Prompt-cache cells fall well below it, and the DeepSeek cells sit on an $-$82\%
billed floor at near-zero raw change. The labelled cell moves in opposite
directions on the two ledgers, both intervals excluding zero.}
\label{fig:twoledger}
\end{figure}
```

### Regenerating the recall split

Run with `uv run python - <<'EOF' ... EOF` (the analysis imports the shared bootstrap helpers):

    import sys, json, glob; sys.path.insert(0, '.'); sys.path.insert(0, 'scripts')
    from pathlib import Path
    from generate_robustness_pack import _bootstrap_mean_pct, _metric_map

    rec = {int(r['question_id']): float(r['gold_table_recall'])
           for r in json.load(open('runs/reports/schema_pruning_full500.json'))['rows']}
    full = {q for q, v in rec.items() if v >= 1.0}
    miss = {q for q, v in rec.items() if v < 1.0}

    for key in ('gpt-4o-mini', 'gemini-2.5-flash', 'deepseek-v3.2'):
        t = glob.glob(f'runs/batches/parallel_v8_prune_500t_r3_{key}_r3_*.json')
        c = glob.glob(f'runs/batches/parallel_v8_p0_500t_r3_{key}_r3_*.json')
        if not (t and c):
            continue
        tm, cm = _metric_map(Path(t[0]), 'tokens'), _metric_map(Path(c[0]), 'tokens')
        row = []
        for grp in (full, miss):
            n, _, _, d, lo, hi = _bootstrap_mean_pct(
                {k: v for k, v in tm.items() if k in grp},
                {k: v for k, v in cm.items() if k in grp})
            row.append(f'{d:+6.1f}% [{lo:+5.1f},{hi:+5.1f}] n={n}')
        print(f'{key:18} complete {row[0]}   incomplete {row[1]}')

Values as of 2026-08-16: 448 complete / 50 incomplete offline; complete −16.1 / −19.4 / −9.9%,
incomplete +55.3 / +155.8 / +57.4%. All six intervals exclude zero.

---

## Labels this section must define

§4 is drafted and forward-references these. Use exactly these names:

| Label | Where |
|---|---|
| `sec:results-prune` | §6.1 — cited twice from §4.1 (recall precondition, generalisation bound) |
| `sec:results-p3` | §6.2 — cited from §4.2's failure-mode paragraph |
| `sec:results-pcache` | §6.3 — cited from §4.3 (billing ledger, price caveat) |
| `sec:results-compose` | §6.4 — cited from §4.4's closing line |

§4 also defines `sec:prune`, `sec:p3`, `sec:pcache`, `sec:interact`, `alg:prune`,
`tab:prune-example`, `fig:digest` and `fig:zones` if you need to point back at them.
