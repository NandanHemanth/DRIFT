# DRIFT

**D**ecay and **R**etention **I**n **F**orgetful **T**emporal-graph memory — a research framework for studying *forgetting and consolidation policies* in LLM agent memory.

> Thesis question: **When should agents forget?** Given a bitemporal knowledge-graph memory (Zep/Graphiti-style), which forgetting policy gives the best accuracy–staleness–cost trade-off over long multi-session interactions?

Full write-up: [`THESIS_REPORT.md`](THESIS_REPORT.md) · Sprint plan: [`docs/BLUEPRINT.md`](docs/BLUEPRINT.md)

## Why

Three 2026 surveys name **learned forgetting** and **continual consolidation** as open problems in agent memory ([arXiv:2603.07670](https://arxiv.org/abs/2603.07670), [arXiv:2602.06052](https://arxiv.org/abs/2602.06052), [arXiv:2605.06716](https://arxiv.org/abs/2605.06716)), and [arXiv:2605.12978](https://arxiv.org/abs/2605.12978) showed that naive continual LLM-driven updates *degrade* memory. DRIFT provides a controlled harness to compare forgetting policies on identical memory substrates.

## Architecture

```
conversation sessions
        │  extract_facts()  (LLM or offline mock, + regex predicate upgrade)
        ▼
BitemporalGraph ──── every fact carries two timelines:
  facts (edges)        valid time:     t_valid_start .. t_invalid_at
        │              ingestion time: t_ingested
        │  contradiction on functional predicates (lives_in, works_at, ...)
        │  closes the old fact's valid window — non-lossy until a policy prunes
        ▼
Policy (P0–P4) ── on_write gate · after_session maintenance · on_retrieve filter
        ▼
hybrid retrieval (embedding cosine + lexical overlap + recency)
        ▼
answer LLM ──► LLM judge (different model family) + token-F1
```

### The five policies

| ID | Policy | Mechanism |
|---|---|---|
| P0 | No forgetting | Append-only baseline |
| P1 | TTL decay | Prune facts older than `ttl_days` |
| P2 | Contradiction invalidation | Exclude superseded facts at retrieval; prune after grace period (exploits bitemporal fields) |
| P3 | Novelty gate | Reject near-duplicate writes (SAGE-style, [arXiv:2605.30711](https://arxiv.org/abs/2605.30711)) |
| P4 | LLM consolidation | Periodic LLM keep/drop review + near-duplicate merge (the risky policy per arXiv:2605.12978) |

## Setup

Core framework is **stdlib-only** (Python ≥ 3.10). No API keys needed for tests or the smoke benchmark.

```bash
git clone <this repo> && cd DRIFT
pip install pytest            # only dev dependency

make test     # 18 unit/integration tests, fully offline
make smoke    # full pipeline on the synthetic dataset with the mock provider
make tables   # markdown result tables from results/smoke
```

### Running with real LLM APIs (free tiers)

DRIFT speaks the OpenAI-compatible protocol. Get free keys (see [free-llm-api-resources](https://github.com/cheahjs/free-llm-api-resources)):

| Provider | Env var | Free tier | Suggested role |
|---|---|---|---|
| [Cerebras](https://cloud.cerebras.ai/) | `CEREBRAS_API_KEY` | 14.4k req/day | fact extraction (heaviest load) |
| [Groq](https://console.groq.com) | `GROQ_API_KEY` | 1k req/day (70B) | question answering |
| [Google AI Studio](https://aistudio.google.com) | `GEMINI_API_KEY` | varies by model | judge (independent family) |
| [NVIDIA NIM](https://build.nvidia.com/models) | `NVIDIA_API_KEY` | 40 req/min | model-diversity runs |
| [OpenRouter](https://openrouter.ai) | `OPENROUTER_API_KEY` | 50 req/day | spillover |

Optional local embeddings on Apple Silicon (recommended — removes the rate-limit bottleneck):

```bash
brew install ollama && ollama pull nomic-embed-text
```

Then:

```bash
export CEREBRAS_API_KEY=... GROQ_API_KEY=... GEMINI_API_KEY=...
make locomo-data   # downloads LoCoMo (Maharana et al., ACL 2024) and converts it
make locomo        # full experiment matrix; resumable, all calls disk-cached
```

Every LLM call is cached in `.drift_cache/` (SHA-256 of provider+model+prompt), so interrupted runs resume free and reruns cost zero API calls.

## Repository layout

```
drift/
  providers.py          # OpenAI-compat client, rate limiter, disk cache, MockProvider
  embeddings.py         # HashingEmbedder (offline) / OllamaEmbedder (local)
  memory/graph.py       # BitemporalGraph: facts with valid+ingestion time, hybrid search
  memory/extraction.py  # LLM triple extraction + regex functional-predicate upgrade
  policies.py           # P0-P4 + registry ("P1:ttl_days=14" spec strings)
  pipeline.py           # ingest_session / answer_question / judge_answer / token_f1
  runner.py             # resumable {policy} x {model} experiment matrix
configs/                # smoke.json (offline), locomo.json (free-API template)
data/                   # synthetic_smoke.json; LoCoMo via scripts/download_locomo.py
tests/                  # pytest suite (offline, no keys required)
analysis/               # report table generation
docs/BLUEPRINT.md       # 7-day execution plan
THESIS_REPORT.md        # the thesis document (updated as benchmarks complete)
```

## Current results (smoke benchmark, offline mock provider)

| Policy | Accuracy | Staleness | Active facts |
|---|---|---|---|
| P0 no forgetting | 0.714 | 0.286 | 12 |
| P1 TTL decay | 0.500 | 0.071 | 6 |
| **P2 contradiction invalidation** | **0.929** | **0.000** | 9 |
| P3 novelty gate | 0.714 | 0.286 | 11 |
| P4 LLM consolidation | 0.714 | 0.286 | 11 |

Never forgetting causes stale answers; naive TTL forgetting destroys recall; **structure-aware forgetting (P2) dominates both**. See `THESIS_REPORT.md` §6 for analysis. LoCoMo results with real models: pending (requires API keys).

## Extending DRIFT

- **New policy:** subclass `Policy` in `drift/policies.py`, register in `POLICY_REGISTRY`, add to a config.
- **New provider:** any OpenAI-compatible endpoint — add a preset in `drift/providers.py`.
- **New dataset:** emit the schema in `drift/runner.py:load_dataset` (see `scripts/download_locomo.py` for a converter example).
- **New metrics:** records carry per-question retrieval traces; aggregate in `analysis/`.

## Citation & license

Apache-2.0 (see LICENSE). If you use DRIFT, please cite the thesis report in this repository.
