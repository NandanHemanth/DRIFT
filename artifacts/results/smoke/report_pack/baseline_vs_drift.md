# Baseline vs DRIFT

| agent | accuracy | staleness | tokens/q | active facts |
|---|---|---|---|---|
| No memory | 0.000 | 0.000 | 84 | 12 |
| Memory, no policy | 0.714 | 0.286 | 221 | 12 |
| DRIFT (P2) | 0.929 | 0.000 | 221 | 9 |

DRIFT delta over no-policy agent: accuracy +0.214, staleness reduced by 0.286.
