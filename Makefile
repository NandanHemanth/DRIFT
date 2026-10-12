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
        compare generalization real-all compact clean clean-all \
        final-check judge-check final-pilot final-mq final-fc final-cm \
        grace-history grace-history-answers heldout-weights rq4 \
        preflight substrate final-report

# ---------------------------------------------------------------- help

help:
	@grep -E '^[a-zA-Z0-9_-]+:.*?## .*$$' $(MAKEFILE_LIST) \
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

convomem-data: ## Download ConvoMem changing-facts and convert (natural dialogue)
	$(PY) scripts/download_convomem.py --questions 100 --group-size 10

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

convomem: ## Run the ConvoMem matrix (7 policies x 2 models, pinned judge)
	$(PY) -m drift.runner --config configs/convomem.json

regrade: ## Regrade both published matrices with one pinned judge (answers cached)
	$(PY) -m drift.runner --config configs/regrade_mquake_t.json
	$(PY) -m drift.runner --config configs/regrade_factconsolidation.json

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

pdf: ## Render paper/DRIFT_SUMMARY.md to PDF (needs pandoc + texlive-xetex)
	bash scripts/build_pdf.sh paper/DRIFT_SUMMARY.md

pdf-report: ## Render the full paper/REPORT.md to PDF
	bash scripts/build_pdf.sh paper/REPORT.md

compare: ## Cross-dataset table: ranks, Spearman rho, paired McNemar
	$(PY) src/analysis/compare_datasets.py \
		artifacts/results/factconsolidation artifacts/results/mquake_t \
		--out paper/generalization.md

# ------------------------------------------------------- sensitivity analysis
#
# Answers "would a different constant have changed the conclusion?" for the
# retrieval weighting, retrieval depth, and every policy hyperparameter. The
# sweeps measure retrieval directly rather than end-task accuracy, so they cost
# no answer-model or judge calls: extraction is served from .drift_cache and
# embeddings come from local Ollama. Nothing here can change a published number.

deep-smoke: ## Deep 10x10x10 weight sensitivity, offline check on synthetic data (free)
	$(PY) -m analysis.deep_sensitivity plan    --config configs/deep_sensitivity_smoke.json
	$(PY) -m analysis.deep_sensitivity run     --config configs/deep_sensitivity_smoke.json
	$(PY) -m analysis.deep_sensitivity analyze --config configs/deep_sensitivity_smoke.json

deep-plan: ## Deep sensitivity stage 1: contexts for all 1,000 weightings, prints exact call count (no LLM calls)
	$(PY) -m analysis.deep_sensitivity plan --config configs/deep_sensitivity.json

deep-run: ## Deep sensitivity stage 2: answer and grade every unique prompt on Ollama (resumable)
	$(PY) -m analysis.deep_sensitivity run --config configs/deep_sensitivity.json

deep-analyze: ## Deep sensitivity stage 3: every analysis and figure, works on partial results
	$(PY) -m analysis.deep_sensitivity analyze --config configs/deep_sensitivity.json

deep-date-plan: ## Full 10x10x10, facts listed by date: stage 1 (no LLM calls)
	$(PY) -m analysis.deep_sensitivity plan --config configs/deep_sensitivity_bydate.json

deep-date-run: ## Full 10x10x10, facts listed by date: answer + grade, MQuAKE-T then ConvoMem (resumable)
	$(PY) -m analysis.deep_sensitivity run --config configs/deep_sensitivity_bydate.json

deep-date-analyze: ## Full 10x10x10, facts listed by date: report + figures (works on partial results)
	$(PY) -m analysis.deep_sensitivity analyze --config configs/deep_sensitivity_bydate.json

check-providers: ## Preflight: is every model in every config still reachable?
	$(PY) scripts/check_providers.py --all

check-convomem: ## Preflight the ConvoMem configs only
	$(PY) scripts/check_providers.py --config configs/sensitivity_convomem.json
	$(PY) scripts/check_providers.py --config configs/convomem.json

sensitivity-smoke: ## Offline sensitivity check on synthetic data (no keys, free)
	$(PY) -m analysis.sensitivity --config configs/sensitivity_smoke.json

sensitivity: ## Full sensitivity sweep on MQuAKE-T (needs Ollama, no paid calls)
	$(PY) -m analysis.sensitivity --config configs/sensitivity_mquake_t.json

sensitivity-fc: ## Full sensitivity sweep on FactConsolidation
	$(PY) -m analysis.sensitivity --config configs/sensitivity_factconsolidation.json

sensitivity-convomem: ## Full sensitivity sweep on ConvoMem
	$(PY) -m analysis.sensitivity --config configs/sensitivity_convomem.json

surface-convomem: ## Response surface on ConvoMem
	$(PY) -m analysis.retrieval_surface artifacts/sensitivity/convomem_sensitivity.json \
		--policy P2 --figures

sensitivity-validate: ## Check the retrieval proxy against graded answers from real cells
	$(PY) -m analysis.sensitivity --config configs/sensitivity_mquake_t.json --validate
	$(PY) -m analysis.sensitivity --config configs/sensitivity_factconsolidation.json --validate

surface: ## Response surface over the weight simplex: corners, Pareto front, ternary plots
	$(PY) -m analysis.retrieval_surface artifacts/sensitivity/mquake_t_sensitivity.json \
		--policy P2 --figures

surface-fc: ## Same response surface on FactConsolidation
	$(PY) -m analysis.retrieval_surface artifacts/sensitivity/factconsolidation_sensitivity.json \
		--policy P2 --figures

sensitivity-all: sensitivity sensitivity-fc sensitivity-validate surface ## Every sweep, both benchmarks

# --------------------------------------------------- parameter search (best value)
#
# The sweeps above answer "does the conclusion depend on this constant?".
# These answer "which value is best?", which needs the real pipeline because the
# intrinsic metrics are flat across most of the range. Candidates are
# pre-screened by the sweep, so only settings that can match current accuracy
# are ever run.

grace-search: ## Best P2 grace period, 1 to 21 days, end to end (5 cells, paid)
	$(PY) scripts/param_search.py --config configs/mquake_t.json --search grace

grace-search-fc: ## Same grace search on FactConsolidation
	$(PY) scripts/param_search.py --config configs/factconsolidation.json --search grace

weights-search: ## Best retrieval weighting, 6 pre-screened candidates (paid)
	$(PY) scripts/param_search.py --config configs/mquake_t.json --search weights

weights-search-fc: ## Same weighting search on FactConsolidation (the TUNING set)
	$(PY) scripts/param_search.py --config configs/factconsolidation.json --search weights

weights-search-convomem: ## Weighting search on ConvoMem
	$(PY) scripts/param_search.py --config configs/convomem.json --search weights

grace-search-convomem: ## Grace search on ConvoMem
	$(PY) scripts/param_search.py --config configs/convomem.json --search grace

# --------------------------------------------------- external-validity probes

frontier: ## Confirmatory cells with a frontier answer model (paid, 4 cells)
	$(PY) -m drift.runner --config configs/frontier_mquake_t.json

judge-upgrade: ## Regrade the MQuAKE-T matrix with a frontier judge (answers cached)
	$(PY) -m drift.runner --config configs/judge_upgrade_mquake_t.json

# ---------------------------------------------------------------- final matrix
#
# Five answer models (two frontier, one mid, two small) x seven policies x the
# three thesis benchmarks, graded by one fixed judge. Every target stops starting
# new cells once BUDGET dollars have been spent in that invocation; completed
# cells are skipped on rerun, so stopping and resuming costs nothing.

BUDGET ?= 18
JUDGE_CHEAP ?= openrouter:deepseek/deepseek-v4.1-flash
JUDGE_REF ?= openrouter:anthropic/claude-sonnet-5.5

final-check: ## Ping every model in the final configs (a few cents)
	-$(PY) scripts/check_providers.py --config configs/final_mquake_t.json
	-$(PY) scripts/check_providers.py --config configs/final_convomem.json
	-$(PY) scripts/check_providers.py --config configs/rq4_normalized.json

judge-check: ## DeepSeek judge vs Claude Sonnet 5.5 on 200 existing answers (about $0.30)
	$(PY) scripts/judge_agreement.py --cheap $(JUDGE_CHEAP) --reference $(JUDGE_REF) --n 200

final-pilot: ## P0 and P2 on MQuAKE-T for all five models, to measure real cost (about $1-2)
	$(PY) -m drift.runner --config configs/final_mquake_t.json --policies P0,P2 --budget 3

final-mq: ## Final matrix on MQuAKE-T
	$(PY) -m drift.runner --config configs/final_mquake_t.json --budget $(BUDGET)

final-fc: ## Final matrix on FactConsolidation
	$(PY) -m drift.runner --config configs/final_factconsolidation.json --budget $(BUDGET)

final-cm: ## Final matrix on ConvoMem
	$(PY) -m drift.runner --config configs/final_convomem.json --budget $(BUDGET)

grace-history: ## P2 grace sweep with history questions, retrieval only (free, needs Ollama)
	$(PY) -m analysis.grace_history run --config configs/grace_history.json
	$(PY) -m analysis.grace_history analyze --config configs/grace_history.json

grace-history-answers: ## Same sweep answered by the two small models and judged (about $2-4)
	$(PY) -m analysis.grace_history run --config configs/grace_history.json --answers
	$(PY) -m analysis.grace_history analyze --config configs/grace_history.json

heldout-weights: ## Search winners vs 0.6/0.3/0.1 on held-out FactConsolidation (about $0.50)
	$(PY) -m drift.runner --config configs/heldout_weights_fc_w631.json
	$(PY) -m drift.runner --config configs/heldout_weights_fc_w912.json
	$(PY) -m drift.runner --config configs/heldout_weights_fc_w811.json
	$(PY) scripts/heldout_weights.py

preflight: ## Extract every session once with DeepSeek (about $0.50), then report detection coverage
	$(PY) scripts/preflight_final.py

substrate: ## P2 under exact and LLM relation matching, two small models (about $1-2)
	for b in mquake_t factconsolidation convomem; do for m in exact llm; do \
		$(PY) -m drift.runner --config configs/substrate_$${b}_$${m}.json; done; done

final-report: ## Deep analysis of everything above -> paper/FINAL_ANALYSIS.md (free)
	$(PY) -m analysis.final_report

rq4: ## Multi-writer memory: exact vs normalised vs LLM relation matching (about $5-8)
	$(PY) -m drift.swarm --config configs/rq4_exact.json --budget 8
	$(PY) -m drift.swarm --config configs/rq4_normalized.json --budget 10
	$(PY) -m drift.swarm --config configs/rq4_llm.json --budget 8

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
