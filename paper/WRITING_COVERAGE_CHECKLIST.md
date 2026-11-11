# Writing coverage checklist: every paper, every section

Detailed points so nothing important is missed while writing. Points only: the sentences are yours.

- **Part 1:** for every reference, the things you must cover, the numbers worth quoting, the nuances that show you read it carefully, and mistakes to avoid.
- **Part 2:** for every chapter and section (1 to 6), a tick-list of what must appear, with the figures, tables and numbers that belong there.

Every number in Part 1 comes from the paper (read in full, or the arXiv abstract where marked). Every DRIFT number in Part 2 comes from `paper/V3_ANALYSIS.md`.

---

# Part 1. Per-paper checklists

Each card has three sections:

- **Must cover:** the minimum for a correct description.
- **Worth quoting:** numbers or phrases that add precision.
- **Nuance / avoid:** what a careful reader will check.

## 1.1 MemGPT `packer2023memgpt`

**Must cover**
- The problem it addresses: a fixed context window, and long-context models using extra context poorly.
- The OS analogy: "virtual context management", paging between fast and slow memory.
- The two tiers:
  - main context: system instructions, an editable working context, a FIFO message queue;
  - external context: recall storage (all messages) and archival storage (searched by similarity).
- The model manages memory itself through function calls.
- The memory-pressure warning, then eviction and recursive summarisation.
- Evaluated on multi-session chat (the DMR task it introduced) and on document analysis.

**Worth quoting**
- DMR with GPT-4 Turbo: 93.4% with MemGPT, 35.3% without; ROUGE-L 0.827 vs 0.359.

**Nuance / avoid**
- DMR asks about static facts, not changed ones. Do not imply MemGPT handles updates.
- Outdated records remain in archival storage and are retrievable: that is your DRIFT link, since it behaves like P0.
- Zep reported it could not reproduce DMR from the paper's description. Mention it only if you discuss reproducibility.

## 1.2 Mem0 `chhikara2025mem0`

**Must cover**
- Two phases:
  1. **Extraction:** newest message pair, with a conversation summary and the last 10 messages.
  2. **Update:** for each fact, retrieve the 10 most similar memories, and an LLM tool call picks ADD, UPDATE, DELETE or NOOP.
- Graph variant Mem0^g: entity-relation graph, where contradicted relations are marked invalid rather than deleted.
- Benchmark: LoCoMo, four categories (single-hop, multi-hop, temporal, open-domain).
- Metrics: F1, BLEU-1 and LLM-as-a-Judge (J). They argue lexical metrics mislead on facts.
- 10 runs, mean ± SD, temperature 0.

**Worth quoting** (overall J on LoCoMo, mean ± SD over 10 runs)

| System | J |
|---|---|
| Mem0 | 66.88 ± 0.15% |
| Mem0^g | 68.44 ± 0.17% |
| Zep | 65.99% |
| OpenAI memory | 52.90% |
| A-Mem | 48.38% |
| **Full context** | **72.90%** |

- Mem0 uses about 1.8K tokens per conversation, against about 26K for full context.
- p95 latency is 91% lower and token use over 90% lower than full context.
- J is 26% higher (relative) than OpenAI's memory.

**Nuance / avoid**
- **Full context is more accurate than Mem0** (72.90% vs 66.88%). Mem0's case is cost and latency, not accuracy. Do not write that Mem0 beats full context in accuracy.
- Base Mem0 *deletes* on contradiction; only the graph variant invalidates.
- No staleness metric.
- Link to DRIFT: P4 (LLM-decided removal); Mem0 is the precedent for an LLM judge and for repeated runs.

## 1.3 Zep / Graphiti `rasmussen2025zep`, `graphiti`

**Must cover**
- Motivation: enterprise memory over changing data, not static RAG.
- Graphiti's three subgraphs: episodes (raw messages, kept), semantic entities and facts, communities.
- **Bitemporal**:
  - timeline T, when a fact held: t_valid, t_invalid;
  - timeline T′, when the system created or expired it.
- **Extraction context:** the current message plus the previous 4 messages; reflection to reduce hallucination; entity resolution by embedding, full-text search and an LLM.
- **Contradiction handling:** an LLM compares a new edge with related edges and invalidates the old one (sets t_invalid); nothing is deleted.
- **Retrieval:** cosine, BM25 and breadth-first graph search, then a reranker (RRF, MMR, graph distance, cross-encoder). Facts go to the prompt with date ranges.
- **Evaluation:** DMR against MemGPT, and LongMemEval with gpt-4o-mini and gpt-4o; GPT-4o judge.

**Worth quoting**
- DMR: 94.8% vs MemGPT 93.4%.
- LongMemEval:

  | Model | Full context | Zep | Context tokens (full vs Zep) | Latency (full vs Zep) |
  |---|---|---|---|---|
  | gpt-4o | 60.2% | 71.2% | 115K vs 1.6K | 28.9 s vs 2.58 s |
  | gpt-4o-mini | 55.4% | 63.8% | | |

- Knowledge-update category: gpt-4o-mini 76.9% (full) vs 74.4% (Zep), a 3.36% drop; gpt-4o 78.2% vs 83.3%, a 6.52% gain.

**Nuance / avoid**
- **Zep already invalidates instead of deleting. DRIFT must not claim that idea.** DRIFT's question is what to do with invalidated facts.
- Even Zep's knowledge-update accuracy is not uniformly better than full context.
- Single run, no significance tests.

## 1.4 A-MEM `xu2025amem`

**Must cover**
- Zettelkasten-inspired notes, each with content, timestamp, keywords, tags, context description, embedding and links.
- Linking a new note to its top-k similar notes.
- **Memory evolution:** an LLM rewrites existing notes' context and tags when new notes arrive.
- Evaluated on LoCoMo and DialSim, six foundation models, with lexical metrics.

**Worth quoting**
- In Mem0's later comparison with a judge, A-Mem scores 48.38% J. Cite Mem0 for that number, not A-MEM.

**Nuance / avoid**
- Its own paper reports only lexical metrics (F1, BLEU-1).
- Memory evolution is LLM rewriting of old memories, the risk Zhang et al. measure.
- Link to DRIFT: P4.

## 1.5 Generative Agents `park2023generative`

**Must cover**
- 25 agents in a sandbox town.
- The memory stream (timestamped observations).
- Retrieval = recency + importance + relevance:
  - each min-max normalised;
  - equal weights;
  - recency decays 0.995 per game hour since last access;
  - importance is an LLM rating from 1 to 10;
  - relevance is cosine similarity.
- Reflection and planning modules.
- Evaluation: human believability ratings, plus ablations.

**Nuance / avoid**
- Recency there means *time since last access*; DRIFT's means *valid-start date*. Say this when citing it as precedent.
- It measures believability, not factual correctness.

## 1.6 RAG `lewis2020rag`

**Must cover**
- Retrieve passages with a dense retriever (DPR), then generate with a seq2seq model (BART).
- RAG-Sequence vs RAG-Token.
- Open-domain QA results.
- Knowledge can be updated by swapping the index.

**Nuance / avoid**
- Cite it once, where "RAG" is first used.
- The index-swap idea assumes the index is current. DRIFT's setting is the opposite: old and new facts sit in the same index.

## 1.7 Zhang et al. `zhang2026faulty`

**Must cover**
- Setting: an LLM repeatedly consolidates experiences into a textual memory bank.
- Finding: utility rises, then degrades, and can fall below no memory.
- Mechanisms:
  - misgrouping unrelated experiences;
  - abstraction that drops applicability conditions;
  - overfitting to a narrow stream;
  - dependence on update order.
- Control: episodic-only memory (keep raw trajectories) stays competitive.
- ARC-AGI Stream with Retain, Delete and Consolidate actions: agents prefer to keep raw episodes, and that doubles accuracy over forced consolidation.
- Recommendation: raw episodes are first-class evidence; gate consolidation.

**Worth quoting**
- GPT-5.4 fails on 54% of ARC-AGI problems it had solved without memory, after consolidating from ground-truth solutions (abstract figure).

**Nuance / avoid**
- Their tasks are procedural (agent skills), not factual QA. Say the finding transfers by mechanism, not by task.
- Link to DRIFT: closing keeps evidence; P4's instability and unsoundness.

## 1.8 SAGE `wang2026sage`

**Must cover**
- The problem: write-side control is neglected; LLM decisions on every write are costly; wrong writes damage later answers.
- Method:
  - embeddings normalised to the unit sphere;
  - a von Mises-Fisher kernel density measures how covered a new fact is;
  - an adaptive threshold that tracks the memory's geometry;
  - routing: ADD (novel), NOOP (redundant), LLM merge only when uncertain.
- Evaluation: LoCoMo, seven open-weight backbones plus GPT-4o-mini; token F1, BLEU-1 and J; write-phase cost and latency.

**Worth quoting**
- Best average token F1 against Mem0 on all 7 open backbones.
- On GPT-4o-mini: **3.4×** lower write cost and **2.5×** lower latency, with only a small average judge-score gap.

**Nuance / avoid**
- The cost saving comes with a small drop in judge score. Do not say it is better on every metric.
- It is not evaluated on changing facts.
- Corrections are similar to what they correct, which is DRIFT's P3 argument.
- Use 3.4×, not 3.5×.

## 1.9 Xie et al. `xie2024adaptive`

**Must cover**
- Setup:
  - elicit the model's own (parametric) answer;
  - construct coherent conflicting evidence (counter-memory);
  - vary the mixture of supporting and conflicting evidence.
- Two findings:
  1. When the conflicting evidence is the only evidence and is coherent, models readily accept it ("chameleon").
  2. When supporting and conflicting evidence appear together, models show confirmation bias toward their own knowledge ("sloth").
- Order and amount of evidence matter.

**Nuance / avoid**
- Their conflict is prompt vs model weights. DRIFT's is old fact vs new fact, both in the prompt. Cite it for "the prompt strongly shapes answers", not as an identical setting.

## 1.10 Du (survey) `du2026memory`

**Must cover**
- Write, manage, read loop.
- Three-dimensional taxonomy: temporal scope, substrate, control policy.
- Five mechanism families: context-resident compression, retrieval-augmented stores, reflective self-improvement, hierarchical virtual context, policy-learned management.
- Evaluation metric stack: utility, efficiency, adaptivity, faithfulness.
- Open challenges, including **learned forgetting**.

**Nuance / avoid**
- Use it to establish that forgetting is open; do not over-quote a survey.

## 1.11 STALE `chao2026stale`

**Must cover**
- Implicit conflict: Type I (same attribute) and Type II (cascading), each with its example.
- 400 expert-validated scenarios, 1,200 queries, over 100 topics, contexts up to 150K tokens.
- Three probes: State Resolution, Premise Resistance, Implicit Policy Adaptation.
- Judge validated against humans (95.8% agreement).
- CUPMem prototype: write-time state consolidation with propagation-aware search.

**Worth quoting**
- Best model 55.2% overall.
- A gap between retrieving updated evidence and acting on it.

**Nuance / avoid**
- STALE studies implicit conflicts; DRIFT's benchmarks are explicit. Say so in scope (3.4) and limitations.
- STALE is model-side; DRIFT is memory-side.

## 1.12 Supersede `patel2026supersede`

**Must cover**
- The supersession gap: full context vs a bounded, self-maintained memory, on LongMemEval knowledge updates.
- Programmatic scoring:
  - r_cur: answer conveys the current value;
  - r_stale: answer asserts a superseded value.
- Paired McNemar; temperature 0 and greedy decoding.
- RL environment (GRPO) as a fix.

**Worth quoting**
- gpt-5.4: 92% to 77% (p < 0.005).
- As the conversation grows 24×: 68% to 28%; more memory gives no recovery (28% to 28%, n = 25).
- GRPO on a 3B model: 9.0% to 16.7% held-out.

**Nuance / avoid**
- Same staleness definition as DRIFT. Credit them for it; DRIFT adds the mentions/asserts split.
- Their fix trains the model; DRIFT's fixes the memory.

## 1.13 LoCoMo `maharana2024locomo`

**Must cover**
- Machine-human pipeline: LLM agents with personas and temporal event graphs, image sharing, human editing for consistency.
- 50 conversations, about 300 turns, about 9K tokens, up to 35 sessions.
- Tasks: QA in five categories, event summarisation, multimodal generation.
- Metric: F1 partial match.

**Nuance / avoid**
- The reason it is excluded: no question stores the superseded answer, so a stale answer cannot be scored.
- It is the standard benchmark, so say why you did *not* use it, not that it is bad.

## 1.14 LongMemEval `wu2025longmemeval`

**Must cover**
- 500 questions across five abilities: IE, MR, KU, TR, ABS.
- Scalable histories: S (about 115K tokens) and M (about 1.5M tokens).
- Framework: indexing, retrieval, reading; optimisations (session decomposition, fact-augmented keys, time-aware query expansion).
- GPT-4o judge with above 97% agreement with humans.

**Worth quoting**
- Commercial assistants and long-context LLMs show about a 30% accuracy drop over sustained interactions.

**Nuance / avoid**
- Knowledge-update questions record only the new answer. That is why staleness cannot be scored and why it is excluded.
- Its human-validated judge is the field's standard.

## 1.15 MQuAKE / MQuAKE-T `zhong2023mquake`

**Must cover**
- Motivation: knowledge in LLMs goes stale; editing methods were tested only on the edited fact.
- Edit = (s, r, o → o*).
- Multi-hop questions test whether an edit propagates.
- MQuAKE-CF (counterfactual) and MQuAKE-T (real Wikidata changes).
- MeLLo: edits in external memory, retrieved, self-checked for contradiction.

**Worth quoting**
- MQuAKE-T: 1,868 instances (1,421 two-hop, 445 three-hop, 2 four-hop).
- Example: UK head of government, Boris Johnson → Rishi Sunak.
- Parameter editing (ROME, MEMIT) fails badly on multi-hop.

**Nuance / avoid**
- DRIFT uses a 96-question **single-hop** derivation of MQuAKE-T, not the multi-hop task. Say so explicitly.

## 1.16 MemoryAgentBench / FactConsolidation `hu2026memoryagentbench`

**Must cover**
- Four competencies: accurate retrieval, test-time learning, long-range understanding, selective forgetting.
- Incremental chunked input with a "memorise" instruction.
- FactConsolidation:
  - built from MQuAKE counterfactual pairs (original and rewritten fact);
  - SH and MH versions at 6K, 32K, 64K and 262K tokens;
  - agents told to prefer later information.
- Metric: substring exact match.

**Worth quoting** (their validation table)

| | FactCon-SH 6K | FactCon-MH 6K | FactCon-MH 32K |
|---|---|---|---|
| GPT-4o | 92.0% | 28.0% | |
| o4-mini | 100.0% | 80.0% | 14.0% |

- Conclusion: the 6K single-hop task is solvable, so failures there are memory failures, not task difficulty.

**Nuance / avoid**
- DRIFT uses FactCon-SH 6K (100 questions, 65 with an old value). Their validation shows 6K SH is solvable, which supports your choice.
- **DRIFT does not tell the model to prefer later facts.** Explain why.

## 1.17 ConvoMem `pakhomov2025convomem` (arXiv abstract)

**Must cover**
- 75,336 QA pairs; categories include user facts, assistant recall, abstention, preferences, temporal changes, implicit connections.
- Memory starts from zero and grows, unlike a fixed RAG corpus.
- Full context vs RAG memory.

**Worth quoting**
- Full context reaches 70% to 82%; Mem0 30% to 45%, on histories under 150 conversations.
- Transition points: long context is best for about 30 conversations and viable up to about 150.

**Nuance / avoid**
- DRIFT uses 100 changing-fact questions over 10 conversations, a small subset. Say so.
- Their finding that extraction-based memory loses information matches DRIFT's extraction-bound ConvoMem result.

## 1.18 G-Memory `zhang2025gmemory` (arXiv abstract)

**Must cover**
- The problem: multi-agent memory ignores collaboration trajectories and has no cross-trial or agent-specific memory.
- Three graphs: insight, query, interaction.
- Bi-directional traversal (insights upward, trajectories downward); the hierarchy evolves after each task.
- Five benchmarks, three backbones, three frameworks.

**Worth quoting**
- Up to +20.89% embodied success and +10.12% knowledge-QA accuracy.

**Nuance / avoid**
- Task success only, with no notion of a fact becoming false.

## 1.19 Collaborative Memory `rezazadeh2025collaborative` (arXiv abstract)

**Must cover**
- Multi-user, multi-agent memory with permissions that differ between users and change over time.
- Bipartite graphs linking users, agents and resources.
- Private and shared tiers.
- Immutable provenance on every fragment.
- Read and write policies.

**Nuance / avoid**
- Governs who may see a fact, not whether it is current.
- DRIFT shares the provenance idea.

## 1.20 GateMem `ren2026gatemem`

**Must cover**
- Multiple principals with roles writing to and querying one memory.
- Three dimensions: utility (with state updates), access control, active forgetting (no recovery after a deletion request).
- Four domains, 91 episodes, 2,218 hidden checkpoints, leak targets.
- Memory Governance Score.
- GPT-4o judge checked against humans.

**Worth quoting**
- No method is strong on all three.
- Long-context prompting governs best at high token cost.
- Retrieval and external memory are cheaper but still leak unauthorised or deleted information.

**Nuance / avoid**
- "Active forgetting" there is *user-requested deletion*. DRIFT's completeness is *automatic hiding of superseded facts*. Call them related, not the same.

## 1.21 Governed Shared Memory `margalit2026governed` (arXiv abstract)

**Must cover**
- The fleet-memory problem and its four failure modes: unauthorised leakage, stale propagation, contradiction persistence, provenance collapse.
- Primitives: scoped retrieval, temporal supersession, provenance tracking, governed propagation.
- MemClaw (production service) and ArgusFleet (evaluation harness).
- A live study, not a baseline comparison.

**Worth quoting**
- 100% of depth-four provenance chains reconstructed; zero cross-fleet leakage.
- A synchronous near-duplicate gate can reject contradictory writes before the asynchronous contradiction detector evaluates them.

**Nuance / avoid**
- Their evaluation is of one production system, so cite them for failure modes and design, not for comparative numbers.
- The near-duplicate finding is independent evidence for DRIFT's P3 result.

## 1.22 Yu et al. `yu2026multiagent` (arXiv abstract)

**Must cover**
- Position paper, not experiments.
- Shared vs distributed memory; three-layer hierarchy (I/O, cache, memory).
- Protocol gaps: cache sharing and access control.
- Consistency is the most pressing open challenge.

**Nuance / avoid**
- Cite for framing, not evidence.

## 1.23 BM25 `robertson2009bm25`

**Must cover**
- What its three parts do: rarity weighting (IDF), a saturating term-frequency factor (k1), length normalisation (b).

**Nuance / avoid**
- DRIFT's overlap is BM25 without IDF, saturation or length normalisation. Say "a simplified form", not "BM25".

## 1.24 RRF `cormack2009rrf`

**Must cover**
- The formula: score = Σ 1 / (k + rank), with k = 60.
- Why it exists: different retrievers' scores are on incompatible scales.
- Result: beat Condorcet fusion and individual learning-to-rank methods.

## 1.25 Nomic Embed `nussbaum2024nomic`

**Must cover**
- Open weights, data and code.
- 8,192-token context.
- Contrastively trained.

**Nuance / avoid**
- Reported to beat OpenAI's ada-002 and text-embedding-3-small on MTEB and long-context tasks. Check the exact wording before quoting.

## 1.26 Temporal databases

- **`snodgrass1985taxonomy`:** valid time vs transaction time (plus user-defined time). Four kinds of database: snapshot, rollback, historical, temporal. Do not credit them with the word "bitemporal".
- **`jensen1998glossary`:** the agreed definitions, including "bitemporal". Cite when you define the terms.
- **`snodgrass1999developing`:** implementing these in SQL; updates close periods rather than delete rows.
- **`kulkarni2012sql2011`:** SQL:2011 application-time periods, system-versioned tables, bitemporal tables, FOR SYSTEM_TIME AS OF.
- **`xtdbdocs`:** a production bitemporal database.

## 1.27 Statistics (what each one needs in 3.7)

For each test, state what it is, why it fits, and how you applied it:

- **McNemar**
  - Paired binary outcomes; only discordant pairs matter.
  - Exact (binomial) version because counts are small.
  - Per run.
  - Dietterich: acceptable error rates for comparing methods on one fixed test set.
- **Holm:** step-down; family = the 30 comparisons per benchmark per run.
- **Bootstrap**
  - Resampling unit = question (cluster), 5,000 resamples, percentile interval.
  - Why cluster: each question appears 15 times (5 models × 3 runs).
- **Difference of gains:** small-model gain minus frontier gain, same bootstrap.
- **Kendall τ-b:** concordant minus discordant pairs; tie-corrected; with 6 items the exact p comes from all 720 orderings; one-sided.
- **Spearman and Pearson:** checks; Pearson compares values, not order.
- **Perlitz et al.**
  - Benchmark Agreement Testing, over 40 benchmarks analysed.
  - Methodological choices change agreement conclusions.
  - Best practices; the BenchBench package.
  - Precedent for ranking-transfer tests.
- **Cohen's κ:** agreement corrected for chance. Landis and Koch call 0.81 to 1.00 "almost perfect".
- **Mean ± SD and flip rate** over 3 runs: descriptive. Mem0 is the precedent for repeated runs.

## 1.28 Models

For each model state: name, version or model ID, provider, open or closed, reasoning setting, role, and the run dates. Cite the launch page, model card or technical report once.

---

# Part 2. Per-chapter, per-section checklists

Tick each item when it is in your draft.

## Chapter 1. Introduction

**Opening paragraph**
- [ ] What the thesis studies, in one sentence.
- [ ] What DRIFT is: everything fixed except the forgetting policy.
- [ ] What is measured: accuracy, stale answers, cost.

**1.1 The Problem**
- [ ] Context window and external memory defined.
- [ ] Why external memory exists (MemGPT).
- [ ] Running example (Ashley → Daniel) with dates.
- [ ] Why retrieval returns both facts.
- [ ] What goes wrong; stale answer defined.
- [ ] Why it matters (confident errors, accumulation, small models deployed at scale).
- [ ] The gap, with citations (MemGPT, Mem0, Zep, A-MEM, Du, STALE).
- [ ] Forgetting defined.
- [ ] (Optional) Fig 1.1 timeline.

**1.2 Background**
- [ ] Triples.
- [ ] Valid time and transaction time, with citations (Snodgrass and Ahn; Jensen et al.; SQL:2011).
- [ ] The three questions (now, on a date, believed on a date).
- [ ] Supersession (MQuAKE) and functional relations.
- [ ] Closing vs forgetting.
- [ ] Forgetting policy: refuse, hide, delete.
- [ ] Deployed systems (LangGraph, Letta, Mem0, Zep).
- [ ] Staleness defined (Supersede).
- [ ] Graph-aware consolidation (for RQ3).
- [ ] Multi-agent memory (for RQ4).

**1.3 Hypothesis**
- [ ] Three parts (accuracy, staleness, cost).
- [ ] How each is tested.

**1.4 Research Questions**
- [ ] RQ1 to RQ4.
- [ ] One sentence each on how it is answered.

**1.5 Contributions** (v3 numbers)
- [ ] Controlled comparison: 7 × 5 × 3 × 3 runs, 31,080 graded answers.
- [ ] Exposure × reading-error decomposition.
- [ ] P2 results:
  - MQuAKE-T 95.2% vs 91.3%; FactConsolidation 79.9% vs 67.2%;
  - fewer stale answers;
  - 9% to 29% fewer prompt tokens;
  - time, not graph (P5 is 18.1% and 15.3% worse).
- [ ] Small models: Llama 75.7% → 93.1% and 31.3% → 62.7%; difference of gains +9.4% and +24.6%.
- [ ] Soundness and completeness: P2 100% sound, 92% / 85% complete.
- [ ] Failure modes: P3 refuses corrections; P4 unstable and unsound; ConvoMem extraction-bound.
- [ ] Multi-agent: rankings transfer (τ 0.73 to 0.87); P2's completeness falls with mixed writers; LLM matching helps.
- [ ] Benchmark audit.
- [ ] What DRIFT does *not* claim (Zep's mechanism).

**1.6 Organisation**
- [ ] One line per chapter.

## Chapter 2. Related Work

- [ ] Opening point: systems are evaluated as whole designs.
- [ ] **2.1 Systems:** MemGPT, Mem0 (incl. full context being more accurate), Zep (incl. invalidation), A-MEM, Generative Agents. For each: storage, change handling, what happens to old facts, evaluation, what is missing.
- [ ] **2.2 Extraction and retrieval:** Mem0 / Zep / LongMemEval extraction; dense, BM25, hybrid, RRF; nomic.
- [ ] **2.3 Consolidation and gating:** error types; Zhang et al.; Xie et al.; SAGE (3.4×, small judge drop); why corrections look redundant.
- [ ] **2.4 Temporal data:** Snodgrass and Ahn; Jensen; Snodgrass; SQL:2011; XTDB; close vs delete.
- [ ] **2.5 Staleness and benchmarks**
  - Du, STALE, Supersede.
  - Requirements for a revision benchmark.
  - LoCoMo and LongMemEval (why excluded).
  - MQuAKE-T, FactConsolidation, ConvoMem.
  - Grading practice (F1, SubEM, judges validated against humans).
  - Table 2.1.
- [ ] **2.6 Multi-agent:** G-Memory, Collaborative Memory, GateMem, Governed Shared Memory (incl. near-duplicate finding), Yu et al.; the gap (no ranking-transfer study).
- [ ] **2.7 Positioning:** Table 2.2 and a one-paragraph gap statement.
- [ ] No DRIFT results anywhere in the chapter.

## Chapter 3. Method

- [ ] Opening: what is fixed, what varies.
- [ ] **3.1 Substrate**
  - Fact structure; fields (Table 3.1).
  - Two timelines.
  - Contradiction rule (functional relations); normalised matching.
  - Exclusions (speech acts, multi-valued); soft delete.
- [ ] **3.2 Pipeline** (Fig 3.1)
  - Extraction: DeepSeek, 4-line context, rule pass, retry.
  - Closing.
  - Retrieval: three signals defined with ranges; weights; k = 25; the ratio point.
  - Listing 3.1 (hooks).
  - Answer prompt: dates shown, no "prefer newest", and why.
  - Grading: two rules, judge, F1; why a judge; why a different family.
  - Table 3.2 (constants and sources).
- [ ] **3.3 Policies**
  - Definition; NOMEM to P5.
  - Expected behaviour of each.
  - Sound and complete defined (DRIFT's definitions; relation to GateMem and MemoryAgentBench).
  - Table 3.3.
- [ ] **3.4 Benchmarks**
  - Source, kind of change, conversion, size, time span of each (MQuAKE-T 96 Q, 37 days; FactConsolidation 100 Q / 65 changed, 38 sessions, 37 days; ConvoMem 100 Q, 10 × 20 sessions, 19 days).
  - Why these three; why not LoCoMo or LongMemEval.
  - Scope.
- [ ] **3.5 Setup**
  - Main matrix and the 3 runs (why).
  - Models (Table 3.4, with provider, ID, settings, dates).
  - RQ4 topologies (Fig 3.2, Table 3.5), stating the orchestrator / shared-extraction and ConvoMem single-writer points.
  - Follow-ups.
- [ ] **3.6 Metrics:** the metrics table; P(stale) decomposition; latency not measured.
- [ ] **3.7 Statistics:** Table 3.6; exact permutation; judge validation and its limit.
- [ ] **3.8 Reproducibility:** temperature 0, cache, replicate tag, pinning, run records, code release.

## Chapter 4. Results

Order the sections by RQ. Each section: the point first, then the figure or table, then the numbers, then the test.

- [ ] **4.1 RQ1: exposure and staleness under P0**
  - V03 left: exposure 90.6% (MQuAKE-T), 95.4% (FactConsolidation), 29.3% (ConvoMem).
  - P0 staleness 6.7% / 6.8% / 8.9%; Llama 20.1% / 32.3%.
  - V03 right: reading error by model (frontier ≤ 3.6% on MQuAKE-T and 0% on FactConsolidation; Llama 22.3% / 52.2%).
  - Decomposition check: 90.6 × 7.6 ≈ 6.9 vs 6.7 observed.
  - Caveat: FactConsolidation exposure is overstated by string match.
- [ ] **4.2 RQ2: the policy comparison**
  - V01 and `policy_average.csv`: accuracy and staleness ± SD.
  - Paired table (`paired_p2.csv`): P2 vs each, with CI and runs significant.
  - V02 per model.
  - Difference of gains (+9.4%, +24.6%; ConvoMem +1.1% n.s.).
  - Cost: V04, tokens and facts as % of P0; USD per 1,000 correct.
  - Hypothesis parts 1 to 3 against the data.
- [ ] **4.3 Forgetting correctness**
  - V05 and `forgetting_correctness.csv`.
  - P2 100% sound, 91.9% / 84.6% complete.
  - P1 unsound; P3, P4, P5 incomplete; P4 52.6% sound on FactConsolidation.
- [ ] **4.4 RQ3: time vs graph**
  - P2 vs P5: +18.1% [+12.4, +24.4] and +15.3% [+11.1, +20.1], 3/3 runs; ConvoMem +0.1% n.s.
  - P5 completeness 4% to 7%.
- [ ] **4.5 ConvoMem**
  - Every policy < 13%; P2 −4.0% [−7.3, −1.3].
  - Current value stored for about 30 of 100 questions; 79% to 86% of wrong answers had no gold in context.
  - Over-closing: 241 of 495 facts closed (run 1).
  - P1 = P0 (19-day span < 20-day TTL).
  - V08: extractor effect (GPT 85%, Claude 82%, Gemini 60%, Qwen 17%, Llama 4%, DeepSeek 12.4%).
- [ ] **4.6 Stability across runs**
  - V06 flip rates.
  - Extraction differs per run (MQuAKE-T: 382 / 325 / 352 facts).
  - Rankings identical across runs on MQuAKE-T (top 4) and FactConsolidation (all 6).
- [ ] **4.7 RQ4**
  - V07; `rq4_cells.csv`.
  - Shared:
    - P0 staleness roughly doubles (12.3% vs 6.7%; 11.2% vs 6.8%);
    - cross-writer closures 26 of 38 and 38 of 54;
    - P2 completeness falls (45.1%, 59.5%) and its gain shrinks (+0.6%, +6.8%);
    - relation naming evidence;
    - matching modes (exact / normalised / LLM closures 37 / 38 / 63; P2 87.1 / 87.1 / 88.5).
  - Independent: P2 vs P0 (70.8 vs 68.0; 61.7 vs 52.3); SD across agents.
  - Orchestrator = single-agent run 1 (consistency check).
  - Ranking agreement table with exact p; per-model τ ranges; ConvoMem uninformative.
- [ ] **4.8 Follow-ups**
  - Matching (single agent): LLM helps (Llama 94% → 99%, 61% → 70%; ConvoMem closes fewer, 153 vs 241).
  - Weights: all within about 1.5% under P2; BM25 pilot.
  - Grace (V10): current flat, history rises (MQuAKE-T 16.9% → 99.0%).
- [ ] **4.9 Judge check:** 96.0%, κ = 0.919; rules overrode the judge on 0% of answers.

## Chapter 5. Discussion

- [ ] **Why P2 works:** exposure removal × reading error; the theory and decomposition confirmed.
- [ ] **The story:** forgetting moves the work of tracking change from model to memory; who benefits (small models); cost implication (Llama + P2 at $0.011 vs GPT + P0 at $1.38 per 1,000 correct).
- [ ] **Why the alternatives fail:**
  - P1: time alone is not change;
  - P3: corrections look redundant (SAGE; Governed Shared Memory's near-duplicate finding);
  - P4: LLM consolidation (Zhang et al.);
  - P5: support without time.
- [ ] **Detection is the bottleneck:** ConvoMem over-closing; shared-memory vocabulary mismatch; LLM matching as remedy; relation-specific functional predicates.
- [ ] **What forgetting cannot fix:** facts never extracted (ConvoMem); sessions never seen (independent agents).
- [ ] **Relation to prior work:** Zep (same mechanism, now tested); Mem0 (LLM deletion); STALE (model-side vs memory-side); Supersede (training vs memory); GateMem and Governed Shared Memory (RQ4).
- [ ] **Generality:** what the three benchmarks cover and what they do not.
- [ ] **Threats to validity**
  - Judge vs humans.
  - One extractor.
  - RQ4 and follow-ups ran once.
  - Orchestrator not independent.
  - ConvoMem single-writer.
  - FactConsolidation exposure overcount.
  - Latency not measured.

## Chapter 6. Conclusion

- [ ] **Problem and approach** in brief.
- [ ] **Answer to each RQ**, one or two sentences each, with the key number.
- [ ] **Hypothesis verdict:** supported on MQuAKE-T and FactConsolidation for all three parts; part 1 not supported on ConvoMem; parts 2 and 3 supported on all three.
- [ ] **Contributions** restated briefly.
- [ ] **Limitations** (short).
- [ ] **Future work**
  - LLM or embedding-based contradiction matching, and relation-specific functional predicates.
  - Stronger or ensemble extraction.
  - Implicit and cascading changes (STALE).
  - A shared relation vocabulary for multi-writer memory.
  - Human-validated judge.
  - Latency.
  - Long horizons and real logs.
  - Learned forgetting (Du).
  - Consistency across agents (Yu et al.).
- [ ] **Closing sentence:** what a practitioner should do (close on contradiction, hide closed facts, choose grace by how much history is needed, invest in detection).
