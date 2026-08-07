# DRIFT

**Decay Rates in Forgetful Bitemporal Memory.**

A controlled framework for answering one question about your agent: **which forgetting policy should its memory use?**

DRIFT is two things. It is a bitemporal memory you can drop into any agent in five lines, and it is the harness that measured which forgetting rule is worth using. The second is why you should trust the first.

```python
from drift import Memory

mem = Memory(policy="P2", functional_predicates=["lives_in", "works_at"])
mem.observe(["user: I moved to Seattle."], when=time.time())
print(mem.context("Where does the user live?"))
```

Zero dependencies. Runs offline. 99 tests in 0.2 seconds without an API key.

**Authors:** Nandan Hemanth, Hao Wang · Stevens Institute of Technology
**Paper:** [`paper/REPORT.md`](paper/REPORT.md)

---

## Contents

- [The problem](#the-problem)
- [Hypothesis](#hypothesis)
- [What the results show](#what-the-results-show)
- [Which policy should I use](#which-policy-should-i-use)
- [Install](#install)
- [Integrate DRIFT into your agent](#integrate-drift-into-your-agent)
- [Run the experiments](#run-the-experiments)
- [Command reference](#command-reference)
- [Repository layout](#repository-layout)
- [Extending DRIFT](#extending-drift)
- [Citing](#citing)

---

## The problem

An assistant is told "I live in Boston". Three months later it is told "I moved to Seattle". Both facts are in memory, both are semantically close to "where do I live", and retrieval ranks by similarity and recency. The older fact often comes back alongside the newer one, and the model answers from a value that is no longer true.

This is not a retrieval failure. The correct fact was stored and could be found. It is a memory hygiene failure: nothing marks the older fact as no longer current, and nothing removes it.

Existing memory systems (MemGPT, Zep, Mem0, A-MEM) solve storage and retrieval well. The rule that decides what to discard is usually chosen rather than measured. DRIFT measures it.

## Hypothesis

> Selective forgetting grounded in bitemporal structure improves an agent's answer quality and cost profile relative to both append-only memory and to structure-blind or novelty-based forgetting.

Four research questions:

| | Question | Verdict |
|---|---|---|
| RQ1 | Does append-only memory surface superseded facts? | Yes, confirmed on both benchmarks, CIs exclude zero |
| RQ2 | Which policy has the best accuracy, staleness and cost trade-off? | P2, replicated on both benchmarks |
| RQ3 | Does *bitemporal* structure beat structure-blind forgetting? | Yes, p < 0.001 on both accuracy and staleness |
| RQ4 | Do rankings survive multi-agent use? | Validated offline; real-data campaign outstanding |

Method: hold the substrate, extraction, retrieval, answer model and judge constant. Vary only the forgetting policy across seven settings. Full write-up in [`paper/REPORT.md`](paper/REPORT.md).

## What the results show

Two benchmarks. Seven policies, two answer models each. Percentile bootstrap 95 percent CIs, 5,000 resamples.

| Policy | What it does | FC accuracy | MQuAKE-T accuracy | FC staleness | MQ staleness | Tokens/q | Facts kept |
|---|---|---|---|---|---|---|---|
| NOMEM | no memory (floor) | 0.000 | 0.000 | 0.000 | 0.000 | 242 | n/a |
| **P0** | never forget | **0.840** | **0.969** | 0.030 | 0.052 | 814 | 100% |
| P1 | TTL decay | 0.630 | 0.870 | 0.020 | 0.026 | 803 | 55 to 66% |
| **P2** | **bitemporal invalidation** | **0.840** | **0.969** | 0.025 | 0.036 | **716** | **85 to 93%** |
| P3 | novelty write gate | 0.665 | 0.792 | **0.140** | **0.161** | 806 | 88 to 92% |
| P4 | LLM consolidation | 0.800 | 0.953 | 0.060 | 0.057 | 809 | 97% |
| P5 | topology consolidation (time-blind) | 0.795 | 0.802 | 0.035 | **0.214** | 814 | 96% |

Three findings, each replicated on both benchmarks:

**1. Bitemporal forgetting is free.** P2 is statistically tied with the accuracy ceiling. Paired McNemar returns 3 to 3 (p = 1.000) and 2 to 2 (p = 1.000), while P2 spends **12 percent fewer tokens** and stores 6 to 15 percent fewer facts.

**2. Novelty gating causes staleness.** P3 shows 4.5 to 4.7 times P2's staleness, p < 0.001. A correction is textually near-identical to the fact it corrects, so a write gate rejects it as a duplicate and the correction never enters memory. No downstream retrieval can recover a value that was never stored. On MQuAKE-T that means answering "Elizabeth II" for the current UK head of state, permanently.

**3. Bitemporal beats structure-blind.** P5 is deliberately structure-aware but time-blind: it resolves competing facts by corroboration count instead of valid time. On MQuAKE-T, P2 beats it 34 to 2 on accuracy and 3 to 37 on staleness, both p < 0.001. A long-serving predecessor accumulates more corroborating mentions than a recent successor, so corroboration-count consolidation systematically prefers the outdated fact. This attributes the advantage to bitemporal semantics specifically, not to graph structure in general.

Cross-benchmark rank agreement: **Spearman rho = 0.891**.

Benchmarks used, and why these two:

| Benchmark | Regime | `stale_answer` coverage |
|---|---|---|
| MemoryAgentBench FactConsolidation (ICLR 2026) | injected supersession, counterfactual golds | 65 of 100 |
| MQuAKE-T (EMNLP 2023) | real Wikidata drift 2021 to 2023 | 96 of 96 |
| LoCoMo | conversational | **0 of 300** |
| LongMemEval | conversational | **0 of 150** |

The staleness metric fires only on questions annotated with the superseded value. The two most-used agent-memory benchmarks carry no such annotation, so staleness reads 0.000 on them for structural reasons rather than policy reasons. Finding two benchmarks that support the metric is part of the contribution.

## Which policy should I use

**If your agent tracks facts that get corrected over time** (a personal assistant, a CRM, an ops agent tracking system state): use **P2**, declare your functional predicates, and do **not** use a novelty write gate. A gate trades roughly 12 percent memory saving for a permanent inability to learn corrections.

**If your facts are append-only and never revised:** P0 is fine and the question does not arise.

**Do not assume; measure.** P3 was statistically tied with the best policy on the first campaign and is the worst policy on both fact benchmarks. Which policy wins depends on whether your facts get corrected. That is what this harness is for: point it at your own data before you commit.

One caveat established by ablation. Setting `functional_predicates` correctly buys P2 **nothing in accuracy and all of its efficiency**. P2 is safe to enable untuned, since it cannot make an agent worse, but it only pays for itself if the predicates that admit a single true value are declared.

## Install

```bash
git clone https://github.com/nandanhemanth/DRIFT.git
cd DRIFT
pip install -e ".[all]"     # or: pip install -e .   for the zero-dependency core
make test                   # 99 tests, no API keys, no network
```

Python 3.10 or newer. The core has **no dependencies**. `pytest` is needed only for tests and `matplotlib` only for figures.

For real semantic retrieval, install [Ollama](https://ollama.com) and pull an embedder:

```bash
ollama pull nomic-embed-text
```

For real-API experiments, copy `.env.example` to `.env` and add keys. Any OpenAI-compatible endpoint works.

## Integrate DRIFT into your agent

DRIFT is agent-framework agnostic. It is a memory object with two methods; wire it to whatever loop you already have.

```python
import time
from drift import Memory

mem = Memory(
    policy="P2",                              # the measured recommendation
    provider="openrouter:z-ai/glm-5.2",       # used only for triple extraction
    embedder="ollama:nomic-embed-text",       # "hashing" for offline/deterministic
    functional_predicates=["lives_in", "works_at", "assigned_to", "status"],
)

# 1. After each turn or session, record what happened.
mem.observe(["user: I moved to Seattle.", "assistant: Noted."], when=time.time())

# 2. Before each model call, retrieve what matters and paste it into the prompt.
memory_block = mem.context("Where does the user live?", k=8)
response = your_llm(f"MEMORY:\n{memory_block}\n\nQUESTION: {question}")
```

That is the whole interface. Everything below is optional.

| Call | Purpose |
|---|---|
| `mem.observe(lines, when)` | Extract triples, apply the write gate, run policy maintenance. Returns `{"extracted", "written"}`; the gap is how many writes the policy rejected. |
| `mem.remember(subject, predicate, object_, when)` | Write one structured fact directly, skipping LLM extraction. |
| `mem.recall(query, k, now)` | Retrieve `Fact` objects after the policy's retrieval filter. |
| `mem.context(query, k)` | The same, rendered as a dated memory block ready for a prompt. |
| `mem.stats()` | Total, active, superseded-but-present, pruned, write rejections. |
| `mem.snapshot()` | Serialisable event log; replayable through `analysis/timeline.py`. |
| `mem.graph` | The underlying `BitemporalGraph` for anything the facade does not cover. |

**Two settings decide whether this helps you.**

`policy` is the subject of this whole study. Start at `"P2"`.

`functional_predicates` declares which predicates admit exactly one true object at a time. Pass a list, or `"*"` if every predicate in your domain is single-valued. Leaving it at the default keeps a personal-conversation set (`lives_in`, `works_at`, `job`, `relationship_status`, `owns_pet`, `studies`, `located_in`, `age`), under which a domain outside personal chat records **zero** invalidations and P2 has nothing to act on.

Pass the time a fact **became true**, not the time you ingested it, when the two differ. That distinction is the point of a bitemporal store.

### Evaluate a policy on your own data

The recommendation above is measured on fact corpora. To check it on your workload:

1. Export your agent's history into DRIFT's dataset schema:

```json
{"conversations": [{
  "id": "user-42",
  "sessions":  [{"time": 1704067200.0, "lines": ["user: ...", "assistant: ..."]}],
  "questions": [{"question": "...", "answer": "...",
                 "category": "...", "stale_answer": "..."}]
}]}
```

2. Annotate `stale_answer` on any question whose answer changed over time. Accuracy works without it; **staleness cannot fire without it**. Recover it deterministically from your data's structure. An LLM annotator was tried and produced 1 usable annotation out of 78.

3. Write a config. Experiments are data, not code:

```json
{"dataset": "data/yours.json",
 "results_dir": "artifacts/results/yours",
 "embedder": "ollama:nomic-embed-text",
 "retrieval_k": 25,
 "functional_predicates": ["lives_in", "assigned_to"],
 "models": ["openrouter:z-ai/glm-5.2"],
 "policies": ["NOMEM", "P0", "P2", "P3"]}
```

4. Run and read:

```bash
python -m drift.runner --config configs/yours.json
make figures record dashboard
python src/analysis/compare_datasets.py artifacts/results/yours artifacts/results/mquake_t
```

5. Ship the policy that wins on your data.

## Run the experiments

Everything offline, no keys, in under a minute:

```bash
make test          # 99 tests
make smoke         # full pipeline on synthetic data, MockProvider
make swarm         # three multi-agent topologies, synthetic
make figures dashboard
```

The real campaign, resumable and disk-cached throughout:

```bash
make fc-data && make fc            # FactConsolidation, 14 cells
make mq-data && make mq            # MQuAKE-T, 14 cells
make mq-ablation                   # the functional_predicates probe, 3 cells
make compare                       # cross-dataset statistics -> paper/generalization.md
make replay                        # scrubbable P2-vs-P3 memory replay
```

Every provider call is cached by SHA-256 of the request, so an interrupted run resumes at zero cost and a rerun is bit-for-bit reproducible. Failures are caught per cell, so one exhausted quota costs a cell rather than a campaign.

### Watch memory build

```bash
make live          # then open artifacts/results/mquake_t/live.html
```

Facts appear as they are ingested and turn red the moment a contradiction closes their valid-time window. The monitor writes atomically and swallows every exception, so it cannot break the run it is watching.

### Replay a finished run

```bash
make replay
```

A bitemporal fact carries its own history, so a saved snapshot is a complete event log. The replay reconstructs the whole run from it: no rerun, no instrumentation. Side-by-side mode shows P2 closing a superseded window in the same session that P3 rejects the correction outright.

## Command reference

`make help` prints this list from the Makefile itself.

### Setup and verification

| Command | What it does |
|---|---|
| `make install` | Editable install with dev and analysis extras |
| `make test` | 99 offline tests. No API keys, no network, 0.2 s |

### Offline, free, deterministic

| Command | What it does |
|---|---|
| `make smoke` | Full pipeline on synthetic data with `MockProvider` |
| `make swarm` | Three multi-agent topologies on synthetic data |

### Dataset preparation

| Command | What it does |
|---|---|
| `make fc-data` | Download MemoryAgentBench FactConsolidation, single-hop 6k. 65/100 annotated |
| `make mq-data` | Download MQuAKE-T and convert. Real Wikidata drift, 96/96 annotated |
| `make locomo-data` | Download LoCoMo and derive a stratified 300-question sample |
| `make longmemeval-data` | Download LongMemEval, 150 questions |
| `make ku-data` | Build the LongMemEval knowledge-update subset, oracle variant |
| `make ku-data-s` | The same subset under realistic retrieval pressure |

### Experiments (need `.env` keys)

| Command | What it does |
|---|---|
| `make fc` | FactConsolidation matrix, 7 policies x 2 models |
| `make mq` | MQuAKE-T matrix, 7 policies x 2 models |
| `make mq-ablation` | Overfit probe: MQuAKE-T without `functional_predicates` declared, 3 cells |
| `make locomo` | LoCoMo matrix |
| `make longmemeval` | LongMemEval matrix |
| `make ku` / `make ku-s` | Knowledge-update matrices |
| `make swarm-real` | Multi-agent matrix on real data, 7 policies x 3 topologies |
| `make real-all` | The whole campaign: download, run every matrix, analyse, compact |

### Analysis and artifacts

| Command | What it does |
|---|---|
| `make tables` | Print markdown summary tables for a results directory |
| `make figures` | 300 dpi figures for every populated results directory |
| `make record` | Evidence pack per results dir: tables, radar, per-category, memory views, per-cell graph and replay views |
| `make dashboard` | Self-contained interactive dashboard covering every benchmark |
| `make compare` | Cross-dataset table: ranks, Spearman rho, paired McNemar, annotation coverage |
| `make replay` / `make replay-fc` | Scrubbable P2-vs-P3 memory replay |
| `make live` | Run a matrix while publishing a live memory view |
| `make generalization` | The full generalization argument end to end |

### Housekeeping

| Command | What it does |
|---|---|
| `make compact` | Drop embedding vectors from saved cells. 230 MB to 6 MB, lossless for every analysis tool |
| `make clean` | Remove caches and offline results |
| `make clean-all` | Also remove every real-data result. Destructive |

## Repository layout

```
DRIFT/
├── src/
│   ├── drift/                  the framework
│   │   ├── memory_api.py       Memory: the integration surface
│   │   ├── memory/graph.py     BitemporalGraph and Fact: the substrate
│   │   ├── memory/extraction.py    LLM triple extraction + regex upgrade
│   │   ├── policies.py         Policy base class, NOMEM and P0-P5, registry
│   │   ├── pipeline.py         ingest, answer, judge
│   │   ├── runner.py           the single-agent experiment matrix
│   │   ├── swarm.py            three multi-agent topologies
│   │   ├── providers.py        stdlib OpenAI-compatible client, rate limits, disk cache
│   │   ├── embeddings.py       HashingEmbedder (offline) and OllamaEmbedder
│   │   └── live.py             opt-in live memory monitor
│   └── analysis/               read-only consumers of the result schema
│       ├── report_tables.py    markdown tables
│       ├── plots.py            300 dpi figures
│       ├── dashboard.py        interactive HTML dashboard
│       ├── record.py           evidence packs
│       ├── timeline.py         scrubbable bitemporal replay
│       ├── compare_datasets.py cross-dataset statistics
│       └── graphify_export.py  node-link export for NetworkX and Gephi
├── configs/                    experiments as data, one JSON per matrix
├── scripts/                    benchmark converters, results compaction
├── tests/                      99 offline tests
├── data/                       converted datasets
├── artifacts/                  everything the runs produced
│   ├── results/                one JSON per cell, plus figures and evidence packs
│   ├── replays/                interactive memory replays
│   └── dashboard.html
└── paper/                      everything for the write-up and the defence
    ├── REPORT.md               the full report
    ├── generalization.md       cross-dataset statistics, regenerated by make compare
    ├── REPO_GUIDE.md           maps each claim to the code that produces it
    ├── references/             all 14 cited papers as PDFs
    ├── drift_paper.tex/.bib    LaTeX sources
    └── archive/                superseded drafts, kept for provenance
```

## Extending DRIFT

**Add a forgetting policy.** Subclass `Policy`, implement any of the three hooks, register it. Nothing else in the codebase changes.

```python
# src/drift/policies.py
class P6MyPolicy(Policy):
    name = "P6_my_policy"

    def on_write(self, fact: dict, graph: BitemporalGraph) -> bool:
        return True                       # False rejects the write

    def after_session(self, graph, provider, now: float) -> None:
        ...                               # periodic maintenance

    def on_retrieve(self, facts: list[Fact], now: float) -> list[Fact]:
        return facts                      # filter or rerank

POLICY_REGISTRY["P6"] = P6MyPolicy
```

Then add `"P6"` to a config's `policies` list. Spec strings take arguments: `"P6:threshold=0.8"`.

**Add a benchmark.** Write a converter that emits the dataset schema above, then a config pointing at it. `scripts/download_mquake.py` is the cleanest template.

**Add a provider.** Add a preset in `src/drift/providers.py`. Any OpenAI-compatible endpoint works.

**Add an analysis.** Everything in `src/analysis/` is a read-only consumer of the runner output schema. Write another one.

## Design commitments

- **Zero dependencies in the core.** `pyproject.toml` declares `dependencies = []` and it stays that way.
- **Offline-verifiable.** `MockProvider` and `HashingEmbedder` run the entire pipeline with no network, so the mechanics can be checked before anyone spends a cent.
- **Reproducible.** Every provider call is cached by SHA-256 of provider, model, prompt, temperature and max tokens.
- **Resumable.** One file per experiment cell; completed cells are skipped. `--force` reruns.
- **Non-destructive substrate.** Contradiction closes a valid-time window but never deletes. Only a policy hides or removes data. That separation is what keeps the policy the sole independent variable.

## Citing

```bibtex
@misc{hemanth2026drift,
  author = {Hemanth, Nandan and Wang, Hao},
  title  = {{DRIFT}: Decay Rates in Forgetful Bitemporal Memory},
  year   = {2026},
  school = {Stevens Institute of Technology},
  note   = {https://github.com/nandanhemanth/DRIFT}
}
```

Full report, statistics and references: [`paper/REPORT.md`](paper/REPORT.md).

## License

Apache 2.0. See [`LICENSE`](LICENSE).
