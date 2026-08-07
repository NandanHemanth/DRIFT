# Cross-dataset generalization

Every figure below is pooled over the answer models in each results directory. Accuracy and staleness carry percentile bootstrap 95% CIs (5,000 resamples); policy-vs-policy tests are paired McNemar exact, because the same questions go to every policy.

## 1. Accuracy and staleness, side by side

| Policy | factconsolidation acc | factconsolidation stale | mquake_t acc | mquake_t stale |
|---|---|---|---|---|
| NOMEM | 0.000 [0.000, 0.000] | 0.000 [0.000, 0.000] | 0.000 [0.000, 0.000] | 0.000 [0.000, 0.000] |
| P0 | 0.840 [0.785, 0.890] | 0.030 [0.010, 0.055] | 0.969 [0.943, 0.990] | 0.052 [0.021, 0.089] |
| P1:ttl_days=20 | 0.630 [0.565, 0.695] | 0.020 [0.005, 0.040] | 0.870 [0.823, 0.917] | 0.026 [0.005, 0.052] |
| P2 | 0.840 [0.785, 0.890] | 0.025 [0.005, 0.050] | 0.969 [0.943, 0.990] | 0.036 [0.010, 0.068] |
| P3 | 0.665 [0.600, 0.730] | 0.140 [0.095, 0.190] | 0.792 [0.729, 0.849] | 0.161 [0.109, 0.214] |
| P4 | 0.800 [0.745, 0.855] | 0.060 [0.030, 0.095] | 0.953 [0.922, 0.979] | 0.057 [0.026, 0.094] |
| P5 | 0.795 [0.735, 0.850] | 0.035 [0.010, 0.060] | 0.802 [0.745, 0.854] | 0.214 [0.156, 0.276] |

## 2. Cost and memory footprint

| Policy | factconsolidation tok/q | factconsolidation active facts | mquake_t tok/q | mquake_t active facts |
|---|---|---|---|---|
| NOMEM | 250 | 380 | 233 | 382 |
| P0 | 812 | 380 | 816 | 382 |
| P1:ttl_days=20 | 799 | 210 | 807 | 251 |
| P2 | 715 | 324 | 716 | 357 |
| P3 | 806 | 334 | 805 | 351 |
| P4 | 814 | 374 | 804 | 372 |
| P5 | 812 | 365 | 816 | 365 |

## 3. Does the ranking survive the dataset change?

| Policy | factconsolidation rank | mquake_t rank |
|---|---|---|
| NOMEM | 7 | 7 |
| P0 | 1 | 1 |
| P1:ttl_days=20 | 6 | 4 |
| P2 | 2 | 2 |
| P3 | 5 | 6 |
| P4 | 3 | 3 |
| P5 | 4 | 5 |

Spearman rho (factconsolidation vs mquake_t) over 7 policies: **0.891**
  -> broadly preserved with local swaps; name the swapped pair explicitly rather than claiming a clean replication.

## 4. Paired tests within each dataset

`A better` / `B better` count discordant pairs only. p is the exact two-sided binomial.

### factconsolidation

| Comparison | Metric | A better | B better | p |
|---|---|---|---|---|
| P0 vs P2 | accuracy | 3 | 3 | 1.000 |
| P0 vs P2 | staleness | 5 | 4 | 1.000 |
| P2 vs P3 | accuracy | 36 | 1 | <0.001 |
| P2 vs P3 | staleness | 1 | 24 | <0.001 |
| P2 vs P5 | accuracy | 11 | 2 | 0.022 |
| P2 vs P5 | staleness | 3 | 5 | 0.727 |
| P2 vs P4 | accuracy | 11 | 3 | 0.057 |
| P2 vs P4 | staleness | 4 | 11 | 0.118 |

### mquake_t

| Comparison | Metric | A better | B better | p |
|---|---|---|---|---|
| P0 vs P2 | accuracy | 2 | 2 | 1.000 |
| P0 vs P2 | staleness | 6 | 3 | 0.508 |
| P2 vs P3 | accuracy | 38 | 4 | <0.001 |
| P2 vs P3 | staleness | 4 | 28 | <0.001 |
| P2 vs P5 | accuracy | 34 | 2 | <0.001 |
| P2 vs P5 | staleness | 3 | 37 | <0.001 |
| P2 vs P4 | accuracy | 7 | 4 | 0.549 |
| P2 vs P4 | staleness | 4 | 8 | 0.388 |

## 5. Staleness metric power

Staleness can only fire on questions carrying a `stale_answer` annotation. A dataset with low coverage reports a low staleness rate for structural reasons, not policy reasons -- which is the trap LoCoMo (0/300) and LongMemEval (0/150) fell into.

| Dataset | Source file | Questions | Annotated | Coverage |
|---|---|---|---|---|
| factconsolidation | factconsolidation_sh_6k.json | 100 | 65 | 65% |
| mquake_t | mquake_t_sh.json | 96 | 96 | 100% |

> A 0% row means the staleness column below it is uninformative: the metric could not fire regardless of policy. This is exactly what happened on LoCoMo (0/300) and LongMemEval (0/150) in the first campaign, where staleness read 0.000 everywhere and was briefly mistaken for a result.
