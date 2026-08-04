# Baseline vs DRIFT

| agent | accuracy | staleness | tokens/q | active facts |
|---|---|---|---|---|
| No memory | 0.000 | 0.000 | 136 | - |
| Memory, no policy | 0.667 | 0.286 | 284 | - |
| DRIFT (P2) | 0.881 | 0.000 | 272 | - |

DRIFT delta over no-policy agent: accuracy +0.214, staleness reduced by 0.286.
