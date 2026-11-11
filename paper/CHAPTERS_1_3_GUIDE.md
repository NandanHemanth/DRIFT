# Chapters 1 to 3: detailed guide, section by section and paper by paper

What to cover in every section and subsection of Chapters 1 to 3, where each figure and table goes, and for every referenced work: what it is, how it works, what it reports, what to say about it, and how DRIFT relates to it.

Everything here is points, facts, numbers and citation keys. The sentences in the thesis must be yours.

**How to use this guide**

- Part A covers Chapter 1, Part B Chapter 2, Part C Chapter 3.
- Part D is a reference card for every work cited in Chapters 1 to 3, giving what to say about each.
- `key` is the BibTeX key in `paper/references_v3.bib`. Cite systems as `Name~\citep{key}`; use `\citet{key}` when the authors are the subject of the sentence.
- Numbers marked **[v3]** come from the final campaign (`paper/V3_ANALYSIS.md`). Use them only in the contributions (1.5) and in Chapters 4 and 5, not in Chapter 2.
- Professor's rules: full paragraphs, define each term at first use, open each section with its point, no "This chapter..." openers, no em dashes, no DRIFT results in Chapter 2.

**Running example** (use it in all three chapters):

- March: "My manager is Ashley."
- 15 June: Ashley leaves.
- 10 July: "Ashley has left; I now report to Daniel."
- Question: "Who should I send my weekly report to?"

---

# Part A. Chapter 1: Introduction

## Opening paragraph (2 to 4 sentences, under `\chapter{Introduction}`)

- **Subject:** how the long-term memory of an LLM agent should deal with facts that stop being true.
- **What DRIFT is:** a framework that fixes the memory store, extraction, retrieval, answer prompt and grading, and changes only the forgetting policy.
- **What it measures:** accuracy, stale answers and cost.
- **What the reader will get:** a controlled answer to which policy works, why it works, and for which models it matters.
- **Do not:** open with "In recent years, AI has..." or "This chapter introduces...".

## 1.1 The Problem

Job: make one concrete failure visible, then name the gap.

1. **Setting**
   - Agents now keep memory across sessions: personal assistants, coding agents, customer support.
   - Define *context window*: the fixed amount of text a model reads in one call.
   - Define *external memory*: a store outside the model. The model sees an item only when it is retrieved into the prompt.
   - Why external memory exists: histories outgrow the context window, and sending the full history is slow and expensive. MemGPT `packer2023memgpt` frames this as an operating-system memory hierarchy.
2. **Running example.** Both the Ashley fact and the Daniel fact are stored.
3. **Why retrieval cannot separate them**
   - The two facts differ in one word, so they are almost equally similar to the question.
   - A retriever that ranks by similarity (and even by recency) returns both.
   - State this qualitatively here; the measured exposure goes in Chapter 4.
4. **What goes wrong**
   - The model sees two answers and must work out which is current. It may say "Ashley".
   - Define a *stale answer*: an answer that asserts a value that has been replaced.
5. **Why this matters**
   - A stale answer is confidently wrong, and the user may act on it.
   - It gets worse over time, because every change leaves one more outdated fact behind.
   - Small, cheap models are the ones most often deployed at scale, and they are the most easily misled. State this as a motivation; the evidence comes in Chapter 4.
6. **The gap in current work**
   - Memory systems are carefully designed for storing and retrieving; what they discard is an implementation detail.
   - Evaluations measure whole systems on recall and accuracy, not whether outdated facts reach the model: MemGPT `packer2023memgpt`, Mem0 `chhikara2025mem0`, Zep `rasmussen2025zep`, A-MEM `xu2025amem`.
   - The survey by `\citet{du2026memory}` lists learned forgetting among the open challenges.
   - STALE `chao2026stale` finds that agents often retrieve the updated evidence but fail to act on it.
7. **Define forgetting** as used in this thesis: an explicit rule that decides which facts the answer model can no longer see.

- **Fig 1.1 (recommended): timeline of the running example.** A horizontal time axis with three marks (March, 15 June, 10 July) and two bars showing when each fact was valid. It shows valid time and transaction time before 1.2 defines them.
- Avoid: result numbers; the "this is not X but Y" sentence pattern.

## 1.2 Background

Job: give the reader every term Chapters 2 to 5 depend on, each with a definition and the running example.

1. **Facts as triples**
   - A fact is (subject, relation, object), for example (user, reports to, Ashley).
   - Pick "triple" or "triplet" and keep it throughout.
2. **Bitemporal storage**
   - *Valid time*: when the fact was true in the world (Ashley: March to 15 June).
   - *Transaction time*: when the system recorded it (Daniel: from 10 July).
   - Origin: Snodgrass and Ahn `snodgrass1985taxonomy`. Book treatment: `snodgrass1999developing`. Agreed definitions: `jensen1998glossary`. Part of the SQL standard since SQL:2011 `kulkarni2012sql2011`.
   - The three questions the example can answer:
     - who now: Daniel;
     - who on 1 July: Daniel;
     - what the agent believed on 1 July: Ashley.
   - Why the third matters: auditing a past decision.
3. **Supersession**
   - A new fact with the same subject and relation and a different object replaces the old one *in meaning*.
   - MQuAKE `zhong2023mquake` defines an edit as e = (s, r, o → o*).
   - It applies only to *functional* relations, which hold one value at a time ("reports to", "lives in"), not to multi-valued ones ("likes").
4. **Closing**
   - What the store does on a contradiction: it sets the old fact's end of validity. The fact stays in memory.
   - Closing is not forgetting.
5. **Forgetting policy**
   - The rule deciding which facts the answer model can no longer see. Three actions:
     - *refuse* an incoming fact at write time;
     - *hide* a stored fact at retrieval (reversible);
     - *delete* a stored fact (in DRIFT a soft delete, kept on record).
   - A policy may use any of these; some use none.
6. **How deployed systems handle change** (one sentence each, with the mechanism)
   - LangGraph `langgraphdocs` and Letta `lettadocs`: records change only if the application or agent overwrites or deletes them.
   - Mem0 `chhikara2025mem0`: an LLM chooses ADD, UPDATE, DELETE or NOOP for each new fact against its most similar memories.
   - Zep `rasmussen2025zep`: an LLM detects contradictions and sets the old fact's invalid-at time; nothing is deleted.
7. **Staleness as a measurement**
   - A stale answer asserts the old value (and not the current one).
   - It is measured separately from accuracy, because an answer can be wrong without being stale ("I don't know").
   - Supersede `patel2026supersede` scores stale answers the same way.
8. **Graph-aware consolidation** (needed for RQ3)
   - Keeps whichever conflicting value is supported by more stored facts.
   - Uses the graph but ignores time.
9. **Multi-agent memory** (needed for RQ4)
   - Several agents write to and read from one store, so the agent reading a fact may not be the one that wrote it.
   - GateMem `ren2026gatemem` and Governed Shared Memory `margalit2026governed` study this setting.

## 1.3 Hypothesis

- One paragraph, using the committee-approved wording. A policy that removes only superseded facts:
  1. gives answer accuracy at least as good as append-only memory;
  2. produces fewer answers that repeat superseded information;
  3. uses fewer prompt tokens and stores fewer facts than append-only memory and novelty-based forgetting.
- Add one sentence on what counts as support for each part:
  - accuracy compared on the same questions with a paired test;
  - staleness rate;
  - prompt tokens per question and facts stored at the end of a run.
- State it as a prediction; the verdict belongs in Chapter 6.

## 1.4 Research Questions

The four RQs are already in the template. After the list, write one sentence per RQ saying how it is answered:

| RQ | How it is answered |
|---|---|
| RQ1 | How often the old value reaches the prompt under append-only memory (P0), and how often models repeat it |
| RQ2 | 7 policies × 5 answer models × 3 benchmarks, run 3 times; paired comparisons of accuracy, staleness and cost |
| RQ3 | P2 against P5, which has the same facts and graph but ignores dates |
| RQ4 | Shared, independent and orchestrator topologies; Kendall's τ between single-agent and multi-agent policy rankings, with Spearman and Pearson as checks |

- **Table 1.1 (optional): RQ → experiment → metric → section of Chapter 4.**

## 1.5 Contributions

One paragraph per contribution, each with its evidence pointer. Headline numbers belong here, all **[v3]**.

1. **A controlled comparison.** The policy is the only variable: 7 policies × 5 models (8B to frontier) × 3 benchmarks, 3 independent runs, 31,080 graded answers. Prior systems are evaluated as whole designs.
2. **A mechanism-level staleness measure.**
   - Exposure (does the old value reach the prompt) times reading error (does the model repeat it).
   - Asserting the old value is counted separately from mentioning it.
3. **Bitemporal invalidation is more accurate, fresher and cheaper where changes are explicit.**
   - MQuAKE-T: 95.2% vs 91.3% accuracy; FactConsolidation: 79.9% vs 67.2%.
   - Fewer stale answers and 9% to 29% fewer prompt tokens.
   - The benefit comes from time, not graph structure: removing dates costs 18% and 15%.
4. **Correct forgetting moves the work of tracking change from the model to the memory.**
   - Llama 3.1 8B: 75.7% → 93.1% on MQuAKE-T, 31.3% → 62.7% on FactConsolidation.
   - Frontier models barely change.
   - The extra gain for small models is significant.
5. **Measured correctness of forgetting.**
   - Sound and complete defined as precision and recall of forgetting decisions.
   - P2 is 100% sound and 92% / 85% complete; P3, P4 and P5 are almost entirely incomplete.
6. **Measured failure modes.**
   - Novelty gating refuses corrections.
   - LLM consolidation is unstable and removes current values.
   - On conversational data, contradiction detection over-fires and extraction is the bottleneck.
7. **Multi-agent memory.**
   - Rankings transfer where changes are explicit (Kendall τ 0.73 to 0.87, all p < 0.03), and P2 stays best.
   - With several writers, extractors name relations differently, so P2's completeness falls (92% to 45% on MQuAKE-T) and its advantage shrinks.
   - LLM matching doubles cross-writer detection.
8. **Benchmark audit.** Which benchmarks can measure memory revision at all: LoCoMo and LongMemEval record no old value.
- Close with what DRIFT does *not* claim: the invalidate-instead-of-delete mechanism exists in Zep. DRIFT's contribution is the controlled comparison and the measurements.

## 1.6 Thesis Organization

- 2 to 3 sentences naming what each chapter contains.

---

# Part B. Chapter 2: Related Work

Rules: open each section with its point, explain *how* each system works (mechanism, not only results), 2 to 5 paragraphs per section, no DRIFT results.

## Opening paragraph

- **Point:** memory systems are evaluated as complete designs, so the effect of how they forget cannot be separated from storage, extraction and retrieval.
- Preview the sections: systems, extraction and retrieval, consolidation, temporal data, staleness and benchmarks, multi-agent memory.

## 2.1 Agent Memory Systems

- **Point:** each system bundles a forgetting rule with everything else, and none isolates it.
- Define *a memory*: one stored record, usually a fact or a message.
- Paper cards (Part D): MemGPT, Mem0, Zep, A-MEM, Generative Agents.
- For each system, cover four things:
  1. how it stores;
  2. how it decides what to change;
  3. what happens to an outdated fact;
  4. what its evaluation measures, and what it leaves out (staleness).
- **End of section:** a summary sentence that outdated facts are deleted (Mem0), invalidated (Zep), left searchable (MemGPT) or rewritten (A-MEM), and that none of these choices was tested against the others.

## 2.2 Fact Extraction and Retrieval

- **Point:** extraction and retrieval decide what can reach the model. DRIFT holds them fixed, so the reader needs to know the standard practice.
- **Extraction**
  - Mem0 uses a conversation summary and the last 10 messages.
  - Zep uses the previous 4 messages as context and extracts only from the current message.
  - LongMemEval uses Llama 3.1 8B to extract user facts for indexing.
- **Retrieval**
  - Dense similarity: nomic-embed-text `nussbaum2024nomic`.
  - Lexical: BM25 `robertson2009bm25`.
  - Hybrid scoring: Generative Agents `park2023generative`, Zep.
  - Combining signals: weighted sum vs reciprocal rank fusion `cormack2009rrf`.
- Leave DRIFT's choices for Chapter 3, but make sure each one has its precedent here.

## 2.3 Consolidation and Write-side Filtering

- **Point:** removing information by rewriting or gating is risky, because a correction looks like a duplicate of what it corrects.
- Kinds of consolidation error: lost detail, unrelated facts merged, older value kept, invented statement. Errors compound over updates.
- Paper cards: `zhang2026faulty`, `xie2024adaptive`, SAGE `wang2026sage`.
- **End of section:** a correction shares subject, relation and wording with the fact it replaces, so a similarity gate scores it as redundant.

## 2.4 Temporal Data Management

- **Point:** bitemporal storage is a mature database technique; agent memory has adopted the data model but not the policy question.
- Cards: `snodgrass1985taxonomy`, `snodgrass1999developing`, `jensen1998glossary`, `kulkarni2012sql2011`, XTDB `xtdbdocs`.
- **End of section:** in databases, closing a period and deleting a row are separate operations. DRIFT tests that separation in agent memory.

## 2.5 Staleness and Benchmarks

- **Point:** few benchmarks can measure memory revision at all.
- **What a benchmark needs:**
  - a fact that changes;
  - a question about its current value;
  - the old value recorded, so that a stale answer can be scored.
- Cards:
  - frameworks: Du `du2026memory`, STALE `chao2026stale`, Supersede `patel2026supersede`;
  - benchmarks: LoCoMo `maharana2024locomo`, LongMemEval `wu2025longmemeval`, MQuAKE `zhong2023mquake`, MemoryAgentBench / FactConsolidation `hu2026memoryagentbench`, ConvoMem `pakhomov2025convomem`.
- **How others grade:**
  - lexical F1 (LoCoMo, Mem0, A-MEM);
  - substring exact match (MemoryAgentBench);
  - LLM judge validated against humans (LongMemEval above 97%, STALE 95.8%);
  - a programmatic matcher (Supersede).
- **Table 2.1: benchmarks** (in the template): questions, whether the old value is recorded, kind of change.

## 2.6 Multi-agent Memory

- **Point:** shared memory is now studied for access control and governance, but not for whether forgetting policies chosen for one agent still work for many.
- Cards: G-Memory `zhang2025gmemory`, Collaborative Memory `rezazadeh2025collaborative`, GateMem `ren2026gatemem`, Governed Shared Memory `margalit2026governed`, `\citet{yu2026multiagent}`.
- **End of section:** consistency across agents is named as an open problem, and nobody measures ranking transfer.

## 2.7 Summary and Positioning

- **Table 2.2: how prior systems treat outdated facts.**
  - Rows: MemGPT, Mem0, Zep, A-MEM, Generative Agents, SAGE, GateMem, DRIFT.
  - Columns: what happens to an old fact (left searchable / deleted / invalidated / rewritten / decayed / gated), measures staleness, isolates the policy, multi-agent.
- One paragraph stating the gap DRIFT fills. No DRIFT results.

---

# Part C. Chapter 3: Method

This must describe v3 as it ran. Changes since the October text in the template:

- extraction sees the previous 4 lines;
- the main matrix ran 3 times;
- RQ4 and the follow-ups use all five answer models on all three benchmarks.

## Opening paragraph

- **Point:** the design isolates the forgetting policy.
- List what is fixed (store, extraction, contradiction rule, retrieval, answer prompt, judge) and the single thing that varies.

## 3.1 The Memory Substrate

1. **Fact structure.** Triple plus text, for example (New Zealand, head of government, Jacinda Ardern) with the sentence it came from.
2. **The two timelines and the fields** (Table 3.1). Name valid time and transaction time and cite `snodgrass1985taxonomy`.
   - valid start;
   - invalid-at, empty while the fact is current;
   - ingested;
   - pruned, empty while kept;
   - provenance;
   - active.
3. **Contradiction rule**
   - Same subject and functional relation with a new object closes the old fact's valid time.
   - Closing is non-destructive. Same idea as Zep `rasmussen2025zep`; matches the edit definition of MQuAKE `zhong2023mquake`.
4. **Normalised matching**
   - Ignores case, articles and filler words, and matches in either direction ("X is headquartered in Y" vs "Y is home to X").
   - Exact matching and an LLM check (Zep-style) are the follow-up alternatives.
5. **Exclusions**
   - Speech acts ("said", "told") and multi-valued relations are never closed.
   - Evidence: without the speech-act guard, 379 of 380 facts were closed on a corpus with 133 real changes.
6. **Soft delete.** Deletion sets active = false and records the time. The fact is never retrieved again but stays for analysis.

- **Table 3.1: fields stored with every fact** (in the template).

## 3.2 The Pipeline

Open with Fig 3.1, then one subsection per stage. For each stage give what it does, the setting, and why, with its precedent.

- **Fig 3.1: pipeline** (`F00_pipeline.pdf`). Update the caption to say extraction sees 4 earlier lines.

### 3.2.1 Extraction
- Model: DeepSeek V4.1 Flash `deepseek2026v41flash`, reasoning off, temperature 0.
- Output: a JSON list of triples with the source sentence.
- Context: the previous 4 lines are shown for reference only; facts come only from the current session. Zep uses exactly 4 previous messages `\citep[Sec.~2.2.1]{rasmussen2025zep}`.
- A rule pass adds functional relations the LLM missed (moved to, works at). It reads only the current lines.
- If the reply has no readable JSON, it retries once with 4,096 tokens.
- Why one fixed extractor: the policy must be the only variable.

### 3.2.2 Contradiction detection and closing
- Refer to 3.1. Say when it runs: on every write.

### 3.2.3 Retrieval
- Score = 0.6 semantic + 0.3 lexical + 0.1 recency; the top 25 facts go to the prompt.
- **Semantic:** cosine similarity of nomic-embed-text vectors `nussbaum2024nomic`, run locally.
- **Lexical:** share of the question's words (3 or more letters) found in the fact. It is a simplified BM25 `robertson2009bm25` without rarity weighting.
- **Recency:** the fact's valid-start date scaled to 0 to 1 across stored facts. Same idea as the recency score of Generative Agents `park2023generative`.
- All three signals lie between 0 and 1, so only the ratio of the weights matters.
- The weights come from a sweep (Chapter 4 shows the result). Reciprocal rank fusion `cormack2009rrf` is the weight-free alternative tested in the follow-ups.
- Why 25: wide enough that the current fact is retrieved; the old fact is then also present unless a policy removes it.

### 3.2.4 The policy interface
- **Listing 3.1:** three hooks, `on_write`, `after_session`, `on_retrieve`. One policy per run.

### 3.2.5 Answering
- The model sees the 25 facts, each with its valid-start date.
- The prompt does not say "prefer the newest fact". MemoryAgentBench `hu2026memoryagentbench` tells agents to prioritise later information; DRIFT deliberately does not, because that would give every policy P2's behaviour for free.

### 3.2.6 Grading
- Two fixed rules first:
  - a refusal ("I don't know") is incorrect;
  - the gold answer stated verbatim is correct.
- Otherwise a DeepSeek V4.1 Flash judge decides.
- Token F1 is also recorded, as in LoCoMo `maharana2024locomo` and Mem0.
- Why a judge: Mem0 shows F1 misleads on facts ("born in July" vs "March" overlap heavily).
- Why a different model family judges: answer models never grade themselves.

- **Table 3.2 (new): every constant and its source.**

| Constant | Value | Source |
|---|---|---|
| Context lines | 4 | Zep |
| k | 25 | sweep and gold-support check |
| Weights | 0.6/0.3/0.1 | sweep, confirmed in the follow-up |
| P1 TTL | 20 days | sensitivity sweep |
| P2 grace | 7 days | grace sweep (V10) |
| P3 threshold | 0.9 | sweep |
| P4 cadence, batch and merge threshold | every 3rd session, 40, 0.97 | sweep |
| Temperature | 0 | standard practice (Mem0, LongMemEval, Supersede) |
| Retry tokens | 4,096 | parse-failure fix |

## 3.3 Policies Under Test

1. **Definition** of a forgetting policy and its three actions (refuse, hide, delete).
2. **NOMEM**
   - Retrieval returns nothing; the floor.
   - Its staleness is trivially near 0, because it never sees the old value.
   - Refusals are graded incorrect.
3. **P0, append-only.** Shows everything; the baseline every deployed system without forgetting resembles.
4. **P1, time-based decay.** Deletes facts more than 20 days past their valid start. A decay rule in the spirit of recency scoring; unsound by construction.
5. **P2, bitemporal invalidation.** Hides closed facts at retrieval and deletes them 7 days after closing.
6. **P3, novelty gate.** Refuses a fact with cosine similarity above 0.9 to any stored fact. A simplified SAGE `wang2026sage`.
7. **P4, LLM consolidation.** Every third session DeepSeek reviews facts in batches of 40 and may drop some; near-duplicates (similarity above 0.97) are merged, keeping the newest. In the spirit of Mem0 and A-MEM.
8. **P5, topology consolidation.**
   - Between conflicting facts, keeps the object supported by more other facts.
   - Never uses dates; communities by label propagation; never reduces an entity below 2 facts.
   - The time ablation of P2.
9. **Correctness criteria**, defined here and measured in Chapter 4:
   - *sound*: never hides a still-true fact;
   - *complete*: hides every replaced fact.
   - Say these are DRIFT's definitions, analogous to precision and recall of forgetting decisions. The closest prior ideas are GateMem's "active forgetting" and MemoryAgentBench's "selective forgetting".
10. **Expected behaviour of each policy** from its mechanism (the theory table in `V3_ANALYSIS.md`, Section 3). This makes Chapter 4 a test of predictions.

- **Table 3.3: the seven policies** (in the template).

## 3.4 Benchmarks and Data Preparation

For each benchmark: source, what kind of change, how it was converted to sessions and questions, size.

- **MQuAKE-T** `zhong2023mquake`
  - Real Wikidata changes, 2021 to 2023.
  - 96 single-hop questions, all about changed facts.
  - One conversation spanning 37 days.
- **FactConsolidation** `hu2026memoryagentbench`
  - Counterfactual edits built from MQuAKE edit pairs, 6K-token single-hop version.
  - 100 questions, 65 with a recorded old value.
  - 38 sessions spanning 37 days.
- **ConvoMem** `pakhomov2025convomem`
  - Changes stated in natural dialogue.
  - 100 changing-fact questions over 10 conversations of 20 sessions, spanning 19 days.
- **Why these three:** each records the old value; together they cover clean, counterfactual and conversational change. FactConsolidation also stops models from answering from memorised knowledge.
- **Why not LoCoMo and LongMemEval:** no recorded old value (Table 2.1).
- **Scope to state:** not covered are implicit or cascading changes (STALE's Type I and II), multi-valued relations, noisy logs and long horizons.

## 3.5 Experimental Setup

1. **Main matrix**
   - 7 policies × 5 answer models × 3 benchmarks = 105 cells and 10,360 graded answers per run.
   - Run 3 times, with a replicate tag that remakes every call, including extraction and judging.
   - Why 3 runs: temperature 0 is not fully deterministic for hosted reasoning models and for the extractor. Mem0 repeated its judge 10 times for the same reason.
2. **Models** (Table 3.4)
   - Frontier: GPT-6.1 Sol `openai2026gpt61sol`, low reasoning effort; Claude Sonnet 5.5 `anthropic2026sonnet55`.
   - Mid-tier: Gemini 3.8 Flash `google2026gemini38flash`, low effort.
   - Small: Llama 3.1 8B `grattafiori2024llama3`; Qwen3 14B `yang2025qwen3`, reasoning on.
   - Infrastructure: DeepSeek V4.1 Flash `deepseek2026v41flash`.
   - Each model is pinned to one provider through OpenRouter `openrouterdocs` with no fallback.
   - In the table give the exact model ID, provider, reasoning setting and run dates.
   - Why these five: they span 8B open models to frontier models, so "who benefits" can be tested.
3. **RQ4 topologies** (Table 3.5, Fig 3.2)
   - *Shared:* 5 writers (the five answer models as extractors), round-robin over sessions, one graph per conversation; every answer model reads it.
   - *Independent:* 3 private agents, each seeing a random 80% of sessions (seed 42); DeepSeek extracts.
   - *Orchestrator:* one ingesting agent; a Gemini router assigns each question to one of 4 specialist workers.
   - Policies P0 to P5 (NOMEM excluded). Shared memory also runs with exact and LLM matching for P0 and P2.
   - **State honestly:**
     - the orchestrator shares run 1's extraction, so it checks that routing changes nothing;
     - in ConvoMem each conversation has a single writer.
4. **Follow-ups** (run once, all five models, P2)
   - Contradiction matching: exact, normalised, LLM.
   - Retrieval weighting: 0.9/0.1/0.2, 0.8/0.1/0.1, no recency, RRF.
   - Grace sweep: 0, 1, 3, 5, 7, 10, 14, 21 days and never, with history questions ("before it changed, what was it?").

- **Fig 3.2 (new): the three topologies** side by side.
- **Table 3.5 (new): RQ4 design.** Columns: writers, graphs, extractor, readers, policies, what it tests.

## 3.6 Metrics

| Metric | Definition | Precedent |
|---|---|---|
| Accuracy | share of answers graded correct (rules, then judge) | LongMemEval, Mem0 (judge) |
| Token F1 | word-overlap F1 with the gold answer | LoCoMo, Mem0, A-MEM |
| Staleness | answer asserts the old value and not the current one | Supersede's r_stale |
| Mentions-old | answer contains the old value at all | DRIFT addition |
| Exposure | old value appears in a retrieved fact | like Recall@k (LongMemEval), but for the *old* value |
| Reading error | stale answers among exposed questions | DRIFT |
| Cost | prompt and completion tokens per question, USD per 1,000 correct answers, facts stored at the end | Mem0, Zep (tokens) |
| Soundness, completeness | Section 3.3 | DRIFT |
| RQ4 extras | cross-writer invalidations, stale propagation, contradiction persistence | Governed Shared Memory names the last two |
| Stability | mean ± SD over 3 runs; flip rate = share of questions whose grade changes across runs | Mem0 (mean ± SD) |

- State the decomposition P(stale) ≈ P(exposed) × P(reading error | exposed). It links the metrics to the theory.
- State what is *not* measured: latency.

## 3.7 Statistics

**Table 3.6: each test, its use, why, and its reference.**

| Test | Used for | Why | Reference |
|---|---|---|---|
| Exact McNemar, per run | P2 vs each policy | paired yes/no outcomes on the same questions | `mcnemar1947`, `dietterich1998` |
| Holm correction | 30 comparisons per benchmark | family-wise error, less conservative than Bonferroni | `holm1979` |
| Question-level (cluster) bootstrap 95% CI | size of every difference | no distribution assumption; a question appears 15 times (5 models × 3 runs), so resample questions | `efron1993bootstrap`, `dror2018` |
| Difference of gains with cluster bootstrap | "small models benefit more" | tests the interaction directly | `efron1993bootstrap` |
| Kendall's τ-b, exact one-sided permutation p over 720 orderings | RQ4 ranking agreement | standard for benchmark agreement; exact with 6 items | `kendall1938`, `perlitz2024` |
| Spearman ρ, Pearson r, same exact p | RQ4 checks | rank and score agreement | `spearman1904`, `pearson1896` |
| Cohen's κ | judge vs reference grader | agreement beyond chance | `cohen1960`, `landis1977` |

- Judge validation: 96.0% agreement and κ = 0.919 with Claude Sonnet 5.5 on 198 answers.
- State the limit: the field validates judges against humans (LongMemEval, STALE).

## 3.8 Reproducibility

- Temperature 0 everywhere.
- Every call cached by a hash of provider, model, prompt, temperature and max tokens.
- A replicate tag separates the 3 runs.
- Provider pinning with no fallback.
- Run records hold the config, git commit and cost.
- Code and data released (say where).

---

# Part D. Reference cards

For each work: **what** it is, **how** it works, **reports** (key numbers), **say** (what the thesis should say about it), **DRIFT** (how DRIFT relates), **where** (sections). Check every number against the paper before using it.

## Memory systems

**MemGPT** `packer2023memgpt` (Packer et al., 2023, arXiv:2310.08560)
- **What:** an LLM agent that manages its own memory like an operating system.
- **How:**
  - *Main context* (the prompt: system instructions, an editable working context, a message queue) and *external context* (recall storage of all messages, archival storage searched by similarity).
  - The model moves data between them with function calls.
  - A memory-pressure warning makes it save information before old messages are evicted and summarised.
- **Reports:** Deep Memory Retrieval on Multi-Session Chat, 93.4% accuracy with GPT-4 Turbo against 35.3% for a recursive-summary baseline; single run.
- **Say:** outdated records stay in archival storage and stay searchable; nothing marks them as replaced.
- **DRIFT:** MemGPT behaves like P0 for changed facts. Zep later could not reproduce its result for lack of method detail, an argument for DRIFT's reproducibility.
- **Where:** 1.1, 2.1.

**Mem0** `chhikara2025mem0` (Chhikara et al., 2025, arXiv:2504.19413)
- **What:** a production memory layer.
- **How:**
  - *Extraction:* an LLM reads the newest message pair with a conversation summary and the last 10 messages.
  - *Update:* for each fact it retrieves the 10 most similar memories, and an LLM chooses ADD, UPDATE, DELETE or NOOP.
  - Graph variant Mem0g marks contradicted relations invalid instead of deleting them.
- **Reports:**
  - On LoCoMo: F1, BLEU-1, and an LLM-judge score J as the main metric (they argue F1 misleads on facts).
  - 26% relative J improvement over OpenAI's memory, 91% lower p95 latency, over 90% fewer tokens than full context.
  - **10 judge runs, mean ± 1 SD** (about 0.1 to 0.4), temperature 0.
- **Say:** Mem0 deletes or rewrites old facts by LLM decision; it measures accuracy and cost, not stale answers.
- **DRIFT:** P4 is in this spirit (LLM-decided removal). Mem0 is the precedent for repeated runs and for an LLM judge over F1.
- **Where:** 1.1, 1.2, 2.1, 2.2, 3.2.6, 3.5.

**Zep / Graphiti** `rasmussen2025zep`, `graphiti` (Rasmussen et al., 2025, arXiv:2501.13956)
- **What:** a temporal knowledge-graph memory.
- **How:**
  - Three layers: episodes (raw messages), entities and facts, communities.
  - **Bitemporal**: timeline T (when facts held) and timeline T′ (when the system created or expired them).
  - Extraction uses the current message plus the **previous 4 messages** as context, with a reflection step.
  - Contradictions: an LLM compares a new edge with related edges and sets t_invalid; nothing is deleted.
  - Retrieval combines cosine, BM25 and graph search, reranked by RRF, MMR or a cross-encoder; top results go in with their date ranges.
- **Reports:**
  - DMR 94.8% vs MemGPT 93.4%.
  - LongMemEval up to +18.5% accuracy and about 90% lower latency than full context; GPT-4o judge; single run.
  - Knowledge-update accuracy for gpt-4o-mini was slightly below full context.
- **Say:** Zep invalidates instead of deleting, and keeps invalidated facts available. It compares whole systems, not rules for what to do with invalidated facts.
- **DRIFT:** same data model. DRIFT's 4-line context comes from Zep, and its LLM-matching follow-up is Zep-style. DRIFT does not claim the mechanism.
- **Where:** 1.1, 1.2, 1.5, 2.1, 2.2, 3.1, 3.2.1.

**A-MEM** `xu2025amem` (Xu et al., 2025, arXiv:2502.12110)
- **What:** self-organising Zettelkasten-style memory.
- **How:**
  - Each note has content, timestamp, LLM keywords, tags, a context description, an embedding and links.
  - A new note links to its top-k similar notes.
  - "Memory evolution" lets an LLM rewrite neighbouring notes' descriptions.
- **Reports:** LoCoMo and DialSim, six models, F1 and BLEU-1 only; no variance.
- **Say:** memory is rewritten by an LLM as it grows; nothing tracks which version of a fact is current.
- **DRIFT:** related to P4 (LLM rewriting). Its evaluation shows the field's reliance on lexical metrics.
- **Where:** 1.1, 2.1.

**Generative Agents** `park2023generative` (Park et al., 2023, UIST)
- **What:** simulated characters with a memory stream.
- **How:** retrieval score = recency + importance + relevance, each min-max normalised, equal weights. Recency decays exponentially (0.995 per hour since last access); importance is rated by an LLM; relevance is cosine similarity.
- **Say:** the origin of hybrid, normalised retrieval scores with a recency term.
- **DRIFT:** DRIFT's weighted score of normalised signals follows the same pattern. DRIFT's recency uses valid time, not access time.
- **Where:** 2.1, 2.2, 3.2.3.

**Documentation sources** `langgraphdocs`, `lettadocs`, `mem0docs`, `xtdbdocs`, `openrouterdocs`
- **Say:** cite these only for current software behaviour that the papers do not describe:
  - LangGraph and Letta change records only on explicit overwrite;
  - XTDB is a production bitemporal database;
  - OpenRouter supports provider pinning and cost accounting.
- **Where:** 1.2, 2.4, 3.5, 3.8.

## Consolidation and write filtering

**Zhang et al. (2026)** `zhang2026faulty`, "Useful Memories Become Faulty When Continuously Updated by LLMs" (arXiv:2605.12978)
- **What:** a study of what happens when an LLM keeps rewriting a memory bank.
- **How:** experiences are consolidated into abstract lessons over many updates.
- **Reports:**
  - Utility first rises, then falls, and can drop below no memory.
  - A strong model that solved a set of ARC-AGI problems without memory failed many of them after consolidating from the correct solutions. The paper gives 46% in the main text and 54% in the abstract; check which to cite.
  - Causes: unrelated experiences grouped, conditions stripped by abstraction, overfitting to a narrow stream; results depend on update order.
- **Say:** LLM consolidation can destroy useful information. They recommend keeping raw evidence and gating consolidation.
- **DRIFT:** supports non-destructive closing and predicts P4's failure, which v3 measured (P4 is 52.6% sound on FactConsolidation, the least accurate memory policy there).
- **Where:** 2.3; Chapter 5.

**Xie et al. (2024)** `xie2024adaptive`, "Adaptive Chameleon or Stubborn Sloth" (ICLR 2024)
- **What:** how LLMs behave when the evidence in the prompt conflicts with what they learned in training.
- **Reports:** models are highly receptive to evidence in the prompt when it is coherent, even if it conflicts with their own knowledge. With mixed evidence they show confirmation bias.
- **Say:** whatever reaches the prompt strongly shapes the answer, so showing an outdated fact is risky.
- **DRIFT:** explains why exposure matters and why reading error is large for some models.
- **Where:** 2.3; Chapter 5 mechanism discussion.

**SAGE** `wang2026sage` (Wang, Brahma and Henao, 2026, arXiv:2605.30711)
- **What:** a novelty gate on writes.
- **How:**
  - Fact embeddings are normalised onto the unit sphere.
  - A von Mises-Fisher kernel density scores how well memory already covers a new fact.
  - An adaptive threshold routes it to NOOP (redundant), ADD (novel), or an LLM merge in an uncertainty band.
- **Reports:** on LoCoMo, best token F1 against Mem0 on seven open backbones; on GPT-4o-mini, **3.4×** lower write cost and 2.5× lower latency.
- **Say:** gating writes by novelty cuts cost.
- **DRIFT:** P3 is a simplified version (fixed cosine threshold 0.9). A correction looks redundant to such a gate, which v3 shows: P3 is 1% to 2% complete and the stalest gate.
- **Where:** 2.3, 3.3; Chapter 5.

## Temporal databases

**Snodgrass and Ahn (1985)** `snodgrass1985taxonomy`
- **What:** introduced the taxonomy of time in databases, separating valid time and transaction time. The term *bitemporal* for storing both became standard later, through Jensen et al.
- **Say:** the original source of the two timelines.
- **Where:** 1.2, 2.4, 3.1.

**Snodgrass (1999)** `snodgrass1999developing`
- **What:** a book on building time-oriented applications in SQL.
- **Say:** shows how periods are closed rather than rows deleted.
- **Where:** 1.2, 2.4.

**Jensen et al. (1998)** `jensen1998glossary`
- **What:** the consensus glossary of temporal database terms.
- **Say:** cite for exact definitions of valid time and transaction time.
- **Where:** 1.2, 2.4.

**Kulkarni and Michels (2012)** `kulkarni2012sql2011`
- **What:** temporal features added in SQL:2011: application-time and system-versioned periods.
- **Say:** bitemporal storage is standardised and in production databases.
- **Where:** 1.2, 2.4.

## Staleness and memory revision

**Du (2026)** `du2026memory`, "Memory for Autonomous LLM Agents" (survey, arXiv:2603.07670)
- **What:** a survey framing memory as a write, manage, read loop.
- **How:** a taxonomy by temporal scope, representation and control policy, plus an evaluation "metric stack": utility, efficiency, adaptivity, faithfulness.
- **Reports (open challenges):** continual consolidation, causally grounded retrieval, trustworthy reflection, **learned forgetting**, multimodal memory.
- **Say:** forgetting is an acknowledged open problem.
- **DRIFT:** answers the forgetting part with a controlled comparison; its cost metrics match the efficiency layer.
- **Where:** 1.1, 2.5; Chapter 6 future work.

**STALE** `chao2026stale` (Chao et al., 2026, arXiv:2605.06527)
- **What:** a benchmark for *implicit* conflicts, where new information invalidates an old memory without saying so.
  - Type I: same attribute, e.g. a new lease in Portland implies the user no longer lives in Seattle.
  - Type II: cascading, e.g. a broken leg invalidates a cycling commute.
- **How:** 400 scenarios, 1,200 queries, contexts up to 150K tokens, three probes (state resolution, premise resistance, policy adaptation). Gemini judge validated against humans at 95.8%.
- **Reports:** best model 55.2% overall; agents retrieve the update but fail to act on it.
- **Say:** staleness is a recognised failure even for strong models.
- **DRIFT:** STALE tests whether the *model* notices; DRIFT tests whether *memory* keeps stale facts away. STALE classes FactConsolidation as explicit conflicts only, which fixes DRIFT's scope.
- **Where:** 1.1, 2.5, 3.4 (scope), 3.7 (judge validation).

**Supersede** `patel2026supersede` (Patel, 2026, arXiv:2606.27472)
- **What:** the "supersession gap", the accuracy lost when an agent answers from a bounded, self-maintained memory instead of full history.
- **How:** a programmatic matcher: r_cur = 1 if the answer gives the current value; r_stale = −1 if it **asserts a superseded value**. Paired McNemar test, temperature 0.
- **Reports:** on LongMemEval knowledge updates, gpt-5.4 drops from 92% (full context) to 77% (bounded memory), p = 0.0033. GRPO fine-tuning of a 3B model raises held-out accuracy from 9.0% to 16.7%.
- **Say:** the closest prior definition of a stale answer.
- **DRIFT:** same staleness definition and the same paired test. DRIFT adds the mentions vs asserts split and fixes the problem in memory rather than by training the model.
- **Where:** 1.2, 2.5, 3.6, 3.7.

## Benchmarks

**LoCoMo** `maharana2024locomo` (Maharana et al., 2024, ACL)
- **What:** very long conversations generated by LLM agents with personas and event graphs, then edited by humans.
- **How:** 50 conversations of about 300 turns and 9K tokens, up to 35 sessions. QA in five categories (single-hop, multi-hop, temporal, open-domain, adversarial); F1 with partial match.
- **Say:** the standard long-memory benchmark, used by Mem0, A-MEM and SAGE.
- **DRIFT:** no question records a replaced answer, so it cannot score staleness. Excluded, and shown in Table 2.1.
- **Where:** 1.5, 2.5, Table 2.1.

**LongMemEval** `wu2025longmemeval` (Wu et al., 2025, ICLR)
- **What:** 500 curated questions over five abilities, including **knowledge updates** and abstention.
- **How:**
  - S version about 115K tokens; M version 500 sessions.
  - Memory as indexing, retrieval and reading.
  - Storing per round and expanding keys with extracted facts help.
  - GPT-4o judge with more than 97% agreement with humans.
- **Say:** the strongest judge-validation practice in the field.
- **DRIFT:** knowledge-update questions record only the new answer, so staleness cannot be scored. Its human-validated judge is the standard DRIFT's judge check falls short of.
- **Where:** 1.5, 2.5, Table 2.1, 3.7.

**MQuAKE / MQuAKE-T** `zhong2023mquake` (Zhong et al., 2023, EMNLP)
- **What:** a knowledge-editing benchmark.
- **How:**
  - An edit is e = (s, r, o → o*): same subject and relation, new object.
  - MQuAKE-T has 1,868 instances of real Wikidata changes.
  - Their method, MeLLo, stores edits in external memory and lets the model check whether a retrieved edit contradicts its answer.
- **Say:** gives DRIFT its definition of supersession and its cleanest benchmark.
- **DRIFT:** 96 single-hop questions derived from MQuAKE-T, every one about a changed fact.
- **Where:** 1.2, 1.5, 2.5, 3.1, 3.4.

**MemoryAgentBench / FactConsolidation** `hu2026memoryagentbench` (Hu, Wang and McAuley, 2026, ICLR)
- **What:** a benchmark of four memory competencies, including **selective forgetting**.
- **How:**
  - FactConsolidation concatenates true facts with rewritten contradictory versions, in single-hop and multi-hop versions of several lengths.
  - Agents are told to prefer later information.
  - Scored by substring exact match.
- **Reports:** all methods fail multi-hop (at most 28%).
- **Say:** the source of DRIFT's counterfactual benchmark. Its counterfactual answers cannot come from what a model learned in training.
- **DRIFT:** uses the 6K single-hop version (100 questions, 65 with an old value) and deliberately does *not* tell the model to prefer later facts.
- **Where:** 1.5, 2.5, 3.2.5, 3.4.

**ConvoMem** `pakhomov2025convomem` (Pakhomov, Nijkamp and Xiong, 2025, arXiv:2511.10523)
- **What:** a large conversational memory benchmark: 75,336 QA pairs over user facts, preferences, temporal changes and more.
- **Reports:** full context reaches 70% to 82% while RAG-style memory such as Mem0 reaches 30% to 45% on histories under 150 conversations.
- **Say:** changes stated in natural dialogue, the hardest setting for extraction.
- **DRIFT:** uses 100 changing-fact questions over 10 conversations. Their finding that RAG memory struggles foreshadows DRIFT's extraction-bound ConvoMem result.
- **Where:** 1.5, 2.5, 3.4.

## Multi-agent memory

**G-Memory** `zhang2025gmemory` (Zhang et al., 2025, NeurIPS)
- **What:** hierarchical memory for multi-agent systems.
- **How:** three graphs: insights, queries, and interactions between agents.
- **Reports:** up to 20.89% higher success on embodied tasks and 10.12% on knowledge QA, across five benchmarks and three agent frameworks.
- **Say:** shared memory improves team performance.
- **DRIFT:** measures task success only, not what happens to outdated facts.
- **Where:** 2.6.

**Collaborative Memory** `rezazadeh2025collaborative` (Rezazadeh et al., 2025, arXiv:2505.18279)
- **What:** memory shared between multiple users and agents under access control.
- **How:**
  - Private and shared memory fragments.
  - Permissions as bipartite graphs that change over time.
  - Every fragment carries provenance (which agent, which resources, when).
- **Say:** shared memory needs provenance and permissions.
- **DRIFT:** DRIFT records provenance (which agent wrote a fact) for the same reason; it studies freshness, not permissions.
- **Where:** 2.6.

**GateMem** `ren2026gatemem` (Ren et al., 2026, arXiv:2606.18829)
- **What:** a benchmark for memory shared by several people with different roles (medical, office, education, household).
- **How:** 91 episodes, 2,218 hidden checkpoints. Three dimensions: utility, access control, and *active forgetting* (information deleted on request must not be recovered). GPT-4o judge checked against human annotation.
- **Reports:** no method is strong on all three; long context governs best but costs the most.
- **Say:** the closest work to RQ4's setting.
- **DRIFT:** GateMem measures governance; DRIFT measures whether forgetting-policy rankings transfer. Its "active forgetting" is the closest prior idea to DRIFT's completeness.
- **Where:** 1.2, 2.6, 3.3.

**Governed Shared Memory** `margalit2026governed` (Margalit et al., 2026, arXiv:2606.24535)
- **What:** systems design for memory shared by a fleet of agents.
- **How:**
  - Names four failure modes: unauthorised leakage, **stale propagation**, **contradiction persistence**, provenance collapse.
  - Proposes scoped retrieval, temporal supersession, provenance tracking and governed propagation, implemented in a production service.
- **Say:** shared memory makes staleness spread and contradictions persist.
- **DRIFT:** DRIFT measures two of these failure modes. Stale answers under P0 roughly double in shared memory, and contradictions survive more often. Its abstract reports that a near-duplicate gate can reject a contradictory write before the contradiction detector sees it: the same failure as P3, found in a production system.
- **Where:** 1.2, 2.6, 3.6; Chapter 5.

**Yu et al. (2026)** `yu2026multiagent`, "Multi-Agent Memory from a Computer Architecture Perspective" (arXiv:2603.10062)
- **What:** a position paper treating multi-agent memory as a computer-architecture problem.
- **How:** shared vs distributed memory, a three-layer hierarchy, and consistency models borrowed from multiprocessors.
- **Reports:** names memory consistency as the most pressing open challenge.
- **Say:** keeping agents' views of memory consistent is open.
- **DRIFT:** RQ4 is an empirical look at one part of it: whether a forgetting rule keeps shared memory fresh.
- **Where:** 2.6; Chapter 6.

## Retrieval and embeddings

**Nomic Embed** `nussbaum2024nomic` (Nussbaum et al., 2024, arXiv:2402.01613)
- **What:** an open, reproducible long-context text embedding model.
- **Say:** chosen because it is open and runs locally, so retrieval adds no API cost and is reproducible.
- **Where:** 2.2, 3.2.3.

**BM25** `robertson2009bm25` (Robertson and Zaragoza, 2009)
- **What:** the standard lexical ranking function; it weights rare words more and saturates repeated words.
- **Say:** the lexical signal in Zep and in many retrieval baselines.
- **DRIFT:** DRIFT's word-overlap signal is BM25 without rarity weighting. A pilot found the two identical under P2 and about 10% apart under P0 for Llama.
- **Where:** 2.2, 3.2.3; Chapter 4.

**Reciprocal Rank Fusion** `cormack2009rrf` (Cormack, Clarke and Buettcher, 2009, SIGIR)
- **What:** combines rankings by summing 1 / (60 + rank) over signals; no weights to tune.
- **Say:** the usual way to combine signals on different scales; used by Zep.
- **DRIFT:** the weight-free alternative in the follow-up. It was within about 1.5% of 0.6/0.3/0.1 on every benchmark.
- **Where:** 2.2, 3.2.3, 3.5.

## Models

| Key | Model | Source to cite | Where |
|---|---|---|---|
| `openai2026gpt61sol` | GPT-6.1 Sol | launch page; its system card is an addendum to GPT-6 Astra's | 3.5, Table 3.4 |
| `anthropic2026sonnet55` | Claude Sonnet 5.5 | product page and system card | 3.5, Table 3.4 |
| `google2026gemini38flash` | Gemini 3.8 Flash | model card | 3.5, Table 3.4 |
| `grattafiori2024llama3` | Llama 3.1 8B | "The Llama 3 Herd of Models" | 3.5, Table 3.4 |
| `yang2025qwen3` | Qwen3 14B | Qwen3 Technical Report | 3.5, Table 3.4 |
| `deepseek2026v41flash` | DeepSeek V4.1 Flash | technical report | 3.2.1, 3.2.6, 3.5 |

- Cite each once (in the table or at first mention).
- Give the model ID, provider, reasoning setting and run dates.

## Statistics

| Key | What it is | Say | Where |
|---|---|---|---|
| `mcnemar1947` | Test for paired yes/no outcomes using only the discordant pairs | the correct test when two policies answer the same questions | 3.7, Ch 4 |
| `dietterich1998` | Compares tests for comparing classifiers | recommends McNemar for this setting | 3.7 |
| `holm1979` | Step-down correction for many tests | controls false positives across 30 comparisons, less conservative than Bonferroni | 3.7, Ch 4 |
| `efron1993bootstrap` | Resampling to get confidence intervals | intervals without assuming a distribution | 3.7, Ch 4 |
| `dror2018` | Significance testing practice in NLP | supports paired tests and the bootstrap in NLP evaluation | 3.7 |
| `kendall1938` | Rank correlation τ | main RQ4 statistic | 3.7, Ch 4 |
| `perlitz2024` | Benchmark agreement testing (BenchBench) | precedent for comparing rankings with rank correlation | 3.7, Ch 5 |
| `spearman1904` | Rank correlation ρ | RQ4 check | 3.7 |
| `pearson1896` | Linear correlation r | compares scores, not order | 3.7 |
| `cohen1960` | Agreement beyond chance, κ | judge validation | 3.7 |
| `landis1977` | How to read κ (above 0.8 = almost perfect) | interpret 0.919 | 3.7 |
| `kendall1939` | Kendall's W, concordance of many rankings | cite only if you report W | optional |

## Also add

**RAG** `lewis2020rag` (Lewis et al., 2020, NeurIPS)
- **What:** retrieval-augmented generation: retrieve documents, then generate from them.
- **Say:** the basic pattern of vector-memory systems.
- **Where:** 1.1 or 2.1, wherever you mention RAG.
