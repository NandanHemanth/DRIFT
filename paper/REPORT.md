# When Should Agents Forget?

## A Controlled Study of Forgetting Policies in Bitemporal Knowledge-Graph Agent Memory

**Authors:** Nandan Hemanth, Hao Wang
**Affiliation:** Stevens Institute of Technology
**Framework:** DRIFT (Decay and Retention In Forgetful Temporal-graph memory) v1.0.0
**Code, data and artifacts:** [`../README.md`](../README.md)
**Date:** August 2026

> This document is the source text for a conference or journal submission. Every table is computed from the result files in [`../artifacts/results/`](../artifacts/results/) and can be regenerated with the commands in Appendix D. Sections map onto the standard paper structure so that a submission can be assembled by selection rather than rewriting.

---

## Contents

1. [Abstract](#abstract)
2. [Introduction](#1-introduction)
3. [Related work](#2-related-work)
4. [Novelty and positioning](#3-novelty-and-positioning)
5. [Method](#4-method)
6. [Experimental setup](#5-experimental-setup)
7. [Results](#6-results)
8. [Discussion: why the results come out this way](#7-discussion-why-the-results-come-out-this-way)
9. [Impact](#8-impact)
10. [What DRIFT means going forward](#9-what-drift-means-going-forward)
11. [Threats to validity](#10-threats-to-validity)
12. [Limitations and future work](#11-limitations-and-future-work)
13. [Conclusion](#12-conclusion)
14. [References](#references)
15. [Appendices](#appendix-a-complete-per-cell-results)

---

## Abstract

Long-lived language-model agents accumulate memories that go stale. A fact that was true when written is later superseded, but retrieval keeps surfacing it, and the agent answers from a value that no longer holds. Research on agent memory has concentrated on storage and retrieval; the rule that decides what to discard has been treated as an implementation detail rather than as an object of study.

This work isolates that rule. DRIFT holds a bitemporal knowledge-graph substrate, the extraction step, the retrieval function, the answer model and the judge constant, and varies only the forgetting policy across seven settings: a no-memory floor, an append-only baseline, and five forgetting strategies drawn from current systems. We evaluate on two public benchmarks that annotate the superseded answer, which is the annotation the staleness metric requires and which the two most widely used agent-memory benchmarks do not provide.

Four findings replicate across both benchmarks. First, append-only memory measurably surfaces superseded facts, with staleness confidence intervals excluding zero. Second, bitemporal contradiction invalidation is **statistically equivalent** to the accuracy ceiling: the paired accuracy difference is +0.000 with a bootstrap 95 percent interval of [-0.025, +0.025] on one benchmark and [-0.021, +0.021] on the other, while spending 12 percent fewer tokens per question and storing 6.5 to 14.7 percent fewer facts. Third, novelty-gated writing, a popular efficiency technique, increases staleness by 0.115 to 0.125 absolute (p < 0.001 on both), because a correction is textually near-identical to the fact it corrects and is therefore rejected as a duplicate; the correction never enters memory and no downstream retrieval can recover it. Fourth, structure-aware but time-blind consolidation is significantly worse than bitemporal consolidation on real-world knowledge updates, by 0.167 accuracy and 0.177 staleness (both p < 0.001), which attributes the advantage to bitemporal semantics specifically rather than to graph structure in general.

We additionally report two methodological results. An ablation quantifies how much of the reported efficiency depends on correctly declaring which predicates are single-valued: the answer is all of the efficiency and none of the accuracy. And a judge-reliability audit identifies a 12.5-point accuracy artifact produced by a rotating judge pool on byte-identical answers, establishing a noise floor below which reported differences are not interpretable.

The framework is released as a dependency-free, offline-verifiable Python package with a five-line integration surface, so that the central question, which forgetting policy suits a given workload, can be answered empirically rather than by assumption.

---

## 1. Introduction

### 1.1 The problem

Consider an assistant told "I live in Boston" and, three months later, "I moved to Seattle". Both statements are in memory. Both are semantically close to the query "where do I live". A retrieval function ranks by similarity and recency, and the older fact is often retrieved alongside the newer one. The model then produces an answer grounded in a fact whose validity ended.

This is not a retrieval failure. The correct fact was stored and could be found. It is a failure of memory hygiene: nothing in the system marks the older fact as no longer current, and nothing removes it.

The failure compounds with time. An agent that runs for a year accumulates thousands of facts, an increasing fraction of which are superseded. Every superseded fact retrieved is context spent on misinformation, and every one that reaches the answer model is an opportunity to produce a confidently wrong answer about the user's own life.

### 1.2 Why this has not been settled

Production memory systems address the storage and retrieval halves of the problem. MemGPT [1] manages a paged context hierarchy. Zep [2] adds a temporal knowledge graph. Mem0 [3] provides a scalable long-term store. A-MEM [4] organises memory agentically. In each, the treatment of superseded information is secondary, and where a forgetting mechanism exists it is chosen rather than measured.

The reason is partly methodological. Comparing forgetting rules across published systems is confounded: the systems differ in substrate, retrieval, extraction, prompt and model, so an observed difference cannot be attributed to the forgetting rule. What is missing is not another memory system but a controlled comparison.

### 1.3 Hypothesis

> **H.** Selective forgetting grounded in bitemporal structure improves an agent's answer quality and cost profile relative to both append-only memory and to structure-blind or novelty-based forgetting.

### 1.4 Research questions

**RQ1.** Does append-only memory measurably surface superseded facts?

**RQ2.** Which forgetting policy offers the best accuracy, staleness and cost trade-off?

**RQ3.** Does bitemporal structure specifically outperform structure-blind alternatives, or is any graph-aware consolidation sufficient?

**RQ4.** Do the policy rankings survive multi-agent use, where the reader is not the writer?

### 1.5 Contributions

1. **A controlled experimental framework** in which the forgetting policy is the only independent variable over a fixed substrate, retrieval function, extraction step, answer model and judge (Section 4).
2. **A staleness metric separated from accuracy**, together with the finding that the two most-used agent-memory benchmarks cannot support it, and the identification of two that can (Section 5.1).
3. **Replicated evidence on two benchmarks of different provenance** that bitemporal invalidation is free, that novelty gating causes unrecoverable staleness, and that time-blind consolidation is significantly worse than bitemporal consolidation (Section 6).
4. **An equivalence result, not merely a null result.** Paired bootstrap intervals bound the accuracy difference between bitemporal invalidation and the ceiling to within ±2.5 points (Section 6.4).
5. **A configuration ablation** separating the contribution of the policy from the contribution of a domain declaration (Section 6.8).
6. **A judge-reliability audit** establishing a noise floor for LLM-judged accuracy under a rotating judge pool (Section 6.9).
7. **An open, dependency-free implementation** that runs offline in 0.2 seconds and integrates into a third-party agent in five lines (Appendix E).

---

## 2. Related work

### 2.1 Agent memory systems

**MemGPT** [1] introduced operating-system-style paging for context, treating the context window as physical memory and external storage as disk. **Zep** [2] built a temporal knowledge graph for agent memory and is the closest architectural relative of DRIFT's substrate; it records fact validity intervals but does not compare policies for acting on them. **Mem0** [3] targets production deployment with a scalable long-term store. **A-MEM** [4] organises memory agentically, with an LLM deciding memory structure.

All four are systems contributions. None isolates the forgetting rule for controlled comparison, and none reports a metric separating staleness from accuracy.

### 2.2 Consolidation and its risks

Zhang et al. [5] show that memories consolidated by repeated LLM rewriting degrade over time, and that utility can fall below a no-memory baseline. Their headline observation, that GPT-5.4 fails on 54 percent of ARC-AGI problems it had previously solved without memory once consolidation is applied, motivates treating LLM consolidation as a policy under test rather than as an assumed improvement. It is P4 in our taxonomy.

### 2.3 Write-side control

Wang et al. [6] propose SAGE, a write-side novelty gate using a von Mises-Fisher density estimator over memory embeddings, routing clearly novel facts to ADD, clearly redundant ones to NOOP, and only uncertain cases to an LLM merge. They report a 3.4-fold reduction in add-phase API cost. This is the technique our P3 policy models, and Section 6.6 reports a failure mode that follows from its design rather than from its implementation.

### 2.4 Staleness as a first-class problem

Chao et al. [7] introduce STALE, a benchmark for whether agents recognise that a stored belief is outdated, identifying implicit conflict as an underexplored failure mode. Patel [8] frames the same gap as a memory-update problem and studies training-time remedies. Du [9] surveys the field and identifies evaluation of memory revision as an open frontier.

Our contribution is complementary and orthogonal. Rather than asking whether a model can detect staleness, or training it to, we ask which forgetting policy prevents staleness from arising in the first place, holding the model fixed.

### 2.5 Benchmarks

LoCoMo [10] and LongMemEval [11] are the standard agent-memory benchmarks, covering long conversational histories with multi-hop and temporal questions. Neither annotates the superseded answer; see Section 5.1. MemoryAgentBench [12] contains a FactConsolidation split constructed so that later facts overwrite earlier ones on the same subject and predicate. MQuAKE [13] provides knowledge-editing instances that ship both the pre-edit and post-edit answer. GateMem [14] studies memory governance in multi-principal shared memory, which is the setting of RQ4.

---

## 3. Novelty and positioning

The novelty of this work is not a memory architecture. Bitemporal modelling is decades old in database research, and Zep [2] has already applied it to agent memory. The novelty is fourfold and lies in the experimental design and in what that design makes visible.

**N1. The forgetting policy as an isolated independent variable.** To our knowledge this is the first study that holds the substrate, extraction, retrieval function, answer model and judge fixed and varies only the forgetting rule, across a taxonomy spanning no-memory, append-only, time-based decay, contradiction-based invalidation, novelty gating, LLM consolidation and topology consolidation. Published comparisons between memory systems confound the forgetting rule with four other design choices.

**N2. The bitemporal-versus-structure-blind ablation.** P5 is designed for one purpose: it is structure-aware, operates on the same graph, performs the same kind of consolidation, and is deliberately denied access to valid time, resolving competing facts by structural corroboration instead. This isolates the contribution of bitemporal semantics from the contribution of graph structure. Without P5, a result showing that P2 beats a flat baseline would be consistent with "graphs help" and would say nothing about temporality. With P5, the claim is specific and, on real-world updates, decisive (Section 6.5).

**N3. Novelty gating as a named, measured failure mode.** Write-side gating is currently promoted as an efficiency technique [6]. We give the first controlled demonstration that on any workload where facts get corrected it trades a bounded memory saving for an unbounded correctness liability, and we demonstrate the mechanism from saved graph snapshots rather than hypothesising it (Section 6.6). The claim transfers beyond DRIFT: it follows from the definition of a novelty gate and the textual form of a correction, not from our implementation.

**N4. A negative result about the standard benchmarks.** The observation that LoCoMo and LongMemEval carry zero superseded-answer annotations, and therefore cannot support any measurement of memory revision, is itself a contribution to how this subfield evaluates. We report the trap we fell into, the diagnostic, and two benchmarks that do support the metric (Section 5.1).

To these we add two methodological results that were not planned and emerged from reconciling runs against each other: the configuration ablation (Section 6.8) and the judge-reliability audit (Section 6.9).

---

## 4. Method

### 4.1 The substrate

Every fact is a `(subject, predicate, object)` triple carrying two timelines and a lifecycle marker:

| Field | Meaning |
|---|---|
| `t_valid_start` | when the fact became true of the world |
| `t_invalid_at` | when the fact stopped being true, `null` while current |
| `t_ingested` | when the agent learned it |
| `t_pruned` | when a policy removed it, `null` while retained |
| `provenance` | which agent wrote it |
| `active` | `false` once pruned |

When a new fact arrives on a **functional predicate**, one that admits a single true object at a time, the previous fact's valid-time window is closed by setting `t_invalid_at`. This closing is **non-destructive**: the fact remains in memory and remains retrievable. Only a policy removes or hides data.

That separation is the methodological core of the design. It guarantees that any difference between two experimental cells is attributable to the policy, because the substrate behaves identically in all of them.

**Speech-act guard.** Predicates such as `stated`, `said`, `mentioned` and `reported` are excluded from contradiction handling even when all predicates are declared functional. Without this guard, a degenerate extraction in which every line returns as `speaker / stated / <whole line>` causes every fact to contradict its predecessor. We measured 379 of 380 facts invalidated on a corpus whose true count is 133. The failure is silent and resembles a policy result, which is why it is worth reporting.

### 4.2 The pipeline

```
session lines
    -> extract_facts()            LLM triple extraction + deterministic regex upgrade
    -> policy.on_write()          write gate
    -> BitemporalGraph            contradiction closes the superseded valid window
    -> policy.after_session()     periodic maintenance
    -> graph.search()             0.6 cosine + 0.3 lexical + 0.1 recency, k = 25
    -> policy.on_retrieve()       retrieval filter or rerank
    -> answer model
    -> LLM judge (different family) + token-F1
```

A policy is defined by exactly three hooks. Adding one is a subclass and a registry entry; the runner, substrate, providers and analysis code never learn about it.

```python
class Policy:
    def on_write(self, fact: dict, graph) -> bool: ...        # False rejects the write
    def after_session(self, graph, provider, now: float): ... # periodic maintenance
    def on_retrieve(self, facts: list, now: float) -> list:   # filter or rerank
```

### 4.3 Policies under test

| ID | Name | Mechanism | Hooks used | Source |
|---|---|---|---|---|
| NOMEM | No memory | Retrieval returns nothing | `on_retrieve` | floor baseline |
| P0 | No forgetting | Append-only; nothing gated, pruned or filtered | none | ceiling baseline |
| P1 | TTL decay | Prune facts older than `ttl_days` by valid time | `after_session` | classical |
| P2 | Contradiction invalidation | Exclude superseded facts at retrieval; prune after a 7-day grace period | `on_retrieve`, `after_session` | bitemporal, after [2] |
| P3 | Novelty gate | Reject writes whose neighbourhood cosine exceeds tau = 0.9 | `on_write` | after SAGE [6] |
| P4 | LLM consolidation | Every third session an LLM decides keep or drop, plus deterministic near-duplicate merge | `after_session` | after [5] |
| P5 | Topology consolidation | Resolve competing facts by structural corroboration count; deliberately time-blind | `after_session` | ablation partner to P2 |

**On NOMEM as a baseline.** The answer prompt instructs the model to respond "I don't know" when memory lacks the answer, and NOMEM's records are almost entirely that string, including for facts the model plainly knows. NOMEM therefore measures memory-gated answering, not parametric ignorance. The P0-minus-NOMEM gap should be read as the value of memory under an instruction to ground answers in memory. A consequence worth stating: NOMEM's staleness of 0.000 is trivially achieved by refusing to answer, so staleness is only interpretable among policies that actually answer.

**On P5 as an ablation.** P5 builds the entity co-occurrence graph, finds communities by label propagation, and within each community resolves competing facts on the same subject and predicate by keeping whichever object is corroborated by the most other facts in memory. High-degree entities are protected from pruning below a floor. It has access to everything P2 has except valid time.

### 4.4 Metrics

**Accuracy.** An LLM judge from a different model family than the answer model returns CORRECT or INCORRECT against the gold answer. Judges are drawn from a three-provider fallback pool; Section 6.9 audits the consequences.

**Staleness.** The fraction of answers containing the superseded value, computed as a substring test against the `stale_answer` annotation:

```python
def staleness_hit(answer, stale_answer):
    return bool(stale_answer) and stale_answer.lower() in answer.lower()
```

Staleness fires only on annotated questions, so a benchmark's annotation coverage bounds what this metric can report. This is not a minor caveat; see Section 5.1.

**Token-F1.** Unigram overlap between answer and gold, reported alongside accuracy because it is judge-independent. It penalises verbosity, which is why the two answer models differ sharply on F1 while agreeing on accuracy.

**Cost.** Mean tokens per question at answer time, and the count of active facts retained.

**Retrieved-invalidated.** The mean number of superseded facts appearing in each retrieval. This is the mechanism variable: it is 0.00 for P2 by construction and 4.2 to 5.4 for the policies that do not filter.

### 4.5 Statistics

- **Bootstrap 95 percent confidence intervals**, percentile method, 5,000 resamples.
- **Paired McNemar exact test** for policy comparisons, using the exact two-sided binomial on discordant pairs. The same questions go to every policy, so an unpaired test would overstate significance.
- **Paired bootstrap on the difference** for effect sizes. This is stronger than comparing two overlapping intervals and is what turns a failure to reject into a bounded equivalence claim.
- **Spearman's rho** on policy rankings for cross-benchmark agreement.

---

## 5. Experimental setup

### 5.1 Benchmark selection, and a negative result about the standard benchmarks

The staleness metric requires each question to be annotated with the value a stale memory would return. Auditing the candidate benchmarks:

| Benchmark | Conversations | Sessions | Lines | Questions | With `stale_answer` | Coverage |
|---|---|---|---|---|---|---|
| LoCoMo [10] | 10 | 272 | 5,882 | 300 | 0 | **0 percent** |
| LongMemEval [11] | n/a | n/a | n/a | 150 | 0 | **0 percent** |
| LongMemEval knowledge-update, LLM-annotated | 78 | 156 | 1,830 | 78 | 1 | **1 percent** |
| MemoryAgentBench FactConsolidation [12] | 1 | 38 | 380 | 100 | 65 | **65 percent** |
| MQuAKE-T [13] | 1 | 38 | 382 | 96 | 96 | **100 percent** |
| Synthetic smoke (offline) | 2 | 10 | 28 | 14 | 4 | 29 percent |

On the first campaign, staleness read exactly 0.000 across all 42 single-agent cells. This was briefly read as a finding. It was not: the metric could not fire, because the annotation it depends on does not exist in those datasets.

We report this because the same trap is available to anyone measuring memory revision on LoCoMo or LongMemEval, and because the diagnostic is simple. Any staleness result should be accompanied by the annotation coverage of its source data. Our cross-dataset tool prints coverage automatically for this reason.

An attempt to recover the annotation for LongMemEval's knowledge-update questions using an LLM annotator produced 1 usable annotation out of 78, despite the superseded values appearing in plain text in the evidence turns ("27:12", "$350,000", "twice a week"). Deterministic recovery from dataset structure, which is what both converters used here do, is the more reliable route.

### 5.2 The two benchmarks used

**FactConsolidation** (MemoryAgentBench [12], ICLR 2026). A numbered fact list in which later facts overwrite earlier ones on the same subject and predicate, with the gold answer always the latest value. The superseded value is recoverable without an annotator by tracking the previous object of whichever pair resolves to the gold answer. Facts are atomic triples, so contradiction detection is not extractor-limited. Gold answers are counterfactual ("rugby union was created in India"), so parametric knowledge is actively unhelpful.

**MQuAKE-T** (MQuAKE [13], EMNLP 2023). Built by diffing Wikidata snapshots from April 2021 against April 2023 and retaining relations whose change is a genuine real-world update. Each instance ships the pre-edit answer alongside the post-edit answer, so the annotation is deterministic. Selected as the generalization test because its updates are **real rather than injected**, which breaks the most artificial property of FactConsolidation while holding the task form fixed.

The conversion is sized to match FactConsolidation cell for cell:

| Property | FactConsolidation | MQuAKE-T |
|---|---|---|
| Sessions | 38 | 38 |
| Fact lines | 380 | 382 |
| Questions | 100 | 96 |
| `stale_answer` coverage | 65 percent | 100 percent |
| Policies x answer models | 7 x 2 = 14 cells | 7 x 2 = 14 cells |
| Question-answers pooled | 200 | 192 |

Two conversion decisions are load-bearing and should be defended explicitly in any submission.

**Randomised supersession placement.** For each edited pair, the old value is placed in a uniformly random session *i* and the new value in a uniformly random session *j > i*, rather than blocking all old facts into an early half and all new facts into a late half. A clean boundary would let any policy win by learning that later sessions dominate, without using bitemporal structure at all. That is exactly the confound the P2 versus P5 ablation exists to rule out.

**Flat statement phrasing.** Edited facts are restated in compact subject-predicate-object form ("The head of government of New York City is Eric Adams") rather than MQuAKE's cloze ("The name of the current head of the New York City government is"). Contradiction detection keys on the subject and predicate as the *extractor* produces them, and a wordier frame introduces extraction variance on the one join the entire experiment depends on. The alternative phrasing is retained behind a flag so the trade-off can be measured.

### 5.3 Models and infrastructure

| Role | Models |
|---|---|
| Answer | GLM-5.2, MiniMax-M3 (via OpenRouter) |
| Extraction | GLM-5.2, MiniMax-M3, gpt-oss-120b, Llama-3.3-70B, Llama-3.1-8B, Mistral Small (rotated per conversation) |
| Judge | gpt-oss:20b (local), gpt-oss-20b (hosted), Command-R7B (rotated per conversation) |
| Embedding | `nomic-embed-text` served locally by Ollama, 768 dimensions |
| Retrieval depth | k = 25 |

Extraction and judging rotate across providers to spread volume over independent rate limits. Section 6.9 shows that judge rotation is also a confound, and recommends pinning.

### 5.4 Reproducibility

- Every provider call is cached on disk by SHA-256 of `(provider, model, prompt, temperature, max_tokens)`. An interrupted campaign resumes at zero cost and a rerun is bit-for-bit reproducible.
- One result file per experiment cell; completed cells are skipped on resume.
- Failures are caught per cell, so one exhausted quota costs a cell rather than a campaign.
- `MockProvider` and `HashingEmbedder` run the entire pipeline offline and deterministically. The full test suite is 99 tests in 0.2 seconds with no API key and no network, so the mechanics can be verified independently of the reported results.
- The core package declares zero dependencies.

---

## 6. Results

### 6.1 Headline table

Pooled across both answer models. Percentile bootstrap 95 percent CIs, 5,000 resamples. n = 200 question-answers on FactConsolidation, 192 on MQuAKE-T.

| Policy | FC accuracy | MQuAKE-T accuracy | FC staleness | MQuAKE-T staleness | FC tok/q | MQ tok/q | FC facts | MQ facts |
|---|---|---|---|---|---|---|---|---|
| NOMEM | 0.000 [.000, .000] | 0.000 [.000, .000] | 0.000 | 0.000 | 250 | 233 | n/a | n/a |
| **P0** | **0.840** [.785, .890] | **0.969** [.943, .990] | 0.030 [.010, .055] | 0.052 [.021, .089] | 812 | 816 | 380 | 382 |
| P1 (TTL 20 d) | 0.630 [.565, .695] | 0.870 [.823, .917] | 0.020 [.005, .040] | 0.026 [.005, .052] | 799 | 807 | 210 | 251 |
| **P2** | **0.840** [.785, .890] | **0.969** [.943, .990] | 0.025 [.005, .050] | 0.036 [.010, .068] | **715** | **716** | **324** | **357** |
| P3 | 0.665 [.600, .730] | 0.792 [.729, .849] | **0.140** [.095, .190] | **0.161** [.109, .214] | 806 | 805 | 334 | 351 |
| P4 | 0.800 [.745, .855] | 0.953 [.922, .979] | 0.060 [.030, .095] | 0.057 [.026, .094] | 814 | 804 | 374 | 372 |
| P5 | 0.795 [.735, .850] | 0.802 [.745, .854] | 0.035 [.010, .060] | **0.214** [.156, .276] | 812 | 816 | 365 | 365 |

Figures: [`accuracy_staleness.png`](../artifacts/results/mquake_t/figures/accuracy_staleness.png) plots this table; [`tradeoff_scatter.png`](../artifacts/results/mquake_t/figures/tradeoff_scatter.png) places each policy in accuracy-staleness space; [`token_cost.png`](../artifacts/results/mquake_t/figures/token_cost.png) plots the cost column. FactConsolidation equivalents are in [`../artifacts/results/factconsolidation/figures/`](../artifacts/results/factconsolidation/figures/).

### 6.2 Effect sizes with paired bootstrap intervals

Comparing two overlapping confidence intervals is weak evidence. The table below bootstraps the **paired per-question difference**, which is the correct estimator when every policy sees the same questions.

| Benchmark | Comparison | Metric | Delta | 95 percent CI | Excludes 0 |
|---|---|---|---|---|---|
| FC | P2 minus P0 | accuracy | **+0.000** | [-0.025, +0.025] | no |
| FC | P2 minus P0 | staleness | -0.005 | [-0.035, +0.025] | no |
| FC | P2 minus P3 | accuracy | +0.175 | [+0.120, +0.230] | **yes** |
| FC | P2 minus P3 | staleness | -0.115 | [-0.165, -0.070] | **yes** |
| FC | P2 minus P5 | accuracy | +0.045 | [+0.015, +0.080] | **yes** |
| FC | P2 minus P5 | staleness | -0.010 | [-0.040, +0.015] | no |
| FC | P2 minus P4 | accuracy | +0.040 | [+0.005, +0.080] | **yes** |
| FC | P2 minus P1 | accuracy | +0.210 | [+0.150, +0.270] | **yes** |
| FC | P0 minus NOMEM | accuracy | +0.840 | [+0.790, +0.890] | **yes** |
| MQ | P2 minus P0 | accuracy | **+0.000** | [-0.021, +0.021] | no |
| MQ | P2 minus P0 | staleness | -0.016 | [-0.047, +0.016] | no |
| MQ | P2 minus P3 | accuracy | +0.177 | [+0.120, +0.240] | **yes** |
| MQ | P2 minus P3 | staleness | -0.125 | [-0.182, -0.073] | **yes** |
| MQ | **P2 minus P5** | **accuracy** | **+0.167** | **[+0.109, +0.224]** | **yes** |
| MQ | **P2 minus P5** | **staleness** | **-0.177** | **[-0.240, -0.120]** | **yes** |
| MQ | P2 minus P4 | accuracy | +0.016 | [-0.016, +0.047] | no |
| MQ | P2 minus P1 | accuracy | +0.099 | [+0.057, +0.146] | **yes** |
| MQ | P0 minus NOMEM | accuracy | +0.969 | [+0.943, +0.990] | **yes** |

This is the strongest form of the RQ2 result. The accuracy difference between P2 and the ceiling is not merely non-significant; it is **bounded within ±2.5 points on one benchmark and ±2.1 points on the other**. That is an equivalence claim, and it is what licenses the phrase "forgetting is free".

### 6.3 RQ1: append-only memory surfaces superseded facts

P0 staleness is 0.030 [0.010, 0.055] on FactConsolidation and 0.052 [0.021, 0.089] on MQuAKE-T. Both intervals exclude zero. Averaged over its retrievals, P0 surfaces **4.20 superseded facts per question** on FactConsolidation and **4.80** on MQuAKE-T, out of k = 25.

The mechanism variable makes this concrete:

| Policy | FC retrieved-invalidated | MQ retrieved-invalidated |
|---|---|---|
| NOMEM | 0.00 | 0.00 |
| P0 | 4.20 | 4.80 |
| P1 | 2.08 | 3.28 |
| **P2** | **0.00** | **0.00** |
| P3 | 3.91 | 3.94 |
| P4 | 4.24 | 4.64 |
| P5 | 4.12 to 4.16 | 5.31 to 5.43 |

P2 is 0.00 by construction, since its retrieval hook excludes facts whose valid window has closed. P5 is the highest on MQuAKE-T at 5.31 to 5.43, which is the numerical signature of the failure analysed in Section 6.5.

RQ1 is answered affirmatively on both benchmarks.

### 6.4 RQ2: bitemporal invalidation is free

**Accuracy.** P2 matches P0 exactly on both benchmarks: 0.840 against 0.840, and 0.969 against 0.969. Paired McNemar returns 3 to 3 (p = 1.000) and 2 to 2 (p = 1.000). The paired difference intervals in Section 6.2 bound the gap to within ±2.5 points.

**Cost.**

| Benchmark | P0 tok/q | P2 tok/q | Saved | P0 facts | P2 facts | Fewer |
|---|---|---|---|---|---|---|
| FactConsolidation | 812 | 715 | **12.0 percent** | 380 | 324 | **14.7 percent** |
| MQuAKE-T | 816 | 716 | **12.2 percent** | 382 | 357 | **6.5 percent** |

The token saving replicates to within 0.2 percentage points across two benchmarks of different provenance. The footprint saving differs because the two corpora have different supersession densities, which is the expected behaviour: P2 prunes exactly the facts that were superseded and then aged past the grace period.

**No other policy achieves both.** P1 stores far less (210 and 251 facts) but loses 0.210 and 0.099 accuracy. P3 and P5 shrink memory modestly and lose accuracy and gain staleness. P4 is close on accuracy but saves nothing.

RQ2 is answered: P2.

### 6.5 RQ3: bitemporal structure beats structure-blind structure

This is the ablation the design exists to support, and it is the strongest result in the study.

P2 and P5 share the substrate, the retrieval function, the extraction step, the answer model and the judge. Both are structure-aware. Both consolidate. The only difference is that P2 knows which fact is current from valid time, and P5 must infer it from corroboration count.

**On MQuAKE-T:**

| Metric | P2 | P5 | Paired delta | McNemar | p |
|---|---|---|---|---|---|
| Accuracy | 0.969 | 0.802 | +0.167 [+0.109, +0.224] | 34 to 2 | **< 0.001** |
| Staleness | 0.036 | 0.214 | -0.177 [-0.240, -0.120] | 3 to 37 | **< 0.001** |
| Retrieved-invalidated | 0.00 | 5.31 to 5.43 | | | |

P5's staleness is **5.9 times** P2's.

**The failures are the predicted ones.** Fifteen questions where P5 returned the superseded value and P2 did not:

| Question | Gold, current as of the snapshot | P5 answered | P2 answered |
|---|---|---|---|
| Head of state, South Korea | Yoon Suk-yeol | Moon Jae-in | Yoon Suk-yeol |
| Head of government, Czech Republic | Petr Fiala | Andrej Babiš | Petr Fiala |
| Head of state, Czech Republic | Petr Pavel | Miloš Zeman | Petr Pavel |
| Head of government, Malawi | Lazarus Chakwera | Peter Mutharika | Lazarus Chakwera |
| Head of state, Malawi | Lazarus Chakwera | Peter Mutharika | Lazarus Chakwera |
| Head of government, South Korea | Yoon Suk-yeol | Moon Jae-in | Yoon Suk-yeol |

**The mechanism.** A long-serving predecessor accumulates more corroborating mentions across the memory graph than a recent successor. Corroboration-count consolidation therefore systematically prefers the outdated fact. Recency is not a proxy for correctness, but valid time is a proxy for currency, and that distinction is exactly what the substrate encodes and what P5 is denied.

**Why this is sharper than on FactConsolidation.** There the same comparison was p = 0.022 on accuracy and inconclusive on staleness (3 to 5, p = 0.727). FactConsolidation's entities are arbitrary Wikidata pairs with roughly uniform corroboration, so P5's heuristic fails at random and the effect is small and noisy. MQuAKE-T's entities are real people holding real offices, so corroboration is **systematically biased toward the incumbent of record**, and the heuristic fails in a consistent direction. The second benchmark did not merely replicate the finding; it exposed the mechanism.

RQ3 is answered: the advantage is attributable to bitemporal semantics specifically.

### 6.6 Novelty gating causes unrecoverable staleness

P3 shows 4.7 times P2's staleness on FactConsolidation (0.140 against 0.025) and 4.5 times on MQuAKE-T (0.161 against 0.036), both at p < 0.001, with paired deltas of -0.115 and -0.125.

**The mechanism is structural, not statistical.** A fact update is by construction textually near-identical to the fact it supersedes:

```
"Thomas Kyd was born in the city of London"     stored
"Thomas Kyd was born in the city of Leeds"      the correction
```

A novelty gate computes neighbourhood cosine similarity, sees a near-duplicate, and rejects the write. The correction never enters memory. No downstream retrieval, reranking or prompting can recover a value that was never stored.

**Verified from saved graph snapshots**, not hypothesised. On FactConsolidation, 46 write rejections produced 24 subject-predicate pairs where P0 recorded the update and P3 retained only the superseded value. On MQuAKE-T, 31 write rejections produced 14 questions answered from a stale value that P0 got right:

| Question | Gold | P3 retained |
|---|---|---|
| Head of state, United Kingdom | Charles, Prince of Wales | Elizabeth II |
| Head of state, South Korea | Yoon Suk-yeol | Moon Jae-in |
| Headquarters city, Scientific American | Los Angeles | New York City |
| Head of state, Mongolia | Khurelsukh Ukhnaa | Khaltmaagiin Battulga |
| Headquarters city, Apax Partners | Paris | London |

**This is the most transferable claim in the study**, because it follows from the definition of a novelty gate rather than from our implementation of one. The rate will differ across corpora; the failure mode will not. Any workload where facts get corrected inherits it.

The asymmetry is what makes it serious. The saving is bounded: P3 retained 334 and 351 facts against P0's 380 and 382, a 12 percent and 8 percent reduction. The liability is unbounded: the wrong value persists indefinitely and cannot be corrected by any later mechanism.

### 6.7 Generalization across benchmarks

**Spearman's rho on policy ranking: 0.891** over seven policies.

| Policy | FC rank | MQuAKE-T rank | Stable | Explanation of movement |
|---|---|---|---|---|
| P0 | 1 | 1 | yes | |
| P2 | 2 | 2 | yes | |
| P4 | 3 | 3 | yes | |
| P5 | 4 | 5 | no | Corroboration bias against incumbents (Section 6.5) |
| P3 | 5 | 6 | no | Rejected corrections (Section 6.6) |
| P1 | 6 | 4 | **no, moves two places** | See below |
| NOMEM | 7 | 7 | yes | |

**P1's movement is the most informative result in this table.** On MQuAKE-T every question is a knowledge update, so the gold fact is always the recent one and TTL pruning removes mostly superseded values. On FactConsolidation only 65 percent of questions are updates, so TTL destroys answerable non-update facts. **P1's rank is a property of the workload's update ratio, not a property of TTL policies.**

The top and bottom of the ranking are stable; the middle is workload-dependent. This is not a weakness of the study. It is the study's own argument, demonstrated: which forgetting policy wins is an empirical question about the target workload, and P1 moving two places when the update ratio changes is the cleanest available demonstration.

### 6.8 Ablation: how much of the result is a configuration choice?

The `functional_predicates` setting declares which predicates admit a single true object. FactConsolidation required it to be set to "all predicates", and that choice was made while looking at that dataset, which makes it the largest threat to external validity in the study. We therefore reran MQuAKE-T with the setting left at the substrate default, a personal-conversation set that covers none of MQuAKE-T's relations. Invalidations drop from 59 to 1, switching P2's mechanism off.

| Cell | Declared | Not declared | Change |
|---|---|---|---|
| P2 accuracy | 0.969 | 0.969 | none |
| P2 tokens per question | **641** | 733 | +14.4 percent |
| P2 active facts | **357** | 382 | +7.0 percent |
| P2 retrieved-invalidated | 0.00 | 0.00 | none |
| P0 accuracy | 0.969 | 0.969 (corrected, see 6.9) | none |
| P3 accuracy | 0.802 | 0.802 | none, as expected |
| Graph invalidations | 59 | 1 | mechanism off |

**The setting buys P2 nothing in accuracy and all of its efficiency.**

This is a more useful result than either "the flag matters" or "the flag does not matter". It decomposes the claim: P2 is **safe to enable untuned**, because it cannot make an agent worse than append-only memory, but it **only pays for itself** if the domain's functional predicates are declared. That is a deployment instruction derived from measurement.

### 6.9 A judge-reliability audit

While reconciling the ablation against the main run we found that the ablation's P0 cell produced **96 of 96 byte-identical answers** to the main run's P0 cell, yet was scored 0.844 against 0.969. Twelve verdicts flipped, all in one direction, on answers such as:

```
Question: What is the name of the current head of the Australia government?
Gold:     Anthony Albanese
Answer:   Anthony Albanese          judged INCORRECT
```

Auditing every cell for answers whose normalised gold appears verbatim yet were graded incorrect:

| Scope | Verbatim-correct answers | Judged INCORRECT | Rate |
|---|---|---|---|
| FactConsolidation, all cells | 515 | 3 | **0.6 percent** |
| MQuAKE-T, all cells | 782 | 12 | **1.5 percent** |
| MQuAKE-T ablation, P0 cell alone | 93 | 14 | **15.1 percent** |

The baseline judge false-negative rate is 1 to 2 percent, which does not change any conclusion. But one cell drew a poor member of the three-provider judge fallback pool and lost 12.5 accuracy points on verbatim-correct answers. **The ablation's P0 = 0.844 is an artifact; the true value is 0.969**, which is what Section 6.8 reports.

Three consequences:

1. **Any reported gap smaller than roughly 3 points is inside judge noise.** This places P2 versus P4 on MQuAKE-T (delta +0.016, p = 0.549) outside interpretation, while leaving Sections 6.5 and 6.6 far outside the noise floor at 16.7 and 17.7 points with p < 0.001.
2. **Judge rotation is a confound as well as a resilience mechanism.** The fallback pool exists so a dead provider does not kill a campaign, but it means two cells can be graded by different judges. Pin one judge for reported cells, or record judge identity per record so this is auditable rather than archaeological.
3. **The verbatim-match audit is worth running as a standing check.** It is ten lines of code and it caught a 12.5-point artifact that would otherwise have been written up as a policy effect.

We report this in full because it is a class of error that is easy to commit and hard to detect, and because the LLM-as-judge methodology is now standard across this subfield.

### 6.10 RQ4: multi-agent topologies, validated offline

The multi-agent harness runs seven policies across three topologies over the same substrate and policies:

| Topology | Structure | What it isolates |
|---|---|---|
| shared | 5 writer agents round-robin into one graph, each fact tagged with its writer | Write contention: contradictions now arrive from a different agent than wrote the original |
| independent | 5 agents with private graphs, each seeing a seeded random 80 percent of sessions | Robustness under partial observation |
| orchestrator | One shared graph, a router LLM assigns each question to one of 5 specialist workers | The production coordinator-worker pattern, where the reader is not the writer |

Results on synthetic data with the offline provider, 14 questions per cell:

| Policy | shared acc/stale | independent acc/stale | orchestrator acc/stale | Cross-writer invalidations |
|---|---|---|---|---|
| NOMEM | 0.000 / 0.000 | 0.000 / 0.000 | 0.000 / 0.000 | 5 |
| P0 | 0.714 / 0.286 | 0.667 / 0.286 | 0.714 / 0.286 | 5 |
| P1 (TTL 14 d) | 0.143 / 0.000 | 0.143 / 0.000 | 0.143 / 0.000 | 3 |
| **P2** | **0.929 / 0.000** | **0.881 / 0.000** | **0.929 / 0.000** | 5 |
| P3 | 0.714 / 0.286 | 0.667 / 0.286 | 0.714 / 0.286 | 5 |
| P4 | 0.714 / 0.286 | 0.667 / 0.286 | 0.714 / 0.286 | 5 |
| P5 | 0.500 / 0.143 | 0.548 / 0.095 | 0.500 / 0.071 | 4 |

P2 leads in all three topologies and holds staleness at 0.000 in all three. Every shared-topology invalidation arrives **cross-writer**, that is, the contradicting fact was written by a different agent than wrote the original, which is evidence that structure-aware forgetting is writer-agnostic by construction.

**This is validation, not a result.** n = 14 questions with a deterministic mock provider. RQ4 is not answered on real data, and this is the study's most consequential gap (Section 11).

### 6.11 Memory growth

Active fact count at session checkpoints, GLM-5.2 cells:

**FactConsolidation**

| Policy | s1 | s10 | s20 | s30 | s38 |
|---|---|---|---|---|---|
| P0 | 10 | 100 | 200 | 300 | 380 |
| P1 | 10 | 100 | 200 | 210 | 210 |
| P2 | 10 | 100 | 189 | 270 | 324 |
| P3 | 10 | 98 | 185 | 273 | 334 |
| P4 | 10 | 96 | 195 | 294 | 374 |
| P5 | 10 | 100 | 198 | 291 | 365 |

**MQuAKE-T**

| Policy | s1 | s10 | s20 | s30 | s38 |
|---|---|---|---|---|---|
| P0 | 1 | 74 | 169 | 276 | 382 |
| P1 | 1 | 74 | 169 | 209 | 251 |
| P2 | 1 | 74 | 165 | 266 | 357 |
| P3 | 1 | 74 | 164 | 264 | 351 |
| P4 | 1 | 74 | 166 | 266 | 369 |
| P5 | 1 | 74 | 168 | 271 | 365 |

Plotted in [`memory_growth.png`](../artifacts/results/mquake_t/figures/memory_growth.png).

Two observations. P1's curve flattens abruptly once the TTL horizon is reached, which is why its accuracy collapses: it is discarding answerable facts wholesale rather than selectively. P2 tracks P0 closely and diverges gradually, which is the shape of a policy that removes only what has genuinely been superseded.

### 6.12 Complete pairwise significance matrix

All 21 policy pairs, both metrics, both benchmarks. Counts are discordant pairs; p is the exact two-sided binomial. Significance markers: `*` p < 0.05, `**` p < 0.01, `***` p < 0.001.

**FactConsolidation**

| Comparison | Accuracy | p | Staleness | p |
|---|---|---|---|---|
| NOMEM vs P0 | 0-168 | <0.001 *** | 0-6 | 0.031 * |
| NOMEM vs P1 | 0-126 | <0.001 *** | 0-4 | 0.125 |
| NOMEM vs P2 | 0-168 | <0.001 *** | 0-5 | 0.062 |
| NOMEM vs P3 | 0-133 | <0.001 *** | 0-28 | <0.001 *** |
| NOMEM vs P4 | 0-160 | <0.001 *** | 0-12 | <0.001 *** |
| NOMEM vs P5 | 0-159 | <0.001 *** | 0-7 | 0.016 * |
| P0 vs P1 | 44-2 | <0.001 *** | 4-2 | 0.688 |
| **P0 vs P2** | **3-3** | **1.000** | **5-4** | **1.000** |
| P0 vs P3 | 36-1 | <0.001 *** | 1-23 | <0.001 *** |
| P0 vs P4 | 8-0 | 0.008 ** | 1-7 | 0.070 |
| P0 vs P5 | 9-0 | 0.004 ** | 0-1 | 1.000 |
| P1 vs P2 | 1-43 | <0.001 *** | 2-3 | 1.000 |
| P1 vs P3 | 34-41 | 0.489 | 2-26 | <0.001 *** |
| P1 vs P4 | 5-39 | <0.001 *** | 2-10 | 0.039 * |
| P1 vs P5 | 9-42 | <0.001 *** | 1-4 | 0.375 |
| P2 vs P3 | 36-1 | <0.001 *** | 1-24 | <0.001 *** |
| P2 vs P4 | 11-3 | 0.057 | 4-11 | 0.118 |
| P2 vs P5 | 11-2 | 0.022 * | 3-5 | 0.727 |
| P3 vs P4 | 9-36 | <0.001 *** | 24-8 | 0.007 ** |
| P3 vs P5 | 8-34 | <0.001 *** | 23-2 | <0.001 *** |
| P4 vs P5 | 9-8 | 1.000 | 7-2 | 0.180 |

**MQuAKE-T**

| Comparison | Accuracy | p | Staleness | p |
|---|---|---|---|---|
| NOMEM vs P0 | 0-186 | <0.001 *** | 0-10 | 0.002 ** |
| NOMEM vs P1 | 0-167 | <0.001 *** | 0-5 | 0.062 |
| NOMEM vs P2 | 0-186 | <0.001 *** | 0-7 | 0.016 * |
| NOMEM vs P3 | 0-152 | <0.001 *** | 0-31 | <0.001 *** |
| NOMEM vs P4 | 0-183 | <0.001 *** | 0-11 | <0.001 *** |
| NOMEM vs P5 | 0-154 | <0.001 *** | 0-41 | <0.001 *** |
| P0 vs P1 | 20-1 | <0.001 *** | 6-1 | 0.125 |
| **P0 vs P2** | **2-2** | **1.000** | **6-3** | **0.508** |
| P0 vs P3 | 38-4 | <0.001 *** | 4-25 | <0.001 *** |
| P0 vs P4 | 5-2 | 0.453 | 3-4 | 1.000 |
| P0 vs P5 | 34-2 | <0.001 *** | 2-33 | <0.001 *** |
| P1 vs P2 | 1-20 | <0.001 *** | 2-4 | 0.688 |
| P1 vs P3 | 35-20 | 0.058 | 2-28 | <0.001 *** |
| P1 vs P4 | 6-22 | 0.004 ** | 2-8 | 0.109 |
| P1 vs P5 | 32-19 | 0.092 | 0-36 | <0.001 *** |
| P2 vs P3 | 38-4 | <0.001 *** | 4-28 | <0.001 *** |
| P2 vs P4 | 7-4 | 0.549 | 4-8 | 0.388 |
| **P2 vs P5** | **34-2** | **<0.001 ***** | **3-37** | **<0.001 *****|
| P3 vs P4 | 6-37 | <0.001 *** | 24-4 | <0.001 *** |
| P3 vs P5 | 23-25 | 0.885 | 19-29 | 0.193 |
| P4 vs P5 | 36-7 | <0.001 *** | 5-35 | <0.001 *** |

Note that NOMEM appearing to "win" on staleness against every policy is an artifact of refusing to answer. Staleness is only interpretable among policies that answer.

### 6.13 Per-model breakdown

Policy effects are not an idiosyncrasy of one answer model. Both models rank the policies identically.

| Policy | FC GLM-5.2 | FC MiniMax-M3 | MQ GLM-5.2 | MQ MiniMax-M3 |
|---|---|---|---|---|
| NOMEM | 0.000 | 0.000 | 0.000 | 0.000 |
| P0 | 0.860 | 0.820 | 0.969 | 0.969 |
| P1 | 0.650 | 0.610 | 0.865 | 0.875 |
| P2 | 0.850 | 0.830 | 0.969 | 0.969 |
| P3 | 0.680 | 0.650 | 0.802 | 0.781 |
| P4 | 0.820 | 0.780 | 0.958 | 0.948 |
| P5 | 0.820 | 0.770 | 0.823 | 0.781 |

Token-F1 diverges sharply between the models (for example 0.973 against 0.622 for P0 on MQuAKE-T) because MiniMax-M3 answers verbosely and F1 penalises length. Accuracy, which is judged semantically, agrees. This divergence is itself a small methodological note: token-F1 should not be used as a primary metric for models with different verbosity profiles.

Plotted in [`model_comparison.png`](../artifacts/results/mquake_t/figures/model_comparison.png).

---

## 7. Discussion: why the results come out this way

### 7.1 Why forgetting can be free

The intuition that forgetting must cost accuracy assumes that all stored information has positive expected value. Bitemporal invalidation violates that assumption in a specific way: it removes only facts whose valid-time window has closed, that is, facts that a later observation has explicitly contradicted. Those facts have **negative** expected value at retrieval time, because surfacing them can only produce a stale answer.

This explains the shape of the result. P2 does not trade accuracy for efficiency. It removes information that was already harmful, so the efficiency gain arrives without a corresponding cost. P1 by contrast removes facts by age, which is uncorrelated with whether they have been superseded, so it destroys useful and harmful information indiscriminately and pays for its savings in accuracy.

The general principle: **a forgetting policy is free to the extent that its removal criterion correlates with the information's harmfulness rather than with its age or its redundancy.**

### 7.2 Why novelty gating fails, structurally

A novelty gate makes an inference from textual similarity to informational redundancy. That inference holds for genuine duplicates and fails precisely for corrections, because a correction is a minimal edit of the thing it corrects. The gate's discriminative signal is inversely aligned with the case that matters most.

This is not a tuning problem. Lowering tau admits more duplicates and does not distinguish a correction from a restatement, because the two are textually indistinguishable at the embedding level. Distinguishing them requires exactly the structure the gate does not consult: whether the new fact shares a subject and predicate with an existing fact and differs in the object. That is the bitemporal contradiction test.

The two policies are therefore not merely different points on a trade-off curve. They are **inverses**: both shrink memory, but P2 preserves the ability to be corrected and P3 destroys it.

### 7.3 Why corroboration count is a bad currency proxy

P5's heuristic asks which of two competing values the rest of memory agrees with. On a corpus of real entities, agreement accumulates with tenure. A head of state who served eight years appears in more contexts than one who took office last year. The heuristic therefore has a systematic bias toward the past, in exactly the setting where currency matters.

Generalising: **structural corroboration measures how established a fact is, not whether it is current.** Those two quantities are positively correlated for stable facts and negatively correlated for facts undergoing revision, which is the subset a forgetting policy exists to handle.

### 7.4 Why the two benchmarks disagree in the middle of the ranking

FactConsolidation and MQuAKE-T differ on one axis that turns out to matter: the fraction of questions that concern a fact that changed. On MQuAKE-T it is 100 percent by construction. On FactConsolidation it is 65 percent.

Policies whose removal criterion is aligned with supersession (P2) are insensitive to this ratio. Policies whose criterion is unaligned (P1, which removes by age) are highly sensitive: when every question is about a recent change, removing old facts is harmless, and when a third of questions are about stable facts, it is destructive.

This yields a practical diagnostic. **Estimate the update ratio of your workload before choosing a policy.** A high ratio makes crude policies look good; a low ratio exposes them.

---

## 8. Impact

### 8.1 For research

**A measurement instrument for a subfield that currently reasons by assertion.** The comparison DRIFT performs is not available from published results, because published memory systems differ on five dimensions at once. Making the forgetting rule separable is a precondition for accumulating knowledge about it.

**A correction to the evaluation practice of this subfield.** The finding that LoCoMo and LongMemEval cannot support any measurement of memory revision affects every paper that claims to evaluate memory updating on them. The associated recommendation, that any staleness or revision result be reported with its annotation coverage, costs nothing and prevents a specific and easy error.

**A noise floor for LLM-as-judge evaluation under provider rotation.** Rotating judge pools are common practice for cost and rate-limit reasons. We show they introduce a confound of up to 12.5 points on identical answers, and give a ten-line detector.

**A named failure mode with a mechanism.** Write-gate-induced staleness now has a name, a controlled measurement, a demonstrated mechanism and reproducible evidence. Future work on write-side control can cite it as a constraint to design against rather than rediscovering it.

### 8.2 For practice

The engineering recommendation is narrow, measured and falsifiable:

> If an agent tracks facts that get corrected over time, use bitemporal contradiction invalidation, declare the domain's functional predicates, and do not use a novelty write gate. If facts are append-only and never revised, the question does not arise.

Three properties make this actionable rather than aspirational.

**It is free at the margin.** P2 is statistically equivalent to append-only memory on accuracy while reducing token spend by 12 percent. In a deployed assistant serving many sessions, the token saving is a direct cost reduction with no measured quality cost.

**It fails safe.** The ablation shows that a wrongly configured P2 degrades to P0, not below it. An engineer can enable it without a tuning campaign and without risk.

**It names the thing that must be configured.** `functional_predicates` is the one setting that determines whether P2 pays for itself. This is a single, inspectable list of predicate names, not a hyperparameter requiring search.

The framework itself lowers the cost of not taking our word for it. Exporting a workload into the schema, writing a config, and running four policies is an afternoon, and the result is specific to the deployment rather than to our benchmarks.

### 8.3 For the broader technology trajectory

Agents are moving from single-session tools to persistent systems that accumulate state over months. Three consequences follow from this work.

**Memory hygiene becomes a correctness problem, not an efficiency problem.** The dominant framing of memory management is cost: context is expensive, so store less. This work shows the correctness axis is larger. The gap between the best and worst policy is 18 accuracy points and a 6-fold staleness difference, while the cost differences are around 12 percent. Optimising memory for size while ignoring currency optimises the smaller quantity.

**Efficiency techniques need correctness audits.** Novelty gating reduces write-phase cost by 3.4-fold [6]. It also, on corrected-fact workloads, produces permanent errors. This pattern, where an efficiency technique carries an unbounded correctness liability that is invisible on benchmarks lacking the relevant annotation, is likely to recur as agent systems are optimised. The general lesson is that efficiency evaluations should include a workload where the optimisation's assumption is violated.

**The right-to-be-forgotten and auditability requirements point the same direction.** A bitemporal store records when each fact was learned, when it stopped being true and when it was removed. That is the structure regulatory deletion and provenance requirements need, and it is the same structure that makes forgetting free. Systems that treat memory as an undifferentiated vector store will have to retrofit it.

**Reproducibility at low cost is achievable.** The framework is dependency-free, its entire pipeline runs offline deterministically, its test suite completes in 0.2 seconds, and every API call is content-addressed and cached. This is a demonstration that agent-memory research does not require a large compute budget to be rigorous, which matters for who can participate in it.

---

## 9. What DRIFT means going forward

### 9.1 As an artifact

DRIFT is not a memory library competing with Mem0 or Zep. It is **a harness for choosing a forgetting policy before committing to one**, plus a reference implementation of the policy that won. The argument for why that choice needs measuring rather than assuming is in the results: P3 was statistically tied with the best policy on the first campaign and is the worst policy on both fact benchmarks, because the workloads differ in whether facts get corrected.

The intended usage is: export your agent's real history, annotate the questions whose answers changed, run four policies, ship the winner. Adding a policy is a subclass and one registry line; adding a benchmark is a converter and a config.

### 9.2 Immediate roadmap

Ordered by value per unit of effort.

| Priority | Work | Why | Cost |
|---|---|---|---|
| 1 | **Multi-agent campaign on MQuAKE-T** | RQ4 is answered offline only. The harness already covers 7 policies x 3 topologies and is validated. This closes the last open research question on the benchmark where the effect is largest. | 21 cells |
| 2 | **Judge pinning and per-record judge identity** | Section 6.9. Removes a known confound from every future number. | free |
| 3 | **A conversational benchmark with recoverable supersession** | The missing third regime. Would close the extraction-noise gap, which is the largest threat to validity. Requires deterministic annotation recovery, not an LLM annotator. | new converter + 14 cells |
| 4 | **Multi-hop MQuAKE-T** | The converter already supports it via one flag. Tests whether the ranking holds when the answer changes as an entailed consequence rather than by direct lookup. | 14 cells |
| 5 | **Haystack-size ablation** | FactConsolidation ships 32k, 64k and 262k context variants. LoCoMo is retrieval-bound and these benchmarks are policy-bound; locating the crossover would characterise when policy choice stops mattering. | 14 cells per size |
| 6 | **`show_supersession` ablation** | Answers "is the value in the policy, or in telling the model?" A reviewer will ask. | 14 cells |

### 9.3 Longer-term research directions the framework enables

**Learned forgetting policies.** The three-hook interface is a policy API. A policy whose `on_retrieve` is a learned ranker, or whose `after_session` is a learned pruner, drops into the same harness and is compared under identical conditions. The current seven policies are a benchmark for such work.

**Policy composition.** Nothing in the design prevents combining hooks from different policies, for example P2's retrieval filter with P4's periodic consolidation. The current results suggest the combination is worth testing: P2 and P4 are statistically indistinguishable on MQuAKE-T accuracy but use disjoint mechanisms.

**Memory governance in multi-principal settings.** GateMem [14] frames shared-memory agents as a governance problem. DRIFT's `provenance` field and cross-writer invalidation counter provide the instrumentation to study whether forgetting policies need to be writer-aware.

**Adversarial memory.** A superseded fact retrieved is a small case of memory poisoning. The same substrate and metric extend to injected false memories, where the question becomes whether a forgetting policy can be made to remove adversarial writes without removing legitimate corrections. The P2 versus P3 asymmetry suggests these objectives are in tension.

**Deletion and compliance.** `t_pruned` and `provenance` give the audit trail that right-to-be-forgotten requirements need. Whether policy-driven forgetting can be made to satisfy a formal deletion guarantee is an open question the substrate is positioned to study.

---

## 10. Threats to validity

Stated in full, in order of severity.

1. **Both real-data results come from fact corpora, not conversation.** In both benchmarks facts arrive as clean atomic statements, so extraction never bottlenecks contradiction detection. In conversation it will. P2 requires the extractor to produce the same subject and predicate for a fact and its correction; nothing here tests that under noise. This is the single largest limit on the generality of the result.

2. **MQuAKE-T's relations are narrow.** Of 1,868 instances, 1,157 edit head of government and 651 edit head of state, giving 96 distinct supersessions. It is a head-of-office corpus. It tests real-versus-injected drift, not breadth of relation type.

3. **FactConsolidation's gold answers are counterfactual**, so its NOMEM floor of 0.000 is maximal by construction and the memory-versus-no-memory gap is the largest the design can produce.

4. **Sample size is approximately 100 questions per benchmark.** The paired difference intervals bound the P2-versus-P0 gap to ±2.5 points, which is a meaningful equivalence claim, but a smaller true difference would not be detectable.

5. **Judge noise is 1 to 2 percent with one 15 percent outlier cell** (Section 6.9). Differences under roughly 3 points are not interpretable. This affects the P2 versus P4 comparison specifically.

6. **NOMEM = 0.000 is prompt-gated**, not evidence of parametric ignorance (Section 4.3). Its staleness of 0.000 is achieved by refusing to answer.

7. **P1's TTL was set relative to synthetic session spacing**, 20 days over 38 daily sessions. Its rank is partly a statement about that choice, and Section 6.7 shows its rank is workload-dependent regardless.

8. **RQ4 is not answered on real data** (Section 6.10).

9. **`functional_predicates` was chosen per dataset.** Section 6.8 quantifies the consequence, which is that the setting controls all of P2's efficiency and none of its accuracy. It remains a per-domain configuration burden.

10. **Two answer models, both accessed through one provider.** Policy rankings agree across them (Section 6.13), but both are recent mid-size instruction-tuned models and neither is a frontier model.

---

## 11. Limitations and future work

The threats above translate into a work programme. The three that would most change the paper's standing:

**Close RQ4 on real data.** One of four research questions is currently validated only on 14 synthetic questions with a mock provider. This is the most likely single reason for a reviewer to reject, and the harness is already built and tested. Estimated cost: 21 cells.

**Add the conversational regime.** The extraction-noise threat cannot be addressed by any amount of additional work on fact corpora. It requires a conversational benchmark with recoverable supersession annotation, which does not currently exist and which our LongMemEval attempt failed to produce with an LLM annotator. Building one deterministically is a contribution in its own right.

**Broaden the relation types.** Both benchmarks are Wikidata-derived and MQuAKE-T is narrow. A workload with genuinely multi-valued predicates would test whether the functional-predicate declaration scales beyond hand-listing.

Beyond these, the P2-and-P4 composition, learned policies, and the adversarial-memory extension described in Section 9.3 are the directions the framework most naturally supports.

---

## 12. Conclusion

Forgetting is not a secondary concern in agent memory. Across two benchmarks of different provenance, the choice of forgetting policy moves accuracy by up to 18 points and staleness by up to 6-fold, over a substrate, retrieval function, answer model and judge held constant. The cost differences between policies are around 12 percent. The correctness differences are an order of magnitude larger.

Four claims are supported by replicated, statistically tested evidence:

1. **Append-only memory measurably surfaces superseded facts**, at 4.2 to 4.8 stale facts per retrieval, with staleness intervals excluding zero.
2. **Bitemporal contradiction invalidation is free.** Its accuracy difference from the ceiling is bounded within ±2.5 points on one benchmark and ±2.1 on the other, while it spends 12 percent fewer tokens and stores 6.5 to 14.7 percent fewer facts.
3. **The advantage is attributable to bitemporal semantics specifically**, not to graph structure in general. The structure-aware but time-blind ablation is worse by 0.167 accuracy and 0.177 staleness on real-world updates, both p < 0.001, with a legible mechanism: corroboration count is a measure of how established a fact is, not of whether it is current.
4. **Novelty-gated writing causes unrecoverable staleness**, replicated across injected and real supersessions, with the mechanism demonstrated from saved graph snapshots. It follows from the definition of a novelty gate rather than from any implementation of one.

Two methodological findings accompany them: the configuration ablation, which decomposes P2's benefit into an accuracy component that is unconditional and an efficiency component that is contingent on a domain declaration; and the judge-reliability audit, which establishes a noise floor and identifies a 12.5-point artifact on byte-identical answers.

The framework's own contribution is that these recommendations are measurable rather than assumed. A policy that was statistically tied with the best on one workload is the worst on another, because the workloads differ in whether facts get corrected. Choosing a forgetting policy without measuring it on the target workload is not a safe default, and the cost of measuring it is now an afternoon.

---

## References

Local copies of all cited papers are in [`references/`](references/). Every citation below was verified against the retrieved PDF.

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

BibTeX for all fourteen is in [`drift_paper.bib`](drift_paper.bib).

---

## Appendix A: complete per-cell results

Every cell that was run. Accuracy CIs are percentile bootstrap, 5,000 resamples, per cell (n = 100 or 96).

### A.1 FactConsolidation, 14 cells

| Policy | Model | Accuracy | 95 percent CI | F1 | Staleness | Tok/q | Active | Inval | Pruned | Rejected | Retr-inval |
|---|---|---|---|---|---|---|---|---|---|---|---|
| NOMEM | MiniMax-M3 | 0.000 | [.000, .000] | 0.000 | 0.000 | 316 | 380 | 92 | 0 | 0 | 0.00 |
| NOMEM | GLM-5.2 | 0.000 | [.000, .000] | 0.000 | 0.000 | 184 | 380 | 92 | 0 | 0 | 0.00 |
| P0 | MiniMax-M3 | 0.820 | [.740, .890] | 0.555 | 0.060 | 871 | 380 | 92 | 0 | 0 | 4.20 |
| P0 | GLM-5.2 | 0.860 | [.790, .930] | 0.644 | 0.000 | 754 | 380 | 92 | 0 | 0 | 4.20 |
| P1 | MiniMax-M3 | 0.610 | [.510, .710] | 0.382 | 0.030 | 842 | 210 | 27 | 170 | 0 | 2.08 |
| P1 | GLM-5.2 | 0.650 | [.550, .740] | 0.461 | 0.010 | 756 | 210 | 27 | 170 | 0 | 2.08 |
| P2 | MiniMax-M3 | 0.830 | [.750, .900] | 0.490 | 0.050 | 772 | 324 | 36 | 56 | 0 | 0.00 |
| P2 | GLM-5.2 | 0.850 | [.770, .920] | 0.608 | 0.000 | 657 | 324 | 36 | 56 | 0 | 0.00 |
| P3 | MiniMax-M3 | 0.650 | [.560, .740] | 0.413 | 0.160 | 865 | 334 | 67 | 0 | 46 | 3.91 |
| P3 | GLM-5.2 | 0.680 | [.580, .770] | 0.528 | 0.120 | 748 | 334 | 67 | 0 | 46 | 3.91 |
| P4 | MiniMax-M3 | 0.780 | [.700, .860] | 0.530 | 0.100 | 874 | 374 | 92 | 6 | 0 | 4.24 |
| P4 | GLM-5.2 | 0.820 | [.740, .890] | 0.611 | 0.020 | 753 | 374 | 92 | 6 | 0 | 4.24 |
| P5 | MiniMax-M3 | 0.770 | [.680, .850] | 0.515 | 0.070 | 870 | 365 | 87 | 15 | 0 | 4.16 |
| P5 | GLM-5.2 | 0.820 | [.740, .890] | 0.643 | 0.000 | 754 | 365 | 86 | 15 | 0 | 4.12 |

### A.2 MQuAKE-T, 14 cells

| Policy | Model | Accuracy | 95 percent CI | F1 | Staleness | Tok/q | Active | Inval | Pruned | Rejected | Retr-inval |
|---|---|---|---|---|---|---|---|---|---|---|---|
| NOMEM | MiniMax-M3 | 0.000 | [.000, .000] | 0.003 | 0.000 | 311 | 382 | 59 | 0 | 0 | 0.00 |
| NOMEM | GLM-5.2 | 0.000 | [.000, .000] | 0.003 | 0.000 | 156 | 382 | 59 | 0 | 0 | 0.00 |
| P0 | MiniMax-M3 | 0.969 | [.927, 1.000] | 0.622 | 0.094 | 897 | 382 | 59 | 0 | 0 | 4.80 |
| P0 | GLM-5.2 | 0.969 | [.927, 1.000] | 0.973 | 0.010 | 734 | 382 | 59 | 0 | 0 | 4.80 |
| P1 | MiniMax-M3 | 0.875 | [.802, .938] | 0.569 | 0.031 | 885 | 251 | 39 | 131 | 0 | 3.28 |
| P1 | GLM-5.2 | 0.865 | [.792, .927] | 0.870 | 0.021 | 729 | 251 | 39 | 131 | 0 | 3.28 |
| P2 | MiniMax-M3 | 0.969 | [.927, 1.000] | 0.623 | 0.062 | 791 | 357 | 34 | 25 | 0 | 0.00 |
| P2 | GLM-5.2 | 0.969 | [.927, 1.000] | 0.990 | 0.010 | 641 | 357 | 34 | 25 | 0 | 0.00 |
| P3 | MiniMax-M3 | 0.781 | [.698, .865] | 0.442 | 0.177 | 883 | 351 | 44 | 0 | 31 | 3.94 |
| P3 | GLM-5.2 | 0.802 | [.719, .875] | 0.832 | 0.146 | 727 | 351 | 44 | 0 | 31 | 3.94 |
| P4 | MiniMax-M3 | 0.948 | [.896, .990] | 0.628 | 0.094 | 883 | 374 | 56 | 8 | 0 | 4.79 |
| P4 | GLM-5.2 | 0.958 | [.917, .990] | 0.960 | 0.021 | 725 | 369 | 53 | 13 | 0 | 4.64 |
| P5 | MiniMax-M3 | 0.781 | [.698, .865] | 0.537 | 0.260 | 907 | 365 | 57 | 17 | 0 | 5.43 |
| P5 | GLM-5.2 | 0.823 | [.750, .896] | 0.819 | 0.167 | 725 | 365 | 56 | 17 | 0 | 5.31 |

### A.3 MQuAKE-T ablation, 3 cells

`functional_predicates` omitted, so the substrate default applies and covers none of MQuAKE-T's relations.

| Policy | Model | Accuracy | F1 | Staleness | Tok/q | Active | Inval | Rejected |
|---|---|---|---|---|---|---|---|---|
| P0 | GLM-5.2 | 0.844 (artifact, true 0.969) | 0.973 | 0.010 | 734 | 382 | 1 | 0 |
| P2 | GLM-5.2 | 0.969 | 0.980 | 0.010 | 733 | 382 | 1 | 0 |
| P3 | GLM-5.2 | 0.802 | 0.832 | 0.146 | 727 | 351 | 0 | 31 |

### A.4 LoCoMo, partial

The LoCoMo matrix is 2 of 30 cells complete. Reported for the regime contrast only, not as a result.

| Policy | Model | Accuracy | Staleness | Tok/q | Note |
|---|---|---|---|---|---|
| NOMEM | MiniMax-M3 | 0.037 | 0.000 | 311 | staleness structurally cannot fire, 0/300 annotated |
| NOMEM | GLM-5.2 | 0.037 | 0.000 | 183 | as above |

Per-category NOMEM accuracy: temporal 0.000, single-hop 0.031, multi-hop 0.047, adversarial 0.060, open-domain 0.067. Note that unlike the fact corpora, NOMEM is non-zero here, because LoCoMo's questions are about a fictional conversation the model can occasionally guess.

---

## Appendix B: figure index

All figures are 300 dpi PNG, regenerated by `make figures record`.

| Figure | Path | Shows | Supports |
|---|---|---|---|
| Accuracy and staleness | `artifacts/results/{fc,mquake_t}/figures/accuracy_staleness.png` | Grouped bars per policy | Section 6.1 |
| Trade-off scatter | `.../figures/tradeoff_scatter.png` | Accuracy against staleness, one point per policy | Section 6.4 |
| Memory growth | `.../figures/memory_growth.png` | Active facts over sessions | Section 6.11 |
| Token cost | `.../figures/token_cost.png` | Mean tokens per question | Section 6.4 |
| Model comparison | `.../figures/model_comparison.png` | Per-model policy ranking | Section 6.13 |
| Policy radar | `.../report_pack/radar_policies.png` | All policies across all metrics | overview figure |
| Baseline versus DRIFT | `.../report_pack/baseline_vs_drift.png` | NOMEM and P0 against the forgetting policies | Section 6.3 |
| Architecture | `.../report_pack/architecture.png` | Pipeline diagram | Section 4.2 |
| Swarm topology | `artifacts/results/swarm_smoke/figures/swarm_topology.png` | Per-topology comparison | Section 6.10 |
| Swarm variance | `.../swarm_smoke/figures/swarm_variance.png` | Mean and standard deviation across independent agents | Section 6.10 |

Interactive artifacts:

| Artifact | Path | Use |
|---|---|---|
| Dashboard | [`../artifacts/dashboard.html`](../artifacts/dashboard.html) | Self-contained, tabs for every benchmark |
| Memory replay | [`../artifacts/replays/`](../artifacts/replays/) | Scrubbable P2-versus-P3 timeline; shows Section 6.6 as an event |
| Per-cell graphs | `artifacts/results/*/report_pack/graphs/*.graph.html` | The snapshots that established the P3 finding |
| Per-cell replays | `artifacts/results/*/report_pack/graphs/*.replay.html` | Per-cell scrubbable timeline |

---

## Appendix C: the dataset schema

Any workload can be evaluated by emitting this structure.

```json
{"conversations": [{
  "id": "user-42",
  "sessions":  [{"time": 1704067200.0,
                 "lines": ["user: I moved to Seattle.", "assistant: Noted."]}],
  "questions": [{"question": "Where does the user live?",
                 "answer": "Seattle",
                 "category": "knowledge_update",
                 "stale_answer": "Boston"}]
}]}
```

`stale_answer` is what the staleness metric needs. Accuracy works without it; staleness cannot fire without it. Recover it deterministically from the data's structure rather than with an LLM annotator; see Section 5.1.

---

## Appendix D: reproducing every number in this report

```bash
make install                # editable install with dev and analysis extras
make test                   # 99 offline tests, no API keys, no network

make fc-data && make fc     # FactConsolidation, 14 cells   -> Appendix A.1
make mq-data && make mq     # MQuAKE-T, 14 cells            -> Appendix A.2
make mq-ablation            # configuration probe, 3 cells   -> Section 6.8, A.3

make figures record dashboard
make compare                # Sections 6.1, 6.7 -> paper/generalization.md
make replay                 # Section 6.6 as a scrubbable timeline
make swarm                  # Section 6.10, offline
```

Real-API runs need keys in `.env`; see `.env.example`. Every call is disk-cached by SHA-256, so a rerun of a completed campaign costs nothing and produces identical output.

---

## Appendix E: using DRIFT in another agent

```python
import time
from drift import Memory

mem = Memory(
    policy="P2",
    provider="openrouter:z-ai/glm-5.2",
    embedder="ollama:nomic-embed-text",
    functional_predicates=["lives_in", "works_at", "assigned_to", "status"],
)

mem.observe(["user: I moved to Seattle."], when=time.time())
memory_block = mem.context("Where does the user live?", k=8)
```

`tests/test_memory_api.py` pins that this facade makes fact-for-fact identical decisions to the experimental harness running the same policy, which is what licenses reading the measured results as advice about the library.

Adding a policy is a subclass and one registry line:

```python
class P6MyPolicy(Policy):
    name = "P6_my_policy"
    def on_write(self, fact, graph) -> bool: return True
    def after_session(self, graph, provider, now): ...
    def on_retrieve(self, facts, now): return facts

POLICY_REGISTRY["P6"] = P6MyPolicy
```

---

## Appendix F: submission checklist

Practical notes for assembling a submission from this document.

| Target | Suggested selection | Length |
|---|---|---|
| Full archival paper (8 to 9 pages) | Abstract, 1, 2, 3, 4, 5, 6.1 to 6.9, 7, 10, 12, references. Move 6.10 to 6.13 and Appendix A to supplementary. | ~9 pages |
| Short paper (4 pages) | Abstract, 1.1 to 1.4, 4.1 to 4.3, 5.1 to 5.2, 6.1, 6.2, 6.5, 6.6, 10, 12 | ~4 pages |
| Journal (TMLR, TACL) | Everything, with Appendix A inline rather than supplementary. TMLR in particular rewards the completeness of Sections 6.9 and 10. | unbounded |
| Poster or student track | 6.1, 6.5, 6.6 with the two failure-mode tables, plus the replay artifact | 2 pages |

**What to lead with.** Section 6.5 (the bitemporal-versus-time-blind ablation) is the strongest result and the one that isolates the specific claim. Section 6.6 (novelty gating) is the most transferable and the most likely to be cited by others. Section 5.1 (the benchmark negative result) is the most surprising to reviewers who work in this area. Lead with those three, not with the framework.

**What to disclose prominently.** Sections 6.9 and 10. Reporting a judge artifact you found in your own results, and eight specific threats to validity, is stronger than having a reviewer find them.

**What must be fixed first.** RQ4 (Section 6.10) is validated offline only. This is the single easiest thing to reject on, and the harness is already built.
