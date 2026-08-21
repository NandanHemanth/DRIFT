# Thesis Defense Preparation: DRIFT

A complete question-and-answer preparation guide for defending "DRIFT: Decay Rates in Forgetful Bitemporal Memory." Read this end to end at least once, then use the section headers to drill the areas you feel least solid on.

---

## Part 1: How the defense itself will go

A master's thesis defense at a US institution like Stevens typically runs as follows. Confirm the exact format with your advisor, since department practice varies, but the shape below is standard.

**Format.** A committee of two to three people (in your case: Dr. Hao Wang as advisor, Dr. Joseph Helsing as reader, possibly a chair). The defense usually runs 45 to 60 minutes total: a 20 to 30 minute presentation, followed by 20 to 40 minutes of questions. Some programs open the room to other students or faculty for the presentation, then ask non-committee members to leave for a closed questioning period.

**Sequence.** Advisor introduces you and the committee. You present. The committee asks questions, usually going deepest on the parts of the thesis closest to their own expertise. Your advisor (Dr. Wang) will very likely ask fewer adversarial questions than your reader, since his job during the defense is mostly to make sure you get a fair hearing, not to test you as hard as the reader will. After questions, you are asked to step out while the committee deliberates, then brought back in for the result (pass, pass with minor revisions, pass with major revisions).

**What they are actually evaluating.** Not whether your results are perfect. They are evaluating whether you understand your own work deeply enough to have done it yourself, whether you understand its limitations as well as its contributions, and whether you can think on your feet when someone pokes at an assumption. A confident "here is a real limitation of this work, and here is why I don't think it undermines the main claim" answers far better than pretending there are no weaknesses.

**Practical tips that come up repeatedly in advice from people who have been through this:**
- Prepare a 2 to 3 sentence summary of the whole thesis you can say without slides, for when someone asks "so what did you actually do" cold.
- Don't be modest about your contributions during the presentation itself; state them plainly. Save the humility for the limitations section.
- If you don't know an answer, say so directly and reason about it out loud from what you do know, rather than guessing confidently. Committees respect "I don't know, but here's how I'd find out" far more than a fumbled invention.
- Anticipate that the reader will focus disproportionately on whatever they consider their own area, and will probe your weakest section hardest. For this thesis, that is very likely to be Section 10 (Threats to Validity) and the RQ4 status (multi-agent, offline-only) — see Part 5 below, prepare that section hardest.
- It is completely normal to be nervous. It does not read as unprepared; everyone in the room has been through this themselves.

Sources: [The Thesis Defense (UAB)](https://www.uab.edu/cas/art/images/documents/forms-resources/The-Thesis-Defense.pdf), [MIT Math Thesis Defense](https://math.mit.edu/academics/grad/timeline/defense.html), [BeMo: 40 Thesis Defense Questions](https://bemoacademicconsulting.com/blog/thesis-defense-questions), [VivaCoach: CS Defense Questions](https://vivacoach.ai/defense-questions/computer-science)

---

## Part 2: The 3-sentence version (memorize this)

If someone asks "what is your thesis about" cold, in an elevator, this is your answer:

> "AI agents that remember things over long periods of time eventually accumulate facts that are no longer true — someone moves, a job changes, a country gets a new president — and the agent keeps answering from the old fact because nothing tells the memory to forget it. My thesis builds a framework called DRIFT that holds everything else about an AI agent's memory system fixed and only changes the rule for what gets forgotten, so that for the first time you can measure, rather than assume, which forgetting strategy actually works. The headline finding is that a specific strategy — invalidating a fact only when it's actually been contradicted, using a bitemporal data structure — gets you the same accuracy as never forgetting anything, but at 12% lower cost, while every other forgetting strategy people currently use in production systems either doesn't save you anything or actively makes the agent wrong more often."

Practice saying this without reading it. Everything else in this document is elaboration on pieces of this paragraph.

---

## Part 3: Why — the problem and the motivation

**Q: Why does this problem matter? Give me a concrete example.**

An assistant is told "I live in Boston." Three months later it's told "I moved to Seattle." Both facts sit in memory. When later asked "where do I live," a retrieval system ranks by semantic similarity and recency — both facts are relevant, both mention "live" and a city, so both often get pulled into context. The model then has to pick, and sometimes picks the stale one. This isn't a retrieval bug — the correct fact was found — it is a failure of memory *hygiene*: nothing in the system ever marked the old fact as no longer current.

This compounds with time. An agent running for a year accumulates thousands of facts, an increasing fraction superseded. Every stale fact retrieved is context spent on misinformation; every one that reaches the final answer is a confidently wrong statement about something the user told the agent themselves.

**Q: Isn't this just a retrieval problem? Why not just build a better retriever?**

Because the retriever is working correctly by its own definition — it found the two most relevant memories. The problem is upstream: the system never decided what to do with a fact once it's been contradicted. You can have perfect retrieval and still surface a stale fact, because "relevant" and "current" are different properties, and only one of them is what retrieval optimizes for. This is exactly why DRIFT holds retrieval fixed and varies only the forgetting policy — to isolate that the effect is coming from the write/retention side, not the retrieval side.

**Q: Why hasn't someone already solved this?**

Production memory systems (MemGPT, Zep, Mem0, A-MEM) all focus on the storage and retrieval halves of the problem — how to structure memory, how to search it efficiently. Where a forgetting mechanism exists at all in these systems, it was chosen by the system's authors, not measured against alternatives. The reason nobody has done a controlled comparison is partly methodological: if you compare two published memory systems and one forgets better than the other, you can't tell whether that's because of the forgetting rule or because the two systems also differ in their substrate, retrieval function, extraction step, and underlying model. Four confounds stacked on top of the one variable you actually wanted to test. DRIFT's contribution is holding those four things fixed so the forgetting rule is the only thing that changes.

**Q: What is your hypothesis, precisely?**

> H: Selective forgetting grounded in bitemporal structure improves an agent's answer quality and cost profile relative to both append-only memory (never forgetting) and to structure-blind or novelty-based forgetting.

**Q: What are your research questions?**

- RQ1: Does append-only memory (never forgetting anything) measurably surface superseded facts? (Establishes the problem is real, not hypothetical.)
- RQ2: Which forgetting policy offers the best accuracy/staleness/cost trade-off?
- RQ3: Does bitemporal structure specifically outperform structure-blind graph-based alternatives, or would any graph-aware consolidation do?
- RQ4: Do the policy rankings established with one agent survive when multiple agents read and write the same memory?

---

## Part 4: What — the framework, the substrate, the policies

**Q: What is a "bitemporal" knowledge graph, in plain terms?**

Every fact your agent learns is stored as a subject-predicate-object triple (e.g., "head_of_government(France) = Macron") plus **two independent timelines**:
1. **Valid time** — the period during which the fact was actually true in the world (when did Macron become president, when did he stop being president, if ever).
2. **Ingestion time** — when the agent itself learned the fact, which can be completely different from valid time (you might be told about a change days after it happened).

Keeping these two timelines separate is what "bitemporal" means (it's a decades-old idea from database research — DRIFT's novelty is not inventing bitemporal modeling, it's what the novelty section covers below). A fact also carries a `t_pruned` field: when a *policy* removed it, separate from when it stopped being valid. This is the key design decision: **contradiction closes a fact's valid-time window automatically and non-destructively.** The fact stays in the graph and is still technically retrievable. Only a *policy* actively deletes or hides data. This guarantees that any difference you measure between two experimental conditions is attributable to the policy, not to some accidental difference in how the substrate handles contradictions.

**Q: Walk me through the full pipeline, start to finish.**

```
session text (raw conversation lines)
    -> extract_facts()          LLM pulls out (subject, predicate, object) triples,
                                  plus a deterministic regex upgrade for known
                                  "functional" predicates so contradiction detection
                                  doesn't depend purely on extractor luck
    -> policy.on_write()        the policy's write gate: can reject a write outright
                                  (this is where a novelty gate would reject a
                                  near-duplicate correction, for example)
    -> BitemporalGraph          if the new fact contradicts an existing one on a
                                  "functional" predicate (one that only has one true
                                  value at a time), the old fact's valid-time window
                                  is closed -- non-destructively
    -> policy.after_session()   periodic maintenance: TTL pruning, LLM consolidation,
                                  whatever the policy does between sessions
    -> graph.search()           hybrid retrieval: 0.6 cosine similarity + 0.3 lexical
                                  overlap + 0.1 recency, top k=25
    -> policy.on_retrieve()     the policy's retrieval filter/rerank hook (this is
                                  where P2 excludes facts whose valid window has closed)
    -> answer model              produces the final answer given the retrieved memory
    -> LLM judge (different      scores CORRECT/INCORRECT against the gold answer;
       model family) + token-F1  token-F1 is a second, judge-independent metric
```

**Q: What exactly is a "policy" in your framework, mechanically?**

A policy is a Python class with exactly three hooks:

```python
class Policy:
    def on_write(self, fact, graph) -> bool: ...        # False rejects the write
    def after_session(self, graph, provider, now): ...   # periodic maintenance
    def on_retrieve(self, facts, now) -> list: ...        # filter or rerank
```

That's the entire interface. Adding a new policy to the framework is a subclass plus one line registering it — the runner, the substrate, the providers, and the analysis code never need to know a new policy exists. This is deliberate: it's what makes the claim "DRIFT is a general harness, not a one-off experiment" true in a checkable way rather than an assertion.

**Q: List and explain all seven policies. Be ready to explain each one's mechanism in one sentence.**

| ID | Name | Mechanism (one sentence) |
|---|---|---|
| NOMEM | No memory | Retrieval always returns nothing — the floor baseline; measures what the model can do from its own parametric knowledge alone with an instruction to say "I don't know" if memory can't answer |
| P0 | No forgetting | Append-only. Nothing is ever gated, pruned, or filtered — the ceiling baseline |
| P1 | TTL decay | Prune any fact older than a fixed number of days, measured by *valid* time, regardless of whether it's still true |
| P2 | Bitemporal contradiction invalidation | Exclude facts whose valid-time window has closed at *retrieval* time; physically prune them after a 7-day grace period — this is the policy the thesis recommends |
| P3 | Novelty gate | At write time, reject any candidate fact whose embedding is too similar (cosine > 0.9) to something already in memory — models the "SAGE" technique from recent literature |
| P4 | LLM consolidation | Every third session, ask an LLM to decide keep-or-drop for each fact, plus a deterministic near-duplicate merge |
| P5 | Topology consolidation | Structure-aware but **deliberately denied valid-time information** — when two facts conflict, keep whichever one has more corroborating mentions elsewhere in the graph. This exists purely as an ablation partner to P2 (see Part 6, RQ3) |

**Q: Why NOMEM and not just start from P0?**

Because NOMEM tells you how much of the model's apparent "knowledge" is actually coming from memory versus from what the model already knows parametrically. On both fact benchmarks NOMEM scores exactly 0.000 accuracy, which tells you the datasets are designed so the model cannot guess the answer without consulting memory — this is a *validity check* on the benchmarks as much as it is a baseline.

**Q: What does "functional predicate" mean and why does it matter so much?**

A functional predicate is one that only ever has one true value at a given moment — "head_of_state(France)" can only be one person at a time, so a new value necessarily contradicts and supersedes the old one. Non-functional predicates (like "visited(France)") can have many simultaneously-true values and shouldn't trigger contradiction logic. You have to *tell* the substrate which predicates in your domain are functional — this is the single configuration setting that determines whether P2's contradiction mechanism has anything to act on at all. Section 6.8 (the ablation) exists entirely to quantify what happens if you get this wrong: see Part 6 below.

**Q: Why is contradiction-closing "non-destructive" — why not just delete the old fact immediately?**

Two reasons. First, methodologically: if closing a contradiction also deleted data, you couldn't tell whether an observed effect came from the *substrate's* behavior or from a *policy's* behavior, because there'd be no experimental condition where the old fact was still available to retrieve. Keeping it non-destructive means the substrate behaves identically across every policy, and only the policy decides whether to actually act on the closed window. Second, practically: it's what makes NOMEM-style policies, replay/audit tooling, and "what did the agent believe at time T" queries possible — you can reconstruct the agent's belief state at any past moment, which matters for debugging and for right-to-be-forgotten/audit use cases (discussed in Part 8).

---

## Part 5: Novelty — what is actually new here

Be very precise about this if asked "what's new, since bitemporal databases have existed for decades." The novelty is **experimental design**, not the data structure.

**N1 — the forgetting policy as an isolated independent variable.** As far as this thesis is aware, this is the first study that holds substrate, extraction, retrieval, answer model, and judge fixed and varies *only* the forgetting rule, across a taxonomy from no-memory through append-only through five distinct forgetting strategies. Every prior comparison in the literature confounds the forgetting rule with several other design choices at once, because it's comparing different whole systems (MemGPT vs. Zep vs. Mem0), not different forgetting rules on top of the same system.

**N2 — the P2-versus-P5 ablation isolates *bitemporal* semantics specifically, not "graph structure" in general.** This is the single most important design decision in the thesis, and you should be ready to explain why it matters unprompted. Without P5, if P2 (bitemporal) beats a flat baseline, a skeptical reader can say "sure, but *any* structure-aware consolidation would probably do that — you haven't shown it's specifically the temporal reasoning that helps." P5 closes that gap: it's built to be *exactly* as structure-aware as P2, operating on the same graph, doing the same kind of consolidation — the *only* difference is P5 is deliberately denied access to valid-time information and has to infer currency from corroboration count instead. When P2 beats P5 by a wide, statistically significant margin, that specifically isolates temporal reasoning as the source of the advantage, not graph-awareness in general.

**N3 — novelty gating identified and measured as a named failure mode.** Write-side novelty gating (reject a write if it looks too similar to something already stored) is currently promoted in the literature as a pure efficiency win. This thesis gives the first controlled demonstration that on any workload where facts get corrected over time, a novelty gate trades a *bounded* memory saving for an *unbounded* correctness liability — and demonstrates the actual mechanism from saved knowledge-graph snapshots, not just from aggregate statistics. This claim is explicitly argued to generalize beyond this thesis's own implementation, because it follows from the *definition* of a novelty gate and the textual structure of a correction, not from any implementation detail (see Part 6, RQ2/novelty gating).

**N4 — a negative result about the field's standard benchmarks.** The two most commonly used agent-memory benchmarks, LoCoMo and LongMemEval, turn out to carry **zero** annotations of what the "stale" answer to a question would be. Discovering this (the hard way — see Part 9, "what went wrong") and finding two benchmarks that do support the measurement is itself presented as a contribution, because it's a trap available to anyone else trying to measure memory revision on those benchmarks.

---

## Part 6: Results — know every number in the headline table cold

**The headline table** (pooled across both answer models; percentile bootstrap 95% CIs, 5,000 resamples; n=200 on FactConsolidation, n=192 on MQuAKE-T):

| Policy | FC accuracy | MQuAKE-T accuracy | FC staleness | MQuAKE-T staleness | FC tok/q | MQ tok/q |
|---|---|---|---|---|---|---|
| NOMEM | 0.000 | 0.000 | 0.000 | 0.000 | 250 | 233 |
| **P0** | **0.840** | **0.969** | 0.030 | 0.052 | 812 | 816 |
| P1 (TTL 20d) | 0.630 | 0.870 | 0.020 | 0.026 | 799 | 807 |
| **P2** | **0.840** | **0.969** | 0.025 | 0.036 | **715** | **716** |
| P3 | 0.665 | 0.792 | 0.140 | 0.161 | 806 | 805 |
| P4 | 0.800 | 0.953 | 0.060 | 0.057 | 814 | 804 |
| P5 | 0.795 | 0.802 | 0.035 | 0.214 | 812 | 816 |

**Q: RQ1 — does append-only memory actually surface stale facts? Prove it.**

Yes. P0's staleness is 0.030 [CI 0.010, 0.055] on FactConsolidation and 0.052 [CI 0.021, 0.089] on MQuAKE-T — both intervals exclude zero, so this isn't noise. More concretely: averaged over its retrievals, P0 surfaces **4.20 superseded facts per question** on FactConsolidation and **4.80** on MQuAKE-T, out of a retrieval depth of k=25. That's the mechanism made visible, not just the downstream symptom.

**Q: RQ2 — which policy wins, and how confident are you?**

P2. And the way to state the accuracy result precisely matters: it is **not** "P2 has no accuracy loss because we failed to detect one" (a null result). It's an **equivalence claim**: the paired-bootstrap 95% confidence interval on the P2-minus-P0 accuracy difference is [-0.025, +0.025] on FactConsolidation and [-0.021, +0.021] on MQuAKE-T. Both intervals are narrow and centered on zero. That means we can say with statistical confidence that the true difference, whatever it is, is *small* — not just that we couldn't rule out zero. On top of matching P0's accuracy, P2 spends 12% fewer tokens per question and stores 6.5–14.7% fewer facts than P0. No other policy achieves both: P1 stores far less but loses 21–10 points of accuracy; P3 and P5 shrink memory modestly but lose accuracy and gain staleness; P4 is close on accuracy but saves nothing.

**Q: What's a paired bootstrap and why does it matter more than comparing two confidence intervals?**

If you just look at whether P0's CI and P2's CI for accuracy overlap, that's a weak test, because it ignores the fact that both policies were scored on the *exact same questions*. A paired bootstrap resamples the *per-question differences* directly (P2's answer minus P0's answer, question by question), which uses that shared structure and gives a tighter, more correct estimate. This is what lets you say "bounded within ±2.5 points" instead of just "not statistically distinguishable."

**Q: RQ3 — this is your strongest result. Explain the P2-vs-P5 comparison in full, including the mechanism.**

On MQuAKE-T: P2 gets 0.969 accuracy, P5 gets 0.802 — a paired delta of +0.167 [CI +0.109, +0.224], McNemar 34-to-2 discordant pairs, p < 0.001. Staleness: P2 is 0.036, P5 is 0.214 — nearly 6x worse, p < 0.001. **The mechanism**: P5 resolves a conflict between two competing facts by picking whichever one has more corroborating mentions elsewhere in the memory graph. A head of state who has served for eight years simply *appears* in more sessions, more incidental mentions, more co-occurrences than a successor who took office last month — so corroboration count is systematically biased toward whoever has held the office longer, which is exactly backwards when what you want is whoever holds it *now*. Real example from the data: asked who the head of state of South Korea is, P5 answers "Moon Jae-in" (the *previous* president, more corroborated) while P2 correctly answers "Yoon Suk-yeol" (the *current* president, per the bitemporal valid-time window). The general lesson, stated precisely: **structural corroboration measures how established a fact is, not whether it's current** — those two properties are the same for stable facts and diverge exactly for facts under revision, which is the one case a forgetting policy exists to handle.

**Q: Why is this result sharper on MQuAKE-T than on FactConsolidation?**

On FactConsolidation, the same P2-vs-P5 comparison is p=0.022 on accuracy and inconclusive on staleness (p=0.727). FactConsolidation's entities are arbitrary Wikidata pairs whose corroboration is roughly uniform across the corpus — so P5's heuristic fails close to randomly, a small noisy effect. MQuAKE-T's entities are real people holding real public offices, so corroboration is *systematically* biased toward whoever has held the office longer — P5 fails in a *consistent direction*, not randomly. Getting a second benchmark didn't just replicate the finding, it exposed *why* it happens.

**Q: RQ2 continued — explain the novelty-gating (P3) failure in full.**

P3 shows 4.7x P2's staleness on FactConsolidation (0.140 vs 0.025) and 4.5x on MQuAKE-T (0.161 vs 0.036), both p < 0.001. **The mechanism is structural, not statistical**: a correction to a fact is, by construction, textually near-identical to the fact it corrects — "Thomas Kyd was born in the city of London" versus "...in the city of Leeds" differ by one word. A novelty gate computes cosine similarity between an incoming fact and its nearest neighbors already in memory; a correction registers as a near-duplicate and gets *rejected at write time*. The correction never enters memory at all. No amount of smarter retrieval, reranking, or prompting downstream can recover a value that was never stored in the first place, because the failure happens before any of those mechanisms have anything to work with. This was verified directly from saved knowledge-graph snapshots (not just inferred from aggregate numbers): on MQuAKE-T, 31 write rejections produced 14 specific questions P3 answered wrong from a stale value that P0 got right, including things like the UK head of state still showing "Elizabeth II" after her death, because the correction to "Charles" was rejected as a near-duplicate.

**Q: Is the novelty-gating failure specific to your implementation, or does it generalize?**

It generalizes, and this is an important distinction to be able to draw under questioning. It follows from two facts that are true of *any* novelty gate, not just this one: (1) a correction is, by definition, a minimal edit of the thing it corrects, and (2) a novelty gate's entire decision criterion is textual/embedding similarity. Those two facts alone guarantee the gate's discriminative signal is inversely aligned with the case that matters most. Lowering the similarity threshold doesn't fix it either — it just changes how many genuine duplicates also get admitted; it can never distinguish a correction from a restatement because the two are textually indistinguishable at the embedding level. Distinguishing them requires structure the gate doesn't consult (same subject and predicate, different object) — which is exactly the bitemporal contradiction test P2 does and P3 doesn't.

**Q: Does the ranking hold across both benchmarks? If not, where does it break?**

Mostly yes — Spearman's rho on the full 7-policy ranking across both benchmarks is 0.891. The top (P0, P2) and bottom (P3, NOMEM) are completely stable. The one policy that moves substantially is **P1 (TTL decay)** — rank 6 on FactConsolidation, rank 4 on MQuAKE-T, a two-place jump. This is explained, not just observed: on MQuAKE-T, *100%* of questions concern a fact that changed, so TTL-pruning old facts is nearly always safe — you're removing things that are (by construction) already superseded. On FactConsolidation, only 65% of questions are about updates; the other 35% are stable facts that TTL destroys indiscriminately by age. **P1's rank is a property of the workload's update ratio, not an intrinsic property of TTL as a policy** — and this is presented as a feature of the study, not a weakness: it's the cleanest demonstration that you can't answer "which policy is best" in the abstract, only "which policy is best for a given workload," which is the thesis's whole practical recommendation.

---

## Part 7: The two methodological findings (these show rigor — lead with them if asked "what are you most proud of")

**The configuration ablation (Section 6.8).** `functional_predicates` — the setting that tells the substrate which predicates are single-valued — was declared for MQuAKE-T based on looking at that dataset, which is itself a threat to external validity worth naming proactively. So the thesis reran MQuAKE-T with the setting left at its substrate default (which covers none of MQuAKE-T's actual relations). Result: graph invalidations dropped from 59 to 1 — the contradiction mechanism essentially switched off. But **P2's accuracy stayed at 0.969 either way** — identical. Only the efficiency numbers moved: token cost per question rose 14.4% (641 → 733) and active fact count rose 7.0% (357 → 382) when the setting was wrong. **The finding, stated precisely: the setting buys P2 none of its accuracy and all of its efficiency.** This decomposes into a genuinely useful engineering claim: P2 is safe to turn on without tuning (misconfiguring it degrades gracefully to append-only behavior, never below it), but it only pays for itself in cost savings if you've correctly declared your domain's functional predicates. That's a specific, falsifiable, actionable instruction — not a vague "your mileage may vary."

**The judge-reliability audit (Section 6.9) — this is the finding that shows the most intellectual honesty; expect a question about it.** While reconciling the ablation run against the main run, an unexpected discrepancy turned up: the ablation's P0 cell produced 96 out of 96 **byte-identical** answers to the main run's P0 cell — and yet was scored 0.844 versus the main run's 0.969. Same exact text, different grade. Investigating: 12 judge verdicts had flipped, all in the same direction, on answers where the literal correct string appeared verbatim in the answer but the judge marked it INCORRECT anyway (example: asked for Australia's head of government, the answer literally says "Anthony Albanese," judged incorrect). Auditing every cell for this pattern (verbatim-correct-but-judged-incorrect) found a baseline false-negative rate of 1–2% across most cells, but one specific cell got unlucky with a rotating three-provider judge fallback pool and lost 12.5 accuracy points on answers that were, character for character, correct. **The corrected conclusion: the ablation's reported P0 = 0.844 is a judge artifact; the true value is 0.969**, which is what's actually reported in the ablation table. This matters beyond fixing one number — it establishes that any reported gap under roughly 3 accuracy points is inside judge noise and shouldn't be over-interpreted (this specifically affects how you should read the P2-vs-P4 comparison, which is only 1.6 points apart), while it leaves the P2-vs-P5 and P2-vs-P3 results (16.7 and up points apart) far outside that noise floor. It's a ten-line verbatim-match detector that caught a real measurement bug before it got reported as a policy effect — that's the thing to emphasize if asked "why does this matter."

---

## Part 8: Datasets — what they are and why you chose them (expect a "why not benchmark X" question)

**Q: What datasets did you use, and why?**

Two, chosen very deliberately, plus a documented failed attempt with a third:

**FactConsolidation** (a split of MemoryAgentBench, ICLR 2026): a numbered list of facts where a later fact overwrites an earlier one sharing the same subject and predicate; the gold answer is always the most recent value. 38 sessions, 380 facts, 100 questions, 65% carry a `stale_answer` annotation. Because facts arrive as clean atomic triples rather than free-form conversation, extraction quality never bottlenecks contradiction detection — this makes it a clean setting to isolate the *policies'* behavior specifically. Its gold answers are also deliberately counterfactual (e.g., "rugby union was created in India"), so the model's own parametric knowledge is actively unhelpful and can't be used to shortcut the memory system — the NOMEM floor of 0.000 confirms this worked as intended.

**MQuAKE-T** (from MQuAKE, EMNLP 2023): built by diffing real Wikidata snapshots from April 2021 against April 2023 and keeping only relations that changed as a genuine real-world update (not synthetically injected). Every instance ships both the pre-edit and post-edit answer, so the staleness annotation is deterministic — no separate annotation step needed. 38 sessions (matched in size to FactConsolidation), 382 facts, 96 questions, **100%** carry a `stale_answer` annotation, because on MQuAKE-T every question is, by construction, about something that changed. Chosen specifically as the generalization test, because its updates are *real* rather than *constructed by the benchmark's authors*, which removes the most artificial property of FactConsolidation while holding the underlying task form (a fact list, then questions about the current value) fixed between the two benchmarks — that constancy of task form is what makes it a fair generalization test rather than a different experiment altogether.

**Q: Why not just use LoCoMo or LongMemEval — aren't those the standard benchmarks for this?**

They are the standard benchmarks for agent memory broadly, but they turn out to be unusable for measuring *staleness* specifically, and finding this out is itself one of the thesis's four novelty claims (N4). The staleness metric requires knowing, for each question, what the *wrong, superseded* answer would be — and auditing both benchmarks found **zero** questions in either one carry that annotation. On the very first campaign run, staleness read exactly 0.000 across all 42 cells — which briefly looked like a finding ("forgetting policies never cause staleness!") before realizing the metric structurally could not fire, because the ground-truth data it needs doesn't exist in those datasets. There was also an attempt to *recover* this annotation for LongMemEval's knowledge-update questions using an LLM annotator — it produced only 1 usable annotation out of 78 attempts, despite the correct superseded values appearing in plain text in the source conversation. That failure is reported directly in the thesis as a negative result, precisely because deterministic recovery from a dataset's own structure (which is what both converters used here do) turned out to be the only reliable route, and an LLM annotator is not a substitute.

**Q: Doesn't a 0% coverage benchmark seem worth still testing on for a different reason (e.g., conversational realism)?**

Yes — that's explicitly named as a threat to validity (see Part 9): both real benchmarks here are fact-corpus style, not natural conversation, so extraction never has to work under conversational noise. A conversational benchmark with recoverable supersession is listed as the single highest-value piece of unfinished work in the thesis, precisely because that gap can't be closed with more work on the fact-corpus benchmarks already used — it needs a benchmark that doesn't currently exist, built the same deterministic way FactConsolidation and MQuAKE-T were adapted.

**Q: How big are these experiments, really? Sample sizes?**

200 question-answer pairs pooled for FactConsolidation (100 questions × 2 answer models), 192 for MQuAKE-T (96 × 2). Roughly 100 questions per benchmark per model is what the confidence intervals in Part 6 are computed over — worth being upfront that this bounds detectable effect sizes (Part 9, threat #4): the paired intervals are tight enough to support the P2≈P0 equivalence claim within about ±2.5 points, but a smaller true difference than that wouldn't be detectable at this sample size.

---

## Part 9: Threats to validity and limitations — memorize these, they will ask

State these confidently and unprompted if you get the chance; a committee is far more impressed by a candidate who raises their own thesis's weaknesses clearly than one who waits to be caught. In order of how much they actually matter:

1. **Both real-data benchmarks are fact corpora, not natural conversation.** Facts arrive as clean, atomic statements in both, so extraction never bottlenecks contradiction detection — P2 depends on the extractor producing the *same* subject and predicate string for a fact and its later correction, and nothing in the real-data results tests that requirement under conversational noise. **This is the single largest limit on how far these results generalize**, and it's worth saying so plainly if asked what the biggest weakness is.

2. **MQuAKE-T's relations are narrow.** Of its full instance pool, the overwhelming majority concern head-of-government and head-of-state edits. It's a strong test of *real-versus-injected* drift, but not a broad test across many kinds of relations.

3. **FactConsolidation's gold answers are deliberately counterfactual**, which maximizes the NOMEM-vs-memory gap by construction — that's useful for isolating memory's contribution but means the absolute accuracy numbers on that benchmark shouldn't be read as "how good is the model," only as "how much does memory help."

4. **Sample size is roughly 100 questions per benchmark.** Enough to bound the P2-vs-P0 equivalence claim to about ±2.5 points, not enough to rule out a smaller true difference.

5. **Judge noise is 1–2% baseline, with one 15% outlier cell** (see Part 7). Reported gaps under roughly 3 points shouldn't be treated as interpretable on their own.

6. **NOMEM's 0.000 is prompt-gated, not proof of zero parametric knowledge.** The answer prompt instructs the model to say "I don't know" when memory doesn't contain the answer, and NOMEM's records are almost entirely that string — even for facts the model plausibly knows on its own. NOMEM measures memory-*gated* answering under that instruction, not the model's raw parametric ignorance.

7. **P1's TTL window (20 days) was set relative to synthetic session spacing** (roughly one session per day across 38 sessions) — its exact rank is partly an artifact of that choice, and Part 6 already shows its rank is workload-dependent regardless of the exact TTL chosen.

8. **RQ4 — multi-agent — is validated in full only on synthetic data (n=14, mock provider); a real-data pilot (5 of 21 cells, one topology, five of seven policies) is complete and found a genuine boundary condition.** This is explicitly the most consequential open gap in the thesis. See Part 10 below for exactly how to handle this if asked directly — do not overclaim here.

9. **`functional_predicates` is a per-dataset configuration choice**, made by looking at the dataset. The ablation (Part 7) quantifies the consequence precisely, but it remains a real deployment burden: someone adopting DRIFT on a new domain has to correctly enumerate their own functional predicates.

10. **Two answer models, both accessed through one provider (OpenRouter), and both mid-size instruction-tuned models — neither is a frontier model.** Policy rankings agree between the two (Part 6, per-model breakdown), which is reassuring, but this doesn't establish the ranking holds for, say, GPT-5-class or Claude-class frontier models.

**Q: Which of these worries you most, personally?**

The honest answer is #1 (fact-corpus-only) and #8 (RQ4 offline-only) together, because they're the two gaps that can't be argued away with statistics — they're gaps in what's been tested, not gaps in how confidently a tested claim is stated. Framing it this way (rather than picking the "safest" sounding one) reads as more credible than picking whichever limitation sounds smallest.

---

## Part 10: RQ4 and the multi-agent status — handle this carefully, it's your softest spot

**What the thesis currently says, and what is actually true right now:** RQ4 asks whether the policy rankings established with a single reader/writer survive when multiple agents share the memory. The thesis validates this claim on **synthetic data with a deterministic mock provider**, across three topologies:
- **shared** — 5 writer agents round-robin into one graph; tests whether contradictions still get handled correctly when the correcting fact arrives from a *different* agent than the one who wrote the original.
- **independent** — 5 agents each with a private graph, each observing a random 80% subset of sessions; tests variance/robustness under partial observation.
- **orchestrator** — one shared graph, a router LLM assigns each incoming question to one of five specialist worker agents; models a production coordinator/worker pattern.

On the synthetic run (14 questions/cell), P2 leads in all three topologies and holds staleness at 0.000 in all three, and every invalidation in the shared topology arrives cross-writer (the correcting fact came from a different agent than the original) — which is evidence the mechanism is writer-agnostic by construction. **But this is explicitly flagged in the thesis itself as validation of the harness, not as a settled empirical finding** — 14 questions with a scripted mock model is a sanity check, not a result you'd want to generalize from.

**What has happened since — this is now a completed, reported pilot, not a work-in-progress:** a real-data run on MQuAKE-T (the actual benchmark, five real heterogeneous LLM providers, not the mock) was run on the shared topology across five policies (NOMEM, P0, P1, P2, P3; 96 questions each). It is written up in the thesis itself as Section 5.10.1, with a real table and numbers, not left as a verbal aside. The result:

| Policy | Accuracy | Staleness | Invalidations | Active facts |
|---|---|---|---|---|
| NOMEM | 0.000 | 0.000 | 0 | 140 |
| P0 | 0.333 | 0.271 | 0 | 140 |
| P1 (TTL 20d) | 0.281 | 0.135 | 0 | 79 |
| P2 | 0.365 | 0.271 | 0 | 140 |
| P3 | 0.365 | 0.271 | 0 | 140 |

The finding: P2 records **zero invalidations** in this cell, identical to P0's untouched 140 active facts. Directly inspecting the saved graph explains why — of 140 stored facts across 30 distinct predicate strings, the same real-world relation gets extracted under multiple surface forms depending on which of the five models wrote it: `head_of_government` (28 occurrences), `is_head_of_government_of` (9), `head_of_government_of` (7) all for one functional predicate in MQuAKE-T's schema; the same pattern on `citizen_of` (32) vs. `is_citizen_of` (6) vs. `citizenship` (5). P2's contradiction detection matches on exact subject-and-predicate string, so a correction extracted under a different surface form than the original never triggers a match, and the valid-time window never closes. Only 3 of 137 subjects in the graph carry more than one fact at all, versus dozens in the single-extractor single-agent runs — direct, measured evidence the relation is being scattered across string variants rather than consolidated. P1 (TTL) is the one policy whose staleness reduction survives this heterogeneity, because it keys on `t_valid_start` alone and never needs two facts to agree on a predicate string — though at a real accuracy cost (0.281, the lowest of the four non-floor policies here).

The remaining 16 cells (independent and orchestrator topologies, plus P4 and P5 on shared) were not completed — P4's LLM-consolidation step turned out to cost 25–40+ seconds per checkpoint and grows with memory size, making it the dominant cost in the matrix. That was a deliberate, informed stopping point given time constraints, not an accident.

**If asked "is RQ4 answered" — the correct answer, verbatim-adaptable:**

> "Not on the full seven-policy, three-topology design — that's validated only on 14 synthetic questions with a deterministic provider. But I don't want to leave it there, because I did run a real-data pilot: five policies on the shared topology, real heterogeneous LLMs, 96 real questions, and it's in the thesis as a full section with real numbers, not just a caveat. And it's not a null result — it found something the single-agent experiments structurally couldn't surface. When five different models share extraction duty, they don't agree on how to phrase the same relation — I can show you the exact predicate strings — and that silently breaks the exact-match contradiction detection P2 depends on. P2 recorded zero invalidations in that cell, identical to append-only. Only the TTL policy, which doesn't need string agreement, kept working. So the honest state of RQ4 is: partially answered, with a real, mechanistically-explained boundary condition identified, and a clear, already-scoped fix — canonicalizing predicate strings before the match. The other sixteen cells weren't run because the LLM-consolidation policy's cost scales with memory size and I made a deliberate call not to spend the night before this defense grinding through it."

This is a *strong* answer delivered calmly: it distinguishes "validated the harness" from "answered the question," reports a specific mechanism with numbers rather than a vague gesture at "an interesting early signal," and is explicit that the stopping point was a reasoned decision, not something that ran out of time on its own. Do not guess at what the independent or orchestrator topologies would show, and do not claim P4/P5 numbers exist — they don't.

---

## Part 11: Models, providers, and configuration — "when was it trained," parameters, generalizability

**Important framing point, likely worth stating early if this comes up:** DRIFT does not train any model. It is an *evaluation framework* that uses existing, already-trained, off-the-shelf language models purely as components in a pipeline (for extraction, for answering, for judging). Nothing in this thesis involves training or fine-tuning a model — the "training" that happened was of the frontier/mid-size models used as-is (their training is someone else's work, done well before this thesis). If asked "when was it trained" about DRIFT itself, the precise answer is: DRIFT has no training phase; the experiments were run in 2026 against already-released models accessed via API.

**Models used, and their roles:**

| Role | Models | Notes |
|---|---|---|
| Answer model | GLM-5.2, MiniMax-M3 (via OpenRouter) | Two different mid-size instruction-tuned models, to check the policy ranking isn't an artifact of one model's quirks |
| Extraction | GLM-5.2, MiniMax-M3, gpt-oss-120b, Llama-3.3-70B, Llama-3.1-8B, Mistral Small | Rotated per conversation across several providers, mainly to spread call volume over independent rate limits rather than for methodological reasons |
| Judge | gpt-oss:20b (local), gpt-oss-20b (hosted), Command-R7B | A three-provider fallback pool, deliberately from a **different model family** than either answer model, to avoid a model grading its own or a closely related model's answers; Part 7 covers why this rotation is also a confound worth disclosing |
| Embedding | nomic-embed-text (served locally via Ollama), 768 dimensions | Used for the semantic half of the hybrid retrieval score |
| Retrieval depth | k = 25 | Top 25 facts by the hybrid score are what's available to the answer model each turn |

**Q: What "parameters were being tweaked" — what's actually configurable, and what did you tune vs. hold fixed?**

This is worth answering carefully because "hyperparameter tuning" in the ML sense is *not* really what happened — the thesis's whole point is to hold almost everything fixed and vary only the policy. The things that are genuinely configuration choices, per policy:

- **P1's TTL window** (how many days before a fact ages out) — set to 20 days for MQuAKE-T relative to the dataset's ~38-day session span; explicitly named as a threat to validity (Part 9, #7) rather than something optimized for best results.
- **P2's grace period** (how long after invalidation before a superseded fact is physically pruned rather than just excluded from retrieval) — 7 days, chosen to allow some buffer for late-arriving corrections before committing to deletion.
- **P3's novelty threshold** (cosine similarity above which a write is rejected as a near-duplicate) — 0.9, modeling the threshold used in the SAGE paper this policy is based on.
- **`functional_predicates`** — not a numeric hyperparameter but a *declaration*: which predicates in a domain are single-valued. This is the one setting a new deployment genuinely has to configure, and Part 7's ablation exists specifically to show what happens if you get it wrong.
- **Retrieval weighting** (0.6 cosine / 0.3 lexical / 0.1 recency) and **k=25** — held constant across every single experimental cell in the entire thesis; never varied as an experimental condition, because varying it would reintroduce exactly the kind of confound the whole design is built to avoid.

None of these were swept in a grid-search sense — they were each set once, deliberately, and the ablation section (Part 7) is precisely the mechanism by which the thesis checks whether a specific choice (functional_predicates) was doing unacknowledged work.

**Q: How does someone else actually use DRIFT on their own agent? Be concrete.**

Five lines, using the packaged integration surface:

```python
from drift import Memory

mem = Memory(
    policy="P2",
    provider="openrouter:z-ai/glm-5.2",
    embedder="ollama:nomic-embed-text",
    functional_predicates=["lives_in", "works_at", "assigned_to", "status"],
)

mem.observe(["user: I moved to Seattle."], when=time.time())
memory_block = mem.context("Where does the user live?", k=8)
```

There's a dedicated test (`tests/test_memory_api.py`) that pins this integration-facade code path to produce **fact-for-fact identical decisions** to the full experimental harness running the same policy — this is what licenses reading the measured results in the thesis as practical advice about the *library itself*, rather than results that only apply to the specific harness used to produce them. Adding a brand-new policy that isn't one of the seven tested is a subclass plus one registry line, shown in Part 4.

**Q: Is DRIFT dependency-free? What does that actually mean and why does it matter?**

The core package (`pyproject.toml`) declares zero third-party dependencies — it's pure standard-library Python. The only two things ever needed on top of that are `pytest` for running the test suite during development, and `matplotlib` for generating figures during analysis; neither is needed to run the framework itself or to reproduce any reported number. The 99-test offline suite runs in about 0.2 seconds with no network access and no API keys, using a deterministic mock provider and a deterministic hashing-based embedder. This matters for two reasons: it means the framework's *mechanics* (does the substrate correctly close a contradiction, does a policy correctly reject a write, etc.) can be verified completely independently of whether you trust any of the reported experimental results, and it means reproducing the actual numbers only costs an API budget, not a research-lab compute budget — which the thesis argues matters for who can participate in this kind of research at all.

**Q: How reproducible are your actual reported numbers?**

Every single call to a model provider is cached to disk, keyed by a SHA-256 hash of (provider, model, prompt, temperature, max_tokens). This means an interrupted experimental campaign resumes at zero additional cost, and a full rerun produces bit-for-bit identical output to the original run. Results are also organized one JSON file per experimental cell, with failures caught per-cell so one exhausted API quota costs a single cell, not the whole campaign.

---

## Part 12: Impact and "so what" — the practitioner-facing takeaway

**Q: If I'm building a product tomorrow, what do I actually do differently because of your thesis?**

The recommendation is deliberately narrow and falsifiable, not a general "use good judgment":

> If your agent tracks facts that get corrected over time, use bitemporal contradiction invalidation (P2), correctly declare your domain's functional predicates, and do not use a write-time novelty gate. If your facts are genuinely append-only and never get revised, the question doesn't arise at all.

Three things make this actionable rather than aspirational: it's **free at the margin** (statistically equivalent accuracy to never forgetting, at 12% lower token cost — a straightforward cost reduction with no measured quality tradeoff); it **fails safe** (a misconfigured P2 degrades gracefully to append-only behavior, never below it, so there's no risk in turning it on without a tuning campaign); and it **names the one thing you have to configure** (a single inspectable list of predicate names, not an opaque hyperparameter requiring search).

**Q: What's the bigger-picture argument, beyond "use this one policy"?**

Three things. First, memory hygiene should be understood as a **correctness problem, not primarily a cost problem** — the gap between the best and worst policy tested here is 18 accuracy points and up to a 6-fold staleness difference, while the *cost* differences between policies are only around 12%. Most of the current industry framing treats memory management purely as a cost/context-window problem; this thesis's numbers say the correctness axis is the bigger one. Second, **efficiency techniques need correctness audits, not just cost audits** — novelty gating looks purely good on a cost basis (a 3.4x reduction in write-phase API cost, per the paper it's modeled on) and is invisible-bad on a correctness basis unless you specifically build a benchmark that can detect it, which most current evaluations don't. Third, a **bitemporal record is exactly the structure right-to-be-forgotten and audit/provenance requirements need** — it records when a fact was learned, when it stopped being true, and when it was actually removed, which is the same structure that happens to make forgetting free from a modeling perspective.

---

## Part 13: Anticipated hostile/tricky questions, with suggested answers

**"Isn't this just applying a known database concept (bitemporal modeling) to a slightly different problem? Where's the actual research contribution?"**
> "That's fair, and I want to be precise about it rather than oversell it — bitemporal modeling is decades old, and Zep has already applied a version of it to agent memory. The contribution isn't the data structure, it's the experimental design: holding everything else fixed and varying only the forgetting policy, which is what makes the P2-versus-P5 ablation possible. Without that ablation, you could only say 'a bitemporal system did well,' which is compatible with 'graph structure helps' — you couldn't isolate *why*. P5 is built to have every structural advantage P2 has except access to time, and it loses by 16.7 points with p < 0.001. That's what lets me say the advantage comes specifically from bitemporal semantics, not from graph-awareness generally — and that specific, isolated claim, verified statistically, is the contribution."

**"Your sample sizes are only ~100 questions per benchmark. How do I know this isn't noise?"**
> "Two answers. First, the equivalence claims are stated as confidence intervals, not point estimates — I'm not claiming P2 equals P0 exactly, I'm claiming the true difference is bounded within about ±2.5 points, which is a meaningful and falsifiable claim at this sample size even though it wouldn't detect a smaller true difference. Second, and more importantly, the results I lead with — P2 versus P5, and P2 versus P3 — are 16 to 18 points apart with p < 0.001, which is far outside what sample-size noise or the judge noise I separately measured (1-2%, with one bad cell at 15%) could produce. The comparisons I'm cautious about, like P2 versus P4 at only 1.6 points apart, I explicitly flag as inside the noise floor rather than claim a winner."

**"You used an LLM to judge your results. Isn't that circular — aren't you just measuring what the judge model believes, not ground truth?"**
> "It's a real limitation and I found and reported a concrete instance of exactly that risk — the judge-reliability audit in Section 6.9. What limits the damage: the judge model is deliberately from a different family than either answer model, so it's not grading its own outputs; I also report token-F1 in parallel, which is judge-independent lexical overlap, as a cross-check; and when I found the artifact — a 12.5-point swing from judge rotation on byte-identical answers — I didn't just note it, I built a ten-line verbatim-match detector and used it to correct the affected number and establish a noise floor for every other comparison in the thesis. I'd rather have found and disclosed that than have it found by someone else after publication."

**"Why should I believe your framework generalizes beyond the two benchmarks you tested, given they're both fairly narrow fact corpora?"**
> "I don't think I can claim it generalizes to natural conversation yet, and I say that directly in the threats-to-validity section — that's the single biggest limitation I'd point to myself. What I can say is that the two benchmarks I did use are meaningfully different from each other — one is a synthetic, counterfactual fact list, the other is real Wikidata history — and the top and bottom of the policy ranking are stable across that difference, with Spearman's rho of 0.891 across all seven policies. That's evidence the finding isn't an artifact of one specific dataset's construction. But extending to genuinely noisy conversational extraction is explicitly the next piece of work, not something I'm claiming already."

**"What would change your mind about your main recommendation (use P2)?"**
> "A workload where functional predicates can't be cleanly enumerated in advance — my ablation shows P2's efficiency gain depends entirely on that declaration being roughly correct, so a domain where the space of single-valued relations is itself unstable or hard to specify would weaken the practical recommendation, even though the underlying mechanism (don't retrieve what's been contradicted) would presumably still be sound. Also, if the real-data multi-agent run I have in progress right now confirms the predicate-fragmentation issue I'm seeing early signs of, that would be a genuine, specific boundary condition on when the recommendation holds — heterogeneous multi-model extraction, specifically."

**"Practically, what does it cost someone to try this on their own system?"**
> "About an afternoon, by design. Export your agent's real interaction history into the schema DRIFT expects — sessions of timestamped lines, plus a set of questions with gold answers — write a short config file naming your provider and your functional predicates, and run the four or five policies that make sense for your workload. There's no training step, no GPU requirement, and every call is cached, so iterating on the config is nearly free after the first pass."

---

## Part 14: Closing checklist for the night before

- [ ] Say the 3-sentence summary (Part 2) out loud five times without reading it.
- [ ] Be able to draw the pipeline (Part 4) on a whiteboard from memory.
- [ ] Be able to state all seven policies and their one-sentence mechanism without looking.
- [ ] Know the four headline numbers cold: P2≈P0 accuracy (both benchmarks), P2 vs P5 (+16.7 points, p<0.001), P3's staleness multiplier (4.5–4.7x), and the 12% token saving.
- [ ] Rehearse the RQ4 answer (Part 10) specifically — this is your one area of genuine incompleteness, and a calm, precise answer here will read better than a confident answer anywhere else.
- [ ] Rehearse naming your own top 2–3 threats to validity unprompted, early in the presentation, before anyone asks.
- [ ] Sleep. A tired, correct answer reads worse than a rested, honest "let me think about that for a second."
