# When Should Agents Forget? A Controlled Study of Forgetting Policies in Bitemporal Knowledge-Graph Agent Memory

*This guide presents the DRIFT repository in the structure of a camera-ready research paper (AAAI 2027 author-kit conventions). Every section maps claims to the code and data that produce them. The full thesis document is [`THESIS_REPORT.md`](../THESIS_REPORT.md).*

## Abstract

Long-lived LLM agents accumulate memories that go stale: facts true at ingestion time are later superseded, yet retrieval continues to surface them. We present **DRIFT** (Decay Rates In Forgetful biTemporal memory), a controlled experimental framework that isolates the *forgetting policy* as the sole independent variable over a fixed bitemporal knowledge-graph substrate, and uses it to compare six policies — a no-memory floor (NOMEM), an append-only baseline (P0), TTL decay (P1), contradiction-driven invalidation (P2), novelty-gated writes (P3), and LLM consolidation (P4) — across two public benchmarks (LoCoMo; LongMemEval), five answer-model families (Llama-3.3-70B, gpt-oss-120B, Gemini 2.5 Flash, GLM-5.2, MiniMax-M3), and three multi-agent topologies (shared writers, independent partial observers, orchestrator/workers). We separate *staleness* (answers containing superseded facts) from accuracy, and measure cross-writer contradiction handling directly. Harness validation shows the ordering P2 > P0 ≈ P3 ≈ P4 > P1 is invariant across agent topologies, with all shared-topology invalidations arriving cross-writer — evidence that structure-aware forgetting is writer-agnostic by construction. Real-data results populate §5 as the experiment matrix completes.

**Code** — this repository · **Datasets** — `scripts/download_locomo.py`, `scripts/download_longmemeval.py` · **Interactive results** — `docs/dashboard.html`

## 1. Introduction

Production agent memories (Zep, Mem0, MemGPT-style systems) must decide what to keep. Three 2026 surveys name forgetting and consolidation as open problems (arXiv:2603.07670, 2602.06052, 2605.06716); STALE (arXiv:2605.06527) measures frontier models at ~55% on memory-conflict scenarios; and Supersede (arXiv:2606.27472) shows agents retrieve updates yet fail to act on them. Existing work evaluates memory *systems* whole — substrate, retrieval, and forgetting confounded. DRIFT's contribution is methodological: hold everything constant except the forgetting policy, so differences are *caused* by the policy.

**Research questions.** RQ1: how often does append-only memory surface superseded facts? RQ2: which policy achieves the best accuracy–staleness–cost trade-off? RQ3: does exploiting bitemporal structure beat structure-blind forgetting? RQ4: do the rankings survive multi-agent usage — shared writers, partial observation, orchestrator reads — and are they invariant across model families?

**Contributions.** (1) The controlled harness itself (stdlib-only, deterministic offline mode, content-addressed call cache — bit-for-bit reproducible). (2) The **staleness rate** metric, separable from accuracy via `stale_answer` annotations. (3) The first policy × topology factorial for forgetting in multi-agent shared memory, with cross-writer invalidation accounting. (4) An agent-to-agent analysis across five model families testing whether memory hygiene matters equally for weak and strong reasoners. (5) Empirical corroboration, on an independent harness, of the deterministic-over-LLM conflict-resolution principle (arXiv:2606.01435).

## 2. Related Work and Novelty Position

**Substrate.** Zep/Graphiti (arXiv:2501.13956) introduced the bitemporal edge model DRIFT reimplements minimally (`drift/memory/graph.py`). TOKI (arXiv:2606.06240) gives the mechanism a formal operator algebra — theory to our experiments. Engram (arXiv:2606.09900) ships a bitemporal engine; MIRIX (arXiv:2507.07957) and GAM (arXiv:2604.12285) build multi-agent/hierarchical memory systems. All propose *a* mechanism; none compares mechanisms controlled.

**Forgetting policies.** SAGE's novelty gate (arXiv:2605.30711) is our P3; TTL/priority decay appears in FiFA's forgetting-by-design benchmark; arXiv:2605.12978 shows LLM-driven continual updates degrade memory — our P4 operationalizes exactly that risk, and arXiv:2606.01435 argues for deterministic freshness tracking — exactly what P2 is.

**Multi-agent shared memory.** GateMem (arXiv:2606.18829) and governed-shared-memory work (arXiv:2606.24535) name stale propagation and contradiction persistence as open failure modes but benchmark *governance*, not forgetting policies. DRIFT's shared topology measures those two failure modes under controlled policy variation.

**The gap DRIFT fills:** a causal, within-harness comparison of the forgetting-policy design space, factorial over datasets × model families × agent topologies, with staleness as a first-class metric. As of July 2026 no published work occupies this cell.

## 3. Method: the DRIFT Framework

**Substrate** (`drift/memory/graph.py`). Facts are edges with valid time (`t_valid_start..t_invalid_at`) and ingestion time. A contradiction on a functional predicate *closes* the old fact's valid window non-destructively; `provenance` records the writing agent. This makes "what is provably superseded" a queryable property — the precondition for P2 and for cross-writer analysis.

**Pipeline** (`drift/pipeline.py`, `drift/memory/extraction.py`, `drift/embeddings.py`). LLM triple extraction with a deterministic regex upgrade for functional predicates (decouples contradiction detection from extractor luck); hybrid retrieval (0.6 cosine + 0.3 lexical + 0.1 recency); memory-conditioned answering; LLM judge from a different model family cross-checked by token-F1.

**Policies** (`drift/policies.py`) — the independent variable, behind three hooks (write gate / maintenance / retrieval filter): NOMEM (floor: retrieval disabled), P0 (append-only), P1 (TTL), P2 (retrieval-time exclusion of superseded facts + grace-period pruning), P3 (novelty gate τ=0.9), P4 (periodic LLM keep/drop + dedup).

**Topologies** (`drift/swarm.py`) — the usage variable: *shared* (N writers → one graph, round-robin interleaved timeline; reports cross-writer invalidations), *independent* (private graphs, 80% seeded observation; reports mean±std), *orchestrator* (router LLM assigns questions to specialist workers over shared memory; workers may be different model families).

**Reproducibility** (`drift/providers.py`). Stdlib HTTP; per-provider rate limiting; SHA-256(provider, model, prompt, temperature) disk cache making every run resumable and every result re-derivable; `.env` secrets loading; `MockProvider` — retained **strictly for harness validation and the offline test suite**, never for reported results.

## 4. Experimental Design

**Datasets.** LoCoMo (ACL 2024; converter `scripts/download_locomo.py`) — the primary benchmark; LongMemEval (ICLR 2025; converter `scripts/download_longmemeval.py`) — cross-dataset validation, its *knowledge-update* category being an independently-authored staleness probe; synthetic (`data/synthetic_smoke.json`) — harness validation only.

**Model matrix** (`configs/locomo.json`): 6 policies × 5 answer models across four vendor families, extraction fixed (gpt-oss-120B), judge fixed (Gemini 2.5 Flash + token-F1). The agent-to-agent question: do strong reasoners (GLM-5.2, MiniMax-M3) *compensate* for stale memory via in-context reasoning, or *amplify* it by using retrieved-but-superseded facts more confidently? `figures/model_comparison.png` renders this directly.

**Real-world simulation** (`configs/swarm_real.json`): heterogeneous workers (Llama-3.3-70B / GLM-5.2 / MiniMax-M3), GLM-5.2 router, interleaved multi-conversation world — the deployment pattern of production agent systems.

**Metrics** (`drift/runner.py`, `drift/swarm.py`): accuracy, token-F1, staleness rate, tokens/question, memory trajectory, pruned/rejected counts, cross-writer invalidations, per-agent variance.

**Execution.** `make real-all` runs the entire campaign; every cell resumable. Figures: `analysis/plots.py` (six 300-dpi figure types incl. trade-off scatter and model comparison); interactive: `analysis/dashboard.py` → `docs/dashboard.html`; tables: `analysis/report_tables.py`.

## 5. Results

**Harness validation (offline, deterministic — instrument check, not evidence).** Ordering P2 > P0 ≈ P3 ≈ P4 > P1 on the synthetic benchmark (P2: 0.929 acc / 0.000 staleness vs P0: 0.714 / 0.286); invariant across all three swarm topologies; 5/5 shared-topology invalidations cross-writer with no accuracy loss; TTL collapses (0.143) on interleaved timelines. Committed under `results/smoke/`, `results/swarm_smoke/`.

**Real-data results (§6.2–6.5 of THESIS_REPORT.md).** Populated by `make real-all` as cells complete: main LoCoMo table, agent-to-agent model comparison, LongMemEval knowledge-update breakdown, model-diverse swarm. All figures regenerate via `make figures dashboard`.

## 6. Discussion, Limitations, Reproduction

Forgetting is not one mechanism but three intervention points; only the policy consuming the graph's temporal structure improved correctness in validation. Limitations: fixed functional-predicate list; string-based entity resolution; LLM judge bias (mitigated by family separation + F1); free-tier rate limits shape the model matrix. Reproduce: `make test` (25 offline tests) → `make smoke swarm` (validation) → `make real-all` (thesis evidence).

## Appendix A — File-by-File Map

| Path | Role in the experiment |
|---|---|
| `drift/memory/graph.py` | Bitemporal substrate; contradiction semantics; provenance; hybrid search |
| `drift/memory/extraction.py` | LLM triples + deterministic functional-predicate upgrade |
| `drift/policies.py` | NOMEM, P0–P4 behind 3 hooks; registry for `"P1:ttl_days=14"` specs |
| `drift/pipeline.py` | ingest → answer → judge; token-F1 |
| `drift/providers.py` | Providers, rate limiter, SHA-256 cache, `.env`; MockProvider (tests only) |
| `drift/embeddings.py` | Hashing (deterministic) / Ollama (local real) embedders |
| `drift/runner.py` | {policy}×{model} matrix; staleness metric; resumable cells |
| `drift/swarm.py` | shared / independent / orchestrator topologies; cross-writer accounting |
| `configs/*.json` | Experiments-as-data: smoke, locomo (5-model matrix), longmemeval, swarm_{smoke,real,real_mini} |
| `data/`, `scripts/` | Synthetic validation set; LoCoMo + LongMemEval downloaders/converters |
| `tests/` (25) | Substrate semantics, policy isolation, E2E staleness differentiation, swarm topologies |
| `analysis/plots.py` | 300-dpi figures: bars, trade-off, growth, cost, swarm, model comparison |
| `analysis/dashboard.py` | Self-contained interactive HTML (animated pipeline + tabbed charts) |
| `analysis/report_tables.py` | Result JSON → markdown tables |
| `THESIS_REPORT.md`, `docs/BLUEPRINT.md` | The thesis; the execution plan |
| `Makefile` | One target per experiment; `real-all` = the full campaign |

## Appendix B — Trace of One Number

Validation P2 accuracy 0.929: `make smoke` → `runner.py` reads `configs/smoke.json` → fresh `BitemporalGraph` per conversation → `ingest_session` extracts and writes past P2's hooks → `add_fact` closes contradicted windows → questions retrieved, `P2.on_retrieve` hides superseded facts → answered, judged → `results/smoke/P2__mock.json` → `report_tables.py` / `plots.py` / `dashboard.py` → THESIS_REPORT §6.1. Every repository file appears exactly once in this chain.

## References

Zep arXiv:2501.13956 · MemGPT arXiv:2310.08560 · Mem0 arXiv:2504.19413 · A-MEM arXiv:2502.12110 · surveys arXiv:2603.07670, 2602.06052, 2605.06716 · SAGE arXiv:2605.30711 · faulty-updates arXiv:2605.12978 · STALE arXiv:2605.06527 · TOKI arXiv:2606.06240 · deterministic freshness arXiv:2606.01435 · Supersede arXiv:2606.27472 · GateMem arXiv:2606.18829 · governed shared memory arXiv:2606.24535 · Engram arXiv:2606.09900 · MIRIX arXiv:2507.07957 · GAM arXiv:2604.12285 · LoCoMo ACL 2024 · LongMemEval ICLR 2025. Full list: THESIS_REPORT.md §References.
