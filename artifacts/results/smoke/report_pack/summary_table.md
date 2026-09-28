# Summary table

| policy | model | topology | n_questions | accuracy | f1 | staleness | tokens_per_q | active_facts | pruned | write_rejections | cross_writer_invalidations |
|---|---|---|---|---|---|---|---|---|---|---|---|
| NOMEM | mock |  | 14 | 0.0 | 0.0 | 0.0 | 84 | 12 | 0 | 0 |  |
| P0 | mock |  | 14 | 0.714 | 0.19 | 0.286 | 221 | 12 | 0 | 0 |  |
| P1:ttl_days=35 | mock |  | 14 | 0.5 | 0.114 | 0.071 | 206 | 6 | 6 | 0 |  |
| P2 | mock |  | 14 | 0.929 | 0.233 | 0.0 | 221 | 9 | 3 | 0 |  |
| P3 | mock |  | 14 | 0.714 | 0.19 | 0.286 | 221 | 11 | 0 | 1 |  |
| P4 | mock |  | 14 | 0.714 | 0.19 | 0.286 | 221 | 11 | 1 | 0 |  |
| P5 | mock |  | 14 | 0.571 | 0.142 | 0.143 | 182 | 5 | 7 | 0 |  |
