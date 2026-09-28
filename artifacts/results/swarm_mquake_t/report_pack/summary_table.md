# Summary table

| policy | model | topology | n_questions | accuracy | f1 | staleness | tokens_per_q | active_facts | pruned | write_rejections | cross_writer_invalidations |
|---|---|---|---|---|---|---|---|---|---|---|---|
| NOMEM |  | shared | 96 | 0.0 | 0.003 | 0.0 | 156 | 140 | 0 | 0 | 0 |
| P0 |  | shared | 96 | 0.333 | 0.357 | 0.271 | 710 | 140 | 0 | 0 | 0 |
| P1:ttl_days=20 |  | shared | 96 | 0.281 | 0.303 | 0.135 | 729 | 79 | 61 | 0 | 0 |
| P2 |  | shared | 96 | 0.365 | 0.357 | 0.271 | 710 | 140 | 0 | 0 | 0 |
| P3 |  | shared | 96 | 0.365 | 0.357 | 0.271 | 710 | 140 | 0 | 0 | 0 |
