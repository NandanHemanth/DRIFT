# Summary table

| policy | model | topology | n_questions | accuracy | f1 | staleness | tokens_per_q | active_facts | pruned | write_rejections | cross_writer_invalidations |
|---|---|---|---|---|---|---|---|---|---|---|---|
| NOMEM |  | independent | 42 | 0.0 | 0.0 | 0.0 | 65 |  |  |  |  |
| P0 |  | independent | 42 | 0.667 | 0.233 | 0.286 | 173 |  |  |  |  |
| P1:ttl_days=14 |  | independent | 42 | 0.143 | 0.059 | 0.0 | 151 |  |  |  |  |
| P2 |  | independent | 42 | 0.881 | 0.288 | 0.0 | 172 |  |  |  |  |
| P3 |  | independent | 42 | 0.667 | 0.233 | 0.286 | 173 |  |  |  |  |
| P4 |  | independent | 42 | 0.667 | 0.233 | 0.286 | 173 |  |  |  |  |
| P5 |  | independent | 42 | 0.5 | 0.17 | 0.143 | 172 |  |  |  |  |
| NOMEM |  | orchestrator | 14 | 0.0 | 0.0 | 0.0 | 65 | 28 | 0 | 0 |  |
| P0 |  | orchestrator | 14 | 0.714 | 0.243 | 0.286 | 173 | 28 | 0 | 0 |  |
| P1:ttl_days=14 |  | orchestrator | 14 | 0.143 | 0.059 | 0.0 | 151 | 6 | 22 | 0 |  |
| P2 |  | orchestrator | 14 | 0.929 | 0.299 | 0.0 | 172 | 23 | 5 | 0 |  |
| P3 |  | orchestrator | 14 | 0.714 | 0.243 | 0.286 | 174 | 25 | 0 | 3 |  |
| P4 |  | orchestrator | 14 | 0.714 | 0.243 | 0.286 | 173 | 25 | 3 | 0 |  |
| P5 |  | orchestrator | 14 | 0.643 | 0.221 | 0.071 | 175 | 11 | 17 | 0 |  |
| NOMEM |  | shared | 14 | 0.0 | 0.0 | 0.0 | 65 | 28 | 0 | 0 | 5 |
| P0 |  | shared | 14 | 0.714 | 0.243 | 0.286 | 173 | 28 | 0 | 0 | 5 |
| P1:ttl_days=14 |  | shared | 14 | 0.143 | 0.059 | 0.0 | 151 | 6 | 22 | 0 | 3 |
| P2 |  | shared | 14 | 0.929 | 0.299 | 0.0 | 172 | 23 | 5 | 0 | 5 |
| P3 |  | shared | 14 | 0.714 | 0.243 | 0.286 | 174 | 25 | 0 | 3 | 5 |
| P4 |  | shared | 14 | 0.714 | 0.243 | 0.286 | 173 | 25 | 3 | 0 | 5 |
| P5 |  | shared | 14 | 0.643 | 0.229 | 0.071 | 172 | 11 | 17 | 0 | 4 |
