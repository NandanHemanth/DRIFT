.PHONY: test smoke locomo tables clean

test:
	python -m pytest tests/ -v

smoke:
	python -m drift.runner --config configs/smoke.json

locomo-data:
	python scripts/download_locomo.py

locomo:
	python -m drift.runner --config configs/locomo.json

tables:
	python analysis/report_tables.py results/smoke

clean:
	rm -rf .drift_cache results/smoke __pycache__ .pytest_cache
