# DRIFT Repository Guide

*Every file, what it does, and how it contributes to testing the thesis.*

## The claim under test

**Thesis question:** When should LLM agents forget?
**Central hypothesis (H1):** forgetting driven by the memory's *bitemporal structure* (P2: hide facts the graph proves superseded) beats both never forgetting (P0, accumulates staleness) and structure-blind forgetting (P1 TTL, destroys recall; P3/P4, don't address staleness).
**Supporting hypotheses:** H2 — write-time novelty gating (P3) shrinks memory cheaply but leaves staleness untouched. H3 — LLM-driven consolidation (P4) is risky (corroborating arXiv:2605.12978). RQ4 — these rankings survive multi-agent usage (shared writers, partial observation, orchestrator/worker reads).

The experimental logic of the whole repo: **hold everything constant except the forgetting policy.** Same extraction, same graph, same retrieval, same judge — so any measured difference is *caused* by the policy. Each file below exists to build, control, measure, or communicate that comparison.

## `drift/` — the framework

| File | What | Why it matters to the hypothesis |
|---|---|---|
| `providers.py` | OpenAI-compatible LLM client (stdlib urllib), per-provider rate limiter, SHA-256 disk cache, `.env` loader, and `MockProvider` | **Control + reproducibility.** The cache makes every experiment resumable and bit-for-bit repeatable; the mock provider removes LLM nondeterminism entirely so the smoke benchmark isolates policy effects. Provider presets (Groq/Cerebras/Gemini/NVIDIA/OpenRouter) let extraction, answering, and judging use *different model families* — the judge-independence bias control. |
| `embeddings.py` | `HashingEmbedder` (offline, deterministic) and `OllamaEmbedder` (local nomic-embed-text) | Retrieval needs vectors. The hashing embedder makes offline runs deterministic; Ollama removes the API-quota bottleneck for real runs. Kept swappable so retrieval quality is a controlled variable, not a confound. |
| `memory/graph.py` | `BitemporalGraph` + `Fact`. Facts carry valid time (`t_valid_start..t_invalid_at`) and ingestion time; contradictions on functional predicates (lives_in, works_at, …) *close* the old fact's valid window instead of deleting it. Hybrid search (0.6 cosine + 0.3 lexical + 0.1 recency). | **The load-bearing file.** The bitemporal window is what makes H1 testable: P2's "forget only what's provably superseded" is only expressible because contradiction closes a window non-destructively. `provenance` records which agent wrote each fact — the hook RQ4's cross-writer analysis relies on. |
| `memory/extraction.py` | LLM triple extraction plus a deterministic regex pass that upgrades functional predicates | The regex upgrade ensures contradiction detection doesn't silently depend on extractor quality — separating "P2 failed" from "extraction failed", which is exactly the confound the LoCoMo run must diagnose. |
| `policies.py` | The five policies behind one interface: `on_write` / `after_session` / `on_retrieve`, plus a registry for spec strings like `"P1:ttl_days=14"` | **The independent variable.** P0 append-only, P1 TTL, P2 contradiction invalidation, P3 novelty gate, P4 LLM consolidation. The three hooks are themselves a finding: forgetting is not one mechanism but three intervention points with different failure modes. |
| `pipeline.py` | `ingest_session` → `answer_question` → `judge_answer`, plus `token_f1` | The fixed experimental procedure every policy runs through. Token-F1 is the model-free cross-check on the LLM judge. |
| `runner.py` | `{policy} × {model}` experiment matrix; one JSON per cell; resumable; computes the **staleness rate** (answers containing the annotated superseded fact) | **The measurement instrument.** Staleness is the thesis's metric contribution — accuracy alone can't distinguish "wrong because forgotten" from "wrong because stale". |
| `swarm.py` | Three multi-agent topologies over the same substrate: `shared` (N writers, one graph), `independent` (private graphs, 80% observation), `orchestrator` (router LLM + specialist workers). Reports cross-writer invalidations and per-agent variance. | **RQ4.** Tests whether the policy ranking survives how agent systems are actually deployed. Key §6.4 result: 5/5 invalidations were cross-writer and P2's accuracy held — contradiction detection lives in the graph, so it's writer-agnostic by construction. |

## `configs/` — experiments as data

Each JSON is one experiment specification; changing an experiment never means changing code (reviewability + reproducibility).

- `smoke.json` — offline single-agent baseline (mock provider). Produced §6.1.
- `locomo.json` — the main event: LoCoMo with Cerebras extraction, Groq/Cerebras answering, Gemini judging.
- `swarm_smoke.json` — offline 3-topology × 5-policy matrix. Produced §6.4.
- `swarm_real.json` — model-diverse swarm: workers Llama-3.3-70B / GLM-5.2 / MiniMax-M3, GLM-5.2 router, Gemini judge.
- `swarm_real_mini.json` — single-cell Gemini-only config used to validate the real-API path end-to-end.

## `data/`, `scripts/`

- `data/synthetic_smoke.json` — hand-built 2-conversation dataset with planted fact updates (Boston→Seattle, Acme→Globex), duplicate utterances (novelty probes), and questions annotated with `stale_answer`. The annotations are what make staleness *measurable*; the planted updates make contradiction handling *observable*.
- `scripts/download_locomo.py` — downloads LoCoMo (Maharana et al., ACL 2024) and converts it to DRIFT's schema. External validity: synthetic data proves the mechanism, LoCoMo proves the claim.

## `tests/` — 24 offline tests, no keys needed

- `test_graph.py` — bitemporal semantics: contradiction closes windows, search ranks correctly. Guards the substrate every hypothesis stands on.
- `test_policies.py` — each policy does exactly its mechanism and nothing else (a policy that secretly does more would invalidate the controlled comparison).
- `test_pipeline.py` — end-to-end incl. `test_staleness_differentiation_p0_vs_p2`: on the same stream P0 answers "Boston", P2 answers "Seattle" — H1's mechanism as an executable assertion.
- `test_swarm.py` — timeline interleaving, cross-writer invalidation detection, per-agent variance reporting, router coverage.

## `analysis/`, `results/`, `docs/`

- `analysis/report_tables.py` — result JSONs → markdown tables (the ones in THESIS_REPORT.md).
- `analysis/plots.py` — 300-dpi thesis figures: accuracy/staleness bars, trade-off scatter (ideal = top-left), memory-growth curves, token cost, swarm topology comparison, variance error bars.
- `analysis/dashboard.py` — generates `docs/dashboard.html`, a self-contained interactive page (animated pipeline, concept explainer, tabbed charts) with results embedded at build time so it opens offline by double-click.
- `results/smoke/`, `results/swarm_smoke/` — committed result cells + figures backing §6.1/§6.4 (anyone can verify the tables without rerunning).
- `docs/BLUEPRINT.md` — the 7-day execution plan. `THESIS_REPORT.md` (root) — the thesis itself.

## Root

- `Makefile` — every experiment is one target: `test`, `smoke`, `swarm`, `swarm-real`, `locomo-data`, `locomo`, `tables`, `figures`, `dashboard`, `clean`.
- `pyproject.toml` — core deps: **none** (stdlib-only by design — nothing in the measured pipeline can drift with a library version). Dev: pytest; figures: matplotlib.
- `.env` / `.env.example` / `.gitignore` — secrets stay local (`.env` gitignored, loaded automatically by `providers.py`); the example file documents required keys for cloners.
- `README.md` — quickstart, provider table, current results, extension points.

## How a single result is produced (trace one number)

The §6.1 P2 accuracy of 0.929 was produced by: `make smoke` → `runner.py` reads `configs/smoke.json` → for each conversation builds a fresh `BitemporalGraph` → `pipeline.ingest_session` extracts facts (`extraction.py`) and writes them past P2's hooks (`policies.py`) into the graph (`graph.py`) → questions retrieved hybrid-scored, filtered by `P2.on_retrieve` (superseded facts hidden) → answered and judged (`pipeline.py`, MockProvider) → per-question records + memory curves written to `results/smoke/P2__mock.json` → tabulated by `report_tables.py`, plotted by `plots.py`, embedded by `dashboard.py`, cited in `THESIS_REPORT.md` §6.1. Every file in the repo appears exactly once in that chain — that's the architecture.
