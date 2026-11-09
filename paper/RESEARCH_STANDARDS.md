# DRIFT and the research standards of its reference papers

A study guide prepared for the committee's questions. It summarises what each reference paper did, how it did it, and how DRIFT's procedures compare with that practice. It is for understanding, not for pasting into the thesis: read the sections of each paper cited here yourself before writing about them.

Sources: the PDFs in `paper/references/` (14 papers, read for this guide) and the ConvoMem abstract (arXiv:2511.10523; the PDF is not in the folder). DRIFT facts come from the code (`src/drift/`) and the final-run outputs.

---

## 1. The reference papers, one by one

### 1.1 Memory systems

**MemGPT (Packer et al., 2023, arXiv:2310.08560)**
- Problem: LLMs have a fixed context window, so long conversations and long documents do not fit.
- What they built: an operating-system-style memory hierarchy. "Main context" (the prompt: system instructions, an editable working context, a FIFO message queue) and "external context" (recall storage of all messages, archival storage searched by similarity). The LLM moves data between them with function calls; a "memory pressure" warning tells it to save information before old messages are evicted.
- Evaluation: Multi-Session Chat (MSC) dataset. New task "Deep Memory Retrieval" (DMR): a question about an earlier session, answer scored by an LLM judge (accuracy) and ROUGE-L recall. Also document QA and a nested key-value retrieval task.
- Results: GPT-4 Turbo with MemGPT 93.4% DMR accuracy vs 35.3% for the recursive-summary baseline.
- Procedure notes: single run, no variance or significance reported. Zep later reported it could not reproduce MemGPT's DMR result with gpt-4o-mini "due to insufficient methodological details".

**Zep (Rasmussen et al., 2025, arXiv:2501.13956)**
- Problem: agent memory must handle data that changes over time, not static documents.
- What they built: Graphiti, a temporal knowledge graph with three layers (episodes = raw messages, semantic entities and facts, communities). It is explicitly **bi-temporal**: timeline T (when facts held true: t_valid, t_invalid) and timeline T′ (when the system created or expired them). This is the same idea as DRIFT's substrate.
- Extraction: an LLM extracts entities from the current message plus the **previous 4 messages** for context, uses a reflection step to reduce hallucination, and resolves duplicates by embedding + full-text search + an LLM.
- Contradictions: "an LLM compares new edges against semantically related existing edges"; contradicted edges are invalidated by setting t_invalid, never deleted.
- Retrieval: three searches (cosine similarity, Okapi BM25 full-text, breadth-first graph search), then a **reranker**: Reciprocal Rank Fusion (RRF), Maximal Marginal Relevance (MMR), graph-distance rerankers or a cross-encoder. Top 10 results go into the prompt with their date ranges.
- Evaluation: DMR (94.8% vs MemGPT 93.4%) and LongMemEval (up to +18.5% accuracy, about 90% lower latency than full context). Answers graded by a GPT-4o judge using LongMemEval's prompts. Reports latency and context tokens.
- Procedure notes: single run, no variance or significance tests. Knowledge-update accuracy was slightly *worse* than full context for gpt-4o-mini (76.9% vs 74.4%).

**Mem0 (Chhikara et al., 2025, arXiv:2504.19413)**
- Problem: production agents need memory that is accurate, fast and cheap.
- What they built: an extraction phase (an LLM extracts facts from the newest message pair, using a conversation summary and the last m = 10 messages) and an update phase (for each fact, retrieve the s = 10 most similar memories; an LLM chooses ADD, UPDATE, DELETE or NOOP). A graph variant (Mem0g) marks contradicted relations invalid instead of deleting them.
- Evaluation: LoCoMo, four question categories. Metrics: F1, BLEU-1 and an LLM-as-a-Judge score (J). They argue F1 and BLEU are misleading for facts ("Alice was born in July" vs "March" still overlaps heavily), which is why the judge is the main metric. Also token consumption (tiktoken) and latency (p50, p95).
- **Runs:** "Due to the stochastic nature of J evaluations, we conducted 10 independent runs for each method on the entire dataset and report the mean scores along with ±1 standard deviation." Temperature set to 0 "to ensure the runs are as reproducible as possible". The reported SDs are tiny (about 0.1 to 0.4 points).
- Results: 26% relative improvement in J over OpenAI's memory, 91% lower p95 latency and over 90% fewer tokens than full context.

**A-MEM (Xu et al., 2025, arXiv:2502.12110)**
- Problem: memory systems have fixed structures and cannot reorganise themselves.
- What they built: Zettelkasten-style notes (content, timestamp, LLM-generated keywords, tags, context description, embedding, links). A new note is linked to its top-k most similar notes (cosine), and "memory evolution" lets an LLM rewrite the descriptions and tags of neighbouring notes.
- Evaluation: LoCoMo and DialSim, six foundation models, metrics F1 and BLEU-1 (plus ROUGE-L, ROUGE-2, METEOR and SBERT similarity in the appendix).
- Procedure notes: lexical metrics only (no LLM judge in the original paper; Mem0 later re-ran it with a judge). No variance reported.

### 1.2 Consolidation, write control, staleness

**Zhang et al. (2026), Useful Memories Become Faulty When Continuously Updated by LLMs (arXiv:2605.12978)**
- Finding: when an LLM keeps rewriting experience into a memory bank, memory utility first rises, then falls, and can drop below the no-memory baseline. GPT-5.4 solves a set of ARC-AGI problems at 100% without memory, then fails on many of them after consolidating from the ground-truth solutions (the paper reports 46% in the main text and 54% in the abstract; check which figure to cite).
- Mechanisms they identify: (1) misgrouping unrelated experiences before abstracting, (2) abstraction strips the conditions under which a lesson applies, (3) abstraction overfits when the input stream is narrow. Results also depend on update order (all-at-once vs streaming).
- Takeaway they draw: keep raw episodes as first-class evidence and gate consolidation explicitly. This supports DRIFT's non-destructive closing and its finding that P4 (LLM consolidation) is risky.

**SAGE (Wang, Brahma and Henao, 2026, arXiv:2605.30711)**
- Problem: deciding on every write with an LLM (as Mem0 and A-MEM do) makes writing the most expensive step.
- What they built: a novelty gate. Fact embeddings are normalised onto the unit sphere; a von Mises-Fisher kernel density estimate scores how well the existing memory already covers a new fact; an adaptive threshold routes it to NOOP (redundant), ADD (novel) or, in an uncertainty band, an LLM merge.
- Evaluation: LoCoMo with token-F1, BLEU-1 and an LLM judge; seven open-weight backbones; cost and latency of the add phase.
- Results: best token-F1 against Mem0 on all seven open backbones; on GPT-4o-mini, **3.4×** lower add-phase API cost and 2.5× lower latency. **Correction for Chapter 2:** the thesis text says "roughly 3.5-fold"; the paper (v2) says 3.4×.
- Relevance: DRIFT's P3 is a simplified version (a fixed cosine threshold of 0.9 instead of an adaptive density).

**STALE (Chao et al., 2026, arXiv:2605.06527)**
- Problem: "implicit conflict", where a new observation invalidates an old memory without saying so (Type I: same attribute, e.g. a new lease in Portland implies the user no longer lives in Seattle; Type II: a change to one attribute cascades to another, e.g. a broken leg invalidates a cycling commute).
- Benchmark: 400 expert-validated scenarios, 1,200 queries, contexts up to 150K tokens, three probes: State Resolution, Premise Resistance (reject a question that assumes the old state), Implicit Policy Adaptation.
- Evaluation: LLM judge (Gemini-3.1-flash-lite), validated against humans at 95.8% agreement. Best model 55.2% overall.
- Relevance: tests whether the *model* notices staleness; DRIFT tests whether *memory* keeps stale facts away. Its comparison table lists FactConsolidation and LongMemEval as covering only *explicit* conflicts.

**Supersede (Patel, 2026, arXiv:2606.27472)**
- Problem: the "supersession gap", accuracy lost when an agent must answer from a bounded, self-maintained memory rather than the full history.
- Findings: on LongMemEval knowledge-update questions, gpt-5.4 drops from 92% (full context) to 77% (bounded memory), paired McNemar p = 0.0033. More memory does not help; GRPO fine-tuning of Qwen2.5-3B raises held-out accuracy from 9.0% to 16.7%.
- **Metric:** r_cur = 1 if the answer conveys the current value (programmatic matcher, normalised variant match with a token-overlap fallback, no judge); r_stale = −1 if the answer *asserts a superseded value*. This is essentially DRIFT's staleness definition.
- **Runs:** temperature 0 and greedy decoding, so "re-running the eval reproduces the same count"; the paper flags its single training seed as a limitation.
- **Statistics:** paired McNemar test (continuity-corrected χ²), the same family of test DRIFT uses.

**Du (2026), Memory for Autonomous LLM Agents (survey, arXiv:2603.07670)**
- Frames memory as a write, manage, read loop; taxonomy by temporal scope, representational substrate and control policy.
- Proposes an evaluation "metric stack": utility, efficiency (token, latency and storage cost per unit of utility), adaptivity, faithfulness. Discusses write-path filtering, contradiction handling and latency budgets.
- Open challenges listed: continual consolidation, causally grounded retrieval, trustworthy reflection, **learned forgetting**, multimodal memory. DRIFT addresses the forgetting part with a controlled comparison.

### 1.3 Benchmarks

**LoCoMo (Maharana et al., 2024, arXiv:2402.17753)**
- Built by LLM agents with personas and temporal event graphs, then edited by human annotators. 50 conversations, about 300 turns and 9K tokens each, up to 35 sessions.
- Tasks: QA in five categories (single-hop, multi-hop, temporal, open-domain/commonsense, adversarial), event-graph summarisation, multimodal dialogue generation.
- Metric: **F1 partial match** after answer normalisation; retrieval measured with recall@k. Temperature 0, top-p 1.
- No question records a superseded answer.

**LongMemEval (Wu et al., 2025, ICLR, arXiv:2410.10813)**
- 500 human-curated questions over five abilities: information extraction, multi-session reasoning, temporal reasoning, **knowledge updates**, abstention. Two sizes: S (about 115K tokens) and M (500 sessions, about 1.5M tokens).
- Framework: memory = key-value store with three stages (indexing, retrieval, reading). Findings: store per round rather than per session; expanding keys with extracted user facts raises recall@k by 9.4% and accuracy by 5.4%; time-aware query expansion helps temporal questions.
- Retriever: dense Stella V5 (1.5B), compared with BM25 and Contriever (dense beats BM25). Extraction for indexing with Llama 3.1 8B.
- Metric: **GPT-4o judge with question-type-specific prompts, more than 97% agreement with human experts** (meta-evaluation table: 0.98 for GPT-4o answers, 0.97 for Llama answers). Retrieval: Recall@k, NDCG@k. Greedy decoding.
- Knowledge-update questions record only the new answer.

**MemoryAgentBench (Hu, Wang and McAuley, 2026, ICLR, arXiv:2507.05257)**
- Four competencies: accurate retrieval, test-time learning, long-range understanding, **selective forgetting**. Data are fed incrementally as chunks with a "please memorise" instruction.
- **FactConsolidation** (source of DRIFT's second benchmark): built from MQuAKE counterfactual edit pairs (a true fact and a rewritten contradictory version), concatenated into 6K, 32K, 64K and 262K-token contexts; single-hop (SH) and multi-hop (MH) versions. Agents "are prompted to prioritize later information in case of conflict".
- Agents compared: long-context, simple RAG (BM25), embedding RAG, structure-augmented RAG, commercial memory agents. Top-k ablated at 2, 5, 10; chunk size ablated.
- Metric: **substring exact match (SubEM)** for short answers; LLM judge only for LongMemEval and summarisation (citing LongMemEval's 98% human agreement).
- Finding: all methods fail multi-hop FactConsolidation (at most 28%).

**MQuAKE (Zhong et al., 2023, EMNLP, arXiv:2305.14795)**
- Knowledge-editing benchmark. An edit is defined as e = (s, r, o → o*): **same subject and relation, new object**. This is exactly DRIFT's definition of a superseded fact.
- MQuAKE-CF (counterfactual edits, 9,218 instances) and **MQuAKE-T** (real temporal updates from Wikidata, 1,868 instances: 1,421 two-hop, 445 three-hop, 2 four-hop).
- Metrics: edit-wise success rate, instance-wise accuracy, multi-hop accuracy (matching the output against the answer and its aliases).
- MeLLo, their method, stores edits in an external memory, retrieves them with Contriever and lets the model self-check whether a retrieved edit contradicts its tentative answer: an early memory-based approach to updating.
- DRIFT used a 96-question single-hop derivation of MQuAKE-T, all about changed facts.

**ConvoMem (Pakhomov, Nijkamp and Xiong, 2025, arXiv:2511.10523)** (abstract only)
- 75,336 QA pairs across user facts, assistant recall, abstention, preferences, temporal changes and implicit connections; designed for statistical power.
- Finding: full context reaches 70 to 82% accuracy, while RAG-style memory such as Mem0 reaches 30 to 45% on histories under 150 conversations. Long context is best for the first 30 conversations.
- DRIFT used 100 changing-fact questions over 10 conversations.

**GateMem (Ren et al., 2026, arXiv:2606.18829)**
- Multi-principal **shared memory**: several people with different roles write to and query one memory (medical, office, education, household). 91 episodes, 2,218 hidden checkpoints.
- Three dimensions: Utility (authorised requests answered), Access Control (no leaks across roles), Active Forgetting (no recovery after a deletion request).
- Metric: GPT-4o judge with structured judge specifications and leak targets, checked against a stratified human annotation sample.
- Finding: no method is strong on all three; long context governs best but costs the most tokens.
- Relevance: the closest reference to RQ4 (several writers, one memory). It measures governance, not whether policy rankings transfer.

---

## 2. What is standard practice, and where DRIFT sits

| Component | What the references do | What DRIFT does | Assessment |
|---|---|---|---|
| **Fact extraction** | An LLM extracts facts or triples: Mem0 (GPT-4o-mini, summary + last 10 messages), Zep (entities and facts with the previous 4 messages for context, reflection, LLM entity resolution), LongMemEval (Llama 3.1 8B for user facts and keyphrases), A-MEM (LLM note attributes) | One fixed LLM (DeepSeek V4.1 Flash) extracts triples per session, plus a rule pass for single-valued relations and a retry on unreadable output | Standard. One difference: DRIFT gives the extractor no earlier-message context. Zep's 4-message window is a concrete future-work fix for ConvoMem, where facts are revised in passing |
| **Detecting that a fact changed** | MQuAKE defines an edit as same subject and relation, new object. Mem0 and Zep ask an LLM whether a new fact contradicts similar stored ones | Main run: rule (same normalised subject and relation, new object; either direction). Ablation: LLM check, Zep-style | Both standard approaches are covered, and DRIFT compares them (Section 5.4) |
| **Handling a contradiction** | Mem0: DELETE (base) or mark invalid (graph). Zep: set t_invalid, keep the fact. Zhang et al.: keep raw evidence | Close the validity window (non-destructive); only the policy hides or deletes | Matches Zep and Zhang's recommendation |
| **Retrieval** | Dense cosine similarity (all), BM25 lexical (Zep, MemoryAgentBench), graph search (Zep); combined by a reranker such as RRF or MMR (Zep). Top-k typically 5 to 10, ablated at 2, 5, 10 (MemoryAgentBench) | Weighted combination of three normalised signals (cosine, word overlap, recency), top 25; RRF implemented as a weight-free alternative | Hybrid dense + lexical retrieval is standard; RRF is the more common way to combine. See Section 5 for units and normalisation |
| **Retrieval quality** | LongMemEval: Recall@k, NDCG@k; LoCoMo: recall@k | Gold support (does the current value reach the prompt) and stale exposure | Same idea as Recall@k; DRIFT adds exposure of the *old* value, which the references do not measure |
| **Answer accuracy** | Lexical: F1 partial match (LoCoMo), F1 and BLEU-1 (A-MEM, Mem0), ROUGE-L (MemGPT), SubEM (MemoryAgentBench). LLM judge: GPT-4o (LongMemEval, Zep, GateMem), Gemini (STALE). Programmatic matcher (Supersede) | Two fixed rules, then an LLM judge (DeepSeek V4.1 Flash); token F1 also recorded | Standard |
| **Judge validation** | Against **human** annotators: LongMemEval >97%, STALE 95.8%, GateMem stratified human sample | Against a stronger LLM (Claude Sonnet 5.5): 96.0% agreement, kappa 0.919 | **Gap.** The field validates judges against humans. Grade a sample yourself (for example 150 to 200 answers) and report agreement with the judge |
| **Staleness** | Supersede: r_stale = answer asserts a superseded value. Memora's FAMA metric (cited by Supersede) penalises reliance on obsolete memory. STALE: judge-scored probes. Most benchmarks record no old value | Asserts the old value and not the current one; mentions-old reported separately | Matches Supersede's definition; DRIFT's mentions vs asserts split is an addition |
| **Sound / complete** | Not used as terms in the references. Closest: GateMem's Active Forgetting (deleted information must not be recovered) and MemoryAgentBench's "selective forgetting" competency (measured only through accuracy) | DRIFT's own formalisation: sound = never hides a still-true fact, complete = hides every replaced fact | Present it as DRIFT's definition, analogous to precision and recall of forgetting decisions, not as an established standard |
| **Cost** | Tokens (Mem0 with tiktoken, Zep context tokens, GateMem token cost) and latency p50/p95 (Mem0, Zep) | Prompt and completion tokens, USD per 1,000 correct answers, facts stored | Standard; latency is not measured (state as a limitation) |
| **Statistics** | Most report point estimates only (MemGPT, Zep, A-MEM, LoCoMo, MemoryAgentBench). Mem0: mean ± 1 SD over 10 runs. Supersede: paired McNemar | Paired bootstrap 95% CIs, exact McNemar, Holm correction, Spearman, Kendall's W, Cohen's kappa | More rigorous than most references |
| **Runs and randomness** | Temperature 0 or greedy decoding (Mem0, LoCoMo, LongMemEval, Supersede). Mem0 repeats the judge 10 times; Supersede argues greedy re-evaluation is deterministic; most others run once | One run, temperature 0, every call cached | Common practice, but see Section 3 |
| **Benchmarks for updates** | LongMemEval KU (new answer only), FactConsolidation (explicit conflicts), MQuAKE (edits), STALE (implicit conflicts), ConvoMem (temporal changes) | MQuAKE-T, FactConsolidation, ConvoMem, all recording the old value | Well chosen; STALE confirms FactConsolidation tests explicit conflicts only |
| **Prompting about conflicts** | MemoryAgentBench tells agents to "prioritize later information in case of conflict" | The prompt states what the date means and deliberately does not say how to resolve conflicts | A deliberate departure; explain it (otherwise every policy gets P2's behaviour for free) |

---

## 3. Is one run enough? Deterministic or random?

**Where randomness can enter DRIFT:**

| Stage | Random? | Why |
|---|---|---|
| Benchmark data, policies, retrieval, staleness scoring, grading rules, statistics | No | Deterministic code. The same graph gives the same retrieved facts every time |
| Extraction (DeepSeek) | Slightly | Temperature 0, but hosted models are not guaranteed bit-identical across calls (batching and hardware effects). A different extraction would change the graph for *every* policy equally |
| Answer generation | Slightly | Temperature 0 is requested; reasoning models (Qwen3 14B with thinking, GPT-6.1 Sol and Gemini at low effort) may sample their reasoning regardless |
| LLM judge | Slightly | Temperature 0; only answers the two rules do not settle reach the judge |

**What "one run" means in DRIFT:** every call is cached by a hash of (provider, model, prompt, temperature, max tokens). Re-running DRIFT therefore reproduces every number exactly. That is *reproducibility* (anyone can regenerate the same results), not proof that a fresh run would give the same answers.

**What the references do:** most run once at temperature 0 (MemGPT, Zep, A-MEM, LoCoMo, LongMemEval, MemoryAgentBench). Supersede argues that greedy evaluation is deterministic. Mem0 is the one that measured it: 10 repeated judge runs gave standard deviations of about 0.1 to 0.4 points.

**What DRIFT's results already account for:** the bootstrap intervals cover variation from *which questions* were asked. They do not cover variation from *re-sampling the models*.

**Why the conclusions are unlikely to change:** the main effects are large compared with the run-to-run noise seen in Mem0.
- P2 vs P0 on MQuAKE-T: 26 questions won, 2 lost.
- P2 vs P5 on MQuAKE-T: 113 won, 0 lost.
- Run-to-run noise would have to flip dozens of questions in one direction to change these.

The small effects (frontier-model gains of +0.5 to +3 points, the ConvoMem −3.8) are the ones a second run could move.

**Recommended check:** a replicate run that bypasses the cache and repeats only the answer and judge steps on the cached graphs.
- Scope: P0 and P2, MQuAKE-T and FactConsolidation, all five models, two extra repeats.
- Report: accuracy and staleness as mean ± SD over three runs, and the per-question flip rate (share of questions whose verdict changes between runs).
- Estimated cost: about $1.3 per repeat (20 of the 105 cells; the main matrix cost $6.78), so about $3 for two.
- Optionally, one extraction replicate (DeepSeek only, cheap) to show how much the graph itself varies.
- This needs a small code change (a replicate tag in the cache key). It is not implemented; decide first, then I will prepare it and you run it.

If the flip rate is small (Mem0's figures suggest it will be), the thesis can state: "a single run at temperature 0 is reported; three replicates of the key comparisons changed accuracy by at most X points (Section ...)".

---

## 4. RQ4: correlation values and the references

None of the 14 reference papers uses Spearman, Kendall or Pearson correlation to compare rankings (checked by text search). GateMem is the closest work on shared memory, and it measures governance, not ranking transfer. So the method comes from the statistics literature: Spearman (1904), Kendall (1938), Pearson (1896).

Single-agent ranking (MQuAKE-T accuracy, mean of 5 models) compared with each topology (Gemini 3.8 Flash), six policies (P0 to P5):

| Topology | Spearman ρ | Kendall τ | Pearson r |
|---|---|---|---|
| Independent | 0.943 (p = 0.005) | 0.867 (p = 0.017) | 0.938 (p = 0.006) |
| Orchestrator | 0.928 (p = 0.008) | 0.828 (p = 0.022) | 0.972 (p = 0.001) |
| Shared (normalised matching) | 0.928 (p = 0.008) | 0.828 (p = 0.022) | 0.893 (p = 0.016) |

All three agree that the ranking transfers. Spearman and Kendall compare order; Pearson compares the accuracy values themselves and is shown only for completeness.

---

## 5. The retrieval weights: units, ranges and why they need not sum to 1

**Each signal is a unitless score between 0 and 1** (from `graph.py`, `_signals`):

| Signal | Exact definition | Range | Example |
|---|---|---|---|
| Semantic | Cosine similarity between the question's embedding and the fact's embedding (nomic-embed-text): the cosine of the angle between two vectors | −1 to 1 in theory; about 0 to 1 in practice for text | Higher when the fact means something close to the question, even with different words |
| Lexical | Share of the question's words (lower-cased, longer than 2 letters) that also appear in the fact | 0 to 1 | "What is the name of the current head of the New Zealand government?" has 8 such words; "The head of government of New Zealand is Chris Hipkins." shares 5 (the, head, government, new, zealand), so 5/8 = 0.63 |
| Recency | The fact's "became true" date rescaled so the oldest fact is 0 and the newest is 1: (date − earliest) / (latest − earliest) | 0 to 1 | A fact halfway through the timeline scores 0.5 |

**Score = w_sem × semantic + w_lex × lexical + w_rec × recency.** The 25 highest scores go into the prompt.

**Why the weights do not have to sum to 1:** only the *ranking* of facts matters, and multiplying all three weights by the same number scales every score equally without changing the ranking.
- (0.6, 0.3, 0.1) and (1.2, 0.6, 0.2) produce exactly the same top 25.
- So any weighting can be rescaled to sum to 1 without changing anything.
- The sweep tried every combination of 0.1 to 1.0 for each weight (10 × 10 × 10 = 1,000) for simplicity. Many are rescaled copies of each other: (0.2, 0.2, 0.2) is the same as (0.5, 0.5, 0.5). Only **841** of the 1,000 are genuinely different; the analysis checked that all 115 groups of proportional weightings gave identical prompts.

**The weightings rescaled to sum to 1 (which is how to present them to the committee):**

| As run | Rescaled (semantic / lexical / recency) | Meaning |
|---|---|---|
| 0.6 / 0.3 / 0.1 (thesis setting) | 0.60 / 0.30 / 0.10 | Already sums to 1 |
| 0.9 / 0.1 / 0.2 (MQuAKE-T winner) | 0.75 / 0.08 / 0.17 | 75% meaning, 8% words, 17% recency |
| 0.8 / 0.1 / 0.1 (ConvoMem winner) | 0.80 / 0.10 / 0.10 | Already sums to 1 |

Any rescaled weighting is a point on a triangle (a "simplex"), and the 841 distinct weightings can be drawn as a triangle plot coloured by accuracy. That figure would answer the committee's question visually.

**How the references combine signals:** Zep and the information-retrieval literature usually avoid weights altogether with **Reciprocal Rank Fusion** (each signal contributes 1 / (60 + rank), Cormack et al., 2009), because raw scores from different signals live on different scales. DRIFT puts all three signals on 0 to 1 first, so a weighted sum is meaningful. RRF is implemented in DRIFT (`fusion="rrf"`) as the weight-free comparison point; reporting its accuracy next to 0.6 / 0.3 / 0.1 would show whether the weights matter at all compared with the standard method.

---

## 6. Actions arising from this review

1. **Judge vs humans (gap):** grade a sample of 150 to 200 answers yourself (blind to the judge's verdict) and report agreement and kappa, as LongMemEval, STALE and GateMem do.
2. **Replicates (committee question):** decide on the replicate run in Section 3 (about $3).
3. **Weights:** present weightings rescaled to sum to 1, define each signal's range as in Section 5, and consider the triangle plot and an RRF comparison (RRF needs answer calls; ask first).
4. **Chapter 2 correction:** SAGE reports 3.4×, not 3.5×.
5. **Sound and complete:** introduce them as DRIFT's definitions (analogous to precision and recall of forgetting), not as standard terms.
6. **ConvoMem future work:** extraction with earlier-message context, as Zep does (previous 4 messages).
7. **Limitations to state:** latency not measured; judge validated against an LLM rather than humans (until item 1 is done); one run per cell (until item 2 is done); the answer prompt deliberately omits "prefer the newest fact", unlike MemoryAgentBench.
