# Grace period with history questions

## mquake_t

Closed facts at question time: 95; age in days: median 5.0, max 30.0

| grace (days) | current gold in context | wasted slots | history stored | history in context | active facts |
|---|---|---|---|---|---|
| 0 | 1.000 | 2.39 | 0.219 | 0.219 | 296 |
| 1 | 1.000 | 3.76 | 0.354 | 0.354 | 308 |
| 3 | 1.000 | 4.86 | 0.469 | 0.469 | 320 |
| 5 | 1.000 | 5.56 | 0.562 | 0.552 | 332 |
| 7 | 1.000 | 5.79 | 0.615 | 0.604 | 337 |
| 10 | 1.000 | 6.24 | 0.719 | 0.708 | 347 |
| 14 | 1.000 | 6.76 | 0.781 | 0.781 | 355 |
| 21 | 1.000 | 7.25 | 0.938 | 0.938 | 373 |
| never | 1.000 | 7.44 | 1.000 | 1.000 | 382 |

| grace | model | current accuracy | history accuracy |
|---|---|---|---|
| 0 | llama-3.1-8b-instruct | 0.969 | 0.156 |
| 1 | llama-3.1-8b-instruct | 0.969 | 0.250 |
| 3 | llama-3.1-8b-instruct | 0.969 | 0.354 |
| 5 | llama-3.1-8b-instruct | 0.979 | 0.521 |
| 7 | llama-3.1-8b-instruct | 0.979 | 0.573 |
| 10 | llama-3.1-8b-instruct | 0.969 | 0.677 |
| 14 | llama-3.1-8b-instruct | 0.969 | 0.719 |
| 21 | llama-3.1-8b-instruct | 0.969 | 0.906 |
| never | llama-3.1-8b-instruct | 0.969 | 0.990 |
| 0 | qwen3-14b | 0.979 | 0.125 |
| 1 | qwen3-14b | 0.969 | 0.250 |
| 3 | qwen3-14b | 0.979 | 0.375 |
| 5 | qwen3-14b | 0.979 | 0.479 |
| 7 | qwen3-14b | 0.979 | 0.531 |
| 10 | qwen3-14b | 0.979 | 0.625 |
| 14 | qwen3-14b | 0.979 | 0.708 |
| 21 | qwen3-14b | 0.969 | 0.906 |
| never | qwen3-14b | 0.969 | 0.990 |

## factconsolidation

Closed facts at question time: 60; age in days: median 4.0, max 27.0

| grace (days) | current gold in context | wasted slots | history stored | history in context | active facts |
|---|---|---|---|---|---|
| 0 | 1.000 | 0.31 | 0.754 | 0.631 | 284 |
| 1 | 1.000 | 0.97 | 0.769 | 0.646 | 291 |
| 3 | 1.000 | 1.65 | 0.785 | 0.662 | 302 |
| 5 | 1.000 | 2.77 | 0.815 | 0.738 | 315 |
| 7 | 1.000 | 2.91 | 0.831 | 0.754 | 320 |
| 10 | 1.000 | 3.83 | 0.908 | 0.831 | 335 |
| 14 | 1.000 | 4.25 | 0.938 | 0.877 | 344 |
| 21 | 1.000 | 4.78 | 0.985 | 0.938 | 365 |
| never | 1.000 | 5.28 | 1.000 | 0.954 | 380 |

| grace | model | current accuracy | history accuracy |
|---|---|---|---|
| 0 | llama-3.1-8b-instruct | 0.708 | 0.169 |
| 1 | llama-3.1-8b-instruct | 0.738 | 0.200 |
| 3 | llama-3.1-8b-instruct | 0.692 | 0.246 |
| 5 | llama-3.1-8b-instruct | 0.692 | 0.323 |
| 7 | llama-3.1-8b-instruct | 0.708 | 0.354 |
| 10 | llama-3.1-8b-instruct | 0.769 | 0.354 |
| 14 | llama-3.1-8b-instruct | 0.723 | 0.400 |
| 21 | llama-3.1-8b-instruct | 0.646 | 0.508 |
| never | llama-3.1-8b-instruct | 0.646 | 0.615 |
| 0 | qwen3-14b | 0.877 | 0.200 |
| 1 | qwen3-14b | 0.862 | 0.231 |
| 3 | qwen3-14b | 0.831 | 0.292 |
| 5 | qwen3-14b | 0.846 | 0.385 |
| 7 | qwen3-14b | 0.831 | 0.415 |
| 10 | qwen3-14b | 0.846 | 0.477 |
| 14 | qwen3-14b | 0.846 | 0.538 |
| 21 | qwen3-14b | 0.862 | 0.708 |
| never | qwen3-14b | 0.892 | 0.785 |

## convomem

Closed facts at question time: 14; age in days: median 7.5, max 18.0

| grace (days) | current gold in context | wasted slots | history stored | history in context | active facts |
|---|---|---|---|---|---|
| 0 | 0.010 | 1.20 | 0.290 | 0.290 | 337 |
| 1 | 0.010 | 3.01 | 0.300 | 0.300 | 367 |
| 3 | 0.010 | 4.53 | 0.300 | 0.300 | 394 |
| 5 | 0.010 | 5.34 | 0.320 | 0.300 | 414 |
| 7 | 0.010 | 6.82 | 0.320 | 0.290 | 452 |
| 10 | 0.010 | 8.11 | 0.340 | 0.310 | 516 |
| 14 | 0.010 | 8.99 | 0.340 | 0.310 | 566 |
| 21 | 0.010 | 9.37 | 0.380 | 0.340 | 603 |
| never | 0.010 | 9.37 | 0.380 | 0.340 | 603 |

| grace | model | current accuracy | history accuracy |
|---|---|---|---|
| 0 | llama-3.1-8b-instruct | 0.060 | 0.080 |
| 1 | llama-3.1-8b-instruct | 0.050 | 0.080 |
| 3 | llama-3.1-8b-instruct | 0.040 | 0.050 |
| 5 | llama-3.1-8b-instruct | 0.050 | 0.070 |
| 7 | llama-3.1-8b-instruct | 0.050 | 0.080 |
| 10 | llama-3.1-8b-instruct | 0.070 | 0.080 |
| 14 | llama-3.1-8b-instruct | 0.060 | 0.080 |
| 21 | llama-3.1-8b-instruct | 0.060 | 0.100 |
| never | llama-3.1-8b-instruct | 0.060 | 0.100 |
| 0 | qwen3-14b | 0.070 | 0.060 |
| 1 | qwen3-14b | 0.070 | 0.070 |
| 3 | qwen3-14b | 0.070 | 0.060 |
| 5 | qwen3-14b | 0.080 | 0.090 |
| 7 | qwen3-14b | 0.080 | 0.100 |
| 10 | qwen3-14b | 0.070 | 0.090 |
| 14 | qwen3-14b | 0.080 | 0.110 |
| 21 | qwen3-14b | 0.070 | 0.130 |
| never | qwen3-14b | 0.070 | 0.130 |
