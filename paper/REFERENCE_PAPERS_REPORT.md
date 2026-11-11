# Reference papers: what each one did, and how it connects to DRIFT

A study report on every work DRIFT cites. It is for understanding and for answering committee questions, not for pasting into the thesis.

**Sources.**

- **Read in full** (the PDFs in `paper/references/`): MemGPT, Zep, Mem0, A-MEM, LoCoMo, LongMemEval, MemoryAgentBench, MQuAKE, Du, STALE, Zhang et al., SAGE, GateMem, Supersede.
- **Abstract checked on arXiv** (November 2026): ConvoMem, Governed Shared Memory, Collaborative Memory, G-Memory, Yu et al., Perlitz et al.
- **Summarised from the standard literature**: classic methods and statistics papers. Read the relevant section yourself before quoting a detail.
- Numbers marked "check" need confirming in the paper before you cite them.

**Card layout.** Each card covers:

- **Cite**: key and how to cite it.
- **In one line.**
- **Problem**: what they set out to solve.
- **What and how**: the method.
- **Procedure**: data, models, metrics.
- **Results.**
- **Limits.**
- **DRIFT link**: same, different, or used.
- **Where in the thesis.**

---

## Contents

1. Agent memory systems: MemGPT, Mem0, Zep/Graphiti, A-MEM, Generative Agents, RAG
2. Consolidation, write control and how models use evidence: Zhang et al., SAGE, Xie et al.
3. Staleness and memory revision: Du, STALE, Supersede
4. Benchmarks: LoCoMo, LongMemEval, MQuAKE, MemoryAgentBench (FactConsolidation), ConvoMem
5. Multi-agent memory: G-Memory, Collaborative Memory, GateMem, Governed Shared Memory, Yu et al.
6. Retrieval and embeddings: BM25, Reciprocal Rank Fusion, Nomic Embed
7. Temporal databases: Snodgrass and Ahn, Snodgrass, Jensen et al., SQL:2011
8. Statistics: McNemar, Dietterich, Holm, Efron and Tibshirani, Dror et al., Kendall, Spearman, Pearson, Perlitz et al., Cohen, Landis and Koch, Kendall and Babington Smith
9. Models: GPT-6.1 Sol, Claude Sonnet 5.5, Gemini 3.8 Flash, Llama 3, Qwen3, DeepSeek V4.1 Flash
10. Summary table: every work in one line

---

# 1. Agent memory systems

## MemGPT

- **Cite:** `packer2023memgpt`. Packer, Fang, Patil, Lin, Wooders, Gonzalez (2023), arXiv:2310.08560. Write `MemGPT~\citep{packer2023memgpt}`.
- **In one line:** an LLM that manages its own memory the way an operating system manages RAM and disk.
- **Problem:**
  - Context windows are fixed, so long conversations and long documents do not fit.
  - Making the window longer costs quadratically more compute, and long-context models use extra context poorly.
- **What and how:** "virtual context management".
  - *Main context* = the prompt: system instructions, a working context the model can edit, and a first-in-first-out message queue.
  - *External context* = recall storage (every past message, searchable) and archival storage (arbitrary text, searched by embedding similarity).
  - The model moves information between the two with function calls (search, insert, edit).
  - When the prompt nears its limit, a "memory pressure" warning tells the model to save what matters. Old messages are then evicted and summarised recursively.
- **Procedure:**
  - **Conversational agents:** Multi-Session Chat (MSC). They introduce Deep Memory Retrieval (DMR): a question about an earlier session, scored by an LLM judge and ROUGE-L.
  - **Document analysis:** multi-document QA and nested key-value retrieval.
  - Single run, no variance reported.
- **Results:** on DMR with GPT-4 Turbo, 93.4% accuracy against 35.3% for a recursive-summary baseline.
- **Limits:**
  - DMR asks about static facts from past sessions, not changed facts.
  - Zep later reported it could not reproduce the DMR result for lack of method detail.
- **DRIFT link:**
  - MemGPT has no notion of a fact being replaced. An outdated record stays in archival storage and stays searchable, so for changed facts it behaves like DRIFT's P0.
  - Its reproducibility problem is a good argument for DRIFT's caching, run records and fixed settings.
- **Where:** 1.1 (why external memory exists), 2.1.

## Mem0

- **Cite:** `chhikara2025mem0`. Chhikara, Khant, Aryan, Singh, Yadav (2025), arXiv:2504.19413. Write `Mem0~\citep{chhikara2025mem0}`.
- **In one line:** a production memory layer that extracts facts from conversations and lets an LLM decide how each new fact changes memory.
- **Problem:** fixed context windows break consistency over long multi-session dialogue; full context is slow and expensive.
- **What and how:**
  - **Extraction phase:** for the newest message pair, an LLM extracts salient facts, using a conversation summary and the last m = 10 messages as context.
  - **Update phase:** for each new fact, retrieve the s = 10 most similar stored memories. An LLM (through a tool call) picks one operation:
    - ADD (new information);
    - UPDATE (augment an existing memory);
    - DELETE (the new fact contradicts an old one);
    - NOOP (nothing to do).
  - **Mem0^g (graph variant):** stores entities and relations in a graph. A conflict detector marks contradicted relations *invalid* instead of deleting them.
- **Procedure:**
  - LoCoMo, four question categories (single-hop, multi-hop, temporal, open-domain).
  - Baselines: LangMem, Zep, OpenAI memory, RAG with various chunk sizes and k, full context, and A-MEM.
  - Metrics: F1, BLEU-1, and an LLM-as-a-Judge score J, which they treat as the main metric because F1 and BLEU reward surface overlap. Also token use and p50/p95 latency.
  - **10 independent runs of the judge, mean ± 1 SD**, temperature 0.
- **Results:**
  - J is 26% higher (relative) than OpenAI's memory; Mem0^g adds about 2% more.
  - p95 latency is 91% lower and token use over 90% lower than full context.
- **Limits:** no metric for stale answers; DELETE is decided by an LLM, so a wrong decision silently loses a true fact.
- **DRIFT link:**
  - DRIFT's P4 is in this spirit: an LLM decides what to drop. DRIFT measured that LLM-decided removal is unstable and can remove current values.
  - Mem0 is the precedent for using an LLM judge rather than F1, and for repeated runs with mean ± SD.
  - Mem0^g's "mark invalid" is close to DRIFT's closing.
- **Where:** 1.1, 1.2, 2.1, 2.2, 3.2.6, 3.5.

## Zep and Graphiti

- **Cite:** `rasmussen2025zep`; the open-source engine `graphiti`. Rasmussen, Paliychuk, Beauvais, Ryan, Chalef (2025), arXiv:2501.13956. Write `Zep~\citep{rasmussen2025zep}`; for a section, `\citep[Sec.~2.2.1]{rasmussen2025zep}`.
- **In one line:** a memory service built on a *temporal knowledge graph* that invalidates outdated facts instead of deleting them.
- **Problem:** enterprise agents need memory over data that changes (conversations, business records), not static document retrieval.
- **What and how:** Graphiti, a graph with three layers.
  - **Episodes:** the raw messages, never discarded.
  - **Semantic entities and facts:** extracted by an LLM from the current message **plus the previous 4 messages** for context, with a reflection step against hallucination. Duplicate entities are resolved with embeddings, full-text search and an LLM.
  - **Communities:** clusters of related entities with summaries.
  - **Bitemporal model:** timeline T records when a fact held in the world (t_valid, t_invalid); timeline T′ records when the system created or expired it.
  - **Contradictions:** an LLM compares a new edge with semantically related existing edges. A contradicted edge gets t_invalid set and stays in the graph.
  - **Retrieval:** three searches (cosine similarity, Okapi BM25, breadth-first graph search), then a reranker (Reciprocal Rank Fusion, Maximal Marginal Relevance, graph distance or a cross-encoder). The top results go into the prompt with their validity dates.
- **Procedure:** DMR (against MemGPT) and LongMemEval, with gpt-4o-mini and gpt-4o; GPT-4o judge with LongMemEval's prompts; latency and context tokens. Single run.
- **Results:**
  - DMR 94.8% against MemGPT's 93.4%.
  - On LongMemEval, accuracy up to 18.5% higher and about 90% lower latency than full context.
  - Knowledge-update accuracy for gpt-4o-mini was slightly *below* full context (check the table).
- **Limits:** compares whole systems. It never asks what *should* happen to an invalidated fact (show it, hide it, delete it), and it does not report staleness.
- **DRIFT link:**
  - DRIFT's substrate uses the same bitemporal idea, so say plainly that DRIFT does not claim the mechanism.
  - DRIFT's extraction context (4 previous lines) copies Zep's setting.
  - DRIFT's LLM-matching follow-up is Zep-style contradiction detection.
  - DRIFT's question is the one Zep leaves open: given closed facts, which forgetting policy is best?
- **Where:** 1.1, 1.2, 1.5, 2.1, 2.2, 3.1, 3.2.1.

## A-MEM

- **Cite:** `xu2025amem`. Xu, Liang, Mei, Gao, Tan, Zhang (2025), arXiv:2502.12110. Write `A-MEM~\citep{xu2025amem}`.
- **In one line:** a self-organising memory of linked notes, modelled on the Zettelkasten method.
- **Problem:** existing memories have fixed structures and operations, and cannot reorganise as they grow.
- **What and how:**
  - Each memory is a note: content, timestamp, LLM-generated keywords, tags, a context description, an embedding and links.
  - A new note is linked to its top-k most similar notes.
  - **Memory evolution:** the new note can trigger an LLM to rewrite the descriptions and tags of its neighbours.
- **Procedure:** LoCoMo and DialSim, six foundation models, metrics F1 and BLEU-1 (more lexical metrics in the appendix), no variance.
- **Results:** better than the baselines across the six models (see their tables).
- **Limits:**
  - Lexical metrics only.
  - Memory evolution rewrites old notes with an LLM, which is the kind of consolidation Zhang et al. show can corrupt memory.
  - Nothing records which version of a fact is current.
- **DRIFT link:** related to P4 (LLM rewriting). Its evaluation shows how common lexical metrics are, against which DRIFT's judge plus staleness measure is a step up.
- **Where:** 1.1, 2.1.

## Generative Agents

- **Cite:** `park2023generative`. Park, O'Brien, Cai, Morris, Liang, Bernstein (2023), UIST, arXiv:2304.03442. Write `Generative Agents~\citep{park2023generative}`.
- **In one line:** 25 simulated characters in a sandbox town who remember, reflect and plan using a memory stream.
- **Problem:** believable long-running agents need to remember experiences and use the relevant ones.
- **What and how:**
  - **Memory stream:** every observation stored with a timestamp.
  - **Retrieval score** = recency + importance + relevance, each min-max normalised to 0 to 1, with equal weights:
    - recency decays exponentially (factor 0.995 per game hour since last access);
    - importance is rated by an LLM on a 1 to 10 scale;
    - relevance is cosine similarity to the query.
  - **Reflection:** the agent periodically writes higher-level insights.
  - **Planning:** day plans, revised as events happen.
- **Procedure:** human raters judge the believability of agents' answers in interviews; ablations remove memory, reflection or planning.
- **Results:**
  - The full architecture is rated most believable; removing each component lowers ratings.
  - Information spreads between agents in emergent ways (a Valentine's Day party is organised).
- **Limits:** believability, not factual accuracy; no notion of a fact becoming false.
- **DRIFT link:**
  - The best-known precedent for DRIFT's retrieval: a weighted sum of normalised signals with a recency term.
  - Difference: their recency is time since last access; DRIFT's is the fact's valid-start date.
- **Where:** 2.1, 2.2, 3.2.3.

## Retrieval-Augmented Generation (RAG)

- **Cite:** `lewis2020rag`. Lewis et al. (2020), NeurIPS. Write `retrieval-augmented generation (RAG)~\citep{lewis2020rag}`.
- **In one line:** retrieve relevant passages from an index, then generate the answer conditioned on them.
- **Problem:** knowledge stored only in model weights is hard to update and to inspect.
- **What and how:**
  - A pretrained generator (BART) combined with a dense retriever (DPR) over a Wikipedia index.
  - Two variants: RAG-Sequence (one set of passages per answer) and RAG-Token (passages may change per token).
- **Procedure and results:**
  - State of the art at the time on open-domain QA (Natural Questions, TriviaQA, WebQuestions, CuratedTrec); more specific and factual generation.
  - Replacing the index updates the model's world knowledge without retraining.
- **DRIFT link:**
  - Vector memory for agents is RAG applied to the agent's own history.
  - RAG's "swap the index to update knowledge" assumes the index itself is current. DRIFT studies the case where old and new facts sit in the same index.
- **Where:** 1.1 or 2.1, wherever RAG is mentioned.

---

# 2. Consolidation, write control, and how models use evidence

## Zhang et al., "Useful Memories Become Faulty When Continuously Updated by LLMs"

- **Cite:** `zhang2026faulty`. Zhang, Lin, Wu, Sun, Li, Li, Peng (2026), arXiv:2605.12978. Write `\citet{zhang2026faulty}`.
- **In one line:** when an LLM keeps rewriting its experiences into abstract lessons, memory gets worse.
- **Problem:** many agent-memory systems consolidate experience into a textual memory bank after each interaction. Is that safe?
- **What and how:**
  - Agents consolidate trajectories into memory over a stream of tasks, under different update schedules (all at once vs streaming).
  - A controlled "ARC-AGI Stream" environment gives the agent Retain, Delete and Consolidate actions.
- **Procedure:** ALFWorld, ScienceWorld, WebShop, AppWorld and ARC-AGI, with GPT-5.4 and GPT-5.4-mini; memory utility measured over the course of consolidation.
- **Results:**
  - Utility first rises, then falls, and can drop below the no-memory baseline.
  - Even when consolidating from ground-truth solutions, GPT-5.4 fails on **54%** of a set of ARC-AGI problems it had solved without memory. The abstract says 54%; check the main text, which earlier notes recorded as 46%.
  - **Causes:** unrelated experiences grouped together, abstraction stripping the conditions under which a lesson applies, and overfitting to a narrow stream.
  - An episodic-only control (keep raw trajectories) stays competitive. Agents allowed to choose keep raw episodes and double the accuracy of forced consolidation.
- **Recommendation they make:** treat raw episodes as first-class evidence and gate consolidation explicitly.
- **DRIFT link:**
  - Supports DRIFT's non-destructive closing (keep the evidence, change only visibility).
  - Predicts P4's failure, which v3 measured: P4 is the least accurate memory policy on FactConsolidation (44.0%), only 52.6% sound there, and the least stable across runs.
- **Where:** 2.3, Chapter 5.

## SAGE

- **Cite:** `wang2026sage`. Wang, Brahma, Henao (2026), arXiv:2605.30711. Write `SAGE~\citep{wang2026sage}`.
- **In one line:** a novelty gate that decides, cheaply, whether a new fact should be added to memory.
- **Problem:**
  - Prior work focuses on retrieval and storage, not on the write decision.
  - Deciding every write with an LLM (as Mem0 and A-MEM do) makes writing the most expensive step.
  - A wrong write (duplicate, wrong merge, premature delete) damages later answers.
- **What and how:**
  - Embeddings are normalised onto the unit sphere.
  - A von Mises-Fisher kernel density estimate scores how well existing memory already covers a new fact.
  - An adaptive threshold, which tracks the geometry of the memory store, routes clearly novel facts to ADD and clearly redundant facts to NOOP. Only uncertain cases go to an LLM merge.
- **Procedure:** LoCoMo with token F1, BLEU-1 and an LLM judge; seven open-weight backbones plus GPT-4o-mini; cost and latency of the write phase.
- **Results:**
  - Best token F1 against Mem0 on all seven open backbones.
  - On GPT-4o-mini, **3.4×** lower write cost and 2.5× lower latency.
- **Limits:** novelty is judged by similarity. A correction ("the head of government is now Chris Hipkins") is very similar to the fact it corrects, so a similarity gate risks treating it as redundant. The paper does not evaluate changing facts.
- **DRIFT link:**
  - P3 is a simplified SAGE: a fixed cosine threshold of 0.9 instead of an adaptive density.
  - v3 shows the risk: P3 removes almost none of the old values (1% to 2% complete) and is the stalest gate (15.9% and 16.7% stale).
- **Where:** 2.3, 3.3, Chapter 5.

## Xie et al., "Adaptive Chameleon or Stubborn Sloth"

- **Cite:** `xie2024adaptive`. Xie, Zhang, Chen, Lou, Su (2024), ICLR. Write `\citet{xie2024adaptive}`.
- **In one line:** how LLMs behave when the evidence in their prompt conflicts with what they learned in training.
- **Problem:** retrieval-augmented models receive evidence that may contradict their own knowledge. Which do they follow?
- **What and how:**
  - They elicit each model's own answer (its "parametric memory").
  - They then build a coherent, convincing *counter-memory* that contradicts it, and test the model with different mixtures of supporting and conflicting evidence.
- **Results:**
  - Models are highly receptive to external evidence when it is the only evidence and is coherent, even when it conflicts with what they learned (the "adaptive chameleon").
  - When supporting and conflicting evidence are both present, they show confirmation bias toward their own knowledge (the "stubborn sloth").
  - Order and amount of evidence also influence the choice.
- **DRIFT link:**
  - Explains why exposure matters: what reaches the prompt strongly shapes the answer.
  - In DRIFT both the old and new value are in the prompt and both are "external", so the model has to adjudicate. Weaker models do this badly (Llama's reading error is 22% to 52%).
- **Where:** 2.3, Chapter 5 (mechanism).

---

# 3. Staleness and memory revision

## Du, "Memory for Autonomous LLM Agents" (survey)

- **Cite:** `du2026memory`. Du (2026), arXiv:2603.07670. Write `\citet{du2026memory}`.
- **In one line:** a survey of how agent memory is designed, implemented and evaluated, 2022 to early 2026.
- **What and how:**
  - Formalises agent memory as a **write, manage, read** loop coupled with perception and action.
  - Taxonomy along three dimensions: temporal scope, representational substrate, control policy.
  - Five mechanism families: context-resident compression, retrieval-augmented stores, reflective self-improvement, hierarchical virtual context, policy-learned management.
  - Proposes an evaluation "metric stack": utility, efficiency (token, latency and storage cost per unit of utility), adaptivity, faithfulness.
- **Open challenges named:** continual consolidation, causally grounded retrieval, trustworthy reflection, **learned forgetting**, multimodal memory.
- **DRIFT link:**
  - DRIFT addresses the "manage" step and the forgetting challenge.
  - Its cost measures (tokens and facts per correct answer) fit the survey's efficiency layer.
  - Use it to show forgetting is recognised as open, not invented by you.
- **Where:** 1.1, 2.5, Chapter 6.

## STALE

- **Cite:** `chao2026stale`. Chao, Bai, Sheng, Li, Sun (2026), arXiv:2605.06527. Write `STALE~\citep{chao2026stale}`.
- **In one line:** a benchmark for whether agents notice that a memory has become invalid when nobody says so.
- **Problem:** benchmarks measure static retrieval, not revising beliefs. They name **implicit conflict**: a later observation invalidates an earlier memory without explicit negation.
  - Type I (same attribute): a new lease in Portland implies the user no longer lives in Seattle.
  - Type II (cascading): a broken leg invalidates a cycling commute.
- **What and how:**
  - 400 expert-validated scenarios, 1,200 queries, over 100 everyday topics, contexts up to 150K tokens.
  - Three probes:
    - State Resolution: does the model detect the belief is outdated?
    - Premise Resistance: does it reject a question that assumes the old state?
    - Implicit Policy Adaptation: does it apply the new state in later behaviour?
  - Also proposes CUPMem, a prototype with write-time state consolidation and propagation-aware search.
- **Procedure:** frontier LLMs and memory frameworks; Gemini judge validated against humans at 95.8% agreement.
- **Results:**
  - Best model 55.2% overall.
  - A pervasive gap between *retrieving* the updated evidence and *acting* on it; models accept outdated premises in questions.
- **DRIFT link:**
  - STALE tests whether the **model** notices staleness; DRIFT tests whether **memory** keeps stale facts from reaching the model. The two are complementary.
  - STALE classes FactConsolidation (and LongMemEval) as explicit conflicts only, which fixes DRIFT's scope: implicit and cascading changes are outside it.
  - Its human-validated judge is the standard DRIFT should mention.
- **Where:** 1.1, 2.5, 3.4 (scope), 3.7 (judge validation), Chapter 6.

## Supersede

- **Cite:** `patel2026supersede`. Patel (2026), arXiv:2606.27472. Write `Supersede~\citep{patel2026supersede}`.
- **In one line:** isolates the "supersession gap", the accuracy lost when an agent must use the current value of a changed fact from its own bounded memory.
- **Problem:** do agents fail on changing facts because they cannot understand them, or because they cannot maintain memory?
- **What and how:**
  - On LongMemEval knowledge-update questions, compare full context with a bounded, self-maintained memory.
  - Scoring is programmatic (no judge): r_cur = 1 if the answer conveys the current value; r_stale = −1 if it **asserts a superseded value**.
  - Released as an open reinforcement-learning environment.
- **Procedure:** gpt-5.4 and other models; paired McNemar test; temperature 0 and greedy decoding, so re-evaluation reproduces the same counts.
- **Results:**
  - gpt-5.4 drops from 92% (full context) to 77% (bounded memory), p < 0.005.
  - As the conversation grows 24×, accuracy falls from 68% to 28%, and more memory does not help (28% to 28%).
  - GRPO fine-tuning of a 3B model raises held-out accuracy from 9.0% to 16.7%.
  - Conclusion: the bottleneck is memory maintenance, not comprehension.
- **DRIFT link:**
  - DRIFT's staleness definition is the same as r_stale; DRIFT adds the split between asserting and merely mentioning the old value.
  - Same statistical test (McNemar).
  - Supersede fixes the problem by training the model; DRIFT fixes it in the memory, with no training, which is why it helps small models most.
- **Where:** 1.2, 2.5, 3.6, 3.7.

---

# 4. Benchmarks

## LoCoMo

- **Cite:** `maharana2024locomo`. Maharana, Lee, Tulyakov, Bansal, Barbieri, Fang (2024), ACL. Write `LoCoMo~\citep{maharana2024locomo}`.
- **In one line:** very long conversations for testing long-term conversational memory.
- **Problem:** earlier dialogue benchmarks span at most about five sessions.
- **What and how:**
  - A machine-human pipeline. Two LLM agents with personas and *temporal event graphs* talk over many sessions (and share images); human annotators then check and edit for long-range consistency.
  - 50 conversations of about 300 turns and 9K tokens, up to 35 sessions.
  - Tasks: QA in five categories (single-hop, multi-hop, temporal, open-domain/commonsense, adversarial), event summarisation, multimodal dialogue generation.
- **Procedure:** F1 with partial match after normalisation; retrieval recall@k; temperature 0.
- **Results:** long-context models and RAG still lag well behind humans, especially on temporal and adversarial questions (see their tables).
- **DRIFT link:**
  - The most-used long-memory benchmark (Mem0, A-MEM, SAGE all use it).
  - No question records a replaced answer, so staleness cannot be scored. That is why DRIFT excludes it (Table 2.1).
- **Where:** 1.5 (benchmark audit), 2.5, Table 2.1.

## LongMemEval

- **Cite:** `wu2025longmemeval`. Wu, Wang, Yu, Zhang, Chang, Yu (2025), ICLR. Write `LongMemEval~\citep{wu2025longmemeval}`.
- **In one line:** 500 curated questions testing five long-term memory abilities of chat assistants.
- **Problem:** long-term memory in sustained interactions was underexplored.
- **What and how:**
  - Five abilities: information extraction, multi-session reasoning, temporal reasoning, **knowledge updates**, abstention.
  - Questions are embedded in scalable chat histories: S (about 115K tokens) and M (about 500 sessions, 1.5M tokens).
  - A unified memory framework of indexing, retrieval and reading. Proposed optimisations:
    - session decomposition (store per round);
    - fact-augmented key expansion;
    - time-aware query expansion.
- **Procedure:** commercial assistants and long-context models; GPT-4o judge with type-specific prompts, **above 97% agreement with human experts**; Recall@k and NDCG@k; greedy decoding.
- **Results:**
  - Commercial assistants and long-context LLMs drop about 30% in accuracy over sustained interactions.
  - Key expansion with extracted facts improves recall and QA accuracy.
- **DRIFT link:**
  - Knowledge-update questions record only the *new* answer, so a stale answer cannot be identified.
  - Its human-validated judge is the field's standard, against which DRIFT's LLM-validated judge is a stated limitation.
  - Supersede and Zep both use it.
- **Where:** 1.5, 2.5, Table 2.1, 3.7.

## MQuAKE and MQuAKE-T

- **Cite:** `zhong2023mquake`. Zhong, Wu, Manning, Potts, Chen (2023), EMNLP, arXiv:2305.14795. Write `MQuAKE~\citep{zhong2023mquake}`.
- **In one line:** a benchmark for whether edited knowledge propagates to multi-hop questions.
- **Problem:**
  - Knowledge in LLMs goes out of date, and retraining is expensive.
  - Knowledge-editing methods were evaluated only on recalling the edited fact, not on its consequences.
- **What and how:**
  - An **edit** is e = (s, r, o → o*): same subject and relation, new object. For example, (United Kingdom, head of government, Boris Johnson → Rishi Sunak).
  - Multi-hop questions whose answer must change when an edit is applied.
  - **MQuAKE-CF:** counterfactual edits.
  - **MQuAKE-T:** real temporal updates from Wikidata.
  - Proposed method **MeLLo:** store edits in an external memory, retrieve them, and let the model check whether a retrieved edit contradicts its tentative answer.
- **Procedure:** edit-wise success, instance-wise accuracy and multi-hop accuracy against answers and aliases; editing methods such as ROME and MEMIT.
- **Results:**
  - Parameter-editing methods recall edited facts but fail badly on multi-hop questions.
  - MeLLo, the memory-based approach, does much better.
- **DRIFT link:**
  - Gives DRIFT its definition of supersession: same subject and relation, new object.
  - MQuAKE-T is DRIFT's cleanest benchmark: 96 single-hop questions about real changes.
  - MeLLo is an early example of fixing outdated knowledge in memory rather than in weights, the direction DRIFT takes.
- **Where:** 1.2, 1.5, 2.5, 3.1, 3.4.

## MemoryAgentBench and FactConsolidation

- **Cite:** `hu2026memoryagentbench`. Hu, Wang, McAuley (2026), ICLR, arXiv:2507.05257. Write `MemoryAgentBench~\citep{hu2026memoryagentbench}` or `FactConsolidation~\citep{hu2026memoryagentbench}`.
- **In one line:** a benchmark of four memory competencies for agents that receive information incrementally.
- **Problem:** agent benchmarks test reasoning and planning, not memory. Existing memory benchmarks are short or static (book QA), and none covers all four competencies.
- **What and how:**
  - Four competencies drawn from cognitive science: accurate retrieval, test-time learning, long-range understanding, **selective forgetting**.
  - Data arrive as a sequence of chunks with "please memorise", simulating incremental accumulation.
  - **FactConsolidation** (new, for selective forgetting): built from MQuAKE counterfactual edit pairs, the original fact and a rewritten contradictory version, concatenated into contexts of several lengths.
    - FactConsolidation-SH (single-hop) and -MH (multi-hop).
    - Agents are told to prioritise later information when facts conflict.
- **Procedure:** long-context agents, simple RAG (BM25), embedding RAG, structure-augmented RAG and commercial memory agents; substring exact match for short answers; top-k and chunk-size ablations.
- **Results:**
  - No method masters all four competencies.
  - Multi-hop FactConsolidation is failed by all methods (at most about 28%; check the table).
- **DRIFT link:**
  - DRIFT uses the 6K single-hop version (100 questions, 65 with an old value).
  - Its counterfactual answers cannot be guessed from what the model learned in training, so it isolates memory.
  - **Key difference to explain:** MemoryAgentBench tells agents to prefer later information; DRIFT deliberately does not, because the policy, not the prompt, should resolve conflicts.
- **Where:** 1.5, 2.5, 3.2.5, 3.4.

## ConvoMem

- **Cite:** `pakhomov2025convomem`. Pakhomov, Nijkamp, Xiong (2025), arXiv:2511.10523. Write `ConvoMem~\citep{pakhomov2025convomem}`.
- **In one line:** a large conversational-memory benchmark showing that simple full context beats RAG memory on small histories.
- **Problem:** existing memory benchmarks lack statistical power, consistent data generation and flexible evaluation.
- **What and how:**
  - 75,336 QA pairs across user facts, assistant recall, abstention, preferences, **temporal changes** and implicit connections.
  - Compares full-context approaches with RAG-based memory (such as Mem0).
- **Results:**
  - Full context reaches 70% to 82% even on the hardest multi-message cases; Mem0 reaches 30% to 45% on histories under 150 conversations.
  - Long context is best for the first 30 conversations and viable up to about 150; after that, RAG or hybrids are needed.
  - Memory starts from zero and grows, which makes exhaustive search feasible early on.
- **DRIFT link:**
  - DRIFT uses 100 changing-fact questions over 10 conversations.
  - Their finding that extraction-based memory struggles matches DRIFT's: on ConvoMem, DeepSeek extraction stored the current value for only about 30 of 100 questions, and accuracy was extraction-bound (under 13% for every policy, but 85% when GPT extracted).
  - Use ConvoMem to discuss where forgetting cannot help.
- **Where:** 1.5, 2.5, 3.4, Chapter 5.

---

# 5. Multi-agent memory

## G-Memory

- **Cite:** `zhang2025gmemory`. Zhang, Fu, Wan, Yu, Wang, Yan (2025), NeurIPS (Spotlight), arXiv:2506.07398. Write `G-Memory~\citep{zhang2025gmemory}`.
- **In one line:** hierarchical memory that lets a multi-agent team learn from its past collaborations.
- **Problem:** multi-agent memory is too simple. It ignores how agents collaborated and has no cross-trial or agent-specific memory.
- **What and how:**
  - A three-tier graph inspired by organisational memory theory:
    - **insight graph:** general lessons;
    - **query graph:** past tasks;
    - **interaction graph:** condensed collaboration trajectories.
  - For a new query it traverses both ways, upward for insights and downward for relevant trajectories. After the task, the hierarchy is updated.
- **Procedure:** five benchmarks (embodied action and knowledge QA), three LLM backbones, three multi-agent frameworks.
- **Results:** up to 20.89% higher success on embodied action and 10.12% higher knowledge-QA accuracy, without changing the frameworks.
- **DRIFT link:** shows shared memory helps teams, but measures task success only. It does not ask what happens when a stored fact becomes false, or whether one agent's outdated memory misleads another. That is DRIFT's RQ4 angle.
- **Where:** 2.6.

## Collaborative Memory

- **Cite:** `rezazadeh2025collaborative`. Rezazadeh, Li, Lou, Zhao, Wei, Bao (2025), arXiv:2505.18279. Write `Collaborative Memory~\citep{rezazadeh2025collaborative}`.
- **In one line:** memory shared across users and agents under permissions that differ between users and change over time.
- **Problem:** memory work assumes a single user; sharing across users with different permissions is unaddressed.
- **What and how:**
  - Access controls as bipartite graphs linking users, agents and resources, changing over time.
  - Two memory tiers: *private* fragments (visible only to their originating user) and *shared* fragments.
  - Every fragment carries **immutable provenance**: contributing agents, accessed resources, timestamps.
  - Read policies filter what each user sees; write policies decide retention and sharing.
- **Results:** safe, auditable cross-user sharing, with provable adherence to the access policies (see the paper for its empirical results).
- **DRIFT link:**
  - DRIFT also records provenance (which agent wrote each fact), which is what makes cross-writer invalidations measurable.
  - Collaborative Memory governs *who may see* a fact; DRIFT governs *whether a fact is still true*.
- **Where:** 2.6.

## GateMem

- **Cite:** `ren2026gatemem`. Ren et al. (2026), arXiv:2606.18829. Write `GateMem~\citep{ren2026gatemem}`.
- **In one line:** a benchmark for shared memory used by several people with different roles.
- **Problem:** memory benchmarks assume one user. Real shared assistants (hospitals, offices, campuses, households) have several principals writing and querying under different roles.
- **What and how:**
  - Jointly evaluates three dimensions:
    - **utility:** answering legitimate long-horizon requests with state updates;
    - **access control:** no leaks across authorisation boundaries;
    - **active forgetting:** information deleted on request must not be recovered.
  - Medical, office, education and household domains; 91 long multi-party episodes; incremental memory injection; 2,218 hidden checkpoints; leak targets annotated.
- **Procedure:** many baselines and backbones; GPT-4o judge with structured specifications, checked against a stratified human sample.
- **Results:**
  - No method is strong on all three at once.
  - Long-context prompting governs best but costs the most tokens; retrieval and external memory are cheaper but still leak unauthorised or deleted information.
- **DRIFT link:**
  - The closest work to RQ4's setting (many writers, one memory).
  - It measures governance, not freshness or ranking transfer.
  - Its "active forgetting" is the closest existing idea to DRIFT's *completeness*.
- **Where:** 1.2, 2.6, 3.3.

## Governed Shared Memory

- **Cite:** `margalit2026governed`. Margalit, Cohen-Inger, Avram, Taig, Margalit (2026), arXiv:2606.24535. Write `Governed Shared Memory~\citep{margalit2026governed}`.
- **In one line:** systems design and live evaluation of memory shared by a fleet of agents.
- **Problem:** multi-agent environments need shared knowledge management. They formalise the *fleet-memory problem* with four failure modes:
  1. unauthorised leakage;
  2. **stale propagation**;
  3. **contradiction persistence**;
  4. provenance collapse.
- **What and how:**
  - Primitives: scoped retrieval, **temporal supersession**, provenance tracking, policy-governed propagation.
  - Implemented in MemClaw, a production multi-tenant service, and evaluated with ArgusFleet, a reproducible harness for four governance dimensions. A live-system study, not a baseline comparison.
- **Results:**
  - 100% of depth-four provenance chains reconstructed with the correct writer.
  - Zero cross-fleet leakage.
  - Two production problems found:
    - sub-tenant scope was bypassed on direct lookups (since fixed);
    - **a synchronous near-duplicate gate can reject a contradictory write before the asynchronous contradiction detector sees it.**
- **DRIFT link:**
  - DRIFT measures two of their failure modes empirically. In shared memory P0's stale answers roughly double (stale propagation), and P2's completeness falls from 92% to 45% on MQuAKE-T (contradiction persistence).
  - Their pipeline-ordering finding is the same failure as DRIFT's P3: a near-duplicate gate drops the correction, because a correction looks like a duplicate. You can cite them for this independent production evidence.
- **Where:** 1.2, 2.6, 3.6, Chapter 5.

## Yu et al., "Multi-Agent Memory from a Computer Architecture Perspective"

- **Cite:** `yu2026multiagent`. Yu, Yu, Zhang, Ni, Yin, Yang, Zhao, Zhao (2026), arXiv:2603.10062. Write `\citet{yu2026multiagent}`.
- **In one line:** a position paper treating multi-agent memory as a computer-architecture problem.
- **What and how:**
  - Distinguishes shared and distributed memory paradigms.
  - Proposes a three-layer hierarchy (I/O, cache, memory).
  - Identifies two protocol gaps: cache sharing across agents, and structured access control.
- **Main claim:** the most pressing open challenge is **multi-agent memory consistency**: when one agent's write becomes visible, and correct, for the others.
- **DRIFT link:** RQ4 is an empirical look at one piece of that consistency problem: whether a forgetting rule keeps shared memory fresh when different agents write the old and new versions of a fact.
- **Where:** 2.6, Chapter 6.

---

# 6. Retrieval and embeddings

## BM25 (the Probabilistic Relevance Framework)

- **Cite:** `robertson2009bm25`. Robertson and Zaragoza (2009), Foundations and Trends in Information Retrieval 3(4). Write `BM25~\citep{robertson2009bm25}`.
- **In one line:** the standard lexical ranking function in information retrieval.
- **How:**
  - Scores a document by summing, over query words:
    - an **inverse document frequency** weight (rare words count more);
    - a **term-frequency** factor that saturates (controlled by k1, typically about 1.2);
    - a document-length normalisation (b, typically 0.75).
  - The monograph derives it from the probabilistic relevance framework and extends it to fields (BM25F).
- **DRIFT link:**
  - Zep uses BM25 as one of its three searches.
  - DRIFT's lexical signal (share of question words found in the fact) is BM25 without rarity weighting or saturation.
  - A pilot run with BM25 instead of overlap showed no difference under P2 and about 10% difference for Llama under P0, so the choice matters only when stale facts are visible.
- **Where:** 2.2, 3.2.3, Chapter 4.

## Reciprocal Rank Fusion (RRF)

- **Cite:** `cormack2009rrf`. Cormack, Clarke, Buettcher (2009), SIGIR, pp. 758 to 759. Write `reciprocal rank fusion~\citep{cormack2009rrf}`.
- **In one line:** combine several rankings by summing 1 / (k + rank) over them, with k = 60.
- **Why it exists:** scores from different retrievers are on different scales, so adding them is unreliable. Ranks are comparable.
- **Results:** this simple rule beat Condorcet fusion and individual learning-to-rank methods on TREC and LETOR data.
- **DRIFT link:**
  - Zep reranks with RRF.
  - DRIFT puts all signals on 0 to 1 first, so a weighted sum is meaningful, and tests RRF as the weight-free alternative. Under P2 they are within about 1.5%.
- **Where:** 2.2, 3.2.3, 3.5.

## Nomic Embed

- **Cite:** `nussbaum2024nomic`. Nussbaum, Morris, Duderstadt, Mulyar (2024), arXiv:2402.01613. Write `nomic-embed-text~\citep{nussbaum2024nomic}`.
- **In one line:** an open, fully reproducible text embedding model with long context (8,192 tokens).
- **How:** contrastive training of a long-context BERT-style encoder on large collections of text pairs; weights, training data and code released.
- **Results:** reported to outperform OpenAI's text-embedding-ada-002 and text-embedding-3-small on short- and long-context benchmarks (MTEB, LoCo). Check the exact comparison in the paper.
- **DRIFT link:** open and run locally through Ollama, so retrieval costs nothing per call, is reproducible, and does not depend on an API changing.
- **Where:** 2.2, 3.2.3, Table 3.4.

---

# 7. Temporal databases

## Snodgrass and Ahn, "A Taxonomy of Time in Databases" (1985)

- **Cite:** `snodgrass1985taxonomy`. SIGMOD 1985, pp. 236 to 246. Write `\citep{snodgrass1985taxonomy}`.
- **What:** the paper that separated the kinds of time a database can store:
  - **valid time**: when a fact is true in the modelled world;
  - **transaction time**: when the database recorded it;
  - user-defined time.
- **Classification of databases by which times they keep:** snapshot (neither), rollback (transaction time), historical (valid time), and temporal (both). The term *bitemporal* for storing both became standard later (see Jensen et al.).
- **DRIFT link:** the origin of the two timelines DRIFT stores, which let the memory answer "what is true now", "what was true then" and "what did the agent believe then".
- **Where:** 1.2, 2.4, 3.1.

## Snodgrass, "Developing Time-Oriented Database Applications in SQL" (1999)

- **Cite:** `snodgrass1999developing`. Morgan Kaufmann.
- **What:** a practical book on implementing valid-time, transaction-time and bitemporal tables in SQL. Updates *close a period* rather than overwriting or deleting a row.
- **DRIFT link:** the database practice behind DRIFT's non-destructive closing.
- **Where:** 1.2, 2.4.

## Jensen et al., "The Consensus Glossary of Temporal Database Concepts" (1998)

- **Cite:** `jensen1998glossary`. In *Temporal Databases: Research and Practice*, LNCS 1399, Springer.
- **What:** the community's agreed definitions: valid time, transaction time, bitemporal relation, and related terms.
- **DRIFT link:** cite when you define the terms, so the definitions are standard, not yours.
- **Where:** 1.2, 2.4.

## Kulkarni and Michels, "Temporal Features in SQL:2011" (2012)

- **Cite:** `kulkarni2012sql2011`. ACM SIGMOD Record 41(3), pp. 34 to 43.
- **What:** describes the temporal features added to the SQL standard in 2011:
  - application-time period tables (valid time);
  - system-versioned tables (transaction time);
  - their combination (bitemporal tables).
  - Includes queries such as FOR SYSTEM_TIME AS OF.
- **DRIFT link:** shows bitemporal storage is standardised and used in production. Agent memory adopting it is natural; what is new is the policy question.
- **Where:** 1.2, 2.4.

## XTDB (documentation)

- **Cite:** `xtdbdocs`.
- **What:** a production bitemporal database. Cite it as an example of the technique in current use.
- **Where:** 2.4.

---

# 8. Statistics

For each: what the method is, when it is the right choice, and how DRIFT uses it.

| Key | What it is | Why it is the right choice for DRIFT | DRIFT use |
|---|---|---|---|
| `mcnemar1947` (McNemar, 1947, Psychometrika) | Test for two paired proportions, using only the pairs where the two outcomes differ (b and c) | Every policy answers the same questions, so outcomes are paired yes/no | Exact two-sided McNemar for P2 against each policy, in each run |
| `dietterich1998` (Dietterich, 1998, Neural Computation) | Compares five statistical tests for deciding whether one learning algorithm beats another | Finds McNemar has acceptable false-positive rates when the methods can be evaluated once on a fixed test set, as here | Justifies McNemar |
| `holm1979` (Holm, 1979, Scandinavian Journal of Statistics) | Step-down correction: sort p-values, compare the smallest with α/m, the next with α/(m−1), and so on | Controls the chance of any false positive across many tests, with more power than Bonferroni | Holm over the 30 comparisons per benchmark, per run |
| `efron1993bootstrap` (Efron and Tibshirani, 1993) | Resample the data with replacement many times; the spread of the statistic gives a confidence interval | No assumption about the distribution of accuracy differences | Question-level (cluster) bootstrap 95% intervals, 5,000 resamples |
| `dror2018` (Dror et al., 2018, ACL) | Surveys significance testing in NLP papers and recommends tests by metric type | Many NLP papers report no tests; the bootstrap and permutation tests suit non-normal metrics | Supports DRIFT's paired tests and bootstrap |
| `kendall1938` (Kendall, 1938, Biometrika) | Rank correlation τ = (concordant − discordant pairs) / total pairs; τ-b corrects for ties | Robust with few items and ties; the standard for comparing rankings | RQ4's main statistic |
| `spearman1904` (Spearman, 1904, American Journal of Psychology) | Pearson correlation of ranks | Familiar check on rank agreement | RQ4 check |
| `pearson1896` (Pearson, 1896, Phil. Trans. A) | Linear correlation of values | Compares the accuracies themselves, not only their order | RQ4 context |
| `perlitz2024` (Perlitz et al., 2024, arXiv:2407.13696) | "Benchmark Agreement Testing": validating benchmarks by rank correlation with others. Shows overlooked choices change conclusions; gives best practices; releases BenchBench | Precedent for asking whether two settings rank systems the same way, and for using rank correlation carefully | Precedent for RQ4's ranking-transfer test |
| `cohen1960` (Cohen, 1960) | κ = (observed agreement − chance agreement) / (1 − chance agreement) | Agreement corrected for what two graders would agree on by chance | Judge against Claude: κ = 0.919 |
| `landis1977` (Landis and Koch, 1977, Biometrics) | Bands for reading κ: 0.81 to 1.00 "almost perfect", 0.61 to 0.80 "substantial", and so on | Standard interpretation | Calls 0.919 "almost perfect" |
| `kendall1939` (Kendall and Babington Smith, 1939) | Kendall's W, agreement among many rankings at once | Only needed if you report agreement across several rankings jointly | Optional; not the same as τ |

**Exact permutation p-values.** With six policies there are only 720 possible orderings. DRIFT computes p as the share of all 720 orderings that agree at least as well as the observed one. This is exact, so no approximation is needed. It is one-sided because the hypothesis is that rankings agree.

---

# 9. Models

Cite each once, at first mention or in Table 3.4, and give the model ID, provider, reasoning setting and run dates.

| Key | Model | What the source is | Role in DRIFT |
|---|---|---|---|
| `openai2026gpt61sol` | GPT-6.1 Sol | OpenAI launch page (released 29 September 2026); its safety documentation is an addendum to the GPT-6 Astra system card | Frontier answer model, low reasoning effort |
| `anthropic2026sonnet55` | Claude Sonnet 5.5 | Anthropic product page and system card (released 28 September 2026) | Frontier answer model; reference grader for the judge check |
| `google2026gemini38flash` | Gemini 3.8 Flash | Google DeepMind model card; builds on Gemini 3.7 Flash | Mid-tier answer model; RQ4 router |
| `grattafiori2024llama3` | Llama 3.1 8B | "The Llama 3 Herd of Models" (2024): the Llama 3 family, 8B to 405B, the 3.1 release with 128K context | Small open answer model |
| `yang2025qwen3` | Qwen3 14B | Qwen3 Technical Report (2025): dense and mixture-of-experts models with switchable thinking and non-thinking modes | Small open answer model, thinking on |
| `deepseek2026v41flash` | DeepSeek V4.1 Flash | Technical report (September 2026): a mixture-of-experts model focused on compressing the KV cache | Extraction, judging, P4 review, LLM contradiction checks; reasoning off |

How to justify the choice:

- They span 8B open models to frontier models, so DRIFT can test who benefits from forgetting.
- The infrastructure model is from a different family from the answer models, so no model grades itself.
- All are served with a fixed provider and no fallback, so results are attributable to the named model.

---

# 10. Summary: every work in one line, with its DRIFT link

| Work | One line | DRIFT link |
|---|---|---|
| MemGPT | OS-style memory hierarchy; outdated records stay searchable | Behaves like P0 for changed facts |
| Mem0 | LLM chooses ADD/UPDATE/DELETE/NOOP; 10-run judge | P4's precedent; judge and repeated runs |
| Zep / Graphiti | Bitemporal graph, invalidates instead of deleting, 4-message extraction context | Same substrate idea; DRIFT asks what to do with invalidated facts |
| A-MEM | Linked notes rewritten by an LLM | LLM rewriting, like P4 |
| Generative Agents | Recency + importance + relevance retrieval | Precedent for DRIFT's weighted normalised retrieval |
| RAG | Retrieve then generate | What vector memory is |
| Zhang et al. | LLM consolidation degrades memory; keep raw evidence | Supports closing over rewriting; predicts P4's failure |
| SAGE | Novelty gate on writes | P3 is a simple version; corrections look redundant |
| Xie et al. | Models follow coherent evidence in the prompt | Why exposure matters |
| Du | Survey; forgetting is open | Positions the problem |
| STALE | Implicit conflicts; models fail to act on updates | Complementary (model vs memory); fixes DRIFT's scope |
| Supersede | Supersession gap; asserts-old-value metric | Same staleness definition and test |
| LoCoMo | Long conversations; no old value recorded | Excluded from DRIFT |
| LongMemEval | Five abilities; human-validated judge; new answer only | Excluded; judge standard |
| MQuAKE | Edit = same subject and relation, new object | Definition of supersession; MQuAKE-T benchmark |
| MemoryAgentBench | Four competencies; FactConsolidation | Counterfactual benchmark; DRIFT does not tell the model to prefer later facts |
| ConvoMem | Large conversational benchmark; full context beats RAG early | Extraction-bound result |
| G-Memory | Hierarchical team memory | Task success, not freshness |
| Collaborative Memory | Permissions and provenance in shared memory | Provenance, as in DRIFT |
| GateMem | Governance in shared memory; active forgetting | Closest to RQ4; closest idea to completeness |
| Governed Shared Memory | Stale propagation, contradiction persistence; near-duplicate gate drops contradictions | DRIFT measures both; same failure as P3 |
| Yu et al. | Consistency is the top open challenge | RQ4 studies one part of it |
| BM25 | Lexical ranking with rarity weighting | DRIFT's overlap is a simplified BM25 |
| RRF | Rank fusion without weights | Weight-free alternative tested |
| Nomic Embed | Open long-context embedder | Local, reproducible retrieval |
| Snodgrass and Ahn; Snodgrass; Jensen et al.; SQL:2011; XTDB | Valid time vs transaction time; bitemporal tables | The substrate's foundations |
| Statistics papers | McNemar, Holm, bootstrap, Kendall, Spearman, Pearson, Cohen, Landis and Koch, BenchBench | Every test DRIFT reports |
| Model sources | Launch pages, model cards, technical reports | Table 3.4 |
