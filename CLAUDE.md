# CLAUDE.md

Guidance for Claude Code (claude.ai/code) when working in this repository.

## What this is

DRIFT is a research framework for comparing *forgetting policies* in LLM agent memory over a fixed bitemporal knowledge-graph substrate. The independent variable under test is always the policy (NOMEM, P0-P5); everything else (substrate, retrieval, extraction, judging) is held constant.

Read `README.md` first, then `paper/REPORT.md` for the full write-up and `paper/REPO_GUIDE.md` for a paper-shaped map of claims to code.

The core is **stdlib-only** (`pyproject.toml`: `dependencies = []`). No network or API keys are needed to run tests or the offline smoke benchmark; only `pytest` (dev) and `matplotlib` (analysis) are ever required.

## Layout

```
src/drift/        the framework (importable as `drift`)
src/analysis/     read-only consumers of the runner output schema
configs/          experiments as data, one JSON per matrix
scripts/          benchmark converters and results compaction
tests/            99 offline tests
data/             converted datasets
artifacts/        everything the runs produced (results, replays, dashboard)
paper/            REPORT.md, references/, REPO_GUIDE.md, LaTeX sources
```

`PYTHONPATH=src` is exported by the Makefile, so no install is needed to run anything. `pip install -e .` also works and is what a third-party project uses.

## Commands

```bash
make help              # every target, generated from the Makefile comments
make test              # 99 offline tests, no keys needed
python -m pytest tests/test_policies.py -v          # single file
python -m pytest tests/test_policies.py::test_name  # single test

make smoke             # full pipeline on synthetic data with MockProvider (offline)
make swarm             # multi-agent topologies, offline
make figures record dashboard replay
make compare           # cross-dataset statistics -> paper/generalization.md

make fc-data && make fc          # FactConsolidation (needs .env keys)
make mq-data && make mq          # MQuAKE-T
make mq-ablation                 # the functional_predicates probe
make real-all                    # the whole campaign
make compact                     # strip embeddings from saved cells
```

Real-API runs need keys in `.env` (copy `.env.example`; loaded by `src/drift/providers.py:load_dotenv`, repo-root-relative so it works from any cwd). Every `provider.complete()` is disk-cached in `.drift_cache/` by SHA-256 of (provider, model, prompt, temperature, max_tokens), so reruns after interruption are free and results are bit-for-bit reproducible. `MockProvider` is offline and deterministic, used **only** for tests and the smoke benchmark, never for reported results.

## Architecture

Everything flows through one pipeline, with the forgetting **policy** as the only pluggable stage:

```
session lines --extract_facts()--> BitemporalGraph (subject/predicate/object facts,
    each with valid-time window t_valid_start..t_invalid_at, ingestion time
    t_ingested, and t_pruned once a policy removes it)
        |
    policy.on_write()   gates each write (reject near-duplicates, etc.)
        |
    contradiction on functional predicates closes the old fact's valid window
    (non-destructive: a policy must actively prune to lose data)
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

Key modules:

- `src/drift/memory_api.py` - `Memory`: the public integration surface for using DRIFT inside another agent. A thin composition of existing pieces; it adds no behaviour, and `tests/test_memory_api.py` pins that it makes identical decisions to the harness.
- `src/drift/memory/graph.py` - `BitemporalGraph`/`Fact`: the substrate. Facts carry both timelines plus `t_pruned`; contradictions on functional predicates close old windows; `provenance` tags which agent wrote a fact.
- `src/drift/memory/extraction.py` - LLM triple extraction plus a deterministic regex upgrade for functional predicates, so contradiction detection does not depend on extractor luck.
- `src/drift/policies.py` - `Policy` base class with exactly three hooks (`on_write`, `after_session`, `on_retrieve`); NOMEM/P0-P5 subclasses; `POLICY_REGISTRY` and the `make_policy("P1:ttl_days=14")` spec parser. **Adding a policy = subclass + register here + reference from a config.**
- `src/drift/pipeline.py` - the three pure functions above the policy layer: `ingest_session`, `answer_question`, `judge_answer` (plus `token_f1`).
- `src/drift/providers.py` - stdlib `urllib` OpenAI-compatible client, per-provider rate limiting, disk cache, `.env` loading, `MockProvider`. **Adding a provider = add a preset here.**
- `src/drift/embeddings.py` - `HashingEmbedder` (offline, deterministic) vs `OllamaEmbedder` (needs `ollama pull nomic-embed-text`).
- `src/drift/runner.py` - the single-agent matrix: `{policy} x {model}` over a dataset, one JSON per cell, skips completed cells, `--force` to rerun, `--live` to publish a live memory view. `load_dataset()` defines the schema new datasets must emit.
- `src/drift/swarm.py` - three multi-agent topologies over the same substrate and policies: `shared`, `independent`, `orchestrator`.
- `src/drift/live.py` - opt-in live monitor. Must never raise and never block; failures cost the view, not the run.

`src/analysis/` turns `artifacts/results/*/*.json` into tables, figures, an interactive dashboard, evidence packs, scrubbable bitemporal replays and cross-dataset statistics. All are read-only consumers of the runner output schema.

## Working in this repo

- Runner/swarm failures are caught per cell so one dead provider does not kill a campaign. Completed cells are cached; the run resumes rather than being retried in a loop.
- Contradiction closing is non-destructive by design: only a policy's `after_session`/`on_retrieve` hooks hide or delete data. Keep that separation when touching `graph.py` or `policies.py`.
- `paper/REPORT.md` and `paper/REPO_GUIDE.md` map specific numeric claims to exact code paths. If you change substrate, policy or metric behaviour, check whether a cited claim needs updating.
- Result cells are stored with embeddings stripped (`make compact`, 230 MB to 6 MB). Nothing in `src/analysis/` reads the vectors; they are recomputed on every run.
- Prose in this repo avoids em dashes. Keep it that way.
