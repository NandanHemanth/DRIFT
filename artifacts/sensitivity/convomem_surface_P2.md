# Retrieval response surface: P2

66 weightings on the simplex, step 0.1. The weights are constrained to
sum to one, so this is a mixture experiment and the model below is the Scheffe
canonical form. Linear coefficients are the predicted response at each pure corner.

## 1. What the weighting cannot change

| quantity | invariant | value |
|---|---|---|
| active_facts | yes | 912 |
| pruned | yes | 94 |
| invalidated_active | yes | 89 |

These are fixed during ingestion and maintenance, before retrieval runs, so no
weighting can move them. Memory footprint, storage saved and hygiene are therefore
out of scope for this parameter by construction.

## 2. Corner responses and model fit

| outcome | pure semantic | pure lexical | pure recency | linear R2 | quadratic R2 |
|---|---|---|---|---|---|
| gold_support | 0.057 | 0.046 | 0.007 | 0.821 | 0.847 |
| stale_exposure | 0.673 | 0.616 | 0.243 | 0.960 | 0.965 |
| clean | 0.009 | 0.002 | -0.001 | 0.238 | 0.358 |
| est_ctx_tokens | 484.461 | 492.929 | 445.234 | 0.867 | 0.960 |
| wasted_slots | 2.285 | 2.678 | 3.204 | 0.690 | 0.904 |
| ctx_facts | 22.715 | 22.322 | 21.796 | 0.690 | 0.904 |

A linear R2 near 1 means the outcome is close to a straight interpolation
between the corners, so mixing buys nothing that the corners do not already
explain. A large jump from linear to quadratic means the blend itself matters.

## 3. Measured pure corners

| corner | gold support | stale exposure | clean | wasted slots | est tokens |
|---|---|---|---|---|---|
| semantic | 0.050 | 0.640 | 0.000 | 2.26 | 476 |
| lexical | 0.040 | 0.560 | 0.000 | 2.06 | 486 |
| recency | 0.010 | 0.280 | 0.000 | 2.90 | 453 |
| published 0.6/0.3/0.1 | 0.050 | 0.600 | 0.010 | 2.49 | 490 |

## 4. Pareto frontier (6 of 66 weightings)

Non-dominated on gold support up, stale exposure down, tokens down. No single
weighting wins on all three, which is why a single best value does not exist
independently of which outcome is being prioritised.

| sem | lex | rec | gold | stale | tokens |
|---|---|---|---|---|---|
| 0.4 | 0.3 | 0.3 | 0.050 | 0.550 | 470 |
| 0.4 | 0.2 | 0.4 | 0.040 | 0.510 | 466 |
| 0.5 | 0.1 | 0.4 | 0.040 | 0.520 | 465 |
| 0.5 | 0.0 | 0.5 | 0.030 | 0.430 | 462 |
| 0.0 | 0.1 | 0.9 | 0.020 | 0.290 | 456 |
| 0.0 | 0.0 | 1.0 | 0.010 | 0.280 | 453 |

## 5. Cox effect directions

Each component varied from 0 to 1 while the other two keep their relative
proportions from the published blend. This is how a single component's effect
is read out of a mixture experiment, since the proportions must always sum to
one and something has to give.

| outcome | at published | semantic 0 to 1 | lexical 0 to 1 | recency 0 to 1 |
|---|---|---|---|---|
| gold_support | 0.050 | 0.033 to 0.052 (+0.019) | 0.046 to 0.046 (-0.000) | 0.056 to 0.011 (-0.045) |
| stale_exposure | 0.616 | 0.524 to 0.663 (+0.140) | 0.607 to 0.592 (-0.014) | 0.654 to 0.222 (-0.432) |
| clean | 0.006 | 0.001 to 0.004 (+0.003) | 0.006 to 0.000 (-0.006) | 0.006 to -0.005 (-0.011) |
| est_ctx_tokens | 485.597 | 475.058 to 479.717 (+4.659) | 474.131 to 494.088 (+19.957) | 492.582 to 456.208 (-36.374) |
| wasted_slots | 2.507 | 2.894 to 2.248 (-0.646) | 2.416 to 2.379 (-0.037) | 2.360 to 2.837 (+0.477) |
| ctx_facts | 22.493 | 22.106 to 22.752 (+0.646) | 22.584 to 22.621 (+0.037) | 22.640 to 22.163 (-0.477) |

## 6. Does the hypothesis depend on the weighting?

Margin in favour of P2 at every weighting on the simplex.
A claim that only holds at the published blend would be an artifact of that
blend. One that holds everywhere is not.

Objectives only. Wasted slots and context size are mechanism diagnostics with
no better direction across policies, so they are excluded here.

| outcome | comparison | min | mean | max | holds | ties | reversed |
|---|---|---|---|---|---|---|---|
| gold_support | P2 vs P0 | 0.000 | 0.000 | 0.010 | 1/66 | 65 | 0 |
| gold_support | P2 vs P1:ttl_days=20 | 0.000 | 0.000 | 0.010 | 1/66 | 65 | 0 |
| gold_support | P2 vs P3 | -0.010 | -0.000 | 0.000 | 0/66 | 63 | 3 |
| gold_support | P2 vs P5 | -0.010 | -0.002 | 0.000 | 0/66 | 54 | 12 |
| stale_exposure | P2 vs P0 | -0.000 | 0.035 | 0.070 | 63/66 | 3 | 0 |
| stale_exposure | P2 vs P1:ttl_days=20 | -0.000 | 0.035 | 0.070 | 63/66 | 3 | 0 |
| stale_exposure | P2 vs P3 | -0.000 | 0.040 | 0.070 | 65/66 | 1 | 0 |
| stale_exposure | P2 vs P5 | 0.010 | 0.044 | 0.100 | 66/66 | 0 | 0 |
| clean | P2 vs P0 | 0.000 | 0.000 | 0.000 | 0/66 | 66 | 0 |
| clean | P2 vs P1:ttl_days=20 | 0.000 | 0.000 | 0.000 | 0/66 | 66 | 0 |
| clean | P2 vs P3 | -0.010 | -0.000 | 0.000 | 0/66 | 65 | 1 |
| clean | P2 vs P5 | -0.010 | -0.001 | 0.000 | 0/66 | 62 | 4 |
| est_ctx_tokens | P2 vs P0 | 55.873 | 72.058 | 83.375 | 66/66 | 0 | 0 |
| est_ctx_tokens | P2 vs P1:ttl_days=20 | 55.873 | 72.058 | 83.375 | 66/66 | 0 | 0 |
| est_ctx_tokens | P2 vs P3 | 50.423 | 66.647 | 78.075 | 66/66 | 0 | 0 |
| est_ctx_tokens | P2 vs P5 | 30.305 | 44.720 | 56.413 | 66/66 | 0 | 0 |
