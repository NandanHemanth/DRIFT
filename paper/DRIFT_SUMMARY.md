# DRIFT: a one-page summary

**Nandan Hemanth, Hao Wang** · Stevens Institute of Technology · August 2026
Full report: [`REPORT.md`](REPORT.md) · Code: <https://github.com/nandanhemanth/DRIFT>

---

## The problem

An assistant is told "I live in Boston" and, three months later, "I moved to Seattle". Both facts sit in memory, both are semantically close to "where do I live", and retrieval ranks by similarity and recency. The older fact often returns alongside the newer one, and the agent answers from a value that is no longer true.

This is not a retrieval failure. The correct fact was stored and could be found. It is a memory hygiene failure: nothing marks the older fact as no longer current, and nothing removes it. Existing memory systems (MemGPT, Zep, Mem0, A-MEM) solve storage and retrieval well; the rule that decides what to discard is chosen rather than measured.

## Hypothesis

> Selective forgetting grounded in bitemporal structure improves an agent's answer quality and cost profile relative to both append-only memory and to structure-blind or novelty-based forgetting.

## What DRIFT is and how it tests the hypothesis

DRIFT holds the memory substrate, the fact extractor, the retrieval function, the answer model and the LLM judge constant, and varies **only the forgetting policy** across seven settings: a no-memory floor (NOMEM), append-only memory (P0), TTL decay (P1), bitemporal contradiction invalidation (P2), a novelty write gate (P3), LLM consolidation (P4), and topology consolidation (P5).

The substrate is a bitemporal knowledge graph. Each fact carries the interval during which it was true of the world, the time the agent learned it, and the time a policy removed it. When a new fact arrives on a single-valued predicate, the previous fact's validity window is closed **non-destructively**: the fact stays in memory and stays retrievable. Only a policy hides or deletes it. That separation is what makes the policy the sole independent variable, and it is what licenses attributing any measured difference to the policy rather than to the substrate.

Alongside accuracy, DRIFT reports **staleness**: the fraction of answers that repeat the superseded value.

## Novelty

1. **The forgetting policy isolated as an independent variable.** Published comparisons between memory systems confound the forgetting rule with four other design choices. To our knowledge this is the first controlled study that varies only the rule.
2. **A bitemporal-versus-structure-blind ablation.** P5 is deliberately structure-aware, operates on the same graph, performs the same kind of consolidation, and is denied access to valid time, resolving competing facts by structural corroboration instead. Without it, a result showing P2 beats a flat baseline would only say "graphs help". With it, the claim is specific to bitemporal semantics.
3. **Novelty gating named and measured as a failure mode.** Write-side gating is currently promoted as an efficiency technique. We give the first controlled demonstration that on any workload where facts get corrected it trades a bounded memory saving for an unbounded correctness liability, and demonstrate the mechanism from saved graph snapshots.
4. **A negative result about the standard benchmarks.** LoCoMo (0 of 300 questions) and LongMemEval (0 of 150) carry no superseded-answer annotation and therefore cannot support any measurement of memory revision. We identify two benchmarks that can.

## Results

Two public benchmarks, seven policies, two answer models each, 31 cells. Bootstrap 95 percent CIs with 5,000 resamples; paired McNemar exact tests.

| Policy | FactConsolidation accuracy | MQuAKE-T accuracy | FC staleness | MQ staleness | Tokens/q | Facts kept |
|---|---|---|---|---|---|---|
| NOMEM | 0.000 | 0.000 | 0.000 | 0.000 | 242 | n/a |
| **P0** never forget | **0.840** | **0.969** | 0.030 | 0.052 | 814 | 100% |
| P1 TTL decay | 0.630 | 0.870 | 0.020 | 0.026 | 803 | 55 to 66% |
| **P2** bitemporal | **0.840** | **0.969** | 0.025 | 0.036 | **716** | **85 to 93%** |
| P3 novelty gate | 0.665 | 0.792 | **0.140** | **0.161** | 806 | 88 to 92% |
| P4 LLM consolidation | 0.800 | 0.953 | 0.060 | 0.057 | 809 | 97% |
| P5 topology, time-blind | 0.795 | 0.802 | 0.035 | **0.214** | 814 | 96% |

**Four findings, each replicated on both benchmarks.**

**1. Append-only memory measurably surfaces superseded facts.** P0 retrieves 4.2 to 4.8 stale facts per question out of k = 25, with staleness confidence intervals excluding zero.

**2. Bitemporal forgetting is free.** The paired accuracy difference between P2 and the ceiling is +0.000, with a bootstrap interval of [-0.025, +0.025] on one benchmark and [-0.021, +0.021] on the other. This is a bounded equivalence, not merely a failure to reject. Meanwhile P2 spends **12 percent fewer tokens** per question on both benchmarks and stores 6.5 to 14.7 percent fewer facts.

**3. Novelty gating causes unrecoverable staleness.** P3 raises staleness by 0.115 to 0.125 absolute, p < 0.001 on both. The mechanism is structural: a correction is by construction textually near-identical to the fact it corrects, so a novelty gate rejects it as a duplicate. The correction never enters memory, and no downstream retrieval can recover a value that was never stored. On MQuAKE-T this produces permanent errors such as answering "Elizabeth II" for the current UK head of state.

**4. Bitemporal structure beats structure-blind structure.** On real-world knowledge updates, P2 beats the time-blind ablation by 0.167 accuracy (34 to 2, p < 0.001) and 0.177 staleness (3 to 37, p < 0.001). The mechanism is legible: a long-serving predecessor accumulates more corroborating mentions than a recent successor, so corroboration-count consolidation systematically prefers the outdated fact. Corroboration measures how *established* a fact is, not whether it is *current*.

Cross-benchmark rank agreement is **Spearman rho = 0.891**.

## Short analysis

**Why forgetting can be free.** The intuition that forgetting must cost accuracy assumes all stored information has positive expected value. Bitemporal invalidation removes only facts whose validity window a later observation explicitly closed. Those facts have negative expected value at retrieval time, so removing them yields efficiency without a corresponding cost. TTL decay by contrast removes by age, which is uncorrelated with supersession, and pays for its savings in accuracy. The general principle: a forgetting policy is free to the extent that its removal criterion tracks the information's harmfulness rather than its age or its redundancy.

**Why the ranking is only partly stable.** The top and bottom of the ranking hold across both benchmarks; the middle moves. TTL decay ranks 6th on one benchmark and 4th on the other because the benchmarks differ in what fraction of questions concern a fact that changed. That is the framework's own argument demonstrated: which policy wins is an empirical question about the target workload.

**Two methodological findings** emerged from reconciling runs against one another. An ablation shows that declaring the domain's single-valued predicates buys P2 all of its efficiency and none of its accuracy, so the policy is safe to enable untuned but only pays for itself when configured. And a judge audit found a 12.5-point accuracy artifact on 96 byte-identical answers, caused by a rotating judge pool, establishing a noise floor of 1 to 2 percent below which reported differences are not interpretable.

## Practical output

> If an agent tracks facts that get corrected over time, use bitemporal contradiction invalidation, declare the domain's single-valued predicates, and do not use a novelty write gate. If facts are append-only and never revised, the question does not arise.

DRIFT is released as a dependency-free Python package with a five-line integration surface, so this recommendation can be re-tested on any workload rather than taken on trust. The full pipeline runs offline and deterministically; the test suite is 99 tests in 0.2 seconds with no API key.

## Status and remaining work

Three of four research questions are answered on real data. The fourth, whether the rankings survive multi-agent use, is validated offline on synthetic data only. The multi-agent harness covers seven policies across three topologies and is already built and tested; the outstanding work is a 21-cell run on real data. This is the highest-priority item before submission.
