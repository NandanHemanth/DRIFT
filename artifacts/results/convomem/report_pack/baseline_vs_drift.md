# Baseline vs DRIFT

| agent | accuracy | staleness | tokens/q | active facts |
|---|---|---|---|---|
| No memory | 0.000 | 0.000 | 300 | 77 |
| Memory, no policy | 0.230 | 0.240 | 1029 | 77 |
| DRIFT (P2) | 0.230 | 0.180 | 877 | 68 |

DRIFT delta over no-policy agent: accuracy +0.000, staleness reduced by 0.060.
