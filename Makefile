.PHONY: test smoke locomo tables swarm swarm-real figures dashboard clean \
        longmemeval-data longmemeval real-all record ku-data ku ku-data-s ku-s \
        fc-data fc

longmemeval-data:
	python scripts/download_longmemeval.py --max-questions 150

longmemeval:
	python -m drift.runner --config configs/longmemeval.json

# LongMemEval knowledge-update staleness benchmark: the only dataset in the repo
# where staleness can fire on real (non-synthetic) data. stale_answer is derived
# from the pre-update value marked in LongMemEval's own has_answer turns.
#
# Two builds, forming a haystack-size ablation on the SAME 78 questions:
#   ku-data    'oracle'  ~2.6 sessions/question  (~200 total) -- cheap, ~1h ingest
#   ku-data-s  's' capped at 12 sessions/question (~900 total) -- retrieval pressure
# The uncapped 's' variant (~50/question, 3.7k sessions, ~9.6M extraction tokens)
# is NOT deliverable on free-tier providers: their per-minute token ceilings
# throttle a ~3k-token session prompt to roughly one call a minute.
#
# The annotator defaults to local ollama:gpt-oss:20b, so `ollama serve` must be
# running. Pass --annotator groq:llama-3.3-70b-versatile to use a hosted one.
ku-data:
	python scripts/build_longmemeval_ku.py --variant oracle

ku-data-s:
	python scripts/build_longmemeval_ku.py --variant s --max-sessions 12

ku:
	python -m drift.runner --config configs/longmemeval_ku.json

ku-s:
	python -m drift.runner --config configs/longmemeval_ku_s.json

# MemoryAgentBench FactConsolidation (ICLR 2026, arXiv:2507.05257, MIT).
# The strongest staleness benchmark available: later facts overwrite earlier ones
# on the same (subject, predicate) and the gold answer is always the latest
# value, so stale_answer is recoverable without an LLM annotator -- 65/100
# questions on the 6k split, vs 0/300 on LoCoMo and 0/150 on LongMemEval.
# Needs `functional_predicates: "*"` (set in the config): the substrate default
# only covers personal-life predicates, under which this corpus records zero
# invalidations and P2 looks inert for reasons unrelated to the policy.
# --context {6k,32k,64k,262k} is a built-in retrieval-pressure ablation.
fc-data:
	python scripts/download_factconsolidation.py --context 6k --hop sh

fc:
	python -m drift.runner --config configs/factconsolidation.json

# The full real-data campaign. Everything is resumable: rerun after any
# interruption or quota exhaustion and completed cells / cached calls are free.
real-all:
	-python scripts/download_locomo.py
	-python scripts/download_longmemeval.py --max-questions 150
	-python scripts/build_longmemeval_ku.py --variant oracle
	-python scripts/download_factconsolidation.py --context 6k --hop sh
	python -m drift.runner --config configs/locomo.json
	python -m drift.runner --config configs/longmemeval.json
	python -m drift.runner --config configs/longmemeval_ku.json
	python -m drift.runner --config configs/factconsolidation.json
	python -m drift.swarm --config configs/swarm_real.json
	-python analysis/plots.py results/locomo
	-python analysis/plots.py results/longmemeval
	-python analysis/plots.py results/longmemeval_ku
	-python analysis/plots.py results/factconsolidation
	-python analysis/plots.py results/swarm_real --swarm
	python analysis/dashboard.py results/* -o docs/dashboard.html
	python analysis/record.py results/*

# Evidence pack: tables (md+csv), radar, baseline-vs-DRIFT, memory/pruned-fact
# views, per-cell graph views, architecture diagram -> results/*/report_pack/
record:
	python analysis/record.py results/*

test:
	python -m pytest tests/ -v

smoke:
	python -m drift.runner --config configs/smoke.json

swarm:
	python -m drift.swarm --config configs/swarm_smoke.json

swarm-real:
	python -m drift.swarm --config configs/swarm_real.json

figures:
	python analysis/plots.py results/smoke
	python analysis/plots.py results/swarm_smoke --swarm
	-python analysis/plots.py results/locomo
	-python analysis/plots.py results/longmemeval
	-python analysis/plots.py results/longmemeval_ku
	-python analysis/plots.py results/factconsolidation
	-python analysis/plots.py results/swarm_real --swarm

dashboard:
	python analysis/dashboard.py results/* -o docs/dashboard.html

# Downloads the full LoCoMo benchmark AND derives a stratified 300-question
# sample (same conversations, full session histories, fewer probe questions)
# so the 6-policy x 5-model matrix fits free-tier judge quotas (~1500/day) in
# days rather than the ~40 days the full 1,986-question x 30-cell matrix
# would need. configs/locomo.json points at the sample by default; rerun with
# --sample-size omitted, or a larger value, to widen it once quota allows.
locomo-data:
	python scripts/download_locomo.py
	python scripts/download_locomo.py --in data/locomo_drift.json \
		--out data/locomo_drift_sample.json --sample-size 300

locomo:
	python -m drift.runner --config configs/locomo.json

tables:
	python analysis/report_tables.py results/smoke

clean:
	rm -rf .drift_cache results/smoke __pycache__ .pytest_cache
