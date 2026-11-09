# Chapter 1 guide: what each section must cover

Points, facts and sources for you to write from. The sentences in the thesis must be yours; nothing here is meant to be pasted.

The Stevens template's Chapter 1 has a short opening paragraph, then *Problem Statement*, *Problem Scope*, *Research Approach* and a *Hypothesis* subsection. DRIFT's chapter maps onto it like this:

| Template slot | DRIFT section |
|---|---|
| Opening paragraph under `\chapter{Introduction}` | 2 to 4 sentences: the subject of the thesis |
| Problem Statement | 1.1 The Problem |
| Problem Scope | 1.2 Background |
| Research Approach / Hypothesis | 1.3 Hypothesis and 1.4 Research Questions |
| (added) | 1.5 Contributions |

All final-run numbers below come from `paper/FINAL_REPORT.md` and `paper/tables_final/`. Citation keys are the ones in the Overleaf `references.bib`.

---

## Opening paragraph (2 to 4 sentences)

- What the thesis studies: how an LLM agent's memory should forget facts that are no longer true.
- What DRIFT is: a framework that holds the memory system fixed and changes only the forgetting policy, then measures accuracy, stale answers and cost.
- Do not open with "This chapter introduces..." (your reader asked for no descriptions of the document itself) or with a broad claim about AI in general.

---

## 1.1 The Problem

**Job of this section:** make the reader see one concrete failure, then name what is missing in current systems.

Points to cover, in this order:

1. **Setting.** An agent answers from a persistent memory written and read across many sessions, not from one context window.
   - Define *context window* (the fixed-length input a model reads per call) and *external memory* (a store outside the model; the model sees an item only when it is retrieved into the prompt).
2. **Running example** (keep the same one through Chapters 1 to 3).
   - March: "My manager is Ashley." Ashley leaves on 15 June. On 10 July the user says "Ashley has left; I now report to Daniel." Both facts are stored.
   - Later question: "Who should I send my weekly report to?"
3. **Why retrieval cannot fix it.** The two facts differ in one value, so they are almost equally similar to the question; a retriever ranking by similarity and recency returns both.
   - In DRIFT's own measurements recency separates them by about 0.016 of score. Use this number later (Chapter 4); here a plain statement is enough.
4. **What goes wrong.** The model receives two candidate answers and no reliable signal about which is current; it may answer "Ashley". Name this a *stale answer*.
5. **The gap.**
   - Memory systems handle storing and retrieving well, but what the memory discards is treated as an implementation detail.
   - Evaluations measure whole systems on recall, not whether outdated facts reach the model: MemGPT `packer2023memgpt`, Mem0 `chhikara2025mem0`, Zep `rasmussen2025zep`, A-MEM `xu2025amem`.
   - Du `du2026memory` lists learned forgetting among open challenges; STALE `chao2026stale` reports that systems "often retrieve updated evidence but fail to act on it".
6. **Define forgetting** as used in the thesis: an explicit rule deciding which stored facts the answer model can no longer see.

Avoid: results numbers (they belong to the contributions and Chapter 4), and "this is not a retrieval failure but..." (binary-contrast pattern; state what it is).

---

## 1.2 Background

**Job of this section:** give the reader every term Chapters 2 to 5 rely on, each with a one-line definition and an example.

1. **Bitemporal storage** (an established database technique: `snodgrass1999developing`, `jensen1998glossary`; standardised in SQL:2011, `kulkarni2012sql2011`).
   - *Valid time*: the period during which a fact was true in the world.
   - *Transaction time*: the period during which the system recorded it as believed.
   - The three questions the example can now answer: who the user reports to now (Daniel), on 1 July (Daniel), what the agent believed on 1 July (Ashley).
   - Why the third matters: auditing a past decision.
2. **Facts as triples.** Subject, relation, object (*user, reports to, Ashley*), stored with valid-from, stored-at and closed-at dates.
3. **Supersession.** A new fact with the same subject and relation and a different object replaces the old one. This is MQuAKE's definition of an edit, e = (s, r, o → o*) `zhong2023mquake`. In DRIFT the old fact's validity is *closed*, not deleted.
4. **Forgetting policy.** Three possible actions, which every later chapter uses:
   - *refuse* a fact at write time,
   - *hide* it at retrieval (reversible),
   - *delete* it.
   - Closing a validity window is part of the store, not forgetting.
5. **How deployed systems handle change** (one sentence each, with the mechanism):
   - LangGraph long-term store and Letta archival memory: records are replaced only if the application or agent overwrites or deletes them.
   - Mem0: an LLM chooses ADD, UPDATE, DELETE or NOOP for each new fact against the 10 most similar memories `chhikara2025mem0`.
   - Zep: an LLM detects contradictions and sets the old fact's invalid-at date; nothing is deleted `rasmussen2025zep`.
6. **Staleness.** An answer is stale when it asserts the superseded value. Measured separately from accuracy because a wrong answer need not be stale ("I don't know"). Supersede `patel2026supersede` scores stale answers the same way.
7. **Graph-aware consolidation.** Keeps whichever conflicting value is supported by more stored facts; uses the graph but not time. Needed to understand RQ3.

Keep it to what the reader needs. Detailed system comparisons go to Chapter 2.

---

## 1.3 Hypothesis

**Job:** one paragraph stating a testable claim, with how each part will be measured.

- Claim (committee-approved wording): a forgetting policy that removes only superseded facts
  1. gives answer accuracy at least as good as append-only memory,
  2. produces fewer answers that repeat superseded information,
  3. uses fewer prompt tokens and stores fewer facts than append-only memory and novelty-based forgetting.
- Add one sentence per part saying what would count as support:
  - accuracy compared question by question with a paired test,
  - staleness rate,
  - prompt tokens per question and facts stored at the end of a run.
- State it as a prediction. No results here; the verdict goes in Chapter 6.

---

## 1.4 Research Questions

**Job:** the four questions, each followed by one sentence on how it is answered.

| RQ | Question (approved wording) | Answered by |
|---|---|---|
| RQ1 | Does append-only memory measurably surface superseded facts to the answer model and produce stale answers? | How often the old value reaches the prompt under P0, and how often models repeat it |
| RQ2 | Which forgetting policy gives the best trade-off between accuracy, staleness rate and cost (prompt tokens, facts stored)? | Seven policies × five models × three benchmarks, paired comparisons |
| RQ3 | Is the benefit due to the bitemporal timeline, or does a graph-aware policy that ignores time do as well? | P2 against P5, which has the same facts and graph but no dates |
| RQ4 | With several agents writing to and reading from shared memory, do single-agent policy rankings hold? | Three multi-agent topologies; agreement between rankings (Spearman, with Kendall as a check) |

A numbered list is acceptable for the RQs themselves; the "answered by" sentences should be prose.

---

## 1.5 Contributions

**Job:** what is new, each with its evidence, in paragraphs. This is where a few headline numbers belong.

1. **A controlled comparison of forgetting policies.**
   - What is held fixed: store, extraction, retrieval, answer prompt, judge.
   - What varies: the policy. Seven policies, five answer models from 8B open models to frontier models, three benchmarks.
   - Prior systems are evaluated as whole designs.
2. **A staleness measure that separates exposure from reading.**
   - Exposure: does the old value reach the prompt? Reading error: does the model repeat it?
   - Asserting the old value is counted separately from merely mentioning it.
3. **Bitemporal invalidation is more accurate and cheaper.**
   - Accuracy 93.5% → 98.5% (MQuAKE-T) and 67.4% → 79.4% (FactConsolidation), p < 0.001.
   - Staleness to about 1%; 9 to 25% fewer prompt tokens.
   - The timeline, not the graph, produces the gain: P2 beats P5 by 23.5 and 15.2 points.
4. **Forgetting matters most for small models.** Llama 3.1 8B rises from 29% to 62% on FactConsolidation and comes close to frontier models on real-world updates at a small fraction of the cost.
5. **Measured failure modes of popular policies.**
   - Novelty gating discards corrections as duplicates.
   - LLM consolidation deletes updates that contradict its own training (on FactConsolidation, 49 of the 65 facts it deleted held the current answer).
6. **Multi-agent memory.** Rankings transfer (Spearman 0.93 to 0.94), and detecting contradictions between different writers needs semantic matching.
7. **Benchmark audit.** LoCoMo `maharana2024locomo` and LongMemEval `wu2025longmemeval` record no superseded answer, so a staleness metric reads zero on them. MQuAKE-T, FactConsolidation `hu2026memoryagentbench` and ConvoMem `pakhomov2025convomem` do.
8. **One sentence on what is not claimed:** closing a fact instead of deleting it is Zep's mechanism; the contribution is the controlled evidence for when it helps, by how much and for whom.
9. Optional: the dialogue limitation (ConvoMem accuracy is bounded by extraction), so the contributions do not overstate.

---

## Writing rules for this chapter

From your committee's comments and the no-ai-slop guide (github.com/petergyang/no-ai-slop):

- **Paragraphs, not bullet lists** (Dr. Helsing). Lists only for the RQs.
- **Define every term at first use, with an example.**
- **Explain how, not only what.** Every claim about a system needs its mechanism in a sentence.
- **Be concrete.** Names, numbers, dates and mechanisms. Portability test: if a sentence could appear unchanged in someone else's thesis, replace it with something specific to DRIFT.
- **Name the source** for every claim about prior work; never "studies show" or "experts agree".
- **Repeat the right word.** Do not rotate "memory / store / repository / knowledge base" for variety; pick one term per concept and keep it.
- **Active voice:** "P2 hides closed facts", not "closed facts are hidden by the policy".
- **No meta-commentary:** "this section describes", "it is important to note", "the key point is".
- **Patterns to avoid:**
  - binary contrasts ("not X but Y"),
  - colon reveals ("The result: ..."),
  - trailing "-ing" analysis ("..., highlighting the need for..."),
  - importance puffery ("plays a vital role", "a pivotal step"),
  - summary-recap endings ("In conclusion, ...").
- **Words to avoid:** delve, leverage, utilize, facilitate, robust, crucial, pivotal, landscape, realm, intricate, paramount, transformative, harness, seamless.
- **No em dashes**; use commas, full stops or parentheses.
- **No results in Chapter 2**; in Chapter 1, only the few headline numbers in 1.5.

---

## Where to cite, section by section

How to cite with natbib in the Stevens template:

- `\citep{key}` gives "(Chhikara et al., 2025)" at the end of a claim.
- `\citet{key}` gives "Chhikara et al. (2025)" when the authors are the subject of your sentence.

Cite at the first sentence that relies on the source, not at the end of a paragraph that mixes several sources. The "what the source supports" column is what you may claim; check the location given before writing.

### Opening paragraph

No citations needed. It states what this thesis does.

### 1.1 The Problem

| Point you are making | Cite | What the source supports (where to check) |
|---|---|---|
| Agents use external memory beyond the context window; memory is moved in and out of the prompt | `\citep{packer2023memgpt}` | MemGPT's main context vs recall and archival storage (Sections 1 and 2) |
| Production memory systems extract, update and retrieve facts across sessions | `\citep{chhikara2025mem0}` | Mem0's extraction and update phases (Section 2) |
| A temporal memory that keeps facts with validity periods exists | `\citep{rasmussen2025zep}` | Graphiti's bi-temporal edges (Section 2.2.3) |
| Memory systems are evaluated on recall and QA accuracy as whole systems | `\citep{packer2023memgpt, chhikara2025mem0, xu2025amem, rasmussen2025zep}` | Their evaluation sections: DMR, LoCoMo, LongMemEval; none reports staleness separately |
| Benchmarks mostly measure whether a fact can be recalled, not whether a changed fact stops being used | `\citep{chao2026stale}` | STALE, Section 1: existing benchmarks "predominantly operationalize success as static fact retrieval" |
| Systems retrieve updated evidence but fail to act on it | `\citet{chao2026stale}` | STALE abstract and contributions |
| Bounded memory loses accuracy on knowledge updates even for frontier models | `\citet{patel2026supersede}` | gpt-5.4: 92% to 77%, paired McNemar p = 0.0033 (abstract, Section 5.1) |
| Forgetting is an open problem in agent memory | `\citep{du2026memory}` | Survey's open challenges, which list "learned forgetting" |

### 1.2 Background

| Point you are making | Cite | What the source supports |
|---|---|---|
| Valid time and transaction time are established database concepts | `\citep{jensen1998glossary}` | Definitions of valid time and transaction time |
| Building time-oriented (bitemporal) applications | `\citep{snodgrass1999developing}` | Book-length treatment |
| Temporal tables are part of the SQL standard | `\citep{kulkarni2012sql2011}` | SQL:2011 application-time and system-time periods |
| A fact update is a change of object for the same subject and relation, e = (s, r, o → o*) | `\citep{zhong2023mquake}` | MQuAKE, Section 2 (definition of a fact edit) |
| LangGraph's long-term store saves and searches records; replacement is up to the application | `\citep{langgraphdocs}` | Documentation page on stores |
| Letta (formerly MemGPT) archival memory | `\citep{lettadocs}` with `\citep{packer2023memgpt}` | Documentation on memory management |
| Mem0 decides ADD, UPDATE, DELETE or NOOP per fact against the 10 most similar memories | `\citep{chhikara2025mem0}` (optionally `\citep{mem0docs}`) | Mem0 Section 2 (update phase; m = 10 and s = 10 are given there) |
| Zep closes a contradicted fact's validity instead of deleting it | `\citep{rasmussen2025zep}` | Section 2.2.3, "Temporal Extraction and Edge Invalidation" |
| Scoring an answer as stale when it asserts a superseded value | `\citep{patel2026supersede}` | The reward definition, r_stale = −1 if the answer asserts a superseded value |
| Rewriting memory with an LLM can make it worse than no memory | `\citep{zhang2026faulty}` | Only if you mention LLM consolidation here; detail goes to Chapter 2 |

Graph-aware consolidation needs no citation in Chapter 1; P5 is DRIFT's own policy. Mention its inspiration (`\citep{graphify}`) in Chapter 3.

### 1.3 Hypothesis

No citations. The hypothesis is your claim.

### 1.4 Research Questions

No citations in the questions themselves. If the RQ4 sentence mentions shared memory as an open problem, `\citep{ren2026gatemem}` supports that shared, multi-principal memory is "insufficiently studied" (GateMem, Section 1).

### 1.5 Contributions

| Point you are making | Cite | Why |
|---|---|---|
| Prior systems are evaluated as complete designs | `\citep{packer2023memgpt, chhikara2025mem0, rasmussen2025zep, xu2025amem}` | Contrast with DRIFT isolating the policy |
| The three benchmarks used | MQuAKE-T `\citep{zhong2023mquake}`, FactConsolidation `\citep{hu2026memoryagentbench}`, ConvoMem `\citep{pakhomov2025convomem}` | Cite each at first mention |
| LoCoMo and LongMemEval record no superseded answer | `\citep{maharana2024locomo, wu2025longmemeval}` | The claim is your audit; the citation identifies the benchmarks |
| Novelty gating, as used in deployed systems | `\citep{wang2026sage}` | SAGE, the gate P3 simplifies |
| LLM consolidation risks | `\citep{zhang2026faulty}` | Supports the P4 contribution |
| Invalidating instead of deleting is Zep's mechanism | `\citep{rasmussen2025zep}` | Needed in the "what is not claimed" sentence |
| Multi-agent shared memory | `\citep{ren2026gatemem}` | Closest work; it studies governance, not ranking transfer |

Your own results (accuracy, staleness, Spearman) are cited to your chapters, for example "(Section 4.3)", not to papers.

### References to add to `references.bib` if you use them

These are not in the Overleaf `references.bib` yet; add them only if Chapter 1 or 2 mentions them.

- Generative Agents (Park et al., 2023), arXiv:2304.03442. For the recency score, in Chapter 3.
- Collaborative Memory (Rezazadeh et al., 2025), arXiv:2505.18279. For multi-agent memory, in Chapter 2.
- Governed Shared Memory (Margalit et al., 2026), arXiv:2606.24535. For stale propagation in shared memory, in Chapter 2.
- G-Memory (Zhang et al., NeurIPS 2025), arXiv:2506.07398. For multi-agent memory, in Chapter 2.
