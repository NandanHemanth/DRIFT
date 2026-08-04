.PHONY: test smoke locomo tables swarm swarm-real figures dashboard clean \
        longmemeval-data longmemeval real-all record ku-data ku

longmemeval-data:
	python scripts/download_longmemeval.py --max-questions 150

longmemeval:
	python -m drift.runner --config configs/longmemeval.json

# LongMemEval knowledge-update staleness benchmark. The only dataset in the repo
# where the staleness metric can actually fire on real (non-synthetic) data:
# stale_answer is derived from the pre-update value marked in LongMemEval's own
# has_answer turns. Built from the 's' variant (~50 haystack sessions/question)
# so forgetting policies face realistic retrieval pressure.
# Needs `ollama serve` running for the annotator; ~78 cached calls.
ku-data:
	python scripts/build_longmemeval_ku.py --variant s

ku:
	python -m drift.runner --config configs/longmemeval_ku.json

# The full real-data campaign. Everything is resumable: rerun after any
# interruption or quota exhaustion and completed cells / cached calls are free.
real-all:
	-python scripts/download_locomo.py
	-python scripts/download_longmemeval.py --max-questions 150
	-python scripts/build_longmemeval_ku.py --variant s
	python -m drift.runner --config configs/locomo.json
	python -m drift.runner --config configs/longmemeval.json
	python -m drift.runner --config configs/longmemeval_ku.json
	python -m drift.swarm --config configs/swarm_real.json
	-python analysis/plots.py results/locomo
	-python analysis/plots.py results/longmemeval
	-python analysis/plots.py results/longmemeval_ku
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
