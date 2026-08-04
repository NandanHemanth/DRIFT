# Summary table

| policy | model | topology | n_questions | accuracy | f1 | staleness | tokens_per_q | active_facts | pruned | write_rejections | cross_writer_invalidations |
|---|---|---|---|---|---|---|---|---|---|---|---|
| NOMEM |  | independent | 42 | 0.0 | 0.0 | 0.0 | 136 |  |  |  |  |
| P0 |  | independent | 42 | 0.667 | 0.182 | 0.286 | 284 |  |  |  |  |
| P1:ttl_days=14 |  | independent | 42 | 0.143 | 0.047 | 0.0 | 244 |  |  |  |  |
| P2 |  | independent | 42 | 0.881 | 0.225 | 0.0 | 272 |  |  |  |  |
| P3 |  | independent | 42 | 0.667 | 0.182 | 0.286 | 284 |  |  |  |  |
| P4 |  | independent | 42 | 0.667 | 0.182 | 0.286 | 284 |  |  |  |  |
| P5 |  | independent | 42 | 0.548 | 0.146 | 0.095 | 283 |  |  |  |  |
| NOMEM |  | orchestrator | 14 | 0.0 | 0.0 | 0.0 | 136 | 28 | 0 | 0 |  |
| P0 |  | orchestrator | 14 | 0.714 | 0.19 | 0.286 | 284 | 28 | 0 | 0 |  |
| P1:ttl_days=14 |  | orchestrator | 14 | 0.143 | 0.047 | 0.0 | 244 | 6 | 22 | 0 |  |
| P2 |  | orchestrator | 14 | 0.929 | 0.233 | 0.0 | 272 | 23 | 5 | 0 |  |
| P3 |  | orchestrator | 14 | 0.714 | 0.19 | 0.286 | 284 | 25 | 0 | 3 |  |
| P4 |  | orchestrator | 14 | 0.714 | 0.19 | 0.286 | 284 | 25 | 3 | 0 |  |
| P5 |  | orchestrator | 14 | 0.5 | 0.146 | 0.071 | 275 | 11 | 17 | 0 |  |
| NOMEM |  | shared | 14 | 0.0 | 0.0 | 0.0 | 136 | 28 | 0 | 0 | 5 |
| P0 |  | shared | 14 | 0.714 | 0.19 | 0.286 | 284 | 28 | 0 | 0 | 5 |
| P1:ttl_days=14 |  | shared | 14 | 0.143 | 0.047 | 0.0 | 244 | 6 | 22 | 0 | 3 |
| P2 |  | shared | 14 | 0.929 | 0.233 | 0.0 | 272 | 23 | 5 | 0 | 5 |
| P3 |  | shared | 14 | 0.714 | 0.19 | 0.286 | 284 | 25 | 0 | 3 | 5 |
| P4 |  | shared | 14 | 0.714 | 0.19 | 0.286 | 284 | 25 | 3 | 0 | 5 |
| P5 |  | shared | 14 | 0.5 | 0.152 | 0.143 | 275 | 11 | 17 | 0 | 4 |
