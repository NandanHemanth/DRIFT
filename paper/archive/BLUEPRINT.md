# Blueprint: "When Should Agents Forget?" — 7-Day Thesis Sprint
*A controlled study of forgetting & consolidation policies in temporal knowledge-graph agent memory*

**Mode:** direct (no existing repo) · **Steps:** 9 · **Parallelizable:** Steps 4a–4c, 7a–7b · **Generated:** 2026-07-11

---

## 0. Why This Topic (the pitch you'll write in your intro)

- **Named open problem.** "Learned forgetting" and "continual consolidation" are explicitly listed as open challenges in the 2026 surveys ([arXiv:2603.07670](https://arxiv.org/abs/2603.07670), [arXiv:2602.06052](https://arxiv.org/pdf/2602.06052), [arXiv:2605.06716](https://arxiv.org/html/2605.06716v1)).
- **A known failure to explain.** [arXiv:2605.12978](https://arxiv.org/pdf/2605.12978) showed continual LLM-driven memory updates *degrade* memory. Nobody has systematically tested whether cheap forgetting policies fix this in graph memory.
- **Perfect 1-week shape.** No training, no GPUs — it's ingestion + retrieval + QA scoring. All compute is API calls you already have for free. Positive OR negative results are publishable.
- **Research question (RQ):** *Given a bitemporal knowledge-graph memory (Graphiti-style), which forgetting/consolidation policy gives the best accuracy–token-cost–staleness Pareto across long multi-session interactions?*
- **Contributions you can honestly claim:**
  1. First controlled comparison of N forgetting policies on graph-based agent memory.
  2. Replication (or refutation) of the memory-degradation effect in the graph setting.
  3. Open-source harness + all traces released.
  4. (Stretch) contamination stress test: do forgetting policies also purge poisoned memories?

---

## 1. Fixed Design Decisions (don't relitigate these mid-week)

| Decision | Choice | Why |
|---|---|---|
| Memory system | **Graphiti** (getzep/graphiti) + FalkorDB via Docker | OSS, bitemporal, supports OpenAI-compatible endpoints; credibility + zero build time |
| Benchmark | **LoCoMo** (10 conversations, public) primary; **LongMemEval-S** 100-question subset secondary | Both public, QA-style, standard in every memory paper |
| Ingestion/answer model | **Llama 3.3 70B via Groq** (1k req/day) + **gpt-oss-120b via Cerebras** (14.4k req/day) as second model | Fast, free, high daily limits |
| Diversity model | One NVIDIA NIM model (e.g., nemotron-3-super-120b, 40 req/min) | Shows results generalize across model families |
| Judge model | **Gemini 2.5/3 Flash via Google AI Studio** (different family from answer models) | Avoids self-preference bias in LLM-as-judge |
| Embeddings | Local via Ollama (nomic-embed-text) on your M1 Pro | Free, unlimited, removes a rate-limit bottleneck |
| Policies (5) | P0 no-forgetting baseline · P1 TTL/recency decay · P2 contradiction-triggered invalidation (uses bitemporal fields) · P3 novelty-gated writes (SAGE-style) · P4 periodic LLM consolidation (merge+prune) | Spans heuristic → agentic; P4 is the one arXiv:2605.12978 says may degrade |
| Metrics | QA accuracy (judge-scored), tokens per answered question, retrieval latency, memory size (nodes/edges) over sessions, staleness errors (answers using invalidated facts) | Pareto framing = your headline figure |
| Scale budget | 10 LoCoMo convos × ~50 sessions ingest + ~500 QA × 5 policies × 2 models ≈ **~8–12k LLM calls** | Fits free tiers if spread across providers + 2 days of runs |

**Rate-limit math (sanity check):** Groq Llama-3.3-70B = 1,000 req/day → use for QA answering only (~2.5k calls over week ✅). Cerebras gpt-oss-120b = 14.4k req/day → use for ingestion/extraction (heaviest load ✅). NIM = 40 req/min ≈ 57k/day theoretical → diversity runs ✅. Cache **every** call to disk (hash of prompt → response) so reruns are free.

---

## 2. Repo Structure (create Day 1)

```
forgetful-agents/
├── README.md                  # install, repro commands, results table
├── pyproject.toml             # uv or pip; pin versions
├── docker-compose.yml         # FalkorDB
├── src/
│   ├── providers.py           # OpenAI-compatible client w/ per-provider rate limiter + disk cache
│   ├── memory/
│   │   ├── graphiti_store.py  # thin wrapper over Graphiti
│   │   └── policies.py        # P0–P4, one class each, common interface
│   ├── ingest.py              # conversation sessions → memory episodes
│   ├── answer.py              # question → retrieve → answer
│   ├── judge.py               # LLM-as-judge scoring (+ exact-match fallback)
│   └── run_experiment.py      # experiment matrix runner, resumable
├── data/                      # LoCoMo + LongMemEval subsets (download scripts)
├── results/                   # JSON traces, one file per (policy, model, dataset)
├── analysis/
│   └── figures.ipynb          # Pareto plot, degradation curves, memory-size curves
└── paper/
    └── main.tex               # ACL/NeurIPS workshop template
```

---

## 3. The 9 Steps (each has a cold-start brief, tasks, verification, exit criteria)

### Step 1 — Environment & API bring-up *(Day 1 morning)*
**Brief:** Fresh machine, M1 Pro. Goal: all providers callable through one interface.
**Tasks:** Get keys (Groq, Cerebras, Google AI Studio, NVIDIA NIM, OpenRouter as spare). Install Docker + FalkorDB, Ollama + nomic-embed-text, Python env, Graphiti. Write `providers.py`: OpenAI-compatible client, per-provider token bucket, SQLite/disk response cache.
**Verify:** `python -m src.providers --smoke` returns a completion from all 4 providers; second identical call hits cache (0 API calls).
**Exit:** All providers green + cache proven. **Rollback:** drop any provider that fails verification; 3 providers is enough.

### Step 2 — Data & baseline memory pipeline *(Day 1 afternoon – Day 2 morning)*
**Brief:** Get LoCoMo (github.com/snap-research/locomo) and LongMemEval; ingest ONE conversation into Graphiti end-to-end.
**Tasks:** Download datasets; write `ingest.py` (session → Graphiti episodes with timestamps); write `answer.py` (question → Graphiti hybrid search → answer prompt); write `judge.py` (judge prompt from the LoCoMo paper, plus F1/exact-match as sanity metric).
**Verify:** 1 full conversation ingested; 20 questions answered; judge scores produced; spot-check 5 judgments by hand.
**Exit:** End-to-end trace JSON for 1 conversation committed. **Rollback:** if Graphiti ingestion is too slow/token-hungry, switch to its smaller extraction model setting or reduce to 8 conversations — decide HERE, not later.

### Step 3 — Lock the experiment config *(Day 2 afternoon)*
**Brief:** Freeze the matrix before writing policies, so results are comparable.
**Tasks:** Fix: conversations list, question subset (all LoCoMo QA; 100 LongMemEval), retrieval k, prompts (versioned files), seeds, model list. Write `run_experiment.py`: iterates matrix, resumable (skips completed cells), writes one JSON per cell.
**Verify:** P0 baseline runs on 2 conversations unattended and resumes correctly after a forced kill.
**Exit:** `configs/experiment.yaml` frozen; baseline numbers for 2 convos exist.

### Step 4 — Implement policies P1–P4 *(Day 3; 4a/4b/4c parallelizable)*
**Brief:** Common interface: `policy.on_write(episode, graph)`, `policy.periodic(graph)`, `policy.on_retrieve(results)`.
- **4a (P1+P2, heuristic):** TTL decay (edges older than T excluded/deleted); contradiction-triggered invalidation (Graphiti already sets `invalid_at` — P2 actively prunes/deprioritizes invalidated edges at retrieval).
- **4b (P3 novelty gate):** embedding-similarity gate — skip writes whose novelty vs existing neighborhood < τ (SAGE-style, cite arXiv:2605.30711).
- **4c (P4 LLM consolidation):** every S sessions, LLM summarizes/merges duplicate entities and prunes low-salience edges — the risky policy the degradation paper warns about (cite arXiv:2605.12978).
**Verify:** unit test per policy on a synthetic 10-fact graph (e.g., P2 removes the superseded "lives in X" fact); memory size measurably differs from P0 after ingesting 1 conversation.
**Exit:** 5 policies runnable via the same runner flag.

### Step 5 — Full experiment run *(Day 4, machine works while you sleep)*
**Brief:** Run the whole matrix: {5 policies} × {2 answer models} × {LoCoMo}; NIM diversity model on best + worst policy only. LongMemEval subset on P0 + best policy.
**Tasks:** Launch runs staggered across providers to respect limits; monitor cache-hit rate and error log; re-queue failures.
**Verify:** every matrix cell has a results JSON with ≥95% questions answered; no cell mixed prompt versions.
**Exit:** `results/` complete. **Rollback (scope cut):** drop model 2 on P1/P3 cells; the core claim only needs 1 model × 5 policies.

### Step 6 — Analysis & figures *(Day 5 morning)*
**Brief:** Turn traces into the 4 figures + 2 tables the paper needs.
**Deliverables:** (F1) accuracy vs token-cost Pareto scatter, one point per policy/model — **headline**; (F2) accuracy over session-depth curves (does P0 degrade? does P4 collapse?); (F3) memory size (edges) over sessions per policy; (F4) staleness-error rate per policy; (T1) main results table; (T2) ablation (retrieval k, τ, T).
**Verify:** numbers in tables regenerate from raw JSON via one script (`make figures`); a colleague-level reader can trace any number to a trace file.
**Exit:** figures/ committed.

### Step 7 — Stretch: contamination test *(Day 5 afternoon — SKIP if behind)*
**Brief:** Inject 20 false/adversarial facts per conversation mid-way (Zombie-Agents-style, cite arXiv:2602.15654); measure how many survive into answers under each policy.
**7a:** injection script; **7b:** rerun P0, P2, P4 only.
**Exit:** one extra figure: "poisoned-fact survival rate by policy." **Skip criterion:** if Step 5 isn't done by Day 5 noon, cut this — the thesis stands without it.

### Step 8 — Write the paper *(Day 5 evening – Day 6)*
**Brief:** 6–8 pages, workshop format (NeurIPS/ICLR agent-memory workshops or ACL SRW).
**Structure:** Abstract · Intro (RQ + 3 contributions) · Related work (you already have the 30-source survey — condense §1–3 of `agent-thesis-research-report.md`) · Method (memory model + 5 policies, 1 figure) · Setup (datasets, models, judge, budget) · Results (F1–F4, T1–T2) · Limitations (judge bias, 2 datasets, no human eval, free-tier model selection) · Conclusion.
**Thesis wrapper (if your program needs a thesis doc, not just a paper):** Chapter 1 = extended intro/motivation, Chapter 2 = full literature review (expand the survey report), Chapter 3 = the paper's method, Chapter 4 = results, Chapter 5 = discussion/future work. This is reformatting, not new research — budget 3–4 hours.
**Verify:** every claim has a citation or a results file; every number matches `make figures` output; run a plagiarism-safe originality pass on your own text.
**Exit:** PDF compiles; advisor-ready draft.

### Step 9 — Ship *(Day 7)*
**Tasks:** Clean README with exact repro commands; push repo public (GitHub); tag v1.0; upload traces (HuggingFace dataset or repo LFS); optional arXiv submission (needs endorsement — ask your advisor); write a short thread/blog post.
**Verify:** fresh `git clone` → `make smoke` works on a clean machine (or clean venv).
**Exit:** public repo + PDF + traces. Done.

---

## 4. Day-by-Day Schedule

| Day | Focus | Hard exit criterion |
|---|---|---|
| 1 | Steps 1–2a: env, keys, Graphiti up, data downloaded | All providers green, 1 episode ingested |
| 2 | Steps 2b–3: end-to-end baseline, freeze config | Baseline trace on 2 convos |
| 3 | Step 4: all 5 policies implemented + unit tests | Runner works for every policy |
| 4 | Step 5: full matrix runs (start morning, babysit) | ≥80% of cells complete by midnight |
| 5 | Step 6 + optional 7: analysis, figures, contamination | F1–F4 + T1 exist |
| 6 | Step 8: paper writing | Complete draft PDF |
| 7 | Step 9 + buffer: polish, repro check, ship | Public repo + final PDF |

**Golden rule:** every day has a scope-cut lever (fewer conversations → fewer models → fewer policies → drop LongMemEval → drop Step 7). Cut scope, never cut the controlled-comparison core (1 model × 5 policies × LoCoMo).

## 5. Risk Table

| Risk | Likelihood | Mitigation |
|---|---|---|
| Graphiti ingestion too slow/token-heavy on free tiers | Medium | Cerebras 14.4k/day for extraction; reduce to 8 convos; pre-ingest P0 graph once and snapshot-copy it for P1/P2 (they only differ at retrieval/pruning) |
| Rate-limit bans | Low-Med | Token-bucket limiter at 80% of published limits; disk cache; OpenRouter as spillover |
| Judge unreliability | Medium | Dual metric (judge + F1); hand-check 30 samples; report agreement |
| Results are "boring" (all policies similar) | Low | Still publishable: "cheap forgetting is free" is a finding; degradation replication is a second finding |
| LoCoMo contested numbers | Medium | You compare policies *within* your own harness — never against others' published numbers (cite Letta's critique as justification) |

## 6. Key References for the Paper
Surveys: arXiv:2603.07670, 2602.06052, 2605.06716, 2602.05665 · Systems: Zep arXiv:2501.13956 (Graphiti), Mem0 arXiv:2504.19413, A-MEM arXiv:2502.12110, SAGE arXiv:2605.30711 · Motivation: arXiv:2605.12978 (degradation), arXiv:2606.15903 (control-plane forgetting) · Security stretch: arXiv:2602.15654 (Zombie Agents), arXiv:2605.28009 (MemGuard) · Benchmarks: LoCoMo, LongMemEval arXiv:2605.12493 · Full annotated list: see `agent-thesis-research-report.md`.
