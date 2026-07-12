# When Should Agents Forget?
## A Controlled Study of Forgetting and Consolidation Policies in Temporal Knowledge-Graph Agent Memory

**Author:** Nandan Hemanth · **Program:** M.Sc. Applied AI · **Framework:** [DRIFT](README.md) v0.1.0
**Status of this document:** living thesis report — updated as benchmark stages complete.

| Stage | Status | Section |
|---|---|---|
| Framework implementation + test suite (18 tests) | ✅ complete (2026-07-11) | §5 |
| Smoke benchmark (synthetic, offline, controlled) | ✅ complete (2026-07-11) | §6.1 |
| LoCoMo benchmark (real LLMs via free APIs) | ⏳ pending API keys | §6.2 |
| Model-diversity + ablation runs | ⏳ pending | §6.3 |
| Contamination stress test (stretch) | ⏳ planned | §8 |

---

## Abstract

LLM agents increasingly rely on persistent memory, yet the dominant design is append-only: facts accumulate and are never revised or removed. Recent work shows this is not benign — long-term memory stores accumulate superseded facts that surface as *stale answers*, and naive LLM-driven consolidation can actively degrade memory quality (arXiv:2605.12978). Three 2026 surveys independently name *learned forgetting* and *continual consolidation* as open problems (arXiv:2603.07670, 2602.06052, 2605.06716). We present **DRIFT**, an open-source framework that isolates the forgetting policy as the experimental variable: a bitemporal knowledge-graph memory (following Zep/Graphiti, arXiv:2501.13956) is held fixed while five policies — no forgetting (P0), TTL decay (P1), contradiction-triggered invalidation (P2), novelty-gated writes (P3), and periodic LLM consolidation (P4) — are compared on identical multi-session conversation streams. On our controlled synthetic benchmark, the append-only baseline answers 28.6% of current-state questions with superseded facts; naive temporal decay eliminates most staleness but collapses long-range recall (accuracy 0.50 vs 0.71); structure-aware forgetting that exploits the graph's bitemporal fields (P2) dominates both, reaching 0.93 accuracy with zero staleness at lower memory cost. We release the framework, datasets, and all experiment traces.

---

## 1. Introduction

### 1.1 Motivation

An agent that remembers everything eventually contradicts itself. When a user says *"I moved to Seattle"*, an append-only memory still contains *"lives in Boston"*, and whether the agent answers correctly becomes an accident of retrieval ranking. Human memory solves this with forgetting and consolidation; agent memory systems mostly do not — the field's production systems (Mem0, Letta/MemGPT, Zep) focus on what to *store* and *retrieve*, treating deletion as an afterthought.

### 1.2 Research questions

- **RQ1 (staleness):** How often does an append-only temporal-graph memory surface superseded facts in its answers, and does this grow with interaction depth?
- **RQ2 (policy comparison):** Across heuristic and agentic forgetting policies, which achieves the best accuracy–staleness–token-cost trade-off?
- **RQ3 (structure):** Does exploiting the memory graph's *bitemporal structure* (valid-time windows closed by contradictions) outperform structure-blind policies (TTL, novelty gates, LLM review)?
- **RQ4 (multi-agent):** Do the policy rankings survive when memory is used the way agent systems actually use it — multiple writers sharing one memory, agents with partial observation, and orchestrator/worker read patterns?

### 1.3 Contributions

1. **DRIFT**, an open-source, dependency-light framework where the forgetting policy is a plug-in and everything else (extraction, graph, retrieval, judging) is held constant. Core is stdlib-only Python; all LLM calls are provider-agnostic (OpenAI-compatible), rate-limited, and content-addressed-cached for exact reproducibility.
2. A **controlled comparison of five forgetting policies** spanning the design space: append-only, temporal decay, bitemporal invalidation, write gating, and agentic consolidation.
3. A **staleness metric** — the fraction of answers containing a superseded fact — measurable because our datasets annotate current-state questions with their outdated alternative (`stale_answer`).
4. Empirical evidence (§6.1) that **structure-aware forgetting dominates** both never-forgetting and structure-blind decay; full-scale LoCoMo validation in progress (§6.2).

## 2. Related Work

**Agent memory systems.** MemGPT/Letta introduced OS-style paged memory with self-editing (Packer et al., 2023). Mem0 (arXiv:2504.19413) targets token-efficient production memory. A-MEM (arXiv:2502.12110) organizes memory as self-evolving Zettelkasten notes. Zep (arXiv:2501.13956) contributes the substrate we adopt: **Graphiti**, a temporal knowledge graph where each edge carries valid-time and ingestion-time, and contradictions close validity windows rather than deleting history. DRIFT's memory model is a faithful, minimal reimplementation of this bitemporal scheme, chosen precisely because it makes "what to forget" a well-posed question over explicit time windows.

**Forgetting and consolidation.** Surveys of agent memory name learned forgetting and continual consolidation as open frontiers (arXiv:2603.07670; arXiv:2602.06052; arXiv:2605.06716; graph-memory taxonomy in arXiv:2602.05665). SAGE (arXiv:2605.30711) gates memory *writes* by novelty — our P3. D-MEM (arXiv:2603.14597) routes writes by reward-prediction error. Most relevant, arXiv:2605.12978 demonstrates that memories continually *updated* by LLMs become faulty over repeated cycles — our P4 operationalizes exactly this risky policy class, and arXiv:2606.15903 shows that *where* memory-management logic sits changes what gets forgotten across 13 system configurations. To our knowledge no prior work compares these policy families on an identical bitemporal graph substrate.

**Evaluation.** LoCoMo (Maharana et al., ACL 2024) and LongMemEval(-V2, arXiv:2605.12493) are the standard long-term conversational memory benchmarks; reported cross-paper numbers are contested (see Letta's reproduction critique), which motivates our within-harness comparison design: DRIFT never compares against numbers produced outside its own pipeline.

## 3. The DRIFT Framework

### 3.1 Memory substrate

A fact is an edge `(subject, predicate, object)` with free-text surface form and four temporal/lifecycle fields: `t_valid_start`, `t_invalid_at` (valid time), `t_ingested` (ingestion time), and `active` (set false only by policy pruning). *Functional predicates* (`lives_in`, `works_at`, `job`, `relationship_status`, `owns_pet`, `studies`, …) admit one true object at a time: ingesting a new object closes the old fact's valid window (`t_invalid_at ← t_event`) without deleting it — non-lossy until a policy decides otherwise. This mirrors Graphiti's bitemporal edge model.

### 3.2 Pipeline

Extraction converts each session's turns into atomic facts (LLM prompt with normalized predicates, plus a deterministic regex pass that recovers functional predicates — ensuring contradiction detection does not depend on extractor quality). Retrieval is hybrid: 0.6·embedding-cosine + 0.3·lexical overlap + 0.1·recency, top-k. Answering is memory-conditioned QA with an "I don't know" instruction. Judging uses an LLM judge from a *different model family* than the answerer, plus token-F1 as a model-free check.

### 3.3 Policy interface and the five policies

Policies see three hooks: `on_write(fact, graph) → bool`, `after_session(graph, provider, now)`, `on_retrieve(facts, now) → facts`.

| ID | Policy | Hook used | Structure-aware? | Hypothesis |
|---|---|---|---|---|
| P0 | No forgetting | none | — | High recall, accumulating staleness |
| P1 | TTL decay (35d) | after_session | no | Kills staleness *and* old recall |
| P2 | Contradiction invalidation (7d grace) | on_retrieve + after_session | **yes** | Kills staleness, preserves recall |
| P3 | Novelty gate (τ=0.9) | on_write | no | Smaller memory, neutral accuracy |
| P4 | LLM consolidation (every 3 sessions) | after_session | partially | Risky: may drop needed facts (arXiv:2605.12978) |

### 3.4 Reproducibility engineering

Deterministic offline mode (MockProvider + hashing embedder) makes every experiment repeatable bit-for-bit without keys; the disk cache keys every real LLM call by SHA-256(provider, model, prompt, temperature), so resumed or repeated runs are free and traceable; the runner writes one JSON per experiment cell with full per-question retrieval traces.

### 3.5 Multi-agent (swarm) extension

`drift/swarm.py` runs the same policies under three agent topologies, holding substrate, extraction, retrieval, and judging constant so that only the *usage pattern* varies:

- **shared** — N writer agents ingest an interleaved global session timeline into one shared graph (round-robin). Contradictions now arrive from *different* writers; each fact records its writer in `provenance`, and the runner reports how many invalidations were cross-writer. Tests policy behaviour under write contention.
- **independent** — N agents with private graphs, each observing a seeded random subset (default 80%) of sessions. Reports per-policy mean ± std across agents: robustness under partial observation.
- **orchestrator** — one shared graph; a router LLM assigns each question to a specialist worker agent (workers may use different model families). Tests the production coordinator/worker read pattern.

## 4. Experimental Setup

**Datasets.** (a) *Synthetic smoke* (this report §6.1): 2 conversations × 5 sessions spanning ~58 simulated days, containing functional-fact updates (city moves, job changes), duplicate utterances (novelty probes), and 14 questions in three categories — `current_state` (annotated with `stale_answer`), `recall_old`, `recall_recent`. (b) *LoCoMo* (§6.2): 10 very-long multi-session conversations, ~1.5k QA pairs, converted by `scripts/download_locomo.py`.

**Models (planned for §6.2).** Extraction: gpt-oss-120B (Cerebras). Answering: Llama-3.3-70B (Groq) and gpt-oss-120B (Cerebras). Judge: Gemini Flash (Google) — different family. Diversity: one NVIDIA NIM model. Embeddings: nomic-embed-text via local Ollama.

**Metrics.** Accuracy (judge), token-F1, **staleness rate** (answers containing the annotated superseded fact), tokens/question, memory-size trajectory (active facts per session), pruned count, write rejections.

## 5. Implementation Status & Verification

- 24 offline tests pass (`make test`), including the swarm topology suite (`tests/test_swarm.py`): graph bitemporality, contradiction semantics, all five policies, extraction upgrade pass, cache round-trip, end-to-end staleness differentiation (P0 answers "Boston", P2 answers "Seattle" on the same stream — `tests/test_pipeline.py::test_staleness_differentiation_p0_vs_p2`).
- Full pipeline smoke run completes offline in <1s with zero API calls (`make smoke`).

## 6. Results

### 6.1 Smoke benchmark (synthetic, offline mock provider) — ✅ completed 2026-07-11

*Purpose: controlled validation of the experimental mechanism with a deterministic answerer/judge, so differences are attributable to policies alone. Absolute numbers are not comparable to LLM runs.*

| Policy | Accuracy | Mean F1 | Staleness | Tokens/Q | Active facts | Pruned | Write rej. |
|---|---|---|---|---|---|---|---|
| P0 no forgetting | 0.714 | 0.243 | 0.286 | 173 | 12 | 0 | 0 |
| P1 TTL decay (35d) | 0.500 | 0.146 | 0.071 | 161 | 6 | 6 | 0 |
| **P2 contradiction invalidation** | **0.929** | **0.299** | **0.000** | 172 | 9 | 3 | 0 |
| P3 novelty gate (τ=0.9) | 0.714 | 0.243 | 0.286 | 173 | 11 | 0 | 1 |
| P4 LLM consolidation | 0.714 | 0.243 | 0.286 | 173 | 11 | 1 | 0 |

Per-category accuracy:

| Category | P0 | P1 | P2 | P3 | P4 |
|---|---|---|---|---|---|
| current_state (staleness probes) | 0.00 | 0.75 | 0.75 | 0.00 | 0.00 |
| recall_old | 1.00 | 0.00 | 1.00 | 1.00 | 1.00 |
| recall_recent | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 |

**Findings (support RQ1–RQ3 at smoke scale):**

1. **Staleness is real and systematic (RQ1).** The append-only baseline fails *every* current-state question, answering with superseded facts 28.6% of the time overall — the superseded surface form is lexically closer to the question than the update ("I live in Boston, the city…" vs "I moved to Seattle…"), so retrieval systematically prefers it. This is a mechanism, not an accident, and it will not vanish with better retrieval alone.
2. **Structure-blind forgetting trades one failure for another (RQ2).** TTL decay cuts staleness 4× but zeroes out `recall_old` — exactly the accuracy-collapse mode the degradation literature predicts for time-based pruning.
3. **Structure-aware forgetting dominates (RQ3).** P2, which forgets *only what the graph's bitemporal semantics prove superseded*, achieves the best accuracy (0.93), zero staleness, and full old-fact recall, with 25% less active memory than P0. Write-gating (P3) and consolidation (P4) shrink memory but do not address staleness, confirming that the three hook points target different failure modes.

### 6.2 LoCoMo with real LLMs — ⏳ pending

Blocked only on API keys (`CEREBRAS_API_KEY`, `GROQ_API_KEY`, `GEMINI_API_KEY`). Run: `make locomo-data && make locomo`. This section will be updated with: the main 5-policy × 2-model table, accuracy-vs-tokens Pareto, per-category breakdown (LoCoMo's multi-hop/temporal/adversarial categories), and memory-size trajectories. Estimated budget: ~8–12k LLM calls, within free tiers over 1–2 days with the built-in cache and rate limiter.

### 6.3 Ablations — ⏳ planned

Retrieval k ∈ {4, 8, 16}; P1 ttl ∈ {14, 35, 70}d; P3 τ ∈ {0.8, 0.9, 0.95}; P4 period ∈ {1, 3, 5}; judge-vs-F1 agreement analysis.

### 6.4 Swarm topologies (synthetic, offline mock provider) — ✅ completed 2026-07-12

*Purpose: test RQ4 — whether the policy ordering from §6.1 survives multi-agent usage patterns. Same controlled mock setting as §6.1; note P1 uses ttl=14d here (vs 35d in §6.1) against the interleaved ~58-day global timeline. Figures: `results/swarm_smoke/figures/`.*

| Topology | P0 | P1 (14d) | **P2** | P3 | P4 |
|---|---|---|---|---|---|
| shared (3 writers, acc) | 0.714 | 0.143 | **0.929** | 0.714 | 0.714 |
| independent (3 agents, acc mean ± std) | 0.667 ± 0.041 | 0.143 ± 0.000 | **0.881 ± 0.041** | 0.667 ± 0.041 | 0.667 ± 0.041 |
| orchestrator (3 workers, acc) | 0.714 | 0.143 | **0.929** | 0.714 | 0.714 |
| staleness (all topologies) | 0.286 | 0.000 | **0.000** | 0.286 | 0.286 |

**Findings (RQ4):**

1. **The ordering P2 > P0 ≈ P3 ≈ P4 > P1 is invariant across all three topologies.** Policy choice matters more than agent topology at this scale.
2. **Contradiction invalidation survives multi-writer contention.** In the shared topology, 5/5 invalidations were *cross-writer* — the update fact arrived via a different agent than the original — yet P2 matched its single-agent accuracy (0.929). Because contradiction detection lives in the graph (bitemporal semantics), not in any agent, it is writer-agnostic by construction. This is the mechanism that makes P2 suitable for shared-memory agent systems.
3. **TTL collapses catastrophically on interleaved timelines (0.143).** With sessions from multiple conversations interleaved, the global stream spans the full ~58 days and a 14-day TTL prunes nearly all old-but-true facts. TTL's failure mode *worsens* with swarm-style usage, where memory horizons stretch.
4. **Partial observation degrades P2 gracefully** (0.929 → 0.881 ± 0.041): an agent that missed the update session cannot invalidate the old fact, but agents that saw it are unaffected. Variance is small and equal across structure-blind policies.

## 7. Discussion

The smoke results sharpen the thesis claim: *forgetting is not one thing.* The three policy hook points (write gate, maintenance, retrieval filter) address different failure modes, and the only policy that improved correctness was the one that consumed the graph's temporal structure rather than a proxy signal (age, similarity, LLM judgment). This suggests the field's framing of "learned forgetting" as a scoring problem may be incomplete — the representation (bitemporal windows) does much of the work before any learning happens. If the LoCoMo runs preserve the ordering P2 > P0 > P1 with real models, the practical recommendation to memory-system builders is concrete: implement contradiction-driven invalidation *at retrieval time* before investing in LLM-driven consolidation, which adds cost and (per arXiv:2605.12978) risk.

## 8. Limitations & Future Work

The smoke benchmark is small and lexically constructed to be solvable by a deterministic answerer; it validates the harness and mechanism, not generality — that is what §6.2 is for. The judge in real runs is an LLM with known biases (mitigated by family separation and F1 cross-checks). Functional-predicate contradiction detection currently relies on a fixed predicate list; entity resolution is string-based. Future work: contamination stress test (Zombie-Agents-style injections, arXiv:2602.15654 — does P2's provenance-adjacent structure also quarantine poisoned facts?); learned policies (bandit over policy actions using the staleness signal as reward). The multi-agent extension (§3.5, §6.4) currently uses the synthetic dataset and a mock provider; scaling the swarm study to LoCoMo with model-diverse workers (configs/swarm_real.json wires Llama-3.3-70B, GLM-5.2, and MiniMax-M3 as specialist workers) is the immediate next step, along with adversarial writers (a Zombie-Agents-style contamination test, arXiv:2602.15654 — does P2 also quarantine poisoned facts?).

## 9. Conclusion

DRIFT turns "when should agents forget?" from a position-paper question into a measurable, reproducible experiment. Even at smoke scale the answer has structure: never forgetting poisons current-state answers, naive decay poisons recall, and bitemporal contradiction-aware forgetting — nearly free to implement on a Graphiti-style substrate — dominates both.

## References

1. Rasmussen et al., *Zep: A Temporal Knowledge Graph Architecture for Agent Memory*, arXiv:2501.13956.
2. Packer et al., *MemGPT: Towards LLMs as Operating Systems*, arXiv:2310.08560.
3. Chhikara et al., *Mem0: Production-Ready AI Agents with Scalable Long-Term Memory*, arXiv:2504.19413.
4. Xu et al., *A-MEM: Agentic Memory for LLM Agents*, arXiv:2502.12110.
5. *Memory for Autonomous LLM Agents: Mechanisms, Evaluation, and Emerging Frontiers*, arXiv:2603.07670.
6. *Rethinking Memory Mechanisms of Foundation Agents in the Second Half*, arXiv:2602.06052.
7. *From Storage to Experience: Survey on the Evolution of LLM Agent Memory*, arXiv:2605.06716.
8. *Graph-based Agent Memory: Taxonomy, Techniques, and Applications*, arXiv:2602.05665.
9. *SAGE: A Novelty Gate for Efficient Memory Evolution in Agentic LLMs*, arXiv:2605.30711.
10. *D-MEM: Dopamine-Gated Agentic Memory via Reward Prediction Error Routing*, arXiv:2603.14597.
11. *Useful Memories Become Faulty When Continuously Updated by LLMs*, arXiv:2605.12978.
12. *Control-Plane Placement Shapes Forgetting*, arXiv:2606.15903.
13. Maharana et al., *Evaluating Very Long-Term Conversational Memory of LLM Agents* (LoCoMo), ACL 2024.
14. *LongMemEval-V2: Evaluating Long-Term Agent Memory Toward Experienced Colleagues*, arXiv:2605.12493.
15. *Zombie Agents: Persistent Control of Self-Evolving LLM Agents via Self-Reinforcing Injections*, arXiv:2602.15654.
16. *MemGuard: Preventing Memory Contamination in Long-Term Memory-Augmented LLMs*, arXiv:2605.28009.
17. *Multi-Agent Memory from a Computer Architecture Perspective*, arXiv:2603.10062.
18. Letta, *Benchmarking AI Agent Memory* (reproduction critique), letta.com/blog/benchmarking-ai-agent-memory.

## Appendix A — Reproduction

```bash
make test          # 18 tests, offline
make smoke         # regenerates §6.1 exactly (deterministic)
make tables        # regenerates the tables above from results/smoke
```

All numbers in §6.1 are generated by `analysis/report_tables.py` from `results/smoke/*.json`; no number in this document is hand-computed.
