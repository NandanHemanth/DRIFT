# Sensitivity analysis: smoke

Dataset: `data/synthetic_smoke.json`  |  embedder: `hashing`  |  default weights: (0.6, 0.3, 0.1)  |  default k: 8

### Weights: value at the published setting

| policy | w_sem | w_lex | w_rec | gold_support | stale_exposure | clean | wasted_slots | ctx_facts |
|---|---|---|---|---|---|---|---|---|
| P0 | 0.600 | 0.300 | 0.100 | 1.000 | 1.000 | 0.714 | 0.000 | 8.000 |
| P2 | 0.600 | 0.300 | 0.100 | 1.000 | 0.000 | 1.000 | 0.000 | 8.000 |
| P5 | 0.600 | 0.300 | 0.100 | 0.500 | 0.714 | 0.500 | 0.000 | 5.571 |

Ordering by `clean` at the published weighting: P2 > P0 > P5. That exact ordering holds in 16 of 16 weightings on the simplex (100.0 percent).

### Weights: pairwise ordering stability across the whole simplex

| pair | settings | held | ties | reversed | pct |
|---|---|---|---|---|---|
| P2 > P0 | 16 | 16 | 0 | 0 | 100.000 |
| P2 > P5 | 16 | 16 | 0 | 0 | 100.000 |
| P0 > P5 | 16 | 16 | 0 | 0 | 100.000 |

### Retrieval depth k

| policy | k | gold_support | stale_exposure | clean | wasted_slots | ctx_facts | est_ctx_tokens |
|---|---|---|---|---|---|---|---|
| P0 | 4 | 1.000 | 1.000 | 0.714 | 0.000 | 4.000 | 64.804 |
| P0 | 8 | 1.000 | 1.000 | 0.714 | 0.000 | 8.000 | 127.893 |
| P0 | 16 | 1.000 | 1.000 | 0.714 | 0.000 | 14.286 | 223.286 |
| P2 | 4 | 1.000 | 0.000 | 1.000 | 0.000 | 4.000 | 64.304 |
| P2 | 8 | 1.000 | 0.000 | 1.000 | 0.000 | 8.000 | 127.500 |
| P2 | 16 | 1.000 | 0.000 | 1.000 | 0.000 | 11.857 | 182.857 |
| P5 | 4 | 0.357 | 0.786 | 0.357 | 0.000 | 4.000 | 63.393 |
| P5 | 8 | 0.357 | 0.786 | 0.357 | 0.000 | 5.571 | 87.821 |
| P5 | 16 | 0.357 | 0.786 | 0.357 | 0.000 | 5.571 | 87.821 |

### Policy parameter: grace_days

| policy | grace_days | gold_support | stale_exposure | clean | wasted_slots | ctx_facts | active_facts | pruned |
|---|---|---|---|---|---|---|---|---|
| P2 | 0.000 | 1.000 | 0.000 | 1.000 | 0.000 | 8.000 | 23 | 5 |
| P2 | 7.000 | 1.000 | 0.000 | 1.000 | 0.000 | 8.000 | 23 | 5 |
| P2 | 30.000 | 1.000 | 0.000 | 1.000 | 1.214 | 6.786 | 28 | 0 |

### Policy parameter: ttl_days

| policy | ttl_days | gold_support | stale_exposure | clean | wasted_slots | ctx_facts | active_facts | pruned |
|---|---|---|---|---|---|---|---|---|
| P1 | 5.000 | 0.214 | 0.000 | 0.214 | 0.000 | 2.000 | 4 | 24 |
| P1 | 20.000 | 0.500 | 0.000 | 0.500 | 0.000 | 4.571 | 9 | 19 |
| P1 | 60.000 | 1.000 | 1.000 | 0.714 | 0.000 | 8.000 | 28 | 0 |

### Policy parameter: tau

| policy | tau | gold_support | stale_exposure | clean | wasted_slots | ctx_facts | active_facts | pruned |
|---|---|---|---|---|---|---|---|---|
| P3 | 0.800 | 1.000 | 1.000 | 0.714 | 0.000 | 8.000 | 25 | 0 |
| P3 | 0.900 | 1.000 | 1.000 | 0.714 | 0.000 | 8.000 | 25 | 0 |
| P3 | 0.990 | 1.000 | 1.000 | 0.714 | 0.000 | 8.000 | 25 | 0 |
