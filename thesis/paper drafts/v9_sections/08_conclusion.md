# §8 Conclusion and future work — 0.4pp

**Status:** not started
**Source to adapt:** `draft_paper_ieee_v7.tex` lines 954–988 — but v7's conclusion is built on
database round-trips and must be rewritten, not edited.

---

## Conclusion

Answer the narrowed research question directly and in one sentence before elaborating. Of the three
prompt surfaces:

> **Repricing is unconditional, shrinking is conditional on recall, and reshaping pays only in
> company.**

Then the supporting beats, compactly:

- **Repricing** — cache-stable prompt structure changes no content byte, leaves raw tokens
  statistically unchanged in 8 of 9 cells, and cuts billed input 18.6–82.0% in all nine. It is the
  one method with no precondition and no failure mode worse than silently reverting to baseline cost.
- **Shrinking** — pruning reliably cuts 14.7–28.7% of raw tokens with accuracy flat, but full-scale
  gold-table recall of 89.6% makes *correctness of table selection*, not aggressiveness of pruning,
  the thing that determines whether it is safe to deploy.
- **Reshaping** — the fact store has no reliable sign in isolation, yet the stack that includes it
  beats the product of its parts on 11 of 15 configurations. Isolation attributes; composition
  decides.
- **The constraint holds, with one named exception** — accuracy is unmoved in 58 of 60 cells; on
  DeepSeek at full scale N=10 the fact store trades 3.5pp of EX for 7% of tokens. Report it as a
  finding of the EX-as-constraint design, not as a caveat.

Close on the transferable lesson, which is the two-ledger point sharpened by the composition result:
raw and billed tokens are different ledgers, a component can look worthless alone and pay in
combination, and both facts mean a coordination layer must be evaluated on the ledger that binds and
in the configuration it will actually ship in.

Mention the released trace-driven harness in one clause.

## Future work

Four directions, all following directly from stated limitations rather than invented:

1. **Learned schema linking** to lift the 89.6% recall ceiling without hand-written per-database
   patches — the single change that would make pruning deployable beyond the databases tuned here.
2. **Eviction and a cost-aware injection budget** for the fact store: the current 128-entry cap
   silently drops new keys, and the injection tax is uncapped in N.
3. **A paired, seeded composed-vs-parts design** to test the composition result inferentially rather
   than descriptively — the direct answer to the paper's main statistical limitation.
4. **Cross-task prefix persistence**, gated against benchmark leakage, plus **latency measurement**,
   which no current instrumentation captures.

## Constraints

- **Do not mention the cross-model ensemble.** Decided and excluded — different axis, older
  configuration, and it invites "why not do that instead?".
- Do not reintroduce database round-trips as a headline. That result belongs to the cut policies.
- Do not end on limitations. End on the transferable lesson.
- No new numbers here that have not appeared in §6.

---

## DRAFT

**Status: drafted 2026-08-17. Compiles clean. ~0.35pp, under the 0.4 allocation.**

**The three-way answer changed with the full-scale data.** "Reshaping pays only in company" is still
right, but the reason is now sharper: at full scale the fact store *does* save on two models of
three — what makes it conditional is the accuracy cost on the third, not a mixed token sign. Do not
revert to the older "no reliable sign, therefore drop it" framing.

**No number appears here that has not appeared in §6**, per the brief. The cross-model ensemble is
not mentioned, deliberately.

---

```latex
\section{Conclusion and future work}\label{sec:conclusion}

A speculative agent re-sends its prompt on every turn of every replica, and the
identity $N \times T \times \mathrm{price}(P + \bar{H})$ has exactly three
factors to attack. Measuring one method against each, in isolation and composed,
across three models and sixty cells, gives a different answer for each factor.
Repricing is unconditional. Cache-stable structure changes no content byte,
leaves raw consumption unmoved in fourteen of fifteen configurations, and still
removes 18.8--86.0\% of billed input in all fifteen. Shrinking the prefix is
conditional on recall, and that condition is decidable offline before any model
runs. Pruning saves 9.9--19.7\% where every gold table survives and adds
32--156\% where one does not. Reshaping history pays only in company. Alone, the
fact store saves on two models of three at full scale but costs the third 3.5
points of accuracy, while the stack containing it beats the product of its parts
in eleven of fifteen configurations. Accuracy is unmoved in 58 of 60 cells.

What generalises furthest is not any of the three methods but the methodological
result behind them. Raw and
billed tokens are separate ledgers that can move in opposite directions in the
same run, and a policy must be judged on the one that binds. Isolation is
necessary to attribute an effect to a mechanism and insufficient to decide
deployment. The component this study is most critical of in isolation appears in
every configuration that saves most.

Four directions follow directly. Learned schema linking would lift the 89.6\%
recall ceiling without the hand-written per-database rules that currently set
it. The fact store needs eviction and a cost-aware injection budget, being
capped at 128 entries and silently dropping new keys once full, while the
injected digest grows with replica count unchecked. A paired, seeded
composed-versus-parts design would test the composition result inferentially
rather than descriptively, answering this paper's main statistical limitation,
while prefix persistence across tasks, gated against benchmark leakage, would
extend repricing beyond the single-task boundary it currently respects. Latency,
unmeasured here for want of instrumentation, remains the obvious complement to a
study of cost.
```
