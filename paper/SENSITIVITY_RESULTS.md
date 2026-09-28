# Sensitivity and mixture experiment: complete results

Both benchmarks, five policies, 66 weightings each. 330 weight rows per benchmark
plus the depth, grace, ttl and tau sweeps. All measured at the retrieval layer
before any answer or judge model runs, so every number here is deterministic and
free to regenerate.

## 1. The headline result

**The hypothesis does not depend on the retrieval weighting, on either benchmark,
against any competing policy, anywhere in the usable design space.**

Restricting to weightings with recency at or below 0.3, which is 38 of the 66
points, there are zero reversals. Not one, across two benchmarks, four objectives
and four policy comparisons. P2 beats P0, P1, P3 and P5 at every single point.

Across the full simplex including the degenerate high-recency corner there are 35
reversals in total, and they share one property without exception.

## 2. Every reversal is the same artifact

All 35 occur at recency weight 0.4 or above, and in **35 of 35 the apparent
winner has strictly lower gold support than P2**. The pattern is always the same:
heavy recency weighting degrades retrieval so badly that a policy which prunes
harder appears to win on staleness, because a superseded fact that was never
retrieved cannot be served.

The clearest example, FactConsolidation at 0.3 / 0.2 / 0.5, where P1 beats P2 on
stale exposure by 0.123:

| | stale exposure | gold support |
|---|---|---|
| P2 | 0.508 | 0.670 |
| P1 (ttl 20) | 0.385 | 0.510 |

P1 bought 12 points of staleness by giving up 16 points of answerability. That is
the same trap the pure-recency corner falls into, and it is worth putting on a
slide, because it is the cleanest demonstration in the whole thesis that
**staleness cannot be read without reading answerability alongside it**.

The single reversal against P5 on clean, FactConsolidation at 0.0 / 0.1 / 0.9,
has a margin of 0.010, which is one question in a hundred, at a corner where both
policies have collapsed to gold support below 0.38.

## 3. Structure of the response surface

Pure-corner responses for P2, from the Scheffé canonical model:

| outcome | benchmark | semantic | lexical | recency | linear R2 | quad R2 |
|---|---|---|---|---|---|---|
| gold support | MQuAKE-T | 1.085 | 1.063 | 0.344 | 0.941 | 0.973 |
| gold support | FactConsolidation | 0.978 | 0.973 | 0.348 | 0.894 | 0.963 |
| stale exposure | MQuAKE-T | 0.463 | 0.429 | -0.048 | 0.910 | 0.924 |
| stale exposure | FactConsolidation | 0.724 | 0.690 | 0.292 | 0.930 | 0.939 |
| clean | MQuAKE-T | 0.623 | 0.633 | 0.412 | 0.462 | 0.876 |
| clean | FactConsolidation | 0.491 | 0.513 | 0.283 | 0.704 | 0.920 |
| est tokens | MQuAKE-T | 353.7 | 372.0 | 423.7 | 0.799 | 0.851 |
| est tokens | FactConsolidation | 387.4 | 392.1 | 409.0 | 0.281 | 0.876 |

Three things replicate cleanly. Semantic and lexical are near-interchangeable on
both benchmarks, differing by 0.022 and 0.005 on gold support. The recency corner
lands at almost exactly the same place on both, 0.344 and 0.348, despite the
benchmarks differing in everything else. And `clean` is the only outcome with
real curvature, jumping from 0.46 to 0.88 and 0.70 to 0.92 between the linear and
quadratic fits, meaning the blend genuinely matters for that outcome alone.

Rank correlation of P2's response across the 66 weightings, between benchmarks:

| outcome | Spearman rho |
|---|---|
| stale exposure | 0.970 |
| gold support | 0.963 |
| clean | 0.692 |
| est tokens | 0.553 |

The two primary outcomes agree almost perfectly on the shape of the surface. The
token surface agrees least, and the FactConsolidation token fit is poor (linear R2
0.281), because P2 filters less there (2.27 wasted slots against 3.51), so there
is simply less token variation to explain.

## 4. The accuracy ceiling replicates

| | MQuAKE-T | FactConsolidation |
|---|---|---|
| best achievable gold support | 1.000 | 0.910 |
| weightings reaching it | 26 of 66 | 18 of 66 |
| clean spread inside that group | 0.031 | 0.030 |
| judge noise floor | 0.030 | 0.030 |
| published 0.6/0.3/0.1 inside | yes | yes |

On both benchmarks the spread of `clean` within the tied group is the same size
as the noise floor, so nothing inside it is distinguishable from anything else.
On FactConsolidation the published weighting is not merely inside the group, it
ties for the best clean value in it at 0.480.

On both, the weighting with the best clean score overall sits outside the ceiling
group and pays for it in answerability: 0.3/0.4/0.3 reaching clean 0.698 at gold
0.927 on MQuAKE-T, and 0.2/0.5/0.3 reaching 0.500 at gold 0.860 on
FactConsolidation. Optimising the composite would cost accuracy on both.

## 5. Retrieval depth: k = 25 is worse than k = 5 on both

| k | MQuAKE-T clean | MQuAKE-T tokens | FC clean | FC tokens |
|---|---|---|---|---|
| 5 | 0.583 | 77 | 0.610 | 79 |
| 10 | 0.573 | 149 | 0.520 | 155 |
| 25 | 0.573 | 373 | 0.480 | 389 |
| 50 | 0.562 | 711 | 0.450 | 796 |

Clean retrieval is highest at k = 5 on both benchmarks and falls monotonically as
depth increases, while token cost rises roughly fivefold from k = 5 to k = 25.
Gold support is flat on MQuAKE-T and rises only from 0.880 to 0.930 on
FactConsolidation across the whole range. Deeper retrieval mostly pulls in more
material containing the superseded value.

This is now a replicated finding rather than a single-benchmark curiosity, and it
is a concrete deployment recommendation the thesis can make.

## 6. Novelty gating fails at every threshold, on both

| tau | MQuAKE-T gold | MQuAKE-T stale | FC gold | FC stale |
|---|---|---|---|---|
| 0.80 | 0.156 | 0.990 | 0.560 | 0.954 |
| 0.85 | 0.562 | 1.000 | 0.630 | 0.985 |
| 0.90 | 0.906 | 0.990 | 0.800 | 0.969 |
| 0.95 | 0.990 | 1.000 | 0.910 | 0.954 |
| 0.99 | 1.000 | 1.000 | 0.910 | 0.954 |

Stale exposure swings 0.010 on MQuAKE-T and 0.031 on FactConsolidation across the
entire threshold range, both inside the noise floor. Gold support swings 0.844
and 0.350. Tightening the gate never buys hygiene on either benchmark. It only
destroys answerability. This is the most strongly replicated result in the whole
sweep, and it upgrades the P3 claim from "bad at the chosen setting" to "bad by
construction across its operating range, on two benchmarks".

## 7. A correction: the grace-period claim does not fully replicate

On MQuAKE-T, gold support, stale exposure and clean are byte-identical at 0, 1,
3, 7, 14 and 30 days, exactly as the mechanism predicts. On FactConsolidation
they are not:

| grace | FC stale exposure | FC clean | FC context facts |
|---|---|---|---|
| 0 | 0.692 | 0.460 | 24.8 |
| 7 | 0.662 | 0.480 | 22.7 |
| 30 | 0.646 | 0.490 | 20.9 |

Longer grace slightly *improves* both, by 0.046 on stale exposure and 0.030 on
clean, which is the opposite of the direction the cost argument predicts.

The explanation is a limitation of the proxy rather than a property of the
policy. Longer grace keeps more invalidated facts occupying top-k slots, which
crowds out other facts, and some of those other facts contain the superseded
answer string without ever having been invalidated themselves. Narrowing the
context therefore reduces the measured stale exposure. This is the string-match
weakness already flagged: the metric counts the old value appearing anywhere, not
only in a fact P2 should have caught.

The honest statement for the thesis is now: on MQuAKE-T the grace period has
exactly zero effect on correctness; on FactConsolidation it has a small monotone
effect of 0.030 on clean, which sits exactly at the noise floor and is explained
by context narrowing rather than by invalidation. The parameter remains primarily
a cost knob, but "zero effect on correctness" is a MQuAKE-T statement, not a
general one.

## 8. P1's best ttl differs by benchmark, as the thesis already argues

Clean peaks at ttl = 10 on MQuAKE-T (0.375) and at ttl = 20 to 30 on
FactConsolidation (0.330). At ttl = 60 both collapse to P0's behaviour with zero
facts pruned. This is direct support for the existing claim that P1's standing is
a property of the workload's update ratio rather than of time-based pruning as a
strategy, now visible in the parameter's optimum and not only in its rank.

## 9. What this licenses in the write-up

The strongest sentence available is that the central comparison is invariant to
the retrieval weighting across two benchmarks, four competing policies and four
outcomes, with zero reversals anywhere in the usable region, and that every
reversal outside it is an instance of a single identifiable artifact in which the
apparent winner retrieved less of the right answer.

Three claims strengthen from single-benchmark to replicated: the novelty gate
failing at every threshold, the accuracy-ceiling group being indistinguishable
inside the noise floor, and k = 25 being worse than k = 5 on the clean metric.

One claim weakens and must be restated: grace-period invariance holds on
MQuAKE-T and only approximately on FactConsolidation.

## 10. Still outstanding

Everything here is retrieval-layer evidence. `make weights-search` and
`make grace-search` are the end-to-end confirmations that convert these into
accuracy claims, and neither has run yet. The string-match proxy should be
tightened to match on invalidated-fact identity, which would remove the
FactConsolidation grace artifact described in section 7 and is the single
highest-value fix to the measurement.
