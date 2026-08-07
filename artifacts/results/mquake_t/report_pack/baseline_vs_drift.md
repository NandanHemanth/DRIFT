# Baseline vs DRIFT

| agent | accuracy | staleness | tokens/q | active facts |
|---|---|---|---|---|
| No memory | 0.000 | 0.000 | 311 | 382 |
| Memory, no policy | 0.969 | 0.094 | 897 | 382 |
| DRIFT (P2) | 0.969 | 0.062 | 791 | 357 |

DRIFT delta over no-policy agent: accuracy +0.000, staleness reduced by 0.031.
