# How related work sets hybrid retrieval weights, and what DRIFT should do

Written in response to the checklist item "complete experiments to determine best
weights for cosine + lexical + recency metrics", and specifically to the
instruction to read the reference papers first before designing the experiment.

All fourteen papers in `paper/thesis/references.bib` were converted to text and
searched for how each one combines retrieval signals and how it chose whatever
parameters that combination needs. Quotes below are from those PDFs.

## 1. What the reference papers actually do

| Paper | How retrieval is scored | How the parameters were chosen |
|---|---|---|
| MemGPT | Pure vector search over archival storage, "performs vector search based on cosine similarity" | No weighting exists, so nothing to tune |
| Zep | Hybrid search over facts, entities and communities, followed by a **reranker**: RRF, MMR, episode mentions, node distance, or a cross-encoder | **RRF is parameter-free.** No weights are reported or tuned |
| Mem0 | Entity-centric lookup plus semantic similarity; a recency window `m` is named as a hyperparameter | Value not reported, no search described |
| A-MEM | Cosine similarity retrieval | Runs a **hyperparameter analysis on k**, reported as analysis rather than tuning |
| MemoryAgentBench | Cosine-similarity RAG baselines, plus a FIFO recency baseline | Benchmark paper, no tuning |
| SAGE | Novelty gate with a density-dependent threshold | **Grid search on a 20 percent subsample of LoCoMo, then frozen** |
| STALE | Survey | Notes hybrid retrievers blending semantic and temporal signals "remain largely unexplored" |
| LoCoMo, LongMemEval | Benchmark papers | Prompt tuning only |
| GateMem, du2026 survey | Retrieval plus reranking | Their "validation set" refers to human validation of an LLM judge, not a hyperparameter split |
| MQuAKE, Supersede, zhang2026 | Not retrieval-fusion papers | n/a |

Three findings follow, and the first is the important one.

**Nobody in this bibliography tunes a weighted hybrid retrieval formula on a
train, validation and test split.** Not one of the fourteen. The question the
committee raised is real, but the field does not currently answer it that way.

**The only grid search anywhere in the bibliography is SAGE's**, and it is worth
quoting exactly because it is the closest available precedent:

> "We selected these via a grid search on Qwen2.5-3B using a 20% subsample of
> LoCoMo, sweeping over tau0 in {0.15, 0.25, 0.35}, taumin in {0.01, 0.025, 0.05},
> lambda in {1.0, 2.0, 4.0}. The configuration tau0 = 0.25, taumin = 0.025,
> lambda = 2.0 was selected and held fixed."

That is: search on a held-out subsample, pick once, freeze for every reported
experiment. SAGE is already implemented in this thesis as policy P3, so citing
its protocol is natural rather than opportunistic.

**Zep, the system closest to DRIFT's substrate, sidesteps weights entirely.** It
fuses ranked lists with Reciprocal Rank Fusion, citing Cormack, Clarke and
Buettcher (SIGIR 2009). RRF scores a document by summing 1 / (k + rank) across
the ranked lists it appears in, with k = 60 by convention. It has no weights, and
because it consumes ranks rather than scores it is immune to the three signals
living on different numeric scales, which is a real problem for the current
formula: cosine sits in roughly [0, 1], lexical overlap is a ratio over query
tokens, and the recency prior is a min-max normalisation whose spread depends
entirely on how long the corpus runs.

Outside the bibliography, the closest work is Hsu and Tzeng's DAT
(arXiv 2503.23013), cited by SAGE, which argues that "fixed weighting schemes
fail to adjust to different queries" and sets the balance per query using an LLM
to score each retriever's top result. That is a genuinely different paradigm and
it is not appropriate here, because an LLM call inside retrieval would contaminate
the controlled design that the whole thesis rests on. It is worth one sentence in
related work and nothing more.

## 2. Why splitting the benchmark will not work

The second option raised was splitting a benchmark into train, validation and
test. That is standard practice and it is the right instinct, but the arithmetic
does not survive contact with these sample sizes.

MQuAKE-T has 96 questions. The split has to be by question, not by observation,
otherwise the same question appears in both train and test under two different
answer models. A conventional 60/20/20 split therefore gives 57 train, 19
validation, 20 test.

Precision of a single accuracy estimate, 95 percent interval half-width, at the
0.969 that P2 actually scores:

| set | n | half-width |
|---|---|---|
| MQuAKE-T, full, both answer models | 192 | 2.5 points |
| FactConsolidation, full, both models | 200 | 2.4 points |
| 60 percent train split | 57 | 4.5 points |
| 20 percent validation split | 19 | 7.8 points |
| 20 percent test split | 20 | 7.6 points |

The judge-reliability audit already established a noise floor of 3 points. A
20-question test set has an interval more than twice that wide before any
comparison is attempted.

Simulated power for a paired McNemar test at alpha 0.05, which is the test this
thesis uses:

| test-set size | detect 3 points | detect 5 points | detect 10 points |
|---|---|---|---|
| 20 | 0% | 0% | 1% |
| 57 | 3% | 9% | 50% |
| 96 | 8% | 23% | 94% |
| 192 | 18% | 54% | 100% |
| 400 | 40% | 87% | 100% |

Eighty percent is the usual minimum for a study to be called adequately powered.
A 20-question test set cannot detect a ten-point difference. Even the full
192-observation benchmark has only 18 percent power at 3 points, which is the
scale the free sweep says the candidate weightings actually differ by.

The conclusion is not that splitting is bad practice. It is that this benchmark
is an order of magnitude too small for it, and a split would produce a confident
looking answer with no evidential content behind it.

## 3. What the free sweep already established

Across all 66 weightings on the simplex, 26 hold gold support at 1.000. Gold
support is a hard ceiling on accuracy, because a memory-only prompt cannot
produce a fact that never reached the context. Within those 26 the composite
score spans 0.562 to 0.594, a range of 0.031, against a judge noise floor of
0.030. The published 0.6 / 0.3 / 0.1 sits inside that group.

The weighting with the single best composite score, 0.3 / 0.4 / 0.3, achieves it
by dropping gold support to 0.927, which caps accuracy roughly seven points below
what P2 currently reaches. Optimising the composite would have made the thesis
worse, which is worth reporting on its own.

## 4. Recommended protocol

Four steps, in order, each of which is either already done or already built.

**Step one, report the sweep as sensitivity, not selection.** This follows A-MEM's
precedent of publishing a hyperparameter analysis. It is complete for MQuAKE-T and
one command away for FactConsolidation.

**Step two, add the weight-free comparison.** Reciprocal rank fusion is now
implemented in `BitemporalGraph.search(fusion="rrf")` and wired into the parameter
search as its own arm. It uses the identical three signals and the same k = 60 as
the original paper, so the only difference is how the signals are combined.

This is the step that changes the shape of the answer. If RRF matches the weighted
formula, the right conclusion is not "0.6 / 0.3 / 0.1 is best" but "the weighting
is unnecessary, and a parameter-free fusion used by the closest comparable system
performs equivalently, so the hyperparameter is removed." That is a stronger
result than picking a winner, and it eliminates the criticism rather than
answering it.

**Step three, select across benchmarks rather than within one.** Tune on
FactConsolidation at full size, 200 observations, freeze, then evaluate once on
MQuAKE-T at full size, 192 observations. Both sets stay whole, so nothing is lost
to splitting, and the transfer between two benchmarks of different provenance is
exactly the generalisation the committee asked about. Follow SAGE's wording:
selected on one corpus, held fixed everywhere else.

**Step four, keep a genuinely untouched test set.** MQuAKE-CF is the cheapest
third benchmark, since `scripts/download_mquake.py` already parses the format, and
it adds multi-hop questions. Selecting on FactConsolidation, validating on
MQuAKE-T and testing once on MQuAKE-CF gives a three-corpus protocol with no
split small enough to be meaningless.

## 5. Expected outcome, stated in advance

The power table says this study cannot resolve differences below roughly five
points between weightings, and the sweep says the surviving candidates differ by
about three. So the most likely result is no significant difference between any
of them, including RRF.

That should be pre-registered rather than discovered, and reported the way the
P2-versus-P0 comparison already is: as a bounded equivalence claim, not a failed
search. "No weighting in the feasible set differs from any other by more than X
points, with a 95 percent interval" is a publishable and honest answer to the
checklist item. It is also the answer the arithmetic predicts before a single
paid call is made.

## 6. What to add to the bibliography

- Cormack, Clarke and Buettcher, "Reciprocal rank fusion outperforms Condorcet
  and individual rank learning methods", SIGIR 2009. Already Zep's reference [20].
- Hsu and Tzeng, "DAT: Dynamic Alpha Tuning for Hybrid Retrieval in
  Retrieval-Augmented Generation", arXiv 2503.23013. One sentence in related work,
  as the per-query alternative this thesis deliberately does not adopt.

## 7. Commands

```bash
make sensitivity-fc          # free, completes the sweep on the second benchmark
make weights-search          # 7 cells: 6 weightings plus the RRF arm, paid
make weights-search-fc       # same on FactConsolidation, for selection
```
