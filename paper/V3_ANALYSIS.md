# DRIFT v3: deep analysis of the final campaign

This document explains every result of the v3 campaign, how it was produced, why each choice was made, and what it supports. It is written for your understanding and for defending the work. Write the thesis chapters in your own words from it.

Every number here is recomputed from the saved per-question records by three scripts. Nothing in them calls a model.

| Script | Produces |
|---|---|
| `python -m analysis.v3_compact` | `artifacts/v3_compact/` (re-graded records, graphs without embeddings) |
| `python -m analysis.v3_analysis` | `artifacts/v3_analysis.json`, `paper/tables_v3/*.csv` |
| `python -m analysis.v3_figures` | `paper/figures_v3/V01` to `V10` (PNG and PDF) |

Conventions: every rate is a percentage. "± x" is one sample standard deviation over the three runs. A difference between two percentages is written as a plain difference of percentages (for example 95.2% against 91.3%), and the paired tables give it with its 95% interval.

---

## 0. Status of the campaign

| Study | Cells planned | Cells present | Answers graded |
|---|---|---|---|
| Main matrix, run 1 | 105 | 105 | 10,360 |
| Main matrix, run 2 | 105 | 105 | 10,360 |
| Main matrix, run 3 | 105 | 105 | 10,360 |
| RQ4, normalised matching (3 topologies × 6 policies × 3 benchmarks) | 54 | 54 | all RQ4 |
| RQ4, exact and LLM matching (shared, P0 and P2) | 12 | 12 | included above |
| Follow-up: matching (exact, LLM) | 30 | 30 | 2,960 |
| Follow-up: retrieval weighting (4 settings) | 60 | 60 | 5,920 |
| Follow-up: grace with history questions | 3 benchmarks × 9 graces × 5 models | complete | |

Eight cells failed in the first pass (provider errors inside the cell) and were re-run on 10 November with the same commands. The re-run reused every cached response, so only the missing cells were billed. The campaign is now complete.

Billed cost recorded in the result cells is $44.78. This counts only calls that were not already in the cache. The preflight extractions, the pilot and the grace study are billed separately.

---

## 1. What DRIFT is, fundamentally

**The problem.** An agent with long-term memory stores facts as it hears them. When a fact changes ("my manager is Ashley", later "I now report to Daniel"), both versions stay in memory. Because they differ in one word, a retriever ranks them almost equally, and both reach the answer model. The model must then work out which one is current. A *stale answer* is one that asserts the old value.

**The idea.** Decide, in the memory and before the model reads anything, which facts the model should no longer see. That decision is a *forgetting policy*. DRIFT is a framework that holds everything else fixed so that the policy is the only thing that changes:

- the store (a bitemporal knowledge graph);
- extraction (DeepSeek V4.1 Flash, previous 4 lines as context);
- contradiction detection;
- retrieval (0.6 semantic + 0.3 lexical + 0.1 recency, top 25);
- the answer prompt;
- grading (two fixed rules, then a DeepSeek judge).

**Three actions a policy can take**, and closing is not one of them:

| Action | Where | Reversible | Example |
|---|---|---|---|
| Refuse | at write (`on_write`) | no, the fact never enters | P3 rejects near-duplicates |
| Hide | at retrieval (`on_retrieve`) | yes | P2 hides closed facts |
| Delete | after a session (`after_session`) | soft: `active = False`, kept for audit | P1 by age, P2 after grace, P4 by LLM, P5 by vote |

*Closing* is what the store does on a contradiction: it sets `t_invalid_at` on the old fact. Nothing is hidden or deleted by closing. Under P0 a closed fact is still shown.

**Why bitemporal.** Each fact records when it was true in the world (valid time) and when the agent learned it (transaction time), following the database literature (Snodgrass and Ahn, 1985; Jensen et al., 1998; SQL:2011, Kulkarni and Michels, 2012). This lets the memory answer three different questions: what is true now, what was true on a date, and what the agent believed on a date. Zep uses the same model (Rasmussen et al., 2025). DRIFT does not claim the data model; it claims the controlled comparison of what to do with closed facts.

---

## 2. The pipeline: what ran, how, and why

| Stage | What it does | Setting in v3 | Why this setting | Reference |
|---|---|---|---|---|
| Sessions | Each benchmark is converted into time-stamped sessions of "Speaker: line" text and questions asked at the end | 3 benchmarks | Each records the old value, so staleness can be scored | Zhong et al. 2023; Hu et al. 2026; Pakhomov et al. 2025 |
| Extraction | LLM turns each session into (subject, relation, object, text) facts; a regex pass adds functional relations; retry at 4,096 tokens if no JSON | DeepSeek V4.1 Flash, reasoning off, temperature 0, **previous 4 lines as context only** | Context resolves references ("let's do Saturday instead"); Zep uses exactly 4 previous messages | Rasmussen et al. 2025, Sec. 2.2.1 |
| Write hook | Policy may refuse the fact | only P3 uses it | | |
| Contradiction | Same subject and functional relation, new object: old fact's validity is closed | normalised matching (case, articles, filler, either direction); LLM matching as a follow-up | Non-destructive, like Zep's invalid-at | Rasmussen et al. 2025 |
| Maintenance hook | Policy may delete facts after each session | P1, P2, P4, P5 | | |
| Retrieval | score = 0.6 cosine + 0.3 word overlap + 0.1 recency; top 25 | nomic-embed-text, local | Hybrid scoring is standard (Generative Agents; Zep combines cosine, BM25 and graph search); weights chosen by a 1,000-point sweep and confirmed below (V09) | Park et al. 2023; Nussbaum et al. 2024; Robertson and Zaragoza 2009; Cormack et al. 2009 |
| Retrieval hook | Policy may hide or reorder the 25 facts | P2 hides closed facts | | |
| Answer | The model sees the 25 facts with their valid-start dates; the prompt does not say how to resolve conflicts | 5 answer models, temperature 0 | Conflict resolution must come from the policy, not the prompt | |
| Grading | (1) a refusal is incorrect; (2) the gold string verbatim is correct; otherwise the DeepSeek judge decides | DeepSeek V4.1 Flash judge | LLM judges are standard (LongMemEval, Zep, STALE); validated at 96.0% agreement, κ = 0.919 against Claude Sonnet 5.5 on 198 answers | Wu et al. 2025; Chao et al. 2026; Cohen 1960 |

**Models.** GPT-6.1 Sol and Claude Sonnet 5.5 (frontier), Gemini 3.8 Flash (mid-tier), Qwen3 14B and Llama 3.1 8B (small). Each is pinned to one provider through OpenRouter with no fallback. DeepSeek V4.1 Flash does extraction, judging and P4's review, so the answer models never grade themselves.

**Reproducibility.** Temperature 0 everywhere. Every call is cached by a hash of provider, model, prompt, temperature and max tokens. A replicate tag (0, 2, 3) makes runs 2 and 3 remake every call, including extraction and judging. Each results folder holds a run record (config, git commit, cost).

**Grading audit.** The two fixed rules overrode the judge on 0.0% of answers in v3, so every grade equals the judge's grade.

---

## 3. The policies, and why each should or should not work (theory)

Let a *slot* be a (subject, relation) pair whose value changes from o to o\*. After the change, a correct memory shows o\* and not o.

Two properties of a policy's end state:

- **Complete**: every superseded value o is no longer visible.
- **Sound**: every current value o\* is still visible.

These are DRIFT's own definitions. They are the precision and recall of forgetting decisions: soundness fails when a policy forgets something true, and completeness fails when it keeps something false.

**Staleness decomposes.** A model can only repeat the old value if it sees it:

P(stale) ≈ P(old value in prompt) × P(model repeats it | it is in the prompt)

The first factor is *exposure*, which the policy controls. The second is the *reading error*, which belongs to the model. This decomposition is the core of the thesis: a policy acts on the first factor, so it helps most when the second is large, which is the case for small models.

Check against data (policy average, MQuAKE-T): P0 exposure 90.6% × reading error 7.6% = 6.9%, observed stale 6.7%. P2: 9.4% × 36.0% = 3.4%, observed 3.3%. The decomposition holds.

What each policy should do, from its mechanism alone:

| Policy | Mechanism | Sound? | Complete? | Prediction |
|---|---|---|---|---|
| NOMEM | retrieval returns nothing | n/a | n/a | floor: near 0% accuracy and trivially near 0% stale |
| P0 | keep and show everything | yes, by construction | no, by construction (0%) | high exposure; accuracy depends on the reader |
| P1 | delete facts older than 20 days | no: deletes old facts that are still true | partly: only old values past the TTL | trades accuracy for staleness; no gain where data spans less than 20 days |
| P2 | hide closed facts, delete 7 days after closing | yes, if detection never closes a true fact | equals detection recall | best wherever contradictions are detected precisely |
| P3 | refuse a fact with cosine > 0.9 to a stored fact | no: a correction is worded like what it replaces, so it is refused | no | worst kind of failure: keeps the old value, drops the new one |
| P4 | an LLM reviews memory every third session | not guaranteed: LLM rewriting can drop true facts | not guaranteed | unpredictable; varies between runs |
| P5 | keep the value with more supporting facts, never use dates | no: when the old value has more support, the new one is removed | near chance | shows what is lost without time |

Why P3 fails: o and o\* share subject, relation and wording ("The head of government of New Zealand is Jacinda Ardern" vs "... is Chris Hipkins"), so their embeddings are almost identical and the gate refuses the correction. SAGE's density gate (Wang et al., 2026) and the near-duplicate gate of Governed Shared Memory have the same weakness.

Why P5 cannot be complete: support counts carry no information about order. If the old value was mentioned more often, the vote keeps it. Only time says which value is newer, which is exactly what RQ3 tests.

---

## 4. Results, figure by figure and table by table

### 4.1 Headline: accuracy and staleness by policy (Figure V01, `tables_v3/policy_average.csv`)

What the figure shows: for each benchmark, the accuracy (top) and stale-answer rate (bottom) of each policy, averaged over the five answer models; error bars are the SD over the three runs.

| | MQuAKE-T acc | stale | FactConsolidation acc | stale | ConvoMem acc | stale |
|---|---|---|---|---|---|---|
| NOMEM | 0.6 ± 0.1 | 0.1 | 0.3 ± 0.1 | 0.9 | 0.0 | 0.4 |
| P0 | 91.3 ± 2.0 | 6.7 | 67.2 ± 0.7 | 6.8 | 12.4 ± 1.6 | 8.9 |
| P1 | 82.9 ± 1.5 | 4.0 | 57.3 ± 0.7 | 3.6 | 12.4 ± 1.6 | 8.9 |
| **P2** | **95.2 ± 2.3** | **3.3** | **79.9 ± 0.6** | **0.9** | 8.4 ± 0.6 | 7.9 |
| P3 | 79.1 ± 0.7 | 15.9 | 54.7 ± 0.4 | 16.7 | 12.3 ± 1.7 | 8.9 |
| P4 | 89.9 ± 1.4 | 7.6 | 44.0 ± 5.0 | 31.5 | 11.9 ± 1.2 | 8.1 |
| P5 | 77.2 ± 3.3 | 20.3 | 64.6 ± 0.5 | 9.7 | 8.3 ± 0.8 | 7.8 |

How to read it:

- On the two benchmarks where change is explicit (MQuAKE-T, FactConsolidation), P2 is the most accurate policy and has the fewest stale answers, in every run.
- P1 lowers staleness, but only by deleting true facts too, so accuracy drops (it is unsound).
- P3 and P5 are the stalest policies: they keep the old value (and P3 refuses corrections).
- P4 on FactConsolidation is the least accurate memory policy, and its SD (5.0) is the largest in the table: LLM consolidation is unstable between runs (Zhang et al., 2026).
- ConvoMem is different: every policy is below 13%, and P2 is lower than P0. Section 4.8 explains why.

### 4.2 Paired tests: is P2 better than each alternative? (`tables_v3/paired_p2.csv`)

Method:

- Every policy answers the same questions, so comparisons are paired.
- **Effect size**: mean per-question difference, pooled over models and runs, with a 95% interval from a bootstrap that resamples *questions* (a question keeps all its runs and models). This is a cluster bootstrap: it respects the fact that the same question appears 15 times (5 models × 3 runs) and is not 15 independent observations.
- **Significance**: exact McNemar test on the discordant answers, run separately in each run, Holm-corrected over the 30 comparisons of each benchmark. "Runs significant" counts how many of the three runs pass at 0.05 after correction.

Pooled over the five models:

| Benchmark | P2 vs P0 | P2 vs P1 | P2 vs P3 | P2 vs P4 | P2 vs P5 | Runs significant |
|---|---|---|---|---|---|---|
| MQuAKE-T | +3.9 [+2.5, +5.4] | +12.3 [+7.0, +18.2] | +16.1 [+9.9, +22.5] | +5.3 [+3.1, +8.1] | +18.1 [+12.4, +24.4] | 3/3 for all |
| FactConsolidation | +12.7 [+9.3, +16.6] | +22.7 [+15.0, +30.6] | +25.3 [+18.9, +32.0] | +35.9 [+29.0, +42.9] | +15.3 [+11.1, +20.1] | 3/3 for all |
| ConvoMem | −4.0 [−7.3, −1.3] | −4.0 [−7.3, −1.3] | −3.9 [−7.0, −1.3] | −3.5 [−6.7, −0.9] | +0.1 [−1.4, +1.7] | 2/3, 2/3, 2/3, 2/3, 0/3 |

Discordant counts make the direction concrete: on FactConsolidation run 1, P2 was right and P0 wrong on 67 answers, the reverse on 5.

### 4.3 Who benefits: P0 against P2 per model (Figure V02)

What the figure shows: P0 (blue) and P2 (green) accuracy for each answer model, with SD over runs.

| Model | MQuAKE-T P0 → P2 | FactConsolidation P0 → P2 | ConvoMem P0 → P2 |
|---|---|---|---|
| GPT-6.1 Sol | 96.2 → 96.2 | 85.0 → 86.0 | 15.7 → 11.0 |
| Claude Sonnet 5.5 | 95.8 → 96.2 | 81.7 → 86.3 | 13.3 → 8.7 |
| Gemini 3.8 Flash | 96.2 → 96.2 | 83.0 → 86.0 | 13.0 → 9.0 |
| Qwen3 14B | 92.7 → 94.4 | 55.0 → 78.7 | 12.3 → 8.0 |
| Llama 3.1 8B | 75.7 → 93.1 | 31.3 → 62.7 | 7.7 → 5.3 |

- Frontier models gain little: on MQuAKE-T, GPT and Gemini give the identical answer under P0 and P2 on every question in every run (0 discordant pairs).
- Small models gain a lot, and significantly in all three runs: Llama +17.4 [+10.8, +24.7] on MQuAKE-T; Qwen +23.7 [+16.0, +31.7] and Llama +31.3 [+22.7, +40.7] on FactConsolidation.
- **The gain is larger for small models than for frontier models, and the difference is itself significant**: small-model gain minus frontier-model gain is +9.4 [+5.8, +13.4] on MQuAKE-T and +24.6 [+18.3, +31.5] on FactConsolidation (question-cluster bootstrap). On ConvoMem it is +1.1 [−1.0, +3.7], not significant.
- **Small model with correct forgetting against frontier model without**: Llama under P2 reaches 93.1% on MQuAKE-T against GPT's 96.2% under P0; Qwen under P2 reaches 78.7% on FactConsolidation against Claude's 81.7% under P0. At the measured prices, Llama under P2 costs $0.011 per 1,000 correct answers on MQuAKE-T, against $1.38 for GPT under P0.

### 4.4 Why: exposure and reading error (Figure V03)

What the figure shows. Left: the share of questions where the superseded value appears in at least one of the 25 retrieved facts (exposure), per policy. Right: under P0, the share of exposed questions on which each model repeats the old value (reading error).

- P0 exposes the old value on 90.6% of MQuAKE-T questions and 95.4% of FactConsolidation questions. P2 cuts that to 9.4% and 55.4%.
  - FactConsolidation exposure is overstated: its counterfactual old values ("ice hockey") also occur in unrelated facts, so the string match fires without the superseded fact itself being shown.
- Reading error under P0 is where the models differ:

| Model | MQuAKE-T | FactConsolidation | ConvoMem |
|---|---|---|---|
| GPT-6.1 Sol | 3.6% | 0.0% | 32.7% |
| Claude Sonnet 5.5 | 2.8% | 0.0% | 35.1% |
| Gemini 3.8 Flash | 3.6% | 0.0% | 30.6% |
| Qwen3 14B | 5.6% | 2.7% | 28.3% |
| Llama 3.1 8B | 22.3% | 52.2% | 22.9% |

Interpretation: frontier models read through a mixed memory almost perfectly (they use the dates), so removing the old value changes little for them. Llama repeats the old value on about a quarter to a half of exposed questions, so removing exposure removes most of its errors. **That is the story: correct forgetting moves the work of tracking change from the model to the memory, and the models that cannot do that work themselves benefit most.** Xie et al. (2024) give the underlying reason: models tend to follow what is in the prompt, even when it conflicts.

### 4.5 Cost (Figure V04, `tables_v3/policy_average.csv`)

What the figure shows: prompt tokens per question and facts kept at the end of the run, each as a percentage of P0.

| | Prompt tokens per question, P0 → P2 | Facts kept, P0 → P2 |
|---|---|---|
| MQuAKE-T | 717 → 587 (82%) | 353 → 317 (90%) |
| FactConsolidation | 661 → 599 (91%) | 380 → 318 (84%) |
| ConvoMem | 802 → 567 (71%) | 529 → 394 (74%) |

- P2 sends fewer tokens because hidden facts free retrieval slots and the 25 facts are shorter on average, and it stores fewer facts because closed facts are deleted after the grace period.
- P1 stores the fewest facts on MQuAKE-T and FactConsolidation (64% and 55% of P0) but pays for it in accuracy. Memory size alone is not the goal.
- USD per 1,000 correct answers (mean over models): MQuAKE-T $0.96 (P0) and $0.72 (P2); FactConsolidation $1.11 and $0.84. On ConvoMem P2 costs more per correct answer ($8.30 against $7.47) because it answers fewer questions correctly.

This answers the third part of the hypothesis: on the benchmarks where it is more accurate, P2 is also cheaper than P0 and P3.

### 4.6 Is the forgetting correct? Soundness and completeness (Figure V05, `tables_v3/forgetting_correctness.csv`)

Method: for every changed slot found in P0's end-of-run memory, check the same slot in each policy's end-of-run memory. *Complete* = the old value is no longer visible. *Sound* = the current value is still visible. Mean over models, SD over runs. No model is called.

| Policy | MQuAKE-T complete | sound | FactConsolidation complete | sound |
|---|---|---|---|---|
| P0 | 0.0 | 100.0 | 0.0 | 100.0 |
| P1 | 45.7 ± 3.9 | 89.3 ± 0.3 | 59.6 ± 0.0 | 82.8 ± 0.0 |
| **P2** | **91.9 ± 0.3** | **100.0 ± 0.0** | **84.6 ± 3.3** | **100.0 ± 0.0** |
| P3 | 1.2 ± 0.1 | 90.8 ± 3.0 | 1.9 ± 0.0 | 75.0 ± 0.0 |
| P4 | 0.2 ± 0.3 | 99.7 ± 0.4 | 0.6 ± 0.2 | 52.6 ± 6.9 |
| P5 | 6.6 ± 4.7 | 84.8 ± 3.9 | 3.6 ± 0.8 | 93.0 ± 0.5 |

How this justifies the policies' correctness:

- **Theory says** P2 is sound whenever contradiction detection is precise and complete up to detection recall. **The data says** P2 is 100% sound on both benchmarks in all three runs, and 92% and 85% complete. The incompleteness is exactly the contradictions extraction did not detect. For example, the same relation is named `headquarters` in one session and `headquarters_location` in another; the LLM-matching follow-up (Section 4.10) recovers part of it.
- P2 is the only policy that is both sound and largely complete. P1 is partly complete but unsound. P3, P4 and P5 are almost entirely incomplete, which is why they stay stale.
- P4's soundness of 52.6% on FactConsolidation means the LLM review removes almost half of the current values: the measured version of the "faulty consolidation" failure (Zhang et al., 2026).
- ConvoMem is not in this table: the slot test finds only 4 changed slots there, too few to report. Section 4.8 uses a looser test.

### 4.7 RQ3: is it time, or the graph? (P2 against P5)

P5 has the same facts and the same graph as P2 but ignores dates.

| | P2 | P5 | Paired difference, all models |
|---|---|---|---|
| MQuAKE-T | 95.2 | 77.2 | +18.1 [+12.4, +24.4], 3/3 runs |
| FactConsolidation | 79.9 | 64.6 | +15.3 [+11.1, +20.1], 3/3 runs |
| ConvoMem | 8.4 | 8.3 | +0.1 [−1.4, +1.7], 0/3 runs |

P5 is complete on only 4% to 7% of changed slots. The benefit therefore comes from the timeline, not from graph structure: removing the dates removes the benefit.

### 4.8 ConvoMem: an honest negative result, and what it teaches

Every policy scores below 13% on ConvoMem, and P2 is about 4% below P0. Three measurements explain this.

1. **Extraction, not forgetting, is the bottleneck.**
   - The current value appears anywhere in memory for only 29 to 33 of the 100 questions (loose string match, GPT cell, three runs).
   - Of wrong answers, 79% to 86% had no retrieved fact containing the gold answer.
   - Figure V08 shows this directly. In the RQ4 shared run each ConvoMem conversation happened to be extracted by one answer model. P0 accuracy by extractor:

     | Extractor | Accuracy |
     |---|---|
     | GPT-6.1 Sol | 85% |
     | Claude Sonnet 5.5 | 82% |
     | Gemini 3.8 Flash | 60% |
     | Qwen3 14B | 17% |
     | Llama 3.1 8B | 4% |
     | DeepSeek V4.1 Flash (main run) | 12.4% |

     GPT extracted about 480 to 580 facts per conversation, where DeepSeek extracted about 50.
2. **Contradiction detection over-fires on conversation.**
   - DeepSeek's memory closed 241 of 495 facts in run 1 (49%), far more than the roughly 100 real changes.
   - Under P2 the current value was hidden for 5 to 8 of the roughly 30 questions where it was stored, so P2 is about 78% sound on ConvoMem.
   - Only about 30% of stored old values were hidden.
   - With `functional_predicates = "*"`, every relation is treated as single-valued, which suits encyclopaedic facts but not conversation ("user likes X" does not replace "user likes Y").
3. **P1 equals P0 on ConvoMem** because the whole timeline spans 19 days, shorter than the 20-day TTL. Nothing ever expires.

What to conclude, and say in the thesis: forgetting cannot help with facts that were never stored, and bitemporal invalidation is only as good as contradiction detection. On conversational data detection is less precise, so a sound policy needs either a stronger extractor or relation-specific functional predicates. This is a limitation of the substrate, not a reversal of the main result. It is also an argument for the generality claim being scoped: DRIFT's benefit holds where changes are explicit and detectable.

### 4.9 Variance and determinism (Figure V06)

- **Source of run-to-run variation: extraction.** DeepSeek V4.1 Flash at temperature 0 still produced different memories in each run:

  | Benchmark | Run 1 facts / closures | Run 2 | Run 3 |
  |---|---|---|---|
  | MQuAKE-T | 382 / 90 | 325 / 69 | 352 / 81 |
  | FactConsolidation | 380 / 112 | 380 / 102 | 380 / 107 |
  | ConvoMem | 495 / 241 | 547 / 286 | 545 / 257 |

  This is why GPT, Claude and Gemini have the same SD (2.6) on MQuAKE-T: they read the same, slightly different, memory in each run.
- **Flip rate** (share of questions whose grade changes in at least one of the three runs, mean over P0 to P5):
  - 4.7% to 7.4% for the frontier and mid models on MQuAKE-T and FactConsolidation;
  - up to 15.0% for Llama on MQuAKE-T and 14.6% for Qwen on FactConsolidation.
- **Rankings are stable.** The order P2 > P0 > P4 > P1 holds in all three runs on MQuAKE-T, and P2 > P0 > P5 > P1 > P3 > P4 is identical in all three runs on FactConsolidation. On ConvoMem the top four policies swap places from run to run because they are within about 1% of each other.
- What this means for reporting: a single run would have been enough to rank the policies on MQuAKE-T and FactConsolidation. It would not have been enough to report exact accuracies within 2% to 3%. The three runs measure that uncertainty; they do not reduce the variation itself. Mem0 (Chhikara et al., 2025) repeated its judge 10 times for the same reason.

### 4.10 Contradiction matching and retrieval weights (Figure V09)

What the figure shows: P2 accuracy (mean of five models, run once) under three contradiction-matching modes (left) and five retrieval weightings (right).

Matching:

| | exact | normalised (main) | LLM | Closures (exact / normalised / LLM) |
|---|---|---|---|---|
| MQuAKE-T | 97.5 | 97.5 | 98.8 | 90 / 90 / 96 |
| FactConsolidation | 79.2 | 79.8 | 82.8 | 111 / 112 / 133 |
| ConvoMem | 8.8 | 8.4 | 9.0 | 237 / 241 / 153 |

- An LLM contradiction check finds more real changes on MQuAKE-T and FactConsolidation (Llama rises from 94% to 99% and from 61% to 70%), and closes fewer facts on ConvoMem (153 against 241), so it over-fires less.
- It costs one extra LLM call per candidate pair.
- On MQuAKE-T, normalisation adds nothing over exact matching in a single-agent memory; it matters in shared memory (Section 5).

Retrieval weighting:

| | 0.6/0.3/0.1 (main) | 0.9/0.1/0.2 | 0.8/0.1/0.1 | 0.6/0.3/0 (no recency) | RRF |
|---|---|---|---|---|---|
| MQuAKE-T | 97.5 | 97.3 | 97.7 | 97.7 | 97.5 |
| FactConsolidation | 79.8 | 80.6 | 79.6 | 81.0 | 81.0 |
| ConvoMem | 8.4 | 7.8 | 7.8 | 7.4 | 7.4 |

All weightings are within about 1.5% of each other on every benchmark. Under P2 the choice of weights does not change the conclusion, because the old fact is hidden before ranking matters. The earlier BM25 pilot showed the same: the lexical scorer moved Llama by about 10% under P0 and not at all under P2.

### 4.11 The grace period (Figure V10)

What the figure shows: as P2's grace period grows from 0 days to "never delete", current-value accuracy (green), accuracy on history questions ("before it changed, what was it?", orange), and the share of old values still stored (grey dashed). Mean of five models.

| Grace (days) | 0 | 7 | 21 | never |
|---|---|---|---|---|
| MQuAKE-T current / history | 97.5 / 16.9 | 97.5 / 56.0 | 97.3 / 91.7 | 97.3 / 99.0 |
| FactConsolidation current / history | 90.5 / 13.2 | 90.8 / 34.2 | 91.4 / 64.9 | 92.0 / 76.3 |

- Current accuracy does not change with grace. Hiding happens at closing, not at deletion.
- History recall grows with how long closed facts are kept. The grace period is therefore a retention setting, not an accuracy setting.
- The 7 days in the main run is a middle point on a curve. The right value depends on how far back an application needs to answer history questions.
- On ConvoMem the curve is flat because the old values were rarely stored in the first place.

---

## 5. RQ4: multi-agent memory

### 5.1 Design

| Topology | Writers | Graphs | Who extracts | Who answers | What it tests |
|---|---|---|---|---|---|
| Shared | 5 (the five answer models), round-robin over sessions | one per conversation | each writer with its own model | every answer model reads the same memory | contradictions that arrive from different writers |
| Independent | 3 private agents, each sees a random 80% of sessions (seed 42) | one per agent and conversation | DeepSeek | every answer model | partial observation; agent-to-agent spread |
| Orchestrator | 1 ingesting agent | one per conversation | DeepSeek | a Gemini router assigns each question to one of 4 workers; every answer model answers | coordinator/worker reading pattern |

Six policies (P0 to P5) in each topology. Shared memory also runs with exact and LLM matching for P0 and P2.

### 5.2 Two design facts you must state

1. **The orchestrator reproduces the single-agent run exactly.** It uses the same extractor, the same sessions and the same context lines as run 1 of the main matrix, so every extraction call came from the cache and the memory is identical. Its accuracies match run 1 to the decimal (MQuAKE-T P0 93.5%, P2 97.5%), and its agreement with the single-agent ranking is close to perfect. It is a consistency check that routing does not change results. It is not independent evidence.
2. **ConvoMem shared memory has one writer per conversation.** Sessions are assigned round-robin over the global timeline. ConvoMem has 10 conversations of 20 sessions with identical timestamps, so conversation c is always written by agent c mod 5. Cross-writer invalidations are 0 there. On ConvoMem the shared topology therefore tests extractor quality (Section 4.8), not cross-writer contradictions. MQuAKE-T and FactConsolidation are single conversations, so their shared runs do mix writers.

### 5.3 Results (Figure V07, `tables_v3/rq4_cells.csv`)

What the figure shows: accuracy of each policy (mean of five answer models) in each topology, with the single-agent 3-run mean in black. A gap in a line is a missing cell.

**Shared memory (MQuAKE-T and FactConsolidation, the genuine multi-writer case):**

| | P0 | P1 | P2 | P3 | P4 | P5 |
|---|---|---|---|---|---|---|
| MQuAKE-T accuracy | 86.5 | 78.3 | **87.1** | 72.9 | 85.0 | 79.8 |
| MQuAKE-T stale | 12.3 | 3.3 | 11.2 | 23.5 | 14.0 | 17.9 |
| FactConsolidation accuracy | 59.8 | 50.8 | **66.6** | 56.0 | 45.4 | 59.8 |
| FactConsolidation stale | 11.2 | 3.0 | 8.0 | 14.8 | 23.0 | 10.4 |

- **Stale propagation.** With mixed writers, staleness under P0 roughly doubles: 12.3% against 6.7% single-agent on MQuAKE-T, and 11.2% against 6.8% on FactConsolidation. Even frontier models drop to about 90.6% on MQuAKE-T. Old and new facts written by different models are phrased differently, which makes them harder to reconcile, both for the model and for the matcher. This is the "stale propagation" failure named by Governed Shared Memory (Margalit et al., 2026).
- **Cross-writer contradictions.** On MQuAKE-T, 26 of 38 closures (68%) were triggered by a different writer from the one that wrote the old fact. On FactConsolidation it was 38 of 54 (70%). With 5 writers in round-robin, about 80% would be expected if detection were writer-blind, so cross-writer contradictions are detected slightly less often than same-writer ones.
- **Contradiction persistence: the main RQ4 finding.** In shared memory P2 stays 100% sound but becomes much less complete:

  | | Single agent | Shared memory |
  |---|---|---|
  | MQuAKE-T | 91.9% | 45.1% |
  | FactConsolidation | 84.6% | 59.5% |

  Five different extractor models name relations differently, so normalised matching misses many cross-writer changes. In the shared MQuAKE-T memory, GPT, Claude and Gemini mostly write `head_of_government` and `head_of_state`, but use `headquarters_in` (GPT) and `headquarters_location` (Claude, Gemini) for the same thing. Llama files most facts under `lives_in` and `works_at`, and Qwen under `job` and `works_at`. When one writer stores the old head of government and another stores the new one under a different relation, no contradiction is detected. The old value stays visible: under P2 it reaches the prompt on 63.5% of MQuAKE-T questions in shared memory, against 9.4% for a single agent.

  The consequence is that **P2's advantage shrinks in shared memory**:
  - MQuAKE-T: P2 87.1% against P0 86.5%, compared with 95.2% against 91.3% for a single agent. Llama still gains (71.9% to 75.0%).
  - FactConsolidation: the gain falls from +12.7% to +6.8% (66.6% against 59.8%).

  Forgetting is only as good as detection, and detection is hardest when writers disagree on vocabulary.
- **Matching matters more with many writers.** Shared memory on MQuAKE-T:

  | Matching | Closures | From a different writer |
  |---|---|---|
  | Exact | 37 | 25 |
  | Normalised | 38 | 26 |
  | LLM | 63 | 51 |

  P2 accuracy on MQuAKE-T is 87.1% (exact), 87.1% (normalised) and 88.5% (LLM). On FactConsolidation it is 66.0%, 66.6% and 69.4%. The LLM check roughly doubles cross-writer detection and recovers part of the lost completeness, which makes it the recommended matcher for multi-writer memory.
- P2 is still the best policy in shared memory on both benchmarks (narrowly on MQuAKE-T), and the policy ranking largely holds (Section 5.4).

**Independent agents (partial observation):**

| | P0 | P2 | SD across the 3 agents |
|---|---|---|---|
| MQuAKE-T | 68.0 | 70.8 | 6.3 / 6.6 |
| FactConsolidation | 52.3 | 61.7 | 4.2 / 4.0 |
| ConvoMem | 9.4 | 6.1 | 0.9 / 0.8 |

Each agent misses about 20% of sessions, so it often never hears about a change. Missing the session with the new value cannot be repaired by any forgetting policy:
- on MQuAKE-T, P2 gains only about 3% over P0, and stale answers stay high (24.1%);
- on FactConsolidation the gain survives (+9.4%, 52.3% to 61.7%).

This marks a boundary of what forgetting can do: it cannot fix information an agent never received.

### 5.4 Do single-agent rankings hold? (`tables_v3/rq4_agreement.csv`)

Method:

- Rank the six policies by accuracy (mean of five models) in the single-agent runs and in each topology. Compare the two rankings with Kendall's τ-b (main statistic), Spearman's ρ and Pearson's r.
- With six policies there are only 720 possible orderings, so p is exact: the share of all 720 orderings that agree at least as well as observed. It is one-sided, because the hypothesis is that rankings agree.
- Kendall's τ is the standard for comparing benchmark rankings (Perlitz et al., 2024) and behaves well with few items and ties. Spearman and Pearson are reported as checks; Pearson compares the scores, not the order.

| Benchmark | Topology | Kendall τ | p | Spearman ρ | p | Pearson r | p |
|---|---|---|---|---|---|---|---|
| MQuAKE-T | shared | 0.73 | 0.028 | 0.83 | 0.029 | 0.87 | 0.024 |
| MQuAKE-T | independent | 0.73 | 0.028 | 0.83 | 0.029 | 0.94 | 0.013 |
| MQuAKE-T | orchestrator | 1.00 | 0.0014 | 1.00 | 0.0014 | 0.99 | 0.0014 |
| FactConsolidation | shared | 0.83 | 0.014 | 0.93 | 0.008 | 0.95 | 0.006 |
| FactConsolidation | independent | 0.87 | 0.008 | 0.94 | 0.008 | 0.98 | 0.004 |
| FactConsolidation | orchestrator | 1.00 | 0.0014 | 1.00 | 0.0014 | 1.00 | 0.0014 |
| ConvoMem | shared | 0.57 | 0.069 | 0.76 | 0.047 | 0.46 | 0.119 |
| ConvoMem | independent | 1.00 | 0.0028 | 1.00 | 0.0028 | 1.00 | 0.0028 |
| ConvoMem | orchestrator | 0.57 | 0.067 | 0.65 | 0.089 | 0.97 | 0.053 |

Reading it:

- **Where changes are explicit, single-agent rankings transfer.** All four genuine multi-agent comparisons are significant:

  | | Shared | Independent |
  |---|---|---|
  | MQuAKE-T | τ = 0.73 | τ = 0.73 |
  | FactConsolidation | τ = 0.83 | τ = 0.87 |

- The orchestrator's τ = 1.00 on MQuAKE-T and FactConsolidation is the consistency check from Section 5.2, not evidence.
- On ConvoMem the picture is mixed:
  - shared τ = 0.57 (p = 0.07) and orchestrator τ = 0.57 (p = 0.07): all policies sit within a few percent of each other, so small differences reorder them;
  - independent τ = 1.00, because the independent agents reproduce the same near-ties in the same order.

  Treat ConvoMem rankings as uninformative rather than as evidence either way.
- **Per answer model** (Kendall τ, 5 models each):

  | | Range of τ |
  |---|---|
  | Shared MQuAKE-T | 0.69 to 0.86 |
  | Shared FactConsolidation | 0.83 to 1.00 |
  | Independent MQuAKE-T | 0.57 to 0.87 |
  | Independent FactConsolidation | 0.73 to 1.00 |

**RQ4 answer.** Yes, rankings transfer where changes are explicit (τ = 0.73 to 0.87, all p < 0.03), and P2 stays the best policy. But its advantage shrinks in shared memory: different writers name relations differently, so P2's completeness falls (to 45% on MQuAKE-T and 60% on FactConsolidation) and more stale facts reach the model. LLM-based contradiction matching roughly doubles cross-writer detection and is the recommended matcher for multi-writer memory. Partial observation (independent agents) is a limit no forgetting policy can fix.

---

## 6. Answering the research questions and the hypothesis

| RQ | Answer | Evidence |
|---|---|---|
| RQ1: does append-only memory surface superseded facts and cause stale answers? | Yes. P0 puts the old value in the prompt for 91% (MQuAKE-T) and 95% (FactConsolidation) of questions. It produces 6.7% and 6.8% stale answers on average, up to 20.1% and 32.3% for Llama | V03, V01 |
| RQ2: which policy gives the best trade-off? | P2 on MQuAKE-T and FactConsolidation: most accurate, least stale, fewer tokens and fewer facts than P0 and P3; significant against every alternative in all three runs. On ConvoMem no policy helps, and P2 costs about 4% accuracy because detection over-fires | V01, V02, V04, `paired_p2.csv` |
| RQ3: time or graph? | Time. P5, same graph without dates, is 18.1% and 15.3% less accurate and almost entirely incomplete | 4.7, V05 |
| RQ4: do rankings hold in multi-agent memory? | Yes on explicit-change data (τ = 0.73 to 0.87, all p < 0.03), and P2 stays best. But with several writers P2's completeness falls (92% to 45% on MQuAKE-T) and its advantage shrinks (+0.6% on MQuAKE-T, +6.8% on FactConsolidation). LLM matching doubles cross-writer detection | V07, 5.3, 5.4 |

**Hypothesis:**

| Part | Verdict | Evidence |
|---|---|---|
| (1) at least as accurate as append-only | Supported on MQuAKE-T (+3.9) and FactConsolidation (+12.7). Not supported on ConvoMem (−4.0) | Paired tests, 4.2 |
| (2) fewer stale answers | Supported on all three benchmarks: 3.3 against 6.7, 0.9 against 6.8, 7.9 against 8.9 | V01 |
| (3) fewer tokens and facts than append-only and novelty-based forgetting | Supported on all three | V04 |

---

## 7. Generality: how far DRIFT's conclusions reach

What the three benchmarks cover:

- **Clean real-world changes**: MQuAKE-T, Wikidata updates 2021 to 2023.
- **Counterfactual changes** that contradict the model's training: FactConsolidation. Prior knowledge cannot answer it.
- **Changes stated inside natural dialogue**: ConvoMem.

What they do not cover, so state them as scope:

- implicit changes ("I'm packing for Boston" implying a move);
- cascading changes (a new CEO changes "who signs the budget");
- multi-valued relations;
- noisy or adversarial writers;
- horizons of months to years;
- real production logs.

What the results support:

- The mechanism (exposure × reading error) is model-independent and was confirmed on two benchmarks.
- The gain from correct forgetting grows as the reader gets weaker.
- The policy ranking is stable across runs and transfers to multi-agent memory where changes are detectable.
- The benefit depends on detection quality, which is the main condition for generalising: wherever contradictions can be detected precisely, invalidation helps; where they cannot (free conversation with a weak extractor), it can hurt.

The framework itself is general:

- a policy is any class with three hooks;
- any OpenAI-compatible model can be plugged in;
- any dataset that records old and new values can be converted;
- `Memory` exposes the same pipeline to other agents.

---

## 8. Limitations to state

1. ConvoMem results are extraction-bound (4.8). Policy differences there are small and partly reversed.
2. Contradiction detection over-fires on conversation because every relation is treated as functional.
3. The judge was validated against a stronger LLM, not against humans. LongMemEval and STALE validate against humans. Grading 150 to 200 answers yourself would close this gap.
4. RQ4 ran once. The orchestrator is not independent of the single-agent run, and ConvoMem shared memory has one writer per conversation.
5. Follow-ups (matching, weights, grace) ran once, on 96 to 100 questions, so differences under about 3% are within noise.
6. Latency was not measured.
7. Extraction uses one model (DeepSeek V4.1 Flash); the ConvoMem shared run shows that extractor choice can matter more than the policy.

---

## 9. Statistics used, and why (with references)

| Statistic | Used for | Why | Reference |
|---|---|---|---|
| Mean ± sample SD over 3 runs | every main-matrix number | shows run-to-run variation, which comes from non-deterministic extraction | descriptive |
| Flip rate | per cell | share of questions whose grade changes across runs; a per-question view of stability | descriptive |
| Cluster (question-level) bootstrap 95% CI, 5,000 resamples | every paired difference | no distribution assumption; resampling questions respects repeated measures | Efron and Tibshirani 1993; Dror et al. 2018 |
| Exact McNemar test, per run | P2 against each policy | paired yes/no outcomes on the same questions; uses only discordant pairs | McNemar 1947; Dietterich 1998 |
| Holm correction | 30 comparisons per benchmark, each run | controls family-wise error, less conservative than Bonferroni | Holm 1979 |
| Difference of gains (small minus frontier) with cluster bootstrap | "small models benefit most" | tests the interaction directly instead of eyeballing two gains | Efron and Tibshirani 1993 |
| Kendall τ-b, exact one-sided permutation p over 720 orderings | RQ4 ranking agreement | standard for benchmark ranking agreement; exact with 6 items | Kendall 1938; Perlitz et al. 2024 |
| Spearman ρ, Pearson r, same exact p | RQ4 checks | rank agreement and score agreement | Spearman 1904; Pearson 1896 |
| Cohen's κ | judge against a reference grader | agreement beyond chance | Cohen 1960; Landis and Koch 1977 |

---

## 10. Files

| What | Where |
|---|---|
| Figures | `paper/figures_v3/V01` to `V10` (`.png` for slides, `.pdf` for LaTeX) |
| Tables | `paper/tables_v3/` (main_cells, policy_average, paired_p2, forgetting_correctness, rq4_cells, rq4_agreement) |
| All numbers | `artifacts/v3_analysis.json` |
| Code | `src/analysis/v3_compact.py`, `v3_analysis.py`, `v3_figures.py` |
