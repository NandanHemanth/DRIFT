# Baseline vs DRIFT

| agent | accuracy | staleness | tokens/q | active facts |
|---|---|---|---|---|
| No memory | 0.000 | 0.000 | 316 | 380 |
| Memory, no policy | 0.820 | 0.060 | 871 | 380 |
| DRIFT (P2) | 0.830 | 0.050 | 772 | 324 |

DRIFT delta over no-policy agent: accuracy +0.010, staleness reduced by 0.010.
