# Pre-run audit of the final campaign (12 October 2026)

Everything below was checked offline against the saved cache and data before
any paid call. `make preflight` reproduces the cache and detection checks.

## Problems found and fixed

| # | Problem | Effect on earlier results | Fix |
|---|---|---|---|
| 1 | Facts stored in the opposite direction (`Ardern \| head_of_government_of \| New Zealand` then `New Zealand \| head_of_government \| Hipkins`) were never matched as the same slot. | On MQuAKE-T, 28 of 96 supersessions were never closed, so P2 could not act on them. | Normalised matching now also matches a fact written the other way round when the shared entity sits on opposite sides. Detected supersessions on MQuAKE-T: 63 to 90 of 96. All 28 new closures checked by hand and correct. Facts that only share an object (`A citizen_of Malta`, `B citizen_of Malta`) are deliberately not matched. Exact mode is unchanged. 4 new tests. |
| 2 | Reasoning models given 1,024 tokens for extraction sometimes returned a truncated thought instead of JSON, and the session was silently stored as having no facts. | ConvoMem: 64 of 200 sessions unparseable. RQ4 pilot: 20 of 38 sessions (one writer returned no facts at all), which is a large part of why the pilot found zero contradictions. MQuAKE-T and FactConsolidation: none. | A session whose reply has no parseable fact list is extracted again with 4,096 tokens (`extract_retry_tokens`). Sessions that parsed the first time keep their cached extraction exactly. Failures after retry are recorded in every cell's summary. |
| 3 | For ConvoMem only the last of 10 conversation graphs was saved, and the memory totals in the summary covered only that conversation. | Mechanism analysis on ConvoMem was impossible (9% of answers traceable). | Every conversation's graph is saved (`graph_snapshots`) and the summary carries totals over all conversations (`memory_totals`). |
| 4 | MQuAKE-T data artefact: in 7 questions a later background sentence restates the old value as current (New York City; Malawi, Kenya and Honduras head of state and government pairs). FactConsolidation has 1 such question. | Those answers are counted as stale although memory genuinely says the old value. | Not changed in the data. The analysis reports every result twice, with and without these questions. |
| 5 | RQ4 independent and orchestrator topologies extracted with a single writer whose extractions were mostly not cached. | Would have meant new, different extractions from the single-agent run. | They now use the same cached extraction chain as the single-agent matrix (`single_extract_model`). |
| 6 | Cross-writer contradiction counting required identical subject and relation, so it undercounted closures found by normalised or LLM matching. | RQ4 cross-writer counts too low. | Superseder is now found by shared entity and matching time. |
| 7 | Spend could not be tracked. | Budget overruns possible. | OpenRouter reports cost per call; every run prints spend after each cell and stops at its budget. |
| 8 | Answer records stored only total tokens. | Cost per correct answer could not be priced. | Records now carry prompt and completion tokens separately. |

## Verified, no change needed

* Every extraction for the three benchmarks is cached (0 misses), so all policies and all answer models start from identical facts.
* No current answer is wrongly closed on any benchmark (the "gold closed" count is 0 under both modes).
* Judge, P4 maintenance model and contradiction model are fixed and are never an answer model.
* 146 offline tests pass; every config was smoke-tested end to end with the offline provider.

## Detection coverage after the fixes (normalised matching)

| benchmark | questions with a superseded answer | old value closed | old value stored but not closed |
|---|---|---|---|
| MQuAKE-T | 96 | 90 | 6 |
| FactConsolidation | 65 | 60 | 5 |
| ConvoMem | 100 | 16 | 34 |

ConvoMem's low coverage is the honest limit of rule-based detection on natural
dialogue: the two mentions of a value are extracted under different subjects or
relation names (`nexus_solutions | contact_number` against `contact | phone_number`).
The substrate ablation measures how much the LLM matching mode recovers.
