.PHONY: test smoke locomo tables swarm swarm-real figures dashboard clean \
        longmemeval-data longmemeval real-all

longmemeval-data:
	python scripts/download_longmemeval.py --max-questions 150

longmemeval:
	python -m drift.runner --config configs/longmemeval.json

# The full real-data campaign. Everything is resumable: rerun after any
# interruption or quota exhaustion and completed cells / cached calls are free.
real-all:
	-python scripts/download_locomo.py
	-python scripts/download_longmemeval.py --max-questions 150
	python -m drift.runner --config configs/locomo.json
	python -m drift.runner --config configs/longmemeval.json
	python -m drift.swarm --config configs/swarm_real.json
	-python analysis/plots.py results/locomo
	-python analysis/plots.py results/longmemeval
	-python analysis/plots.py results/swarm_real --swarm
	python analysis/dashboard.py results/* -o docs/dashboard.html

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

locomo-data:
	python scripts/download_locomo.py

locomo:
	python -m drift.runner --config configs/locomo.json

tables:
	python analysis/report_tables.py results/smoke

clean:
	rm -rf .drift_cache results/smoke __pycache__ .pytest_cache
