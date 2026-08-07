# DRIFT - make targets
#
# Every target is documented in README.md under "Command reference".
# `make help` prints the same list from these comments.
#
# The package lives in src/, so PYTHONPATH is set here and no install is needed
# to run anything below. `pip install -e .` also works and is what you want when
# importing DRIFT from another project.

export PYTHONPATH := src

PY ?= python

.PHONY: help install test smoke swarm \
        locomo-data locomo longmemeval-data longmemeval \
        ku-data ku-data-s ku ku-s fc-data fc mq-data mq mq-ablation \
        tables figures dashboard record replay replay-fc live \
        compare generalization real-all compact clean clean-all

# ---------------------------------------------------------------- help

help:
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) \
		| awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-18s\033[0m %s\n", $$1, $$2}'

# ---------------------------------------------------------------- setup

install: ## Install DRIFT in editable mode with dev and analysis extras
	$(PY) -m pip install -e ".[all]"

test: ## Run the offline test suite (no API keys, no network)
	$(PY) -m pytest tests/ -v

# ---------------------------------------------------------------- offline

smoke: ## Full pipeline on synthetic data with MockProvider (offline, free)
	$(PY) -m drift.runner --config configs/smoke.json

swarm: ## Multi-agent topologies on synthetic data (offline, free)
	$(PY) -m drift.swarm --config configs/swarm_smoke.json

# ---------------------------------------------------------------- datasets
#
# Each converter turns a public benchmark into DRIFT's dataset schema. Only
# FactConsolidation and MQuAKE-T carry the `stale_answer` annotation that the
# staleness metric needs; LoCoMo (0/300) and LongMemEval (0/150) do not, which
# is why staleness reads 0.000 on them for structural reasons rather than
# policy reasons.

locomo-data: ## Download LoCoMo and derive a stratified 300-question sample
	$(PY) scripts/download_locomo.py
	$(PY) scripts/download_locomo.py --in data/locomo_drift.json \
		--out data/locomo_drift_sample.json --sample-size 300

longmemeval-data: ## Download LongMemEval (150 questions)
	$(PY) scripts/download_longmemeval.py --max-questions 150

ku-data: ## Build the LongMemEval knowledge-update subset (oracle variant)
	$(PY) scripts/build_longmemeval_ku.py --variant oracle

ku-data-s: ## Build the knowledge-update subset under retrieval pressure
	$(PY) scripts/build_longmemeval_ku.py --variant s --max-sessions 12

fc-data: ## Download MemoryAgentBench FactConsolidation (single-hop, 6k)
	$(PY) scripts/download_factconsolidation.py --context 6k --hop sh

mq-data: ## Download MQuAKE-T and convert (real Wikidata drift, 96/96 annotated)
	$(PY) scripts/download_mquake.py --dataset MQuAKE-T --hop sh

# ---------------------------------------------------------------- experiments
#
# Real-API runs need keys in .env (copy .env.example). Every provider call is
# disk-cached by SHA-256, so an interrupted campaign resumes for free and a
# rerun is bit-for-bit reproducible. Completed cells are skipped; --force reruns.

locomo: ## Run the LoCoMo matrix
	$(PY) -m drift.runner --config configs/locomo.json

longmemeval: ## Run the LongMemEval matrix
	$(PY) -m drift.runner --config configs/longmemeval.json

ku: ## Run the LongMemEval knowledge-update matrix
	$(PY) -m drift.runner --config configs/longmemeval_ku.json

ku-s: ## Run the knowledge-update matrix under retrieval pressure
	$(PY) -m drift.runner --config configs/longmemeval_ku_s.json

fc: ## Run the FactConsolidation matrix (7 policies x 2 models)
	$(PY) -m drift.runner --config configs/factconsolidation.json

mq: ## Run the MQuAKE-T matrix (7 policies x 2 models)
	$(PY) -m drift.runner --config configs/mquake_t.json

mq-ablation: ## Overfit probe: MQuAKE-T without functional_predicates declared
	$(PY) -m drift.runner --config configs/mquake_t_ablation.json

swarm-real: ## Run the multi-agent matrix on real data (7 policies x 3 topologies)
	$(PY) -m drift.swarm --config configs/swarm_real.json

# ---------------------------------------------------------------- analysis

tables: ## Print markdown summary tables for a results directory
	$(PY) src/analysis/report_tables.py artifacts/results/mquake_t

figures: ## Regenerate 300-dpi figures for every populated results directory
	-$(PY) src/analysis/plots.py artifacts/results/smoke
	-$(PY) src/analysis/plots.py artifacts/results/swarm_smoke --swarm
	-$(PY) src/analysis/plots.py artifacts/results/locomo
	-$(PY) src/analysis/plots.py artifacts/results/factconsolidation
	-$(PY) src/analysis/plots.py artifacts/results/mquake_t

record: ## Build the evidence pack (tables, radar, graphs, replays) per results dir
	$(PY) src/analysis/record.py artifacts/results/*

dashboard: ## Build the self-contained interactive dashboard
	$(PY) src/analysis/dashboard.py artifacts/results/* -o artifacts/dashboard.html

compare: ## Cross-dataset table: ranks, Spearman rho, paired McNemar
	$(PY) src/analysis/compare_datasets.py \
		artifacts/results/factconsolidation artifacts/results/mquake_t \
		--out paper/generalization.md

# ---------------------------------------------------------------- visualisation
#
# The replay is built entirely from saved snapshots. A bitemporal fact carries
# its own history (t_ingested, t_invalid_at, t_pruned), so a final snapshot is a
# complete event log and no rerun or instrumentation is needed.

replay: ## Scrubbable P2-vs-P3 memory replay for MQuAKE-T
	$(PY) src/analysis/timeline.py artifacts/results/mquake_t --policies P2,P3 \
		-o artifacts/replays/replay_mquake_P2_vs_P3.html

replay-fc: ## Scrubbable P2-vs-P3 memory replay for FactConsolidation
	$(PY) src/analysis/timeline.py artifacts/results/factconsolidation --policies P2,P3 \
		-o artifacts/replays/replay_fc_P2_vs_P3.html

live: ## Run MQuAKE-T while publishing a live memory view you can open in a browser
	$(PY) -m drift.runner --config configs/mquake_t.json --live

# ---------------------------------------------------------------- campaigns

generalization: mq-data mq mq-ablation ## The full generalization argument end to end
	-$(PY) src/analysis/plots.py artifacts/results/mquake_t
	$(MAKE) compare
	-$(PY) src/analysis/record.py artifacts/results/mquake_t
	-$(MAKE) replay

real-all: ## The full real-data campaign: download, run every matrix, then analyse
	-$(PY) scripts/download_locomo.py
	-$(PY) scripts/download_longmemeval.py --max-questions 150
	-$(PY) scripts/build_longmemeval_ku.py --variant oracle
	-$(PY) scripts/download_factconsolidation.py --context 6k --hop sh
	-$(PY) scripts/download_mquake.py --dataset MQuAKE-T --hop sh
	$(PY) -m drift.runner --config configs/locomo.json
	$(PY) -m drift.runner --config configs/longmemeval.json
	$(PY) -m drift.runner --config configs/longmemeval_ku.json
	$(PY) -m drift.runner --config configs/factconsolidation.json
	$(PY) -m drift.runner --config configs/mquake_t.json
	$(PY) -m drift.runner --config configs/mquake_t_ablation.json
	$(PY) -m drift.swarm --config configs/swarm_real.json
	$(MAKE) figures record dashboard compare replay
	$(MAKE) compact

# ---------------------------------------------------------------- housekeeping

compact: ## Drop embedding vectors from saved cells (230 MB -> 6 MB, lossless for analysis)
	$(PY) scripts/compact_results.py artifacts/results

clean: ## Remove caches and offline results
	rm -rf .drift_cache artifacts/results/smoke artifacts/results/swarm_smoke \
		__pycache__ .pytest_cache src/**/__pycache__

clean-all: clean ## Also remove every real-data result (destructive)
	rm -rf artifacts/results/* artifacts/replays/* artifacts/dashboard.html
