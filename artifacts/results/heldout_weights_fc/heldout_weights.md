# Held-out weighting test (FactConsolidation, P2)

| model | weighting | accuracy | staleness | better / worse vs published | McNemar p |
|---|---|---|---|---|---|
| llama-3.1-8b-instruct | 0.6/0.3/0.1 (published) | 0.620 | 0.060 | - | - |
| llama-3.1-8b-instruct | 0.9/0.1/0.2 (MQuAKE-T best) | 0.610 | 0.050 | 4 / 5 | 1.000 |
| llama-3.1-8b-instruct | 0.8/0.1/0.1 (ConvoMem best) | 0.560 | 0.050 | 5 / 11 | 0.210 |
| qwen3-14b | 0.6/0.3/0.1 (published) | 0.750 | 0.000 | - | - |
| qwen3-14b | 0.9/0.1/0.2 (MQuAKE-T best) | 0.800 | 0.000 | 9 / 4 | 0.267 |
| qwen3-14b | 0.8/0.1/0.1 (ConvoMem best) | 0.760 | 0.000 | 3 / 2 | 1.000 |
