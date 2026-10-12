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

## Provider check (`make final-check`, 12 October)

* Qwen3 8B is no longer served on OpenRouter (zero endpoints). It is replaced by
  Qwen3 14B, same family and thinking mode, pinned to DeepInfra. The deep
  sensitivity analysis keeps its Qwen3 8B results; the final matrix uses 14B.
* The MQuAKE-T and FactConsolidation extraction providers (NVIDIA, Cerebras, Groq,
  Hugging Face, Mistral) are all gone, which does not matter: every one of their
  extractions is cached and none of those sessions needs a retry.
* The ConvoMem extraction chain and all five RQ4 writers are still served.
* The judge check stopped on one item that OpenRouter refused with HTTP 403
  (moderation). Refused items are now skipped and listed instead of stopping the run.

## Model rule: six models, one provider each, no fallback

The final campaign may use only these models, each pinned to one upstream
provider with `allow_fallbacks: false`, and no model ever falls back to another.
All configs are generated from `scripts/build_final_configs.py`, so the rule lives
in one file.

| role | model | provider |
|---|---|---|
| answer, frontier | GPT-6.1 Sol (low reasoning effort) | OpenAI |
| answer, frontier | Claude Sonnet 5.5 | Anthropic |
| answer, mid | Gemini 3.8 Flash (low reasoning effort; reasoning cannot be switched off) | Google AI Studio |
| answer, small | Llama 3.1 8B | DeepInfra |
| answer, small reasoning | Qwen3 14B (thinking on), replacing Qwen3 8B | DeepInfra |
| extraction, judge, P4 review, LLM contradiction check | DeepSeek V4.1 Flash (reasoning off) | DeepInfra (DeepSeek's own API is excluded by the account's no-training privacy setting) |

Consequences:

* Every session of all three benchmarks is extracted again, once, by DeepSeek V4.1
  Flash (`make preflight`). The old extractions came from models outside the list.
  Graphs therefore differ from earlier campaigns; the detection-coverage numbers
  above will be recomputed by the preflight and reported in the final analysis.
* RQ4's five writers are the five answer models, so the shared memory is still
  written by five different model families.
* The judge check compares DeepSeek V4.1 Flash with Claude Sonnet 5.5.

## Judge check (12 October)

DeepSeek V4.1 Flash against Claude Sonnet 5.5 on 198 existing answers: agreement
0.939, Cohen's kappa 0.878 (MQuAKE-T 0.955, ConvoMem 0.939, FactConsolidation
0.924). Of the 12 disagreements, 5 were DeepSeek grading "I don't know" as
correct when the gold answer is counterfactual. Refusals that do not contain the
gold answer are now graded incorrect by rule before the judge is asked
(`is_abstention` in `pipeline.py`), which removes that bias for every policy
and in particular for NOMEM. Two of Claude's "incorrect" verdicts were on answers
that state the gold verbatim (Thomas Kyd, association football): the reference
judge also leans on world knowledge for counterfactual golds, so neither judge is
treated as ground truth; the agreement figure is the reported reliability.

After the refusal rule, rerun on the same 198 answers (all cached, $0): agreement
**0.960**, kappa **0.919** (ConvoMem 0.970, FactConsolidation 0.955, MQuAKE-T
0.955), with the remaining 8 disagreements split evenly (4 lenient, 4 strict), so
the judge shows no remaining direction of bias.

## Pilot (P0 and P2 on MQuAKE-T, five models, $0.78)

The pilot exposed a flaw in the staleness metric. Claude Sonnet 5.5 explains its
answers ("Joe Biden is the current head of state; the memory also lists Donald
Trump, dated earlier"), so "the answer contains the old value" flagged 75 of its
96 P0 answers as stale while it answered 97.9% correctly. Only 1 of the 75
actually asserted the old value. Staleness now means the answer contains the old
value and not the current one; every question carries a short `current_answer`
(added by `scripts/add_current_answer.py`, deterministic, 261 of 261 recovered),
and plain containment is kept as `mentions_old`. The analysis recomputes
staleness from the saved answers, so the pilot cells are scored with the corrected
definition too.

| model | P0 accuracy | P0 staleness | P2 accuracy | P2 staleness |
|---|---|---|---|---|
| GPT-6.1 Sol | 0.990 | 0.010 | 0.990 | 0.010 |
| Claude Sonnet 5.5 | 0.979 | 0.010 | 0.990 | 0.000 |
| Gemini 3.8 Flash | 0.990 | 0.010 | 0.990 | 0.010 |
| Llama 3.1 8B | 0.771 | 0.208 | 0.979 | 0.010 |
| Qwen3 14B | 0.948 | 0.021 | 0.979 | 0.000 |

The remaining 0.010 for the frontier models is the New York City data artefact.
