# Summary table

| policy | model | topology | n_questions | accuracy | f1 | staleness | tokens_per_q | active_facts | pruned | write_rejections | cross_writer_invalidations |
|---|---|---|---|---|---|---|---|---|---|---|---|
| P2:grace_days=1.0 | openrouter:minimax/minimax-m3 |  | 100 | 0.74 | 0.429 | 0.12 | 806 | 298 | 82 | 0 |  |
| P2:grace_days=3.0 | openrouter:minimax/minimax-m3 |  | 100 | 0.75 | 0.438 | 0.13 | 797 | 303 | 77 | 0 |  |
| P2:grace_days=7.0 | openrouter:minimax/minimax-m3 |  | 100 | 0.77 | 0.444 | 0.14 | 783 | 324 | 56 | 0 |  |
| P2:grace_days=14.0 | openrouter:minimax/minimax-m3 |  | 100 | 0.79 | 0.451 | 0.13 | 757 | 345 | 35 | 0 |  |
| P2:grace_days=21.0 | openrouter:minimax/minimax-m3 |  | 100 | 0.76 | 0.434 | 0.13 | 742 | 364 | 16 | 0 |  |
| P2:grace_days=1.0 | openrouter:z-ai/glm-5.2 |  | 100 | 0.8 | 0.526 | 0.05 | 670 | 298 | 82 | 0 |  |
| P2:grace_days=3.0 | openrouter:z-ai/glm-5.2 |  | 100 | 0.81 | 0.522 | 0.04 | 676 | 303 | 77 | 0 |  |
| P2:grace_days=7.0 | openrouter:z-ai/glm-5.2 |  | 100 | 0.8 | 0.529 | 0.06 | 648 | 324 | 56 | 0 |  |
| P2:grace_days=14.0 | openrouter:z-ai/glm-5.2 |  | 100 | 0.8 | 0.515 | 0.05 | 645 | 345 | 35 | 0 |  |
| P2:grace_days=21.0 | openrouter:z-ai/glm-5.2 |  | 100 | 0.81 | 0.533 | 0.05 | 624 | 364 | 16 | 0 |  |
