# Final run (v3): pre-run check, design, story and analysis plan

Status: **plan for approval. No code has been changed and nothing has been run.** Decisions marked **[confirm]** need your answer before I write any code. After you approve, I prepare the code and configs, you run the checks on your Mac and send me the output, and only then the campaign starts.

---

## 1. Pre-run check (done today, offline)

| Check | Result | Action |
|---|---|---|
| Test suite | 148 of 148 pass | none |
| Uncommitted changes | the final-run code (`pipeline.py`, `runner.py`, `swarm.py`, analysis files) is modified but **not committed** | commit before v3, so every cell can record the exact code version |
| Spend accounting | cell summaries do not store cost; the previous main matrix cost about $8.20 per run at list price ($6.78 billed) | add cost per cell to every summary |
| Model availability | last confirmed in October; Qwen3 8B has already disappeared once | `make final-check` must pass for all 6 models on their pinned providers before the run |
| Repeat runs | the cache returns the stored answer for an identical request, so a "repeat" today would replay run 1 exactly | add a replicate tag to the cache key (run 1 unchanged, runs 2 and 3 fresh calls) |
| Reproducibility record | configs are regenerated from `build_final_configs.py`, but the run does not save them alongside results | save the exact config, code commit and model list with every results folder |

---

## 2. What changes in v3, and why

Everything that is not listed here stays exactly as in the October final run: the 7 policies and their settings, the 5 answer models and DeepSeek V4.1 Flash, the 3 benchmarks, the answer prompt, the grading rules and judge, k = 25, temperature 0, and provider pinning.

### 2.1 Extraction with context, as Zep does

- **Zep** (Rasmussen et al., 2025, Sec. 2.2.1): the extractor reads the current message plus the previous n = 4 messages "to provide context", but extracts entities only from the current message.
- **DRIFT v3:** the extractor reads the last 4 lines before the session, marked as *context only*, then the session. The prompt says to extract facts only from the session's own lines.
- **Why "context only" matters:** if earlier lines were simply prepended, their facts would be extracted again, with the new session's date, which would create false updates.
- **Expected effect:**
  - MQuAKE-T and FactConsolidation: little, since each line is a self-contained fact.
  - ConvoMem: values revised in passing ("let's do Saturday instead") should be resolved more often. That targets the extraction ceiling found last time (the answer was stored for only 14 of 100 questions).

### 2.2 Lexical signal: word overlap, unchanged (decided 8 November)

- **Kept:** the share of the question's words (3+ letters) found in the fact, as in October.
- **Why:** it is the setting the 1,000-weighting sweep and the held-out check validated, so v3 stays comparable with October.
- **BM25:** implemented (`lexical: "bm25"`) and tested, but not used.
- **What to say in the thesis:** word overlap is a simplified form of BM25 (Robertson and Zaragoza, 2009) without rarity weighting. In the New Zealand example, both rank the old and new fact identically; separating them is the forgetting policy's job.

### 2.3 Three runs

- Run 1 uses fresh calls (the extraction change invalidates the old cache anyway). Runs 2 and 3 repeat run 1 with a different replicate tag and nothing else changed.
- **Reported for every number:** mean ± standard deviation over the 3 runs, the range, and the share of questions whose verdict flips between runs.
- **Purpose, stated correctly:** repeats do not reduce randomness. They measure it, and show whether the conclusions survive it.

### 2.4 Same 5 models and 3 benchmarks everywhere [confirm scope]

| Study | Oct. run | v3 proposal |
|---|---|---|
| Main matrix (7 policies × 5 models × 3 benchmarks = 105 cells) | 1 run | **3 runs** |
| RQ4 topologies (shared × 3 matching modes, independent, orchestrator) | Gemini only, MQuAKE-T | **5 answer models, 3 benchmarks, 3 runs** |
| Grace period with history questions (0, 1, 3, 7, 14, 21 days, never) | 2 small models | 5 models, 3 benchmarks, 1 run |
| Contradiction matching (exact, normalised, LLM) | 2 small models | 5 models, 3 benchmarks, 1 run |
| Retrieval weights held-out check | 2 small models, FactConsolidation | 5 models, 3 benchmarks, 1 run, including RRF and recency = 0 |

---

## 3. Cost and time (from `make v3-estimate`, which counts every answer exactly)

The first estimate ($85) undercounted RQ4: with all 5 answer models, every RQ4 cell is answered 5 times, and the independent topology answers once per agent. Corrected, list prices (October billed about 17% below list), one process at a time:

| Study | Answers | List USD | Hours |
|---|---|---|---|
| Main matrix, per run | 10,360 | $9.3 | 4.3 |
| RQ4, per run (shared ×3 matching modes, independent with 3 agents, orchestrator) | 50,320 | $47.3 | 21 |
| Follow-ups once (grace with history, matching, weights incl. RRF and no recency) | 32,370 | $29.6 | 13.5 |

| Option | List USD | Hours (sequential) |
|---|---|---|
| A. Main ×3, RQ4 ×3, follow-ups once | ~$200 | ~89 |
| B. As A, but the independent topology only in run 1 | ~$150 | ~70 |
| C. Main ×3, RQ4 once, follow-ups once | ~$105 | ~52 |

Running two or three studies at the same time in separate terminals cuts the wall-clock time roughly in proportion.

## 4. RQ4: recommendation from the related work

**What related work measures in shared memory:**
- GateMem (Ren et al., 2026): utility, access control, active forgetting.
- Governed Shared Memory (Margalit et al., 2026): unauthorized leakage, **stale propagation**, **contradiction persistence**, provenance collapse.
- Collaborative Memory (Rezazadeh et al., 2025): provenance and permissions.
- Yu et al. (2026): memory **consistency** across agents is "the most pressing open challenge".

None tests whether forgetting policies keep their ranking when several agents share memory. That is DRIFT's gap.

**What ranking-agreement methodology recommends:**
- Benchmark Agreement Testing (Perlitz et al., 2024) compares rankings with **Kendall's τ on ranks** and Pearson on scores.
- It warns that agreement varies with how many items are ranked (0.65 to 0.99 depending on model subset).

**Recommendation for RQ4 in v3**

1. **Primary measure: Kendall's τ**, with exact permutation p-values (all 720 orderings), because it is the BAT standard and behaves better than Spearman with 6 items and ties. Report Spearman alongside; Pearson only as context.
2. **Add an effect-transfer test**, which has far more statistical power than ranking 6 items: in each topology, is P2's gain over P0 still positive? Use a paired McNemar test per question, with a bootstrap 95% interval, per model.
3. **Add the two measures named by related work:**
   - **Stale propagation:** answers that repeat a value written by a *different* agent and later replaced.
   - **Contradiction persistence:** cross-writer contradictions left open at the end of the run.

   Both come from fields DRIFT already records (provenance per fact, closed-by-different-writer counts).
4. **Report variance across the 3 runs**, so ranking agreement is shown to be stable, not a single draw.
5. **With all 5 answer models,** RQ4 can also test whether small models gain most in shared memory, linking it to the thesis story.

---

## 5. The story: why DRIFT matters

1. **The problem.** An agent's memory keeps every value a fact has ever had. Old and new versions differ in one word, so retrieval returns both. The October run measured this: under append-only memory the old value reached the prompt for 100% of MQuAKE-T and 95% of FactConsolidation questions.
2. **Who pays for it.** Frontier models read the dates and pick the newer value; small models do not. Llama 3.1 8B repeated the old value in 21% (MQuAKE-T) and 55% (FactConsolidation) of the cases where both were shown.
3. **What fixes it.** If memory detects the replacement and hides the old fact, the old value never reaches the model. A model cannot repeat what it never sees, so staleness falls to near zero for every model, weak or strong.
4. **Why that matters in practice.** Accuracy, prompt tokens and stored facts all improve together. The gain is largest for the cheapest models: Llama 3.1 8B came within about one point of frontier models on real updates at about 1/160 of the cost per correct answer.
5. **What does not work.** Forgetting by age deletes true facts, novelty gates refuse corrections, LLM consolidation deletes updates it disbelieves, and graph support without time keeps the old value.
6. **The limit.** In natural dialogue, what reaches memory matters more than what leaves it. v3's extraction context tests the first remedy.

**Thesis framing to consider:** "Correct forgetting moves the burden of tracking change from the model to the memory. That is why it matters most for small models." The v3 run tests this directly with a pre-registered prediction (Section 6.1).

---

## 6. Analysis plan for v3

### 6.1 Predictions written down before the run (pre-registration)

Recording predictions before seeing the data is standard practice and protects against reading the results to fit the story.

| ID | Prediction | Test |
|---|---|---|
| H1 | P2 accuracy ≥ P0 on MQuAKE-T and FactConsolidation, in all 3 runs | paired McNemar per run, Holm-corrected; mean ± SD |
| H2 | P2 staleness < P0 | same |
| H3 | P2 gain over P0 is larger for small than for frontier models | bootstrap 95% CI of the difference in gains (tier interaction) |
| H4 | P2 > P5 (the timeline, not the graph) | paired McNemar |
| H5 | P2 is sound (never hides a still-true fact) on the two fact benchmarks | soundness = 100% in every run |
| H6 | the policy ranking transfers to multi-agent memory | Kendall's τ, exact p; P2-vs-P0 effect per topology |
| H7 | extraction context raises ConvoMem's share of answers stored | October 14% vs v3, same questions |
| H8 | stability: no headline conclusion changes across runs | flip rate; SD of every headline number |

### 6.2 Theoretical analysis, each paired with an empirical check

| Theory | Prediction from the theory | Empirical check |
|---|---|---|
| Staleness bound: P(stale) = P(old value in prompt) × P(model repeats it) | a complete policy gives zero staleness for any model | measured P(stale \| old value absent) should be 0% |
| Soundness and completeness of P2 reduce to the correctness of contradiction detection | P2 errors = detection misses and false closures | match each P2 error to a detection log entry |
| Token saving: P2 removes closed facts from the top 25 | saving ≈ (closed facts in the top 25 / 25) × tokens per line | predicted vs measured prompt tokens |
| Grace period: history accuracy is bounded by the share of closed facts younger than the grace period | curve predicted from the age distribution of closed facts | predicted vs measured history accuracy |
| P3 refuses any correction more similar than 0.9 | refusals = corrections above the threshold | count refused corrections |
| P5 picks the better-supported value, usually the older one | P5 errors concentrate on long-lived old values | support counts for P5's wrong answers |

### 6.3 Rationale analysis

One paragraph per design choice, each with its measured reason:
- hide before delete;
- the grace period;
- normalised, direction-insensitive matching;
- the speech-act guard;
- the answer prompt not resolving conflicts;
- k = 25;
- the retrieval weights and BM25;
- extraction with context.

### 6.4 Generality: where DRIFT applies and where it does not

| Applies well | Applies poorly |
|---|---|
| Facts with one current value (who reports to whom, prices, addresses, schedules) | Relations that hold many values at once (friends, hobbies, meetings) |
| Explicit updates ("I now report to Daniel") | Implicit or cascading updates (STALE Type II: a broken leg invalidates a cycling commute) |
| Any answer model, most of all small ones | Dialogue where extraction misses the fact |
| Single agent; several agents with semantic matching | Several writers with exact-name matching only |

Domains: personal assistants, CRM and customer records, enterprise knowledge bases, clinical and financial records where audit history matters (the bitemporal record answers "what did the agent believe on date X").

### 6.5 Output standards for every table, chart and figure

- **Percentages throughout:** accuracy, staleness, soundness and completeness shown as %. Differences are absolute, shown with %, and each caption says "difference in percentage points".
- **Axes:** percentage axes run 0 to 100 and never above 100.
- **Uncertainty:** every chart shows the mean over 3 runs with error bars (± 1 SD across runs) or 95% bootstrap intervals, stated in the caption.
- **Self-contained captions:** each figure and table defines every term and gives n (questions, runs, models).
- **Format:** vector PDF for the thesis, PNG for slides; a consistent colour per policy; P2 highlighted.
- **Statistics:**
  - paired McNemar (exact), Holm-corrected;
  - paired bootstrap 95% CIs (5,000 resamples);
  - Kendall's τ and Spearman ρ with exact permutation p-values;
  - Cohen's κ for the judge;
  - mean ± SD and flip rate across runs.
- **Judge validation against humans:** you grade a blind sample of 150 to 200 answers, and we report agreement and κ. This closes the gap identified in `RESEARCH_STANDARDS.md`.

### 6.5a Why each statistic, with its reference

| Statistic | Used for | Why this one | Reference |
|---|---|---|---|
| Exact McNemar test | P2 vs another policy on the same questions | paired yes/no outcomes; uses only questions where the two disagree | McNemar (1947); recommended for comparing classifiers by Dietterich (1998) |
| Holm correction | many comparisons at once | keeps the chance of any false positive at 5%, less conservative than Bonferroni | Holm (1979) |
| Paired bootstrap 95% CI | size of every difference | no distribution assumption; standard in NLP evaluation | Efron and Tibshirani (1993); Dror et al. (2018) |
| Mean ± SD over runs, flip rate | stability across the 3 runs | separates model randomness from question sampling | Mem0 reports mean ± 1 SD over 10 runs (Chhikara et al., 2025) |
| Kendall's τ, exact permutation p | RQ4 ranking agreement | the Benchmark Agreement Testing standard; reliable with few items and ties | Kendall (1938); Perlitz et al. (2024) |
| Spearman's ρ | RQ4, alongside τ | weights large rank moves more | Spearman (1904) |
| Pearson's r | RQ4, context only | agreement of the scores themselves | Pearson (1896); Perlitz et al. (2024) |
| Cohen's κ | judge vs reference grader | agreement beyond chance | Cohen (1960); Landis and Koch (1977) for the bands |
| Judge vs human agreement | trusting the LLM judge | the field validates judges against people | LongMemEval (Wu et al., 2025); STALE (Chao et al., 2026) |

### 6.6 Deliverables after the run

- **Report:** `FINAL_REPORT_V3.md`, covering every result, each with its theory-vs-measurement check, plus the run-to-run analysis.
- **Figures and tables:** all to the standards above; CSVs for every table.
- **Dashboard:** updated interactive dashboard.
- **Run record:** what ran, what failed and was retried, cost per study.
- **RQ4 deep analysis:** every topology × matching mode × policy × model × benchmark × run, with ranking agreement (τ, ρ, r), the P2-vs-P0 effect per topology, stale propagation, contradiction persistence and cross-writer closures, each with tables and figures to the same standards.

---

## 7. Code changes needed (after your approval)

1. Extraction: context window of the previous 4 lines, marked context-only, plus tests.
2. Lexical: BM25 normalised per question (if confirmed), with config flag `lexical: "bm25" | "overlap"`, plus tests.
3. Cache: replicate tag in the cache key; `--replicate 1|2|3` in the runner and swarm.
4. RQ4: 5 answer models and 3 benchmarks in the swarm configs; stale-propagation and contradiction-persistence metrics.
5. Weights check: RRF and recency = 0 configurations.
6. Run record: cost, code commit and config saved per cell.
7. Dry run: exact call count and cost estimate per study before spending.
8. Analysis: cross-run aggregation, the theory-vs-empirical checks, and the plotting style module (percent axes 0 to 100).

**Order of work:** commit current code → I make changes 1 to 8 with tests → you run `make test`, `make final-check`, `make preflight` and the dry run, and send the output → you approve the cost → the 3 runs → analysis.
