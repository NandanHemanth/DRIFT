# Deep sensitivity analysis of the retrieval weights: interpretation

Companion to the generated report `paper/DEEP_SENSITIVITY_BYDATE.md`. That file holds
every table; this one says what they mean. Figures are in `paper/figures_deep/`.

## 0. The short version

Across all 1,000 weightings on two benchmarks and two answer models, the retrieval
weights matter a great deal, but almost entirely through one mechanism and one knob.
They decide whether the correct fact reaches the prompt, and that single quantity
explains 98 percent (MQuAKE-T) and 93 percent (ConvoMem) of the variation in accuracy
across weightings. The knob that moves it is recency: past a recency share of about
0.2, accuracy falls steeply on both benchmarks and for both models. Semantic and
lexical are close substitutes. The published setting, 0.6 / 0.3 / 0.1, is not beaten
by any of the 999 alternatives after correcting for multiple comparisons, sits in the
top 7 to 8 percent on both benchmarks, and is significantly better than roughly half
the grid. The most thesis-relevant result is new: invalidation (P2) achieves the
low-staleness end of the recency trade-off without paying its accuracy cost, so a
well-weighted retriever is not a substitute for a forgetting policy.

## 1. What was run

| Item | Value |
|---|---|
| Grid | 10 x 10 x 10, each weight in 0.1 to 1.0 (1,000 weightings, 841 distinct rankings) |
| Benchmarks | MQuAKE-T (96 questions), ConvoMem (100 questions) |
| Policy answered end to end | P2; P0 measured at the retrieval level |
| Answer models | Llama 3.1 8B (DeepInfra), Qwen3 8B with reasoning (Alibaba), both pinned via OpenRouter |
| Judge | gpt-oss 20B, local; rule grader for unambiguous cases |
| Graded answers | 37,572 (28,377 by rule, 9,195 by judge) |
| Rule vs judge audit | 1,474 of 1,491 agree (98.9 percent) |
| Fact order in prompt | by date (the weights choose which facts, not their order) |
| Retrieval depth | k = 25 |

Scale invariance was checked, not assumed: all 115 groups of proportional weightings
produced identical prompts on both benchmarks.

## 2. Finding 1: accuracy is retrieval times reading

Accuracy factors into two parts: does the correct fact reach the prompt (gold
support), and given that it does, does the model use it.

| | P(correct given gold in prompt) | P(correct given gold absent) | P(stale given old value in prompt) | P(stale given old value absent) |
|---|---|---|---|---|
| MQuAKE-T, Llama 3.1 8B | 0.862 | 0.000 | 0.158 | 0.000 |
| MQuAKE-T, Qwen3 8B | 0.969 | 0.000 | 0.084 | 0.000 |
| ConvoMem, Llama 3.1 8B | 0.479 | 0.054 | 0.322 | 0.000 |
| ConvoMem, Qwen3 8B | 0.570 | 0.080 | 0.333 | 0.000 |

Three consequences.

1. **The weights act only through the first factor.** Across weightings, gold support
   correlates with accuracy at r = 0.99 on MQuAKE-T and 0.96 on ConvoMem (figure
   `accuracy_vs_gold_support.png`).
2. **No leakage from pretraining on MQuAKE-T.** When the correct fact is absent, neither
   model answers correctly (0.000), so these results measure memory, not what the model
   already knew. ConvoMem's small nonzero value is most likely the needle-matching
   limit on sentence-form gold answers, not recall.
3. **Staleness is fully mediated by retrieval.** A model never gives the outdated value
   unless that value is in the prompt. Keeping outdated facts out of the prompt is
   therefore sufficient to prevent stale answers, which is exactly the lever P2 pulls.

## 3. Finding 2: recency is the knob, and it has a cliff

Share of variation across the 1,000 weightings explained by each weight on its own:

| Outcome | Semantic | Lexical | Recency |
|---|---|---|---|
| MQuAKE-T accuracy | 20% | 14% | **50%** |
| ConvoMem accuracy | 34% | 5% | **48%** |
| MQuAKE-T gold support | 19% | 16% | **54%** |
| ConvoMem gold support | 29% | 5% | **60%** |

Interactions are small (at most 6 percent for accuracy), so the weights act mostly
independently.

Accuracy by recency share of the total weight:

| Recency share | MQuAKE-T | ConvoMem |
|---|---|---|
| up to 0.1 | 0.890 | 0.317 |
| 0.1 to 0.2 | 0.902 | 0.307 |
| 0.2 to 0.3 | 0.890 | 0.295 |
| 0.3 to 0.4 | 0.809 | 0.264 |
| 0.4 to 0.5 | 0.699 | 0.214 |
| 0.5 to 0.6 | 0.623 | 0.179 |
| 0.7 and above | 0.470 | 0.137 |

The mechanism is visible in the gold-support column: recency favours whatever arrived
last, which is often not the fact the question asks about. On MQuAKE-T, raising the
recency weight alone from 0.1 to 1.0 (others at 0.3 and 0.6) drops accuracy from
0.911 to 0.609, with the drop significant from 0.5 upward (p = 0.003 and below).

## 4. Finding 3: semantic and lexical are substitutes, except in dialogue

Holding recency share at or below 0.2 and varying the semantic-to-lexical balance:

| Semantic / (semantic + lexical) | MQuAKE-T | ConvoMem |
|---|---|---|
| below 0.35 | 0.906 | 0.276 |
| 0.35 to 0.50 | 0.894 | 0.299 |
| 0.50 to 0.65 | 0.897 | 0.319 |
| 0.65 to 0.80 | 0.903 | 0.335 |
| above 0.80 | 0.902 | 0.346 |

On MQuAKE-T the balance does not matter: templated facts share their wording with the
question, so both signals find them. On ConvoMem, where the same fact is phrased in
different words across a conversation, leaning semantic is worth about 7 points. That
is a mechanism, not a tuning artefact: lexical matching fails exactly when phrasing
varies.

## 5. Finding 4: the published setting survives the full search

| | MQuAKE-T | ConvoMem |
|---|---|---|
| Accuracy at 0.6 / 0.3 / 0.1 | 0.911 | 0.320 |
| Best of 1,000 | 0.938 at 0.9/0.1/0.2 | 0.370 at 0.8/0.1/0.1 |
| Rank of published | 66 of 1,000 | 80 of 1,000 |
| Alternatives significantly better (uncorrected) | 0 | 1 |
| Alternatives significantly better (Holm-corrected) | **0** | **0** |
| Alternatives significantly worse | 560 | 467 |

The apparent best is inflated by selection. Picking the best weighting on half the
questions and scoring it on the other half loses about 5 points on both benchmarks
(optimism +0.050 and +0.048). On MQuAKE-T the picked weighting beats the published one
on unseen questions in only 21 percent of splits. On ConvoMem it does so in 68 percent,
by an average of 1.4 points, which is a real but small edge consistent with Finding 3.

What this licenses: **0.6 / 0.3 / 0.1 is defensible, not optimal.** It lies inside the
good region, no alternative beats it after correction, and the thesis conclusions do
not depend on it.

## 6. Finding 5: invalidation does what recency tries to do, without the cost

This is the finding that matters most for the thesis (figure
`p2_vs_recency_frontier.png`).

Recency weighting is the retriever's own tool against outdated facts. On MQuAKE-T,
averaged over the other two weights:

| Recency weight | P0 gold support | P0 stale exposure | P2 gold support | P2 stale exposure |
|---|---|---|---|---|
| 0.1 | 1.00 | 0.99 | 1.00 | 0.42 |
| 0.5 | 0.88 | 0.64 | 0.88 | 0.26 |
| 1.0 | 0.71 | 0.37 | 0.71 | 0.16 |

To bring outdated-value exposure down to the level P2 reaches at recency 0.1 (0.42),
a policy without invalidation needs the recency weight near its maximum, which costs
it 26 to 29 points of gold support. P2 gets that exposure with gold support at 1.00.
On MQuAKE-T, P2's curve lies strictly above P0's everywhere: at every level of
staleness, P2 keeps more correct facts in the prompt.

Two sentences for the thesis: *a retriever cannot tune its way out of staleness,
because the only weight that reduces outdated facts also removes the needed ones.
Contradiction invalidation removes the outdated fact specifically, which is why it
dominates any recency weighting.*

On ConvoMem the two curves cross. P2 still lowers exposure, but its false
invalidations (Section 9) also remove some correct facts, so it no longer dominates.
That is the same boundary condition identified earlier, now visible across the whole
grid.

## 7. Finding 6: what the answer model changes, and what it does not

| | Llama 3.1 8B | Qwen3 8B (reasoning) |
|---|---|---|
| Uses the correct fact when present (MQuAKE-T) | 0.862 | 0.969 |
| Repeats the outdated value when present (MQuAKE-T) | 0.158 | 0.084 |
| Spread of accuracy within the good region (MQuAKE-T) | 0.026 | 0.009 |
| Rank agreement across weightings (Spearman) | 0.91 on MQuAKE-T, 0.76 on ConvoMem | |

The reasoning model is a better reader: it uses the correct fact more often, halves
the rate at which it repeats an outdated fact on MQuAKE-T, and is three times less
sensitive to the exact weighting once recency is low. But both models collapse
identically when the correct fact is missing, and both repeat the outdated value about
a third of the time on ConvoMem. **A stronger model narrows the effect of the weights;
it does not remove the need to get the right fact into the prompt, or the outdated one
out of it.** This answers the committee's frontier-model question with evidence
rather than argument: stronger readers help, retrieval and forgetting remain the
bottleneck.

## 8. Finding 7: the good weightings transfer

| | Value |
|---|---|
| Spearman of accuracy across weightings, MQuAKE-T vs ConvoMem | 0.89 |
| Spearman of gold support and of stale exposure | 0.97 and 0.97 |
| Best on MQuAKE-T, rank on ConvoMem | 15 of 1,000 |
| Best on ConvoMem, rank on MQuAKE-T | 168 of 1,000 |

The region transfers; the exact argmax does not. That is the pattern expected when
there is a broad plateau and noise picks the peak.

## 9. Finding 8: the free retrieval sweep is now validated

Gold support predicts accuracy at r = 0.99 and 0.96, and stale exposure predicts
staleness at r = 0.83 and 0.80. The earlier model-free sweep, which covered
FactConsolidation too, can therefore be read as a reliable forecast of end-to-end
behaviour, not only as a retrieval measurement.

## 10. Finding 9: the natural-dialogue boundary holds at every weighting

On ConvoMem, P2 has lower stale exposure than P0 at 993 of 1,000 weightings and lower
gold support at 999 of 1,000. The loss comes from false invalidations (lists of
meetings treated as single-valued), not from the weights, which is why it appears
everywhere on the grid. Both models also repeat the outdated value about one time in
three when it is present, against one in six to twelve on MQuAKE-T.

## 11. What this does to the hypotheses

| Claim | Before | After this analysis |
|---|---|---|
| P2's advantage does not depend on the retrieval weights | Supported at retrieval level | Supported end to end, all 1,000 weightings |
| The chosen weighting is justified | Argued | Not beaten after correction; top 7 to 8 percent on both benchmarks |
| Invalidation is needed beyond good retrieval | Implicit | **New, direct evidence**: recency cannot reach P2's staleness without losing 26 to 29 points of gold support |
| Results carry over to stronger models | Open committee question | Stronger reader helps; bottleneck stays in retrieval and forgetting |
| Retrieval measurements predict accuracy | Assumed | r = 0.99 and 0.96 |
| P2 works in natural dialogue | Partly | Partly, same boundary, now shown to be independent of the weights |

## 12. What to use moving forward

**For the thesis: keep 0.6 / 0.3 / 0.1.** It was fixed before these results, it
survives a full search, and changing it now would be selecting on the test data.
Report the region, not a point.

**The robust region**, supported on both benchmarks and both models:

1. Recency share at most 0.2.
2. Semantic share at least equal to lexical, higher for conversational memory.

Inside it, MQuAKE-T accuracy averages 0.899 (worst 0.865) and ConvoMem 0.326 (worst
0.290), against 0.772 and 0.246 outside.

**If a new default is wanted for a deployment**, do not take the argmax. Pre-register one
candidate from the region and test it on held-out data. FactConsolidation was not in
this run and is the natural held-out set. A single candidate such as 0.8 / 0.1 / 0.2,
the best on both benchmarks combined, against 0.6 / 0.3 / 0.1 costs about 200 answers
per model.

**By scenario:**

| Deployment | Recommended weighting | Why |
|---|---|---|
| Memory with contradiction invalidation (P2-style) | recency share about 0.1 | Invalidation already handles outdated facts; recency only costs recall |
| Memory without invalidation, staleness costly | recency share 0.2 to 0.3, or add invalidation | Recency is the only defence but costs recall steeply past 0.3 |
| Conversational, paraphrase-heavy memory | semantic share 0.6 to 0.8, lexical low | Section 4: semantic worth about 7 points on ConvoMem |
| Templated, entity-keyed facts | any sem / lex balance | Section 4: balance does not matter on MQuAKE-T |
| Small or weak answer model | stay deep inside the region | Weaker readers are three times more sensitive to the exact weighting |
| Strong reasoning answer model | region is enough; point choice matters little | Spread within region 0.009 |
| Prompt-cost constrained | ignore the weights for cost | They move estimated prompt size by under 50 tokens |

## 13. Threats to validity

1. **Fact order.** Facts were listed by date, so this measures which facts the weights
   select, not ranking-order effects. The thesis pipeline lists by rank. Every retrieval
   quantity is identical under both orders by construction; only the reader could
   respond differently to order, which step 2 in Section 14 checks.
2. **Two 8B models on hosted quantisations.** Different hosts could shift absolute
   numbers slightly; rankings across weightings agree between models (0.91, 0.76).
3. **Sample size.** 96 and 100 questions. Every comparison is paired and corrected for
   multiple testing where a "best" is claimed.
4. **P0 answered only at retrieval level.** Finding 5 uses retrieval quantities, which
   Section 9 shows predict answers closely.
5. **ConvoMem measurement.** Sentence-form gold answers make the gold-support needle
   approximate; its direction and ranking are reliable, its absolute level less so.
6. **Grading.** The rule grader agreed with the judge on 98.9 percent of audited cases.
7. **k fixed at 25.** Depth was swept separately in the free analysis.

## 14. Next steps

1. Pre-registered held-out test on FactConsolidation: 0.8 / 0.1 / 0.2 against
   0.6 / 0.3 / 0.1, both models, clean prompt.
2. A small ranked-order confirmation: answer the robust region in rank order on
   MQuAKE-T to show order does not change the conclusion.
3. End-to-end P0 at a handful of recency values to turn Finding 5 from a retrieval
   result into an accuracy result.
