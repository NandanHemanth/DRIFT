# Grace period with history questions

## mquake_t

Closed facts at question time: 90; age in days: median 5.0, max 30.0

| grace (days) | current gold in context | wasted slots | history stored | history in context | active facts |
|---|---|---|---|---|---|
| 0 | 1.000 | 2.25 | 0.260 | 0.260 | 300 |
| 1 | 1.000 | 3.53 | 0.375 | 0.375 | 311 |
| 3 | 1.000 | 4.61 | 0.490 | 0.490 | 323 |
| 5 | 1.000 | 5.24 | 0.573 | 0.562 | 334 |
| 7 | 1.000 | 5.49 | 0.625 | 0.615 | 339 |
| 10 | 1.000 | 5.84 | 0.719 | 0.708 | 348 |
| 14 | 1.000 | 6.36 | 0.781 | 0.781 | 356 |
| 21 | 1.000 | 6.85 | 0.938 | 0.938 | 374 |
| never | 1.000 | 6.95 | 1.000 | 1.000 | 382 |

| grace | model | current accuracy | history accuracy |
|---|---|---|---|
| 0 | claude-sonnet-5.5 | 0.979 | 0.198 |
| 1 | claude-sonnet-5.5 | 0.979 | 0.281 |
| 3 | claude-sonnet-5.5 | 0.990 | 0.396 |
| 5 | claude-sonnet-5.5 | 0.990 | 0.510 |
| 7 | claude-sonnet-5.5 | 0.990 | 0.562 |
| 10 | claude-sonnet-5.5 | 0.990 | 0.667 |
| 14 | claude-sonnet-5.5 | 0.990 | 0.760 |
| 21 | claude-sonnet-5.5 | 0.990 | 0.917 |
| never | claude-sonnet-5.5 | 0.990 | 0.990 |
| 0 | gemini-3.8-flash | 0.990 | 0.146 |
| 1 | gemini-3.8-flash | 0.979 | 0.260 |
| 3 | gemini-3.8-flash | 0.979 | 0.385 |
| 5 | gemini-3.8-flash | 0.990 | 0.500 |
| 7 | gemini-3.8-flash | 0.990 | 0.552 |
| 10 | gemini-3.8-flash | 0.990 | 0.646 |
| 14 | gemini-3.8-flash | 0.990 | 0.729 |
| 21 | gemini-3.8-flash | 0.990 | 0.917 |
| never | gemini-3.8-flash | 0.990 | 0.990 |
| 0 | llama-3.1-8b-instruct | 0.938 | 0.188 |
| 1 | llama-3.1-8b-instruct | 0.938 | 0.271 |
| 3 | llama-3.1-8b-instruct | 0.948 | 0.375 |
| 5 | llama-3.1-8b-instruct | 0.958 | 0.521 |
| 7 | llama-3.1-8b-instruct | 0.938 | 0.583 |
| 10 | llama-3.1-8b-instruct | 0.927 | 0.688 |
| 14 | llama-3.1-8b-instruct | 0.927 | 0.729 |
| 21 | llama-3.1-8b-instruct | 0.938 | 0.917 |
| never | llama-3.1-8b-instruct | 0.938 | 0.990 |
| 0 | gpt-6.1-sol | 0.990 | 0.146 |
| 1 | gpt-6.1-sol | 0.990 | 0.260 |
| 3 | gpt-6.1-sol | 0.990 | 0.385 |
| 5 | gpt-6.1-sol | 0.990 | 0.500 |
| 7 | gpt-6.1-sol | 0.990 | 0.552 |
| 10 | gpt-6.1-sol | 0.990 | 0.646 |
| 14 | gpt-6.1-sol | 0.990 | 0.729 |
| 21 | gpt-6.1-sol | 0.990 | 0.917 |
| never | gpt-6.1-sol | 0.990 | 0.990 |
| 0 | qwen3-14b | 0.979 | 0.167 |
| 1 | qwen3-14b | 0.969 | 0.281 |
| 3 | qwen3-14b | 0.969 | 0.406 |
| 5 | qwen3-14b | 0.969 | 0.500 |
| 7 | qwen3-14b | 0.969 | 0.552 |
| 10 | qwen3-14b | 0.969 | 0.635 |
| 14 | qwen3-14b | 0.969 | 0.719 |
| 21 | qwen3-14b | 0.958 | 0.917 |
| never | qwen3-14b | 0.958 | 0.990 |

## factconsolidation

Closed facts at question time: 63; age in days: median 4.0, max 27.0

| grace (days) | current gold in context | wasted slots | history stored | history in context | active facts |
|---|---|---|---|---|---|
| 0 | 1.000 | 0.28 | 0.723 | 0.600 | 274 |
| 1 | 1.000 | 0.94 | 0.738 | 0.615 | 281 |
| 3 | 1.000 | 1.58 | 0.754 | 0.631 | 292 |
| 5 | 1.000 | 2.72 | 0.785 | 0.708 | 305 |
| 7 | 1.000 | 3.15 | 0.800 | 0.723 | 314 |
| 10 | 1.000 | 4.06 | 0.892 | 0.815 | 329 |
| 14 | 1.000 | 4.58 | 0.938 | 0.877 | 341 |
| 21 | 1.000 | 5.18 | 0.985 | 0.938 | 364 |
| never | 1.000 | 5.75 | 1.000 | 0.954 | 380 |

| grace | model | current accuracy | history accuracy |
|---|---|---|---|
| 0 | claude-sonnet-5.5 | 0.985 | 0.138 |
| 1 | claude-sonnet-5.5 | 0.985 | 0.185 |
| 3 | claude-sonnet-5.5 | 0.985 | 0.246 |
| 5 | claude-sonnet-5.5 | 0.985 | 0.338 |
| 7 | claude-sonnet-5.5 | 0.985 | 0.338 |
| 10 | claude-sonnet-5.5 | 0.985 | 0.400 |
| 14 | claude-sonnet-5.5 | 0.985 | 0.508 |
| 21 | claude-sonnet-5.5 | 0.985 | 0.677 |
| never | claude-sonnet-5.5 | 0.985 | 0.800 |
| 0 | gemini-3.8-flash | 0.969 | 0.138 |
| 1 | gemini-3.8-flash | 0.969 | 0.185 |
| 3 | gemini-3.8-flash | 0.969 | 0.246 |
| 5 | gemini-3.8-flash | 0.985 | 0.338 |
| 7 | gemini-3.8-flash | 0.985 | 0.354 |
| 10 | gemini-3.8-flash | 0.985 | 0.431 |
| 14 | gemini-3.8-flash | 0.985 | 0.523 |
| 21 | gemini-3.8-flash | 0.985 | 0.692 |
| never | gemini-3.8-flash | 0.985 | 0.800 |
| 0 | llama-3.1-8b-instruct | 0.662 | 0.108 |
| 1 | llama-3.1-8b-instruct | 0.723 | 0.138 |
| 3 | llama-3.1-8b-instruct | 0.738 | 0.185 |
| 5 | llama-3.1-8b-instruct | 0.708 | 0.262 |
| 7 | llama-3.1-8b-instruct | 0.677 | 0.308 |
| 10 | llama-3.1-8b-instruct | 0.754 | 0.323 |
| 14 | llama-3.1-8b-instruct | 0.708 | 0.415 |
| 21 | llama-3.1-8b-instruct | 0.692 | 0.492 |
| never | llama-3.1-8b-instruct | 0.708 | 0.631 |
| 0 | gpt-6.1-sol | 0.985 | 0.138 |
| 1 | gpt-6.1-sol | 0.985 | 0.185 |
| 3 | gpt-6.1-sol | 0.985 | 0.246 |
| 5 | gpt-6.1-sol | 0.985 | 0.338 |
| 7 | gpt-6.1-sol | 0.985 | 0.354 |
| 10 | gpt-6.1-sol | 0.985 | 0.431 |
| 14 | gpt-6.1-sol | 0.985 | 0.523 |
| 21 | gpt-6.1-sol | 0.985 | 0.692 |
| never | gpt-6.1-sol | 0.985 | 0.800 |
| 0 | qwen3-14b | 0.923 | 0.138 |
| 1 | qwen3-14b | 0.923 | 0.185 |
| 3 | qwen3-14b | 0.908 | 0.246 |
| 5 | qwen3-14b | 0.908 | 0.338 |
| 7 | qwen3-14b | 0.908 | 0.354 |
| 10 | qwen3-14b | 0.938 | 0.431 |
| 14 | qwen3-14b | 0.908 | 0.523 |
| 21 | qwen3-14b | 0.923 | 0.692 |
| never | qwen3-14b | 0.938 | 0.785 |

## convomem

Closed facts at question time: 16; age in days: median 8.0, max 18.0

| grace (days) | current gold in context | wasted slots | history stored | history in context | active facts |
|---|---|---|---|---|---|
| 0 | 0.020 | 1.86 | 0.250 | 0.250 | 273 |
| 1 | 0.020 | 3.49 | 0.260 | 0.260 | 302 |
| 3 | 0.020 | 5.01 | 0.270 | 0.270 | 320 |
| 5 | 0.020 | 6.33 | 0.270 | 0.260 | 343 |
| 7 | 0.020 | 7.61 | 0.280 | 0.270 | 369 |
| 10 | 0.020 | 8.96 | 0.310 | 0.280 | 417 |
| 14 | 0.020 | 9.95 | 0.310 | 0.280 | 465 |
| 21 | 0.020 | 10.26 | 0.340 | 0.320 | 495 |
| never | 0.020 | 10.26 | 0.340 | 0.320 | 495 |

| grace | model | current accuracy | history accuracy |
|---|---|---|---|
| 0 | claude-sonnet-5.5 | 0.080 | 0.070 |
| 1 | claude-sonnet-5.5 | 0.080 | 0.080 |
| 3 | claude-sonnet-5.5 | 0.080 | 0.100 |
| 5 | claude-sonnet-5.5 | 0.080 | 0.110 |
| 7 | claude-sonnet-5.5 | 0.080 | 0.100 |
| 10 | claude-sonnet-5.5 | 0.080 | 0.100 |
| 14 | claude-sonnet-5.5 | 0.080 | 0.100 |
| 21 | claude-sonnet-5.5 | 0.080 | 0.130 |
| never | claude-sonnet-5.5 | 0.080 | 0.130 |
| 0 | gemini-3.8-flash | 0.080 | 0.030 |
| 1 | gemini-3.8-flash | 0.090 | 0.040 |
| 3 | gemini-3.8-flash | 0.080 | 0.040 |
| 5 | gemini-3.8-flash | 0.080 | 0.040 |
| 7 | gemini-3.8-flash | 0.080 | 0.030 |
| 10 | gemini-3.8-flash | 0.080 | 0.040 |
| 14 | gemini-3.8-flash | 0.070 | 0.050 |
| 21 | gemini-3.8-flash | 0.070 | 0.080 |
| never | gemini-3.8-flash | 0.070 | 0.080 |
| 0 | llama-3.1-8b-instruct | 0.050 | 0.070 |
| 1 | llama-3.1-8b-instruct | 0.060 | 0.070 |
| 3 | llama-3.1-8b-instruct | 0.060 | 0.070 |
| 5 | llama-3.1-8b-instruct | 0.080 | 0.060 |
| 7 | llama-3.1-8b-instruct | 0.080 | 0.040 |
| 10 | llama-3.1-8b-instruct | 0.070 | 0.070 |
| 14 | llama-3.1-8b-instruct | 0.070 | 0.060 |
| 21 | llama-3.1-8b-instruct | 0.070 | 0.080 |
| never | llama-3.1-8b-instruct | 0.070 | 0.080 |
| 0 | gpt-6.1-sol | 0.100 | 0.100 |
| 1 | gpt-6.1-sol | 0.100 | 0.090 |
| 3 | gpt-6.1-sol | 0.090 | 0.090 |
| 5 | gpt-6.1-sol | 0.100 | 0.090 |
| 7 | gpt-6.1-sol | 0.100 | 0.100 |
| 10 | gpt-6.1-sol | 0.100 | 0.100 |
| 14 | gpt-6.1-sol | 0.100 | 0.090 |
| 21 | gpt-6.1-sol | 0.100 | 0.110 |
| never | gpt-6.1-sol | 0.100 | 0.110 |
| 0 | qwen3-14b | 0.080 | 0.090 |
| 1 | qwen3-14b | 0.080 | 0.090 |
| 3 | qwen3-14b | 0.080 | 0.080 |
| 5 | qwen3-14b | 0.080 | 0.090 |
| 7 | qwen3-14b | 0.080 | 0.080 |
| 10 | qwen3-14b | 0.080 | 0.110 |
| 14 | qwen3-14b | 0.080 | 0.100 |
| 21 | qwen3-14b | 0.080 | 0.140 |
| never | qwen3-14b | 0.080 | 0.140 |
