# Presentation video: script, deck and OBS setup

**Accompanying:** *Prompt Cost Optimisation for Speculative Parallelism in Text-to-SQL: Schema Pruning, a Semantic Fact Store, and Cache-Stable Structure* (v9)

**Pasha Gorenkin** · MSc Project 2025/26 · Queen Mary University of London · deadline 19 August 2026

---

## What the guide requires (§4.7.1)

| Requirement | Where it is met |
|---|---|
| 10 minutes, ±10%, so 9:00 to 11:00 | timing plan below totals 10:00 |
| **You must appear on camera.** Voice-over alone fails, and a fail here blocks the viva | the webcam source is on screen for the entire recording |
| **Recorded at normal speed.** Sped-up video loses marks | the demo is pre-recorded and trimmed between commands, never accelerated |
| Statement of the problem investigated | segment 2 |
| Description of the methods used | segments 3 and 4 |
| **Demonstration of practical/implementation work** | segment 5, a real terminal recording |
| Presentation of results, positive **and negative** | segments 6 and 7 |
| Summary of the work | segment 8 |

The negative-results requirement is easy to under-serve and this project has unusually good material for it, so segment 7 is dedicated to it rather than being folded into the results.

---

## The deck

[slides_v9.html](thesis/paper%20drafts/slides_v9.html) — 16 slides, open it in Chrome and press <kbd>F11</kbd>.

It is built for exactly this setup, which is to say a slide behind you at all times with the camera composited over the corner. **The bottom-right 480 × 270 region is reserved on every single slide** and nothing is ever laid out inside it. Press <kbd>g</kbd> to outline that zone while you size and position the OBS camera source, then press <kbd>g</kbd> again to hide it before you record.

| Key | Does |
|---|---|
| <kbd>→</kbd> <kbd>space</kbd> <kbd>click</kbd> | next slide |
| <kbd>←</kbd> | previous |
| <kbd>g</kbd> | toggle the camera-zone outline |
| <kbd>n</kbd> | toggle speaker notes, which carry the timing cue for each slide |
| <kbd>Home</kbd> / <kbd>End</kbd> | first / last |

Notes are off by default and would be captured if left on, so use them in rehearsal only. The deck remembers its position across a reload, and `?s=8` opens straight at slide 8.

It is a fixed 1920 × 1080 stage scaled to the window, so a mis-sized browser window shrinks the whole slide rather than reflowing the text mid-recording. Everything is local, with no fonts or scripts fetched from anywhere, so it cannot break on a bad connection.

### Slide map

| # | Slide | Segment |
|---:|---|---|
| 1 | Title | 1 |
| 2 | How the agent works, the ReAct loop | 1 |
| 3 | The problem, `fig6_scaling` | 2 |
| 4 | Duplicated SQL, `fig7_redundancy` | 2, **cut this one first if you run long** |
| 5 | The cost identity and prompt anatomy, `fig1_anatomy` | 3 |
| 6 | Three methods, one per factor | 4 |
| 7 | How the evidence is recorded, JSONL traces | 5 |
| 8 | Demonstration title and command | 5 |
| 9 | A smaller schema, `fig8_recall_split` | 6, beat 1 |
| 10 | The fact store, `fig10_factstore` | 6, beat 2 |
| 11 | Cache holds by turn, `fig2_cached_by_turn` | 6, beat 3 |
| 12 | The price-schedule caveat, `fig9_billed_by_model` | 6, beat 3 |
| 13 | Two ledgers, `fig4_two_ledger` | 6, beat 4 |
| 14 | Composition, `fig5_additivity` | 6, beat 5 |
| 15 | What did not work | 7 |
| 16 | Summary | 8 |

### Regenerating the figures

```bash
uv run python scripts/make_v8_figures.py --slides    # the eight charts
uv run python scripts/export_tikz_figures.py         # Fig. 1, lifted from the paper
```

The `--slides` variants are re-rendered at presentation scale rather than upscaled, so type, line weights and markers are all set large instead of being blown up along with the pixels. `export_tikz_figures.py` lifts the `tikzpicture` out of the paper source verbatim and compiles it standalone, so the slide and the paper cannot drift apart.

Seven of the eight charts appear nowhere in the paper. Only `fig4_two_ledger` is in it, as Fig. 3. They exist because the 8-page limit cut them, which makes this video the only place your examiners will see them.

**Two old images are superseded and must not be used.** `schema_prune_offline_by_db.png` is the two-database version, replaced by `fig8_recall_split.png`. `baseline_explore_redundancy.png` shows 46–51% rising to 80–88% against the paper's 39–49% and 76–89%, because it was drawn from a different task set. It is replaced by `fig7_redundancy.png`, which reads the same baselines the results matrix does.

---

## OBS setup

**Two scenes, one switch.** Everything hangs off that.

**Scene A, "Talk".** Slides behind you for every segment except the demo.
1. *Window Capture* on Chrome in fullscreen. Prefer window capture over display capture so a notification cannot land in the recording.
2. *Video Capture Device* for the webcam, sized to **480 × 270** and positioned **48 px from the right and bottom edges** at 1080p output. Press <kbd>g</kbd> in the deck and drag the source until it fills the dashed outline exactly.

**Scene B, "Demo".** Same webcam source in the same corner, with the terminal behind it instead of Chrome. Keep the camera identical between scenes, since a webcam that jumps position at the scene switch is the one thing that reads as amateur.

**Settings.**
- Base and output resolution 1920 × 1080, 30fps. There is no motion here that needs 60.
- Record in MP4 or MKV rather than FLV. If you use MKV, remux before uploading.
- Test the audio level for thirty seconds and play it back before recording ten minutes.

**Two things worth doing before the real take.**
- Put your terminal font up to roughly 18pt. Default terminal type is unreadable once the video is compressed, and the demo is the segment most likely to be squinted at.
- Keep the terminal's own output out of the bottom-right corner, or move the camera to the bottom-left for scene B only. Long command output scrolls into that corner and will end up behind your head.

---

## Timing plan

| # | Segment | Slides | Runs | Ends |
|---|---|---|---|---|
| 1 | Who and what, and how the agent works | 1, 2 | 1:05 | 1:05 |
| 2 | The problem | 3, 4 | 1:05 | 2:10 |
| 3 | The cost identity | 5 | 0:45 | 2:55 |
| 4 | Three methods | 6 | 1:10 | 4:05 |
| 5 | Evidence and demonstration | 7, 8, then scene B | 1:40 | 5:45 |
| 6 | Results | 9–14 | 2:40 | 8:25 |
| 7 | What did not work | 15 | 0:50 | 9:15 |
| 8 | Summary | 16 | 0:45 | 10:00 |

---

## Script

Spoken word counts assume roughly 140 words per minute. Read it slightly slower than feels natural, since the requirement penalises speeding up and there is a full minute of headroom before the upper limit.

You are on camera throughout, so there is no "look up now" cue. What matters instead is that you look at the **camera** rather than at the slide when you deliver the lines marked below.

---

### 1. Who and what · 0:00 to 1:05 · **slide 1, then 2**

> I'm Pasha Gorenkin, and this is my MSc project on the cost of running language model agents in parallel.
>
> The setting is text-to-SQL. You give an agent a database and a question in English, and it works out the query. No single attempt is reliable, so the standard fix is to run many at once and pick the best. That works, and it is extremely expensive, and almost all of the expense is waste.

*(advance to slide 2)*

> Here is what one of those attempts actually does. It gets a prompt holding the system instructions, the database schema, and the question. The model reasons and calls one of two tools. \`execute_sql\` runs an exploratory probe and the result is appended to the conversation. \`submit_sql\` ends the episode with a final query. Up to fifteen turns of that. Then N replicas run the same task, a coordinator takes whichever reaches an executable submission in fewest turns, and the answer counts as correct only if it returns the same rows as the gold query.
>
> Hold on to one detail: the whole conversation is re-sent on every turn. That is where the money goes.

*(~200 words across the two slides. **Look at the camera for the first paragraph**, then let slide 2 carry the loop. The last line is the hinge of the whole talk, so slow down on it.)*

---

### 2. The problem · 1:05 to 2:10 · **slide 3, then 4**

> Here is the problem in one picture. As replicas go from three to twenty-five, token cost rises from about three times a single trajectory to nearly thirty times. Accuracy over the same range moves by at most eight points, which is inside the run-to-run noise of the subset it is measured on. So you pay an order of magnitude and get nothing you can distinguish from chance.

*(advance to slide 4)*

> The obvious explanation is duplicated work, and there is plenty of it. At twenty-five replicas a task issues about eighty-two exploratory queries that collapse to sixteen distinct statements. On one question a single statement is issued a hundred and eighty-one times, which is roughly seven times per replica, so this is not only replicas repeating each other but replicas repeating themselves. That was where I started, with a shared cache that returns a peer's result instead of hitting the database again.
>
> It worked, and it barely touched the bill. That failure is what the project is actually about.

*(~175 words. Let slide 3 sit for a beat before you speak. If the timed pass runs long, cut slide 4 and fold its last two sentences into slide 3.)*

---

### 3. The cost identity · 2:10 to 2:55 · **slide 5**

> The reason is that chat APIs are stateless. Every turn re-sends the entire conversation, so the cost is not what the agent asks the database, it is what it re-sends to the model. Caching a query just frees turn budget the replica spends exploring further, and every extra turn re-bills the whole prompt.
>
> Written down, billed input for one task is replicas, times turns, times the price of a static prefix plus an accumulated history. That identity is the spine of the paper, because it has exactly three factors you can attack. You can shrink the prefix. You can trade history against turns. Or you can change what the same bytes cost. I built one method for each, which makes the set complete over the identity rather than a selection from a longer list.

*(~140 words. The diagram already labels each method against the term it attacks, so let it do that work rather than describing it twice.)*

---

### 4. Three methods · 2:55 to 4:05 · **slide 6**

> **Schema pruning** shrinks the prefix. It scores every table against the question, expands the selection along foreign keys, and sends only what survives. The critical part is the safety rail. My first version was a keyword heuristic and it made things worse, because dropping a needed table sends the agent exploring blind and costs more than it saved. The finished version always falls back to the full schema at execution time if a table turns out to be missing.
>
> **The semantic fact store** reshapes history. After every exploration a rule-based extractor distils what happened into short facts: which joins work, what an error was, how many rows came back. Those are shared across the replicas of one task, ranked by how many found them independently, and injected as a short digest. Extraction uses no model calls, so it costs nothing but the injected bytes, and it is advisory.
>
> **Cache-stable structure** changes the price without changing anything else. Providers discount input they have seen before, but only if the prefix is byte-identical and the prompt grows by appending. My agent loop violated both, so this was never a flag I could switch on. It had to be rebuilt into a frozen prefix, an append-only history, and a volatile trailer, and byte stability is now held in place by a unit test rather than by care.

*(~215 words, the densest segment.)*

---

### 5. Evidence and demonstration · 4:05 to 5:45 · **slide 7, then 8, then OBS scene B**

> First, where the results come from. Every run writes one append-only JSONL file per replica. Each turn records its prompt, completion and cached token counts, which is where both cost ledgers come from, and each query is tagged as an exploratory probe or a final answer, which is what makes duplication measurable. Nothing is aggregated at write time, so every table and figure is a script over these files.

*(advance to slide 8)*

> Let me show it running. This is the harness on one BIRD question with three replicas and all three methods enabled.

**Record this in advance and trim the waiting, but never speed up the playback.** Three beats:

1. **Pruning, roughly 25 seconds.** Show the full schema for the database, then the pruned selection for question 1317, with the gold tables highlighted. The paper's appendix worked example uses this question, so it lines up with what the examiners have read.
2. **The fact store, roughly 20 seconds.** Show the peer digest served to one replica, the appendix example on question 1350. Point out that these facts were found by other replicas, not this one.
3. **The cache, roughly 35 seconds.** The money shot. Run the same question twice and put the per-turn cached-token counts side by side. Baseline stays at zero. Cache-stable climbs past fifty per cent on GPT-4o mini by the first turn and keeps climbing.

```bash
uv run python scripts/run_parallel_batch.py --limit 1 --replicas 3 \
    --model gpt-4o-mini \
    --schema-pruning --schema-pruning-mode hybrid --semantic-store --prompt-cache
```

The header now lists only the three methods the paper evaluates. The cut policies print nothing unless one is actually switched on, so nothing appears on screen that a viewer could ask about and you would have to disown.

> Same question, same model, same answer. The only difference is how the prompt is laid out, and the second run bills a fraction of the first.

*(~180 spoken words across both slides. Let the terminal carry the demo itself. Silence over a running command is fine and reads as confidence. Switch back to scene A and slide 9 as you say the closing line.)*

---

### 6. Results · 5:45 to 8:25 · **slides 9 to 14, one per beat**

**Beat 1, slide 9, ~35s**

> Pruning saves, but conditionally. Where every gold table survives the prune it removes ten to twenty per cent of raw tokens, on every model at both replica counts, all six intervals excluding zero. Where a table is lost, consumption rises by thirty-two to a hundred and fifty-six per cent. My pruner keeps every gold table on 89.6% of the full split, and at that rate the two regimes very nearly cancel. So the binding constraint is recall, not aggressiveness, and you can check which regime a task falls into offline, before calling a model.

**Beat 2, slide 10, ~35s**

> The fact store is the honest negative. On its own it has no reliable sign: on fifty tasks it saves seventeen per cent on one model and costs twenty on another, and the sign is not even stable across scales, since the model that appeared to pay most instead saves seven per cent over all five hundred. The lower panel is the obvious explanation failing. Injection load barely moves between scales while the sign flips, so the tax bounds the saving without predicting it. Accuracy improves nowhere, and on that model it drops three and a half points.

**Beat 3, slide 11, ~25s**

> Repricing is the unconditional win. Cache-stable structure changes no content byte, leaves raw consumption statistically unmoved in fourteen of fifteen configurations, and still removes between eighteen and eighty-six per cent of billed input in all fifteen. This chart is the mechanism working, cached share of input climbing turn on turn.

**Beat 3 continued, slide 12, ~20s**

> I will be honest about the size, though. The mechanism is identical across these three groups, so the spread between them is not the method working harder on one model. It is the provider's cached rate: fifty per cent of standard on GPT, ten on Gemini, two on DeepSeek.

**Beat 4, slide 13, ~40s**

> That forces the paper's main methodological point. Raw tokens and billed tokens are separate ledgers. Every point here is one of sixty measured cells, raw change against billed change, and the diagonal is where the two agree. Everything below it changed the bill more than the consumption. The annotated point is the sharpest case: raw tokens up ten per cent, billed down nearly nineteen, both significant, same run. A study reporting only raw tokens would have called my most valuable method useless.

**Beat 5, slide 14, ~45s**

> And the result I did not expect. On the evidence you just saw, you delete the fact store. But compose all three and on eleven of fifteen configurations the stack saves more than its own parts predict. The annotated point is the extreme case: on DeepSeek at three replicas the isolated arms predict tokens going up more than eight per cent, and the composed stack instead saves nearly twenty-four. Isolation is what lets you attribute an effect to a mechanism. It is not what tells you whether to deploy it.

*(~470 words total. Beat 5 is the most interesting thing in the project, so pause after "you delete it".)*

---

### 7. What did not work · 8:25 to 9:15 · **slide 15**

> Three negatives, because they matter as much as the savings.
>
> First, nothing here bought accuracy. Across all sixty cells, fifty-eight accuracy intervals contain zero. That is the constraint being met, not a disappointment, but I chased apparent accuracy gains for months and every one of them died under scrutiny.
>
> Second, there is a real accuracy cost, and I report it rather than burying it. On one model at full scale the fact store trades three and a half points of accuracy for a seven per cent token saving. Two intervals miss zero, and they share a model, a cell and a mechanism, so I do not treat that as coincidence.
>
> Third, my first pruner increased token cost rather than reducing it, and my shared cache removed most database traffic while leaving the bill unchanged. Both are in the paper.

*(~150 words. **Look at the camera for this segment**, not at the slide. The slide is a prompt list and the examiners can read it. Owning the negatives while looking at them is far more convincing than narrating them.)*

---

### 8. Summary · 9:15 to 10:00 · **slide 16**

> To summarise. Prompt cost in a speculative agent workload decomposes into three factors, and each one takes a different kind of method. Repricing is unconditional and the largest effect I measured. Shrinking the prefix is conditional on a recall property you can check in advance. Reshaping history pays only in company, and would have been thrown away by an ablation that stopped at isolation.
>
> Sixty cells, three models, two scales, every comparison carrying a paired bootstrap interval, accuracy held as a constraint throughout. All of it regenerates from execution traces by script, which is what made it survivable when a provider silently replaced one of my three models halfway through.
>
> Thank you. I am happy to take questions in the viva.

*(~130 words. **Camera, not slide.** Hold for a beat after the last word before you stop the recording, and do not trail off or start tidying up while it is still rolling.)*

---

## Production notes

- **Record segments 1, 7 and 8 first**, while you are freshest. They are the ones you deliver to the camera and they carry the most weight with an examiner.
- **Pre-record the demo separately** and cut the dead time between commands. Trimming waiting is not the same as speeding up playback, and the guide only prohibits the second.
- **Read this before recording: the script no longer fits at a slow pace.** It is 1,549 spoken words. At a brisk 150 words per minute that is 10.3 minutes, at 145 it is 10.7, and at a measured 130 it is 11.9. Add roughly 35 seconds of silence over the demo and **only a pace of about 150 stays under the 11:00 ceiling.** Two ways out, and you should pick one deliberately rather than discover it in the edit:
  - **Speak at 150 and keep everything.** Time a real pass first. If you land at 10:45 or under, you are fine.
  - **Cut slide 4 and its paragraph**, the duplicated-SQL chart, worth about 110 words and 45 seconds. That brings a 130-word-per-minute read to 10:50. The 181× statistic is the loss, so fold "one statement issued a hundred and eighty-one times on a single question" into slide 3 as a single clause if you take this route.
  
  After slide 4, the next safest cut is slide 12, the price-schedule caveat, but only if you say the caveat aloud over slide 11 instead. Do not cut segment 7.
- **Keep every on-screen number identical to the submitted paper.** The examiners will have read it, and a mismatch invites exactly the question you do not want.
- **Press <kbd>g</kbd> twice before you hit record.** Once to check the camera still fills the zone, once to hide the outline. It is the easiest thing in this whole setup to leave switched on by accident.
