# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

DRIFT is a research framework (thesis project) for comparing *forgetting policies* in LLM agent memory over a fixed bitemporal knowledge-graph substrate. The independent variable under test is always the policy (NOMEM, P0-P5); everything else (substrate, retrieval, extraction, judging) is held constant. See `README.md` and `docs/REPO_GUIDE.md` (paper-shaped map of claims -> code) for the full research narrative; `THESIS_REPORT.md` is the thesis writeup itself.

Core framework is **stdlib-only** (`pyproject.toml`: `dependencies = []`). No network/API keys are needed to run tests or the offline smoke benchmark — only `pytest` (dev) and `matplotlib` (analysis) are ever required.

## Commands

```bash
make test              # pytest tests/ -v — 25 offline tests, no keys needed
python -m pytest tests/test_policies.py -v          # single test file
python -m pytest tests/test_policies.py::test_name  # single test

make smoke             # full pipeline on synthetic data with MockProvider (offline)
make swarm             # multi-agent topologies, offline (swarm_smoke.json)
make tables            # markdown tables from results/smoke
make figures           # 300-dpi PNGs into results/*/figures/
make dashboard         # self-contained interactive HTML -> docs/dashboard.html
make record            # evidence pack (tables/radar/graph views) -> results/*/report_pack/

make locomo-data       # download + convert LoCoMo dataset
make longmemeval-data  # download + convert LongMemEval dataset (--max-questions 150)
make locomo            # run configs/locomo.json (needs real API keys in .env)
make longmemeval       # run configs/longmemeval.json
make swarm-real        # run configs/swarm_real.json (model-diverse worker pool)
make real-all          # the full real-data campaign: download -> locomo -> longmemeval -> swarm -> figures -> dashboard -> record

make clean             # rm -rf .drift_cache results/smoke __pycache__ .pytest_cache
```

Real-API runs need keys in `.env` (copy `.env.example`; loaded automatically by `drift/providers.py:load_dotenv`, repo-root-relative so it works from any cwd). Every `provider.complete()` call is disk-cached in `.drift_cache/` by SHA-256(provider, model, prompt, temperature) — reruns after interruption or quota exhaustion are free and results are bit-for-bit reproducible. `MockProvider` is offline/deterministic and used **only** for tests and the smoke benchmark, never for reported thesis results.

## Architecture

Everything flows through one pipeline, with the forgetting **policy** as the only pluggable stage:

```
session lines --extract_facts()--> BitemporalGraph (subject/predicate/object facts,
    each with valid-time window t_valid_start..t_invalid_at AND ingestion time t_ingested)
        |
    policy.on_write()   gates each write (reject near-duplicates, etc.)
        |
    contradiction on functional predicates closes the old fact's valid window
    (non-destructive — a policy must actively prune to lose data)
        |
    policy.after_session()   periodic maintenance (TTL prune / grace-period prune /
                              LLM consolidation / topology consolidation)
        |
    hybrid retrieval: 0.6 cosine + 0.3 lexical + 0.1 recency (graph.search)
        |
    policy.on_retrieve()   filters/reranks what the answer model sees
        |
    answer LLM --> LLM judge (different model family) + token-F1
```

Key modules (`drift/`):
- `memory/graph.py` — `BitemporalGraph`/`Fact`: the substrate. Facts carry both timelines; contradictions on functional predicates (lives_in, works_at, ...) close old windows; `provenance` tags which agent wrote a fact (used for cross-writer invalidation accounting in swarm experiments).
- `memory/extraction.py` — LLM triple extraction + a deterministic regex upgrade for functional predicates, so contradiction detection doesn't depend on extractor luck.
- `policies.py` — `Policy` base class with exactly three hooks (`on_write`, `after_session`, `on_retrieve`); NOMEM/P0-P5 subclasses; `POLICY_REGISTRY` + `make_policy("P1:ttl_days=14")` spec-string parser. **Adding a policy = subclass + register here + reference from a config's `"policies"` list.**
- `pipeline.py` — the three pure functions above the policy layer: `ingest_session`, `answer_question`, `judge_answer` (+ `token_f1`). Policy behavior is invoked from here but never hardcoded here.
- `providers.py` — stdlib `urllib` OpenAI-compatible client, per-provider rate limiting, the disk cache, `.env` loading, `MockProvider`. **Adding a provider = add a preset here** (any OpenAI-compatible endpoint).
- `embeddings.py` — `HashingEmbedder` (offline, deterministic) vs `OllamaEmbedder` (local, real semantics — needs `ollama pull nomic-embed-text`).
- `runner.py` — the single-agent experiment matrix: `{policy} x {model}` over a dataset, one JSON per cell in `results_dir`, skips cells whose output file already exists (resumable), `--force` to rerun. `load_dataset()` defines the dataset schema new datasets must emit.
- `swarm.py` — three multi-agent topologies over the same substrate/pipeline/policies: `shared` (N writers -> one graph, tests cross-writer contradiction handling), `independent` (private graphs, partial seeded observation, reports mean+/-std), `orchestrator` (router LLM + specialist workers over one shared graph). Same resumable-cell pattern as `runner.py`.

Configs (`configs/*.json`) are experiments-as-data: dataset path, policies list, model(s), embedder, results_dir. Adding a benchmark or a matrix variant is usually just a new config file, not new code.

`analysis/` turns `results/*/*.json` into markdown tables (`report_tables.py`), matplotlib figures (`plots.py`), a self-contained interactive HTML dashboard (`dashboard.py`), and the evidence-pack generator (`record.py`) — all read-only consumers of the runner/swarm output schema.

## Working in this repo

- Runner/swarm failures are caught per-cell (`except (RuntimeError, OSError)`) so one dead provider or quota exhaustion doesn't kill a whole campaign — completed cells are cached and the run is designed to resume, not to be retried in a loop.
- Contradiction closing is non-destructive by design: only a policy's `after_session`/`on_retrieve` hooks actually hide or delete data. Keep that separation when touching `graph.py` or `policies.py`.
- `THESIS_REPORT.md` and `docs/REPO_GUIDE.md` map specific numeric claims to exact code paths (see REPO_GUIDE's "Trace of One Number" appendix) — if you change substrate/policy/metric behavior, check whether a cited claim needs updating.
