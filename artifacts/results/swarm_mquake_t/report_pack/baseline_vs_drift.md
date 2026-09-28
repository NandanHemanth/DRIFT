# Baseline vs DRIFT

| agent | accuracy | staleness | tokens/q | active facts |
|---|---|---|---|---|
| No memory | 0.000 | 0.000 | 156 | 140 |
| Memory, no policy | 0.333 | 0.271 | 710 | 140 |
| DRIFT (P2) | 0.365 | 0.271 | 710 | 140 |

DRIFT delta over no-policy agent: accuracy +0.031, staleness reduced by 0.000.
