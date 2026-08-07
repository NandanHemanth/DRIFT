# When Should Agents Forget?

## A Controlled Study of Forgetting Policies in Bitemporal Knowledge-Graph Agent Memory

**Author:** Nandan Hemanth
**Framework:** DRIFT (Decay and Retention In Forgetful Temporal-graph memory) v1.0.0
**Code and data:** [`../README.md`](../README.md)
**Date:** August 2026

---

## Abstract

Long-lived language-model agents accumulate memories that go stale. A fact that was true when it was written is later superseded, but retrieval keeps surfacing it, and the agent answers from a value that no longer holds. Research on agent memory has concentrated on storage and retrieval; the rule that decides what to discard has been treated as an implementation detail.

This work isolates that rule. DRIFT holds a bitemporal knowledge-graph substrate, the extraction step, the retrieval function, the answer model and the judge constant, and varies only the forgetting policy across seven settings: a no-memory floor, an append-only baseline, and five forgetting strategies drawn from current systems. We evaluate on two public benchmarks that annotate the superseded answer, which is the annotation the staleness metric requires and which the two most widely used agent-memory benchmarks do not provide.

Three findings replicate across both benchmarks. Bitemporal contradiction invalidation costs nothing in accuracy while reducing token spend by 12 percent and memory footprint by 6 to 15 percent, with paired McNemar tests against the accuracy ceiling returning 3 to 3 and 2 to 2 at p = 1.000. Novelty-gated writing, a popular efficiency technique, causes a 4.5-fold increase in staleness, because a correction is textually near-identical to the fact it corrects and is therefore rejected as a duplicate. Structure-aware but time-blind consolidation is significantly worse than bitemporal consolidation on both accuracy and staleness on real-world knowledge updates, which attributes the advantage to bitemporal semantics rather than to graph structure in general.

We also report two methodological results: a controlled measurement of how much of the reported efficiency gain is contingent on correctly declaring which predicates are single-valued, and a judge-reliability audit that identified a 12.5-point accuracy artifact produced by a rotating judge pool on byte-identical answers.

---

## 1. Introduction

### 1.1 Problem

Consider an assistant that has been told "I live in Boston" and, three months later, "I moved to Seattle". Both statements are in memory. Both are semantically close to the query "where do I live". A retrieval function ranks by similarity and recency, and the older fact is often retrieved alongside the newer one. The model then produces an answer grounded in a fact whose validity ended.

This failure is not a retrieval failure. The right fact was stored and could be found. It is a failure of memory hygiene: nothing in the system marks the older fact as no longer current, and nothing removes it.

Existing production memory systems address the storage and retrieval halves of the problem. MemGPT [1] manages a paged context hierarchy. Zep [2] adds a temporal knowledge graph. Mem0 [3] provides a scalable long-term store. A-MEM [4] organises memory agentically. In each, the treatment of superseded information is a secondary concern, and where a forgetting mechanism exists it is chosen rather than measured.

### 1.2 Hypothesis

> Selective forgetting grounded in bitemporal structure improves an agent's answer quality and cost profile relative to both append-only memory and to structure-blind or novelty-based forgetting.

### 1.3 Research questions

**RQ1.** Does append-only memory measurably surface superseded facts?

**RQ2.** Which forgetting policy offers the best accuracy, staleness and cost trade-off?

**RQ3.** Does bitemporal structure specifically outperform structure-blind alternatives, or is any graph-aware consolidation sufficient?

**RQ4.** Do the policy rankings survive multi-agent use, where the reader is not the writer?

### 1.4 Contributions

1. A controlled experimental framework in which the forgetting policy is the only independent variable over a fixed substrate, retrieval function, extraction step and judge.
2. A staleness metric separated from accuracy, together with the observation that the two most-used agent-memory benchmarks cannot support it, and the identification of two that can.
3. Replicated evidence on two benchmarks that bitemporal invalidation is free, that novelty gating causes unrecoverable staleness, and that time-blind consolidation is significantly worse than bitemporal consolidation.
4. An ablation quantifying how much of the result depends on a configuration choice rather than on the policy.
5. A judge-reliability audit that establishes a noise floor below which reported differences are not interpretable.
6. An open, dependency-free implementation that can be run offline in 0.2 seconds and integrated into a third-party agent in five lines.

---

## 2. Related work

**Memory systems.** MemGPT [1] introduced operating-system-style paging for context. Zep [2] built a temporal knowledge graph for agent memory, and is the closest architectural relative of DRIFT's substrate. Mem0 [3] and A-MEM [4] target production deployment and agentic organisation respectively. All four are systems contributions; none isolates the forgetting rule for controlled comparison.

**Consolidation and its risks.** Zhang et al. [5] show that memories consolidated by repeated LLM rewriting degrade with time, and that utility can fall below a no-memory baseline. This motivates the inclusion of LLM consolidation as a policy under test rather than as an assumed improvement. Wang et al. [6] propose SAGE, a write-side novelty gate that routes clearly novel facts to ADD, clearly redundant ones to NOOP, and only uncertain cases to an LLM merge. This is the technique our P3 policy models, and section 5.3 reports a failure mode of it that follows from its design.

**Staleness as a first-class problem.** Chao et al. [7] introduce STALE, a benchmark for whether agents recognise that a stored belief is outdated, and identify implicit conflict as an underexplored failure mode. Patel [8] frames the same gap as a memory-update problem and studies training remedies. Du [9] surveys the field and identifies evaluation of memory revision as an open frontier. Our contribution is complementary: rather than asking whether a model can detect staleness, we ask which forgetting policy prevents staleness from arising.

**Benchmarks.** LoCoMo [10] and LongMemEval [11] are the standard agent-memory benchmarks. Neither annotates the superseded answer, which is discussed in section 4.1. MemoryAgentBench [12] contains a FactConsolidation split built for exactly this property. MQuAKE [13] provides knowledge-editing instances that ship both the pre-edit and post-edit answer. GateMem [14] studies memory governance in shared multi-agent memory, which is the setting of our RQ4.

---

## 3. Method

### 3.1 Substrate

Every fact is a `(subject, predicate, object)` triple carrying two timelines:

- **valid time** (`t_valid_start`, `t_invalid_at`): the interval during which the fact was true of the world;
- **ingestion time** (`t_ingested`): when the agent learned it.

A third timestamp, `t_pruned`, records when a policy removed the fact. Facts also carry `provenance`, identifying the writing agent, which makes cross-writer invalidation auditable in the multi-agent setting.

When a new fact arrives on a **functional predicate**, one that admits a single true object at a time, the previous fact's valid-time window is closed. This closing is non-destructive: the fact stays in memory and remains retrievable. Only a policy removes or hides data. That separation is what makes the policy the sole independent variable.

Speech-act predicates such as `stated` and `mentioned` are excluded from contradiction handling. Without this guard, a degenerate extraction in which every line returns as `speaker / stated / <whole line>` causes every fact to contradict its predecessor. We measured 379 of 380 facts invalidated on a corpus whose true count is 133. The failure is silent and resembles a policy result.

### 3.2 Pipeline

```
session lines
    -> extract_facts()            LLM triple extraction + deterministic regex upgrade
    -> policy.on_write()          write gate
    -> BitemporalGraph            contradiction closes the superseded window
    -> policy.after_session()     periodic maintenance
    -> graph.search()             0.6 cosine + 0.3 lexical + 0.1 recency, k = 25
    -> policy.on_retrieve()       retrieval filter
    -> answer model
    -> LLM judge (different family) + token-F1
```

A policy is defined by exactly three hooks, `on_write`, `after_session` and `on_retrieve`. Adding one is a subclass and a registry entry; the runner, substrate, providers and analysis code never learn about it.

### 3.3 Policies under test

| ID | Name | Mechanism | Hook |
|---|---|---|---|
| NOMEM | No memory | Retrieval returns nothing | `on_retrieve` |
| P0 | No forgetting | Append-only; nothing gated, pruned or filtered | none |
| P1 | TTL decay | Prune facts older than `ttl_days` by valid time | `after_session` |
| P2 | Contradiction invalidation | Exclude superseded facts at retrieval; prune after a grace period | `on_retrieve`, `after_session` |
| P3 | Novelty gate | Reject writes whose neighbourhood cosine exceeds tau, after SAGE [6] | `on_write` |
| P4 | LLM consolidation | Every third session an LLM decides keep or drop, after [5] | `after_session` |
| P5 | Topology consolidation | Resolve competing facts by structural corroboration count, deliberately time-blind | `after_session` |

P5 is the ablation partner of P2. It is structure-aware but has no access to valid time, so it must infer which of two competing facts is current from corroboration in the surrounding graph. If P2 beats P5, the advantage is attributable to bitemporal semantics specifically rather than to graph structure in general.

NOMEM is a floor, not a parametric-knowledge baseline. The answer prompt instructs the model to respond "I don't know" when memory lacks the answer, and NOMEM's records are almost entirely that string, including for facts the model plainly knows. NOMEM therefore measures memory-gated answering, and the P0-minus-NOMEM gap should be read as the value of memory under an instruction to ground answers in memory.

### 3.4 Metrics

**Accuracy.** An LLM judge from a different model family than the answer model returns CORRECT or INCORRECT against the gold answer.

**Staleness.** The fraction of answers containing the superseded value, computed as a substring test against the `stale_answer` annotation. Staleness fires only on annotated questions, so a benchmark's annotation coverage bounds what this metric can report. This is not a minor caveat; see section 4.1.

**Cost.** Mean tokens per question, and the count of active facts retained.

**Statistics.** Percentile bootstrap 95 percent confidence intervals with 5,000 resamples. Policy comparisons use the paired McNemar exact test, since the same questions go to every policy and an unpaired test would overstate significance. Cross-benchmark rank agreement uses Spearman's rho.

---

## 4. Experimental setup

### 4.1 Benchmark selection, and a negative result about the standard benchmarks

The staleness metric requires each question to be annotated with the value a stale memory would return. Auditing the standard benchmarks:

| Benchmark | Questions | With `stale_answer` | Coverage |
|---|---|---|---|
| LoCoMo [10] | 300 | 0 | 0 percent |
| LongMemEval [11] | 150 | 0 | 0 percent |
| LongMemEval knowledge-update subset, LLM-annotated | 78 | 1 | 1 percent |
| **MemoryAgentBench FactConsolidation** [12] | 100 | 65 | **65 percent** |
| **MQuAKE-T** [13] | 96 | 96 | **100 percent** |

On the first campaign, staleness read exactly 0.000 across all 42 single-agent cells. This was briefly read as a finding. It was not: the metric could not fire, because the annotation it depends on does not exist in those datasets. We report this because the same trap is available to anyone measuring memory revision on LoCoMo or LongMemEval.

An attempt to recover the annotation for LongMemEval's knowledge-update questions using an LLM annotator produced 1 usable annotation out of 78, despite the superseded values appearing in plain text in the evidence turns. Deterministic recovery from dataset structure, which is what both converters used here do, is the more reliable route.

### 4.2 The two benchmarks used

**FactConsolidation** (MemoryAgentBench [12], ICLR 2026). A numbered fact list in which later facts overwrite earlier ones on the same subject and predicate, with the gold answer always the latest value. The superseded value is recoverable without an annotator. Facts are atomic triples, so contradiction detection is not extractor-limited.

**MQuAKE-T** (MQuAKE [13], EMNLP 2023). Built by diffing Wikidata snapshots from April 2021 against April 2023 and retaining relations whose change is a genuine real-world update. Each instance ships the pre-edit answer alongside the post-edit answer, so the annotation is deterministic. Selected as the generalization test because its updates are real rather than injected.

The MQuAKE-T conversion is sized to match FactConsolidation cell for cell:

| Property | FactConsolidation | MQuAKE-T |
|---|---|---|
| Sessions | 38 | 38 |
| Fact lines | 380 | 382 |
| Questions | 100 | 96 |
| `stale_answer` coverage | 65 percent | 100 percent |
| Policies x answer models | 7 x 2 | 7 x 2 |

Two conversion decisions are load-bearing. First, old-before-new placement is randomised per pair rather than blocked into an early half and a late half. A clean boundary would let any policy win by learning that later sessions dominate, without using bitemporal structure, which is exactly the confound the P2 versus P5 ablation exists to rule out. Second, edited facts are restated in flat subject-predicate-object form rather than MQuAKE's wordy cloze, because contradiction detection keys on the subject and predicate as the extractor produces them, and a wordier frame introduces extraction variance on the one join the experiment depends on.

### 4.3 Models and infrastructure

Answer models are GLM-5.2 and MiniMax-M3 via OpenRouter. Extraction rotates across six providers and judging across three, spreading volume over independent rate limits. Embeddings are `nomic-embed-text` served locally by Ollama. Retrieval depth is 25.

Every provider call is cached on disk by SHA-256 of the request, so an interrupted campaign resumes at no cost and a rerun is bit-for-bit reproducible. Failures are caught per cell, so one exhausted quota costs a cell rather than a campaign.

---

## 5. Results

### 5.1 Headline table

Pooled across both answer models. Percentile bootstrap 95 percent CIs, 5,000 resamples. n = 200 question-answers on FactConsolidation, 192 on MQuAKE-T.

| Policy | FC accuracy | MQuAKE-T accuracy | FC staleness | MQuAKE-T staleness | FC tok/q | MQ tok/q | FC facts | MQ facts |
|---|---|---|---|---|---|---|---|---|
| NOMEM | 0.000 | 0.000 | 0.000 | 0.000 | 250 | 233 | n/a | n/a |
| **P0** | **0.840** [.785, .890] | **0.969** [.943, .990] | 0.030 [.010, .055] | 0.052 [.021, .089] | 812 | 816 | 380 | 382 |
| P1 (TTL 20 d) | 0.630 [.565, .695] | 0.870 [.823, .917] | 0.020 | 0.026 | 799 | 807 | 210 | 251 |
| **P2** | **0.840** [.785, .890] | **0.969** [.943, .990] | 0.025 [.005, .050] | 0.036 [.010, .068] | **715** | **716** | **324** | **357** |
| P3 | 0.665 [.600, .730] | 0.792 [.729, .849] | **0.140** [.095, .190] | **0.161** [.109, .214] | 806 | 805 | 334 | 351 |
| P4 | 0.800 [.745, .855] | 0.953 [.922, .979] | 0.060 | 0.057 | 814 | 804 | 374 | 372 |
| P5 | 0.795 [.735, .850] | 0.802 [.745, .854] | 0.035 | **0.214** [.156, .276] | 812 | 816 | 365 | 365 |

Paired McNemar exact tests. Counts are discordant pairs only.

| Comparison | Metric | FactConsolidation | MQuAKE-T |
|---|---|---|---|
| P0 vs P2 | accuracy | 3 to 3, p = 1.000 | 2 to 2, p = 1.000 |
| P0 vs P2 | staleness | 5 to 4, p = 1.000 | 6 to 3, p = 0.508 |
| P2 vs P3 | accuracy | 36 to 1, p < 0.001 | 38 to 4, p < 0.001 |
| P2 vs P3 | staleness | 1 to 24, p < 0.001 | 4 to 28, p < 0.001 |
| **P2 vs P5** | **accuracy** | 11 to 2, p = 0.022 | **34 to 2, p < 0.001** |
| **P2 vs P5** | **staleness** | 3 to 5, p = 0.727 | **3 to 37, p < 0.001** |
| P2 vs P4 | accuracy | 11 to 3, p = 0.057 | 7 to 4, p = 0.549 |

Figures: [`../artifacts/results/mquake_t/figures/accuracy_staleness.png`](../artifacts/results/mquake_t/figures/accuracy_staleness.png), [`tradeoff_scatter.png`](../artifacts/results/mquake_t/figures/tradeoff_scatter.png), [`memory_growth.png`](../artifacts/results/mquake_t/figures/memory_growth.png), [`token_cost.png`](../artifacts/results/mquake_t/figures/token_cost.png), [`model_comparison.png`](../artifacts/results/mquake_t/figures/model_comparison.png). The FactConsolidation equivalents are in [`../artifacts/results/factconsolidation/figures/`](../artifacts/results/factconsolidation/figures/).

### 5.2 RQ3: bitemporal structure beats structure-blind structure

This is the ablation the design exists to support, and MQuAKE-T settles it. P2 and P5 share the substrate, retrieval, extraction and judge. The only difference is that P2 knows which fact is current and P5 must infer it from corroboration count.

On MQuAKE-T, P5's staleness is 0.214 against P2's 0.036, a 5.9-fold gap at p < 0.001, and its accuracy is 0.802 against 0.969 at p < 0.001. The failures are the predicted ones:

| Question | Gold, current | P5 answered | P2 answered |
|---|---|---|---|
| Head of state, South Korea | Yoon Suk-yeol | Moon Jae-in | Yoon Suk-yeol |
| Head of government, Czech Republic | Petr Fiala | Andrej Babiš | Petr Fiala |
| Head of state, Czech Republic | Petr Pavel | Miloš Zeman | Petr Pavel |
| Head of government, Malawi | Lazarus Chakwera | Peter Mutharika | Lazarus Chakwera |

Fifteen questions where P5 returned the superseded value and P2 did not. The mechanism is legible: a long-serving predecessor accumulates more corroborating mentions in memory than a recent successor, so corroboration-count consolidation systematically prefers the outdated fact. Recency is not a proxy for correctness, but valid time is a proxy for currency, and that distinction is what the substrate encodes.

The comparison is much sharper here than on FactConsolidation, where it was p = 0.022 on accuracy and inconclusive on staleness. FactConsolidation's entities are arbitrary Wikidata pairs with roughly uniform corroboration, so P5's heuristic fails at random. MQuAKE-T's entities are real people holding real offices, so corroboration is systematically biased toward the incumbent of record. The second benchmark did not merely replicate the finding; it exposed the mechanism.

### 5.3 Novelty gating causes staleness

P3 shows 4.7 times P2's staleness on FactConsolidation and 4.5 times on MQuAKE-T, both at p < 0.001. The mechanism is structural rather than statistical. A fact update is by construction textually near-identical to the fact it supersedes:

```
"Thomas Kyd was born in the city of London"     stored
"Thomas Kyd was born in the city of Leeds"      the correction
```

A novelty gate sees a near-duplicate and rejects it. The correction never enters memory, and no downstream retrieval or reranking can recover a value that was never stored. Verified from saved graph snapshots as 24 subject-predicate pairs on FactConsolidation where P0 recorded the update and P3 retained only the superseded value. On MQuAKE-T the same failure produced 31 write rejections and 14 questions answered from a stale value that P0 got right:

| Question | Gold | P3 retained |
|---|---|---|
| Head of state, United Kingdom | Charles, Prince of Wales | Elizabeth II |
| Head of state, South Korea | Yoon Suk-yeol | Moon Jae-in |
| Headquarters city, Scientific American | Los Angeles | New York City |
| Head of state, Mongolia | Khurelsukh Ukhnaa | Khaltmaagiin Battulga |

This result transfers beyond DRIFT. Write gating is a current efficiency technique [6], and this is a controlled demonstration that on any workload where facts get corrected it trades a bounded memory saving for an unbounded correctness liability. The rate will differ across corpora; the failure mode will not.

### 5.4 RQ2: P2 is accuracy-free, and its efficiency is configuration-dependent

P2 ties P0 on accuracy on both benchmarks, at 3 to 3 (p = 1.000) and 2 to 2 (p = 1.000), while spending 12 percent fewer tokens per question on both and storing 15 percent and 6.5 percent fewer facts.

The `functional_predicates` ablation sharpens this. That setting declares which predicates admit a single true object. FactConsolidation required it to be set to "all predicates", and that choice was made while looking at that dataset, which makes it the largest threat to external validity in the study. We therefore reran MQuAKE-T with the setting left at the substrate default, which covers none of MQuAKE-T's relations. Invalidations drop from 59 to 1, switching P2's mechanism off:

| | Declared | Not declared |
|---|---|---|
| P2 accuracy | 0.969 | 0.969 |
| P2 tokens per question | **641** | 733 |
| P2 active facts | **357** | 382 |
| P0 accuracy | 0.969 | 0.969 (see 5.6) |

The setting buys P2 nothing in accuracy and all of its efficiency. P2 is therefore safe to enable without tuning, since it cannot make an agent worse, but it will only pay for itself if the domain's functional predicates are declared correctly. This is a deployment instruction derived from measurement, and it is the practical output of the framework.

### 5.5 RQ1 and generalization

RQ1 resolves on both benchmarks. P0 staleness is 0.030 on FactConsolidation and 0.052 on MQuAKE-T, with confidence intervals excluding zero. Append-only memory measurably surfaces superseded facts.

Spearman's rho on policy ranking across the two benchmarks is **0.891**. P0 first, P2 second, P4 third and NOMEM last are identical on both. The movement is in the middle:

| Policy | FC rank | MQuAKE-T rank | Explanation |
|---|---|---|---|
| P1 | 6 | 4 | On MQuAKE-T every question is a knowledge update, so the gold fact is always the recent one and TTL pruning removes mostly superseded values. On FactConsolidation only 65 percent of questions are updates, so TTL destroys answerable non-update facts. P1's rank is a property of the workload's update ratio, not of TTL. |
| P5 | 4 | 5 | Corroboration bias against incumbents, section 5.2 |
| P3 | 5 | 6 | Rejected corrections, section 5.3 |

The top and bottom of the ranking are stable; the middle is workload-dependent. This is the framework's own argument. Which forgetting policy wins is an empirical question about a given deployment, and P1 moving two places when the update ratio changes is the clearest demonstration of it in the study.

### 5.6 A judge-reliability audit

Reconciling the ablation against the main run revealed that the ablation's P0 cell produced 96 of 96 byte-identical answers to the main run's P0 cell, yet was scored 0.844 against 0.969. Twelve verdicts flipped, all in one direction, on answers such as:

```
Question: What is the name of the current head of the Australia government?
Gold:     Anthony Albanese
Answer:   Anthony Albanese          judged INCORRECT
```

Auditing every cell for answers whose normalised gold appears verbatim yet were graded incorrect:

| Scope | Verbatim-correct answers | Judged INCORRECT | Rate |
|---|---|---|---|
| FactConsolidation, all cells | 515 | 3 | 0.6 percent |
| MQuAKE-T, all cells | 782 | 12 | 1.5 percent |
| MQuAKE-T ablation, P0 cell alone | 93 | 14 | 15.1 percent |

The baseline judge false-negative rate is 1 to 2 percent, which does not change any conclusion. But one cell drew a poor member of the three-provider judge fallback pool and lost 12.5 accuracy points on verbatim-correct answers. The ablation's P0 = 0.844 is an artifact; the true value is 0.969, which is what section 5.4 reports.

Three consequences follow. Any reported gap smaller than roughly 3 points is inside judge noise, which places the P2 versus P4 comparison on MQuAKE-T (p = 0.549) outside interpretation while leaving sections 5.2 and 5.3 far outside the noise floor at 15 or more points and p < 0.001. Judge rotation is a confound as well as a resilience mechanism, so a judge should be pinned for reported cells or its identity recorded per record. And the verbatim-match audit is worth running as a standing check: it is ten lines and it caught a 12.5-point artifact that would otherwise have been written up as a policy effect.

---

## 6. Threats to validity

1. **Both real-data results come from fact corpora, not conversation.** In both benchmarks facts arrive as clean atomic statements, so extraction never bottlenecks contradiction detection. In conversation it will. P2 requires the extractor to produce the same subject and predicate for a fact and its correction; nothing here tests that under noise.
2. **MQuAKE-T's relations are narrow.** Of 1,868 instances, 1,157 edit head of government and 651 edit head of state, giving 96 distinct supersessions. It is a head-of-office corpus.
3. **FactConsolidation's gold answers are counterfactual**, so its NOMEM floor is maximal by construction.
4. **Sample size is approximately 100 per benchmark.** The P0 versus P2 tie is a clean failure to reject, but cannot distinguish identical from different by up to roughly 8 points. "Statistically tied" is correct; "equal" is not.
5. **Judge noise is 1 to 2 percent with one 15 percent outlier cell** (section 5.6). Differences under roughly 3 points are not interpretable.
6. **NOMEM = 0.000 is prompt-gated**, not evidence of parametric ignorance (section 3.3).
7. **P1's TTL was set relative to synthetic session spacing**, 20 days over 38 daily sessions. Its rank is partly a statement about that choice.
8. **RQ4 is not answered on real data.** The multi-agent harness covers 7 policies across 3 topologies and is validated offline, where P2 leads in all three topologies and every shared-topology invalidation arrives from a different agent than wrote the original fact. The real-data multi-agent campaign has not been run.

---

## 7. Conclusion

Forgetting is not a secondary concern in agent memory. Across two benchmarks with different provenance, the choice of forgetting policy moves accuracy by up to 18 points and staleness by up to 6-fold, over a substrate, retrieval function and judge held constant.

Three claims are supported by replicated, statistically tested evidence. Bitemporal contradiction invalidation is free: it is statistically tied with the accuracy ceiling on both benchmarks while reducing tokens and footprint. Its advantage is attributable to bitemporal semantics specifically, since the structure-aware but time-blind ablation is significantly worse on both accuracy and staleness with a legible mechanism. And novelty-gated writing, currently promoted as an efficiency technique, causes unrecoverable staleness on any workload where facts get corrected.

The practical recommendation is narrow and falsifiable. If an agent tracks facts that get corrected over time, use bitemporal contradiction invalidation, declare the domain's functional predicates, and do not use a novelty write gate. If facts are append-only and never revised, the question does not arise.

The framework's own contribution is that this recommendation is measurable rather than assumed. A policy that was statistically tied with the best on one workload is the worst on another, because the workloads differ in whether facts get corrected. Choosing a forgetting policy without measuring it on the target workload is not a safe default.

### Immediate future work

The highest-value remaining experiment is the multi-agent campaign on MQuAKE-T, which closes RQ4 on the benchmark where the effect is largest, using a harness that is already validated. Beyond that: a conversational benchmark with recoverable supersession annotation would close the extraction-noise gap, and a haystack-size ablation would locate the crossover between the retrieval-bound regime observed on LoCoMo and the policy-bound regime observed here.

---

## References

Local copies of all cited papers are in [`references/`](references/).

1. Packer, C., Fang, V., Patil, S. G., Lin, K., Wooders, S., and Gonzalez, J. E. MemGPT: Towards LLMs as Operating Systems. arXiv:2310.08560, 2023. [`references/2310.08560.pdf`](references/2310.08560.pdf)
2. Rasmussen, P., Paliychuk, P., Beauvais, T., Ryan, J., and Chalef, D. Zep: A Temporal Knowledge Graph Architecture for Agent Memory. arXiv:2501.13956, 2025. [`references/2501.13956.pdf`](references/2501.13956.pdf)
3. Chhikara, P., Khant, D., Aryan, S., Singh, T., and Yadav, D. Mem0: Building Production-Ready AI Agents with Scalable Long-Term Memory. arXiv:2504.19413, 2025. [`references/2504.19413.pdf`](references/2504.19413.pdf)
4. Xu, W., Liang, Z., Mei, K., Gao, H., Tan, J., and Zhang, Y. A-MEM: Agentic Memory for LLM Agents. arXiv:2502.12110, 2025. [`references/2502.12110.pdf`](references/2502.12110.pdf)
5. Zhang, D., Lin, Y., Wu, Z., Sun, Y., Li, B., Li, D., and Peng, H. Useful Memories Become Faulty When Continuously Updated by LLMs. arXiv:2605.12978, 2026. [`references/2605.12978.pdf`](references/2605.12978.pdf)
6. Wang, S., Brahma, D., and Henao, R. SAGE: A Novelty Gate for Efficient Memory Evolution in Agentic LLMs. arXiv:2605.30711, 2026. [`references/2605.30711.pdf`](references/2605.30711.pdf)
7. Chao, H., Bai, Y., Sheng, R., Li, T., and Sun, Y. STALE: Can LLM Agents Know When Their Memories Are No Longer Valid? arXiv:2605.06527, 2026. [`references/2605.06527.pdf`](references/2605.06527.pdf)
8. Patel, V. Supersede: Diagnosing and Training the Memory-Update Gap in LLM Agents. arXiv:2606.27472, 2026. [`references/2606.27472.pdf`](references/2606.27472.pdf)
9. Du, P. Memory for Autonomous LLM Agents: Mechanisms, Evaluation, and Emerging Frontiers. arXiv:2603.07670, 2026. [`references/2603.07670.pdf`](references/2603.07670.pdf)
10. Maharana, A., Lee, D.-H., Tulyakov, S., Bansal, M., Barbieri, F., and Fang, Y. Evaluating Very Long-Term Conversational Memory of LLM Agents. ACL 2024. arXiv:2402.17753. [`references/2402.17753.pdf`](references/2402.17753.pdf)
11. Wu, D., Wang, H., Yu, W., Zhang, Y., Chang, K.-W., and Yu, D. LongMemEval: Benchmarking Chat Assistants on Long-Term Interactive Memory. ICLR 2025. arXiv:2410.10813. [`references/2410.10813.pdf`](references/2410.10813.pdf)
12. Hu, Y., et al. Evaluating Memory in LLM Agents via Incremental Multi-Turn Interactions (MemoryAgentBench). ICLR 2026. arXiv:2507.05257. [`references/2507.05257.pdf`](references/2507.05257.pdf)
13. Zhong, Z., Wu, Z., Manning, C. D., Potts, C., and Chen, D. MQuAKE: Assessing Knowledge Editing in Language Models via Multi-Hop Questions. EMNLP 2023. arXiv:2305.14795. [`references/2305.14795.pdf`](references/2305.14795.pdf)
14. Ren, Z., et al. GateMem: Benchmarking Memory Governance in Multi-Principal Shared-Memory Agents. arXiv:2606.18829, 2026. [`references/2606.18829.pdf`](references/2606.18829.pdf)

---

## Appendix A: reproducing every number in this report

```bash
make install                # editable install with dev and analysis extras
make test                   # 99 offline tests, no API keys

make fc-data && make fc     # FactConsolidation, 14 cells
make mq-data && make mq     # MQuAKE-T, 14 cells
make mq-ablation            # the functional_predicates probe, 3 cells

make figures record dashboard
make compare                # regenerates paper/generalization.md, the tables in 5.1 and 5.5
make replay                 # the P2 versus P3 memory replay used in the defence
```

Real-API runs need keys in `.env`; see `.env.example`. Every call is disk-cached, so a rerun of a completed campaign costs nothing and produces identical output.

## Appendix B: defence artifacts

| Artifact | Path | Use |
|---|---|---|
| Cross-dataset statistics | [`generalization.md`](generalization.md) | Sections 5.1 and 5.5, regenerated by `make compare` |
| Interactive dashboard | [`../artifacts/dashboard.html`](../artifacts/dashboard.html) | Live navigation of every benchmark during a defence |
| Memory replay, P2 vs P3 | [`../artifacts/replays/`](../artifacts/replays/) | Section 5.3 shown as an event rather than a table |
| Evidence packs | `../artifacts/results/*/report_pack/` | Summary tables, radar, per-category, memory views, per-cell graph and replay views |
| Figures | `../artifacts/results/*/figures/` | 300 dpi, section 5.1 |
| Paper-shaped repository map | [`REPO_GUIDE.md`](REPO_GUIDE.md) | Maps each claim to the code that produces it |
