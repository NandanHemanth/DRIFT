# Retrieval response surface: P2

66 weightings on the simplex, step 0.1. The weights are constrained to
sum to one, so this is a mixture experiment and the model below is the Scheffe
canonical form. Linear coefficients are the predicted response at each pure corner.

## 1. What the weighting cannot change

| quantity | invariant | value |
|---|---|---|
| active_facts | yes | 324 |
| pruned | yes | 56 |
| invalidated_active | yes | 36 |

These are fixed during ingestion and maintenance, before retrieval runs, so no
weighting can move them. Memory footprint, storage saved and hygiene are therefore
out of scope for this parameter by construction.

## 2. Corner responses and model fit

| outcome | pure semantic | pure lexical | pure recency | linear R2 | quadratic R2 |
|---|---|---|---|---|---|
| gold_support | 0.978 | 0.973 | 0.348 | 0.894 | 0.963 |
| stale_exposure | 0.724 | 0.690 | 0.292 | 0.930 | 0.939 |
| clean | 0.491 | 0.513 | 0.283 | 0.704 | 0.920 |
| est_ctx_tokens | 387.402 | 392.061 | 408.969 | 0.281 | 0.876 |
| wasted_slots | 2.273 | 2.536 | 0.148 | 0.774 | 0.973 |
| ctx_facts | 22.727 | 22.464 | 24.852 | 0.774 | 0.973 |

A linear R2 near 1 means the outcome is close to a straight interpolation
between the corners, so mixing buys nothing that the corners do not already
explain. A large jump from linear to quadratic means the blend itself matters.

## 3. Measured pure corners

| corner | gold support | stale exposure | clean | wasted slots | est tokens |
|---|---|---|---|---|---|
| semantic | 0.910 | 0.692 | 0.460 | 2.80 | 373 |
| lexical | 0.860 | 0.646 | 0.450 | 2.69 | 390 |
| recency | 0.270 | 0.338 | 0.190 | 1.00 | 384 |
| published 0.6/0.3/0.1 | 0.910 | 0.662 | 0.480 | 2.27 | 389 |

## 4. Pareto frontier (25 of 66 weightings)

Non-dominated on gold support up, stale exposure down, tokens down. No single
weighting wins on all three, which is why a single best value does not exist
independently of which outcome is being prioritised.

| sem | lex | rec | gold | stale | tokens |
|---|---|---|---|---|---|
| 0.7 | 0.3 | 0.0 | 0.910 | 0.662 | 382 |
| 1.0 | 0.0 | 0.0 | 0.910 | 0.692 | 373 |
| 0.4 | 0.4 | 0.2 | 0.880 | 0.631 | 394 |
| 0.0 | 0.8 | 0.2 | 0.870 | 0.631 | 390 |
| 0.3 | 0.4 | 0.3 | 0.870 | 0.585 | 404 |
| 0.2 | 0.5 | 0.3 | 0.860 | 0.585 | 403 |
| 0.0 | 0.7 | 0.3 | 0.850 | 0.585 | 397 |
| 0.4 | 0.2 | 0.4 | 0.830 | 0.538 | 412 |
| 0.1 | 0.5 | 0.4 | 0.820 | 0.569 | 405 |
| 0.5 | 0.1 | 0.4 | 0.820 | 0.554 | 411 |
| 0.0 | 0.6 | 0.4 | 0.810 | 0.538 | 403 |
| 0.1 | 0.4 | 0.5 | 0.730 | 0.508 | 410 |
| 0.0 | 0.5 | 0.5 | 0.720 | 0.492 | 405 |
| 0.0 | 0.4 | 0.6 | 0.600 | 0.462 | 409 |
| 0.2 | 0.2 | 0.6 | 0.590 | 0.446 | 407 |
| 0.3 | 0.1 | 0.6 | 0.540 | 0.400 | 403 |
| 0.4 | 0.0 | 0.6 | 0.520 | 0.400 | 400 |
| 0.0 | 0.3 | 0.7 | 0.490 | 0.354 | 404 |
| 0.1 | 0.2 | 0.7 | 0.490 | 0.369 | 400 |
| 0.2 | 0.1 | 0.7 | 0.480 | 0.369 | 396 |
| 0.0 | 0.2 | 0.8 | 0.470 | 0.354 | 395 |
| 0.3 | 0.0 | 0.7 | 0.460 | 0.369 | 394 |
| 0.2 | 0.0 | 0.8 | 0.410 | 0.369 | 394 |
| 0.0 | 0.1 | 0.9 | 0.380 | 0.354 | 392 |
| 0.0 | 0.0 | 1.0 | 0.270 | 0.338 | 384 |

## 5. Cox effect directions

Each component varied from 0 to 1 while the other two keep their relative
proportions from the published blend. This is how a single component's effect
is read out of a mixture experiment, since the proportions must always sum to
one and something has to give.

| outcome | at published | semantic 0 to 1 | lexical 0 to 1 | recency 0 to 1 |
|---|---|---|---|---|
| gold_support | 0.912 | 0.850 to 0.940 (+0.090) | 0.888 to 0.878 (-0.010) | 0.938 to 0.185 (-0.752) |
| stale_exposure | 0.666 | 0.605 to 0.729 (+0.124) | 0.671 to 0.680 (+0.009) | 0.699 to 0.257 (-0.442) |
| clean | 0.478 | 0.476 to 0.460 (-0.016) | 0.458 to 0.441 (-0.017) | 0.475 to 0.170 (-0.305) |
| est_ctx_tokens | 390.516 | 399.076 to 372.902 (-26.174) | 388.074 to 380.382 (-7.692) | 381.238 to 381.531 (+0.294) |
| wasted_slots | 2.245 | 1.753 to 2.760 (+1.006) | 1.947 to 2.720 (+0.773) | 2.791 to 1.246 (-1.546) |
| ctx_facts | 22.755 | 23.247 to 22.240 (-1.006) | 23.053 to 22.280 (-0.773) | 22.209 to 23.754 (+1.546) |

## 6. Does the hypothesis depend on the weighting?

Margin in favour of P2 at every weighting on the simplex.
A claim that only holds at the published blend would be an artifact of that
blend. One that holds everywhere is not.

Objectives only. Wasted slots and context size are mechanism diagnostics with
no better direction across policies, so they are excluded here.

| outcome | comparison | min | mean | max | holds | ties | reversed |
|---|---|---|---|---|---|---|---|
| gold_support | P2 vs P0 | 0.000 | 0.001 | 0.010 | 7/66 | 59 | 0 |
| gold_support | P2 vs P1:ttl_days=20 | 0.000 | 0.151 | 0.230 | 65/66 | 1 | 0 |
| gold_support | P2 vs P3 | 0.080 | 0.113 | 0.140 | 66/66 | 0 | 0 |
| gold_support | P2 vs P5 | 0.010 | 0.035 | 0.050 | 66/66 | 0 | 0 |
| stale_exposure | P2 vs P0 | -0.000 | 0.219 | 0.338 | 57/66 | 9 | 0 |
| stale_exposure | P2 vs P1:ttl_days=20 | -0.123 | 0.017 | 0.092 | 42/66 | 10 | 14 |
| stale_exposure | P2 vs P3 | -0.138 | 0.204 | 0.338 | 55/66 | 1 | 10 |
| stale_exposure | P2 vs P5 | -0.000 | 0.178 | 0.277 | 58/66 | 8 | 0 |
| clean | P2 vs P0 | 0.000 | 0.142 | 0.220 | 57/66 | 9 | 0 |
| clean | P2 vs P1:ttl_days=20 | 0.000 | 0.115 | 0.210 | 65/66 | 1 | 0 |
| clean | P2 vs P3 | 0.010 | 0.172 | 0.240 | 66/66 | 0 | 0 |
| clean | P2 vs P5 | -0.010 | 0.115 | 0.180 | 63/66 | 2 | 1 |
| est_ctx_tokens | P2 vs P0 | 9.020 | 25.479 | 43.455 | 66/66 | 0 | 0 |
| est_ctx_tokens | P2 vs P1:ttl_days=20 | -0.470 | 24.908 | 49.488 | 65/66 | 0 | 1 |
| est_ctx_tokens | P2 vs P3 | -0.435 | 22.012 | 46.358 | 64/66 | 0 | 2 |
| est_ctx_tokens | P2 vs P5 | 11.880 | 26.824 | 44.017 | 66/66 | 0 | 0 |
