# Retrieval response surface: P2

66 weightings on the simplex, step 0.1. The weights are constrained to
sum to one, so this is a mixture experiment and the model below is the Scheffe
canonical form. Linear coefficients are the predicted response at each pure corner.

## 1. What the weighting cannot change

| quantity | invariant | value |
|---|---|---|
| active_facts | yes | 357 |
| pruned | yes | 25 |
| invalidated_active | yes | 34 |

These are fixed during ingestion and maintenance, before retrieval runs, so no
weighting can move them. Memory footprint, storage saved and hygiene are therefore
out of scope for this parameter by construction.

## 2. Corner responses and model fit

| outcome | pure semantic | pure lexical | pure recency | linear R2 | quadratic R2 |
|---|---|---|---|---|---|
| gold_support | 1.085 | 1.063 | 0.344 | 0.941 | 0.973 |
| stale_exposure | 0.463 | 0.429 | -0.048 | 0.910 | 0.924 |
| clean | 0.623 | 0.633 | 0.412 | 0.462 | 0.876 |
| est_ctx_tokens | 353.701 | 371.951 | 423.658 | 0.799 | 0.851 |
| wasted_slots | 4.357 | 3.741 | -0.620 | 0.842 | 0.908 |
| ctx_facts | 20.643 | 21.259 | 25.620 | 0.842 | 0.908 |

A linear R2 near 1 means the outcome is close to a straight interpolation
between the corners, so mixing buys nothing that the corners do not already
explain. A large jump from linear to quadratic means the blend itself matters.

## 3. Measured pure corners

| corner | gold support | stale exposure | clean | wasted slots | est tokens |
|---|---|---|---|---|---|
| semantic | 1.000 | 0.438 | 0.562 | 4.91 | 343 |
| lexical | 1.000 | 0.406 | 0.594 | 4.82 | 351 |
| recency | 0.240 | 0.010 | 0.229 | 0.00 | 423 |
| published 0.6/0.3/0.1 | 1.000 | 0.427 | 0.573 | 3.51 | 373 |

## 4. Pareto frontier (27 of 66 weightings)

Non-dominated on gold support up, stale exposure down, tokens down. No single
weighting wins on all three, which is why a single best value does not exist
independently of which outcome is being prioritised.

| sem | lex | rec | gold | stale | tokens |
|---|---|---|---|---|---|
| 0.0 | 1.0 | 0.0 | 1.000 | 0.406 | 351 |
| 0.1 | 0.9 | 0.0 | 1.000 | 0.427 | 350 |
| 0.2 | 0.8 | 0.0 | 1.000 | 0.427 | 350 |
| 0.3 | 0.7 | 0.0 | 1.000 | 0.427 | 350 |
| 0.4 | 0.6 | 0.0 | 1.000 | 0.427 | 350 |
| 1.0 | 0.0 | 0.0 | 1.000 | 0.438 | 343 |
| 0.2 | 0.6 | 0.2 | 0.990 | 0.375 | 389 |
| 0.3 | 0.5 | 0.2 | 0.990 | 0.396 | 388 |
| 0.1 | 0.7 | 0.2 | 0.969 | 0.365 | 389 |
| 0.6 | 0.1 | 0.3 | 0.948 | 0.312 | 383 |
| 0.7 | 0.0 | 0.3 | 0.948 | 0.323 | 377 |
| 0.4 | 0.3 | 0.3 | 0.938 | 0.271 | 388 |
| 0.5 | 0.2 | 0.3 | 0.938 | 0.292 | 386 |
| 0.3 | 0.4 | 0.3 | 0.927 | 0.240 | 388 |
| 0.4 | 0.2 | 0.4 | 0.812 | 0.188 | 389 |
| 0.6 | 0.0 | 0.4 | 0.802 | 0.167 | 386 |
| 0.4 | 0.1 | 0.5 | 0.719 | 0.146 | 392 |
| 0.5 | 0.0 | 0.5 | 0.698 | 0.146 | 390 |
| 0.4 | 0.0 | 0.6 | 0.615 | 0.135 | 393 |
| 0.0 | 0.3 | 0.7 | 0.552 | 0.125 | 404 |
| 0.2 | 0.1 | 0.7 | 0.542 | 0.125 | 399 |
| 0.3 | 0.0 | 0.7 | 0.542 | 0.115 | 399 |
| 0.1 | 0.2 | 0.7 | 0.531 | 0.125 | 398 |
| 0.1 | 0.1 | 0.8 | 0.479 | 0.104 | 406 |
| 0.2 | 0.0 | 0.8 | 0.469 | 0.083 | 409 |
| 0.0 | 0.1 | 0.9 | 0.396 | 0.031 | 411 |
| 0.1 | 0.0 | 0.9 | 0.375 | 0.010 | 417 |

## 5. Cox effect directions

Each component varied from 0 to 1 while the other two keep their relative
proportions from the published blend. This is how a single component's effect
is read out of a mixture experiment, since the proportions must always sum to
one and something has to give.

| outcome | at published | semantic 0 to 1 | lexical 0 to 1 | recency 0 to 1 |
|---|---|---|---|---|
| gold_support | 0.997 | 0.904 to 1.030 (+0.125) | 0.977 to 1.017 (+0.040) | 1.035 to 0.211 (-0.824) |
| stale_exposure | 0.406 | 0.300 to 0.487 (+0.187) | 0.389 to 0.442 (+0.054) | 0.473 to 0.010 (-0.463) |
| clean | 0.593 | 0.610 to 0.540 (-0.070) | 0.592 to 0.570 (-0.022) | 0.559 to 0.211 (-0.348) |
| est_ctx_tokens | 366.063 | 386.269 to 345.341 (-40.928) | 362.126 to 365.070 (+2.944) | 355.656 to 408.367 (+52.711) |
| wasted_slots | 3.787 | 2.440 to 4.918 (+2.478) | 3.629 to 3.991 (+0.362) | 4.636 to 0.650 (-3.985) |
| ctx_facts | 21.213 | 22.560 to 20.082 (-2.478) | 21.371 to 21.009 (-0.362) | 20.364 to 24.350 (+3.985) |

## 5. Best choice per objective, among the 26 at the accuracy ceiling

| objective | weighting | gold | stale | tokens | clean |
|---|---|---|---|---|---|
| fewest tokens | 1.0 / 0.0 / 0.0 | 1.000 | 0.438 | 343 | 0.562 |
| lowest stale exposure | 0.0 / 1.0 / 0.0 | 1.000 | 0.406 | 351 | 0.594 |
| highest clean | 0.0 / 1.0 / 0.0 | 1.000 | 0.406 | 351 | 0.594 |

## 6. Does the hypothesis depend on the weighting?

Margin in favour of P2 at every weighting on the simplex.
A claim that only holds at the published blend would be an artifact of that
blend. One that holds everywhere is not.

Objectives only. Wasted slots and context size are mechanism diagnostics with
no better direction across policies, so they are excluded here.

| outcome | comparison | min | mean | max | holds | ties | reversed |
|---|---|---|---|---|---|---|---|
| gold_support | P2 vs P0 | 0.000 | 0.000 | 0.000 | 0/66 | 66 | 0 |
| gold_support | P2 vs P1:ttl_days=20 | 0.000 | 0.113 | 0.208 | 65/66 | 1 | 0 |
| gold_support | P2 vs P3 | 0.062 | 0.101 | 0.156 | 66/66 | 0 | 0 |
| gold_support | P2 vs P5 | 0.062 | 0.126 | 0.146 | 66/66 | 0 | 0 |
| stale_exposure | P2 vs P0 | -0.000 | 0.371 | 0.594 | 65/66 | 1 | 0 |
| stale_exposure | P2 vs P1:ttl_days=20 | -0.052 | 0.120 | 0.208 | 60/66 | 2 | 4 |
| stale_exposure | P2 vs P3 | -0.000 | 0.351 | 0.573 | 65/66 | 1 | 0 |
| stale_exposure | P2 vs P5 | -0.000 | 0.383 | 0.573 | 65/66 | 1 | 0 |
| clean | P2 vs P0 | 0.000 | 0.369 | 0.594 | 65/66 | 1 | 0 |
| clean | P2 vs P1:ttl_days=20 | 0.000 | 0.217 | 0.333 | 65/66 | 1 | 0 |
| clean | P2 vs P3 | 0.062 | 0.378 | 0.583 | 66/66 | 0 | 0 |
| clean | P2 vs P5 | 0.062 | 0.405 | 0.573 | 66/66 | 0 | 0 |
| est_ctx_tokens | P2 vs P0 | -0.000 | 40.722 | 82.617 | 65/66 | 1 | 0 |
| est_ctx_tokens | P2 vs P1:ttl_days=20 | -0.000 | 37.966 | 77.510 | 65/66 | 1 | 0 |
| est_ctx_tokens | P2 vs P3 | -8.750 | 31.809 | 74.953 | 63/66 | 0 | 3 |
| est_ctx_tokens | P2 vs P5 | 0.820 | 40.495 | 82.487 | 66/66 | 0 | 0 |
